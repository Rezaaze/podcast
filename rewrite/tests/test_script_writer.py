"""TEST-GATE 3 — Stage-B-Integration mit FakeModel (§10.1, §10.3, § Stage B).

Beweist: eine Kontinuitätsstrategie (voller Plan + laufende Zusammenfassung), sofort-
schreiben + Resume, Hazard-Retry, Post-Check gated auf Capability.
"""

import json
import tempfile
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.checkpoint import CheckpointStore
from factory.core.model import FakeModel
from factory.core.state import StateStore, Status
from factory.authoring.script_writer import section_text, write_series


def _record(with_review: bool = False) -> dict:
    caps = ["needs_continuity_review"] if with_review else []
    return {
        "schema_version": 1,
        "identity": {"title": "T", "language": "en", "mode": "drama", "format": "crime_drama"},
        "cast": [{"role": "NARRATOR", "voice": "v1"}, {"role": "DET", "voice": "v2"}],
        "locations": [],
        "capabilities": caps,
        "threads": [{"label": "the_case", "resolution": "butler", "hard_facts": ["knife"]}],
        "episodes": [
            {"figure": "DET", "theme": "arrival", "sections": [
                {"title": "s0", "what": "arrival", "who": ["DET"], "thread": "the_case", "word_budget": 10},
                {"title": "s1", "what": "clue", "who": ["DET"], "thread": "the_case", "word_budget": 10},
            ]},
            {"figure": "DET", "theme": "reckoning", "sections": [
                {"title": "s0", "what": "confront", "who": ["DET"], "thread": "the_case", "word_budget": 10},
            ]},
        ],
    }


def _clean_section(target: int = 10) -> dict:
    return {"lines": [{"speaker": "DET", "text": " ".join(["clue"] * target)}]}


def _router(prompt: str, schema: dict) -> dict:
    if prompt.startswith("[REVIEW]"):
        return {"findings": []}
    payload = json.loads(prompt.split("\n")[1])
    target = payload["write_section"]["word_budget"]
    return _clean_section(target)


