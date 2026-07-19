"""TEST-GATE 4 — Media-Adapter (T4.1/T4.4/T4.5/T4.7).

Getestet wird NUR der neue Adapter (Record→Jobs, State-Bridge, Voice-Guard, Merge-Order).
Der kopierte Audio-Kern (audio_pipeline.py/tts_backends.py) braucht venv+ffmpeg und wird
hier bewusst nicht importiert — er ist produktionsbewährt (§9-incidental).
"""

import tempfile
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core import textproc
from factory.core.checkpoint import CheckpointStore
from factory.core.state import StateStore
from factory.media.jobs import NARRATOR_STYLE, Job, build_jobs
from factory.media.voice_manifest import (
    VoiceDrift,
    build_manifest,
    check_voice_consistency,
    diff_manifest,
)
from factory.media.voicing import voice_episode, voice_series


def _record() -> dict:
    return {
        "schema_version": 1,
        "identity": {"title": "T", "language": "en", "mode": "drama", "format": "crime_drama"},
        "cast": [
            {"role": "NARRATOR", "voice": "v_narr"},
            {"role": "DET", "voice": "v_det", "style": "tense", "speed": 1.1, "seed": 7},
        ],
        "locations": [],
        "capabilities": [],
        "threads": [{"label": "c", "resolution": "x"}],
        "episodes": [],
    }


def _script(*texts_by_speaker) -> dict:
    return {"sections": [{"lines": [{"speaker": sp, "text": tx} for sp, tx in texts_by_speaker]}]}


class TextprocCopyTest(unittest.TestCase):
    def test_chunking_and_speakable(self) -> None:
        sents = textproc.split_into_sentences("First one. Second one. Third one.")
        self.assertEqual(len(sents), 3)
        self.assertFalse(textproc.is_speakable("— …"))
        self.assertTrue(textproc.is_speakable("hello"))


class JobsAdapterTest(unittest.TestCase):
    def test_narrator_style_is_forced(self) -> None:
        jobs = build_jobs(_record(), _script(("NARRATOR", "A cold morning.")))
        self.assertEqual(jobs[0].style, NARRATOR_STYLE)      # harter Override
        self.assertEqual(jobs[0].voice, "v_narr")

    def test_dialogue_resolves_voice_style_speed_seed(self) -> None:
        jobs = build_jobs(_record(), _script(("DET", "Who was here?")))
        j = jobs[0]
        self.assertEqual((j.voice, j.style, j.speed, j.seed), ("v_det", "tense", 1.1, 7))

    def test_line_style_overrides_cast_default_for_non_narrator(self) -> None:
        script = {"sections": [{"lines": [{"speaker": "DET", "text": "Hi.", "style": "calm"}]}]}
        self.assertEqual(build_jobs(_record(), script)[0].style, "calm")

    def test_unspeakable_chunk_becomes_silence_job(self) -> None:
        jobs = build_jobs(_record(), _script(("DET", "—")))
        self.assertTrue(jobs[0].is_silence)

    def test_long_line_is_chunked(self) -> None:
        long = " ".join(f"Sentence number {i} here." for i in range(40))
        jobs = build_jobs(_record(), _script(("DET", long)), chunk_max_chars=80)
        self.assertGreater(len(jobs), 1)


class VoiceManifestTest(unittest.TestCase):
    def test_no_manifest_is_noop(self) -> None:
        check_voice_consistency(_record(), None)   # darf nicht werfen

    def test_consistent_manifest_passes(self) -> None:
        rec = _record()
        check_voice_consistency(rec, build_manifest(rec))

    def test_changed_voice_hard_stops(self) -> None:
        rec = _record()
        committed = build_manifest(rec)
        rec["cast"][1]["voice"] = "v_other"       # Voice nachträglich geändert
        with self.assertRaises(VoiceDrift):
            check_voice_consistency(rec, committed)

    def test_diff_reports_field(self) -> None:
        rec = _record()
        committed = build_manifest(rec)
        rec["cast"][1]["seed"] = 99
        drift = diff_manifest(committed, build_manifest(rec))
        self.assertTrue(any("DET.seed" in d for d in drift))


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list = []

    def render(self, job: Job, episode_index: int, chunk_index: int) -> str:
        self.calls.append((episode_index, chunk_index))
        return f"ep{episode_index}_chunk{chunk_index}.wav"


class VoicingOrchestrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._d1 = tempfile.TemporaryDirectory()
        self._d2 = tempfile.TemporaryDirectory()
        self.state = StateStore(self._d1.name)
        self.cp = CheckpointStore(self._d2.name)
        self.merged: list = []

    def tearDown(self) -> None:
        self._d1.cleanup()
        self._d2.cleanup()

    def _merge(self, paths, ep_index):
        self.merged.append((ep_index, list(paths)))
        return {"episode_path": f"ep{ep_index}.mp3", "part_offsets": list(range(len(paths)))}

    def test_merge_receives_chunks_in_stable_order(self) -> None:
        jobs = build_jobs(_record(), _script(*[("DET", f"Line {i}.") for i in range(6)]))
        backend = FakeBackend()
        voice_episode(_record(), 0, jobs, backend, self.state, self.cp, self._merge,
                      queue=None)
        _, paths = self.merged[0]
        # Merge-Reihenfolge = Job-Reihenfolge, egal wie die Worker fertig wurden.
        self.assertEqual(paths, [f"ep0_chunk{i}.wav" for i in range(len(jobs))])

    def test_resume_skips_rendered_chunks(self) -> None:
        jobs = build_jobs(_record(), _script(("DET", "One. Two. Three.")))
        b1 = FakeBackend()
        voice_episode(_record(), 0, jobs, b1, self.state, self.cp, self._merge)
        self.assertGreater(len(b1.calls), 0)

        b2 = FakeBackend()   # frisch — würde bei jedem Miss rendern
        voice_episode(_record(), 0, jobs, b2, self.state, self.cp, self._merge)
        self.assertEqual(b2.calls, [])   # alles resumt aus State+Checkpoint

    def test_voice_drift_hard_stops_before_any_render(self) -> None:
        rec = _record()
        committed = build_manifest(rec)
        rec["cast"][1]["voice"] = "v_changed"
        backend = FakeBackend()
        with self.assertRaises(VoiceDrift):
            voice_series(rec, [_script(("DET", "Hi."))], backend, self.state, self.cp,
                         self._merge, committed_manifest=committed)
        self.assertEqual(backend.calls, [])   # NICHTS gerendert (Guard vor Dateizugriff)

    def test_series_merges_episodes_in_index_order(self) -> None:
        rec = _record()
        scripts = [_script(("DET", "Ep zero.")), _script(("DET", "Ep one."))]
        voice_series(rec, scripts, FakeBackend(), self.state, self.cp, self._merge)
        self.assertEqual([ep for ep, _ in self.merged], [0, 1])


if __name__ == "__main__":
    unittest.main()
