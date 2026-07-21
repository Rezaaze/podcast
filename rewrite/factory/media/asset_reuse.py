"""Cross-Series-Asset-Reuse, human-gated (T5.3, § Stage D).

Porträts/Locations/SFX können über Serien hinweg wiederverwendet werden — erst per
Exact-Hash, dann per Fuzzy-Match. Aber Fuzzy-Matching auf langen, plot-reichen
Beschreibungen ist unzuverlässig (echte Duplikate und False Positives teilen dasselbe
Score-Band) — statt automatisch zu raten, listet ein **Near-Miss-Audit** die Kandidaten
unter der sicheren Schwelle, und ein Mensch entscheidet.

Deterministisch → stdlib-testbar. Der Exact-Hash nutzt denselben ``sfx_asset_hash`` wie das
Altsystem (identischer Dateiname bei identischem Text, ohne Zuordnungsdatei).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from factory.core.textproc import sfx_asset_hash

# Startwerte (§14): über CONFIDENT sicher wiederverwenden, zwischen AUDIT und CONFIDENT
# einem Menschen vorlegen, darunter als neu behandeln.
CONFIDENT_THRESHOLD = 0.85
AUDIT_THRESHOLD = 0.5

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _tokens(text: str) -> set:
    return {w.lower() for w in _WORD.findall(text)}


def fuzzy_score(a: str, b: str) -> float:
    """Jaccard-Ähnlichkeit über Wort-Tokens (0..1). Simpel, aber genügt für das Audit-Band."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class ReuseDecision:
    verdict: str                       # "exact" | "reuse" | "audit" | "new"
    match_key: str | None = None       # bei "exact"/"reuse": der wiederverwendbare Asset-Key
    candidates: List[Tuple[str, float]] = None  # bei "audit": (key, score), absteigend

    def __post_init__(self) -> None:
        if self.candidates is None:
            self.candidates = []


def classify_reuse(
    description: str,
    existing: Dict[str, str],
    *,
    confident_threshold: float = CONFIDENT_THRESHOLD,
    audit_threshold: float = AUDIT_THRESHOLD,
) -> ReuseDecision:
    """Entscheide über Wiederverwendung. ``existing``: key → Beschreibung bereits erzeugter Assets.

    - **exact**: identischer Hash (byte-für-byte gleicher normalisierter Text) → sicher reuse.
    - **reuse**: bester Fuzzy-Score ≥ confident → auto-reuse (sicher genug).
    - **audit**: bester Fuzzy-Score im Band [audit, confident) → Kandidaten für den Menschen;
      *kein* Auto-Raten, weil echte Duplikate und False Positives dieses Band teilen.
    - **new**: nichts Ähnliches → neu erzeugen.
    """
    target_hash = sfx_asset_hash(description)
    for key, desc in existing.items():
        if sfx_asset_hash(desc) == target_hash:
            return ReuseDecision(verdict="exact", match_key=key)

    scored = sorted(
        ((key, fuzzy_score(description, desc)) for key, desc in existing.items()),
        key=lambda kv: kv[1], reverse=True,
    )
    if scored and scored[0][1] >= confident_threshold:
        return ReuseDecision(verdict="reuse", match_key=scored[0][0])
    near = [(k, s) for k, s in scored if s >= audit_threshold]
    if near:
        return ReuseDecision(verdict="audit", candidates=near)
    return ReuseDecision(verdict="new")
