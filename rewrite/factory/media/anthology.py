"""Anthologie-Merge + Kapitel (T6.1, § Stage E).

Optional pro Serie: die Episoden per **Stream-Copy** in eine Datei mit Kapiteln fügen —
nie re-encodiert, nie voll in RAM (das übernimmt der injizierte ``merge_fn``, in Produktion
ein ffmpeg-Stream-Copy). Formate, die Episoden einzeln ausliefern (z.B. soap_opera),
skippen den Merge, bekommen aber pro Episode einen Index.

Die Kapitel-Berechnung (kumulative Offsets aus Episodendauern) ist deterministisch →
stdlib-testbar; der Merge selbst ist injiziert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence


@dataclass
class Chapter:
    title: str
    start_ms: int


def compute_chapters(titles: Sequence[str], durations_ms: Sequence[int]) -> List[Chapter]:
    """Kumulative Kapitel-Startzeiten. ``durations_ms[i]`` ist die Länge von Episode i."""
    if len(titles) != len(durations_ms):
        raise ValueError("titles and durations_ms must align")
    chapters: List[Chapter] = []
    offset = 0
    for title, dur in zip(titles, durations_ms):
        chapters.append(Chapter(title=title, start_ms=offset))
        offset += int(dur)
    return chapters


# merge_fn(ordered_episode_paths, out_path) -> None  (ffmpeg stream-copy, in Produktion)
MergeFn = Callable[[List[str], str], None]


@dataclass
class AnthologyResult:
    out_path: str
    chapters: List[Chapter]


def merge_anthology(
    episode_paths: Sequence[str],
    titles: Sequence[str],
    durations_ms: Sequence[int],
    out_path: str,
    merge_fn: MergeFn,
) -> AnthologyResult:
    """Merge in **stabiler Reihenfolge** (Episoden-Index) + Kapitel. Kein Re-Encode (merge_fn)."""
    paths = list(episode_paths)
    chapters = compute_chapters(titles, durations_ms)
    merge_fn(paths, out_path)   # ffmpeg stream-copy in Produktion
    return AnthologyResult(out_path=out_path, chapters=chapters)
