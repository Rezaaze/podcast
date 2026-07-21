"""Deterministischer Kontinuitäts-Wächter über fertige Skripte (stdlib-only).

Die Drift-Messung (19.07.2026, docs/kontinuitaets-messung-2026-07-19.md) hat in
16 Produktionsepisoden 18 gegengeprüfte Kanon-Brüche gefunden (~1,1 pro Episode)
— OBWOHL die Beat-Schicht in beiden Serien lief. Der Grund: Beats entstehen VOR
der Prosa aus dem Plan, sie können nicht wissen, was das Modell tatsächlich
geschrieben hat. Die Brüche zerfallen in zwei Klassen, und BEIDE sind ohne einen
einzigen Modellaufruf auffindbar:

1. Erfundene Eigennamen. Der Kanon sagt "The Herald Newsroom", die Prosa
   erfindet über eine Staffel vier Zeitungen (Port Meridian Ledger, City Ledger,
   Port Meridian Gazette, Harbor City Herald). Ein LLM-Prüfpanel hat davon zwei
   übersehen, ein Regex findet alle.
2. Zähler, die rückwärts laufen. "Forty-two mornings" in Ep1, "Six weeks. Six
   faces." in Ep2; Foto "Forty-one" an Tag 48; Panopticon "six weeks" vs. "four
   months" im selben Skript. Das sind die für den Hörer auffälligsten Fehler,
   und Zählen ist eine Maschinenaufgabe — kein LLM-Review hat sie je gemeldet.

Analog `phrase_stats.py`: rein deterministisch, keine API, kein venv. Verwendung
als Report (CONTINUITY_REPORT.txt, Review-Gate neben PHRASE_REPORT.txt) und als
Prompt-Block für die nächste Episode (`build_continuity_block`).

Bewusst NICHT enthalten: eine Prosa-Zusammenfassung, die von Episode zu Episode
weitergereicht wird. Zusammenfassungen von Zusammenfassungen kompoundieren ihre
eigenen Fehler; hier wird immer gegen harte Werte (Kanon-Registry, gemessene
Zählerstände) verglichen, nie gegen erzeugten Text.
"""

from __future__ import annotations

import re
from collections import defaultdict

from fabrik.writing.phrase_stats import speech_text

# Abweichung einer Prosa-Zeitangabe von der Kanon-Angabe zum selben Anker.
# Unter 2x ist es dieselbe Angabe, nur gerundet ("vier Monate" / "16 Wochen").
# Über 12x redet die Stelle offensichtlich von etwas anderem — "zwei Minuten"
# in einem Absatz über Panopticon meint nicht dessen Laufzeit.
MIN_CONFLICT_RATIO = 2.0
MAX_CONFLICT_RATIO = 12.0

# Ein Serien-Zähler muss über mindestens so viele Episoden mit Zahl auftauchen,
# damit er im Prompt-Block als Höchststand gilt.
MIN_COUNTER_EPISODES = 2

# Satzanfänge, die wie Eigennamen aussehen und nie einer sind.
_SENTENCE_STARTERS = frozenset(
    "The This That Each Every When After Before Because Their Then Both Only "
    "Since While Until During Neither Either Another".split()
)

_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_MULTIPLIERS = {"hundred": 100, "thousand": 1000, "million": 1000000}

# Zeiteinheiten → Tage. Erlaubt den Vergleich "six weeks" vs. "four months".
_TIME_UNITS_IN_DAYS = {
    "minute": 1 / 1440, "hour": 1 / 24, "day": 1.0, "night": 1.0,
    "week": 7.0, "month": 30.0, "year": 365.0,
}

