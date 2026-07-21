"""Prompt-Stufe getrennt von Render-Stufe (T5.1, § Stage D).

Das Modell schreibt Bild-*Prompts*; der eigentliche Render ist ein separater Schritt, der
pro Datei skippt, was schon existiert. **Eine existierende Prompt-Datei darf den Render
nicht blocken** — sonst erreicht ein später ergänzter Bildschlüssel (neue Rolle, neue
Emotion) nie die Generierung (die §-Stage-D-Verwandte der §9-Fallen).

Reine Mengenlogik → stdlib-testbar. „Existiert" wird als Prädikat injiziert, damit kein
Dateisystem nötig ist.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Set


def keys_needing_prompt(desired: Iterable[str], has_prompt: Callable[[str], bool]) -> List[str]:
    """Schlüssel, für die noch KEIN Prompt existiert (die Prompt-Stufe schreibt nur diese)."""
    return [k for k in desired if not has_prompt(k)]


def keys_needing_render(
    desired: Iterable[str],
    has_prompt: Callable[[str], bool],
    has_render: Callable[[str], bool],
) -> List[str]:
    """Schlüssel, die gerendert werden müssen: gewünscht, Prompt vorhanden, Bild fehlt noch.

    Entscheidend: die Render-Auswahl hängt an ``has_render``, NICHT an ``has_prompt`` —
    ein neu ergänzter Schlüssel mit frischem Prompt erreicht so den Render, auch wenn für
    andere Schlüssel schon Prompts existieren. Ein Bild wird nur übersprungen, wenn *dieses*
    Bild bereits existiert (idempotent, Re-Klick gratis).
    """
    return [k for k in desired if has_prompt(k) and not has_render(k)]
