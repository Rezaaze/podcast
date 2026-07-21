"""TEST-GATE 2 — Stage-A-Integration mit FakeModel (§ Stage A, §10.2, §2.10).

Beweist: Canon→Arc→Episode assembliert, Exclusion-List korrekt gereicht, kein
Doppel-Climax, Checkpoint resumt, Assembly validiert.
"""

import json
import tempfile
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.checkpoint import CheckpointStore
from factory.core.model import FakeModel
from factory.core.queue import WorkQueue
from factory.core.validator import validate_series
from factory.authoring.conceive import ConceiveConfig, conceive
from factory.authoring.reconciliation import reconcile


def _parse_payload(prompt: str) -> dict:
    return json.loads(prompt.split("\n", 1)[1])


# Ein deterministischer "Autor": Canon/Arc fest, Episoden-Sections inszenieren GENAU die
# zugewiesenen Turning-Points (ehrliche Allokation → saubere Reconciliation).
def _honest_router(prompt: str, schema: dict) -> dict:
    if prompt.startswith("[CANON]"):
        return {
            "cast": [{"role": "NARRATOR", "voice": "v_narr"},
                     {"role": "DETECTIVE", "voice": "v_det"}],
            "locations": [{"key": "manor", "description": "a cold manor"}],
            "threads": [{"label": "the_case", "resolution": "butler did it",
                         "hard_facts": ["a knife"]}],
        }
    if prompt.startswith("[ARC]"):
        return {
            "turning_points": [
                {"id": "tp0", "description": "body found", "episode": 0},
                {"id": "tp1", "description": "confession", "episode": 1},
            ],
            "episodes": [
                {"figure": "DETECTIVE", "theme": "arrival"},
                {"figure": "DETECTIVE", "theme": "reckoning"},
            ],
        }
    # EPISODE
    payload = _parse_payload(prompt)
    ei = payload["episode_index"]
    assigned = payload["assigned_turning_points"]
    what = " ".join(["the", "detective", "carefully", "examines", "the", "scene",
                     "and", "questions", "the", "staff", "at", "length"])
    sections = [{
        "title": f"scene {ei}", "what": what,
        "who": ["DETECTIVE", "NARRATOR"], "thread": "the_case", "word_budget": 300,
        "turning_point": assigned[0]["id"] if assigned else None,
    }]
    # None-turning_point-Feld wieder entfernen, wenn keiner zugewiesen (Schema erlaubt Fehlen)
    if sections[0]["turning_point"] is None:
        del sections[0]["turning_point"]
    return {"sections": sections, "intro": "prev", "outro": "next"}


class ConceiveIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.cp = CheckpointStore(self._dir.name)
        self.cfg = ConceiveConfig(topic="Manor Murders", format="crime_drama")

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_assembles_valid_record(self) -> None:
        model = FakeModel(router=_honest_router)
        record = conceive(self.cfg, model, self.cp, queue=WorkQueue(max_in_flight=4))
        report = validate_series(record)
        self.assertTrue(report.is_valid, msg=str(report))
        self.assertEqual(len(record["episodes"]), 2)
        self.assertEqual(record["episodes"][0]["theme"], "arrival")

    def test_no_double_climax_reconciliation_clean(self) -> None:
        model = FakeModel(router=_honest_router)
        record = conceive(self.cfg, model, self.cp)
        # Arc rekonstruieren fürs Reconcile-Check
        tps = [{"id": "tp0", "description": "", "episode": 0},
               {"id": "tp1", "description": "", "episode": 1}]
        self.assertEqual(reconcile(tps, record["episodes"]), [])

    def test_exclusion_list_is_passed_to_each_episode(self) -> None:
        seen_exclusions = {}

        def spy_router(prompt: str, schema: dict) -> dict:
            if prompt.startswith("[EPISODE]"):
                p = _parse_payload(prompt)
                seen_exclusions[p["episode_index"]] = [
                    tp["id"] for tp in p["exclude_turning_points"]
                ]
            return _honest_router(prompt, schema)

        model = FakeModel(router=spy_router)
        conceive(self.cfg, model, self.cp)
        # Episode 0 bekommt tp1 als Exclusion, Episode 1 bekommt tp0 — nie die eigene.
        self.assertEqual(seen_exclusions[0], ["tp1"])
        self.assertEqual(seen_exclusions[1], ["tp0"])

    def test_checkpoint_resumes_only_missing(self) -> None:
        # Erster Lauf füllt den Checkpoint; zweiter Lauf darf das Modell NICHT erneut rufen.
        model1 = FakeModel(router=_honest_router)
        rec1 = conceive(self.cfg, model1, self.cp)
        first_call_count = len(model1.calls)
        self.assertGreater(first_call_count, 0)

        model2 = FakeModel(router=_honest_router)   # frisch: würde bei Miss aufgerufen
        rec2 = conceive(self.cfg, model2, self.cp)
        self.assertEqual(rec1, rec2)
        self.assertEqual(len(model2.calls), 0)      # alles aus dem Checkpoint


if __name__ == "__main__":
    unittest.main()
