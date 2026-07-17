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

from fabrik.core import config, history, paths, workspace
from fabrik.core.claude_cli import describe_json_error, parse_json_response, run_claude_process

TIMEOUT_SECONDS = 900
MAX_ATTEMPTS = 3
DEFAULT_EPISODE_COUNT = 3
DEFAULT_MINUTES = 35.0
DEFAULT_LOCATION_COUNT = 4
# Obergrenze für Episoden pro Erweiterungs-Call in generate_series_batched() — zugleich
# der Wert bei der Standard-Episodenlänge (siehe compute_batch_size()/TARGET_BATCH_
# EPISODE_MINUTES unten). Bewusst als Obergrenze, nicht nur als Startwert: für KÜRZERE
# Episoden als den Standard gibt es keinen Beleg, dass ein größerer Batch sicher wäre —
# case/character_knowledge-Overhead pro Episode skaliert nicht rein mit der Wortzahl,
# nur mit der Episodenlänge nach UNTEN zu skalieren ist also der vorsichtigere Weg.
BATCH_SIZE_DEFAULT = 3
# Grobe Sprechgeschwindigkeit für Qwen3-TTS-Erzähltempo — nur zur Umrechnung
# Minuten -> Ziel-Wortzahl, keine exakte Vorhersage der gerenderten Audiolänge.
WORDS_PER_MINUTE = 150

# case-basierte Templates (case/character_knowledge pro Rolle UND — bei soap_opera —
# pro Thread) erzeugen pro Section um ein Vielfaches mehr JSON als narration/
# language_course, siehe SERIES_REPAIR_PROMPT-Umgebung. Nur für diese lohnt sich der
# Vorab-Größencheck in main() (episodes * minutes >= BATCH_THRESHOLD_EPISODE_MINUTES).
CASE_BASED_TEMPLATES = {"crime_drama", "soap_opera"}

# Mindest-Durchschnitt an Wörtern pro Section-Eintrag (nur CASE_BASED_TEMPLATES, siehe
# check_section_detail). Kalibriert an echten Produktionsdaten (17.07.2026, 15 Serien):
# gesunde Staffeln liegen bei Ø 13-16 Wörtern in ihrer schwächsten Episode (seven_seats
# 15.0, amity_hollow 13.6, discharged_cured 13.6, the_curator_s_masterwork 16.4); die
# kaputten fallen auf Ø 3-8 (the_glasshouse_vote 3.7, the_understudy 3.8, the_long_fare
# 3.5, negative_space 7.3, the_founding_collection 8.2). Zwischen 8 und 13 liegt nichts —
# es ist keine Skala, sondern ein Kippschalter: entweder das Modell schreibt erzählte
# Szenen ("Corner Diner: Liwei meets Iggy Chen for the first time in person, eager to
# prove the co-op will move fast") oder blanke Titel ("The Ledger Laid Bare"). 10 liegt
# in der leeren Mitte.
SECTION_DETAIL_MIN_AVG_WORDS = 10
# In der Praxis beobachtet: 10 Episoden x 35 Min. (=350) bei soap_opera scheiterte im
# Ein-Schuss-Modus zuverlässig in allen 3 Versuchen (Antwort wurde vom Modell selbst
# abgebrochen, "continuing in the next reply" — es gibt aber keine nächste Antwort bei
# einem einzelnen '-p'-Aufruf). Der Default 3 x 35 (=105) lief unauffällig.
# 17.07.2026 von 200 auf 120 gesenkt: der Graubereich dazwischen (z.B. 6x30=180) riss
# in der Praxis oft ab — drei zum Scheitern verurteilte Ein-Schuss-Versuche à mehrere
# Minuten, BEVOR der ohnehin nötige Batch-Pfad startete ("manchmal endlos"-Symptomatik).
# Seit dem case_canon-Umbau ist der Batch-Pfad qualitativ gleichwertig (Kanon statt
# Drift) und in der Laufzeit planbar — der Ein-Schuss lohnt das Risiko nur noch bei
# wirklich kleinen Serien nahe dem belegten 105-Minuten-Datenpunkt.
BATCH_THRESHOLD_EPISODE_MINUTES = 120

# "3 Episoden x 35 Min. = 105" (siehe Kommentar oben) ist der einzige bisher beobachtete
# sicher-funktionierende Datenpunkt für EINEN Batch-Call in generate_series_batched() —
# TARGET_BATCH_EPISODE_MINUTES macht diesen Zusammenhang explizit, statt BATCH_SIZE als
# von der Episodenlänge losgelöste feste Zahl zu behandeln.
TARGET_BATCH_EPISODE_MINUTES = BATCH_SIZE_DEFAULT * DEFAULT_MINUTES  # = 105

# Obergrenze für gleichzeitig laufende Batch-Calls in Phase 2 von generate_series_batched()
# (siehe dort). Jeder Batch ist ein eigener, unabhängiger Claude-Aufruf (sieht nur das
# gemeinsame Skeleton, nicht die Ausgabe anderer Batches) — Phase 2 lief bisher rein seriell,
# obwohl nichts Inhaltliches das erzwingt. Gedeckelt, damit nicht mehr claude-Prozesse
# gleichzeitig laufen als nötig/sinnvoll (Rate-Limits, lokale Ressourcen) — bei den meisten
# Serien gibt es ohnehin nur 2-4 Batches insgesamt (episode_count / compute_batch_size()).
BATCH_PARALLEL_CAP = 4


def compute_batch_size(minutes: float) -> int:
    """Episoden pro Batch-Call, skaliert mit der gewünschten Episodenlänge — ein Batch
    trägt damit immer ungefähr TARGET_BATCH_EPISODE_MINUTES kombinierten Inhalt, egal wie
    lang die einzelne Episode ist. Ohne das war BATCH_SIZE bisher eine feste Zahl, die nur
    für die STANDARD-Länge (35 Min.) kalibriert war: bei deutlich längeren Episoden (z.B.
    --minutes 90) hätten 3 Episoden pro Batch weit mehr kombinierten Inhalt getragen als
    der beobachtete sichere Wert — genau das Abriss-Risiko, das generate_series_batched()
    eigentlich vermeiden soll, nur eine Ebene tiefer (pro Batch statt pro Ein-Schuss-
    Versuch der ganzen Serie).

    Nach oben bei BATCH_SIZE_DEFAULT gedeckelt (nie mehr Episoden pro Batch als bisher):
    für kürzere Episoden gibt es keinen Beleg, dass ein GRÖSSERER Batch sicher wäre, da
    case/character_knowledge-Overhead pro Episode nicht rein wortzahl-proportional ist —
    nur nach unten zu skalieren ist der vorsichtigere Weg, bis mehr Datenpunkte eine
    genauere Kalibrierung auch nach oben erlauben."""
    return max(1, min(BATCH_SIZE_DEFAULT, round(TARGET_BATCH_EPISODE_MINUTES / minutes)))


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


