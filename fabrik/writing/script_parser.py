"""Parser für das Drama-Skriptformat (mode: "drama").

Ein Part besteht aus Sprecherzeilen und SFX-Regieanweisungen:

    [HOST | style: warm, slow, teacher-like]
    Welcome back to the tea house...

    [SFX: rain against the window, distant thunder]

    [LIN_QIU | style: suspicious, lowered voice | speed: 0.9]
    你到底想说什么？

Regeln:
- "[NAME]" oder "[NAME | style: ... | speed: ...]" beginnt eine Sprecherzeile;
  aller Text bis zur nächsten Klammerzeile gehört diesem Sprecher.
- "style" überschreibt den default_style der Rolle aus episodes.json,
  "speed" (0.5–2.0) geht als Parameter an das TTS-API. "tone"/"emotion"
  werden als Alias für "style" akzeptiert (Claude variiert hier gern).
- "[SFX: ...]" wird nicht vertont, sondern beim Rendern mit ms-Offset
  protokolliert (→ SFX-Cue-Sheet für die DAW).
- "[NOTE: ...]" ist reine Autoren-Buchhaltung (z.B. neu eingeführtes
  Vokabular im language_course-Template) — wird nie vertont und nie
  gecuet, nur beim Schreiben der nächsten Section wieder eingespeist
  (siehe script_writer.extract_vocab_notes()).
- Unbekannte Sprecher, Text ohne Sprecher-Tag oder kaputte Tags sind harte
  Fehler MIT Zeilenangabe — sie fliegen VOR dem ersten TTS-Call auf.
"""

from __future__ import annotations

import re

_TAG_RE = re.compile(r'^\[(.+)\]\s*$')
_SFX_PREFIX_RE = re.compile(r'(?i)^SFX\s*:\s*')
_NOTE_PREFIX_RE = re.compile(r'(?i)^NOTE\s*:\s*')
_SPEED_MIN, _SPEED_MAX = 0.5, 2.0
_STYLE_KEYS = {"style", "tone", "emotion", "instruct"}


class ScriptFormatError(Exception):
    """Formatfehler im Drama-Skript — Meldung enthält Part + Zeilennummer."""


class SpeechLine:
    def __init__(self, speaker, lineno, style=None, speed=None):
        self.kind = "speech"
        self.speaker = speaker
        self.style = style
        self.speed = speed
        self.text = ""
        self.lineno = lineno

    def __repr__(self):
        return f"SpeechLine({self.speaker!r}, style={self.style!r}, speed={self.speed}, text={self.text[:30]!r})"


class SfxCue:
    def __init__(self, description, lineno):
        self.kind = "sfx"
        self.description = description
        self.lineno = lineno

    def __repr__(self):
        return f"SfxCue({self.description!r})"


class VocabNote:
    """[NOTE: word — pinyin — meaning] — author-only bookkeeping for the
    language_course template: flags vocabulary/grammar introduced beyond the
    pre-taught set, so the Analysis section prompt can be fed the exact list
    and forced to cover all of it (not just whatever it happens to pick).
    Never spoken, never cued — dropped entirely during rendering."""

    def __init__(self, content, lineno):
        self.kind = "note"
        self.content = content
        self.lineno = lineno

    def __repr__(self):
        return f"VocabNote({self.content!r})"


def _parse_attrs(attr_text, where):
    """"style: x | speed: 0.9" → {"style": "x", "speed": 0.9}"""
    style = None
    speed = None
    for raw in attr_text.split("|"):
        raw = raw.strip()
        if not raw:
            continue
        if ":" not in raw:
            raise ScriptFormatError(
                f"{where}: Attribut ohne 'schlüssel: wert' — '{raw}' "
                f"(erwartet z.B. 'style: whispering' oder 'speed: 0.9')")
        key, value = raw.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in _STYLE_KEYS:
            style = f"{style}, {value}" if style else value
        elif key == "speed":
            try:
                speed = float(value)
            except ValueError:
                raise ScriptFormatError(f"{where}: speed '{value}' ist keine Zahl")
            if not (_SPEED_MIN <= speed <= _SPEED_MAX):
                raise ScriptFormatError(
                    f"{where}: speed {speed} außerhalb {_SPEED_MIN}–{_SPEED_MAX}")
        else:
            raise ScriptFormatError(
                f"{where}: unbekanntes Attribut '{key}' (erlaubt: style/tone/emotion, speed)")
    return style, speed


