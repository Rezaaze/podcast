#!/usr/bin/env python3
"""
Erzeugt automatisch eine komplett neue Serie unter series/<slug>/ via
Claude CLI — inkl. episodes.json, Ordnerstruktur und LATEST-Pointer.

Jede Serie lebt in ihrem eigenen Ordner; anders als früher wird dabei
NICHTS mehr archiviert oder verschoben — beliebig viele Serien existieren
parallel (archive/ bleibt nur für Alt-Bestände aus dem alten Layout).

Der Creator-Prompt kommt aus templates/<template>/EPISODES_CREATOR_PROMPT.md:
  --template narration        Anthologie mit einem Erzähler (Standard)
  --template language_course  Chinesisch-Sprachkurs als Multi-Voice-Hörspiel

Bezieht figure_history.json ein, damit keine Figur aus früheren Serien
wiederverwendet wird.

Voraussetzung:
  Claude Code installiert und eingeloggt ('claude' im Terminal, /login)

Nutzung (vom Projekt-Root aus):
  python3 -m fabrik.cli.create_series "Kurzbeschreibung der neuen Serie/des Themas"
  python3 -m fabrik.cli.create_series "HSK 3-4 Detektiv-Serie im Teehaus" --template language_course

Danach:
  python3 -m fabrik.cli.generate_episode all
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Optional

from fabrik.core import config, history, paths, sections as pf_sections, textproc, workspace
from fabrik.core.claude_cli import describe_json_error, parse_json_response, run_claude_process

TIMEOUT_SECONDS = 900
MAX_ATTEMPTS = 3
DEFAULT_EPISODE_COUNT = 3
DEFAULT_MINUTES = 35.0
DEFAULT_LOCATION_COUNT = 4
# Grobe Sprechgeschwindigkeit für Qwen3-TTS-Erzähltempo — nur zur Umrechnung
# Minuten -> Ziel-Wortzahl, keine exakte Vorhersage der gerenderten Audiolänge.
WORDS_PER_MINUTE = 150

# case-basierte Templates (case/character_knowledge pro Rolle UND — bei soap_opera —
# pro Thread) durchlaufen seit dem Stage-01-Umbau (docs/konzept-stage-umbau.md) die
# Drei-Stufen-Kette Kanon -> Staffelbogen -> Episoden (generate_case_based_series())
# statt eines Ein-Schuss-/Batch-Aufrufs; narration/media_analysis/language_course/
# shorts bleiben beim einfachen Ein-Schuss-Pfad (generate_with_retry()).
CASE_BASED_TEMPLATES = {"crime_drama", "soap_opera"}

# Detailtiefe-Band für section['what'] (sprachneutrale Länge-Einheiten, siehe
# textproc.count_length_units) — hartes Vertragsfeld in EPISODE_PROMPT.md
# ({{SECTION_WORDS_MIN}}/{{SECTION_WORDS_MAX}}), nicht nur ein Pflichtfeld ohne
# Zielwert (CONCOCT-Lektion, docs/konzept-stage-umbau.md): sonst kann derselbe
# Kipp-Effekt zwischen "erzählte Szene" und "Stichwort" auch INNERHALB einer
# Episode wieder auftreten, nur ohne die alte Batch-Grenze als sichtbaren Marker.
# Kalibriert an der Referenztabelle (T0.3): gesunde Bestandsserien liegen bei
# Ø 13-31 Einheiten in ihrer schwächsten Episode, kaputte fallen auf Ø 3-8.
SECTION_WORDS_MIN = 12
SECTION_WORDS_MAX = 30

# Obergrenze für gleichzeitig laufende Episoden-Konzept-Calls in generate_case_based_series()
# — jeder ist unabhängig (sieht nur canon.json + arc.json, nicht die Ausgabe anderer
# Episoden), analog zum alten BATCH_PARALLEL_CAP, nur pro Episode statt pro Batch.
EPISODE_CONCEPT_PARALLEL_CAP = 4


def load_creator_prompt(template: str) -> str:
    prompt_file = os.path.join(paths.template_dir(template), "EPISODES_CREATOR_PROMPT.md")
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        available = sorted(
            d for d in os.listdir(paths.TEMPLATES_DIR)
            if os.path.exists(os.path.join(paths.TEMPLATES_DIR, d, "EPISODES_CREATOR_PROMPT.md"))
        ) if os.path.isdir(paths.TEMPLATES_DIR) else []
        print(f"❌  {prompt_file} nicht gefunden.")
        if available:
            print(f"    Verfügbare Templates: {', '.join(available)}")
        sys.exit(1)


def load_stage_prompt(template: str, filename: str) -> str:
    """Lädt eine der drei Kanon/Bogen/Episoden-Prompt-Dateien (CANON_PROMPT.md/
    ARC_PROMPT.md/EPISODE_PROMPT.md) unter templates/<template>/ — Pendant zu
    load_creator_prompt() für die CASE_BASED_TEMPLATES-Drei-Stufen-Kette."""
    prompt_file = os.path.join(paths.template_dir(template), filename)
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌  {prompt_file} nicht gefunden.")
        sys.exit(1)


def estimate_section_count(template_text: str, minutes: float) -> int:
    """Leitet aus der im Template selbst hinterlegten format.parts_per_section
    und format.words_per_part_target-Mitte ab, wie viele Sections nötig sind,
    um bei WORDS_PER_MINUTE die gewünschten Minuten zu erreichen. Damit
    skaliert die Struktur mit der gewünschten Episodenlänge, statt pro
    Template auf eine feste Section-Zahl zu bestehen.

    Kann ein Wert nicht aus dem Template gelesen werden, wird LAUT gewarnt
    statt stumm auf Defaults zurückzufallen — sonst ändert eine harmlose
    Umformulierung im Template unbemerkt die Episodenlänge."""
    pps_match = re.search(r'"parts_per_section":\s*(\d+)', template_text)
    if pps_match:
        parts_per_section = int(pps_match.group(1))
    else:
        parts_per_section = config.DEFAULTS["parts_per_section"]
        print(f"⚠️  WARNUNG: 'parts_per_section' nicht im Creator-Template gefunden — "
              f"nutze Default {parts_per_section}. Die --minutes-Umrechnung kann dadurch "
              f"deutlich danebenliegen (Template-Format prüfen).")

    # akzeptiert '"300 to 500"', '"300-500"', '"300 – 500"'
    target_match = re.search(r'"words_per_part_target":\s*"(\d+)\s*(?:to|-|–|—)\s*(\d+)"', template_text)
    if target_match:
        mid_words = (int(target_match.group(1)) + int(target_match.group(2))) / 2
    else:
        mid_words = 475
        print(f"⚠️  WARNUNG: 'words_per_part_target' nicht im Creator-Template gefunden — "
              f"nutze Default-Mitte {mid_words:g} Wörter/Part. Die --minutes-Umrechnung "
              f"kann dadurch deutlich danebenliegen (Template-Format prüfen).")

    total_words = minutes * WORDS_PER_MINUTE
    return max(3, round(total_words / (parts_per_section * mid_words)))


def _inject_figure_history(template_text: str) -> str:
    """Setzt {{FIGURE_HISTORY}} (oder, bei Alt-Templates ohne Platzhalter, den
    Regex-Fallback auf den 'ALREADY-USED FIGURES'-Abschnitt) — geteilt zwischen
    dem Ein-Schuss-Creator-Prompt (build_prompt) und dem neuen Kanon-Prompt
    (build_canon_prompt), beide brauchen dieselbe Anti-Wiederholungs-Liste."""
    used = "\n".join(
        f"- {h['figure']} (Serie: {h['series_title']})"
        for h in history.load_figure_history()
    ) or "(noch keine)"

    if "{{FIGURE_HISTORY}}" in template_text:
        return template_text.replace("{{FIGURE_HISTORY}}", used)
    # Alt-Template ohne Platzhalter: Regex-Fallback — und wenn auch der
    # nicht greift, LAUT warnen, sonst wiederholen sich Figuren still.
    replaced, n = re.subn(
        r"ALREADY-USED FIGURES.*?(?=\n\nSTRICT OUTPUT RULES)",
        f"ALREADY-USED FIGURES (do not reuse any of these — pick different "
        f"people/subjects for every episode, even if the new series covers "
        f"a similar theme):\n{used}\n",
        template_text,
        flags=re.DOTALL,
    )
    if n:
        return replaced
    print("⚠️  WARNUNG: Creator-Template hat weder {{FIGURE_HISTORY}} noch einen "
          "'ALREADY-USED FIGURES'-Abschnitt — die Figuren-Historie wird NICHT "
          "injiziert, frühere Figuren können sich wiederholen.")
    return template_text


def _inject_model_and_roster(template_text: str) -> str:
    """Single-Source-Substitutionen (Chelsie-Lektion): Stimmen-Roster und
    Default-Modell leben in config.py und werden hier eingesetzt, statt
    wörtlich in den Templates zu altern. Geteilt zwischen allen Prompt-Bauern,
    die {{DEFAULT_MODEL}}/{{VOICE_ROSTER}} referenzieren können."""
    template_text = template_text.replace("{{DEFAULT_MODEL}}", config.DEFAULTS["model"])
    roster_bullets = "\n".join(
        f"  - {name} ({gender}) — {desc}."
        for name, gender, desc in config.BUILTIN_SPEAKER_ROSTER
    )
    roster_compact = ", ".join(
        f"{name} ({gender[0]}, {desc.split(',')[0]})"
        for name, gender, desc in config.BUILTIN_SPEAKER_ROSTER
    )
    template_text = template_text.replace("{{VOICE_ROSTER}}", roster_bullets)
    template_text = template_text.replace("{{VOICE_ROSTER_COMPACT}}", roster_compact)
    return template_text


def _warn_leftover_placeholders(template_text: str, label: str = "Template") -> None:
    leftover = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", template_text)))
    if leftover:
        print(f"⚠️  WARNUNG: unersetzte Platzhalter im {label}: {', '.join(leftover)} — "
              f"sie landen wörtlich im Prompt (Tippfehler im Template?).")


def build_prompt(template_text: str, topic: str, episode_count: int, minutes: float,
                 location_count: int = DEFAULT_LOCATION_COUNT) -> str:
    """Baut den vollen Ein-Schuss-Creator-Prompt (narration/media_analysis/
    language_course/shorts — die CASE_BASED_TEMPLATES nutzen stattdessen
    build_canon_prompt/build_arc_prompt/build_episode_concept_prompt)."""
    template_text = _inject_figure_history(template_text)
    section_count = estimate_section_count(template_text, minutes)
    template_text = template_text.replace("{{EPISODE_COUNT}}", str(episode_count))
    template_text = template_text.replace("{{EPISODE_MINUTES}}", f"{minutes:g}")
    template_text = template_text.replace("{{SECTION_COUNT}}", str(section_count))
    template_text = template_text.replace("{{LOCATION_COUNT}}", str(location_count))
    template_text = _inject_model_and_roster(template_text)
    _warn_leftover_placeholders(template_text, "Creator-Template")
    return template_text + topic


def estimate_section_count_from_format(fmt: dict, minutes: float) -> int:
    """Wie estimate_section_count(), aber liest parts_per_section/
    words_per_part_target direkt aus einem bereits generierten format-Dict
    (canon.json) statt sie per Regex aus einer Template-DATEI zu parsen — im
    01c-Schritt der CASE_BASED_TEMPLATES-Kette sind diese Werte zum Zeitpunkt
    der Episoden-Konzept-Generierung schon konkret bekannt, und EPISODE_PROMPT.md
    enthält die Literale gar nicht (die stehen nur in CANON_PROMPT.md), ein
    Regex-Parse würde also ins Leere laufen."""
    parts_per_section = fmt.get("parts_per_section") or config.DEFAULTS["parts_per_section"]
    match = re.match(r"(\d+)\s*(?:to|-|–|—)\s*(\d+)", str(fmt.get("words_per_part_target", "")))
    mid_words = (int(match.group(1)) + int(match.group(2))) / 2 if match else 475
    total_words = minutes * WORDS_PER_MINUTE
    return max(3, round(total_words / (parts_per_section * mid_words)))


def build_canon_prompt(template_text: str, topic: str, episode_count: int, minutes: float,
                       location_count: int) -> str:
    """01a: Kanon-Prompt (Welt/Cast/Orte/Fakten-Threads, noch keine Episoden)."""
    template_text = _inject_figure_history(template_text)
    template_text = template_text.replace("{{EPISODE_COUNT}}", str(episode_count))
    template_text = template_text.replace("{{EPISODE_MINUTES}}", f"{minutes:g}")
    template_text = template_text.replace("{{LOCATION_COUNT}}", str(location_count))
    template_text = _inject_model_and_roster(template_text)
    _warn_leftover_placeholders(template_text, "Kanon-Template")
    return template_text + topic


def build_arc_prompt(template_text: str, canon: dict, episode_count: int) -> str:
    """01b: Staffelbogen-Prompt — bekommt den fertigen Kanon als Kontext, teilt
    jeden Wendepunkt genau einer Episode zu."""
    template_text = template_text.replace(
        "{{CANON_JSON}}", json.dumps(canon, ensure_ascii=False, indent=2))
    template_text = template_text.replace("{{EPISODE_COUNT}}", str(episode_count))
    _warn_leftover_placeholders(template_text, "Bogen-Template")
    return template_text


def build_episode_concept_prompt(template_text: str, canon: dict, arc: dict, episode_number: int,
                                 minutes: float, section_count: int, words_min: int,
                                 words_max: int) -> str:
    """01c: Episoden-Konzept-Prompt für GENAU eine Episode — Kanon + Bogen als
    Kontext, plus die dieser Episode zugeteilten Wendepunkte und eine
    Kurzfassung der Nachbarepisoden für Kontinuität."""
    arc_episodes = arc.get("episodes", []) if isinstance(arc, dict) else []
    ep_entry = next((e for e in arc_episodes if e.get("episode") == episode_number), {})
    turning_points = [tp for tp in (arc.get("turning_points") or [])
                      if tp.get("episode") == episode_number]
    tps_text = (
        "; ".join(f"[{tp.get('thread')}] {tp.get('event')}" for tp in turning_points)
        if turning_points else
        "(none — this is a breather episode, no turning point to narrate)"
    )
    prev_entry = next((e for e in arc_episodes if e.get("episode") == episode_number - 1), None)
    next_entry = next((e for e in arc_episodes if e.get("episode") == episode_number + 1), None)
    prev_text = f"\"{prev_entry.get('figure', '')}\" — {prev_entry.get('theme', '')}" if prev_entry else ""
    next_text = f"\"{next_entry.get('figure', '')}\" — {next_entry.get('theme', '')}" if next_entry else ""

    replacements = {
        "{{CANON_JSON}}": json.dumps(canon, ensure_ascii=False, indent=2),
        "{{ARC_JSON}}": json.dumps(arc, ensure_ascii=False, indent=2),
        "{{EPISODE_NUMBER}}": str(episode_number),
        "{{EPISODE_COUNT}}": str(len(arc_episodes)),
        "{{EPISODE_MINUTES}}": f"{minutes:g}",
        "{{EPISODE_FIGURE}}": ep_entry.get("figure", ""),
        "{{EPISODE_THEME}}": ep_entry.get("theme", ""),
        "{{EPISODE_TURNING_POINTS}}": tps_text,
        "{{PREV_EPISODE_SUMMARY}}": prev_text,
        "{{NEXT_EPISODE_SUMMARY}}": next_text,
        "{{SECTION_COUNT}}": str(section_count),
        "{{SECTION_WORDS_MIN}}": str(words_min),
        "{{SECTION_WORDS_MAX}}": str(words_max),
    }
    for placeholder, value in replacements.items():
        template_text = template_text.replace(placeholder, value)
    _warn_leftover_placeholders(template_text, f"Episode-{episode_number}-Template")
    return template_text


def compute_timeout(episode_count: int) -> int:
    """Skaliert das Timeout pro Claude-Aufruf mit der Episodenzahl. Eine
    10-Episoden-Soap-Opera mit mehreren parallelen Handlungssträngen pro
    Episode erzeugt um Größenordnungen mehr strukturiertes JSON als eine
    3-Episoden-Anthologie — ein fixes Timeout wartet bei kleinen Serien
    unnötig lange und bricht bei großen zu früh ab. Nach oben gedeckelt,
    damit ein wirklich hängender Prozess nicht unbegrenzt blockiert."""
    return min(3600, max(TIMEOUT_SECONDS, 180 * episode_count))


def call_claude(prompt: str, model: str, timeout: int = TIMEOUT_SECONDS, label: str = "Claude") -> str:
    """Gibt die Rohausgabe zurück, oder "" bei einem Fehler, den ein weiterer
    Versuch vielleicht behebt (Timeout, Server-/API-Fehler) —
    generate_with_retry() behandelt eine leere Antwort wie ungültiges JSON
    und versucht es erneut, statt hier den ganzen Prozess zu beenden. NUR bei
    Fehlern, die kein Retry beheben kann ('claude' fehlt, nicht eingeloggt),
    wird sofort abgebrochen."""
    argv = ["claude", "-p", prompt, "--output-format", "text", "--model", model, "--tools", ""]
    try:
        result = run_claude_process(argv, timeout, label)
    except FileNotFoundError:
        print("❌  'claude' nicht gefunden → Claude Code installieren.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"⚠️  Timeout nach {timeout}s.")
        return ""

    if result.returncode != 0:
        output = (result.stderr.strip() or result.stdout.strip())[:500]
        if "401" in output or "authentication" in output.lower():
            print("❌  Nicht eingeloggt → 'claude' im Terminal öffnen und /login ausführen.")
            sys.exit(1)
        print(f"⚠️  Claude-CLI-Fehler (exit {result.returncode}): {output}")
        return ""

    return result.stdout.strip()


def print_raw_snippet(raw: str, indent: str = "  ") -> None:
    """Diagnose-Ausgabe für eine nicht auswertbare Claude-Antwort (ungültiges JSON, oder —
    beim Episoden-Batch — keine passende 'episodes'-Liste). Echte Zeilenumbrüche statt
    repr(), damit der Ausschnitt beim Kopieren aus dem Terminal nicht als eine einzige,
    unhandliche Zeile endet (repr() escaped '\\n' zu literalem Text und macht daraus eine
    Riesenzeile, die beim Copy-Paste aus manchen Terminals mittendrin abgeschnitten wird).

    Zeigt bevorzugt die Fehlerstelle selbst (describe_json_error() — pinpointed per
    JSONDecodeError-Position, mit Kontext-Fenster drumherum): bei einer großen Serie kann
    ein echter Syntaxfehler mitten im mehrere tausend Zeichen langen Dokument liegen, wo
    weder Anfang noch Ende der Antwort etwas verraten (beobachtet in der Praxis: Anfang und
    Ende sahen beide sauber geschlossen aus, der eigentliche Fehler lag dazwischen). Fällt
    auf Anfang/Ende zurück, wenn describe_json_error() gar keinen {...}-Block findet (z.B.
    reiner Fließtext ohne jeden JSON-Versuch) oder das Modell explizit angekündigt hat, in
    einer 'nächsten Antwort' fortzusetzen (bei einem einzelnen '-p'-Aufruf gibt es die
    nicht — dann ist oft nur zu wenig statt syntaktisch kaputtes JSON das Problem, Anfang/
    Ende zeigt das direkter als eine Fehlerposition)."""
    print(f"{indent}🔍  Rohantwort ({len(raw)} Zeichen), nicht auswertbar:")
    detail = describe_json_error(raw)
    if detail:
        print(f"{indent}    {detail}")
    else:
        print(f"{indent}    ANFANG: {raw[:200]}")
        if len(raw) > 200:
            print(f"{indent}    ENDE:   {raw[-200:]}")


TRUNCATION_MIN_CHARS = 3000  # ab dieser Länge gilt "an keiner Position dekodierbar" als Abriss-Signal


# Deckt das längste dekodierbare Objekt weniger als diesen Anteil der Antwort ab,
# ist es nur ein inneres Fragment — das Gesamtobjekt wurde nie geschlossen.
TRUNCATION_FRAGMENT_RATIO = 0.5


def response_looks_truncated(raw: str) -> bool:
    """Heuristik für eine mitten im JSON ABGESCHNITTENE Antwort — der Fehlermodus,
    den Retry-mit-Feedback prinzipiell nicht beheben kann (es ist ein Längen-, kein
    Inhaltsproblem; das Modell würde beim nächsten Versuch genauso lang antworten).

    Drei Signale: (1) das Modell kündigt selbst eine Fortsetzung an ("continuing in
    the next reply" — die es bei einem einzelnen '-p'-Aufruf nie gibt); (2) eine
    lange Antwort mit '{', die parse_json_response an KEINER Position dekodieren
    kann; (3) — der häufigste Fall — parse_json_response findet zwar etwas, aber
    nur ein INNERES Fragment: bei abgeschnittenem Gesamt-JSON ist das längste
    vollständig dekodierbare Objekt typischerweise ein einzelnes Episode-/Unter-
    objekt, das nur einen Bruchteil der Antwort abdeckt (das Gesamtobjekt wurde
    nie geschlossen). Eine VOLLSTÄNDIGE Antwort dekodiert dagegen praktisch die
    ganze Länge (Fences/Whitespace sind vernachlässigbar), und eine kurze kaputte
    Antwort ist eher ein echter Syntax-/Verhaltensfehler, den Feedback sehr wohl
    fixen kann — deshalb die Mindestlänge."""
    if re.search(r"continu\w+ in (?:the )?next (?:reply|response|message)", raw, re.IGNORECASE):
        return True
    if len(raw) < TRUNCATION_MIN_CHARS or "{" not in raw:
        return False
    parsed = parse_json_response(raw)
    if parsed is None:
        return True
    covered = len(json.dumps(parsed, ensure_ascii=False))
    return covered < len(raw) * TRUNCATION_FRAGMENT_RATIO


def generate_with_retry(prompt: str, model: str, episode_count: int):
    """Nur für Nicht-CASE_BASED_TEMPLATES (narration/media_analysis/
    language_course/shorts) — die case-based Templates laufen seit dem
    Stage-01-Umbau über generate_case_based_series(). Bis zu MAX_ATTEMPTS
    Claude-Aufrufe: ungültiges JSON, Struktur-Fehler aus validate_data und
    eine falsche Episodenanzahl werden als konkretes Feedback in den
    nächsten Versuch gegeben (gleicher Mechanismus wie
    call_claude_with_retry beim Skript-Writer). Gibt (data, warnings)
    zurück, oder (None, []) wenn kein einziger Versuch fallback-sicher war
    — der Aufrufer (main()) bricht dann ab.

    Best-Effort-Fallback (analog zu validate_parts()/call_claude_with_retry() beim
    Skript-Writer): scheitern alle Versuche NUR an der Episodenzahl — also gültiges
    JSON, das validate_data() ohne Beanstandung durchlässt, nur mit z.B. 8 statt 10
    Episoden — wird der Versuch mit der geringsten Abweichung ("badness") übernommen,
    statt die komplette Generierung wegzuwerfen. Ein Versuch mit echten validate_data-
    Fehlern (kaputtes Schema, würde generate_episode.py's eigene Validierung crashen)
    ist NIE fallback-sicher, genau wie ein FORMAT ERROR bei Skript-Parts nie
    fallback-sicher ist — nur eine falsche Episodenzahl ist ein kosmetischer statt
    ein struktureller Mangel."""
    timeout = compute_timeout(episode_count)
    print(f"  (Timeout pro Versuch: {timeout}s)")
    feedback = ""
    best = None  # (badness, data, warnings) — bester fallback-sicherer Versuch bisher
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            print(f"🔁  Versuch {attempt}/{MAX_ATTEMPTS} (mit Fehler-Feedback) ...")
        raw = call_claude(prompt + feedback, model, timeout=timeout,
                          label=f"Serie generieren (Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            # Timeout oder API-Fehler — call_claude hat den Grund schon geloggt.
            # Nichts Inhaltliches zu korrigieren, also ohne (irreführendes)
            # Feedback erneut versuchen statt Claude "kein valides JSON" vorzuwerfen.
            feedback = ""
            continue

        data = parse_json_response(raw)
        if data is None:
            errors = ["Die Antwort war kein valides JSON-Objekt."]
            warnings = []
            fallback_safe = False
            badness = 0
            # Nur zur Konsole, NICHT Teil von errors/feedback — der Snippet würde im
            # nächsten Prompt nur Tokens verschwenden, ohne Claude beim Fixen zu helfen.
            # Ohne das war eine fehlgeschlagene Antwort bisher komplett unsichtbar:
            # call_claude() gibt raw nirgends aus, parse_json_response() wirft nie,
            # also blieb nur die generische "kein valides JSON"-Meldung übrig.
            print_raw_snippet(raw, indent="  ")
        else:
            errors, warnings = config.validate_data(data)
            fallback_safe = not errors  # nur echte Schema-Fehler schließen den Fallback aus
            actual = len(data.get("episodes", [])) if isinstance(data.get("episodes"), list) else 0
            badness = abs(actual - episode_count)
            if actual != episode_count:
                errors.append(f"{actual} Episode(n) generiert, gefordert waren {episode_count}.")

        if not errors:
            return data, warnings

        if fallback_safe and (best is None or badness < best[0]):
            best = (badness, data, warnings)

        print(f"⚠️  Versuch {attempt} abgelehnt ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"  - {e}")
        if response_looks_truncated(raw):
            # Abriss ist ein Längen-, kein Inhaltsproblem — weitere Ein-Schuss-
            # Versuche mit Feedback scheitern identisch und kosten je mehrere
            # Minuten. (Der Check sitzt bewusst HIER und nicht nur im Parse-
            # Fehler-Zweig: parse_json_response findet in einer abgeschnittenen
            # Antwort meist ein inneres Teilobjekt, das dann an validate_data
            # scheitert — der Abriss tarnt sich also als Validierungsfehler.)
            print("  ✂️  Antwort ist offenbar ABGESCHNITTEN (Abriss-Signal erkannt) — "
                  "weitere Ein-Schuss-Versuche können das nicht beheben, breche früh ab.")
            break
        feedback = (
            "\n\nIMPORTANT — your previous attempt was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again "
              "(full object, not a diff), following every rule above."
        )

    if best is not None:
        badness, data, warnings = best
        actual = len(data.get("episodes", []))
        print(f"⚠️  Alle {MAX_ATTEMPTS} Versuche verfehlten die geforderte Episodenzahl exakt — "
              f"übernehme den strukturell sauberen Versuch mit {actual} statt {episode_count} "
              f"Episode(n) (Abweichung: {badness}) statt komplett abzubrechen. Bei Bedarf "
              f"episodes.json manuell um weitere Episoden ergänzen oder neu generieren.")
        return data, warnings

    print(f"⚠️  Auch nach {MAX_ATTEMPTS} Versuchen kein brauchbares Ergebnis im Ein-Schuss-Modus "
          f"(typischerweise: die Antwort wird bei einer großen Serie mitten im JSON abgeschnitten, "
          f"kein inhaltliches Problem, das sich durch Feedback beheben ließe).")
    return None, []


def compute_batch_timeout(batch_size: int) -> int:
    """Timeout für einen kleineren Teil-Aufruf (heute: die gezielte
    Episoden-/Serien-Feld-Reparatur in _repair_series_episodes()/
    _repair_series_globals()) — kleinerer Floor als compute_timeout(), so
    ein Teil-Aufruf trägt nur wenige Episoden bzw. gar keine."""
    return min(2400, max(450, 180 * batch_size))


def _normalize_ws(text: str) -> str:
    return " ".join(str(text).split())


def _episode_threads(episode: dict) -> list:
    """episode['case'] als Liste von Thread-Dicts — crime_drama (ein Objekt)
    und soap_opera (Liste) einheitlich behandelt; ein einzelnes Objekt ohne
    'label' bekommt das Pseudo-Label '' (ein Fall = ein Thread)."""
    case = episode.get("case")
    if not case:
        return []
    if isinstance(case, dict):
        return [case]
    return [t for t in case if isinstance(t, dict)]


CHECKPOINT_STAGING_DIR = os.path.join(paths.DATA_DIR, ".create_series_staging")
# Zwischenspeicher für generate_case_based_series(): canon.json, arc.json und jedes
# fertig generierte Episoden-Konzept werden hier als eigene Einheit abgelegt, sobald
# sie erfolgreich sind (_cached_unit()). Scheitert später EINE andere Einheit
# endgültig (nach allen Retries), muss ein Rerun nur den fehlenden Teil neu
# generieren statt die ganze Serie — genau der Fortschrittsverlust, der beim
# Serie-erstellen-Schritt am meisten Zeit kostet (17.07.2026, Nutzer-Feedback). Der
# Ein-Schuss-Pfad (generate_with_retry, für Nicht-CASE_BASED_TEMPLATES) braucht das
# bewusst NICHT: er ist atomar (eine Antwort, ganz oder gar nicht), es gibt dort
# keine Teil-Fortschritte, die es zu retten lohnt.
#
# Geschlüsselt über einen Hash der Eingaben (_checkpoint_key) — ein geänderter
# Aufruf (anderes Thema/Template/Episodenzahl/Minuten) trifft nie einen alten
# Checkpoint, nur ein IDENTISCHER Rerun tut das. Bewusst ohne TTL/Aufräum-Cron wie
# data/.claude_slots/: wird bei vollem Erfolg gelöscht (_clear_checkpoint), ein
# nach endgültigem Scheitern liegen gebliebener Ordner kostet nur ein paar KB.


def _checkpoint_key(topic: str, template: str, episode_count: int, minutes: float,
                    location_count: int, model: str, case_based: bool) -> str:
    """Stabiler Schlüssel für den Batch-Checkpoint dieses Laufs: die AUFRUF-Parameter,
    also genau das, was der Nutzer im Cockpit eingibt. Ein Rerun mit denselben Angaben
    trifft den Checkpoint, jede Änderung (anderes Thema/Template/Episodenzahl/Minuten/
    Orte/Modell) bekommt einen eigenen.

    Bewusst NICHT über den fertig substituierten creator_prompt gehasht (bis 17.07.2026
    genau so, und in der Praxis kaputt): in dem steckt via build_prompt() die komplette
    FIGURE_HISTORY — eine global wachsende Datei, die JEDER generate_episode-Lauf einer
    BELIEBIGEN anderen Serie fortschreibt. Bei mehreren parallel laufenden Cockpits
    änderte sich der Prompt-Text dadurch im Minutentakt, der Hash mit ihm, und ein Rerun
    fand seinen eigenen Checkpoint nie wieder — er generierte Skeleton und alle Batches
    neu, obwohl sie fertig auf Platte lagen (Nutzer-Symptom 17.07.2026: "er generiert
    gerade das Skeleton wieder, warum?"). Inhaltlich veraltet der Checkpoint dadurch
    nicht: die Figuren dieser Serie sind längst gewählt, die Historie ist im Prompt nur
    eine "nimm diese nicht"-Liste. Ein Treffer aus einem Lauf von vor ein paar Minuten
    kann damit höchstens eine Figur wiederholen, die inzwischen woanders vergeben wurde
    — genau dafür gibt es history.warn_on_repeated_figures()."""
    payload = "\x1f".join([topic, template, str(episode_count), f"{minutes:g}",
                           str(location_count), model, str(case_based)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _checkpoint_dir(key: str) -> str:
    return os.path.join(CHECKPOINT_STAGING_DIR, key)


def _load_checkpoint_json(path: str):
    """None bei fehlender ODER kaputter Datei — ein korrupter/unvollständiger
    Checkpoint (z.B. Prozess während des Schreibens gekillt) darf den Lauf nie
    blockieren, führt nur zur Neu-Generierung dieses EINEN Teils."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _save_checkpoint_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _clear_checkpoint(key: str) -> None:
    """Räumt den Staging-Ordner nach VOLLEM Erfolg weg — die Serie ist jetzt in
    episodes.json materialisiert, der Checkpoint hat seinen Zweck erfüllt."""
    shutil.rmtree(_checkpoint_dir(key), ignore_errors=True)


def _cached_unit(checkpoint_key: str, unit_name: str, generate_fn, validate_fn=None):
    """Wrapper mit Checkpoint um EINE Generierungs-Einheit (canon/arc/episode_N) von
    generate_case_based_series(): lädt eine bereits erfolgreich generierte Einheit von
    Platte statt sie neu zu erzeugen, speichert eine frisch erfolgreiche sofort.
    validate_fn (optional): bekommt den geladenen Checkpoint-Wert, gibt eine Fehlerliste
    zurück (leer = gültig) — verwirft und regeneriert einen Checkpoint, der seit einer
    Code-Änderung nicht mehr zum aktuellen Schema passt (Muster aus dem alten
    Skeleton-Checkpoint). generate_fn wird nur bei einem Cache-Miss aufgerufen (lazy)."""
    path = os.path.join(_checkpoint_dir(checkpoint_key), f"{unit_name}.json")
    cached = _load_checkpoint_json(path)
    if cached is not None:
        errors = validate_fn(cached) if validate_fn else []
        if not errors:
            print(f"    ↺  {unit_name} aus Checkpoint übernommen — Generierung übersprungen.")
            return cached
        print(f"    ⚠️  Checkpoint für {unit_name} ist ungültig (Code seither geändert?) — "
              f"wird verworfen und neu generiert.")
    result = generate_fn()
    if result is not None:
        _save_checkpoint_json(path, result)
    return result


def validate_canon(data, template: str) -> list:
    """01a-Validierung: baut ein minimales Kandidat-Dokument mit einer Platzhalter-
    Episode (dieselbe Technik, mit der der alte Batch-Pfad ein Teil-Dokument gegen
    config.validate_data() prüfte) — die vorhandene Prüfung für
    voices/locations/format/audio/generation/threads greift dadurch ohne Duplikation.
    Ergänzt nur, was config.validate_data() bewusst NICHT kennt: wie viele Threads
    ein Template erwartet (Schema-agnostisch, eine Generierungsentscheidung)."""
    if not isinstance(data, dict):
        return ["canon.json war kein JSON-Objekt."]
    candidate = json.loads(json.dumps(data))
    candidate.setdefault("template", template)
    candidate["episodes"] = [{
        "figure": "placeholder", "theme": "placeholder",
        "sections": ["placeholder scene"],
    }]
    errors, _warnings = config.validate_data(candidate)
    errors = [e for e in errors if "episodes[0]" not in e]
    threads = data.get("threads")
    if not isinstance(threads, list) or not threads:
        errors.append("'threads' fehlt oder ist keine nicht-leere Liste.")
    elif template == "crime_drama" and len(threads) != 1:
        errors.append(f"'threads' muss bei crime_drama genau 1 Eintrag haben (hat {len(threads)}) "
                      f"— crime_drama hat EINEN durchgehenden Fall pro Staffel.")
    elif template == "soap_opera" and not (2 <= len(threads) <= 4):
        errors.append(f"'threads' muss bei soap_opera 2 bis 4 Einträge haben (hat {len(threads)}).")
    return errors


def generate_canon(topic: str, template: str, episode_count: int, minutes: float,
                   location_count: int, model: str):
    """01a: EIN Claude-Call für Welt/Cast/Orte/Fakten-Threads — noch keine Episoden.
    Retry-mit-Feedback wie generate_with_retry(), aber ohne Best-Effort-Fallback (ein
    Kanon ist entweder brauchbar oder nicht, keine sinnvolle Zwischenstufe wie bei
    einer Episodenzahl-Abweichung)."""
    template_text = load_stage_prompt(template, "CANON_PROMPT.md")
    prompt = build_canon_prompt(template_text, topic, episode_count, minutes, location_count)
    timeout = compute_timeout(episode_count)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            print(f"  🔁  Kanon — Versuch {attempt}/{MAX_ATTEMPTS} (mit Fehler-Feedback) ...")
        raw = call_claude(prompt + feedback, model, timeout=timeout,
                          label=f"Kanon generieren (Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            feedback = ""
            continue

        data = parse_json_response(raw)
        if data is None:
            print_raw_snippet(raw, indent="  ")
            errors = ["Die Antwort war kein valides JSON-Objekt."]
        else:
            errors = validate_canon(data, template)

        if not errors:
            return data

        print(f"⚠️  Kanon — Versuch {attempt} abgelehnt ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"  - {e}")
        if response_looks_truncated(raw):
            print("  ✂️  Antwort ist offenbar ABGESCHNITTEN — weitere Versuche mit Feedback "
                  "können das nicht beheben, breche früh ab.")
            break
        feedback = (
            "\n\nIMPORTANT — your previous attempt was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again "
              "(full object, not a diff), following every rule above."
        )

    return None


def validate_arc(data, canon: dict, episode_count: int) -> list:
    """01b-Validierung, komplett deterministisch: jeder Wendepunkt referenziert einen
    echten Thread aus dem Kanon, jede Episode 1..N kommt genau einmal vor, kein
    Wendepunkt-'event' dupliziert sich, und jede Episode trägt entweder mindestens
    einen Wendepunkt oder ist ausdrücklich als Atempause markiert — das ist die
    Prüfung, die einen Doppel-Klimax strukturell verhindert (arc.json geht danach in
    JEDEN 01c-Prompt, siehe stage_01c_CONTEXT.md)."""
    if not isinstance(data, dict):
        return ["arc.json war kein JSON-Objekt."]
    errors = []
    thread_labels = {t.get("label") for t in (canon.get("threads") or []) if isinstance(t, dict)}

    turning_points = data.get("turning_points")
    if not isinstance(turning_points, list) or not turning_points:
        errors.append("'turning_points' fehlt oder ist keine nicht-leere Liste.")
        turning_points = []
    seen_events = set()
    episodes_with_tp = set()
    for i, tp in enumerate(turning_points, start=1):
        if not isinstance(tp, dict):
            errors.append(f"turning_points[{i}] muss ein Objekt sein.")
            continue
        thread = tp.get("thread")
        if thread not in thread_labels:
            errors.append(f"turning_points[{i}].thread = '{thread}' ist kein Label aus "
                          f"canon.threads ({sorted(l for l in thread_labels if l)}).")
        ep_num = tp.get("episode")
        if not isinstance(ep_num, int) or not (1 <= ep_num <= episode_count):
            errors.append(f"turning_points[{i}].episode muss eine ganze Zahl zwischen 1 und "
                          f"{episode_count} sein (ist: {ep_num}).")
        else:
            episodes_with_tp.add(ep_num)
        event = _normalize_ws(tp.get("event", "")).lower()
        if not event:
            errors.append(f"turning_points[{i}].event fehlt oder ist leer.")
        elif event in seen_events:
            errors.append(f"turning_points[{i}].event dupliziert einen anderen Wendepunkt "
                          f"(gleicher Text) — jeder Wendepunkt gehört zu GENAU einer Episode.")
        seen_events.add(event)

    episodes = data.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != episode_count:
        actual = len(episodes) if isinstance(episodes, list) else 0
        errors.append(f"'episodes' muss eine Liste mit genau {episode_count} Einträgen sein "
                      f"(hat {actual}).")
        episodes = []
    for i, ep in enumerate(episodes, start=1):
        if not isinstance(ep, dict):
            errors.append(f"arc.episodes[{i}] muss ein Objekt sein.")
            continue
        if ep.get("episode") != i:
            errors.append(f"arc.episodes[{i}].episode muss {i} sein (ist: {ep.get('episode')}) "
                          f"— Reihenfolge/Nummerierung ist Pflicht.")
        for key in ("figure", "theme"):
            if not isinstance(ep.get(key), str) or not ep.get(key, "").strip():
                errors.append(f"arc.episodes[{i}].{key} fehlt oder ist kein nicht-leerer String.")
        if i not in episodes_with_tp and not ep.get("breather"):
            errors.append(f"Episode {i} hat weder einen Wendepunkt noch 'breather: true' — "
                          f"jede Episode braucht eines von beidem.")
    return errors


def generate_arc(canon: dict, episode_count: int, model: str):
    """01b: EIN Claude-Call teilt jeden Thread-Wendepunkt genau einer Episode zu."""
    template_text = load_stage_prompt(canon.get("template"), "ARC_PROMPT.md")
    prompt = build_arc_prompt(template_text, canon, episode_count)
    timeout = compute_timeout(episode_count)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            print(f"  🔁  Staffelbogen — Versuch {attempt}/{MAX_ATTEMPTS} (mit Fehler-Feedback) ...")
        raw = call_claude(prompt + feedback, model, timeout=timeout,
                          label=f"Staffelbogen generieren (Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            feedback = ""
            continue

        data = parse_json_response(raw)
        if data is None:
            print_raw_snippet(raw, indent="  ")
            errors = ["Die Antwort war kein valides JSON-Objekt."]
        else:
            errors = validate_arc(data, canon, episode_count)

        if not errors:
            return data

        print(f"⚠️  Staffelbogen — Versuch {attempt} abgelehnt ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"  - {e}")
        if response_looks_truncated(raw):
            print("  ✂️  Antwort ist offenbar ABGESCHNITTEN — weitere Versuche mit Feedback "
                  "können das nicht beheben, breche früh ab.")
            break
        feedback = (
            "\n\nIMPORTANT — your previous attempt was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again "
              "(full object, not a diff), following every rule above."
        )

    return None


def validate_episode_concept(data, canon: dict, episode_number: int,
                             words_min: int, words_max: int) -> list:
    """01c-Validierung: baut ein Kandidat-Dokument mit GENAU dieser einen Episode aus
    Kanon-Feldern + Konzept-Ausgabe und lässt config.validate_data() die volle
    Struktur (sections/who/thread/location/words gegen voices/threads/locations)
    prüfen — dieselbe Wiederverwendungs-Technik wie validate_canon(). Ergänzt das
    Detailtiefe-Band pro Section (CONCOCT-Lektion, docs/konzept-stage-umbau.md):
    ein Section-'what' unter dem Minimum ODER eine zu große Streuung innerhalb der
    Episode (Faktor > 3 zwischen kürzester und längster Section) wird zurückgewiesen
    — das ist der strukturelle Ersatz für das alte, nachträgliche
    check_section_detail(), jetzt PRO Section und VOR statt NACH der Übernahme."""
    if not isinstance(data, dict):
        return ["Antwort war kein JSON-Objekt."]
    candidate = {
        "series_title": canon.get("series_title") or "x",
        "language": canon.get("language"), "mode": canon.get("mode"),
        "template": canon.get("template"), "voices": canon.get("voices"),
        "locations": canon.get("locations"), "format": canon.get("format"),
        "threads": canon.get("threads"),
        "episodes": [{
            "figure": "x", "theme": "x",
            "intro_note": data.get("intro_note", ""), "outro_note": data.get("outro_note", ""),
            "sections": data.get("sections"), "case": data.get("case"),
        }],
    }
    errors, _warnings = config.validate_data(candidate)
    errors = [e.replace("episodes[0]", f"episode {episode_number}") for e in errors]

    sections = data.get("sections")
    if isinstance(sections, list) and sections:
        lengths = [textproc.count_length_units(pf_sections.section_text(s))
                  for s in sections if isinstance(s, dict)]
        if lengths:
            too_short = [i + 1 for i, length in enumerate(lengths) if length < words_min]
            if too_short:
                errors.append(f"episode {episode_number}: sections {too_short} liegen unter dem "
                              f"Detailtiefe-Minimum ({words_min} Einheiten) — jede Section "
                              f"braucht eine erzählte Szene, kein Stichwort.")
            if min(lengths) > 0 and max(lengths) / min(lengths) > 3:
                errors.append(f"episode {episode_number}: Section-Detailtiefe schwankt zu stark "
                              f"innerhalb der Episode (min {min(lengths)}, max {max(lengths)} "
                              f"Einheiten) — alle Sections sollten im selben Band liegen "
                              f"({words_min}-{words_max}), nicht mal ausführlich, mal Stichwort.")
    return errors


def generate_episode_concept(episode_number: int, canon: dict, arc: dict, minutes: float,
                             section_count: int, words_min: int, words_max: int, model: str):
    """01c: EIN Claude-Call für GENAU eine Episode — sieht canon.json + arc.json (also
    auch die Wendepunkt-Zuteilung ALLER Episoden für Kontinuität), aber nie die
    parallel generierten Sections anderer Episoden. Das ist der Kern des Umbaus:
    keine Batch-Grenze mehr, an der die Section-Tiefe kippen könnte."""
    template_text = load_stage_prompt(canon.get("template"), "EPISODE_PROMPT.md")
    prompt = build_episode_concept_prompt(template_text, canon, arc, episode_number, minutes,
                                          section_count, words_min, words_max)
    timeout = compute_timeout(1)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            print(f"    🔁  Episode {episode_number} — Versuch {attempt}/{MAX_ATTEMPTS} "
                  f"(mit Fehler-Feedback) ...")
        raw = call_claude(prompt + feedback, model, timeout=timeout,
                          label=f"Episode {episode_number} generieren "
                                f"(Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            feedback = ""
            continue

        data = parse_json_response(raw)
        if data is None:
            print_raw_snippet(raw, indent="      ")
            errors = ["Die Antwort war kein valides JSON-Objekt."]
        else:
            errors = validate_episode_concept(data, canon, episode_number, words_min, words_max)

        if not errors:
            return data

        print(f"    ⚠️  Episode {episode_number} — Versuch {attempt} abgelehnt "
              f"({len(errors)} Problem(e)):")
        for e in errors:
            print(f"      - {e}")
        if response_looks_truncated(raw):
            print(f"    ✂️  Episode {episode_number}: Antwort offenbar abgeschnitten — "
                  f"weitere Versuche können das nicht beheben, breche früh ab.")
            break
        feedback = (
            "\n\nIMPORTANT — your previous attempt was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again "
              "(full object, not a diff), following every rule above."
        )

    return None


def generate_case_based_series(topic: str, template: str, episode_count: int, minutes: float,
                               location_count: int, model: str, checkpoint_key: str):
    """Ersetzt für CASE_BASED_TEMPLATES (crime_drama, soap_opera) den alten Ein-Schuss-/
    Batch-Pfad: Kanon (01a, ein Call) -> Staffelbogen (01b, ein Call, sieht den Kanon) ->
    Episoden-Konzepte (01c, ein Call PRO Episode, parallel, sieht Kanon+Bogen aber nie
    die Sections anderer Episoden). Jede Teilstage ist einzeln über _cached_unit()
    checkpointed. Gibt (data, warnings, arc) zurück — arc zusätzlich zu generate_with_retry()s
    (data, warnings), weil main() es für den Reconciliation-Pass (check_turning_point_coverage)
    braucht — oder (None, [], None) bei endgültigem Scheitern irgendeiner Teilstage."""
    print("  Teilstage 1/3: Kanon (Welt, Cast, Orte, Fakten-Threads) ...")
    canon = _cached_unit(
        checkpoint_key, "canon",
        lambda: generate_canon(topic, template, episode_count, minutes, location_count, model),
        validate_fn=lambda c: validate_canon(c, template),
    )
    if canon is None:
        print("  ❌  Kanon-Generierung gescheitert.")
        return None, [], None
    canon.setdefault("template", template)

    print("  Teilstage 2/3: Staffelbogen (Wendepunkt-Zuteilung, Episoden-Themen) ...")
    arc = _cached_unit(
        checkpoint_key, "arc",
        lambda: generate_arc(canon, episode_count, model),
        validate_fn=lambda a: validate_arc(a, canon, episode_count),
    )
    if arc is None:
        print("  ❌  Staffelbogen-Generierung gescheitert.")
        return None, [], None

    section_count = estimate_section_count_from_format(canon.get("format", {}), minutes)
    max_workers = max(1, min(episode_count, EPISODE_CONCEPT_PARALLEL_CAP))
    print(f"  Teilstage 3/3: {episode_count} Episoden-Konzept(e), {max_workers} parallel "
          f"— jedes ein eigener Call, sieht Kanon+Bogen, nie die Sections anderer "
          f"Episoden ...")

    def _episode_unit(n):
        return _cached_unit(
            checkpoint_key, f"episode_{n}",
            lambda: generate_episode_concept(n, canon, arc, minutes, section_count,
                                             SECTION_WORDS_MIN, SECTION_WORDS_MAX, model),
            validate_fn=lambda c, n=n: validate_episode_concept(
                c, canon, n, SECTION_WORDS_MIN, SECTION_WORDS_MAX),
        )

    concepts = {}
    failed = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_episode_unit, n): n for n in range(1, episode_count + 1)}
        for future in concurrent.futures.as_completed(futures):
            n = futures[future]
            concept = future.result()
            if concept is None:
                print(f"  ❌  Episode {n} nach {MAX_ATTEMPTS} Versuchen gescheitert.")
                failed.append(n)
            else:
                print(f"    Episode {n}/{episode_count} ✓")
                concepts[n] = concept

    if failed:
        print(f"  💾  {len(concepts)}/{episode_count} Episoden-Konzept(e) bleiben unter "
              f"{_checkpoint_dir(checkpoint_key)} zwischengespeichert — derselbe Aufruf "
              f"generiert bei einem erneuten Versuch nur noch die fehlgeschlagenen "
              f"Episoden {sorted(failed)} neu.")
        return None, [], None

    # Zusammenbau: Kanon-Top-Level-Felder + threads + Episoden (arc.figure/theme +
    # 01c-Sections/case). Fakten-Injektion (solution/objective_facts pro Thread-Label
    # in jedes episode['case'][i]) ist hier der Ersatz für das alte apply_case_canon()
    # — derselbe Mechanismus (Code statt LLM-Hoffnung), nur ohne Drift-Risiko: die
    # Fakten stehen in canon['threads'] bereits EINMAL final fest, 01c liefert pro
    # Episode nur noch label+character_knowledge.
    threads_by_label = {t.get("label"): t for t in (canon.get("threads") or [])
                        if isinstance(t, dict)}
    arc_episodes_by_num = {e.get("episode"): e for e in (arc.get("episodes") or [])
                           if isinstance(e, dict)}
    data = dict(canon)
    episodes = []
    for n in range(1, episode_count + 1):
        arc_ep = arc_episodes_by_num.get(n, {})
        concept = concepts[n]
        case_blocks = []
        for block in (concept.get("case") or []):
            if not isinstance(block, dict):
                continue
            canon_thread = threads_by_label.get(block.get("label"), {})
            merged = dict(block)
            merged.setdefault("solution", canon_thread.get("solution"))
            merged.setdefault("objective_facts", canon_thread.get("objective_facts"))
            case_blocks.append(merged)
        episodes.append({
            "figure": arc_ep.get("figure", ""),
            "theme": arc_ep.get("theme", ""),
            "intro_note": concept.get("intro_note", ""),
            "outro_note": concept.get("outro_note", ""),
            "sections": concept.get("sections", []),
            "case": case_blocks,
        })
    data["episodes"] = episodes

    errors, warnings = config.validate_data(data)
    if errors:
        # Sollte nach den Einzel-Episoden-Validierungen eigentlich nicht mehr auftreten —
        # reiner Sicherheitsnetz-Check auf dem zusammengesetzten Gesamtdokument, analog
        # zu repair_series(), das seine Korrektur auch immer neu validiert statt zu
        # vertrauen.
        print(f"  ❌  Zusammengesetzte Serie ungültig ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"    - {e}")
        # Checkpoint bleibt erhalten — die Einzel-Konzepte waren jeweils für sich valide,
        # dieser Fehler betrifft nur das Gesamtdokument.
        return None, [], None

    # ACHTUNG: hier bewusst NICHT _clear_checkpoint() aufrufen — main() lässt nach diesem
    # Return noch Inhalts-Review UND ggf. --fix-Reparatur laufen (eigene, oft lange
    # Claude-Aufrufe), BEVOR die Serie überhaupt auf Platte geschrieben wird. main()
    # räumt den Checkpoint selbst auf, erst NACH dem erfolgreichen Schreiben der Datei.
    return data, warnings, arc


REVIEW_PROMPT = """You are a ruthless script editor doing a pre-production review.
Below is the complete episodes.json for a planned podcast series (template: {template}).
The structure is already machine-validated — do NOT comment on JSON syntax or schema.

Check ONLY for these content problems:
1. SPOILER LEAK: for mystery/serial formats, does any early episode's theme/intro_note/
   outro_note give away the solution or a secret that must only be revealed later?
2. CONTRADICTIONS: do objective_facts, character_knowledge entries, or episode themes
   contradict each other anywhere across the season?
3. ACCENT CASTING: of the built-in voices only Ryan and Aiden are accent-free native
   English speakers — every other voice (including ALL female voices) has an audible
   Chinese accent in every line. Flag any character whose description/biography does not
   plausibly explain that accent (and flag a NARRATOR that is not Ryan or Aiden).
   Skip this check if there is no "voices" object.
4. OVERLAP: do two episodes cover nearly the same figure/case/beat, or does a
   figure duplicate one from the already-used list mentioned in the config?
5. SECTION LENGTH BUDGET MISMATCH: check every episode's "section_words" entries
   against that episode's "format"/global words_per_part_min (or the equivalent
   min if this template has no such per-section field — skip this check entirely
   if there is no "section_words" field anywhere). For each NON-NULL override,
   compare its "min" to the section's own title/description: if the section is
   described as a short, sharp, or brief beat (a quick confrontation, a one-line
   call, a closing image) but its "min" is not at least ~80-100 words below the
   episode-wide minimum, flag it by section index and episode — a token 10-20%
   trim is not a real pace change and reliably causes the writer to undershoot
   it. Conversely flag a "min" that is UNREALISTICALLY low (under ~80 words) for
   a section whose description implies real back-and-forth between characters.

Respond ONLY with valid JSON, no markdown fences, exactly:
{{"issues": [{{"episodes": [<1-indexed episode number(s) this problem concerns — BOTH episodes
for a cross-episode contradiction/overlap, just the one for a spoiler leak or a section-budget
issue; leave this EMPTY only for problem 3 (ACCENT CASTING), which is about the top-level
"voices" cast, not any specific episode>], "problem": "one short, specific sentence describing
the problem"}}] — empty list if none}}

Do not invent nitpicks: only report problems a listener or producer would actually
notice. An empty list is a perfectly good answer.

episodes.json:
"""


def review_series(data: dict, model: str, effort: Optional[str] = None) -> Optional[list]:
    """Inhalts-QA nach bestandener Struktur-Validierung: ein zweiter
    Claude-Aufruf prüft Spoiler-Leaks, Widersprüche, Akzent-Casting und
    Episoden-Überschneidungen.

    Rückgabe: Liste von {{"episodes": [int, ...], "problem": str}} (auch leer =
    tatsächlich sauber) bei einem erfolgreichen Review-Lauf, oder None, wenn der
    Review-Aufruf selbst fehlgeschlagen ist (Timeout/API-Fehler/unauswertbare
    Antwort) — dieselbe None-vs-[]-Disziplin wie bei review_episode_script/
    review_episode_beats. "episodes" lokalisiert den Befund für die gezielte
    Episoden-Reparatur (siehe repair_series()) — eine leere Liste heißt
    "betrifft nicht einzelne Episoden" (z.B. Akzent-Casting über 'voices') und
    erzwingt dort den vollen Dokument-Umbau als Fallback. Wichtig für den
    Bestätigungs-Review nach --fix (main()), der einen echten Fehlschlag von
    einem tatsächlich sauberen Ergebnis unterscheiden muss, statt beides als
    '✅ keine Auffälligkeiten' zu zeigen. Der ERSTE Review-Aufruf (vor --fix)
    behandelt None bewusst wie [] (blockiert nie, die Serie ist ja strukturell
    gültig) — siehe `review_series(...) or []` in main()."""
    prompt = REVIEW_PROMPT.format(template=data.get("template", "narration")) \
        + json.dumps(data, ensure_ascii=False, indent=2)
    timeout = compute_timeout(len(data.get("episodes", [])))
    argv = ["claude", "-p", prompt, "--output-format", "text", "--model", model, "--tools", ""]
    if effort:
        argv += ["--effort", effort]
    try:
        result = run_claude_process(argv, timeout, "Inhalts-Review")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("⚠️  Inhalts-Review übersprungen (Claude-Aufruf fehlgeschlagen).")
        return None
    if result.returncode != 0:
        print("⚠️  Inhalts-Review übersprungen (Claude-Aufruf fehlgeschlagen).")
        return None
    parsed = parse_json_response(result.stdout.strip())
    if not isinstance(parsed, dict) or not isinstance(parsed.get("issues"), list):
        print("⚠️  Inhalts-Review übersprungen (Antwort nicht auswertbar).")
        return None
    issues = []
    for i in parsed["issues"]:
        if isinstance(i, dict) and i.get("problem"):
            eps = i.get("episodes")
            eps = [e for e in eps if isinstance(e, int)] if isinstance(eps, list) else []
            issues.append({"episodes": eps, "problem": str(i["problem"])})
        else:
            # Alt-Format/rohes String-Issue (z.B. abweichende Modellantwort) — ohne
            # Episoden-Bezug behandelt, das erzwingt in repair_series() sicher den
            # vollen Dokument-Umbau statt eine falsche Lokalisierung zu raten.
            issues.append({"episodes": [], "problem": str(i)})
    return issues


RECONCILIATION_PROMPT = """You are auditing a serialized audio-drama season for ONE specific \
structural defect: a plot turning point that got independently narrated in more than one \
episode, or in none at all — because each episode was written in a separate call that never saw \
the others' scenes.

SEASON'S PLANNED TURNING POINTS (each was assigned to exactly ONE episode when the season was \
planned; a different episode narrating the same event is a bug):
{turning_points_block}

WHAT EACH EPISODE ACTUALLY CONTAINS (per section: title, the narrated scene, which thread it \
belongs to):
{episodes_block}

For EACH planned turning point listed above, decide which episode(s) actually narrate or resolve \
that specific event in their sections. Respond ONLY with valid JSON, no markdown fences, exactly:
{{"findings": [{{"event": "<the event text, copied EXACTLY from the list above>", "verdict": \
"ok"|"duplicate"|"missing", "episodes": [<episode number(s) that actually narrate this event — \
for "duplicate" list ALL of them, for "missing" an empty list, for "ok" the single correct \
episode>], "explanation": "one short sentence"}}]}}

Output exactly one entry per turning point listed above, in the same order. "duplicate" = \
narrated in more than one episode (even if worded differently — the same underlying event/reveal \
counts as the same). "missing" = narrated in zero episodes. "ok" = narrated in exactly its \
assigned episode and nowhere else. Do not flag a turning point as duplicate just because an \
earlier episode FORESHADOWS or references it in passing without actually resolving/revealing it \
— only an actual narration of the event counts.
"""


def _build_turning_points_block(turning_points: list) -> str:
    return "\n".join(
        f"- [{tp.get('thread')}] assigned to episode {tp.get('episode')}: {tp.get('event')}"
        for tp in turning_points if isinstance(tp, dict)
    )


def _build_episodes_sections_block(episodes: list) -> str:
    blocks = []
    for i, ep in enumerate(episodes, start=1):
        lines = [f"=== EPISODE {i}: \"{ep.get('figure', '')}\" ==="]
        for sec in ep.get("sections", []):
            if isinstance(sec, dict):
                lines.append(f"  - [{sec.get('thread', '?')}] {sec.get('title', '')}: "
                             f"{sec.get('what', '')}")
            else:
                lines.append(f"  - {sec}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def check_turning_point_coverage(data: dict, arc: dict, model: str, effort: Optional[str] = None,
                                 votes: int = 5, threshold: int = 4) -> list:
    """Reconciliation-Pass NACH allen parallelen 01c-Aufrufen (Phase 4,
    docs/konzept-stage-umbau.md): ein LLM-Judge liest arc.json's
    turning_points gegen die fertigen Sections und meldet jeden Wendepunkt,
    der in mehr als einer Episode erzählt wurde (Doppel-Klimax) oder in
    keiner (verloren gegangen). Läuft EINMAL pro Serie, nicht pro Episode
    — ein Fan-out hier ist billig gegen den Nutzen, einen echten
    Doppel-Klimax zu fangen.

    Self-Consistency-Voting (FlawedFictions-Muster gegen dokumentiertes
    LLM-Judge-Rauschen): derselbe Call läuft `votes`-mal; ein Fund zählt
    nur, wenn dasselbe (Wendepunkt, Verdikt, Episoden) in mindestens
    `threshold` von `votes` Läufen übereinstimmend auftaucht — einzelne
    abweichende Läufe werden verworfen statt sofort einen echten Fund zu
    riskieren.

    Rückgabeform identisch zu review_series()/dem gelöschten
    check_case_drift(): [{"episodes": [int], "problem": str}] — fügt sich
    dadurch unverändert in repair_series() ein."""
    turning_points = arc.get("turning_points") if isinstance(arc, dict) else None
    if not turning_points:
        return []
    episodes = data.get("episodes", [])
    prompt = RECONCILIATION_PROMPT.format(
        turning_points_block=_build_turning_points_block(turning_points),
        episodes_block=_build_episodes_sections_block(episodes),
    )
    timeout = compute_timeout(len(episodes))

    all_votes = []  # list of {event_key: (verdict, sorted_episode_tuple)}
    for i in range(votes):
        raw = call_claude(prompt, model, timeout=timeout,
                          label=f"Wendepunkt-Abdeckung prüfen ({i + 1}/{votes})")
        if not raw:
            continue
        parsed = parse_json_response(raw)
        findings = parsed.get("findings") if isinstance(parsed, dict) else None
        if not isinstance(findings, list):
            continue
        vote_map = {}
        for f in findings:
            if not isinstance(f, dict):
                continue
            event_key = _normalize_ws(f.get("event", "")).lower()
            verdict = f.get("verdict")
            eps = tuple(sorted(e for e in (f.get("episodes") or []) if isinstance(e, int)))
            if event_key and verdict in ("ok", "duplicate", "missing"):
                vote_map[event_key] = (verdict, eps)
        if vote_map:
            all_votes.append(vote_map)

    if not all_votes:
        print("  ⚠️  Wendepunkt-Abdeckungs-Check: alle Voting-Läufe fehlgeschlagen — übersprungen.")
        return []

    issues = []
    for tp in turning_points:
        event_key = _normalize_ws(tp.get("event", "")).lower()
        tally = {}
        for vote_map in all_votes:
            if event_key in vote_map:
                verdict, eps = vote_map[event_key]
                if verdict != "ok":
                    key = (verdict, eps)
                    tally[key] = tally.get(key, 0) + 1
        if not tally:
            continue
        (verdict, eps), count = max(tally.items(), key=lambda kv: kv[1])
        if count < threshold:
            continue
        assigned_ep = tp.get("episode")
        if verdict == "duplicate":
            extra_eps = [e for e in eps if e != assigned_ep] or list(eps)
            issues.append({"episodes": extra_eps, "problem": (
                f"Wendepunkt \"{tp.get('event')}\" (Thread '{tp.get('thread')}', laut Bogen für "
                f"Episode {assigned_ep} vorgesehen) wird zusätzlich in Episode(n) {extra_eps} "
                f"erzählt — Doppel-Klimax ({count}/{len(all_votes)} Voting-Läufe einig)."
            )})
        elif verdict == "missing" and assigned_ep is not None:
            issues.append({"episodes": [assigned_ep], "problem": (
                f"Wendepunkt \"{tp.get('event')}\" (Thread '{tp.get('thread')}') wird in der "
                f"dafür vorgesehenen Episode {assigned_ep} nicht erzählt "
                f"({count}/{len(all_votes)} Voting-Läufe einig)."
            )})
    return issues


def build_season_index(episodes: list) -> str:
    """Kompakter Serien-Überblick (Figur+Thema+Thread-Labels pro Episode) für die
    gezielte Episoden-Reparatur — gibt dem Modell genug Kontext, um eine
    Korrektur konsistent mit dem Rest der Staffel zu halten, OHNE die vollen
    Objekte der unveränderten Episoden mitschicken zu müssen."""
    lines = []
    for i, ep in enumerate(episodes, start=1):
        labels = ", ".join(t.get("label", "?") for t in _episode_threads(ep)) or "(kein case)"
        lines.append(f"Episode {i}: \"{ep.get('figure', '')}\" — {ep.get('theme', '')} "
                     f"[Threads: {labels}]")
    return "\n".join(lines)


SERIES_REPAIR_EPISODES_PROMPT = """You are revising SPECIFIC episodes of an already-generated
podcast series concept to fix content problems a reviewer flagged. Change ONLY what is needed to
fix each flagged problem below — every other field of these episodes (unrelated sections, unrelated
case threads/character_knowledge, section_words, etc.) must stay exactly as it is. Do NOT touch
episodes not listed below — they are not included in your input and must not appear in your output.

SEASON CONTEXT (every episode's figure/theme/thread labels, for continuity — episodes not listed
below are NOT part of this repair, shown only so your fix stays consistent with them):
{season_index}

FLAGGED PROBLEMS (each names the episode number(s) it concerns):
{issues_block}

CURRENT full objects of ONLY the episodes that need fixing (keyed by 1-indexed episode number):
{episodes_json}

Output ONLY this JSON shape:
{{"episodes": {{"<episode number as string>": <the complete corrected episode object>, ...}}}}
— exactly one entry per episode number shown above, same per-episode schema each already has, only
the flagged problems fixed. No other top-level fields, no commentary before or after.
"""

SERIES_REPAIR_GLOBALS_PROMPT = """You are revising the SERIES-LEVEL fields of an already-generated
podcast series concept to fix problems a reviewer flagged. These problems concern the series as a
whole (e.g. accent casting in "voices"), not any single episode — the episodes themselves are NOT
part of your input and must not appear in your output.

SEASON CONTEXT (every episode's figure/theme/thread labels, so your fix stays consistent with what
the episodes actually do — you cannot change them):
{season_index}

FLAGGED PROBLEMS (all series-level):
{issues_block}

CURRENT series-level fields (the complete episodes.json WITHOUT its "episodes" list):
{globals_json}

HARD RULE — the role KEYS in "voices" must stay EXACTLY as they are (same names, same set, same
spelling): every episode's "case"/"character_knowledge" references them, and those episodes are not
being touched. Fix a casting problem by changing the VOICE assigned to a role (and, if needed, that
role's description), never by renaming, adding, or removing a role.

Output ONLY this JSON shape:
{{<all series-level fields exactly as listed above, corrected>}}
— the same set of top-level keys you were given, no more, no fewer, NO "episodes" key, only the
flagged problems fixed. No markdown fences, no commentary before or after.
"""

SERIES_REPAIR_PROMPT = """You are revising an already-generated podcast series concept (a complete
episodes.json) to fix specific content problems a reviewer flagged. Change ONLY what is needed to
fix each flagged problem below — every other field (unrelated episodes, titles, voices, unrelated
case/character_knowledge entries, section_words, etc.) must stay exactly as it is.

FLAGGED PROBLEMS:
{issues_block}

CURRENT episodes.json:
{current_json}

Output ONLY the corrected, complete episodes.json object — valid JSON, no markdown fences, no
commentary before or after it. Same schema, same episode count, only the flagged problems fixed.
"""


def _reconcile_case_canon_from_siblings(data: dict, changed_episode_indices: set) -> int:
    """Nach einer GEZIELTEN Episoden-Reparatur: erzwingt, dass solution/objective_facts der
    reparierten Episoden zu den UNVERÄNDERTEN Episoden passen. apply_case_canon() greift hier
    nicht (case_canon existiert zu diesem Zeitpunkt längst nicht mehr — main() hat es schon vor
    dem Speichern entfernt), deshalb wird die Referenz stattdessen aus der ersten unveränderten
    Episode pro Thread-Label abgeleitet. changed_episode_indices ist 0-indexiert."""
    reference = {}
    episodes = data.get("episodes", [])
    for idx, ep in enumerate(episodes):
        if idx in changed_episode_indices:
            continue
        for thread in _episode_threads(ep):
            key = _normalize_ws(thread.get("label", "")).lower()
            if key and key not in reference:
                reference[key] = thread
    changed = 0
    for idx in changed_episode_indices:
        if idx >= len(episodes):
            continue
        for thread in _episode_threads(episodes[idx]):
            key = _normalize_ws(thread.get("label", "")).lower()
            ref = reference.get(key)
            if ref is None:
                continue
            for field in ("solution", "objective_facts"):
                if field in ref and thread.get(field) != ref[field]:
                    thread[field] = ref[field]
                    changed += 1
    return changed


def _repair_series_episodes(data: dict, issues: list, episode_nums: list, model: str) -> Optional[dict]:
    """Repariert NUR die betroffenen Episoden gezielt — das Gegenstück zu repair_part()/
    apply_episode_fixes() beim Skript-Writer, hier auf episodes.json-Ebene. Die Antwort enthält
    nur die paar Episoden, die die Befunde wirklich betreffen (statt aller {episode_count}),
    damit ist sie um ein Vielfaches kleiner als bei _repair_series_full() — genau das Volumen,
    das bei größeren Serien (10 Episoden × mehrere Threads) bisher zuverlässig abriss (siehe
    fabrik/cli/CLAUDE.md, "kommt immer dieser Teil"-Fund vom 17.07.2026).

    Gibt das korrigierte Gesamtdokument zurück, oder None bei endgültigem Fehlschlag — der
    Aufrufer (repair_series()) fällt dann auf den vollen Dokument-Umbau zurück."""
    episodes = data.get("episodes", [])
    season_index = build_season_index(episodes)
    issues_block = "\n".join(
        f"- (Episode(n) {', '.join(str(n) for n in i['episodes'])}): {i['problem']}"
        for i in issues if i.get("episodes")
    )
    subset = {str(n): episodes[n - 1] for n in episode_nums if 1 <= n <= len(episodes)}
    prompt = SERIES_REPAIR_EPISODES_PROMPT.format(
        season_index=season_index, issues_block=issues_block,
        episodes_json=json.dumps(subset, ensure_ascii=False, indent=2),
    )
    timeout = compute_batch_timeout(len(subset))
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        raw = call_claude(prompt + feedback, model, timeout=timeout,
                          label=f"Episoden {sorted(episode_nums)} reparieren "
                                f"(Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            feedback = ""
            continue

        parsed = parse_json_response(raw)
        fixed_map = parsed.get("episodes") if isinstance(parsed, dict) else None
        if not isinstance(fixed_map, dict) or set(fixed_map) != set(subset):
            print_raw_snippet(raw, indent="    ")
            errors = [f"Antwort muss ein 'episodes'-Objekt mit genau den Schlüsseln "
                      f"{sorted(subset)} enthalten."]
        else:
            candidate = json.loads(json.dumps(data))  # billige tiefe Kopie
            malformed = [n for n, ep in fixed_map.items() if not isinstance(ep, dict)]
            if malformed:
                errors = [f"episodes.{n} war kein Objekt." for n in malformed]
            else:
                changed_idx = set()
                for n_str, ep_obj in fixed_map.items():
                    idx = int(n_str) - 1
                    candidate["episodes"][idx] = ep_obj
                    changed_idx.add(idx)
                _reconcile_case_canon_from_siblings(candidate, changed_idx)
                errors, _warnings = config.validate_data(candidate)

        if not errors:
            return candidate

        print(f"    ⚠️  Episoden-Reparatur — Versuch {attempt} strukturell ungültig "
              f"({len(errors)} Problem(e)).")
        if response_looks_truncated(raw):
            # Längen- statt Inhaltsproblem, siehe generate_with_retry(). Anders als ein Batch
            # bei der Erstgenerierung kann dieser Pfad nicht halbieren (welche Episoden zu
            # reparieren sind, geben die Befunde vor) — also früh aufgeben statt blind zu
            # wiederholen; repair_series() versucht danach den vollen Umbau.
            print("    ✂️  Antwort offenbar abgeschnitten — weitere Versuche dieser Größe "
                  "können das nicht beheben, breche früh ab.")
            break
        feedback = (
            "\n\nIMPORTANT — your previous correction was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again (the "
              "{\"episodes\": {...}} object for exactly these episode numbers), still only "
              "touching what's needed for the originally flagged problems."
        )

    return None


def _repair_series_globals(data: dict, issues: list, model: str) -> Optional[dict]:
    """Repariert Befunde OHNE Episodenbezug (Akzent-Casting über 'voices' & Co.) — schickt nur
    die Top-Level-Felder OHNE 'episodes' zur Korrektur. Diese sind auch bei einer 10-Episoden-
    Serie nur ein paar KB, während der volle Dokument-Umbau dafür die komplette episodes.json
    (>100 KB) neu ausgeben müsste — genau das Volumen, an dem _repair_series_full() zuverlässig
    abreißt. Ein Akzent-Casting-Fund betrifft ein paar Zeilen in 'voices'; ihn über einen
    Komplettumbau zu beheben, war die eigentliche Ursache der 10-Episoden-Hänger (17.07.2026).

    Der Vollständigkeit halber re-validiert das Ergebnis wie jeder andere Reparatur-Pfad gegen
    config.validate_data() — das fängt insbesondere umbenannte 'voices'-Rollen ab (die Episoden
    referenzieren sie in character_knowledge und bleiben hier unangetastet).

    Gibt das korrigierte Gesamtdokument zurück, oder None bei endgültigem Fehlschlag."""
    globals_only = {k: v for k, v in data.items() if k != "episodes"}
    prompt = SERIES_REPAIR_GLOBALS_PROMPT.format(
        season_index=build_season_index(data.get("episodes", [])),
        issues_block="\n".join(f"- {i['problem']}" for i in issues),
        globals_json=json.dumps(globals_only, ensure_ascii=False, indent=2),
    )
    timeout = compute_batch_timeout(1)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        raw = call_claude(prompt + feedback, model, timeout=timeout,
                          label=f"Serien-Felder reparieren (Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            feedback = ""
            continue

        fixed = parse_json_response(raw)
        if not isinstance(fixed, dict) or set(fixed) != set(globals_only):
            print_raw_snippet(raw, indent="    ")
            errors = [f"Antwort muss genau die Top-Level-Felder {sorted(globals_only)} "
                      f"enthalten (ohne 'episodes')."]
        else:
            candidate = json.loads(json.dumps(data))  # billige tiefe Kopie
            candidate.update(fixed)
            errors, _warnings = config.validate_data(candidate)

        if not errors:
            return candidate

        print(f"    ⚠️  Serien-Feld-Reparatur — Versuch {attempt} strukturell ungültig "
              f"({len(errors)} Problem(e)).")
        feedback = (
            "\n\nIMPORTANT — your previous correction was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again (the series-level "
              "fields only, no \"episodes\" key), still only touching what's needed for the "
              "originally flagged problems."
        )

    return None


def _repair_series_full(data: dict, issues: list, model: str, episode_count: int) -> Optional[dict]:
    """Voller Dokument-Umbau — der ursprüngliche Reparatur-Weg, jetzt nur noch Fallback für
    Befunde, die sich nicht auf einzelne Episoden lokalisieren lassen (z.B. ACCENT CASTING über
    'voices', oder wenn die gezielte Episoden-Reparatur selbst nach allen Versuchen scheitert).
    Bei großen Serien deutlich abriss-anfälliger als _repair_series_episodes() — siehe dessen
    Docstring —, deshalb bewusst der Ausweichpfad, nicht mehr der Regelfall.

    Läuft wie generate_with_retry() mit Fehler-Feedback bei ungültiger Struktur, hier aber nur
    für die Reparatur selbst (MAX_ATTEMPTS Versuche). Gibt None zurück, wenn keine strukturell
    gültige Korrektur zustande kam."""
    issues_block = "\n".join(f"- {i['problem']}" for i in issues)
    base_prompt = SERIES_REPAIR_PROMPT.format(
        issues_block=issues_block,
        current_json=json.dumps(data, ensure_ascii=False, indent=2),
    )
    timeout = compute_timeout(episode_count)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        raw = call_claude(base_prompt + feedback, model, timeout=timeout,
                          label=f"Serie reparieren, volles Dokument "
                                f"(Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            # Timeout/API-Fehler — nichts Inhaltliches zu korrigieren, ohne
            # (irreführendes) Feedback erneut versuchen, wie in generate_with_retry.
            feedback = ""
            continue

        fixed = parse_json_response(raw)
        if fixed is None:
            errors = ["Die Antwort war kein valides JSON-Objekt."]
        else:
            errors, _warnings = config.validate_data(fixed)
            actual = len(fixed.get("episodes", [])) if isinstance(fixed.get("episodes"), list) else 0
            if actual != episode_count:
                errors.append(f"{actual} Episode(n) in der Korrektur, erwartet waren {episode_count}.")

        if not errors:
            return fixed

        print(f"  ⚠️  Reparatur-Versuch {attempt} strukturell ungültig ({len(errors)} Problem(e)).")
        if response_looks_truncated(raw):
            # Dieselbe Disziplin wie in generate_with_retry()/generate_batch_with_retry(),
            # die hier bisher fehlte: der volle Umbau muss die KOMPLETTE episodes.json neu
            # ausgeben (bei 10 Episoden >100 KB) und reißt dabei zuverlässig ab. Ein Abriss
            # ist ein Längenproblem — derselbe Versuch scheitert identisch, kostet aber je
            # bis zu compute_timeout(episode_count) Sekunden. Genau das ließ einen
            # 10-Episoden-Lauf nach drei Minuten Generierung bis zu 90 Minuten lang wie
            # hängend aussehen (Nutzer-Symptom 17.07.2026).
            print("  ✂️  Antwort ist offenbar ABGESCHNITTEN — der volle Dokument-Umbau ist für "
                  "diese Serie zu groß, weitere Versuche können das nicht beheben. Abbruch der "
                  "Reparatur (das Original bleibt unangetastet, Befunde werden gedruckt).")
            break
        feedback = (
            "\n\nIMPORTANT — your previous correction was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again (full object, not "
              "a diff), still only touching what's needed for the originally flagged problems."
        )

    return None


def repair_series(data: dict, issues: list, model: str, episode_count: int) -> Optional[dict]:
    """Dispatcher: repariert die von check_case_drift()/review_series() gemeldeten Befunde
    (Format: [{"episodes": [int, ...], "problem": str}]).

    TEILT die Befunde nach ihrem Geltungsbereich auf und repariert jede Gruppe mit dem
    kleinstmöglichen Aufruf: Episoden-Befunde gezielt über _repair_series_episodes(),
    serienweite Befunde (Akzent-Casting über 'voices' & Co.) über _repair_series_globals().
    Beide Schritte bauen aufeinander auf — der zweite sieht das Ergebnis des ersten.

    Bis 17.07.2026 entschied dieser Dispatcher am SCHWÄCHSTEN Befund: ein einziger Fund ohne
    Episodenbezug kippte ALLE Befunde in den vollen Dokument-Umbau. Da Akzent-Casting
    konstruktionsbedingt nie eine Episodennummer trägt (es hängt am Top-Level-'voices'),
    landete praktisch jeder --fix-Lauf im Komplettumbau — der bei 10 Episoden (>100 KB
    Ausgabe) zuverlässig abriss und die Erstgenerierung von drei Minuten mit bis zu 90
    Minuten scheinbarem Stillstand quittierte. Genau das war das "bei 10 Episoden gibt es
    Probleme"-Symptom.

    _repair_series_full() bleibt als Auffangnetz für alles, was keine der beiden gezielten
    Reparaturen hinbekommen hat. Gibt das korrigierte Dokument zurück — bei nur TEILWEISEM
    Erfolg den bereits verbesserten Stand (besser als das Original, ehrlicher als None), oder
    None, wenn kein einziger Schritt etwas ausrichten konnte."""
    def _nums(issue):
        return [n for n in issue.get("episodes", []) or []
                if isinstance(n, int) and 1 <= n <= episode_count]

    # Ein Befund mit unbrauchbaren/ausserhalb liegenden Nummern zählt bewusst als
    # serienweit — lieber der breitere Weg als eine falsch geratene Lokalisierung.
    episode_issues = [i for i in issues if _nums(i)]
    global_issues = [i for i in issues if not _nums(i)]
    episode_nums = sorted({n for i in episode_issues for n in _nums(i)})

    working = data
    unresolved = []

    if episode_nums:
        print(f"  🎯  Gezielte Reparatur — {len(episode_issues)} Befund(e) betreffen nur "
              f"Episode(n) {episode_nums} (von {episode_count} insgesamt) ...")
        fixed = _repair_series_episodes(working, episode_issues, episode_nums, model)
        if fixed is not None:
            working = fixed
        else:
            print("  ⚠️  Gezielte Episoden-Reparatur gescheitert — Befunde gehen an den "
                  "vollen Dokument-Umbau.")
            unresolved.extend(episode_issues)

    if global_issues:
        print(f"  🎚️  Serienweite Reparatur — {len(global_issues)} Befund(e) ohne Episodenbezug "
              f"(z.B. Akzent-Casting): nur die Top-Level-Felder gehen an Claude, nicht die "
              f"{episode_count} Episoden ...")
        fixed = _repair_series_globals(working, global_issues, model)
        if fixed is not None:
            working = fixed
        else:
            print("  ⚠️  Serienweite Reparatur gescheitert — Befunde gehen an den vollen "
                  "Dokument-Umbau.")
            unresolved.extend(global_issues)

    if not unresolved:
        return working

    print(f"  🧱  Auffangnetz: {len(unresolved)} unerledigte(r) Befund(e) über den vollen "
          f"Dokument-Umbau (bei großen Serien abriss-anfällig) ...")
    full = _repair_series_full(working, unresolved, model, episode_count)
    if full is not None:
        return full
    # Kein Erfolg im Umbau — aber vielleicht hat ein früherer Schritt schon etwas
    # verbessert; diesen Teilerfolg zu verwerfen wäre schlechter als ihn zu behalten.
    return working if working is not data else None


def main():
    parser = argparse.ArgumentParser(description="Neue Podcast-Serie via Claude CLI erzeugen.")
    parser.add_argument("topic", help="Thema/Konzept der neuen Serie")
    parser.add_argument("--episodes", type=int, default=DEFAULT_EPISODE_COUNT,
                        help=f"Anzahl Episoden (Standard: {DEFAULT_EPISODE_COUNT})")
    parser.add_argument("--template", default="narration",
                        help="Template-Ordner unter templates/ (Standard: narration)")
    parser.add_argument("--minutes", type=float, default=DEFAULT_MINUTES,
                        help=f"Ziel-Länge pro Episode in Minuten (Standard: {DEFAULT_MINUTES:g}) — "
                             f"steuert, wie viele Sections das Template pro Episode anlegt")
    parser.add_argument("--locations", type=int, default=DEFAULT_LOCATION_COUNT,
                        help=f"Anzahl wiederverwendbarer Szenen-Orte für die ganze Serie "
                             f"(Standard: {DEFAULT_LOCATION_COUNT}, nur wirksam bei Templates, "
                             f"die 'locations' unterstützen, z.B. soap_opera)")
    parser.add_argument("--no-review", action="store_true",
                        help="Inhalts-Review (zweiter Claude-Aufruf: Spoiler-Leaks, "
                             "Widersprüche, Akzent-Casting, Überschneidungen) überspringen")
    parser.add_argument("--fix", action="store_true",
                        help="Vom Inhalts-Review gemeldete Probleme automatisch reparieren "
                             "(ein weiterer Claude-Aufruf gibt die korrigierte episodes.json "
                             "aus, danach erneuter Review zur Bestätigung) — wirkungslos "
                             "zusammen mit --no-review, da dafür ein durchgeführter Review "
                             "nötig ist")
    args = parser.parse_args()

    case_based = args.template in CASE_BASED_TEMPLATES
    print(f"🧠  Erzeuge neue Serie ({args.episodes} Episoden, ~{args.minutes:g} Min./Episode, "
          f"{args.locations} Orte, Template '{args.template}') zum Thema: \"{args.topic}\" ...")

    # Einmal berechnet, zweimal gebraucht: für den Checkpoint unten und zum Aufräumen
    # desselben Ordners ganz am Ende von main().
    checkpoint_key = _checkpoint_key(args.topic, args.template, args.episodes, args.minutes,
                                     args.locations, config.DEFAULTS["model"], case_based)

    if case_based:
        # Kanon -> Staffelbogen -> Episoden (einzeln, parallel) — siehe
        # docs/konzept-stage-umbau.md. Ersetzt den früheren Ein-Schuss-/Batch-Pfad
        # komplett für crime_drama/soap_opera.
        print(f"🧩  '{args.template}' — Kanon → Staffelbogen → Episoden ...")
        data, warnings, arc = generate_case_based_series(args.topic, args.template, args.episodes,
                                                         args.minutes, args.locations,
                                                         config.DEFAULTS["model"], checkpoint_key)
        if data is None:
            print("❌  Serien-Generierung ist gescheitert — Abbruch.")
            sys.exit(1)
    else:
        arc = None  # kein Staffelbogen außerhalb von CASE_BASED_TEMPLATES — kein Reconciliation-Pass
        creator_prompt = load_creator_prompt(args.template)
        prompt = build_prompt(creator_prompt, args.topic, args.episodes, args.minutes,
                              args.locations)
        data, warnings = generate_with_retry(prompt, config.DEFAULTS["model"], args.episodes)
        if data is None:
            print("❌  Serien-Generierung ist gescheitert — Abbruch.")
            sys.exit(1)

    # Template-Zuordnung sicherstellen — der Renderer/Writer wählt darüber
    # PROMPT_TEMPLATE.md und (bei drama) das Skriptformat.
    data.setdefault("template", args.template)

    for w in warnings:
        print(f"WARNUNG: {w}")

    if not args.no_review:
        print("🔎  Inhalts-Review (Spoiler-Leaks, Widersprüche, Akzent-Casting, Überschneidungen) ...")
        # light_model: reine QA-Prüfung des fertigen JSON, keine kreative
        # Skript-Arbeit — braucht nicht das teure Schreibmodell.
        review_model = data.get("generation", {}).get("light_model", config.DEFAULTS["light_model"])
        review_effort = data.get("generation", {}).get("effort", config.DEFAULTS["effort"])
        # None (Review-Aufruf selbst gescheitert) wie [] behandeln — dieser
        # erste Review blockiert nie, die Serie ist ja strukturell gültig.
        issues = review_series(data, review_model, effort=review_effort) or []

        if issues and args.fix:
            print(f"🔧  {len(issues)} Hinweis(e) — versuche automatische Reparatur ...")
            fixed = repair_series(data, issues, config.DEFAULTS["model"], args.episodes)
            if fixed is not None:
                data = fixed
                data.setdefault("template", args.template)
                print("  Review erneut, um den Fix zu bestätigen ...")
                reviewed_again = review_series(data, review_model, effort=review_effort)
                if reviewed_again is not None:
                    issues = reviewed_again
                else:
                    print("  ⚠️  Bestätigungs-Review fehlgeschlagen — die Reparatur wurde "
                          "übernommen, aber nicht erneut geprüft.")
                    issues = []
            else:
                print("  ⚠️  Automatische Reparatur fehlgeschlagen — episodes.json bleibt beim "
                      "ursprünglichen Versuch, Hinweise unten ggf. von Hand prüfen.")

        if issues:
            print(f"⚠️  Inhalts-Review: {len(issues)} Hinweis(e) — Serie wird trotzdem angelegt, "
                  f"bei Bedarf episodes.json anpassen oder neu generieren:")
            for i in issues:
                label = f"Ep. {', '.join(str(n) for n in i['episodes'])}: " if i.get("episodes") else ""
                print(f"  - {label}{i['problem']}")
        else:
            print("✅  Inhalts-Review: keine Auffälligkeiten.")

    if arc is not None:
        print("🧭  Wendepunkt-Abdeckung prüfen (5x Self-Consistency-Voting gegen "
              "Doppel-Klimax/verlorene Wendepunkte) ...")
        review_model = data.get("generation", {}).get("light_model", config.DEFAULTS["light_model"])
        review_effort = data.get("generation", {}).get("effort", config.DEFAULTS["effort"])
        coverage_issues = check_turning_point_coverage(data, arc, review_model, effort=review_effort)
        if coverage_issues and args.fix:
            print(f"🔧  {len(coverage_issues)} Wendepunkt-Befund(e) — versuche automatische "
                  f"Reparatur ...")
            fixed = repair_series(data, coverage_issues, config.DEFAULTS["model"], args.episodes)
            if fixed is not None:
                data = fixed
                data.setdefault("template", args.template)
                coverage_issues = check_turning_point_coverage(data, arc, review_model,
                                                                effort=review_effort)
            else:
                print("  ⚠️  Wendepunkt-Reparatur fehlgeschlagen — episodes.json bleibt beim "
                      "ursprünglichen Stand, Befunde unten von Hand prüfen.")
        if coverage_issues:
            print(f"⚠️  Wendepunkt-Abdeckung: {len(coverage_issues)} Befund(e):")
            for i in coverage_issues:
                print(f"  - {i['problem']}")
        else:
            print("✅  Wendepunkt-Abdeckung: jeder Wendepunkt genau einmal erzählt.")

    # Ab hier ist der Ordner reserviert (der leere Ordner IST die Reservierung, siehe
    # paths.reserve_unique_series()). Schlägt das Schreiben danach fehl — oder bricht der
    # Nutzer im Cockpit ab (KeyboardInterrupt/SIGTERM, deshalb BaseException) —, bliebe
    # sonst eine Leiche zurück: list_series() blendet sie zwar aus (kein episodes.json),
    # der Slug wäre aber dauerhaft verbrannt und die nächste Serie desselben Titels hieße
    # '..._2'. Aufgeräumt wird ausschließlich die eigene, gerade erst angelegte
    # Reservierung — an fremden Serien fasst dieser Pfad nie etwas an.
    series = paths.reserve_unique_series(data.get("series_title", "serie"))
    slug = series.slug
    try:
        scaffolded = workspace.scaffold_workspace(series, data, args.template)
        with open(series.episodes_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except BaseException:
        shutil.rmtree(series.root, ignore_errors=True)
        print(f"\n❌  Serie konnte nicht geschrieben werden — die Reservierung "
              f"'{slug}' wurde wieder freigegeben. Der Checkpoint bleibt erhalten: "
              f"ein identischer Neustart übernimmt Kanon/Bogen/Episoden von Platte.")
        raise
    paths.write_latest(slug)

    # Jetzt erst den Checkpoint aufräumen (siehe Kommentar bei CHECKPOINT_STAGING_DIR) —
    # die Serie ist ab hier unwiderruflich gespeichert, ein Rerun braucht den
    # Zwischenspeicher nicht mehr. Harmlos, falls der Ein-Schuss-Pfad direkt
    # erfolgreich war (dann existiert der Ordner nie, _clear_checkpoint() räumt
    # einfach nichts auf).
    _clear_checkpoint(checkpoint_key)

    if scaffolded:
        print(f"    Workspace-Struktur angelegt ({len(scaffolded)} Kontext-/Referenz-Dateien, "
              f"Stage-Verträge unter stages/*/CONTEXT.md)")

    # Maschinen-lesbarer Marker für das WebUI: bei mehreren parallel laufenden
    # Cockpits darf der Client NICHT den globalen LATEST zurücklesen (den hätte
    # eine Schwester-Instanz überschrieben) — dieser Slug ist der von GENAU
    # diesem Lauf erzeugte. Bewusst eine eigene, eindeutig geparste Zeile.
    print(f"PF_CREATED_SERIES={slug}")

    figures = ", ".join(ep["figure"] for ep in data["episodes"])
    print(f"\n✅  Neue Serie angelegt: data/series/{slug}/  (\"{data['series_title']}\")")
    print(f"    {len(data['episodes'])} Episode(n): {figures}")
    print(f"    data/series/LATEST zeigt jetzt auf '{slug}' — alle Skripte nutzen sie als Standard.")
    print(f"\nNächster Schritt:")
    print(f"  python3 -m fabrik.cli.generate_episode all")
    print(f"  (generiert alle Skripte, vertont sie, merged zur Anthologie und")
    print(f"   erzeugt die Anthologie-Metadaten — vollautomatisch)")


if __name__ == "__main__":
    main()