def build_prompt(template_text: str, topic: str, episode_count: int, minutes: float,
                 location_count: int = DEFAULT_LOCATION_COUNT) -> str:
    """Baut den vollen Prompt, mit der echten Figuren-Historie, der festen
    Episodenanzahl und der aus der Ziel-Episodenlänge abgeleiteten
    Section-Zahl eingefügt, und dem Thema am Ende angehängt."""
    used = "\n".join(
        f"- {h['figure']} (Serie: {h['series_title']})"
        for h in history.load_figure_history()
    ) or "(noch keine)"

    if "{{FIGURE_HISTORY}}" in template_text:
        template_text = template_text.replace("{{FIGURE_HISTORY}}", used)
    else:
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
            template_text = replaced
        else:
            print("⚠️  WARNUNG: Creator-Template hat weder {{FIGURE_HISTORY}} noch einen "
                  "'ALREADY-USED FIGURES'-Abschnitt — die Figuren-Historie wird NICHT "
                  "injiziert, frühere Figuren können sich wiederholen.")
    section_count = estimate_section_count(template_text, minutes)
    template_text = template_text.replace("{{EPISODE_COUNT}}", str(episode_count))
    template_text = template_text.replace("{{EPISODE_MINUTES}}", f"{minutes:g}")
    template_text = template_text.replace("{{SECTION_COUNT}}", str(section_count))
    template_text = template_text.replace("{{LOCATION_COUNT}}", str(location_count))

    # Single-Source-Substitutionen (Chelsie-Lektion): Stimmen-Roster und
    # Default-Modell leben in config.py und werden hier eingesetzt, statt
    # wörtlich kopiert in den Templates zu altern.
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

    leftover = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", template_text)))
    if leftover:
        print(f"⚠️  WARNUNG: unersetzte Platzhalter im Creator-Template: {', '.join(leftover)} — "
              f"sie landen wörtlich im Prompt (Tippfehler im Template?).")

    return template_text + topic


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


def check_section_detail(episodes: list, start_num: int = 1) -> list:
    """Meldet Episoden, deren 'sections' bloße TITEL statt Szenenbeschreibungen sind
    (Ø < SECTION_DETAIL_MIN_AVG_WORDS Wörter). Nur für CASE_BASED_TEMPLATES sinnvoll —
    crime_drama und soap_opera verlangen im EPISODES_CREATOR_PROMPT.md wörtlich
    "section title 1 (scene description, name which thread it belongs to)", narration
    dagegen ausdrücklich einen Titel ("The Hook & The Man with a Thousand Faces"). Der
    Check erzwingt also nur, was das Template ohnehin fordert; die Gate-Entscheidung
    trifft der Aufrufer.

    Warum das zählt (12-Serien-Analyse + Nachmessung 17.07.2026): die Section-Tiefe ist
    der stärkste Prädiktor für Skript-Qualität, den die Daten hergeben, und sie bricht
    PRO BATCH ein — jeder Batch ist ein eigener Claude-Aufruf, nichts fixiert die
    Granularität. the_glasshouse_vote: ep1-6 Ø 18-23 Wörter, ep7-10 Ø 3.7-4.1, exakt an
    der Batch-Grenze — und die schweren Fehler (Doppel-Geständnis in ep9+ep10, Deus ex
    machina im Finale) sitzen alle in ep7-10. the_founding_collection spiegelbildlich:
    ep1-3 Ø 8-10 (~39 Fehler), ep4-8 Ø 21-29 (~19). seven_seats gleichmäßig Ø 15-25 und
    entsprechend sauber. Der Grund ist mechanisch: aus "Declan's Turn" (ep9) und "The
    Ledger Laid Bare" (ep10) kann der Writer nicht ableiten, dass nur EINE der beiden
    das Geständnis tragen soll — beide Titel lesen sich gleich gut als "Declan legt die
    Bücher offen", und die zwei Batches sehen einander nicht. Mit erzählten Sections
    steht die Arbeitsteilung dagegen im Text.

    Rückgabe: Liste von Fehler-Strings (wie config.validate_data), gedacht als
    RETRYABLE-Fehler mit Feedback — dieselbe Mechanik, mit der das Wortbudget bei Parts
    schon funktioniert. start_num verschiebt die Nummerierung für Batch-Aufrufe, damit
    die Meldung die ECHTE Episodennummer nennt statt der Position im Batch."""
    errors = []
    for i, ep in enumerate(episodes, start=start_num):
        sections = ep.get("sections")
        if not isinstance(sections, list) or not sections:
            continue  # Struktur-Problem — das meldet config.validate_data() selbst
        texts = [s for s in sections if isinstance(s, str)]
        if not texts:
            continue
        avg = sum(len(s.split()) for s in texts) / len(texts)
        if avg < SECTION_DETAIL_MIN_AVG_WORDS:
            shortest = min(texts, key=lambda s: len(s.split()))
            errors.append(
                f"episodes[{i}].sections sind bloße Titel statt Szenenbeschreibungen "
                f"(Ø {avg:.1f} Wörter, verlangt sind mindestens {SECTION_DETAIL_MIN_AVG_WORDS} "
                f"im Schnitt) — z.B. \"{shortest}\". Jede Section braucht eine erzählte "
                f"Szene: wer ist beteiligt, was passiert, welcher Thread."
            )
    return errors


SECTION_DETAIL_FEEDBACK = (
    "\n\nAbout the \"sections\" problem above — this is the single most important thing to "
    "get right, so be concrete: every entry in \"sections\" must be a SCENE DESCRIPTION, not "
    "a title. Name who is in the scene, what actually happens, and which thread it belongs "
    "to. Good: \"Corner Diner: Liwei meets Iggy Chen for the first time in person, eager to "
    "prove the co-op will move fast\". Bad: \"The Ledger Laid Bare\", \"Declan's Turn\", "
    "\"The Vote\" — those read equally well as three different scenes, so the writer cannot "
    "tell which episode is supposed to carry which turning point, and two episodes end up "
    "playing the same climax twice."
)


