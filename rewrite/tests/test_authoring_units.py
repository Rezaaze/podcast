"""TEST-GATE 2 — deterministische Stage-A-Bausteine (§2.1, §2.2, §2.6, §2.8, §2.9)."""

import tempfile
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.checkpoint import CheckpointStore, key_of
from factory.authoring.detail_band import check_detail_band, length_tier
from factory.authoring.reconciliation import reconcile
from factory.authoring.repair import Finding, dispatch_repair, partition_findings
from factory.authoring.season_fold import season_fold
from factory.authoring.substitution import substitute


class SubstitutionTest(unittest.TestCase):
    def test_replaces_and_reports_unused(self) -> None:
        s = substitute("Voices: {{roster}}.", {"roster": "A, B", "extra": "x"})
        self.assertEqual(s.text, "Voices: A, B.")
        self.assertTrue(s.ok)
        self.assertIn("extra", s.unused)

    def test_unreplaced_placeholder_is_flagged_not_silent(self) -> None:
        s = substitute("Model is {{model}} at {{limit}}.", {"model": "X"})
        self.assertFalse(s.ok)
        self.assertIn("limit", s.unreplaced)
        self.assertIn("{{limit}}", s.text)   # bleibt sichtbar stehen, nicht still weg


class SeasonFoldTest(unittest.TestCase):
    def test_each_step_sees_all_prior_results(self) -> None:
        seen = []
        out = season_fold(
            ["a", "b", "c"],
            lambda item, i, prior: (seen.append(list(prior)) or f"{item}{i}"),
        )
        self.assertEqual(out, ["a0", "b1", "c2"])
        self.assertEqual(seen, [[], ["a0"], ["a0", "b1"]])   # wächst, sieht ALLE vorigen

    def test_skip_on_error_contributes_none_and_continues(self) -> None:
        def step(item, i, prior):
            if item == "boom":
                raise RuntimeError()
            return item
        out = season_fold(["a", "boom", "c"], step, skip_on_error=True)
        self.assertEqual(out, ["a", None, "c"])

    def test_default_propagates_error(self) -> None:
        with self.assertRaises(RuntimeError):
            season_fold(["x"], lambda *_: (_ for _ in ()).throw(RuntimeError()))


class DetailBandTest(unittest.TestCase):
    def _sec(self, title, what):
        return {"title": title, "what": what}

    def test_uniform_episode_passes(self) -> None:
        secs = [self._sec("a", " ".join(["word"] * 10)),
                self._sec("b", " ".join(["word"] * 12))]
        self.assertTrue(check_detail_band(secs).ok)

    def test_lavish_plus_stub_mix_is_flagged(self) -> None:
        secs = [self._sec("lavish", " ".join(["word"] * 40)),
                self._sec("stub", " ".join(["word"] * 6))]
        res = check_detail_band(secs)
        self.assertFalse(res.ok)
        self.assertIn("spread", res.detail)

    def test_too_thin_section_flagged_with_feedback(self) -> None:
        res = check_detail_band([self._sec("thin", "two words")])
        self.assertFalse(res.ok)
        self.assertIn("thin", res.offenders)

    def test_tier_monotonic(self) -> None:
        self.assertLess(length_tier("one two three"), length_tier(" ".join(["w"] * 35)))


