"""TEST-GATE 5 — Stage-D-Adapter (T5.1/T5.2/T5.3/T5.4).

Getestet wird die deterministische Adapter-Logik; die eigentliche Bild-/Sound-Generierung
(§9-incidental, kostenpflichtig, nie automatisch) wird aus fabrik/ adaptiert, nicht hier gebaut.
"""

import unittest

from tests import _bootstrap  # noqa: F401

from factory.media.asset_reuse import classify_reuse, fuzzy_score
from factory.media.emotion_variants import (
    MAX_EMOTIONS_PER_ROLE,
    classify_emotion,
    find_used_emotions,
    resolve_portrait,
)
from factory.media.prompt_render import keys_needing_prompt, keys_needing_render
from factory.media.sfx_plan import grow_palette, reconcile_cues


def _line(speaker, style=""):
    return {"speaker": speaker, "text": "x", "style": style}


def _script(*lines):
    return {"sections": [{"lines": list(lines)}]}


class EmotionVariantTest(unittest.TestCase):
    def test_classify_priority_vulnerability_over_joy(self) -> None:
        # "forced ... bright" enthält joy-Keyword "bright", aber vulnerability hat Priorität.
        self.assertEqual(classify_emotion("a forced, overly bright smile"), "vulnerability")

    def test_no_match_returns_none(self) -> None:
        self.assertIsNone(classify_emotion("speaking normally"))

    def test_cost_cap_limits_emotions_per_role(self) -> None:
        # DET bekommt 5 verschiedene Emotionen unterschiedlich oft; Deckel = 4.
        lines = []
        for style, n in [("furious", 5), ("afraid", 4), ("sad", 3), ("happy", 2), ("tender", 1)]:
            lines += [_line("DET", style)] * n
        used = find_used_emotions([_script(*lines)])
        self.assertLessEqual(len(used["DET"]), MAX_EMOTIONS_PER_ROLE)
        self.assertNotIn("love", used["DET"])   # die seltenste ("tender") fällt raus

    def test_missing_emotion_falls_back_to_neutral(self) -> None:
        self.assertEqual(resolve_portrait("DET", "joy", available=set()), "DET")
        self.assertEqual(resolve_portrait("DET", "joy", available={"joy"}), "DET_joy")


class PromptRenderTest(unittest.TestCase):
    def test_prompt_stage_writes_only_missing_prompts(self) -> None:
        desired = ["DET", "DET_joy", "SUSPECT"]
        have_prompt = {"DET"}
        need = keys_needing_prompt(desired, lambda k: k in have_prompt)
        self.assertEqual(need, ["DET_joy", "SUSPECT"])

    def test_new_key_reaches_render_despite_existing_prompts(self) -> None:
        # Der teure Bug: eine existierende Prompt-Datei darf den Render eines NEUEN
        # Schlüssels nicht blocken. Render hängt an has_render, nicht an has_prompt.
        desired = ["DET", "DET_joy"]
        have_prompt = {"DET", "DET_joy"}     # beide Prompts existieren
        have_render = {"DET"}                # aber nur DET ist gerendert
        need = keys_needing_render(desired, lambda k: k in have_prompt, lambda k: k in have_render)
        self.assertEqual(need, ["DET_joy"])  # der neue Schlüssel erreicht den Render


class SfxPlanTest(unittest.TestCase):
    def test_palette_grows_earliest_definition_wins(self) -> None:
        p1 = {"palette": [{"key": "door", "asset": "door_v1.mp3"}]}
        p2 = {"palette": [{"key": "door", "asset": "door_v2.mp3"}, {"key": "rain", "asset": "rain.mp3"}]}
        merged = grow_palette([p1, p2])
        self.assertEqual(merged["door"]["asset"], "door_v1.mp3")   # Ep1-Türknall bleibt kanonisch
        self.assertIn("rain", merged)

    def test_kept_cue_with_matching_text_is_placed(self) -> None:
        cues = [{"index": 0, "text": "door slams"}]
        plan = [{"id": 0, "keep": True, "asset": "door.mp3", "placement": "before",
                 "gain": -3.0, "cue_text": "door slams"}]
        out = reconcile_cues(cues, plan)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].asset, out[0].placement), ("door.mp3", "before"))

    def test_dropped_cue_not_placed(self) -> None:
        cues = [{"index": 0, "text": "a beat, tension held"}]
        plan = [{"id": 0, "keep": False, "cue_text": "a beat, tension held"}]
        self.assertEqual(reconcile_cues(cues, plan), [])

    def test_stale_plan_places_no_sound_never_wrong(self) -> None:
        # Der Cue-Text hat sich geändert; der Plan-Eintrag ist stale → KEIN Sound (nie falsch).
        cues = [{"index": 0, "text": "glass shatters"}]
        plan = [{"id": 0, "keep": True, "asset": "door.mp3", "cue_text": "door slams"}]
        self.assertEqual(reconcile_cues(cues, plan), [])

    def test_unknown_placement_falls_back_to_default(self) -> None:
        cues = [{"index": 0, "text": "thud"}]
        plan = [{"id": 0, "keep": True, "asset": "t.mp3", "placement": "sideways", "cue_text": "thud"}]
        self.assertEqual(reconcile_cues(cues, plan)[0].placement, "under")


class AssetReuseTest(unittest.TestCase):
    def test_exact_hash_match(self) -> None:
        existing = {"door_a": "a heavy wooden door slamming shut"}
        d = classify_reuse("A Heavy Wooden Door Slamming Shut", existing)  # nur Case/Whitespace
        self.assertEqual(d.verdict, "exact")
        self.assertEqual(d.match_key, "door_a")

    def test_high_fuzzy_auto_reuses(self) -> None:
        existing = {"door_a": "a heavy wooden door slamming shut loudly"}
        d = classify_reuse("a heavy wooden door slamming shut", existing)
        self.assertEqual(d.verdict, "reuse")

    def test_mid_fuzzy_goes_to_audit_not_auto(self) -> None:
        # Jaccard ~0.67 (4 gemeinsam / 6 union) → im Band [0.5, 0.85) → Audit, kein Auto-Reuse.
        existing = {"door_a": "a heavy wooden door slamming"}
        d = classify_reuse("a heavy wooden door closing", existing)
        self.assertEqual(d.verdict, "audit")
        self.assertTrue(d.candidates)

    def test_no_similarity_is_new(self) -> None:
        existing = {"door_a": "a heavy wooden door slamming"}
        d = classify_reuse("distant thunder rolling over mountains", existing)
        self.assertEqual(d.verdict, "new")

    def test_fuzzy_score_bounds(self) -> None:
        self.assertEqual(fuzzy_score("a b c", "a b c"), 1.0)
        self.assertEqual(fuzzy_score("a b", "x y"), 0.0)


if __name__ == "__main__":
    unittest.main()
