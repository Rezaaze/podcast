"""Wortbudget pro Part mit Toleranz (§ Stage B, §14).

Neutrale Längenmetrik (funktioniert über Schriftsysteme; Tokenizer tauschbar). Ein
festes Toleranzband, damit die normale Zähl-Unschärfe des Modells keine Retries auslöst.

Die entscheidende Asymmetrie (§ Stage B): **Overlength retryt NIE** — ein langer Part
kostet Sekunden, eine Regenerierung ein volles Prompt. Nur *zu kurz* und Formatfehler
retryen. Ein sicherer Versuch innerhalb eines kleinen Vielfachen der Toleranz wird sofort
akzeptiert (weitere Retries schlügen ihn nicht).
"""

from __future__ import annotations

from typing import Callable

from factory.core.retry import ValidationResult

TOLERANCE = 0.15          # ±15% (§14)
ACCEPT_MULTIPLE = 1.5     # innerhalb 1.5× Toleranz sofort akzeptieren


def word_count(text: str, tokenize: Callable[[str], int] = lambda t: len(t.split())) -> int:
    return tokenize(text)


def check_word_budget(
    text: str,
    target: int,
    *,
    tokenize: Callable[[str], int] = lambda t: len(t.split()),
) -> ValidationResult:
    """Bewerte einen Part gegen sein Wortbudget.

    - **Overlength** (> target·(1+TOL)) → ``ok=True`` (akzeptiert, nie Retry).
    - **Zu kurz** (< target·(1−TOL)) → ``ok=False, fatal=False`` (retrybar, best-effort).
    - Im Band → ok.
    Badness = relative Unterschreitung, damit der Fallback den least-bad Versuch nimmt.
    """
    n = word_count(text, tokenize)
    low = target * (1 - TOLERANCE)
    high = target * (1 + TOLERANCE)

    if n >= low and n <= high:
        return ValidationResult(ok=True, fatal=False, badness=0.0, detail="")
    if n > high:
        # akzeptiert — Overlength ist nie ein Retry (nur eine Warnung im Aufrufer)
        return ValidationResult(ok=True, fatal=False, badness=0.0,
                                detail=f"overlength {n}>{high:.0f} (accepted, not retried)")
    # zu kurz → retrybar
    shortfall = (low - n) / max(low, 1)
    return ValidationResult(
        ok=False, fatal=False, badness=shortfall,
        detail=f"too short: {n} words < {low:.0f} (target {target}); write more, add a concrete beat",
    )


def accept_immediately_threshold(target: int) -> float:
    """Badness-Schwelle für den Sofort-Akzeptieren-Kurzschluss (§ Stage B 1.5×-Regel)."""
    # Ein Versuch, der nur knapp (innerhalb 1.5× Toleranz) zu kurz ist, ist "gut genug".
    return TOLERANCE * ACCEPT_MULTIPLE
