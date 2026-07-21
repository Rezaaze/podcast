"""Season-Fold-Primitive (§10.5) — die *eine* sequenzielle Akkumulation über Episoden.

Im Altsystem dreimal reimplementiert (Beat-Pre-Pass, SFX-Palette, Phrase-Guard). Es ist
ein Konzept: *iteriere Einheiten in Reihenfolge; jede sieht das Aggregat der vorigen.*
Eine Stelle für Reihenfolge und Fehlersemantik.

Formal ist das auch der Fold über die Right-Seams (§13.6): die „laufende Zusammenfassung",
die die Kontinuitätsstrategie (§10.1) jeder Einheit reicht, IST das akkumulierte Ergebnis
der vorigen Seams.
"""

from __future__ import annotations

from typing import Callable, List, Sequence, TypeVar

I = TypeVar("I")   # item
R = TypeVar("R")   # result


def season_fold(
    items: Sequence[I],
    step: Callable[[I, int, List[R]], R],
    *,
    skip_on_error: bool = False,
) -> List[R]:
    """Seriell über ``items``. ``step(item, index, prior_results)`` sieht ALLE vorigen
    Ergebnisse (nicht nur das unmittelbare — sonst „vergessen" Finales frühe Episoden).

    ``skip_on_error=True``: ein fehlgeschlagener Step trägt ``None`` bei und der Lauf
    geht weiter (z.B. Beat-Call ist non-fatal → Fallback). Default: Exception propagiert.
    """
    results: List[R] = []
    for i, item in enumerate(items):
        try:
            res = step(item, i, list(results))
        except Exception:
            if skip_on_error:
                results.append(None)  # type: ignore[arg-type]
                continue
            raise
        results.append(res)
    return results
