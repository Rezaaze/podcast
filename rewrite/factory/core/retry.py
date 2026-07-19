"""Universeller Retry-Loop mit Feedback-Rückspeisung (§5, §10.8-Carve-out).

Structured Output (§10.8) garantiert *parsebares* JSON — nie *korrekten Inhalt*.
Deshalb überlebt dieser Loop den Interface-Wechsel: er ist Degeneracy (unabhängiger
Fehlerkanal: das Modell erzeugt, ein deterministischer Validator entscheidet), nicht
Transport-Plumbing.

Kernunterscheidung (§5): *fatal* = Output würde einen Downstream-Parser crashen
(Formatfehler, fehlende Unit) → NIE akzeptiert. Alles andere ist *soft* und unterliegt
dem Best-Effort-Fallback: schlägt der letzte Versuch nur an einem weichen Kriterium
fehl, nimm den bislang least-bad *sicheren* Versuch statt abzubrechen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

R = TypeVar("R")


@dataclass
class ValidationResult:
    ok: bool
    fatal: bool          # würde Downstream crashen → nie akzeptierbar
    badness: float       # kleiner = besser; ordnet soft-Fehler für den Fallback
    detail: str          # exakter Fehlertext, wird ins nächste Prompt gespeist


@dataclass
class Attempt(Generic[R]):
    value: R
    result: ValidationResult


class RetryExhausted(Exception):
    """Alle Versuche fehlgeschlagen und kein sicherer (nicht-fataler) Versuch da."""

    def __init__(self, last_detail: str, attempts: int) -> None:
        super().__init__(f"retry exhausted after {attempts} attempts: {last_detail}")
        self.last_detail = last_detail
        self.attempts = attempts


def run_with_retry(
    generate: Callable[[str], R],
    validate: Callable[[R], ValidationResult],
    *,
    base_prompt: str,
    max_attempts: int = 3,
    escalation_threshold: int = 3,
    escalation_note: str = (
        "\n\nSTILL WRONG after several tries — fix the exact issue above concretely."
    ),
    accept_immediately_below: Optional[float] = None,
) -> R:
    """Führe generate→validate mit Feedback-Rückspeisung und Best-Effort-Fallback aus.

    - ``ok`` → sofort zurück.
    - Letzter Versuch, nicht fatal → bislang least-bad *sicherer* (nicht-fataler)
      Versuch (Best-Effort-Fallback). Nie ein fataler.
    - ``accept_immediately_below``: ein sicherer Versuch mit badness darunter wird
      sofort akzeptiert (weitere Retries würden ihn nicht schlagen — § StageB 1.5×-Regel).
    - Feedback (``detail``) wird kumulativ ins Prompt gehängt; ab
      ``escalation_threshold`` zusätzlich ``escalation_note``.

    Startwerte (§14): max_attempts=3, escalation nur beim letzten Versuch.
    """
    feedback = ""
    best_safe: Optional[Attempt[R]] = None
    last_detail = ""

    for attempt in range(1, max_attempts + 1):
        prompt = base_prompt + feedback
        if attempt >= escalation_threshold:
            prompt += escalation_note

        value = generate(prompt)
        res = validate(value)
        last_detail = res.detail

        if res.ok:
            return value

        if not res.fatal:
            # sicherer Versuch — als Fallback-Kandidat merken (kleinste badness gewinnt)
            if best_safe is None or res.badness < best_safe.result.badness:
                best_safe = Attempt(value=value, result=res)
            if (
                accept_immediately_below is not None
                and res.badness < accept_immediately_below
            ):
                return value

        if attempt == max_attempts:
            break

        # exaktes Scheitern zurückspeisen (blinder → korrektiver Retry)
        feedback += f"\n\nPREVIOUS ATTEMPT FAILED: {res.detail}"

    if best_safe is not None:
        return best_safe.value      # Best-Effort-Fallback statt Deadlock
    raise RetryExhausted(last_detail, max_attempts)
