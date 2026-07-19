"""TEST-GATE 7 — Orchestrierung & End-to-End (§8).

Voller A→B→C-Durchlauf durch die Steuerschicht mit Fakes (kein LLM/TTS/ffmpeg), auf einem
echten Workspace auf Platte. Plus Device-Lock-Serialisierung, Cockpit-Isolation, Status,
Missing⇒Default.
"""

import json
import os
import tempfile
import threading
import time
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.checkpoint import CheckpointStore
from factory.core.model import FakeModel
from factory.core.queue import WorkQueue
from factory.core.state import StateStore
from factory.core.workspace import get_latest, reserve_series, set_latest
from factory.authoring.conceive import ConceiveConfig
from factory.media.jobs import Job
from factory.orchestration.cockpit import Cockpit
from factory.orchestration.config import get_flag
from factory.orchestration.locks import DeviceLock
from factory.orchestration.pipeline import (
    PipelineContext,
    run_pipeline,
    scripts_path,
    series_record_path,
    status,
)


# ── ein Router, der ALLE Stufen bedient (Stage A: CANON/ARC/EPISODE, Stage B: SECTION/REVIEW) ──
def _router(prompt: str, schema: dict) -> dict:
    if prompt.startswith("[CANON]"):
        return {
            "cast": [{"role": "NARRATOR", "voice": "v_narr"},
                     {"role": "DET", "voice": "v_det"}],
            "locations": [{"key": "manor", "description": "a cold manor"}],
            "threads": [{"label": "the_case", "resolution": "butler did it",
                         "hard_facts": ["a knife"]}],
        }
    if prompt.startswith("[ARC]"):
        return {
            "turning_points": [{"id": "tp0", "description": "body", "episode": 0},
                               {"id": "tp1", "description": "confession", "episode": 1}],
            "episodes": [{"figure": "DET", "theme": "arrival"},
                         {"figure": "DET", "theme": "reckoning"}],
        }
    if prompt.startswith("[EPISODE]"):
        p = json.loads(prompt.split("\n", 1)[1])
        ei = p["episode_index"]
        assigned = p["assigned_turning_points"]
        sec = {
            "title": f"scene {ei}",
            "what": "the detective carefully examines the scene and questions the staff",
            "who": ["DET", "NARRATOR"], "thread": "the_case", "word_budget": 12,
        }
        if assigned:
            sec["turning_point"] = assigned[0]["id"]
        return {"sections": [sec], "intro": "prev", "outro": "next"}
    if prompt.startswith("[SECTION]"):
        p = json.loads(prompt.split("\n")[1])
        target = p["write_section"]["word_budget"]
        return {"lines": [{"speaker": "DET", "text": " ".join(["clue"] * target)}]}
    if prompt.startswith("[REVIEW]"):
        return {"findings": []}
    raise AssertionError(f"unexpected prompt: {prompt[:30]}")


class FakeBackend:
    def __init__(self) -> None:
        self.calls = []

    def render(self, job: Job, episode_index: int, chunk_index: int) -> str:
        self.calls.append((episode_index, chunk_index))
        return f"ep{episode_index}_chunk{chunk_index}.wav"