# Ortstyp-Wörter nach Klasse. Verglichen wird NUR innerhalb einer Klasse:
# "Adrian's precinct" neben Kanon "Adrian's Apartment" ist sein Arbeitsplatz,
# kein Bruch — "Renata's apartment" neben Kanon "Renata's House" schon.
_PLACE_CLASSES = {
    "dwelling": "house home apartment flat condo loft studio cabin cottage mansion".split(),
    "workplace": "office lab laboratory precinct station newsroom bureau".split(),
    "hospitality": "diner restaurant cafe bar tavern pub hotel motel".split(),
}
_PLACE_TYPE_CLASS = {t: cls for cls, types in _PLACE_CLASSES.items() for t in types}
_PLACE_TYPES = frozenset(_PLACE_TYPE_CLASS)

# Generische Institutions-Suffixe: fängt erfundene Organisationen in Kategorien,
# die der Kanon selbst nie benannt hat (Kanon kennt kein "Gazette" → trotzdem
# meldenswert, wenn die Prosa eine erfindet).
_INSTITUTION_SUFFIXES = frozenset(
    "ledger gazette herald tribune times post chronicle observer journal "
    "precinct newsroom bureau department division unit foundation institute "
    "hospital clinic university college academy bar tavern lounge grill "
    "diner cannery warehouse courthouse morgue".split()
)

# Wörter, die vor einem Suffix stehen dürfen, ohne dass ein Eigenname entsteht
# ("the Fifth Precinct" ist einer, "his police department" nicht).
_GENERIC_HEADS = frozenset("the a an this that his her their our my your its".split())

# Satzanfänge, die großgeschrieben wie ein Namensbestandteil aussehen. Ohne
# diesen Filter meldet der Check "At Unit" aus "…At Unit Four, the log shows…".
_LEADING_FUNCTION_WORDS = frozenset(
    "at in on of to for with from by as into onto over under near behind "
    "outside inside across through around about after before since until "
    "and or but so then when where while because if though".split()
)

_NUM_TOKEN = r"(?:\d[\d,]*|" + "|".join(sorted(_NUM_WORDS, key=len, reverse=True)) + r")"
_NUM_PHRASE_RE = re.compile(
    r"\b((?:" + _NUM_TOKEN + r")(?:[-\s]+(?:" + _NUM_TOKEN + r"|hundred|thousand|million))*)"
    r"\s+([a-z]+)\b", re.IGNORECASE)

_PROPER_RE = re.compile(r"\b((?:[A-Z][a-zA-Z]+\s+){1,3}([A-Z][a-zA-Z]+))\b")
# "The Wharfside bar" — Eigenname mit kleingeschriebenem Typwort. Ohne diese
# zweite Form entgehen dem Check erfundene Lokale, die genau so geschrieben
# werden; mit ihr kam auf zwei Produktionsserien je genau ein Treffer dazu,
# beide echt, kein einziger Fehlalarm.
_LOWER_SUFFIX_RE = re.compile(
    r"\b[Tt]he\s+((?:[A-Z][a-zA-Z]+\s+){1,2}?)([a-z]+)\b")
_POSSESSIVE_PLACE_RE = re.compile(r"\b([A-Z][a-zA-Z]+)'s\s+([a-z]+)\b")


def parse_number(phrase: str) -> float | None:
    """'forty-one' → 41, 'twenty-two hundred' → 2200, '48' → 48. None, wenn die
    Tokenfolge keine sinnvolle Zahl ergibt."""
    tokens = [t for t in re.split(r"[-\s]+", phrase.lower().replace(",", "")) if t]
    if not tokens:
        return None
    total = 0.0
    current = 0.0
    saw_any = False
    for tok in tokens:
        if tok.isdigit():
            current += float(tok)
            saw_any = True
        elif tok in _NUM_WORDS:
            current += _NUM_WORDS[tok]
            saw_any = True
        elif tok in _MULTIPLIERS:
            if not saw_any:
                return None
            mult = _MULTIPLIERS[tok]
            if mult >= 1000:
                total += (current or 1) * mult
                current = 0.0
            else:
                current = (current or 1) * mult
        else:
            return None
    return (total + current) if saw_any else None


