"""SFX-Plan: wachsende Palette + Stale-Plan-Schutz (T5.4, § Stage D).

Der SFX-Plan ist das fehlende Glied zwischen „das Modell schrieb einen Cue im Skript" und
„ein Mixer platziert einen Sound bei Millisekunde X". Ein Call pro Episode mit *wachsender
Palette* (Episode N sieht Assets aus 1..N-1 und ist an Reuse gebunden — der Türknall in
Episode 7 klingt wie der in Episode 1). Er entscheidet pro Cue: keep/drop, welches
Palette-Asset, Placement (eigene Stille-Lücke *vor* der Zeile, oder *unter* ihr), Volume.

Der Plan adressiert Cues per **Position** — ein stale Plan wird gegen den Cue-Text
gegengeprüft und bei Mismatch ignoriert: ein veralteter Plan platziert so nie den
*falschen* Sound, nur keinen. Diese Reconcile-Logik ist deterministisch → stdlib-testbar.
Der LLM-Plan-Call selbst ist ein dünner Wrapper (nicht hier).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

PLACEMENTS = ("before", "under")
DEFAULT_PLACEMENT = "under"   # historisches Verhalten: Cue auf dem Zeilenstart


def palette_index(plan: Dict[str, Any]) -> Dict[str, Any]:
    """key → Asset-Eintrag aus dem Plan (nur Einträge mit key)."""
    return {a["key"]: a for a in plan.get("palette", []) if a.get("key")}


def grow_palette(prior_palettes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregiere die Paletten der Vorepisoden (Season-Fold-Eingabe für Episode N).

    Frühere Definition eines keys gewinnt (ein Asset wird einmal etabliert und wiederverwendet).
    """
    merged: Dict[str, Any] = {}
    for pal in prior_palettes:
        for key, asset in palette_index(pal).items():
            merged.setdefault(key, asset)
    return merged


@dataclass
class ResolvedCue:
    index: int
    text: str
    asset: str
    placement: str
    gain: float


def reconcile_cues(
    cues: List[Dict[str, Any]],
    plan_entries: List[Dict[str, Any]],
) -> List[ResolvedCue]:
    """Wende einen Plan auf die tatsächlichen Cues an; liefere nur platzierbare Cues.

    ``cues``: [{index, text}] in Skript-Reihenfolge. ``plan_entries``: [{id/index, keep,
    asset, placement, gain, cue_text}]. Regeln:
    - ``keep=false`` → verworfen (kein Sound).
    - Plan-Eintrag adressiert per Position; stimmt der aufgezeichnete ``cue_text`` nicht mit
      dem Cue an der Position überein → **ignoriert** (stale → kein Sound, nie der falsche).
    - Kein Plan-Eintrag für einen Cue → kein Sound (der LLM-Plan ist die Kuratierung).
    """
    by_index = {c["index"]: c for c in cues}
    out: List[ResolvedCue] = []
    for entry in plan_entries:
        idx = entry.get("id", entry.get("index"))
        cue = by_index.get(idx)
        if cue is None:
            continue                       # Plan verweist auf nicht existierenden Cue
        if not entry.get("keep", False):
            continue                       # bewusst verworfen (kein Geräusch)
        if entry.get("cue_text") is not None and entry["cue_text"] != cue["text"]:
            continue                       # STALE: Text passt nicht → kein Sound (nie falsch)
        if not entry.get("asset"):
            continue
        placement = entry.get("placement", DEFAULT_PLACEMENT)
        if placement not in PLACEMENTS:
            placement = DEFAULT_PLACEMENT
        out.append(ResolvedCue(
            index=idx, text=cue["text"], asset=entry["asset"],
            placement=placement, gain=float(entry.get("gain", 0.0)),
        ))
    return out
