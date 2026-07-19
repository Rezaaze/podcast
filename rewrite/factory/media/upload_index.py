"""Upload-Index pro Serie/Episode (T6.2, § Stage E).

Menschenlesbare Datei mit Titel, Beschreibung, einer **spoiler-freien** Publikumsfrage
(ans Dilemma gebunden, nie an den Twist) und Kapitelliste — fertig zum Einfügen in eine
Video-Beschreibung.

Die Zusammensetzung ist deterministisch → stdlib-testbar. Ein zusätzlicher Spoiler-Guard
prüft die (vom Modell geschriebene) Frage gegen die Kanon-Auflösungen: eine Frage, die die
Lösung verrät, wird geflaggt statt still ausgeliefert.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence

from factory.media.anthology import Chapter

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def format_ts(ms: int) -> str:
    """ms → 'M:SS' bzw. 'H:MM:SS' für YouTube-Kapitel."""
    total = int(ms) // 1000
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def question_leaks_twist(question: str, resolutions: Iterable[str], *, min_overlap: int = 2) -> bool:
    """True, wenn die Publikumsfrage zu viele Inhaltswörter einer Kanon-Auflösung teilt.

    Heuristik gegen versehentliche Twist-Spoiler: teilt die Frage ≥``min_overlap`` seltene
    Wörter mit einer Auflösung, ist sie verdächtig (der Aufrufer lässt sie neu schreiben).
    """
    q_tokens = {w.lower() for w in _WORD.findall(question) if len(w) > 3}
    for res in resolutions:
        r_tokens = {w.lower() for w in _WORD.findall(res) if len(w) > 3}
        if len(q_tokens & r_tokens) >= min_overlap:
            return True
    return False


def build_upload_index(
    series_title: str,
    episode_title: str,
    description: str,
    audience_question: str,
    chapters: Sequence[Chapter],
) -> str:
    """Setze die menschenlesbare Index-Datei zusammen (Markdown-artig)."""
    lines: List[str] = [
        f"# {series_title} — {episode_title}",
        "",
        description.strip(),
        "",
        f"**Question for you:** {audience_question.strip()}",
    ]
    if chapters:
        lines += ["", "## Chapters"]
        lines += [f"{format_ts(c.start_ms)} {c.title}" for c in chapters]
    return "\n".join(lines) + "\n"