class ScriptWriterTest(unittest.TestCase):
    def setUp(self) -> None:
        self._d1 = tempfile.TemporaryDirectory()
        self._d2 = tempfile.TemporaryDirectory()
        self.state = StateStore(self._d1.name)
        self.cp = CheckpointStore(self._d2.name)

    def tearDown(self) -> None:
        self._d1.cleanup()
        self._d2.cleanup()

    def test_writes_all_sections_and_marks_complete(self) -> None:
        out = write_series(_record(), FakeModel(router=_router), self.state, self.cp)
        self.assertEqual(len(out.episodes), 2)
        self.assertEqual(len(out.episodes[0]["sections"]), 2)
        self.assertTrue(self.state.is_done("ep0/sec0"))
        self.assertTrue(self.state.is_done("ep1/sec0"))

    def test_full_episode_plan_and_running_summary_in_context(self) -> None:
        seen = {"plans": [], "summaries": []}

        def spy(prompt: str, schema: dict) -> dict:
            if prompt.startswith("[SECTION]"):
                p = json.loads(prompt.split("\n")[1])
                seen["plans"].append(len(p["full_episode_plan"]))
                seen["summaries"].append(len(p["prior_episodes_summary"]))
            return _router(prompt, schema)

        write_series(_record(), FakeModel(router=spy), self.state, self.cp)
        # §10.1: jede Section sieht den VOLLEN Episodenplan (Ep0 hat 2 Sections).
        self.assertIn(2, seen["plans"])
        # Ep1-Sections sehen die Zusammenfassung von Ep0 (len 1), nicht nur den Vorgänger.
        self.assertIn(1, seen["summaries"])

    def test_resume_skips_completed_sections(self) -> None:
        write_series(_record(), FakeModel(router=_router), self.state, self.cp)
        fresh = FakeModel(router=_router)   # würde bei jedem Miss aufgerufen
        write_series(_record(), fresh, self.state, self.cp)
        self.assertEqual(len(fresh.calls), 0)   # alles resumt aus State+Checkpoint

    def test_hazard_triggers_retry_then_succeeds(self) -> None:
        attempts = {"n": 0}

        def flaky(prompt: str, schema: dict) -> dict:
            if prompt.startswith("[REVIEW]"):
                return {"findings": []}
            payload = json.loads(prompt.split("\n")[1])
            target = payload["write_section"]["word_budget"]
            attempts["n"] += 1
            if attempts["n"] == 1:
                # erster Versuch: Narrator-Leak → Hazard → Retry
                return {"lines": [{"speaker": "NARRATOR", "text": "now scene 2 begins " + " ".join(["x"] * target)}]}
            return _clean_section(target)

        out = write_series(_record(), FakeModel(router=flaky), self.state, self.cp)
        self.assertGreaterEqual(attempts["n"], 2)          # es wurde retryt
        self.assertTrue(self.state.is_done("ep0/sec0"))    # und am Ende sauber

    def test_review_runs_only_with_capability(self) -> None:
        calls = {"review": 0}

        def counting(prompt: str, schema: dict) -> dict:
            if prompt.startswith("[REVIEW]"):
                calls["review"] += 1
                return {"findings": [{"message": "spoiler in line 2", "section": 0}]}
            return _router(prompt, schema)

        # ohne Capability: kein Review
        write_series(_record(with_review=False), FakeModel(router=counting), self.state, self.cp)
        self.assertEqual(calls["review"], 0)

        # mit Capability: Review läuft und Findings landen im Ergebnis
        s2 = StateStore(tempfile.mkdtemp())
        cp2 = CheckpointStore(tempfile.mkdtemp())
        out = write_series(_record(with_review=True), FakeModel(router=counting), s2, cp2)
        self.assertGreater(calls["review"], 0)
        self.assertIn(0, out.reviews)

    def test_review_finding_triggers_section_repair(self) -> None:
        """Finding mit Section-Index → Section neu geschrieben; behoben → nicht gespeichert."""
        calls = {"repair": 0, "review": 0}

        def router(prompt: str, schema: dict) -> dict:
            if prompt.startswith("[REVIEW]"):
                calls["review"] += 1
                if calls["review"] == 1:          # nur der allererste Review flaggt
                    return {"findings": [{"message": "canon contradiction", "section": 0}]}
                return {"findings": []}           # Repair hat es behoben
            if "FIX REQUIRED" in prompt:
                calls["repair"] += 1
            return _clean_section(10)

        out = write_series(_record(with_review=True), FakeModel(router=router), self.state, self.cp)
        self.assertEqual(calls["repair"], 1)          # genau die geflaggte Section neu geschrieben
        self.assertGreaterEqual(calls["review"], 2)   # Review, dann Nach-Review
        self.assertNotIn(0, out.reviews)              # Finding hat den Repair nicht überlebt

    def test_surviving_finding_is_recorded(self) -> None:
        """Repair scheitert (Finding bleibt) → ehrlich in out.reviews, nicht verschluckt."""
        calls = {"repair": 0}

        def router(prompt: str, schema: dict) -> dict:
            if prompt.startswith("[REVIEW]"):
                return {"findings": [{"message": "still wrong", "section": 0}]}
            if "FIX REQUIRED" in prompt:
                calls["repair"] += 1
            return _clean_section(10)

        out = write_series(_record(with_review=True), FakeModel(router=router), self.state, self.cp)
        self.assertGreaterEqual(calls["repair"], 1)   # Repair wurde versucht
        self.assertIn(0, out.reviews)                 # überlebendes Finding vermerkt
        self.assertEqual(out.reviews[0][0]["message"], "still wrong")

    def test_finding_without_section_index_is_not_repaired(self) -> None:
        """Episoden-weites Finding (kein Section-Index) → kein Repair, aber vermerkt."""
        calls = {"repair": 0}

        def router(prompt: str, schema: dict) -> dict:
            if prompt.startswith("[REVIEW]"):
                return {"findings": [{"message": "episode-wide tone issue"}]}   # kein section
            if "FIX REQUIRED" in prompt:
                calls["repair"] += 1
            return _clean_section(10)

        out = write_series(_record(with_review=True), FakeModel(router=router), self.state, self.cp)
        self.assertEqual(calls["repair"], 0)          # nichts targetbar → kein Neuschreiben
        self.assertIn(0, out.reviews)                 # trotzdem ehrlich vermerkt


if __name__ == "__main__":
    unittest.main()
