#!/usr/bin/env python3
"""
Importiert bereits fertigen Text (alte Romane/Geschichten mit bereits
geschriebenen Szenen) als neue Serie — Gegenstück zu create_series.py:
Claude erfindet hier NICHTS inhaltlich, nur Titel/Thema-Metadaten werden
per Claude aus dem Text zusammengefasst. Der eigentliche Skripttext wird
1:1 aus der Quelle übernommen und deterministisch (ohne Claude) in
--- PART k ----Chunks aufgeteilt, exakt im Format, das
podcast_maker.py/batch.py bereits verstehen.

Quelle kann sein:
  - ein Ordner: jede Datei darin (alphabetisch sortiert) wird eine Episode,
    Inhalt wird 1:1 übernommen
  - eine einzelne Datei: wird automatisch in Episoden zerlegt — zuerst
    Kapitel-Erkennung per Regex ("Chapter 1", "Kapitel 1", Markdown-Header,
    "1. ..."), bei keinem Treffer Fallback nach Wortzahl (--words-per-episode)

Nur mode "narration" wird unterstützt (siehe Plan — drama-Modus-Adaption
mit Dialog→Sprecher-Tags ist bewusst nicht Teil dieser ersten Version).

Voraussetzung:
  Claude Code installiert und eingeloggt ('claude' im Terminal, /login),
  außer bei --no-summary.

Nutzung (vom Projekt-Root aus):
  python3 -m fabrik.cli.import_story roman.txt "Der alte Roman"
  python3 -m fabrik.cli.import_story kapitel_ordner/ "Serie aus Kapiteln"
  python3 -m fabrik.cli.import_story roman.txt "Titel" --split-on "^Kapitel \\d+"

Danach:
  python3 -m fabrik.cli.generate_episode all
  (überspringt importierte Episoden automatisch — vertont sie aber ganz normal)
"""

import argparse
import json
import os
import re
import sys

from fabrik.core import config, history, paths, textproc, workspace
from fabrik.writing import script_writer

DEFAULT_WORDS_PER_EPISODE = 4000
DEFAULT_WORDS_PER_PART_MAX = 520
DEFAULT_PARTS_PER_SECTION = 2

