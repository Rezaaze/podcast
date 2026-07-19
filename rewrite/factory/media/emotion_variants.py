"""Emotion-Varianten, cost-capped (T5.2, § Stage D).

Jede Rolle bekommt ein Porträt pro *tatsächlich genutzter* Emotion, gedeckelt auf die
häufigsten wenigen (eine Liebes-Subplot-Rolle behält „love"; andere nicht). Fehlende
Emotionen fallen auf das neutrale Porträt zurück.

Deterministisch (Keyword-Klassifikation + Häufigkeitsdeckel) → stdlib-testbar. Die
EMOTION_KEYWORDS sind 1:1 aus dem Altsystem übernommen, damit die Emotion→Porträt-Zuordnung
konsistent zum Downstream-Video-Mixer bleibt (dict-Reihenfolge = Match-Priorität).
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Set

MAX_EMOTIONS_PER_ROLE = 4   # Kostenbremse (§14)

# dict-Reihenfolge = Match-Priorität: "vulnerability" zuerst, damit eine Fassade-bricht-
# Regieanweisung nicht fälschlich als "joy" durchgeht. Kopie aus fabrik/cli/character_prompts.py.
EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "vulnerability": ["crack", "raw", "unguarded", "breaking through", "catching himself",
                      "catching herself", "for one line", "for one beat", "genuine",
                      "real feeling", "something real", "forced", "overcompensating",
                      "overly bright", "deflecting"],
    "anger": ["angry", "furious", "rage", "snapp", "hissing", "seething", "aggressive",
              "heated", "bitter", "hostile", "accusing", "sharp", "cutting", "defensive",
              "dismissing"],
    "fear": ["afraid", "fear", "scared", "nervous", "anxious", "panic", "tense", "trembl",
             "terrified", "uneasy", "shaky", "shaken", "shakier", "unsteady", "reeling",
             "alarmed", "dread"],
    "sadness": ["sad", "tearful", "crying", "mournful", "grief", "resigned", "defeated",
                "hollow", "heavy-hearted", "somber", "wistful", "wounded"],
    "joy": ["happy", "joyful", "cheerful", "laughing", "bright", "playful", "amused",
            "excited", "delighted", "teasing", "lighthearted"],
    "surprise": ["surprised", "shocked", "stunned", "startled", "disbelief", "astonished",
                 "incredulous", "caught off"],
    "love": ["tender", "affectionate", "loving", "intimate", "adoring", "flirt", "longing",
             "yearning"],
}


def classify_emotion(style_text: str) -> str | None:
    """Style-Regieanweisung → erste passende Emotion (dict-Priorität), sonst None."""
    if not style_text:
        return None
    lowered = style_text.lower()
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return emotion
    return None


def find_used_emotions(episode_scripts: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    """Zähle je Rolle die klassifizierten Emotionen über alle Skript-Zeilen und deckle
    auf die ``MAX_EMOTIONS_PER_ROLE`` häufigsten. Rückgabe: role → Menge der Emotionen."""
    counts: Dict[str, Counter] = {}
    for script in episode_scripts:
        for section in script.get("sections", []):
            for line in section.get("lines", []):
                emotion = classify_emotion(line.get("style", ""))
                if emotion:
                    counts.setdefault(line["speaker"], Counter())[emotion] += 1
    return {
        role: {emotion for emotion, _ in c.most_common(MAX_EMOTIONS_PER_ROLE)}
        for role, c in counts.items()
    }


def portrait_key(role: str, emotion: str | None) -> str:
    """Dateiname-Baustein: ``<ROLE>`` (neutral) oder ``<ROLE>_<emotion>``."""
    return role if emotion is None else f"{role}_{emotion}"


def resolve_portrait(role: str, emotion: str | None, available: Set[str]) -> str:
    """Löse die zu ladende Porträt-Variante auf; fehlende Emotion → neutrales Porträt."""
    if emotion is not None and emotion in available:
        return portrait_key(role, emotion)
    return portrait_key(role, None)   # neutraler Fallback