class ReconciliationTest(unittest.TestCase):
    def test_clean_allocation_has_no_findings(self) -> None:
        tps = [{"id": "tp1", "description": "d", "episode": 0},
               {"id": "tp2", "description": "d", "episode": 1}]
        eps = [{"sections": [{"turning_point": "tp1"}]},
               {"sections": [{"turning_point": "tp2"}]}]
        self.assertEqual(reconcile(tps, eps), [])

    def test_double_climax_is_flagged(self) -> None:
        tps = [{"id": "tp1", "description": "d", "episode": 0}]
        eps = [{"sections": [{"turning_point": "tp1"}]},
               {"sections": [{"turning_point": "tp1"}]}]   # in beiden Episoden inszeniert
        finds = reconcile(tps, eps)
        kinds = {f.kind for f in finds}
        self.assertIn("duplicated", kinds)

    def test_missing_turning_point_is_flagged(self) -> None:
        tps = [{"id": "tp9", "description": "d", "episode": 1}]
        eps = [{"sections": []}, {"sections": []}]
        finds = reconcile(tps, eps)
        self.assertEqual(finds[0].kind, "missing")
        self.assertEqual(finds[0].episode, 1)

    def test_misplaced_turning_point_is_flagged(self) -> None:
        tps = [{"id": "tp1", "description": "d", "episode": 0}]
        eps = [{"sections": []}, {"sections": [{"turning_point": "tp1"}]}]
        finds = reconcile(tps, eps)
        self.assertTrue(any(f.kind == "misplaced" and f.episode == 1 for f in finds))


class RepairDispatcherTest(unittest.TestCase):
    def test_scopeless_finding_does_not_tip_all_into_full_rebuild(self) -> None:
        # §9 Falle #3: ein scope-loses Finding darf die episoden-bezogenen NICHT
        # in den Full-Rebuild ziehen.
        findings = [Finding("ep bug", episode=2), Finding("cast rule")]
        part = partition_findings(findings)
        self.assertEqual(list(part.by_episode.keys()), [2])
        self.assertEqual(len(part.global_scoped), 1)

    def test_each_scope_repaired_with_smallest_call(self) -> None:
        calls = {"ep": [], "top": 0, "full": 0}

        def rep_ep(rec, ep, group):
            calls["ep"].append(ep)
            return {**rec, f"ep{ep}": "fixed"}

        def rep_top(rec, group):
            calls["top"] += 1
            return {**rec, "top": "fixed"}

        def full(rec, group):
            calls["full"] += 1
            return rec

        out = dispatch_repair(
            {"base": 1},
            [Finding("a", episode=1), Finding("b", episode=3), Finding("c")],
            repair_episodes=rep_ep, repair_toplevel=rep_top, full_rebuild=full,
        )
        self.assertEqual(sorted(calls["ep"]), [1, 3])
        self.assertEqual(calls["top"], 1)
        self.assertEqual(calls["full"], 0)   # kein Full-Rebuild nötig
        self.assertEqual(out.repaired_episodes, [1, 3])
        self.assertTrue(out.repaired_toplevel)

    def test_truncated_scope_keeps_partial_and_bails(self) -> None:
        def rep_ep(rec, ep, group):
            return {**rec, "trunc": True}   # kommt "abgeschnitten" zurück

        out = dispatch_repair(
            {"base": 1},
            [Finding("a", episode=1)],
            repair_episodes=rep_ep,
            repair_toplevel=lambda r, g: r,
            is_truncated=lambda r: r.get("trunc", False),
        )
        self.assertIn("episode:1", out.truncated_scopes)
        self.assertEqual(len(out.unresolved), 1)   # Finding bleibt offen, kein blinder Retry
        self.assertEqual(out.repaired_episodes, [])


class CheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.cp = CheckpointStore(self._dir.name)

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_get_or_compute_caches(self) -> None:
        calls = []
        v1 = self.cp.get_or_compute("k", lambda: (calls.append(1) or {"v": 1}))
        v2 = self.cp.get_or_compute("k", lambda: (calls.append(1) or {"v": 2}))
        self.assertEqual(v1, v2)
        self.assertEqual(len(calls), 1)   # zweiter Aufruf kam aus dem Cache

    def test_key_is_stable_and_param_sensitive(self) -> None:
        self.assertEqual(key_of("a", 1), key_of("a", 1))
        self.assertNotEqual(key_of("a", 1), key_of("a", 2))

    def test_clear_wipes(self) -> None:
        self.cp.put("k", {"v": 1})
        self.cp.clear()
        self.assertIsNone(self.cp.get("k"))


if __name__ == "__main__":
    unittest.main()
