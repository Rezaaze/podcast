"""TEST-GATE 3 — deterministische Stage-B-Bausteine (§ Stage B)."""

import unittest

from tests import _bootstrap  # noqa: F401

from factory.authoring.hazard import scan_hazards
from factory.authoring.phrase_guard import build_phrase_report, ngrams
from factory.authoring.word_budget import check_word_budget


def _words(n: int) -> str:
    return " ".join(["word"] * n)


class WordBudgetTest(unittest.TestCase):
    def test_within_band_is_ok(self) -> None:
        self.assertTrue(check_word_budget(_words(10), 10).ok)

    def test_overlength_is_accepted_never_retried(self) -> None:
        res = check_word_budget(_words(30), 10)
        self.assertTrue(res.ok)                     # akzeptiert
        self.assertIn("overlength", res.detail)     # nur eine Warnung

    def test_too_short_retries(self) -> None:
        res = check_word_budget(_words(3), 10)
        self.assertFalse(res.ok)
        self.assertFalse(res.fatal)                 # soft → best-effort möglich
        self.assertGreater(res.badness, 0)

    def test_badness_grows_with_shortfall(self) -> None:
        near = check_word_budget(_words(8), 10).badness
        far = check_word_budget(_words(2), 10).badness
        self.assertGreater(far, near)


class HazardTest(unittest.TestCase):
    def test_clean_lines_no_hazard(self) -> None:
        lines = [{"speaker": "NARRATOR", "text": "A cold morning at the manor."},
                 {"speaker": "DET", "text": "Who was here last night?"}]
        self.assertEqual(scan_hazards(lines), [])

    def test_narrator_leak_flagged(self) -> None:
        lines = [{"speaker": "NARRATOR", "text": "Now we begin scene 3 of the case."}]
        kinds = {h.kind for h in scan_hazards(lines)}
        self.assertIn("narrator_leak", kinds)

    def test_bare_tp_label_leak(self) -> None:
        lines = [{"speaker": "NARRATOR", "text": "This is tp0 unfolding."}]
        self.assertTrue(any(h.kind == "narrator_leak" for h in scan_hazards(lines)))

    def test_letterless_line_flagged(self) -> None:
        lines = [{"speaker": "DET", "text": "!!! ??? ..."}]
        self.assertTrue(any(h.kind == "letterless" for h in scan_hazards(lines)))

    def test_placeholder_and_markup_flagged(self) -> None:
        lines = [{"speaker": "DET", "text": "He said [TODO: fill in] and **paused**."}]
        kinds = {h.kind for h in scan_hazards(lines)}
        self.assertIn("placeholder", kinds)
        self.assertIn("markup", kinds)

    def test_foreign_script_flagged_for_latin_language(self) -> None:
        lines = [{"speaker": "DET", "text": "He whispered 你好 softly."}]
        self.assertTrue(any(h.kind == "foreign_script" for h in scan_hazards(lines, language="en")))

    def test_foreign_script_allowed_for_chinese(self) -> None:
        lines = [{"speaker": "DET", "text": "他说 你好"}]
        self.assertEqual([h for h in scan_hazards(lines, language="zh") if h.kind == "foreign_script"], [])


class PhraseGuardTest(unittest.TestCase):
    def test_ngrams_basic(self) -> None:
        self.assertEqual(ngrams("a b c d", 2), [("a", "b"), ("b", "c"), ("c", "d")])

    def test_repeated_phrase_flagged(self) -> None:
        texts = ["the cold wind blew", "again the cold wind blew"]
        report = build_phrase_report(texts, n=3)
        joined = report.avoid_block.lower()
        self.assertIn("cold wind blew", joined)

    def test_proper_names_exempt(self) -> None:
        # "detective sarah smith" wiederholt, aber alles Eigennamen → nicht geflaggt.
        texts = ["detective sarah smith arrived", "detective sarah smith left"]
        report = build_phrase_report(
            texts, exempt_names=["detective", "sarah", "smith"], n=3,
        )
        self.assertEqual(report.offenders, [])

    def test_no_repetition_reports_clean(self) -> None:
        report = build_phrase_report(["alpha beta gamma", "delta epsilon zeta"], n=3)
        self.assertEqual(report.avoid_block, "")
        self.assertIn("no", report.report.lower())


if __name__ == "__main__":
    unittest.main()
