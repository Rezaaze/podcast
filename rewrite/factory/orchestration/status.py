"""Status aus dem Dateisystem/State-Record (T7.3, §8).

Das Folder-als-Pipeline-Modell (§2) plus der State-Record (§10.3) machen „was ist
fertig/fehlt" zu einem reinen Read — keine Generierung, keine Interpretation von
Datei-Existenz. Die Steuerfläche (Cockpit) rendert genau diese Struktur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from factory.core.state import StateStore

STAGE_UNIT = "stage:{name}"      # State-Record-Key für „Stufe N fertig"
SECTION_UNIT = "ep{ep}/sec{sec}"


def stage_unit(name: str) -> str:
    return STAGE_UNIT.format(name=name)


@dataclass
class EpisodeStatus:
    episode: int
    sections_total: int
    sections_done: int

    @property
    def complete(self) -> bool:
        return self.sections_total > 0 and self.sections_done == self.sections_total


@dataclass
class SeriesStatus:
    stages: Dict[str, bool] = field(default_factory=dict)
    episodes: List[EpisodeStatus] = field(default_factory=list)


def series_status(record: Dict[str, Any], state: StateStore, stages: List[str]) -> SeriesStatus:
    """Reine Ableitung aus dem State-Record: pro Stufe done?, pro Episode fertige Sections."""
    out = SeriesStatus()
    for name in stages:
        out.stages[name] = state.is_done(stage_unit(name))
    for ei, ep in enumerate(record.get("episodes", [])):
        total = len(ep.get("sections", []))
        done = sum(
            1 for si in range(total)
            if state.is_done(SECTION_UNIT.format(ep=ei, sec=si))
        )
        out.episodes.append(EpisodeStatus(episode=ei, sections_total=total, sections_done=done))
    return out
