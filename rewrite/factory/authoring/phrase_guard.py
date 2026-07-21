"""Phrase-Guard (deterministisch, cross-episode) (§ Stage B).

Zählt wiederholte N-Gramme und Stilwörter über bereits geschriebene Episoden und speist
die schlimmsten Wiederholer als „avoid"-Block ins nächste Prompt zurück. **Eigennamen
sind ausgenommen** — Figuren und Orte *müssen* wiederkehren. Zusätzlich ein
menschenlesbarer Report als Review-Gate.

Läuft im Season-Fold (§10.5): Episode N sieht das Aggregat von 1..N-1.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set, Tuple

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _tokens(text: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(text)]


def ngrams(text: str, n: int = 3) -> List[Tuple[str, ...]]:
    toks = _tokens(text)
    return [tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)]


@dataclass
class PhraseReport:
    avoid_block: str          # ins Prompt rückspeisbar
    report: str               # menschenlesbar (Review-Gate)
    offenders: List[Tuple[str, int]]   # (phrase, count)


def build_phrase_report(
    prior_texts: Sequence[str],
    *,
    exempt_names: Iterable[str] = (),
    n: int = 3,
    top_k: int = 10,
    min_count: int = 2,
) -> PhraseReport:
    """Analysiere bereits geschriebene Episodentexte.

    ``exempt_names``: Cast-Rollen + Location-Keys + Eigennamen — N-Gramme, die *nur* aus
    solchen bestehen, werden nicht als Wiederholung gewertet (sie müssen wiederkehren).
    """
    exempt: Set[str] = {name.lower() for name in exempt_names}
    counter: Counter = Counter()
    for text in prior_texts:
        for gram in ngrams(text, n):
            if all(tok in exempt for tok in gram):
                continue   # reiner Eigenname-N-Gramm → erlaubt
            counter[gram] += 1

    offenders = [
        (" ".join(gram), cnt)
        for gram, cnt in counter.most_common(top_k)
        if cnt >= min_count
    ]

    if offenders:
        avoid_lines = "\n".join(f'- "{phrase}" (used {cnt}×)' for phrase, cnt in offenders)
        avoid_block = "AVOID these over-used phrases from earlier episodes:\n" + avoid_lines
        report = f"{len(offenders)} repeated {n}-gram(s) across {len(prior_texts)} episode(s):\n" + avoid_lines
    else:
        avoid_block = ""
        report = f"no {n}-gram repeated ≥{min_count}× across {len(prior_texts)} episode(s)."

    return PhraseReport(avoid_block=avoid_block, report=report, offenders=offenders)
