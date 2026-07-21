"""Deterministische Hazard-Checks (§ Stage B).

Fangen Fehlerklassen, die keine Prompt-Regel zuverlässig verhindert:
- **Narrator-Leaks:** Narrator-Zeilen, die interne Labels/Szenennummern „aussprechen"
  (Spoiler — der Narrator darf nie „Szene 3" oder „turning point tp0" sagen).
- **Modell-Rauschen:** buchstabenlose „Rede", Platzhalter, Rest-Markup, Fremdschrift
  mitten im Satz.

Alle sind *soft* (retrybar, fallback-safe) und erhöhen die badness — nie fatal, weil
structured output den Formatrahmen ohnehin garantiert.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

# Interne Labels, die ein Narrator nie aussprechen darf.
_LEAK = re.compile(r"\b(scene|section|episode|part|turning[\s_-]?point|tp)\s*[#:]?\s*\d+", re.I)
_LEAK_BARE = re.compile(r"\btp\d+\b", re.I)

# Platzhalter / Rest-Markup.
_PLACEHOLDER = re.compile(r"(\[[^\]]*\]|\{\{[^}]*\}\}|TODO|PLACEHOLDER|lorem ipsum|XXX+)", re.I)
_MARKUP = re.compile(r"(\*\*|__|^#{1,6}\s|</?[a-z][^>]*>)", re.M)
_HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)

# Unerwartete Schrift-Blöcke für lateinische Sprachen (CJK/Kyrillisch/Arabisch/Hebräisch).
_FOREIGN_SCRIPTS = re.compile(
    r"[一-鿿぀-ヿЀ-ӿ؀-ۿ֐-׿]"
)
_LATIN_LANGS = {"en", "de", "fr", "es", "it", "pt", "nl"}


@dataclass
class Hazard:
    kind: str
    line_index: int
    detail: str


def scan_hazards(
    lines: Sequence[dict],
    *,
    narrator_role: str = "NARRATOR",
    language: str = "en",
) -> List[Hazard]:
    """``lines``: [{speaker, text, ...}]. Rückgabe: alle gefundenen Hazards (leer = sauber)."""
    out: List[Hazard] = []
    for i, line in enumerate(lines):
        text = line.get("text", "")
        speaker = line.get("speaker", "")

        if speaker == narrator_role and (_LEAK.search(text) or _LEAK_BARE.search(text)):
            out.append(Hazard("narrator_leak", i,
                              f"narrator speaks an internal label: {text!r}"))

        if text.strip() and not _HAS_LETTER.search(text):
            out.append(Hazard("letterless", i, f"line has no letters: {text!r}"))

        if _PLACEHOLDER.search(text):
            out.append(Hazard("placeholder", i, f"placeholder/leftover token: {text!r}"))

        if _MARKUP.search(text):
            out.append(Hazard("markup", i, f"leftover markup: {text!r}"))

        if language in _LATIN_LANGS and _FOREIGN_SCRIPTS.search(text):
            out.append(Hazard("foreign_script", i,
                              f"unexpected non-latin script mid-text: {text!r}"))
    return out


def hazard_feedback(hazards: Sequence[Hazard]) -> str:
    """Kompaktes, ins Prompt rückspeisbares Feedback."""
    return "; ".join(f"[{h.kind} @line {h.line_index}] {h.detail}" for h in hazards)