def _singular(noun: str) -> str:
    """Grobe Normalisierung: 'faces' → 'face'. Reicht für Zählernomen."""
    low = noun.lower()
    if low.endswith("ies") and len(low) > 4:
        return low[:-3] + "y"
    if low.endswith("ses") or low.endswith("ches") or low.endswith("shes"):
        return low[:-2]
    if low.endswith("s") and not low.endswith("ss"):
        return low[:-1]
    return low


def extract_quantities(text: str) -> list[tuple[float, str, str]]:
    """Alle '<Zahl> <Nomen>'-Paare aus dem gesprochenen Text als
    [(wert, nomen_singular, fundstelle), ...]."""
    out: list[tuple[float, str, str]] = []
    speech = speech_text(text)
    for match in _NUM_PHRASE_RE.finditer(speech):
        value = parse_number(match.group(1))
        if value is None or value <= 0:
            continue
        noun = _singular(match.group(2))
        if noun in _MULTIPLIERS or noun in _NUM_WORDS:
            continue
        start = max(0, match.start() - 45)
        snippet = " ".join(speech[start:match.end() + 45].split())
        out.append((value, noun, snippet))
    return out


def canon_place_names(data: dict) -> set[str]:
    """Die verbindlichen Ortsnamen aus episodes.json (locations[].name)."""
    names = set()
    for cfg in (data.get("locations") or {}).values():
        if isinstance(cfg, dict) and isinstance(cfg.get("name"), str):
            names.add(cfg["name"].strip())
    return names


def _canon_suffixes(names: set[str]) -> frozenset:
    """Selbstkalibrierend: die Ortstyp-Wörter, die der Kanon dieser Serie
    tatsächlich benutzt ('The Herald Newsroom' → newsroom)."""
    return frozenset(n.split()[-1].lower() for n in names if n.split())


def unknown_place_names(data: dict, scripts: dict[int, str]) -> list[tuple[str, list[int]]]:
    """Eigennamen von Orten/Organisationen, die der Kanon nicht kennt.
    → [(name, [episoden]), ...]"""
    canon = canon_place_names(data)
    canon_lower = {n.lower() for n in canon}
    # Einzelwörter aus Kanon-Namen und Rollennamen: 'Cannery' allein ist kein
    # Fund, wenn der Kanon 'The Cannery' kennt.
    canon_words = set()
    for name in canon:
        canon_words.update(w.lower() for w in name.split())
    for role in (data.get("voices") or {}):
        canon_words.update(p.lower() for p in re.split(r"[_\s]+", role) if p)
    # Der Kanon benennt Organisationen auch außerhalb von locations{} — die
    # Zenith Horizon Foundation steht nur in den threads. Ohne diese Quelle
    # meldet der Check jede kanonische Organisation als Erfindung.
    for thread in (data.get("threads") or []):
        blob = " ".join([str(thread.get("solution") or "")]
                        + [str(f) for f in (thread.get("objective_facts") or [])])
        canon_words.update(w.lower() for w in re.findall(r"\b[A-Za-z][\w'-]+\b", blob))
    suffixes = _canon_suffixes(canon) | _INSTITUTION_SUFFIXES

    found: dict[str, set[int]] = defaultdict(set)
    for ep in sorted(scripts):
        speech = speech_text(scripts[ep])
        for match in _PROPER_RE.finditer(speech):
            phrase, last = match.group(1).strip(), match.group(2).lower()
            if last not in suffixes:
                continue
            head = phrase.split()[0].lower()
            if (head in _GENERIC_HEADS or head in _LEADING_FUNCTION_WORDS
                    or phrase.split()[0] in _SENTENCE_STARTERS):
                phrase = " ".join(phrase.split()[1:])
            if not phrase or len(phrase.split()) < 2:
                continue
            low = phrase.lower()
            if low in canon_lower or f"the {low}" in canon_lower:
                continue
            # Besteht der Name nur aus Kanon-Wörtern, ist es eine Variante
            # desselben Ortes, keine Erfindung.
            if all(w.lower() in canon_words for w in phrase.split()):
                continue
            found[phrase].add(ep)

        for match in _LOWER_SUFFIX_RE.finditer(speech):
            head, suffix = match.group(1).strip(), match.group(2).lower()
            if suffix not in _INSTITUTION_SUFFIXES or not head:
                continue
            phrase = f"{head} {suffix}"
            if phrase.lower() in canon_lower or f"the {phrase.lower()}" in canon_lower:
                continue
            # Nur der NAMENSTEIL zählt: "the Cannery warehouse" beschreibt den
            # Kanon-Ort "The Cannery" mit einem generischen Typwort, das im
            # Kanon-Namen nicht vorkommen muss — das ist keine Erfindung.
            if all(w.lower() in canon_words for w in head.split()):
                continue
            found[phrase].add(ep)
    # "Harbor City Precinct" und "Harbor City precinct" sind derselbe Fund.
    merged: dict[str, tuple[str, set[int]]] = {}
    for name, eps in found.items():
        key = name.lower()
        if key in merged:
            merged[key][1].update(eps)
        else:
            merged[key] = (name, set(eps))
    return sorted(((name, sorted(eps)) for name, eps in merged.values()),
                  key=lambda item: (item[1][0], item[0]))