class PipelineE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        self._root = tempfile.TemporaryDirectory()
        self._st = tempfile.TemporaryDirectory()
        self._cp = tempfile.TemporaryDirectory()
        self.ws = reserve_series(os.path.join(self._root.name, "series"), "manor")
        self.merged = []

    def tearDown(self) -> None:
        self._root.cleanup(); self._st.cleanup(); self._cp.cleanup()

    def _merge(self, paths, ep_index):
        self.merged.append((ep_index, list(paths)))
        return {"episode_path": f"ep{ep_index}.mp3", "part_offsets": list(range(len(paths)))}

    def _ctx(self, model, backend):
        return PipelineContext(
            workspace=self.ws, model=model,
            state=StateStore(self._st.name), checkpoints=CheckpointStore(self._cp.name),
            queue=WorkQueue(max_in_flight=4), backend=backend, merge_fn=self._merge,
            device_lock=DeviceLock(self._st.name, "tts"),
        )
    # capabilities=[] → kein Review-Call, damit Resume 0 Modell-Calls beweisen kann
    _CFG = ConceiveConfig(topic="Manor Murders", format="crime_drama", capabilities=[])

    def test_full_run_produces_all_stage_outputs(self) -> None:
        ctx = self._ctx(FakeModel(router=_router), FakeBackend())
        out = run_pipeline(ctx, self._CFG)
        # Stufengrenzen sind physisch: Dateien liegen in ihren Stage-Ordnern.
        self.assertTrue(os.path.isfile(series_record_path(self.ws)))
        self.assertTrue(os.path.isfile(scripts_path(self.ws)))
        self.assertEqual(len(out["record"]["episodes"]), 2)
        self.assertEqual(len(out["audio"]), 2)
        # Status: alles fertig, aus dem State-Record abgeleitet.
        st = status(ctx, out["record"])
        self.assertTrue(st.stages["01_concept"])
        self.assertTrue(st.stages["02_scripts"])
        self.assertTrue(st.stages["03_audio"])
        self.assertTrue(all(e.complete for e in st.episodes))

    def test_rerun_is_idempotent_no_model_or_backend_calls(self) -> None:
        state = StateStore(self._st.name)
        cp = CheckpointStore(self._cp.name)
        ctx1 = PipelineContext(self.ws, FakeModel(router=_router), state, cp,
                               queue=WorkQueue(4), backend=FakeBackend(), merge_fn=self._merge,
                               device_lock=DeviceLock(self._st.name))
        run_pipeline(ctx1, self._CFG)

        m2, b2 = FakeModel(router=_router), FakeBackend()
        ctx2 = PipelineContext(self.ws, m2, state, cp, queue=WorkQueue(4),
                               backend=b2, merge_fn=self._merge,
                               device_lock=DeviceLock(self._st.name))
        run_pipeline(ctx2, self._CFG)
        self.assertEqual(len(m2.calls), 0)   # alles resumt (Concept-Datei + Section-States)
        self.assertEqual(len(b2.calls), 0)   # keine Chunks neu gerendert

    def test_partial_resume_after_concept_only(self) -> None:
        # Nur Stage A laufen lassen, dann alles: Stage A wird nicht neu erzeugt.
        from factory.orchestration.pipeline import run_concept, run_scripts
        ctx = self._ctx(FakeModel(router=_router), FakeBackend())
        run_concept(ctx, self._CFG)
        calls_after_concept = len(ctx.model.calls)
        run_concept(ctx, self._CFG)   # nochmal — darf nicht regenerieren
        self.assertEqual(len(ctx.model.calls), calls_after_concept)


class DeviceLockTest(unittest.TestCase):
    def test_same_device_serializes(self) -> None:
        d = tempfile.TemporaryDirectory()
        lock = DeviceLock(d.name, "tts")
        order = []

        def worker(tag):
            with lock.acquire():
                order.append(f"{tag}-in")
                time.sleep(0.05)
                order.append(f"{tag}-out")

        t1 = threading.Thread(target=worker, args=("A",))
        t2 = threading.Thread(target=worker, args=("B",))
        t1.start(); t2.start(); t1.join(); t2.join()
        # keine Verschachtelung: jedes in/out-Paar ist zusammenhängend
        self.assertIn(order, [["A-in", "A-out", "B-in", "B-out"],
                              ["B-in", "B-out", "A-in", "A-out"]])
        d.cleanup()


class CockpitTest(unittest.TestCase):
    def test_active_decoupled_from_global_pointer(self) -> None:
        d = tempfile.TemporaryDirectory()
        root = os.path.join(d.name, "series")
        reserve_series(root, "a")
        reserve_series(root, "b")
        set_latest(root, "a")

        c1 = Cockpit(root)
        c2 = Cockpit(root)
        c2.adopt("b")                       # c2 übernimmt eigene Serie
        self.assertEqual(c1.active, "a")    # c1 folgt weiter dem globalen Pointer
        self.assertEqual(c2.active, "b")    # c2 ist entkoppelt
        self.assertEqual(get_latest(root), "a")   # globaler Pointer unverändert
        d.cleanup()


class MissingDefaultTest(unittest.TestCase):
    def test_missing_key_uses_default(self) -> None:
        self.assertTrue(get_flag({}, "fix", True))          # fehlt → Default True
        self.assertFalse(get_flag({"fix": False}, "fix", True))  # vorhandenes False gilt
        self.assertEqual(get_flag({"n": 0}, "n", 5), 0)     # 0 ist kein „fehlt"


if __name__ == "__main__":
    unittest.main()
