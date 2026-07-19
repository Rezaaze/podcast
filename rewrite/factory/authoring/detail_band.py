"""Detail-Tiefe als per-Section-Gate (§2.6, §14).

Jedes section-„what" muss in ein neutrales Längenband fallen, und der Spread innerhalb
einer Episode ist begrenzt — so kann eine Episode nicht drei üppige Szenen mit einer
Stub-Szene mischen. Das wird *vor* Acceptance geprüft, mit Feedback (nicht hinterher
auditiert).

Neutrale Metrik (§7/§ Stage B): Wort-Tokens auf Whitespace — robust genug für den
Zweck; für nicht-wortsegmentierte Schriften kann die Tokenizer-Funktion getauscht werden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Sequence

# Startwerte (§14): „what" zwischen 6 und 40 Tokens; Spread innerhalb einer Episode ≤ 2 Tiers.
MIN_TOKENS = 6
MAX_TOKENS = 40
MAX_TIER_SPREAD = 2

# Tier-Grenzen (obere Token-Zahl je Tier). Ein „what" fällt in den ersten Tier, dessen
# Grenze es nicht überschreitet.
_TIER_BOUNDS = (12, 20, 28, 40)


def _default_tokenize(text: str) -> int:
    return len(text.split())


def length_tier(text: str, tokenize: Callable[[str], int] = _default_tokenize) -> int:
    n = tokenize(text)
    for tier, bound in enumerate(_TIER_BOUNDS):
        if n <= bound:
            return tier
    return len(_TIER_BOUNDS)   # oberhalb des letzten Bandes


@dataclass
class BandResult:
    ok: bool
    detail: str = ""
    offenders: List[str] = field(default_factory=list)   # section-Titel, die verstoßen


def check_detail_band(
    sections: Sequence[dict],
    *,
    tokenize: Callable[[str], int] = _default_tokenize,
) -> BandResult:
    """Prüfe eine Episode. Rückgabe ist als Retry-Feedback verwendbar (§2.6)."""
    problems: List[str] = []
    offenders: List[str] = []
    tiers: List[int] = []

    for sec in sections:
        what = sec.get("what", "")
        title = sec.get("title", "<untitled>")
        n = tokenize(what)
        if n < MIN_TOKENS:
            problems.append(f"section {title!r}: 'what' too thin ({n} tokens, min {MIN_TOKENS})")
            offenders.append(title)
        elif n > MAX_TOKENS:
            problems.append(f"section {title!r}: 'what' too lavish ({n} tokens, max {MAX_TOKENS})")
            offenders.append(title)
        tiers.append(length_tier(what, tokenize))

    if tiers:
        spread = max(tiers) - min(tiers)
        if spread > MAX_TIER_SPREAD:
            problems.append(
                f"episode mixes uneven detail: tier spread {spread} > {MAX_TIER_SPREAD} "
                f"(don't pair lavish scenes with stub scenes)"
            )

    return BandResult(
        ok=not problems,
        detail="; ".join(problems),
        offenders=sorted(set(offenders)),
    )