def place_type_conflicts(data: dict, scripts: dict[int, str]) -> list[dict]:
    """Kanon sagt "Renata's House", die Prosa sagt "Renata's apartment" —
    gleicher Besitzer, anderer Ortstyp. → [{owner, canon_type, prosa}, ...]"""
    owners: dict[str, str] = {}
    for name in canon_place_names(data):
        match = re.match(r"([A-Z][a-zA-Z]+)'s\s+([A-Za-z]+)", name)
        if match and match.group(2).lower() in _PLACE_TYPES:
            owners[match.group(1)] = match.group(2).lower()
    if not owners:
        return []

    out = []
    seen: dict[tuple[str, str], set[int]] = defaultdict(set)
    for ep in sorted(scripts):
        for match in _POSSESSIVE_PLACE_RE.finditer(speech_text(scripts[ep])):
            owner, used = match.group(1), match.group(2).lower()
            if (owner in owners and used in _PLACE_TYPES and used != owners[owner]
                    and _PLACE_TYPE_CLASS[used] == _PLACE_TYPE_CLASS[owners[owner]]):
                seen[(owner, used)].add(ep)
    for (owner, used), eps in sorted(seen.items()):
        out.append({"owner": owner, "canon_type": owners[owner],
                    "used": used, "episodes": sorted(eps)})
    return out


def _durations_in(text: str) -> list[tuple[float, str]]:
    """Alle Zeitspannen eines Textstücks in Tagen, mit Fundstelle."""
    return [(days, phrase) for days, phrase, _ in _durations_with_pos(text)]


def _durations_with_pos(text: str) -> list[tuple[float, str, int]]:
    """Wie `_durations_in`, plus Startposition — für Nähe-Vergleiche."""
    out = []
    for match in _NUM_PHRASE_RE.finditer(text):
        value = parse_number(match.group(1))
        unit = _singular(match.group(2))
        if value is None or value <= 0 or unit not in _TIME_UNITS_IN_DAYS:
            continue
        out.append((value * _TIME_UNITS_IN_DAYS[unit], match.group(0), match.start()))
    return out


# Wie weit ein Name und eine Dauer INNERHALB DERSELBEN KLAUSEL auseinanderstehen
# dürfen, um noch als dasselbe Ereignis zu gelten — zweite Sicherung NACH dem
# Klausel-Split, für den seltenen Fall einer langen Klausel ohne Trenner.
FACT_PROXIMITY_CHARS = 110

# Klausel-Grenzen in Kanon-Fakten: Satzende, Semikolon, Gedankenstrich,
# Doppelpunkt-vor-Großbuchstabe. `solution`-Absätze sind oft Bandwurmsätze,
# die mehrere unabhängige Teilaussagen nur mit Semikolon/Gedankenstrich statt
# Punkt verbinden — ein reiner Satz-Split (nur '.','!','?') übersieht das:
# "...ended his marriage four years ago; she has no knowledge of ... Marcus
# Toll..." ist ein Satz, zwei Klauseln, nichts verbindet die Jahreszahl mit
# Marcus. Zeichen-Nähe allein reicht nicht (dieses Paar lag bei nur 62 Zeichen
# Abstand) — erst der Klausel-Split trennt sie zuverlässig.
_CLAUSE_SPLIT_RE = re.compile(r"(?:(?<=[.!?;])\s+|\s+[—-]\s+|:\s+(?=[A-Z]))")


