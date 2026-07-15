#!/usr/bin/env python3
"""Erzeugt Bild-Prompts für die wiederverwendbaren Szenen-Orte einer Serie —
und, falls OPENAI_API_KEY gesetzt ist, gleich die PNGs dazu.

Verwendung:
  python3 location_prompts.py                    # aktuelle Serie (series/LATEST)
  python3 location_prompts.py --series facades
  python3 location_prompts.py --force             # vorhandene Prompts neu generieren
  python3 location_prompts.py --no-images         # nur Prompts, keine Bilder erzeugen

Für jeden Ort aus dem top-level "locations"-Mapping (episodes.json, siehe
episodes[n].section_locations) baut Claude einen Bild-Prompt mit einem für
alle Orte IDENTISCHEN Stil-Block — die Hintergründe sollen wie eine
zusammengehörige Welt aussehen, nicht wie zufällige Einzelbilder.

Ist OPENAI_API_KEY gesetzt (und --no-images nicht angegeben), wird für jeden
Ort sofort ein PNG über gpt-image-1-mini erzeugt (im Querformat, passend als
Video-Hintergrund) und als series/<slug>/locations/<ORT_KEY>.png abgelegt —
ohne Key bleibt es wie bisher bei den Text-Prompts zum manuellen Einfügen bei
einem Bildmodell deiner Wahl. Nützlich für Cover-Kunst, Social-Media-Assets
oder einen eigenen Video-Export, der den Hintergrund anhand der
Location-Timeline (podcast_maker.py/batch.py) wechselt, wenn die Handlung an
diesen Ort springt.

Braucht kein .venv — nur die Claude CLI (wie generate_episode.py); die
Bildgenerierung selbst nutzt nur stdlib (urllib), kein zusätzliches Paket.
"""

import argparse
import os
import re
import sys
import time

from fabrik.core import config, paths
from fabrik.writing import image_backends, location_library
from fabrik.writing.script_writer import call_claude, MAX_RETRIES, RETRY_DELAY

PROMPTS_FILENAME = "PROMPTS.txt"
IMAGE_SIZE = "1536x1024"  # Querformat -- wird als Video-Hintergrund verwendet, kein Bust-Portrait


def locations_dir(series):
    return series.locations_dir


def prompts_file(series):
    return os.path.join(locations_dir(series), PROMPTS_FILENAME)


def collect_locations(data):
    return data.get("locations", {})


def build_prompt(data, locations):
    series_title = data.get("series_title", "")
    language = data.get("language", "German")
    style_guidelines = data.get("style_guidelines", "")

    location_lines = []
    for key, lcfg in locations.items():
        name = lcfg.get("name", key)
        desc = lcfg.get("description", "(keine Beschreibung)")
        location_lines.append(f"- {key}: \"{name}\" — {desc}")
    locations_text = "\n".join(location_lines)

    return (
        f"\"{series_title}\" is an audio drama podcast (dialogue language: "
        f"{language}). Series tone/style notes: {style_guidelines}\n\n"
        f"These are the recurring locations (key: \"display name\" — description):\n{locations_text}\n\n"
        f"I am producing a video version of the podcast: a dark, calm, "
        f"lofi-style ambient loop video. Each location is used as the still "
        f"background for every scene set there, for the whole season. The "
        f"image gets scaled to fill a 16:9 frame and cropped top/bottom to "
        f"fit — nothing essential may sit near the top or bottom edge. Write "
        f"ONE image-generation prompt per location (in English — image "
        f"models work best with English prompts).\n\n"
        f"Requirements for EVERY prompt:\n"
        f"- Start with the exact same shared style-tag prefix for all "
        f"locations, so the backgrounds read as one consistent, believable "
        f"world: \"masterpiece, best quality, painted lo-fi animation style, "
        f"hand-drawn texture, warm muted color palette, cinematic\".\n"
        f"- Give the location ONE dominant, clearly named light source that "
        f"anchors the composition (a lamp, a screen's glow, moonlight through "
        f"a window, a streetlight) — not flat ambient 'moody lighting'. "
        f"Everything else recedes into soft shadow toward the edges of the "
        f"frame, which also keeps the crop-safe center in focus.\n"
        f"- Re-read that location's description above and find the one "
        f"concrete detail in it that actually carries emotional/narrative "
        f"weight for this specific location (often already named there — a "
        f"specific object, a specific light color, a specific small detail "
        f"of absence or presence) — not generic architecture. Make THAT "
        f"detail the literal visual focal point of the composition, rendered "
        f"specifically, not paraphrased into vague atmosphere. This is also "
        f"what makes each location instantly tell-apart from the others.\n"
        f"- Then fill in the rest: architecture/setting, time of day, weather, "
        f"foreground/midground/background layering — matching the "
        f"description above.\n"
        f"- Explicitly rule out in the prose itself (this model has no "
        f"separate negative-prompt field): no people, no characters, no text, "
        f"no watermark, no logos; calm and atmospheric, never eerie or "
        f"horror-toned; dim/warm light, never bright daylight or harsh sun.\n"
        f"- One paragraph per location, no camera jargon lists, no numbered "
        f"options.\n\n"
        f"Answer in EXACTLY this format and nothing else, one block per "
        f"location, using the exact keys given above:\n\n"
        f"=== LOCATION_KEY ===\n<the prompt>\n\n"
        f"=== NEXT_LOCATION_KEY ===\n<the prompt>"
    )


