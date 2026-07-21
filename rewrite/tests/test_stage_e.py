"""TEST-GATE 6 — Stage-E-Adapter (T6.1/T6.2/T6.3)."""

import unittest

from tests import _bootstrap  # noqa: F401

from factory.media.anthology import compute_chapters, merge_anthology
from factory.media.highlights import cue_range_to_ms, select_highlights
from factory.media.upload_index import (
    build_upload_index,
    format_ts,
    question_leaks_twist,
)


def _cues():
    return [
        {"index": 0, "start_ms": 0, "end_ms": 1000, "text": "Hello there."},
        {"index": 1, "start_ms": 1000, "end_ms": 2500, "text": "Who are you?"},
        {"index": 2, "start_ms": 2500, "end_ms": 4000, "text": "The butler."},
    ]


class HighlightTest(unittest.TestCase):
    def test_range_maps_to_cue_boundaries(self) -> None:
        h = cue_range_to_ms(_cues(), 0, 1)
        self.assertEqual((h.start_ms, h.end_ms), (0, 2500))   # snappt auf Cue-Grenzen
        self.assertIn("Hello", h.text)

    def test_out_of_range_index_is_clamped_never_hallucinated(self) -> None:
        h = cue_range_to_ms(_cues(), -5, 99)   # weit außerhalb
        self.assertEqual((h.start_ms, h.end_ms), (0, 4000))   # geklemmt auf gültige Grenzen

    def test_reversed_indices_are_normalized(self) -> None:
        h = cue_range_to_ms(_cues(), 2, 0)
        self.assertEqual((h.start_cue, h.end_cue), (0, 2))

    def test_select_caps_at_max_n(self) -> None:
        ranges = [(0, 0), (1, 1), (2, 2), (0, 2)]
        self.assertEqual(len(select_highlights(_cues(), ranges, max_n=3)), 3)

    def test_no_cues_returns_empty(self) -> None:
        self.assertEqual(select_highlights([], [(0, 1)]), [])


class AnthologyTest(unittest.TestCase):
    def test_chapters_are_cumulative(self) -> None:
        chapters = compute_chapters(["Ep1", "Ep2", "Ep3"], [60000, 90000, 30000])
        self.assertEqual([c.start_ms for c in chapters], [0, 60000, 150000])

    def test_misaligned_inputs_raise(self) -> None:
        with self.assertRaises(ValueError):
            compute_chapters(["Ep1"], [1000, 2000])

    def test_merge_uses_stream_copy_and_stable_order(self) -> None:
        seen = {}

        def fake_merge(paths, out_path):
            seen["paths"] = list(paths)
            seen["out"] = out_path

        result = merge_anthology(
            ["ep0.mp3", "ep1.mp3"], ["A", "B"], [1000, 2000],
            "anthology.mp3", fake_merge,
        )
        self.assertEqual(seen["paths"], ["ep0.mp3", "ep1.mp3"])   # Index-Reihenfolge
        self.assertEqual(result.chapters[1].start_ms, 1000)


class UploadIndexTest(unittest.TestCase):
    def test_format_ts_minutes_and_hours(self) -> None:
        self.assertEqual(format_ts(65000), "1:05")
        self.assertEqual(format_ts(3665000), "1:01:05")

    def test_index_contains_question_and_chapters(self) -> None:
        chapters = compute_chapters(["Intro", "Reveal"], [30000, 60000])
        text = build_upload_index("My Series", "Ep 1", "A tense night.",
                                  "What would you have done?", chapters)
        self.assertIn("**Question for you:**", text)
        self.assertIn("0:00 Intro", text)
        self.assertIn("0:30 Reveal", text)

    def test_spoiler_guard_flags_twist_leak(self) -> None:
        resolutions = ["the butler poisoned the wine at midnight"]
        leaky = question_leaks_twist("Did you suspect the butler and the poisoned wine?", resolutions)
        clean = question_leaks_twist("Who would you have trusted in that house?", resolutions)
        self.assertTrue(leaky)
        self.assertFalse(clean)


if __name__ == "__main__":
    unittest.main()