def canon_time_anchors(data: dict) -> tuple[dict[str, list[tuple[float, str]]], dict[str, set[str]]]:
    """Zeitangaben aus den objective_facts, verankert an den Eigennamen ihrer
    KLAUSEL: {'panopticon': [(120.0, 'four months'), (5475.0, 'fifteen
    years')]}, plus pro Name die Threads, aus denen seine Dauer-Fakten
    stammen.

    Eigennamen sind der einzige Anker, der präzise genug ist. Ein Versuch, über
    beliebige Nomen zu verankern, produzierte auf denselben zwei Serien 127
    Meldungen, praktisch alle falsch ('drei Blocks', '94 Prozent') — Nomen mit
    Zahlen variieren legitim, Kanon-Fakten zu Eigennamen nicht.

    **Klausel-, nicht Fakt-Ebene** (Fund 19.07.2026, dritte Testserie):
    `solution` ist oft ein mehrklausiger Bandwurmsatz. Auf Fakt-Ebene
    attribuiert reißt das Namen und Dauern zusammen, die nichts miteinander
    zu tun haben — 'The Front Page'-solution nennt in einer Klausel Ayas
    sechs Monate Recherche, eine Klausel weiter Zhaos verstecktes
    Panopticon; auf Fakt-Ebene hieß das fälschlich 'Panopticon: sechs
    Monate'. Ein Zeichen-Fenster allein reichte nicht (das Marcus/Custody-
    Beispiel im Docstring von `_CLAUSE_SPLIT_RE` lag mit 62 Zeichen unter
    jeder sinnvollen Schwelle) — erst der Klausel-Split trennt zuverlässig.

    Die Thread-Zuordnung geht zusätzlich an `_usable_anchors`: Namen, deren
    Dauer-Fakten aus MEHR ALS EINEM Thread stammen, werden dort ausgeschlossen
    — Begründung im Docstring dort."""
    anchors: dict[str, list[tuple[float, str]]] = defaultdict(list)
    threads_by_name: dict[str, set[str]] = defaultdict(set)
    for t_idx, thread in enumerate(data.get("threads") or []):
        facts = list(thread.get("objective_facts") or [])
        if isinstance(thread.get("solution"), str):
            facts.append(thread["solution"])
        clauses = [c for fact in facts for c in _CLAUSE_SPLIT_RE.split(fact) if c]
        for clause in clauses:
            durations = _durations_with_pos(clause)
            if not durations:
                continue
            # {2,}: auch kurze Eigennamen wie "Aya" müssen ankern können —
            # der Docstring-Motivfall oben wäre mit {3,} nie gefunden worden.
            for name_match in re.finditer(r"\b[A-Z][a-z]{2,}\b", clause):
                name = name_match.group(0)
                if name.lower() in _GENERIC_HEADS or name in _SENTENCE_STARTERS:
                    continue
                nearby = [(days, phrase) for days, phrase, pos in durations
                         if abs(pos - name_match.start()) <= FACT_PROXIMITY_CHARS]
                if not nearby:
                    continue
                # Fallback auf den Index: label-lose Threads dürfen nicht alle
                # auf "" kollabieren, sonst zählt der Mehrfach-Thread-Filter
                # in _usable_anchors zwei fremde Threads als einen.
                threads_by_name[name.lower()].add(
                    thread.get("label") or f"#thread-{t_idx}")
                for days, phrase in nearby:
                    if (days, phrase) not in anchors[name.lower()]:
                        anchors[name.lower()].append((days, phrase))
    return dict(anchors), dict(threads_by_name)


