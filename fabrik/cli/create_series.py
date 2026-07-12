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
import json
import os
import re
import subprocess
import sys
from typing import Optional

from fabrik.core import config, history, paths, workspace
from fabrik.core.claude_cli import describe_json_error, parse_json_response, run_claude_process

TIMEOUT_SECONDS = 600
MAX_ATTEMPTS = 3
DEFAULT_EPISODE_COUNT = 3
DEFAULT_MINUTES = 35.0
DEFAULT_LOCATION_COUNT = 4
BATCH_SIZE = 3  # Episoden pro Erweiterungs-Call in generate_series_batched()
# Grobe Sprechgeschwindigkeit für Qwen3-TTS-Erzähltempo — nur zur Umrechnung
# Minuten -> Ziel-Wortzahl, keine exakte Vorhersage der gerenderten Audiolänge.
WORDS_PER_MINUTE = 150

# case-basierte Templates (case/character_knowledge pro Rolle UND — bei soap_opera —
# pro Thread) erzeugen pro Section um ein Vielfaches mehr JSON als narration/
# language_course, siehe SERIES_REPAIR_PROMPT-Umgebung. Nur für diese lohnt sich der
# Vorab-Größencheck in main() (episodes * minutes >= BATCH_THRESHOLD_EPISODE_MINUTES).
CASE_BASED_TEMPLATES = {"crime_drama", "soap_opera"}
# In der Praxis beobachtet: 10 Episoden x 35 Min. (=350) bei soap_opera scheiterte im
# Ein-Schuss-Modus zuverlässig in allen 3 Versuchen (Antwort wurde vom Modell selbst
# abgebrochen, "continuing in the next reply" — es gibt aber keine nächste Antwort bei
# einem einzelnen '-p'-Aufruf). Der Default 3 x 35 (=105) lief unauffällig. Grob in der
# Mitte gewählt, bis mehr Datenpunkte eine genauere Kalibrierung erlauben.
BATCH_THRESHOLD_EPISODE_MINUTES = 200


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

    return template_text + topic


def compute_timeout(episode_count: int) -> int:
    """Skaliert das Timeout pro Claude-Aufruf mit der Episodenzahl. Eine
    10-Episoden-Soap-Opera mit mehreren parallelen Handlungssträngen pro
    Episode erzeugt um Größenordnungen mehr strukturiertes JSON als eine
    3-Episoden-Anthologie — ein fixes Timeout wartet bei kleinen Serien
    unnötig lange und bricht bei großen zu früh ab. Nach oben gedeckelt,
    damit ein wirklich hängender Prozess nicht unbegrenzt blockiert."""
    return min(1800, max(TIMEOUT_SECONDS, 120 * episode_count))


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


def generate_with_retry(prompt: str, model: str, episode_count: int):
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

        if not errors:
            return data, warnings

        if fallback_safe and (best is None or badness < best[0]):
            best = (badness, data, warnings)

        print(f"⚠️  Versuch {attempt} abgelehnt ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"  - {e}")
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


def build_skeleton_prompt(creator_prompt: str, episode_count: int) -> str:
    """Für Phase 1 von generate_series_batched(): hängt an den (bereits vollständig
    substituierten) Creator-Prompt eine Zusatzanweisung an, die JEDEN Episode-Eintrag auf
    figure+theme reduziert — kein sections/section_words/case. Das allein macht die Antwort
    bei einer großen Serie schon um ein Vielfaches kleiner, da sections/case den Großteil des
    Volumens ausmachen."""
    return creator_prompt + (
        f"\n\nIMPORTANT — OUTPUT SIZE FOR THIS RESPONSE: only the SERIES SKELETON is needed "
        f"now, not full episodes (they get written individually in a later step, you will see "
        f"this exact plan again then). Output the complete JSON object with every top-level "
        f"field exactly as specified above (series_title, format, voices/locations/course/"
        f"series_outro as applicable), and exactly {episode_count} entries in \"episodes\", "
        f"each containing ONLY \"figure\" and \"theme\" (a one-sentence compass of what this "
        f"episode covers, including which case/thread(s) it involves if applicable) — omit "
        f"\"sections\", \"section_words\", \"section_locations\", and \"case\" entirely for now."
    )


def validate_skeleton(data, episode_count: int) -> list:
    """Leichtgewichtige Validierung für die Skeleton-Phase — KEIN config.validate_data(),
    das würde 'sections'/'case' pro Episode verlangen, die im Skeleton bewusst fehlen."""
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
    return errors


def generate_skeleton_with_retry(creator_prompt: str, episode_count: int, model: str):
    """Phase 1 von generate_series_batched(): dieselbe Retry-mit-Feedback-Schleife wie
    generate_with_retry(), aber für das leichtgewichtige Skeleton statt der vollen Serie —
    kein Best-Effort-Fallback nötig, ein Skeleton ist entweder brauchbar oder nicht, es gibt
    keine sinnvolle 'am wenigsten schlechte' Zwischenstufe wie bei einer falschen
    Episodenzahl. Gibt das Skeleton-dict zurück, oder None nach MAX_ATTEMPTS Fehlschlägen."""
    prompt = build_skeleton_prompt(creator_prompt, episode_count)
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
            errors = validate_skeleton(data, episode_count)

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
"""


def compute_batch_timeout(batch_size: int) -> int:
    """Wie compute_timeout(), aber für einen einzelnen Episoden-Batch statt die ganze Serie —
    kleinerer Floor, ein Batch enthält nur wenige Episoden."""
    return min(1200, max(300, 120 * batch_size))


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
    aus dem Skeleton übernommenen Top-Level-Feldern, nicht an den Episodeninhalten)."""
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
        else:
            candidate = json.loads(json.dumps(skeleton))  # billige tiefe Kopie
            candidate["episodes"] = batch_episodes
            errors, _warnings = config.validate_data(candidate)

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
        )

    return None