def generate_with_retry(prompt: str, model: str, episode_count: int, case_based: bool = False):
    """Bis zu MAX_ATTEMPTS Claude-Aufrufe: ungültiges JSON, Struktur-Fehler
    aus validate_data und eine falsche Episodenanzahl werden als konkretes
    Feedback in den nächsten Versuch gegeben (gleicher Mechanismus wie
    call_claude_with_retry beim Skript-Writer). Gibt (data, warnings) zurück,
    oder (None, []) wenn kein einziger Versuch fallback-sicher war — der
    Aufrufer (main()) entscheidet dann, ob er auf generate_series_batched()
    ausweicht, statt hier selbst abzubrechen (sys.exit).

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
            if case_based:
                # Titel-statt-Szenen-Sections (siehe check_section_detail): retryable mit
                # Feedback, aber fallback-SICHER — dieselbe Disziplin wie beim Wortbudget,
                # eine Serie mit dünnen Sections ist besser als gar keine. Sie zählen aber
                # in badness, damit der Best-Effort-Fallback den erzähltesten Versuch nimmt
                # statt irgendeinen strukturell sauberen.
                thin = check_section_detail(data.get("episodes", []))
                badness += len(thin)
                errors.extend(thin)

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
                  "weitere Ein-Schuss-Versuche können das nicht beheben, "
                  "breche früh ab (Batch-Pfad übernimmt).")
            break
        feedback = (
            "\n\nIMPORTANT — your previous attempt was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again "
              "(full object, not a diff), following every rule above."
            + (SECTION_DETAIL_FEEDBACK if any("bloße Titel" in e for e in errors) else "")
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


def build_skeleton_prompt(creator_prompt: str, episode_count: int,
                          case_based: bool = False) -> str:
    """Für Phase 1 von generate_series_batched(): hängt an den (bereits vollständig
    substituierten) Creator-Prompt eine Zusatzanweisung an, die JEDEN Episode-Eintrag auf
    figure+theme reduziert — kein sections/section_words/case. Das allein macht die Antwort
    bei einer großen Serie schon um ein Vielfaches kleiner, da sections/case den Großteil des
    Volumens ausmachen.

    case_based: bei crime_drama/soap_opera wird zusätzlich ein Top-Level-Feld "case_canon"
    verlangt — die EINMAL festgelegten Threads der ganzen Staffel (label/solution/
    objective_facts). Grund (12-Serien-Analyse 17.07.2026): ohne fixierten Kanon erfand
    jeder Batch in Phase 2 die case-Blöcke unabhängig neu — Täternamen, Daten und
    Beweisstücke drifteten hörbar über die Staffel (cured_by_design: vier Namen für
    denselben Antagonisten). Im Ein-Schuss-Pfad passiert das nicht (eine Antwort =
    ein Kanon), deshalb braucht NUR der Batch-Pfad diese Verankerung."""
    extra = ""
    if case_based:
        extra = (
            f" Additionally output a top-level field \"case_canon\": the COMPLETE list of "
            f"case threads for the whole season, each with \"label\", \"solution\", and "
            f"\"objective_facts\" exactly as the per-episode case schema above defines them. "
            f"This canon is FINAL — episodes written later will carry only each thread's "
            f"\"label\" plus per-episode \"character_knowledge\"; \"solution\" and "
            f"\"objective_facts\" get injected from this canon mechanically. So settle every "
            f"name, date, place, and count here, once, definitively."
        )
    return creator_prompt + (
        f"\n\nIMPORTANT — OUTPUT SIZE FOR THIS RESPONSE: only the SERIES SKELETON is needed "
        f"now, not full episodes (they get written individually in a later step, you will see "
        f"this exact plan again then). Output the complete JSON object with every top-level "
        f"field exactly as specified above (series_title, format, voices/locations/course/"
        f"series_outro as applicable), and exactly {episode_count} entries in \"episodes\", "
        f"each containing ONLY \"figure\" and \"theme\" (a one-sentence compass of what this "
        f"episode covers, including which case/thread(s) it involves if applicable) — omit "
        f"\"sections\", \"section_words\", \"section_locations\", and \"case\" entirely for now."
        f"{extra}"
    )


def validate_skeleton(data, episode_count: int, case_based: bool = False) -> list:
    """Leichtgewichtige Validierung für die Skeleton-Phase — KEIN config.validate_data(),
    das würde 'sections'/'case' pro Episode verlangen, die im Skeleton bewusst fehlen.
    case_based: verlangt zusätzlich den Staffel-Kanon (siehe build_skeleton_prompt)."""
    if not isinstance(data, dict):
        return ["Skeleton war kein JSON-Objekt."]
    errors = []
    if not data.get("series_title"):
        errors.append("'series_title' fehlt.")
    episodes = data.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != episode_count:
        actual = len(episodes) if isinstance(episodes, list) else 0
        errors.append(f"'episodes' muss eine Liste mit genau {episode_count} Einträgen sein "
                      f"(hat {actual}).")
        return errors
    for i, ep in enumerate(episodes, start=1):
        if not isinstance(ep, dict) or not ep.get("figure") or not ep.get("theme"):
            errors.append(f"episodes[{i}] braucht mindestens 'figure' und 'theme'.")
    if case_based:
        canon = data.get("case_canon")
        if not isinstance(canon, list) or not canon:
            errors.append("'case_canon' fehlt oder ist keine nicht-leere Liste — der Staffel-"
                          "Kanon (label/solution/objective_facts pro Thread) ist Pflicht.")
        else:
            for j, thread in enumerate(canon, start=1):
                if (not isinstance(thread, dict)
                        or not isinstance(thread.get("label"), str) or not thread["label"].strip()
                        or not isinstance(thread.get("solution"), str) or not thread["solution"].strip()):
                    errors.append(f"case_canon[{j}] braucht mindestens nicht-leere Strings "
                                  f"'label' und 'solution'.")
    return errors


def generate_skeleton_with_retry(creator_prompt: str, episode_count: int, model: str,
                                 case_based: bool = False):
    """Phase 1 von generate_series_batched(): dieselbe Retry-mit-Feedback-Schleife wie
    generate_with_retry(), aber für das leichtgewichtige Skeleton statt der vollen Serie —
    kein Best-Effort-Fallback nötig, ein Skeleton ist entweder brauchbar oder nicht, es gibt
    keine sinnvolle 'am wenigsten schlechte' Zwischenstufe wie bei einer falschen
    Episodenzahl. Gibt das Skeleton-dict zurück, oder None nach MAX_ATTEMPTS Fehlschlägen."""
    prompt = build_skeleton_prompt(creator_prompt, episode_count, case_based=case_based)
    timeout = compute_timeout(episode_count)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            print(f"  🔁  Skeleton — Versuch {attempt}/{MAX_ATTEMPTS} (mit Fehler-Feedback) ...")
        raw = call_claude(prompt + feedback, model, timeout=timeout,
                          label=f"Skeleton generieren (Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            feedback = ""
            continue

        data = parse_json_response(raw)
        if data is None:
            print_raw_snippet(raw, indent="    ")
            errors = ["Die Antwort war kein valides JSON-Objekt."]
        else:
            errors = validate_skeleton(data, episode_count, case_based=case_based)

        if not errors:
            return data

        print(f"  ⚠️  Skeleton — Versuch {attempt} abgelehnt ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"    - {e}")
        feedback = (
            "\n\nIMPORTANT — your previous attempt was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again "
              "(full object, not a diff), following every rule above."
        )

    return None


EXPAND_BATCH_PROMPT = """{creator_prompt}

IMPORTANT — this call is one BATCH of a larger season being generated in stages, to keep each
response small enough to complete reliably. The season's already-finalized skeleton is below —
do NOT change any of its fields, they are fixed:

