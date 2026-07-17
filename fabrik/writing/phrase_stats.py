"""Deterministischer Phrasen-Frequenz-Wächter (stdlib-only).

Die 12-Serien-Analyse (17.07.2026, docs/script-analysis-2026-07-17/) fand in
jeder Serie massive LLM-Tics: wortgleiche Phrasen, die über eine Staffel
dutzendfach wiederkehren ("barely audible" 57×, "ten years" 75×, Szenenschluss
"Not yet" 33×) und Style-Anweisungen, die zu einem Einheitston kollabieren
(style "quiet" 134× in einer 8-Folgen-Serie). Kein LLM-Review hat das je
gemeldet — Zählen ist eine Maschinenaufgabe.

Zwei Verwendungen:
- `overused_phrases()` → Block im Section-Prompt ("nicht schon wieder benutzen"),
  gebaut aus den BISHER geschriebenen Episoden der Serie (siehe
  script_writer.build_section_prompt / generate_episode.py).
- `build_phrase_report()` → PHRASE_REPORT.txt in stages/02_scripts/output/
  (reine Anzeige, Review-Gate — analog SFX_PLAN.json).
"""

from __future__ import annotations

import re
from collections import Counter

# Phrasen unterhalb dieser Häufigkeit sind normale Sprache, kein Tic. Der Wert
# ist bewusst pro SERIE gedacht (alle bisher geschriebenen Episoden zusammen).
MIN_COUNT = 6
MAX_PROMPT_ITEMS = 15          # Obergrenze für den Prompt-Block (Token-Budget)
NGRAM_RANGE = (3, 4, 5)        # Wortfenster der gezählten Phrasen
STYLE_MIN_COUNT = 25           # ab wann ein Style-Wort als Einheitston gilt

