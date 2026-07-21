"""Teaser-Highlights über Subtitle-Cue-Indizes (T6.3, § Stage E).

Das Modell wählt 1–3 kurze Highlight-Bereiche pro *vertonter* Episode, indem es
Subtitle-Cue-*Indizes* referenziert — **nie rohe Timestamps**. Der Code rechnet die
Millisekunden aus den Cue-Grenzen, damit das Modell keine Zeit halluzinieren kann, und
snappt automatisch auf Satzgrenzen. Das eigentliche Schneiden passiert außerhalb (Video-Editor).

Rein deterministisch → stdlib-testbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple


@dataclass
class Highlight:
    start_ms: int
    end_ms: int
    start_cue: int
    end_cue: int
    text: str


def _clamp(i: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, i))


def cue_range_to_ms(cues: Sequence[dict], start_index: int, end_index: int) -> Highlight:
    """Wandle ein (start_cue, end_cue)-Indexpaar in einen ms-Bereich.

    Indizes werden auf gültige Grenzen geklemmt (nie halluzinierte Zeit); start ≤ end wird
    erzwungen. Die ms-Grenzen kommen aus den Cues selbst → snappen auf Satzgrenzen.
    """
    n = len(cues)
    if n == 0:
        raise ValueError("no cues to derive highlight from")
    s = _clamp(int(start_index), 0, n - 1)
    e = _clamp(int(end_index), 0, n - 1)
    if e < s:
        s, e = e, s
    text = " ".join(cues[i].get("text", "") for i in range(s, e + 1))
    return Highlight(
        start_ms=int(cues[s]["start_ms"]),
        end_ms=int(cues[e]["end_ms"]),
        start_cue=s, end_cue=e, text=text,
    )


def select_highlights(
    cues: Sequence[dict],
    index_ranges: Sequence[Tuple[int, int]],
    *,
    max_n: int = 3,
) -> List[Highlight]:
    """Erzeuge bis zu ``max_n`` Highlights aus Modell-gewählten Index-Bereichen.

    Überzählige Bereiche werden verworfen (protokollierbar durch den Aufrufer — kein
    stilles Truncaten über die Grenze hinaus). Leere cues → leere Liste.
    """
    if not cues:
        return []
    return [cue_range_to_ms(cues, s, e) for s, e in list(index_ranges)[:max_n]]