def _usable_anchors(data: dict, anchors: dict, threads_by_name: dict,
                    scripts: dict[int, str]) -> dict:
    """Anker müssen ENTITÄTEN sein, keine Figuren und nichts Allgegenwärtiges —
    und ihre Dauer-Fakten dürfen nicht aus mehreren Threads stammen.

    Ohne den Häufigkeits-Filter verankert der Check auf 'Adrian', 'Captain',
    'Detective' — Wörter, die in jeder zweiten Zeile stehen, sodass jedes
    Zeitfenster irgendeine Zeitangabe enthält. Auf denselben zwei Serien fiel
    die Zahl der Meldungen dadurch von 90 auf ein handhabbares Maß.

    Der Mehrfach-Thread-Filter kam erst bei einer dritten Serie zutage
    ("The Amaranth Clock", 19.07.2026): trägt ein Name Dauer-Fakten aus zwei
    Threads (z.B. 'Walter' — 8 Monate toter Vater in Thread A, sechs Wochen/
    zwölf Jahre alte Brandstiftung in Thread B), erzeugt der Ratio-Vergleich
    Zufallstreffer zwischen zwei völlig unabhängigen Ereignissen, die nur
    denselben Namen in der Nähe haben (6/6 Fehlalarme). Der frühere Testfall
    'Panopticon' übersteht den Filter trotz Erwähnung in zwei Threads, weil
    nur EINER davon tatsächlich eine Dauer nennt — nur Threads mit einer
    eigenen Dauer-Angabe zählen als Mehrdeutigkeit."""
    from fabrik.writing.phrase_stats import name_words
    blocked = set(name_words(data)) | {
        "captain", "detective", "officer", "sergeant", "lieutenant", "doctor",
        "mister", "missus", "father", "mother", "sister", "brother",
    }
    joined = " ".join(speech_text(t) for t in scripts.values()).lower()
    budget = max(3, 3 * len(scripts))
    usable = {}
    for anchor, values in anchors.items():
        if anchor in blocked:
            continue
        if len(threads_by_name.get(anchor, ())) > 1:
            continue
        if len(re.findall(r"\b" + re.escape(anchor) + r"\b", joined)) > budget:
            continue
        usable[anchor] = values
    return usable