_TAG_LINE_RE = re.compile(r'^\s*\[[^\]]*\]\s*$', re.MULTILINE)
_PART_MARKER_RE = re.compile(r'^---\s*PART\s+\d+\s*---\s*$', re.MULTILINE)
_STYLE_ATTR_RE = re.compile(r'\[[A-Za-z0-9_]+\s*\|\s*(?:style|tone|emotion|instruct)\s*:\s*([^\]|]+)',
                            re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z']+")

# Grenz-Token zwischen zwei Skripten: kann von _WORD_RE nie erzeugt werden
# (enthält '_'), n-Gramme laufen damit nicht über Episodengrenzen hinweg.
_BOUNDARY = "__ep_boundary__"

# Phrasen, die NUR aus diesen Wörtern bestehen, sind grammatisches Bindegewebe
# ("one of the", "I don't know") — hohe Zählwerte dort sind Sprache, kein Tic.
_STOPWORDS = frozenset(
    "a an the and or but if of to in on at for with from by as is are was were be been being "
    "am do does did done don't doesn't didn't it its it's this that these those there here "
    "he she they we you i his her their our your my me him them us not no yes so then than "
    "what who whom which when where why how all any some one two out up down over under "
    "into onto about after before again once just only very too can can't could couldn't "
    "will won't would wouldn't should shouldn't have has had haven't hasn't hadn't "
    "know knows knew think thinks thought want wants wanted going go goes went get gets got "
    "say says said tell tells told see sees saw look looks looked "
    "'s 've 'll 'd 're 'm n't".split()
)


def speech_text(script_text: str) -> str:
    """Nur der gesprochene Text eines Drama-Skripts: Tag-Zeilen ([ROLE | ...],
    [SFX: ...], [NOTE: ...]) und PART-Marker entfernt. Für narration-Skripte
    harmlos (dort matchen die Muster schlicht nicht)."""
    text = _PART_MARKER_RE.sub("", script_text)
    return _TAG_LINE_RE.sub("", text)


def _ngrams(words: list[str], n: int):
    for i in range(len(words) - n + 1):
        yield " ".join(words[i:i + n])


def name_words(data: dict) -> frozenset:
    """Eigennamen-Wörter aus episodes.json (voices-Rollen, locations-Namen,
    series_title): Figuren- und Ortsnamen MÜSSEN über eine Staffel wiederkehren
    und dürfen im Avoid-Block nie landen — sonst verbietet der Prompt dem
    Writer, seine eigenen Charaktere beim Namen zu nennen."""
    words: set[str] = set()
    for role in (data.get("voices") or {}):
        words.update(part.lower() for part in re.split(r"[_\s]+", role) if part)
    for lcfg in (data.get("locations") or {}).values():
        if isinstance(lcfg, dict) and isinstance(lcfg.get("name"), str):
            words.update(_WORD_RE.findall(lcfg["name"].lower()))
    words.update(_WORD_RE.findall(str(data.get("series_title", "")).lower()))
    return frozenset(words)


def overused_phrases(script_texts: list[str], min_count: int = MIN_COUNT,
                     max_items: int = MAX_PROMPT_ITEMS,
                     exclude_words: frozenset = frozenset()) -> list[tuple[str, int]]:
    """Zählt 3-5-Wort-Phrasen über den gesprochenen Text aller übergebenen
    Skripte und liefert die Ausreißer als [(phrase, count), ...], häufigste
    zuerst. Eine kürzere Phrase, die komplett in einer gemeldeten längeren
    steckt und keine nennenswert eigene Häufigkeit hat, wird unterdrückt —
    sonst erschiene "barely audible …" dreifach gestaffelt.

    exclude_words (typisch: name_words(data)): Phrasen, die eines dieser
    Wörter enthalten, werden verworfen — wiederkehrende Figuren-/Ortsnamen
    sind kein Tic."""
    words: list[str] = []
    for text in script_texts:
        words.extend(_WORD_RE.findall(speech_text(text).lower()))
        words.append(_BOUNDARY)  # Skript-Grenze: n-Gramme laufen nicht über Dateigrenzen
    counts: Counter = Counter()
    for n in NGRAM_RANGE:
        for gram in _ngrams(words, n):
            if _BOUNDARY in gram:
                continue
            counts[gram] += 1

    candidates = [(g, c) for g, c in counts.items()
                  if c >= min_count
                  and not all(w in _STOPWORDS for w in g.split())
                  and not any(w in exclude_words for w in g.split())]
    # Längere Phrasen zuerst betrachten, damit sie ihre Teilphrasen schlucken
    candidates.sort(key=lambda gc: (-len(gc[0].split()), -gc[1]))
    kept: list[tuple[str, int]] = []
    for gram, count in candidates:
        subsumed = any(gram in longer and count <= lcount * 1.5 for longer, lcount in kept)
        if not subsumed:
            kept.append((gram, count))
    kept.sort(key=lambda gc: -gc[1])
    return kept[:max_items]


def overused_styles(script_texts: list[str], min_count: int = STYLE_MIN_COUNT) -> list[tuple[str, int]]:
    """Zählt einzelne Wörter in style/tone/emotion-Attributen der Sprecher-Tags
    ("quiet, deliberate" → quiet, deliberate). Ein Wort weit über min_count
    heißt: die Staffel spricht in einem Einheitston."""
    counts: Counter = Counter()
    for text in script_texts:
        for attr in _STYLE_ATTR_RE.findall(text):
            for word in _WORD_RE.findall(attr.lower()):
                if word not in _STOPWORDS:
                    counts[word] += 1
    return [(w, c) for w, c in counts.most_common() if c >= min_count]


def build_avoid_block(phrases: list[tuple[str, int]],
                      styles: list[tuple[str, int]]) -> str:
    """Prompt-Block für build_section_prompt() — leerer String, wenn es nichts
    zu melden gibt (dann hängt der Writer auch nichts an)."""
    if not phrases and not styles:
        return ""
    lines = ["OVERUSED IN THIS SEASON SO FAR — these exact phrasings have already been "
             "used the number of times shown; do NOT use them (or close variants) again, "
             "find fresh wording instead:"]
    for gram, count in phrases:
        lines.append(f'  - "{gram}" ({count}x)')
    if styles:
        lines.append("Overused style directions — vary the emotional register instead of "
                     "defaulting to these again:")
        for word, count in styles[:6]:
            lines.append(f'  - style "{word}" ({count}x)')
    return "\n".join(lines)


def build_phrase_report(script_texts_by_episode: dict[int, str],
                        exclude_words: frozenset = frozenset()) -> str:
    """Menschenlesbarer Serien-Report (PHRASE_REPORT.txt) über ALLE Episoden."""
    texts = [script_texts_by_episode[n] for n in sorted(script_texts_by_episode)]
    phrases = overused_phrases(texts, max_items=40, exclude_words=exclude_words)
    styles = overused_styles(texts)
    lines = ["Phrasen-Frequenz-Report (deterministisch, fabrik/writing/phrase_stats.py)",
             f"Episoden ausgewertet: {', '.join(str(n) for n in sorted(script_texts_by_episode))}",
             ""]
    if phrases:
        lines.append(f"Wiederholte Phrasen (>= {MIN_COUNT}x über die Staffel):")
        lines += [f'  {c:4}x  "{g}"' for g, c in phrases]
    else:
        lines.append("Keine auffällig wiederholten Phrasen.")
    lines.append("")
    if styles:
        lines.append(f"Style-Einheitston (>= {STYLE_MIN_COUNT}x als style/tone/emotion-Wort):")
        lines += [f"  {c:4}x  style \"{w}\"" for w, c in styles]
    else:
        lines.append("Keine auffällig wiederholten Style-Wörter.")
    lines.append("")
    return "\n".join(lines)