def parse_drama_part(part_text, voices=None, part_label="PART"):
    """Parst einen Part-Text in eine Liste von SpeechLine/SfxCue.

    voices: dict der bekannten Rollen aus episodes.json — wenn gesetzt, ist
    jeder unbekannte Sprecher ein harter Fehler."""
    items = []
    current = None

    for lineno, raw in enumerate(part_text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        where = f"{part_label}, Zeile {lineno}"

        match = _TAG_RE.match(line)
        if not match:
            if current is None:
                raise ScriptFormatError(
                    f"{where}: Text ohne vorangehendes Sprecher-Tag — '{line[:60]}'")
            current.text = f"{current.text} {line}".strip() if current.text else line
            continue

        # .+ ist bewusst gierig: die Klammer muss bis zur LETZTEN ']' der
        # Zeile reichen, sonst zerreißt ein zufälliges ']' MITTEN im
        # SFX-/NOTE-Freitext (z.B. eine Beispielklammer wie "[done]" in
        # einer Vokabelerklärung) den Match — die Zeile würde dann fälschlich
        # als Fließtext an die vorherige Sprecherzeile angehängt, statt als
        # eigener Tag erkannt zu werden (SFX/NOTE landen NIE in Sprechertext).
        inner = match.group(1).strip()

        if _SFX_PREFIX_RE.match(inner):
            desc = _SFX_PREFIX_RE.sub('', inner).strip()
            if not desc:
                raise ScriptFormatError(f"{where}: SFX-Tag ohne Beschreibung")
            items.append(SfxCue(desc, lineno))
            current = None
            continue

        if _NOTE_PREFIX_RE.match(inner):
            content = _NOTE_PREFIX_RE.sub('', inner).strip()
            if not content:
                raise ScriptFormatError(f"{where}: NOTE-Tag ohne Inhalt")
            items.append(VocabNote(content, lineno))
            current = None
            continue

        # Sprecher-Tag: "NAME" oder "NAME | attrs" — nur hier wird auf '|'
        # gesplittet, SFX/NOTE oben durchlaufen davon unberührt.
        speaker, _, attrs = inner.partition('|')
        speaker = speaker.strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+", speaker):
            raise ScriptFormatError(
                f"{where}: ungültiger Sprechername '[{speaker}]' — erlaubt sind "
                f"Buchstaben, Zahlen und '_' (z.B. [HOST], [LIN_QIU])")
        if voices is not None and speaker not in voices:
            known = ", ".join(sorted(voices)) or "(keine definiert)"
            raise ScriptFormatError(
                f"{where}: unbekannter Sprecher '[{speaker}]' — bekannte Rollen: {known}")

        style, speed = _parse_attrs(attrs, where)
        current = SpeechLine(speaker, lineno, style=style, speed=speed)
        items.append(current)

    empty = [it for it in items if it.kind == "speech" and not it.text.strip()]
    if empty:
        raise ScriptFormatError(
            f"{part_label}, Zeile {empty[0].lineno}: Sprecher-Tag "
            f"'[{empty[0].speaker}]' ohne nachfolgenden Text")
    if not any(it.kind == "speech" for it in items):
        raise ScriptFormatError(f"{part_label}: enthält keine einzige Sprecherzeile")

    return items


def validate_drama_script(parts, voices, part_numbers=None):
    """Parst alle Parts eines Skripts; Rückgabe: Liste der Item-Listen.
    part_numbers: optionale echte Part-Nummern für Fehlermeldungen."""
    parsed = []
    for i, part_text in enumerate(parts):
        label = f"PART {part_numbers[i] if part_numbers else i + 1}"
        parsed.append(parse_drama_part(part_text, voices=voices, part_label=label))
    return parsed