# Kapitelanfänge, die zur Auto-Erkennung einer einzelnen langen Quelldatei
# ausprobiert werden (der erste Treffer mit >= 2 Vorkommen gewinnt).
_CHAPTER_PATTERNS = [
    re.compile(r'^\s*(?:chapter|kapitel)\s+\S+.*$', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*#{1,3}\s+\S+.*$', re.MULTILINE),           # Markdown-Header
    re.compile(r'^\s*\d+[.)]\s+\S+.*$', re.MULTILINE),          # "1. Titel" / "1) Titel"
]


def split_into_episodes_from_file(text, split_on, words_per_episode):
    """Liefert Liste von (Titel-Hinweis, Volltext) für eine einzelne lange
    Quelldatei — per erkanntem Kapitelmarker, oder als Fallback nach
    Wortzahl entlang von Absatzgrenzen (textproc.chunk_prose_by_words)."""
    text = text.strip()
    pattern = re.compile(split_on, re.MULTILINE) if split_on else None

    if pattern is None:
        for candidate in _CHAPTER_PATTERNS:
            if len(candidate.findall(text)) >= 2:
                pattern = candidate
                break

    if pattern:
        matches = list(pattern.finditer(text))
        episodes = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                episodes.append((body.splitlines()[0].strip()[:80], body))
        return episodes

    chunks = textproc.chunk_prose_by_words(text, words_per_episode, mode="narration")
    return [(f"Part {i+1}", chunk) for i, chunk in enumerate(chunks)]


def load_sources(source_path, split_on, words_per_episode):
    """Liefert Liste von (Titel-Hinweis, Volltext) in Reihenfolge, egal ob
    die Quelle ein Ordner (eine Datei pro Episode) oder eine einzelne lange
    Datei (automatisch zerlegt) ist."""
    if os.path.isdir(source_path):
        files = sorted(
            f for f in os.listdir(source_path)
            if os.path.isfile(os.path.join(source_path, f)) and not f.startswith(".")
        )
        result = []
        for f in files:
            with open(os.path.join(source_path, f), "r", encoding="utf-8") as fh:
                body = fh.read().strip()
            if body:
                result.append((os.path.splitext(f)[0], body))
        return result

    if os.path.isfile(source_path):
        with open(source_path, "r", encoding="utf-8") as fh:
            text = fh.read()
        return split_into_episodes_from_file(text, split_on, words_per_episode)

    print(f"FEHLER: Quelle nicht gefunden: {source_path}")
    sys.exit(1)


def build_section_titles(num_chunks, parts_per_section):
    """Rein kosmetische Section-Titel für die episodes.json-/Status-Anzeige
    ('Part 1-2', 'Part 3-4', ...) — treiben bei importierten Episoden keine
    Generierung an, anders als bei generativen Serien."""
    titles = []
    for first in range(1, num_chunks + 1, parts_per_section):
        last = min(first + parts_per_section - 1, num_chunks)
        titles.append(f"Part {first}" if first == last else f"Part {first}–{last}")
    return titles


def main():
    parser = argparse.ArgumentParser(
        description="Bestehenden Text (Ordner oder Datei) als neue Serie importieren, ohne Claude Inhalt erfinden zu lassen."
    )
    parser.add_argument("source", help="Ordner mit einer Datei pro Episode, oder eine einzelne lange Textdatei")
    parser.add_argument("series_title", help="Titel der neuen Serie")
    parser.add_argument("--template", default="narration",
                        help="Template-Ordner unter templates/ (Standard: narration)")
    parser.add_argument("--words-per-part-max", type=int, default=DEFAULT_WORDS_PER_PART_MAX,
                        help=f"Maximale Wörter/Einheiten pro PART-Chunk (Standard: {DEFAULT_WORDS_PER_PART_MAX})")
    parser.add_argument("--parts-per-section", type=int, default=DEFAULT_PARTS_PER_SECTION,
                        help=f"Wie viele PARTs kosmetisch zu einer Section gruppiert werden (Standard: {DEFAULT_PARTS_PER_SECTION})")
    parser.add_argument("--split-on", default=None, metavar="REGEX",
                        help="Regex für Kapitelanfänge bei einer einzelnen Quelldatei (überschreibt die Auto-Erkennung)")
    parser.add_argument("--words-per-episode", type=int, default=DEFAULT_WORDS_PER_EPISODE,
                        help=f"Fallback-Episodengröße, wenn bei einer einzelnen Quelldatei keine Kapitelmarker gefunden werden (Standard: {DEFAULT_WORDS_PER_EPISODE})")
    parser.add_argument("--language", default=config.DEFAULTS["language"],
                        help="Sprache der Metadaten-Zusammenfassung (Standard: 'English')")
    parser.add_argument("--no-summary", action="store_true",
                        help="Keine Claude-Metadaten-Zusammenfassung — Episodentitel kommt 1:1 aus Dateiname/Kapitelzeile, kein 'claude'-Login nötig")
    args = parser.parse_args()

    if not os.path.isdir(paths.template_dir(args.template)):
        print(f"FEHLER: templates/{args.template}/ existiert nicht.")
        sys.exit(1)

    print(f"📖  Lese Quelle: {args.source}")
    sources = load_sources(args.source, args.split_on, args.words_per_episode)
    if not sources:
        print("FEHLER: keine Episode mit Inhalt gefunden.")
        sys.exit(1)
    print(f"   → {len(sources)} Episode(n) erkannt.")

    persona = "an experienced audiobook producer adapting existing prose for podcast listeners"
    slug = paths.unique_slug(args.series_title)
    series = paths.Series(slug).ensure_dirs()

    episodes = []
    for i, (title_hint, body) in enumerate(sources):
        num = i + 1
        print(f"\nEpisode {num}/{len(sources)}: {title_hint}")

        chunks = textproc.chunk_prose_by_words(body, args.words_per_part_max, mode="narration")
        if not chunks:
            print("  ⚠️  Übersprungen — kein Inhalt.")
            continue

        figure, theme = title_hint, f"Adapted from the source material (\"{title_hint}\")."
        if not args.no_summary:
            summary = script_writer.summarize_source_episode(
                body, persona, args.language, config.DEFAULTS["light_model"]
            )
            if summary:
                figure, theme = summary
            else:
                print("  ⚠️  Metadaten-Zusammenfassung fehlgeschlagen — nutze Dateiname/Kapitelzeile als Titel.")

        script_file = series.script_file("ep", num)
        with open(script_file, "w", encoding="utf-8") as f:
            for j, chunk in enumerate(chunks):
                f.write(f"--- PART {j+1} ---\n\n{chunk}\n\n")

        episodes.append({
            "figure": figure,
            "theme": theme,
            "intro_note": "",
            "outro_note": "",
            "sections": build_section_titles(len(chunks), args.parts_per_section),
            "source": "imported",
        })
        history.record_figure(figure, args.series_title)
        print(f"  ✓ {len(chunks)} Part(s) → {os.path.basename(script_file)} (\"{figure}\")")

    if not episodes:
        print("FEHLER: keine Episode enthielt Inhalt.")
        sys.exit(1)

    data = {
        "series_title": args.series_title,
        "language": args.language,
        "writer_persona": persona,
        "mode": "narration",
        "template": args.template,
        "format": {
            "parts_per_section": args.parts_per_section,
            "words_per_part_target": f"up to {args.words_per_part_max}",
            "words_per_part_min": 1,
            "words_per_part_max": args.words_per_part_max,
        },
        "generation": {"model": config.DEFAULTS["model"]},
        "audio": {
            "api_url": "http://127.0.0.1:42003",
            "voice": "MyVoice",
            "default_style": "Read like an audiobook narrator, calm, steady, and engaging",
            "target_lufs": -16.0,
            "pause_between_chunks_ms": 250,
            "pause_between_parts_ms": 4000,
            "pause_between_episodes_ms": 6000,
        },
        "output_prefix": "ep",
        "episodes": episodes,
    }

    errors, warnings = config.validate_data(data)
    for w in warnings:
        print(f"WARNUNG: {w}")
    if errors:
        print(f"❌  episodes.json ist ungültig ({len(errors)} Problem(e)):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    workspace.scaffold_workspace(series, data, args.template)
    with open(series.episodes_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    paths.write_latest(slug)

    print(f"\n✅  Neue Serie importiert: data/series/{slug}/  (\"{args.series_title}\")")
    print(f"    {len(episodes)} Episode(n), Skripte liegen bereits fertig in "
          f"stages/02_scripts/output/.")
    print(f"    data/series/LATEST zeigt jetzt auf '{slug}'.")
    print(f"\n⚠️  audio.voice ist auf den Platzhalter 'MyVoice' gesetzt — in "
          f"data/series/{slug}/episodes.json auf deine tatsächliche Qwen3-TTS-Stimme "
          f"anpassen, bevor du vertonst.")
    print(f"\nNächster Schritt:")
    print(f"  python3 -m fabrik.cli.generate_episode all")
    print(f"  (überspringt die bereits importierten Skripte, vertont sie aber ganz normal)")


if __name__ == "__main__":
    main()