SERIES SKELETON (series_title, format, voices/locations/course as applicable, and the planned
"figure"+"theme" for EVERY episode of the season, so you can see the whole arc for continuity):
{skeleton_json}

Your job for THIS response: output ONLY this JSON shape —
{{"episodes": [ ...full episode objects for episodes {start} through {end} (1-indexed, {count} episodes total in this batch)... ]}}
— nothing else, no other top-level fields, no commentary before or after. Each episode object
must follow the full per-episode schema from the instructions above (sections, section_words if
applicable, case, etc.) and use EXACTLY the "figure" and "theme" already planned for it in the
skeleton above — do not invent different ones. Stay consistent with every other episode's plan
shown above for continuity, especially any recurring case/thread developments, even though you
are only writing episodes {start}-{end} in this response.

If the skeleton contains a "case_canon": it is the FINAL, season-wide truth for every
thread's "solution" and "objective_facts" — those two fields are injected mechanically from
the canon after generation, so do NOT output them at all (this keeps your response short
enough to complete reliably). Each episode's "case" entries must contain ONLY "label"
(copied EXACTLY from the canon — never invent, rename, or merge threads) and
"character_knowledge" (what each character knows/hides/believes at THIS point of the
season — the only part that evolves per episode). Everything else you write (sections,
themes, intro/outro notes) must stay consistent with the canon's names, dates, places, and
counts: other batches are being written independently against the same canon, and any
invented variation becomes an audible continuity break in the finished season.
"""


def compute_batch_timeout(batch_size: int) -> int:
    """Wie compute_timeout(), aber für einen einzelnen Episoden-Batch statt die ganze Serie —
    kleinerer Floor, ein Batch enthält nur wenige Episoden."""
    return min(2400, max(450, 180 * batch_size))


def generate_batch_with_retry(creator_prompt: str, skeleton: dict, start: int, end: int, model: str):
    """Phase 2 von generate_series_batched(): schreibt die vollen Episode-Objekte für
    episodes[start..end] (1-indexed, inklusive), mit dem Skeleton als Kontext für Kontinuität.

    Validiert die Antwort, indem ein Kandidat-Dokument aus dem Skeleton gebaut wird, dessen
    "episodes" NUR aus diesem Batch besteht, und darauf config.validate_data() läuft — nutzt
    die bestehende, erschöpfende Struktur-Validierung wieder statt sie für Einzel-Episoden zu
    duplizieren. validate_data() prüft nirgends eine feste Gesamt-Episodenzahl (das macht nur
    generate_with_retry() für den Ein-Schuss-Fall), ein Teil-Dokument mit nur diesem Batch ist
    also unproblematisch — und es gibt keine season-weite Prüfung in validate_data(), die eine
    Sicht auf ALLE Episoden gleichzeitig bräuchte (Stimmen-Eindeutigkeit etc. hängt nur an den
    aus dem Skeleton übernommenen Top-Level-Feldern, nicht an den Episodeninhalten).

    Thread-sicher: liest nur seine eigenen Parameter, mutiert `skeleton` nie (die Kandidat-
    Kopie für die Validierung entsteht pro Aufruf frisch über json.loads(json.dumps(...))) und
    schreibt nirgends in geteilten Zustand — call_claude()/config.validate_data() kommen
    ebenfalls ohne globalen Zustand aus. generate_series_batched() ruft diese Funktion für
    mehrere Batches parallel über einen ThreadPoolExecutor auf (siehe dort), genau deshalb
    ist das hier wichtig."""
    count = end - start + 1
    prompt = EXPAND_BATCH_PROMPT.format(
        creator_prompt=creator_prompt,
        skeleton_json=json.dumps(skeleton, ensure_ascii=False, indent=2),
        start=start, end=end, count=count,
    )
    timeout = compute_batch_timeout(count)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            print(f"    🔁  Episoden {start}-{end} — Versuch {attempt}/{MAX_ATTEMPTS} (mit Fehler-Feedback) ...")
        raw = call_claude(prompt + feedback, model, timeout=timeout,
                          label=f"Episoden {start}-{end} generieren (Versuch {attempt}/{MAX_ATTEMPTS})")
        if not raw:
            feedback = ""
            continue

        parsed = parse_json_response(raw)
        batch_episodes = parsed.get("episodes") if isinstance(parsed, dict) else None
        if not isinstance(batch_episodes, list) or len(batch_episodes) != count:
            print_raw_snippet(raw, indent="      ")
            errors = [f"Antwort enthielt keine 'episodes'-Liste mit genau {count} Einträgen."]
            if count > 1 and response_looks_truncated(raw):
                # Klarer Abriss: weitere Versuche bei DIESER Batch-Größe scheitern
                # identisch — überspringe sie und gehe direkt in die Halbierung
                # unten (kleinerer Batch = kürzere Antwort).
                print(f"    ✂️  Episoden {start}-{end}: Antwort offenbar abgeschnitten — "
                      f"überspringe weitere Versuche dieser Größe, halbiere sofort ...")
                break
        else:
            candidate = json.loads(json.dumps(skeleton))  # billige tiefe Kopie
            candidate.pop("case_canon", None)  # kein episodes.json-Feld — nur Skeleton-Kontext
            candidate["episodes"] = batch_episodes
            errors, _warnings = config.validate_data(candidate)
            # Section-Tiefe: DER Ort, an dem sie einbricht (siehe check_section_detail) —
            # jeder Batch ist ein eigener Aufruf, und in Produktion lieferten manche
            # erzählte Szenen, andere blanke Titel, ohne dass irgendetwas anschlug.
            # start_num=start: die Meldung nennt die echte Episodennummer, nicht die
            # Position im Batch.
            if skeleton.get("template") in CASE_BASED_TEMPLATES:
                errors.extend(check_section_detail(batch_episodes, start_num=start))

        if not errors:
            return batch_episodes

        print(f"    ⚠️  Episoden {start}-{end} — Versuch {attempt} abgelehnt ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"      - {e}")
        feedback = (
            "\n\nIMPORTANT — your previous attempt was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again "
              "(the {\"episodes\": [...]} object for this batch only), following every rule above."
            + (SECTION_DETAIL_FEEDBACK if any("bloße Titel" in e for e in errors) else "")
        )

    # Alle MAX_ATTEMPTS Versuche bei DIESER Batch-Größe sind gescheitert. Beobachtet in
    # Produktion (16.07.2026): bei soap_opera mit vielen case-Threads/character_knowledge
    # war die Antwort mehrere tausend Zeichen lang und an KEINER '{'-Position vollständig
    # dekodierbar — ein starkes Indiz für eine mitten in der verschachtelten Struktur
    # abgeschnittene Antwort, weil der Batch schlicht zu viel Inhalt verlangt hat.
    # compute_batch_size() skaliert nur mit Minuten, nicht mit Thread-/Charakteranzahl
    # (siehe dessen Docstring) — kann also für inhaltsreiche Konfigurationen zu groß
    # geraten sein, ohne dass Minuten allein das vorhersagen. Statt denselben zu großen
    # Versuch ein drittes Mal blind zu wiederholen: halbieren. Ein kleinerer Batch braucht
    # eine kürzere Antwort (geringeres Abschneide-Risiko) und bekommt sein eigenes,
    # frisches MAX_ATTEMPTS-Budget. Rekursion terminiert spätestens bei count==1.
    if count > 1:
        mid = (start + end) // 2
        print(f"    ✂️  Episoden {start}-{end}: alle {MAX_ATTEMPTS} Versuche bei Batch-Größe "
              f"{count} gescheitert — halbiere in {start}-{mid} und {mid + 1}-{end} "
              f"(kleinerer Batch = kürzere Antwort = geringeres Abschneide-Risiko) ...")
        first_half = generate_batch_with_retry(creator_prompt, skeleton, start, mid, model)
        second_half = generate_batch_with_retry(creator_prompt, skeleton, mid + 1, end, model)
        if first_half is not None and second_half is not None:
            return first_half + second_half

    return None


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


def apply_case_canon(data: dict) -> int:
    """Normalisiert 'solution' und 'objective_facts' jedes Episode-Threads
    deterministisch auf die Kanon-Fassung aus data['case_canon'] (Match über
    'label'; ein Fall OHNE Label matcht einen Ein-Thread-Kanon, ein Label MIT
    abweichendem Namen dagegen nie — siehe Kommentar unten). Die
    wörtliche Kopie IST die dokumentierte Invariante (siehe EXPAND_BATCH_PROMPT
    und der Beleg aus vanishing_signal: im Ein-Schuss-Pfad sind alle
    solution-Texte über 10 Episoden zeichengleich) — deshalb hier Code statt
    eines weiteren LLM-Calls. Gibt die Anzahl angepasster Threads zurück."""
    canon = data.get("case_canon")
    if not isinstance(canon, list) or not canon:
        return 0
    by_label = {_normalize_ws(t.get("label", "")).lower(): t
                for t in canon if isinstance(t, dict)}
    changed = 0
    unmatched = set()
    for ep_idx, ep in enumerate(data.get("episodes", []), start=1):
        threads = _episode_threads(ep)
        for thread in threads:
            key = _normalize_ws(thread.get("label", "")).lower()
            ct = by_label.get(key)
            if ct is None and not key and len(by_label) == 1 and len(threads) == 1:
                # Der label-LOSE Einzel-Fall (crime_drama: 'case' ist ein einzelnes Objekt
                # ohne 'label', ein Fall = ein Thread) gegen einen Ein-Thread-Kanon — da gibt
                # es nichts zu verwechseln. Bewusst nur bei LEEREM Label: ein Thread MIT
                # abweichendem Label ist keine fehlende Zuordnung, sondern eine Umbenennung.
                # Die still zu kanonisieren hieße, dem Thread die richtigen Fakten unter dem
                # FALSCHEN Namen zu geben — und weil das Ergebnis dann sauber aussieht,
                # bliebe die Umbenennung unbemerkt (check_case_drift vergleicht Episoden
                # untereinander, nicht gegen den Kanon: benennen alle Episoden denselben
                # Thread einheitlich um, fällt es nirgends mehr auf). Deshalb: warnen.
                ct = next(iter(by_label.values()))
            if ct is None:
                unmatched.add(f"Episode {ep_idx}: '{thread.get('label', '(ohne Label)')}'")
                continue
            for field in ("solution", "objective_facts"):
                if field in ct and thread.get(field) != ct[field]:
                    thread[field] = ct[field]
                    changed += 1
    if unmatched:
        # Seit dem Schlank-Umbau tragen Batch-Episoden nur label+character_knowledge —
        # ein Label ohne Kanon-Treffer bleibt dann OHNE solution/objective_facts und
        # wäre beim Schreiben ein Thread ohne Wissens-Grundlage. Laut machen.
        print(f"  ⚠️  {len(unmatched)} Episode-Thread(s) ohne Kanon-Treffer (Label erfunden "
              f"oder umbenannt?) — behalten unverändert, aber ohne injizierte "
              f"solution/objective_facts: {'; '.join(sorted(unmatched)[:4])}")
    return changed


def check_case_drift(data: dict) -> list:
    """Deterministischer Kanon-Check (Gegenstück zu check_section_words_gaps,
    läuft IMMER — auch im Ein-Schuss-Pfad und nach --fix): vergleicht die
    case-Threads aller Episoden untereinander. In einer konsistenten Serie
    sind 'solution' und 'objective_facts' pro Thread-Label über ALLE Episoden
    wörtlich identisch — nur character_knowledge wächst (siehe
    templates/CLAUDE.md). Jede Abweichung ist ein Konsistenz-Befund: genau
    diese Drift erzeugte in der 12-Serien-Analyse (17.07.2026) die schwersten
    Kontinuitätsfehler (Täter mit vier Namen etc.).

    Rückgabe: Liste von {"episodes": [int], "problem": str} — dasselbe
    strukturierte Format wie review_series(), damit beide Quellen über
    dieselbe gezielte Episoden-Reparatur laufen können (siehe repair_series()).
    "episodes" nennt hier immer die ABWEICHENDE Episode (nicht die
    Referenz-Episode) — die ist die, die korrigiert werden muss."""
    issues = []
    episodes = data.get("episodes", [])
    # Referenz: erstes Auftreten eines Labels
    reference = {}   # label_key -> (ep_num, label_display, solution_norm, facts_set)
    labels_by_ep = []
    for ep_idx, ep in enumerate(episodes, start=1):
        threads = _episode_threads(ep)
        if not threads:
            labels_by_ep.append(None)
            continue
        ep_labels = set()
        for thread in threads:
            label = _normalize_ws(thread.get("label", ""))
            key = label.lower()
            ep_labels.add(key)
            sol = _normalize_ws(thread.get("solution", ""))
            facts = frozenset(_normalize_ws(f) for f in (thread.get("objective_facts") or []))
            if key not in reference:
                reference[key] = (ep_idx, label or "(ohne Label)", sol, facts)
                continue
            first_ep, disp, ref_sol, ref_facts = reference[key]
            if sol and ref_sol and sol != ref_sol:
                issues.append({"episodes": [ep_idx], "problem": (
                    f"Episode {ep_idx}, Thread '{disp}': 'solution' weicht von Episode "
                    f"{first_ep} ab — der Kanon eines Threads muss über alle Episoden "
                    f"wörtlich identisch sein (nur character_knowledge entwickelt sich). "
                    f"Ep{first_ep}: \"{ref_sol[:90]}…\" vs. Ep{ep_idx}: \"{sol[:90]}…\""
                )})
            if facts and ref_facts and facts != ref_facts:
                gone = sorted(f[:70] for f in (ref_facts - facts))[:3]
                new = sorted(f[:70] for f in (facts - ref_facts))[:3]
                issues.append({"episodes": [ep_idx], "problem": (
                    f"Episode {ep_idx}, Thread '{disp}': 'objective_facts' weichen von "
                    f"Episode {first_ep} ab"
                    + (f" — entfallen z.B.: {gone}" if gone else "")
                    + (f" — neu/umformuliert z.B.: {new}" if new else "")
                )})
        labels_by_ep.append(ep_labels)
    # Wechselnde Label-Mengen: ein Thread, der mittendrin verschwindet oder neu
    # auftaucht, ist bei soap_opera legal (nicht jede Episode treibt jeden
    # Thread) — nur ein Label, das NIRGENDS sonst vorkommt (Tippfehler/Umbenennung),
    # wird gemeldet.
    all_keys = {k for s in labels_by_ep if s for k in s}
    seen_count = {k: sum(1 for s in labels_by_ep if s and k in s) for k in all_keys}
    for key, count in seen_count.items():
        if count == 1 and len([s for s in labels_by_ep if s]) > 2:
            ep_num = next(i for i, s in enumerate(labels_by_ep, start=1) if s and key in s)
            disp = reference[key][1]
            issues.append({"episodes": [ep_num], "problem": (
                f"Thread-Label '{disp}' kommt NUR in Episode {ep_num} vor — bei einem "
                f"staffelweiten Thread deutet das auf eine Umbenennung/einen Tippfehler hin "
                f"(gleicher Thread unter anderem Namen in den übrigen Episoden?)"
            )})
    return issues


CHECKPOINT_STAGING_DIR = os.path.join(paths.DATA_DIR, ".create_series_staging")
# Zwischenspeicher NUR für den Batch-Pfad (generate_series_batched): Skeleton und
# jeder fertig generierte Batch werden hier abgelegt, sobald sie erfolgreich sind.
# Scheitert später EIN anderer Batch endgültig (nach allen Retries/Halbierungen),
# muss ein Rerun nur den fehlenden Teil neu generieren statt die ganze Serie —
# genau der Fortschrittsverlust, der beim Serie-erstellen-Schritt am meisten Zeit
# kostet (17.07.2026, Nutzer-Feedback). Der EIN-SCHUSS-Pfad (generate_with_retry)
# braucht das bewusst NICHT: er ist atomar (eine Antwort, ganz oder gar nicht) und
# fällt bei Scheitern ohnehin auf diesen Batch-Pfad zurück — es gibt dort keine
# Teil-Fortschritte, die es zu retten lohnt.
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


def _cached_batch(checkpoint_key: str, creator_prompt: str, skeleton: dict,
                  start: int, end: int, model: str):
    """Wrapper um generate_batch_with_retry() mit Checkpoint: lädt einen bereits
    erfolgreich generierten Batch von Platte statt ihn neu zu erzeugen, speichert
    einen frisch erfolgreichen sofort. generate_batch_with_retry() selbst bleibt
    unverändert thread-sicher/zustandslos (siehe dessen Docstring) — die einzige
    Nebenwirkung (Datei schreiben) sitzt hier, im Worker-Thread des jeweiligen
    Batches, bevor future.result() im Hauptthread zurückkehrt: selbst ein
    Prozess-Kill mitten in einem ANDEREN Batch verliert diesen hier nicht."""
    path = os.path.join(_checkpoint_dir(checkpoint_key), f"batch_{start}-{end}.json")
    cached = _load_checkpoint_json(path)
    if isinstance(cached, list) and len(cached) == end - start + 1:
        print(f"    ↺  Episoden {start}-{end}/…  aus Checkpoint übernommen — "
              f"Generierung übersprungen.")
        return cached
    result = generate_batch_with_retry(creator_prompt, skeleton, start, end, model)
    if result is not None:
        _save_checkpoint_json(path, result)
    return result


def generate_series_batched(creator_prompt: str, episode_count: int, model: str, minutes: float,
                            checkpoint_key: str, case_based: bool = False):
    """Rettungsweg, wenn generate_with_retry() den kompletten Ein-Schuss-Aufruf nicht
    hinbekommt (typischerweise: eine große soap_opera-Serie mit vielen Episoden/Threads
    erzeugt so viel strukturiertes JSON, dass die Antwort mitten drin abgeschnitten wird).
    creator_prompt ist hier bereits derselbe vollständig substituierte Prompt, der auch im
    Ein-Schuss-Versuch verwendet wurde (FIGURE_HISTORY/EPISODE_COUNT/SECTION_COUNT/
    LOCATION_COUNT schon eingesetzt, Topic angehängt) — wird hier NICHT nochmal neu gebaut,
    um figure_history.json nicht zweimal zu lesen.

    Statt der ganzen Serie in EINEM Call wird zuerst nur ein leichtgewichtiges Skeleton
    generiert (series_title/format/voices/locations/course + figure+theme pro Episode, ohne
    sections/case), danach die vollen Episode-Objekte in Gruppen von compute_batch_size(minutes)
    — jeder Batch sieht das komplette Skeleton (alle Episoden-Themen) für Kontinuität, schreibt
    aber nur seine eigene Gruppe aus. minutes wird nur für die Batch-Größe gebraucht (siehe
    compute_batch_size()) — alle Episoden EINER create_series.py-Serie teilen sich dieselbe
    Ziel-Länge, das SECTION_COUNT}}-Substitut im Prompt steckt schon in creator_prompt.

    Gibt (data, warnings) wie generate_with_retry() zurück, oder (None, []) wenn schon das
    Skeleton scheitert oder irgendein Batch nach MAX_ATTEMPTS nicht zustande kommt — die
    bereits erfolgreich generierten Episoden werden dann verworfen statt eine Serie mit
    Lücken zu erzeugen.

    case_based: bei crime_drama/soap_opera enthält das Skeleton zusätzlich den
    Staffel-Kanon 'case_canon' (siehe build_skeleton_prompt) — nach dem Zusammensetzen
    werden solution/objective_facts aller Episoden deterministisch darauf normalisiert
    (apply_case_canon) und der Kanon vor der Rückgabe entfernt (kein episodes.json-Feld).

    Checkpoint: Skeleton und jeder fertig generierte Batch werden unter
    CHECKPOINT_STAGING_DIR/<checkpoint_key>/ zwischengespeichert (siehe dessen Kommentar) —
    ein Rerun mit IDENTISCHEM Aufruf generiert nur noch, was beim letzten Mal fehlte, statt
    bei Null anzufangen. checkpoint_key kommt von main() (siehe _checkpoint_key()), weil
    main() die Aufruf-Parameter kennt und denselben Schlüssel ganz am Ende zum Aufräumen
    des Ordners noch einmal braucht."""

    print("  Phase 1/2: Skeleton (Cast, Orte, Format, Episoden-Themen"
          + (", Staffel-Kanon" if case_based else "") + ") ...")
    skeleton_ckpt_path = os.path.join(_checkpoint_dir(checkpoint_key), "skeleton.json")
    skeleton = _load_checkpoint_json(skeleton_ckpt_path)
    if skeleton is not None:
        skeleton_errors = validate_skeleton(skeleton, episode_count, case_based=case_based)
        if skeleton_errors:
            print("    ⚠️  Vorhandener Skeleton-Checkpoint ist ungültig (Code seither "
                  "geändert?) — wird verworfen und neu generiert.")
            skeleton = None
        else:
            print(f"    ↺  Skeleton aus Checkpoint übernommen "
                  f"({os.path.basename(skeleton_ckpt_path)}) — Generierung übersprungen.")
    if skeleton is None:
        skeleton = generate_skeleton_with_retry(creator_prompt, episode_count, model,
                                                case_based=case_based)
        if skeleton is None:
            print("  ❌  Skeleton-Generierung gescheitert.")
            return None, []
        _save_checkpoint_json(skeleton_ckpt_path, skeleton)

    batch_size = compute_batch_size(minutes)
    batches = [(i, min(i + batch_size - 1, episode_count))
               for i in range(1, episode_count + 1, batch_size)]
    max_workers = max(1, min(len(batches), BATCH_PARALLEL_CAP))
    print(f"  Phase 2/2: {len(batches)} Episoden-Batch(es) à bis zu {batch_size} Episoden "
          f"(bei {minutes:g} Min./Episode), {max_workers} parallel — typische Laufzeit "
          f"3-6 Min. pro Batch, der Heartbeat unten zählt mit; das ist normale "
          f"Generierungszeit, kein Hänger ...")

    # Jeder Batch ist unabhängig (sieht nur das gemeinsame, bereits fixierte Skeleton, nicht
    # die Ausgabe anderer Batches — siehe generate_batch_with_retry()'s Docstring) und lief
    # bisher trotzdem rein seriell. Mit ThreadPoolExecutor parallelisiert (I/O-bound: die Zeit
    # geht fast komplett im Warten auf den claude-Subprozess drauf, siehe run_claude_process())
    # — bei z.B. 3 Batches praktisch die Gesamtzeit von Phase 2 durch bis zu BATCH_PARALLEL_CAP
    # statt sie aufzusummieren. Läuft absichtlich bis zum Ende durch statt beim ersten
    # Fehlschlag abzubrechen: alle bereits gestarteten Batches sind ohnehin schon unterwegs,
    # ein früher return würde nur ihre Zeit verschwenden, ohne das Ergebnis zu ändern (ein
    # einziger gescheiterter Batch macht die zusammengesetzte Serie ohnehin ungültig — welcher
    # zuerst scheitert, ist irrelevant). Ergebnisse kommen über as_completed() in
    # Fertigstellungs- statt Batch-Reihenfolge zurück und werden über batch_results (keyed
    # nach start-Index) wieder in der ursprünglichen Episodenreihenfolge zusammengesetzt.
    batch_results = {}
    failed_batches = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_cached_batch, checkpoint_key, creator_prompt, skeleton,
                       start, end, model): (start, end)
            for start, end in batches
        }
        for future in concurrent.futures.as_completed(futures):
            start, end = futures[future]
            batch_episodes = future.result()
            if batch_episodes is None:
                print(f"  ❌  Episoden {start}-{end} nach {MAX_ATTEMPTS} Versuchen gescheitert.")
                failed_batches.append((start, end))
            else:
                print(f"    Episoden {start}-{end}/{episode_count} ✓")
                batch_results[start] = batch_episodes

    if failed_batches:
        print(f"  💾  {len(batch_results)}/{len(batches)} erfolgreiche Batch(es) bleiben unter "
              f"{_checkpoint_dir(checkpoint_key)} zwischengespeichert — derselbe Aufruf "
              f"(gleiches Thema/Template/Episodenzahl/Minuten) generiert bei einem erneuten "
              f"Versuch nur noch die fehlgeschlagenen Episoden {sorted(failed_batches)} neu.")
        return None, []

    full_episodes = []
    for start, end in batches:
        full_episodes.extend(batch_results[start])

    data = skeleton
    data["episodes"] = full_episodes
    # Kanon durchsetzen: wörtliche Kopie ist die Invariante — Abweichungen, die
    # trotz der Prompt-Regel entstanden sind, werden hier deterministisch
    # zurückgeschrieben statt auf einen weiteren LLM-Call zu hoffen. Danach
    # fliegt case_canon raus (kein Feld des episodes.json-Schemas).
    normalized = apply_case_canon(data)
    if normalized:
        print(f"  🧭  Staffel-Kanon durchgesetzt: {normalized} Thread-Feld(er) auf die "
              f"Kanon-Fassung normalisiert (solution/objective_facts wörtlich vereinheitlicht).")
    data.pop("case_canon", None)
    errors, warnings = config.validate_data(data)
    if errors:
        # Sollte nach den Einzel-Batch-Validierungen eigentlich nicht mehr auftreten — reiner
        # Sicherheitsnetz-Check auf dem zusammengesetzten Gesamtdokument, analog zu
        # repair_series(), das seine Korrektur auch immer neu validiert statt zu vertrauen.
        print(f"  ❌  Zusammengesetzte Serie ungültig ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"    - {e}")
        # Checkpoint bleibt erhalten (nicht gecleart) — die Einzel-Batches waren jeweils
        # für sich valide, dieser Fehler betrifft nur das Gesamtdokument; ein erneuter
        # Lauf muss Skeleton/Batches deshalb nicht neu generieren.
        return None, []

    # ACHTUNG: hier bewusst NICHT _clear_checkpoint() aufrufen, obwohl Skeleton+Batches
    # erfolgreich waren — main() lässt nach diesem Return noch Inhalts-Review UND ggf.
    # --fix-Reparatur laufen (beides eigene, oft lange Claude-Aufrufe), BEVOR die Serie
    # überhaupt auf Platte geschrieben wird (paths.reserve_unique_series() erst ganz am
    # Ende von main()). Ein hier zu früh gelöschter Checkpoint hätte einen Abbruch
    # WÄHREND Review/Reparatur so aussehen lassen, als müsse beim nächsten Versuch die
    # komplette (teuerste) Skeleton+Batch-Phase erneut laufen — obwohl die schon fertig
    # war. main() räumt den Checkpoint deshalb selbst auf, erst NACH dem erfolgreichen
    # Schreiben der Datei (siehe _checkpoint_key()-Aufruf dort).
    return data, warnings


SECTION_WORDS_MIN_GAP = 80  # ein section_words-Override, der weniger als das unter dem
                            # episode-weiten Minimum liegt, ist kein echter Pace-Wechsel
                            # (siehe EPISODES_CREATOR_PROMPT.md 'section_words'-Regel)


def check_section_words_gaps(data: dict) -> list:
    """Deterministische Ergänzung zu review_series Check 5 (SECTION LENGTH BUDGET
    MISMATCH): vergleicht jedes NICHT-null section_words.min gegen das episode-weite
    format.words_per_part_min und meldet jeden Override, der weniger als
    SECTION_WORDS_MIN_GAP darunter liegt.

    Bewusst als reiner Zahlenvergleich statt Teil des LLM-Reviews: im Praxistest
    (Serie 'vanishing_signal') hat review_series genau diesen Fall — section_words.min
    nur 30-50 Wörter unter dem Default statt der geforderten deutlichen Absenkung —
    NICHT gefunden, vermutlich weil ein stumpfer Zahlenvergleich über viele Episoden/
    Sections hinweg neben vier anderen inhaltlichen Prüfungen in derselben Antwort
    leicht untergeht. Läuft immer (auch mit --no-review), da lokal und kostenlos."""
    default_min = data.get("format", {}).get("words_per_part_min")
    if not isinstance(default_min, (int, float)):
        return []
    issues = []
    for ep_idx, ep in enumerate(data.get("episodes", []), start=1):
        section_words = ep.get("section_words")
        if not section_words:
            continue
        sections = ep.get("sections", [])
        for sec_idx, override in enumerate(section_words, start=1):
            if not isinstance(override, dict):
                continue
            omin = override.get("min")
            if not isinstance(omin, (int, float)):
                continue
            gap = default_min - omin
            if 0 < gap < SECTION_WORDS_MIN_GAP:
                title = sections[sec_idx - 1][:60] if sec_idx - 1 < len(sections) else ""
                issues.append(
                    f"Episode {ep_idx}, Section {sec_idx} (\"{title}\"): section_words.min "
                    f"{omin} liegt nur {gap} Wörter unter dem episode-weiten Minimum "
                    f"{default_min} — zu knapp für einen echten Pace-Wechsel (Faustregel: "
                    f"mindestens {SECTION_WORDS_MIN_GAP} Wörter Abstand), führt beim "
                    f"Schreiben erfahrungsgemäß zu wiederholten Unterschreitungen."
                )
    return issues


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

    creator_prompt = load_creator_prompt(args.template)

    print(f"🧠  Erzeuge neue Serie ({args.episodes} Episoden, ~{args.minutes:g} Min./Episode, "
          f"{args.locations} Orte, Template '{args.template}') zum Thema: \"{args.topic}\" ...")
    prompt = build_prompt(creator_prompt, args.topic, args.episodes, args.minutes, args.locations)

    episode_minutes = args.episodes * args.minutes
    skip_one_shot = (args.template in CASE_BASED_TEMPLATES
                     and episode_minutes >= BATCH_THRESHOLD_EPISODE_MINUTES)

    case_based = args.template in CASE_BASED_TEMPLATES
    # Einmal berechnet, zweimal gebraucht: für den Batch-Checkpoint unten und zum
    # Aufräumen desselben Ordners ganz am Ende von main().
    checkpoint_key = _checkpoint_key(args.topic, args.template, args.episodes, args.minutes,
                                     args.locations, config.DEFAULTS["model"], case_based)
    if skip_one_shot:
        print(f"🧩  {args.episodes} Episoden × {args.minutes:g} Min. bei '{args.template}' — "
              f"das sprengt erfahrungsgemäß eine einzelne Antwort (siehe BATCH_THRESHOLD_"
              f"EPISODE_MINUTES). Gehe direkt auf Batch-Generierung, ohne die Zeit für einen "
              f"praktisch aussichtslosen Ein-Schuss-Versuch erst zu verschwenden ...")
        data, warnings = generate_series_batched(prompt, args.episodes, config.DEFAULTS["model"],
                                                 args.minutes, checkpoint_key,
                                                 case_based=case_based)
        if data is None:
            print("❌  Batch-Generierung ist gescheitert — Abbruch.")
            sys.exit(1)
    else:
        data, warnings = generate_with_retry(prompt, config.DEFAULTS["model"], args.episodes,
                                             case_based=case_based)
        if data is None:
            print("🧩  Wechsle zu Batch-Generierung (Grundgerüst zuerst, dann Episoden in kleinen "
                  "Gruppen) — vermeidet, dass eine große Serie in einer einzigen, zu langen "
                  "Antwort abgeschnitten wird ...")
            data, warnings = generate_series_batched(prompt, args.episodes, config.DEFAULTS["model"],
                                                     args.minutes, case_based=case_based)
            if data is None:
                print("❌  Auch die Batch-Generierung ist gescheitert — Abbruch.")
                sys.exit(1)

    # Template-Zuordnung sicherstellen — der Renderer/Writer wählt darüber
    # PROMPT_TEMPLATE.md und (bei drama) das Skriptformat.
    data.setdefault("template", args.template)

    for w in warnings:
        print(f"WARNUNG: {w}")

    for w in check_section_words_gaps(data):
        print(f"WARNUNG: {w}")

    # Kanon-Drift-Check (deterministisch, gratis, läuft IMMER — auch mit
    # --no-review): solution/objective_facts pro Thread müssen über alle
    # Episoden wörtlich identisch sein. Mit --fix gehen Befunde an
    # repair_series() (dieselbe Maschine wie fürs Inhalts-Review), sonst
    # werden sie laut gewarnt.
    drift_issues = check_case_drift(data)
    if drift_issues and args.fix:
        print(f"🧭  Kanon-Drift: {len(drift_issues)} Befund(e) — versuche automatische Reparatur ...")
        fixed = repair_series(data, drift_issues, config.DEFAULTS["model"], args.episodes)
        if fixed is not None:
            data = fixed
            data.setdefault("template", args.template)
            drift_issues = check_case_drift(data)
        else:
            print("  ⚠️  Kanon-Reparatur fehlgeschlagen — episodes.json bleibt beim "
                  "ursprünglichen Stand, Befunde unten von Hand prüfen.")
    for w in drift_issues:
        print(f"WARNUNG (Kanon-Drift): {w['problem']}")

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
                for w in check_section_words_gaps(data):
                    print(f"WARNUNG: {w}")
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
              f"'{slug}' wurde wieder freigegeben. Der Batch-Checkpoint bleibt erhalten: "
              f"ein identischer Neustart übernimmt Skeleton und Episoden von Platte.")
        raise
    paths.write_latest(slug)

    # Jetzt erst den Batch-Checkpoint aufräumen (siehe Kommentar in
    # generate_series_batched()) — die Serie ist ab hier unwiderruflich
    # gespeichert, ein Rerun braucht den Zwischenspeicher nicht mehr. Harmlos,
    # falls der Ein-Schuss-Pfad direkt erfolgreich war (dann existiert der
    # Ordner nie, _clear_checkpoint() räumt einfach nichts auf).
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