def generate_series_batched(creator_prompt: str, episode_count: int, model: str):
    """Rettungsweg, wenn generate_with_retry() den kompletten Ein-Schuss-Aufruf nicht
    hinbekommt (typischerweise: eine große soap_opera-Serie mit vielen Episoden/Threads
    erzeugt so viel strukturiertes JSON, dass die Antwort mitten drin abgeschnitten wird).
    creator_prompt ist hier bereits derselbe vollständig substituierte Prompt, der auch im
    Ein-Schuss-Versuch verwendet wurde (FIGURE_HISTORY/EPISODE_COUNT/SECTION_COUNT/
    LOCATION_COUNT schon eingesetzt, Topic angehängt) — wird hier NICHT nochmal neu gebaut,
    um figure_history.json nicht zweimal zu lesen.

    Statt der ganzen Serie in EINEM Call wird zuerst nur ein leichtgewichtiges Skeleton
    generiert (series_title/format/voices/locations/course + figure+theme pro Episode, ohne
    sections/case), danach die vollen Episode-Objekte in Gruppen von BATCH_SIZE — jeder Batch
    sieht das komplette Skeleton (alle Episoden-Themen) für Kontinuität, schreibt aber nur
    seine eigene Gruppe aus.

    Gibt (data, warnings) wie generate_with_retry() zurück, oder (None, []) wenn schon das
    Skeleton scheitert oder irgendein Batch nach MAX_ATTEMPTS nicht zustande kommt — die
    bereits erfolgreich generierten Episoden werden dann verworfen statt eine Serie mit
    Lücken zu erzeugen."""
    print("  Phase 1/2: Skeleton (Cast, Orte, Format, Episoden-Themen) ...")
    skeleton = generate_skeleton_with_retry(creator_prompt, episode_count, model)
    if skeleton is None:
        print("  ❌  Skeleton-Generierung gescheitert.")
        return None, []

    batches = [(i, min(i + BATCH_SIZE - 1, episode_count))
               for i in range(1, episode_count + 1, BATCH_SIZE)]
    print(f"  Phase 2/2: {len(batches)} Episoden-Batch(es) à bis zu {BATCH_SIZE} Episoden ...")

    full_episodes = []
    for start, end in batches:
        print(f"    Episoden {start}-{end}/{episode_count} ...")
        batch_episodes = generate_batch_with_retry(creator_prompt, skeleton, start, end, model)
        if batch_episodes is None:
            print(f"  ❌  Episoden {start}-{end} nach {MAX_ATTEMPTS} Versuchen gescheitert.")
            return None, []
        full_episodes.extend(batch_episodes)

    data = skeleton
    data["episodes"] = full_episodes
    errors, warnings = config.validate_data(data)
    if errors:
        # Sollte nach den Einzel-Batch-Validierungen eigentlich nicht mehr auftreten — reiner
        # Sicherheitsnetz-Check auf dem zusammengesetzten Gesamtdokument, analog zu
        # repair_series(), das seine Korrektur auch immer neu validiert statt zu vertrauen.
        print(f"  ❌  Zusammengesetzte Serie ungültig ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"    - {e}")
        return None, []
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
{{"issues": ["one short, specific sentence per real problem — empty list if none"]}}

Do not invent nitpicks: only report problems a listener or producer would actually
notice. An empty list is a perfectly good answer.

episodes.json:
"""


def review_series(data: dict, model: str) -> list:
    """Inhalts-QA nach bestandener Struktur-Validierung: ein zweiter
    Claude-Aufruf prüft Spoiler-Leaks, Widersprüche, Akzent-Casting und
    Episoden-Überschneidungen. Nur Warnungen — blockiert nie (bei Fehlern
    im Review-Aufruf selbst wird still übersprungen, die Serie ist ja
    strukturell gültig)."""
    prompt = REVIEW_PROMPT.format(template=data.get("template", "narration")) \
        + json.dumps(data, ensure_ascii=False, indent=2)
    timeout = compute_timeout(len(data.get("episodes", [])))
    argv = ["claude", "-p", prompt, "--output-format", "text", "--model", model, "--tools", ""]
    try:
        result = run_claude_process(argv, timeout, "Inhalts-Review")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("⚠️  Inhalts-Review übersprungen (Claude-Aufruf fehlgeschlagen).")
        return []
    if result.returncode != 0:
        print("⚠️  Inhalts-Review übersprungen (Claude-Aufruf fehlgeschlagen).")
        return []
    parsed = parse_json_response(result.stdout.strip())
    if not isinstance(parsed, dict) or not isinstance(parsed.get("issues"), list):
        print("⚠️  Inhalts-Review übersprungen (Antwort nicht auswertbar).")
        return []
    return [str(i) for i in parsed["issues"]]


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


def repair_series(data: dict, issues: list, model: str, episode_count: int) -> Optional[dict]:
    """Lässt Claude die komplette episodes.json neu ausgeben mit dem Auftrag, NUR die von
    review_series() gemeldeten Probleme zu beheben — das Gegenstück zu repair_part() beim
    Skript-Writer, aber auf Dokumentebene statt Part-Ebene: episodes.json hat (anders als ein
    Skript mit '--- PART N ---'-Markern) keine unabhängig adressierbaren Text-Blöcke, ein
    einzelnes Feld gezielt zu patchen wäre also fragiler als das ganze (vergleichsweise kleine)
    Objekt neu validiert auszugeben.

    Läuft wie generate_with_retry() mit Fehler-Feedback bei ungültiger Struktur, hier aber nur
    für die Reparatur selbst (MAX_ATTEMPTS Versuche). Gibt None zurück, wenn keine strukturell
    gültige Korrektur zustande kam — der Aufrufer behält dann die ursprüngliche data statt eine
    kaputte Reparatur zu übernehmen."""
    issues_block = "\n".join(f"- {i}" for i in issues)
    base_prompt = SERIES_REPAIR_PROMPT.format(
        issues_block=issues_block,
        current_json=json.dumps(data, ensure_ascii=False, indent=2),
    )
    timeout = compute_timeout(episode_count)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        raw = call_claude(base_prompt + feedback, model, timeout=timeout,
                          label=f"Serie reparieren (Versuch {attempt}/{MAX_ATTEMPTS})")
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
        feedback = (
            "\n\nIMPORTANT — your previous correction was REJECTED for these problems:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix ALL of them and output the complete corrected JSON again (full object, not "
              "a diff), still only touching what's needed for the originally flagged problems."
        )

    return None


def unique_slug(title: str) -> str:
    """Slug aus dem Serientitel; bei Kollision mit vorhandener Serie wird
    durchnummeriert statt die bestehende Serie zu überschreiben."""
    base = paths.slugify(title)
    slug = base
    counter = 2
    while slug in paths.list_series():
        slug = f"{base}_{counter}"
        counter += 1
    return slug


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

    if skip_one_shot:
        print(f"🧩  {args.episodes} Episoden × {args.minutes:g} Min. bei '{args.template}' — "
              f"das sprengt erfahrungsgemäß eine einzelne Antwort (siehe BATCH_THRESHOLD_"
              f"EPISODE_MINUTES). Gehe direkt auf Batch-Generierung, ohne die Zeit für einen "
              f"praktisch aussichtslosen Ein-Schuss-Versuch erst zu verschwenden ...")
        data, warnings = generate_series_batched(prompt, args.episodes, config.DEFAULTS["model"])
        if data is None:
            print("❌  Batch-Generierung ist gescheitert — Abbruch.")
            sys.exit(1)
    else:
        data, warnings = generate_with_retry(prompt, config.DEFAULTS["model"], args.episodes)
        if data is None:
            print("🧩  Wechsle zu Batch-Generierung (Grundgerüst zuerst, dann Episoden in kleinen "
                  "Gruppen) — vermeidet, dass eine große Serie in einer einzigen, zu langen "
                  "Antwort abgeschnitten wird ...")
            data, warnings = generate_series_batched(prompt, args.episodes, config.DEFAULTS["model"])
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

    if not args.no_review:
        print("🔎  Inhalts-Review (Spoiler-Leaks, Widersprüche, Akzent-Casting, Überschneidungen) ...")
        issues = review_series(data, config.DEFAULTS["model"])

        if issues and args.fix:
            print(f"🔧  {len(issues)} Hinweis(e) — versuche automatische Reparatur ...")
            fixed = repair_series(data, issues, config.DEFAULTS["model"], args.episodes)
            if fixed is not None:
                data = fixed
                data.setdefault("template", args.template)
                print("  Review erneut, um den Fix zu bestätigen ...")
                reviewed_again = review_series(data, config.DEFAULTS["model"])
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
                print(f"  - {i}")
        else:
            print("✅  Inhalts-Review: keine Auffälligkeiten.")

    slug = unique_slug(data.get("series_title", "serie"))
    series = paths.Series(slug)
    scaffolded = workspace.scaffold_workspace(series, data, args.template)
    with open(series.episodes_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    paths.write_latest(slug)
    if scaffolded:
        print(f"    Workspace-Struktur angelegt ({len(scaffolded)} Kontext-/Referenz-Dateien, "
              f"Stage-Verträge unter stages/*/CONTEXT.md)")

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
