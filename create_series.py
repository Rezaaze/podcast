#!/usr/bin/env python3
"""
Erzeugt automatisch eine komplett neue episodes.json für eine neue
Podcast-Serie via Claude CLI — automatisiert das bisher manuelle
Copy-Paste von EPISODES_CREATOR_PROMPT.md in eine neue Konversation.

Bezieht figure_history.json ein, damit keine Figur aus früheren Serien
wiederverwendet wird (dieselbe Historie, die generate_episode.py auch
nach jeder fertigen Episode aktualisiert).

Archiviert automatisch alle Artefakte der ALTEN Serie (episodes.json,
figur*.txt, figur*_META.txt, ANTHOLOGY_META.txt, podcast_output/) nach
archive/<alter_serientitel>_<timestamp>/ — nichts wird gelöscht, nur
verschoben, damit die neue Serie nicht mit alten Dateien kollidiert
(z.B. Chunk-Checkpoints oder "schon vorhanden"-Skips, die sonst fälschlich
für die neue Serie gelten würden).

Voraussetzung:
  Claude Code installiert und eingeloggt ('claude' im Terminal, /login)

Nutzung:
  python3 create_series.py "Kurzbeschreibung der neuen Serie/des Themas"

Danach:
  python3 generate_episode.py all
  (generiert automatisch alle Skripte, vertont sie, merged zur Anthologie
   und erzeugt die Anthologie-Metadaten — alles in einem Rutsch)
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

import generate_episode as ge

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "EPISODES_CREATOR_PROMPT.md")
FIGURE_HISTORY_FILE = os.path.join(SCRIPT_DIR, "figure_history.json")
EPISODES_FILE = os.path.join(SCRIPT_DIR, "episodes.json")
ARCHIVE_DIR = os.path.join(SCRIPT_DIR, "archive")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "podcast_output")

TIMEOUT_SECONDS = 300
DEFAULT_EPISODE_COUNT = 3


def load_prompt_template() -> str:
    with open(PROMPT_TEMPLATE_FILE, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(topic: str, episode_count: int) -> str:
    """Baut den vollen Prompt aus EPISODES_CREATOR_PROMPT.md, mit der echten
    Figuren-Historie und der festen Episodenanzahl eingefügt (statt der
    Platzhalter-Anweisung, sie manuell einzufügen) und dem Thema am Ende
    angehängt."""
    template = load_prompt_template()

    history = ge.load_figure_history()
    used = "\n".join(f"- {h['figure']} (Serie: {h['series_title']})" for h in history) or "(noch keine)"

    template = re.sub(
        r"ALREADY-USED FIGURES.*?(?=\n\nSTRICT OUTPUT RULES)",
        f"ALREADY-USED FIGURES (do not reuse any of these — pick different "
        f"people/subjects for every episode, even if the new series covers "
        f"a similar theme):\n{used}",
        template,
        flags=re.DOTALL,
    )
    template = template.replace("{{EPISODE_COUNT}}", str(episode_count))

    return template + topic


def call_claude(prompt: str, model: str) -> str:
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text", "--model", model, "--tools", ""],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        print("❌  'claude' nicht gefunden → Claude Code installieren.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"❌  Timeout nach {TIMEOUT_SECONDS}s.")
        sys.exit(1)

    if result.returncode != 0:
        output = (result.stderr.strip() or result.stdout.strip())[:500]
        if "401" in output or "authentication" in output.lower():
            print("❌  Nicht eingeloggt → 'claude' im Terminal öffnen und /login ausführen.")
        else:
            print(f"❌  Claude-CLI-Fehler (exit {result.returncode}): {output}")
        sys.exit(1)

    return result.stdout.strip()


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        print(f"❌  Antwort war kein valides JSON:\n---\n{raw}\n---")
        sys.exit(1)


def archive_old_series():
    """Verschiebt alle Artefakte der aktuellen Serie nach archive/ — nichts
    wird gelöscht. Läuft nur, wenn tatsächlich eine alte episodes.json
    existiert (sonst ist es der allererste Lauf, nichts zu archivieren)."""
    if not os.path.exists(EPISODES_FILE):
        return

    with open(EPISODES_FILE, "r", encoding="utf-8") as f:
        try:
            old_data = json.load(f)
        except json.JSONDecodeError:
            old_data = {}
    old_title = old_data.get("series_title", "unbekannte_serie")
    prefix = old_data.get("output_prefix", "figur")

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", old_title).strip("_").lower()[:50]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(ARCHIVE_DIR, f"{slug}_{ts}")
    os.makedirs(dest, exist_ok=True)

    moved = []

    def move(path, name=None):
        if os.path.exists(path):
            target = os.path.join(dest, name or os.path.basename(path))
            shutil.move(path, target)
            moved.append(os.path.basename(path))

    move(EPISODES_FILE)
    move(os.path.join(SCRIPT_DIR, "ANTHOLOGY_META.txt"))
    for f in os.listdir(SCRIPT_DIR):
        if re.fullmatch(rf"{re.escape(prefix)}\d+(_META)?\.txt", f):
            move(os.path.join(SCRIPT_DIR, f))

    if os.path.isdir(OUTPUT_DIR):
        move(OUTPUT_DIR, name="podcast_output")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"📦  Alte Serie \"{old_title}\" archiviert nach: {dest}")
    print(f"    Verschoben: {', '.join(moved) if moved else '(nichts gefunden)'}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Neue Podcast-Serie via Claude CLI erzeugen.")
    parser.add_argument("topic", help="Thema/Konzept der neuen Serie")
    parser.add_argument("--episodes", type=int, default=DEFAULT_EPISODE_COUNT,
                         help=f"Anzahl Episoden (Standard: {DEFAULT_EPISODE_COUNT})")
    args = parser.parse_args()

    print(f"🧠  Erzeuge neue Serie ({args.episodes} Episoden) zum Thema: \"{args.topic}\" ...")
    prompt = build_prompt(args.topic, args.episodes)
    raw = call_claude(prompt, model=ge.DEFAULTS["model"])
    data = parse_json_response(raw)

    errors, warnings = ge.validate_data(data)
    for w in warnings:
        print(f"WARNUNG: {w}")
    if errors:
        print(f"❌  Generierte episodes.json ist ungültig ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # Absicherung: Inhalt soll IMMER Englisch sein, unabhängig von der Sprache
    # des Themen-Prompts (siehe LANGUAGE RULE in EPISODES_CREATOR_PROMPT.md).
    # Diese Prüfung fängt ab, falls das Modell die Regel trotzdem ignoriert.
    if data.get("language", "").strip().lower() not in ("english", "englisch"):
        print(f"⚠️  WARNUNG: 'language' ist '{data.get('language')}', nicht Englisch — "
              f"die generierte Serie widerspricht der Englisch-Regel. Bitte prüfen, "
              f"ggf. neu generieren.")

    actual_count = len(data.get("episodes", []))
    if actual_count != args.episodes:
        print(f"⚠️  WARNUNG: {actual_count} Episode(n) generiert, angefordert waren "
              f"{args.episodes} — bitte prüfen, ggf. neu generieren.")

    archive_old_series()

    with open(EPISODES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    figures = ", ".join(ep["figure"] for ep in data["episodes"])
    print(f"\n✅  Neue Serie geschrieben: \"{data['series_title']}\"")
    print(f"    {len(data['episodes'])} Episode(n): {figures}")
    print(f"\nNächster Schritt:")
    print(f"  python3 generate_episode.py all")
    print(f"  (generiert alle Skripte, vertont sie, merged zur Anthologie und")
    print(f"   erzeugt die Anthologie-Metadaten — vollautomatisch)")


if __name__ == "__main__":
    main()
