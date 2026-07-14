#!/usr/bin/env python3
"""Erzeugt EIN Cover-Bild für eine Serie und kopiert es auf die externe
Backup-Platte — einmalig pro Serie, kein per-Episode-Artefakt wie Porträts
oder Location-Bilder.

Verwendung:
  python3 cover_art.py                    # aktuelle Serie (series/LATEST)
  python3 cover_art.py --series thin_walls
  python3 cover_art.py --force             # vorhandenes Cover neu generieren
  python3 cover_art.py --no-copy           # nicht auf die externe Platte kopieren

Braucht OPENAI_API_KEY (anders als character_prompts.py/location_prompts.py
gibt es hier keinen Text-Prompt-only-Fallback ohne Key — ein Cover ohne Bild
ist kein sinnvolles Zwischenergebnis).

1024×1024 ist die größte quadratische Größe, die gpt-image-1-mini anbietet —
unter Apple Podcasts/Spotify-Minimum (1400×1400), aber ohne zusätzliche
Bildbearbeitung (Pillow bräuchte ein venv, siehe CLAUDE.md: fabrik/writing/
muss ohne venv laufen) nicht hochskalierbar.

Braucht kein .venv — nur die Claude CLI (wie character_prompts.py).
"""

import argparse
import os
import re
import shutil
import sys
import time

from fabrik.core import config, paths
from fabrik.writing import image_backends
from fabrik.writing.script_writer import call_claude, MAX_RETRIES, RETRY_DELAY

COVER_FILENAME = "cover.png"

# Manuell bestätigter Zielort für den automatischen Kopiervorgang. Auf der
# Platte pflegt der Nutzer pro Serie einen Ordner "Podcasts/<Serientitel>/"
# (mit den Episoden darin) — das Cover gehört DORT hinein, nicht flach ins
# Wurzelverzeichnis (dort lagen früher fälschlich kopierte Cover wie
# "Vanishing Signal.png"). Kein Absturz, falls die Platte beim Lauf nicht
# eingesteckt ist — nur eine Warnung, siehe unten.
EXTERNAL_DRIVE_ROOT = "/Volumes/NO NAME"
EXTERNAL_PODCASTS_SUBDIR = "Podcasts"

_ILLEGAL_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|]')


def cover_file(series):
    return os.path.join(series.visuals_dir, COVER_FILENAME)


def sanitize_filename(name):
    return _ILLEGAL_FILENAME_CHARS.sub("", name).strip()


def build_prompt(data):
    series_title = data.get("series_title", "")
    language = data.get("language", "German")
    writer_persona = data.get("writer_persona", "")
    style_guidelines = data.get("style_guidelines", "")
    template = data.get("template", data.get("mode", "narration"))

    return (
        f"\"{series_title}\" is an audio drama podcast (dialogue language: "
        f"{language}, format: {template}). Writer's persona/voice: "
        f"{writer_persona}. Series tone/style notes: {style_guidelines}\n\n"
        f"Write ONE image-generation prompt for this podcast's COVER ART — "
        f"the square thumbnail listeners see in their podcast app before "
        f"pressing play (in English — image models work best with English "
        f"prompts).\n\n"
        f"Requirements:\n"
        f"- Style: masterpiece, best quality, painted lo-fi animation style, "
        f"hand-drawn texture, warm muted color palette, cinematic — the same "
        f"visual language as this show's character portraits and location "
        f"art, so the cover feels part of the same world, not a separate "
        f"marketing graphic.\n"
        f"- Find the ONE image that captures this specific show's premise or "
        f"central tension in a single symbolic frame — not a generic genre "
        f"mood board. The one object, gesture, or moment that IS this story "
        f"if you saw it on a shelf.\n"
        f"- Must read clearly as a small thumbnail: one strong, clear focal "
        f"point, bold silhouette and composition — not a busy wide scene "
        f"full of small detail that disappears at thumbnail size.\n"
        f"- The show's title, \"{series_title}\", must appear as tasteful "
        f"typography integrated into the composition (movie-poster style) — "
        f"placed where it stays legible at thumbnail size (e.g. lower third, "
        f"against a calm area of the image, not over busy detail), in a "
        f"typeface that matches the hand-painted lo-fi mood (a clean serif "
        f"or display face, not a generic sans-serif). Spell it EXACTLY as "
        f"given, nothing added or changed. This is the ONLY text allowed in "
        f"the image — no other words, letters, or logos anywhere else.\n"
        f"- NO close-up human faces (AI-generated faces read as uncanny at "
        f"thumbnail size) — implied presence, silhouette, or a symbolic "
        f"object instead.\n"
        f"- One paragraph, no camera jargon lists, no numbered options.\n\n"
        f"Answer with EXACTLY this and nothing else — no preamble, no "
        f"markdown, just the prompt text itself."
    )


def copy_to_external_drive(src_path, series_title):
    if not os.path.isdir(EXTERNAL_DRIVE_ROOT):
        print(f"⚠️  Externe Platte nicht gefunden ({EXTERNAL_DRIVE_ROOT}) — Cover NICHT "
              f"kopiert. Platte einstecken und diesen Befehl erneut ausführen (das "
              f"vorhandene Cover wird dabei nur kopiert, nicht neu generiert).")
        return

    safe_title = sanitize_filename(series_title) or "cover"
    series_folder = os.path.join(EXTERNAL_DRIVE_ROOT, EXTERNAL_PODCASTS_SUBDIR, safe_title)
    os.makedirs(series_folder, exist_ok=True)
    dest_path = os.path.join(series_folder, f"{safe_title}.png")
    shutil.copy2(src_path, dest_path)
    print(f"Kopiert nach: {dest_path}")


def main():
    parser = argparse.ArgumentParser(description="Cover-Art für eine Serie generieren")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandenes Cover neu generieren")
    parser.add_argument("--no-copy", action="store_true",
                        help="Nicht auf die externe Platte kopieren")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)

    out_path = cover_file(series)
    series_title = data.get("series_title", series.slug)

    if os.path.exists(out_path) and not args.force:
        print(f"Cover existiert bereits: {out_path}")
        print("Neu generieren mit --force.")
        if not args.no_copy:
            copy_to_external_drive(out_path, series_title)
        return

    if not image_backends.api_key_available():
        print("FEHLER: OPENAI_API_KEY nicht gesetzt — Cover-Art braucht die Bild-API, "
              "anders als bei Porträts/Locations gibt es hier keinen Text-Prompt-Fallback.")
        sys.exit(1)

    model = data.get("generation", {}).get("model", config.DEFAULTS["model"])
    print(f"Serie: {series.slug} — generiere Cover-Prompt (Modell: {model}) ...")

    prompt_text = None
    for attempt in range(1, MAX_RETRIES + 1):
        output = call_claude(build_prompt(data), model)
        if output and output.strip():
            prompt_text = output.strip()
            break
        print(f"Versuch {attempt}/{MAX_RETRIES}: keine Ausgabe.")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    if not prompt_text:
        print("FEHLER: Cover-Prompt konnte nicht erzeugt werden — erneut starten.")
        sys.exit(1)

    print("Erzeuge Cover-Bild (gpt-image-1-mini, 1024x1024) ...")
    try:
        image_backends.save_image(prompt_text, out_path)
    except RuntimeError as exc:
        print(f"FEHLER: {exc}")
        sys.exit(1)

    print(f"Gespeichert: {out_path}")
    if not args.no_copy:
        copy_to_external_drive(out_path, series_title)


if __name__ == "__main__":
    main()
