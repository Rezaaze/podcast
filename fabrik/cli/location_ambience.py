#!/usr/bin/env python3
"""Erzeugt Ambience-Loops für die wiederverwendbaren Szenen-Orte einer
Serie über ElevenLabs — das Audio-Gegenstück zu location_prompts.py.

Verwendung:
  python3 -m fabrik.cli.location_ambience                    # aktuelle Serie
  python3 -m fabrik.cli.location_ambience --series facades
  python3 -m fabrik.cli.location_ambience --force             # vorhandene Dateien neu generieren

Für jeden Ort aus dem top-level "locations"-Mapping (episodes.json) wird
ein kurzer, geloopter Ambience-Track erzeugt und als
series/<slug>/stages/03_audio/output/sfx/ambience/<ORT_KEY>.mp3 abgelegt.
Dort findet ihn das Lolfi-Video-Rendering und wechselt die Hintergrund-
Ambience automatisch, wenn die Handlung an diesen Ort springt (gleiche
Location-Timeline wie beim Hintergrundbild-Wechsel).

Braucht ELEVENLABS_API_KEY. Vor jedem API-Aufruf wird zuerst die
serienübergreifende Sound-Bibliothek (fabrik/writing/sfx_library.py) auf
einen exakten oder ähnlichen vorhandenen Track geprüft — zwei Orte mit
ähnlicher Beschreibung (auch über verschiedene Serien hinweg) teilen sich
dieselbe Ambience, ohne zweimal zu generieren.

Braucht kein .venv — die Generierung selbst nutzt nur stdlib (urllib).
"""

import argparse
import os
import sys

from fabrik.core import config, paths
from fabrik.writing import elevenlabs_backend, sfx_library

AMBIENCE_GEN_DURATION_SECONDS = 10.0  # kurz genug, Lolfi loopt es per -stream_loop -1 nahtlos


def ambience_dir(series):
    return os.path.join(series.output_dir, "sfx", "ambience")


def collect_locations(data):
    return data.get("locations", {})


def build_ambience_prompt(lcfg):
    name = lcfg.get("name", "")
    desc = lcfg.get("description", "")
    base = f"{name} — {desc}" if name else desc
    return f"{base}, ambient background loop, continuous atmosphere, no music, no voices, no sudden events"


def main():
    parser = argparse.ArgumentParser(description="Ambience-Loops für die Szenen-Orte einer Serie (ElevenLabs)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene Ambience-Dateien neu generieren")
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

    if not elevenlabs_backend.api_key_available():
        print("FEHLER: ELEVENLABS_API_KEY nicht gesetzt — 'export ELEVENLABS_API_KEY=...' vor dem Aufruf.")
        sys.exit(1)

    out_dir = ambience_dir(series)
    os.makedirs(out_dir, exist_ok=True)
    print(f"Serie: {series.slug} — {len(locations)} Ort(e): {', '.join(locations)}")

    failed = []
    for key, lcfg in locations.items():
        out_path = os.path.join(out_dir, f"{key}.mp3")
        if os.path.exists(out_path) and not args.force:
            print(f"  {key}: übersprungen (existiert bereits)")
            continue
        prompt = build_ambience_prompt(lcfg)
        try:
            sfx_library.resolve_or_generate(prompt, "ambience", out_path,
                                            duration_seconds=AMBIENCE_GEN_DURATION_SECONDS)
            print(f"  {key}: gespeichert → sfx/ambience/{key}.mp3")
        except RuntimeError as exc:
            print(f"  {key}: FEHLER — {exc}")
            failed.append(key)

    if failed:
        print(f"\n{len(failed)} Ambience-Track(s) fehlgeschlagen ({', '.join(failed)}) — "
              f"Skript erneut starten (fertige Dateien werden übersprungen).")


if __name__ == "__main__":
    main()