def parse_blocks(output, expected_keys):
    chunks = re.split(r"===\s*([A-Z0-9_]+)\s*===", output)
    blocks = {}
    for i in range(1, len(chunks), 2):
        key = chunks[i].strip()
        text = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
        if key in expected_keys and text:
            blocks[key] = text
    return blocks


def main():
    parser = argparse.ArgumentParser(description="Bild-Prompts für die Szenen-Orte einer Serie")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene PROMPTS.txt neu generieren")
    parser.add_argument("--no-images", action="store_true",
                        help="Nur Text-Prompts erzeugen, auch wenn OPENAI_API_KEY gesetzt ist")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)

    locations = collect_locations(data)
    if not locations:
        print(f"Serie '{series.slug}' hat kein 'locations'-Mapping in episodes.json — "
              f"nichts zu tun (nur Templates mit Location-Unterstützung, z.B. soap_opera, "
              f"legen dieses Feld an).")
        return

    out_file = prompts_file(series)
    expected_keys = set(locations)

    # Vorhandene PROMPTS.txt heißt nur "der TEXT ist fertig" — nicht "die
    # Bilder sind fertig" (die Datei wird auch im reinen Text-Modus ohne
    # OPENAI_API_KEY geschrieben). Ein Re-Lauf, nachdem der Key nachträglich
    # gesetzt wurde, muss die vorhandenen Prompts wiederverwenden können,
    # statt sie erneut per Claude zu erzeugen — und darf danach nicht
    # abbrechen, sondern MUSS bei der Bildgenerierung unten ankommen.
    blocks = {}
    if os.path.exists(out_file) and not args.force:
        with open(out_file, "r", encoding="utf-8") as f:
            existing = f.read()
        blocks = parse_blocks(existing, expected_keys)
        if len(blocks) == len(expected_keys):
            print(f"Location-Prompts bereits vorhanden: {out_file} (--force zum Neu-Generieren) "
                  f"— prüfe/erzeuge fehlende Hintergrundbilder ...")
        else:
            missing = sorted(expected_keys - set(blocks))
            print(f"Vorhandene Prompts decken nicht alle Orte ab (fehlen: {', '.join(missing)}, "
                  f"z.B. neue Locations aus einer inzwischen geänderten episodes.json) — "
                  f"generiere Prompts neu ...")
            blocks = {}

    if not blocks:
        # light_model: reine Bild-Prompt-Texte, keine kreative Skript-Arbeit — braucht
        # nicht das teure Schreibmodell.
        model = data.get("generation", {}).get("light_model", config.DEFAULTS["light_model"])
        print(f"Serie: {series.slug} — {len(locations)} Ort(e): {', '.join(locations)}")
        print(f"Generiere Location-Prompts (Modell: {model}) ...")

        prompt = build_prompt(data, locations)
        for attempt in range(1, MAX_RETRIES + 1):
            output = call_claude(prompt, model)
            if output:
                blocks = parse_blocks(output, expected_keys)
                if len(blocks) == len(expected_keys):
                    break
                missing = sorted(expected_keys - set(blocks))
                print(f"Versuch {attempt}/{MAX_RETRIES}: Blöcke fehlen für {', '.join(missing)}.")
            else:
                print(f"Versuch {attempt}/{MAX_RETRIES}: keine Ausgabe.")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        if len(blocks) != len(expected_keys):
            print("FEHLER: Location-Prompts unvollständig — erneut starten.")
            sys.exit(1)

        os.makedirs(locations_dir(series), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(f"# Location-Bild-Prompts — {data.get('series_title', series.slug)}\n")
            f.write("# Jedes Bild extern generieren und hier im Ordner ablegen als: <ORT_KEY>.png\n")
            f.write("# (z.B. " + f"{next(iter(locations))}.png" + ") — für Cover-Kunst,\n")
            f.write("# Social-Media-Assets oder einen eigenen Video-Export.\n\n")
            for key in locations:
                f.write(f"=== {key} ===\n{blocks[key]}\n\n")

        print(f"\nGespeichert: {out_file}")

    if args.no_images or not image_backends.api_key_available():
        for key in locations:
            print(f"  === {key} ===  →  locations/{key}.png")
        if not image_backends.api_key_available():
            print("\nOPENAI_API_KEY nicht gesetzt — Prompts manuell bei einem Bildmodell "
                  "einfügen, PNGs unter den genannten Dateinamen in locations/ ablegen.")
        else:
            print("\n--no-images gesetzt — Prompts manuell bei einem Bildmodell einfügen, "
                  "PNGs unter den genannten Dateinamen in locations/ ablegen.")
        return

    print(f"\nErzeuge Hintergrundbilder (gpt-image-1-mini, {IMAGE_SIZE}) — vor jeder Anfrage "
          f"wird zuerst die serienübergreifende Orts-Bibliothek geprüft "
          f"(data/location_library/) ...")
    failed = []
    reused = 0
    for key, lcfg in locations.items():
        img_path = os.path.join(locations_dir(series), f"{key}.png")
        if os.path.exists(img_path):
            print(f"  {key}: übersprungen (existiert bereits)")
            continue

        description = lcfg.get("description", "")
        lib_hash, lib_entry = location_library.find_match(description) if description else (None, None)

        try:
            if lib_hash:
                location_library.copy_from_library(lib_hash, img_path)
                match_desc = lib_entry.get("description", "")
                print(f"  {key}: aus Bibliothek wiederverwendet"
                      f"{f' (≈ \"{match_desc[:60]}\")' if match_desc else ''} → locations/{key}.png")
                reused += 1
                continue

            png_bytes = image_backends.generate_image(blocks[key], size=IMAGE_SIZE)
            with open(img_path, "wb") as f:
                f.write(png_bytes)
            if description:
                location_library.register(description, png_bytes)
            print(f"  {key}: gespeichert → locations/{key}.png")
        except RuntimeError as exc:
            print(f"  {key}: FEHLER — {exc}")
            failed.append(key)

    if reused:
        print(f"\n{reused} Hintergrundbild(er) aus der Bibliothek wiederverwendet (kein API-Call nötig).")
    if failed:
        print(f"\n{len(failed)} Hintergrundbild(er) fehlgeschlagen ({', '.join(failed)}) — "
              f"Skript erneut starten (fertige Bilder werden übersprungen).")


if __name__ == "__main__":
    main()