def canon_time_conflicts(data: dict, scripts: dict[int, str],
                         window: int = 220) -> list[dict]:
    """Prosa-Zeitangaben in der Nähe eines Kanon-Eigennamens, die keiner der
    für diesen Namen festgelegten Kanon-Angaben entsprechen.

    Gemeldet wird nur das Band zwischen `MIN_CONFLICT_RATIO` und
    `MAX_CONFLICT_RATIO`: darunter ist es dieselbe Angabe (gerundet), darüber
    redet die Stelle offensichtlich von etwas anderem ("zwei Minuten" neben
    "Panopticon" meint nicht dessen Laufzeit)."""
    raw_anchors, threads_by_name = canon_time_anchors(data)
    anchors = _usable_anchors(data, raw_anchors, threads_by_name, scripts)
    if not anchors:
        return []
    out = []
    for ep in sorted(scripts):
        speech = speech_text(scripts[ep])
        low = speech.lower()
        for anchor, canon_values in sorted(anchors.items()):
            for hit in re.finditer(r"\b" + re.escape(anchor) + r"\b", low):
                start = max(0, hit.start() - window)
                chunk = speech[start:hit.end() + window]
                for days, phrase in _durations_in(chunk):
                    ratios = [max(days, cv) / min(days, cv)
                              for cv, _ in canon_values if cv > 0 and days > 0]
                    if not ratios:
                        continue
                    closest = min(ratios)
                    if MIN_CONFLICT_RATIO <= closest <= MAX_CONFLICT_RATIO:
                        out.append({
                            "episode": ep, "anchor": anchor, "prose": phrase,
                            "prose_days": days,
                            "canon": [p for _, p in canon_values],
                            "quote": " ".join(chunk.split())[:200],
                        })
    # Dieselbe Prosa-Angabe kann über mehrere Anker gefunden werden.
    seen = set()
    unique = []
    for item in out:
        key = (item["episode"], item["anchor"], item["prose"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _fmt_days(days: float) -> str:
    if days < 1 / 24:
        return f"{days * 1440:.0f} Min."
    if days < 1:
        return f"{days * 24:.0f} Std."
    if days < 14:
        return f"{days:.0f} Tage"
    if days < 60:
        return f"{days / 7:.0f} Wochen"
    return f"{days / 30:.0f} Monate"


def build_continuity_report(data: dict, scripts: dict[int, str]) -> str:
    """Menschenlesbarer Serien-Report (CONTINUITY_REPORT.txt)."""
    places = unknown_place_names(data, scripts)
    types = place_type_conflicts(data, scripts)
    times = canon_time_conflicts(data, scripts)

    lines = ["Kontinuitäts-Report (deterministisch, fabrik/writing/continuity.py)",
             f"Episoden ausgewertet: {', '.join(str(n) for n in sorted(scripts))}",
             ""]

    lines.append("1. Ortsnamen, die der Kanon nicht kennt")
    if places:
        canon = sorted(canon_place_names(data))
        lines.append(f"   Kanon-Orte: {', '.join(canon)}")
        for name, eps in places:
            lines.append(f"   !! \"{name}\" — Episode {', '.join(str(e) for e in eps)}")
    else:
        lines.append("   Keine.")
    lines.append("")

    lines.append("2. Ortstyp weicht vom Kanon ab (gleicher Besitzer)")
    if types:
        for item in types:
            eps = ", ".join(str(e) for e in item["episodes"])
            lines.append(f"   !! {item['owner']}: Kanon \"{item['canon_type']}\", "
                         f"Prosa \"{item['used']}\" — Episode {eps}")
    else:
        lines.append("   Keine.")
    lines.append("")

    lines.append("3. Zeitangaben, die dem Kanon widersprechen")
    if times:
        for item in times:
            canon_joined = '" / "'.join(item["canon"])
            lines.append(f"   !! Episode {item['episode']}, \"{item['anchor']}\": "
                         f"Prosa \"{item['prose']}\" ({_fmt_days(item['prose_days'])}), "
                         f"Kanon \"{canon_joined}\"")
            lines.append(f"      …{item['quote']}…")
    else:
        lines.append("   Keine.")
    lines.append("")
    return "\n".join(lines)


def build_continuity_block(data: dict, scripts: dict[int, str],
                           max_items: int = 12) -> str:
    """Prompt-Block für die NÄCHSTE Episode: die harten Werte, die schon
    festliegen. Leerer String, wenn es nichts festzuhalten gibt — dann hängt
    der Writer auch nichts an."""
    if not scripts:
        return ""
    lines: list[str] = []

    canon = sorted(canon_place_names(data))
    if canon:
        lines.append("CANONICAL PLACE NAMES — use these exact names, do not invent "
                     "variants or new institutions:")
        lines += [f"  - {name}" for name in canon]

    # Höchststände der Serien-Zähler: die Zahlen, hinter die die neue Episode
    # nicht zurückfallen darf.
    per_noun: dict[str, float] = {}
    episodes_seen: dict[str, set[int]] = defaultdict(set)
    for ep, text in scripts.items():
        for value, noun, _ in extract_quantities(text):
            episodes_seen[noun].add(ep)
            if value > per_noun.get(noun, 0):
                per_noun[noun] = value
    counters = [(n, v) for n, v in per_noun.items()
                if len(episodes_seen[n]) >= MIN_COUNTER_EPISODES]
    counters.sort(key=lambda item: -item[1])
    if counters:
        lines.append("ESTABLISHED COUNTS so far this season — the story has already "
                     "reached these numbers; never state a lower one for the same thing:")
        for noun, value in counters[:max_items]:
            lines.append(f"  - {value:.0f} {noun}")
    return "\n".join(lines)
