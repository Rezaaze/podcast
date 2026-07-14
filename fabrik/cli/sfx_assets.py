#!/usr/bin/env python3
"""Erzeugt One-Shot-SFX für die [SFX: ...]-Cues einer Serie über ElevenLabs.

Verwendung:
  python3 -m fabrik.cli.sfx_assets                    # aktuelle Serie
  python3 -m fabrik.cli.sfx_assets --series facades
  python3 -m fabrik.cli.sfx_assets --force             # vorhandene Dateien neu generieren

Liest jede vorhandene <Episode>_SFX_CUES.json der Serie (geschrieben von
podcast_maker.py/batch.py NACH dem Vertonen — vor diesem Schritt
ausführen: podcast_maker/batch), sammelt die serienweit eindeutigen
Cue-Beschreibungen und erzeugt pro eindeutiger Beschreibung einen Sound,
abgelegt als series/<slug>/stages/03_audio/output/sfx/oneshots/<hash>.mp3
— <hash> = fabrik.core.textproc.sfx_asset_hash(description), damit Lolfi
beim Rendern ohne zusätzliche Zuordnungsdatei denselben Dateinamen aus dem
Cue-Text der jeweiligen Episode berechnen und die Datei finden kann.

Braucht ELEVENLABS_API_KEY. Vor jedem API-Aufruf wird zuerst die
serienübergreifende Sound-Bibliothek (fabrik/writing/sfx_library.py) auf
einen exakten oder ähnlichen vorhandenen Sound geprüft (Wortmengen-
Überlappung, keine Synonym-Erkennung: "gunshot echoing down the hallway"
aus einer früheren Serie deckt ein neues "a gunshot echoes down the long
hallway" ab, aber nicht "a gun fires" ohne gemeinsame Wörter).

Braucht kein .venv — die Generierung selbst nutzt nur stdlib (urllib).
"""

import argparse
import glob
import json
import os
import sys

from fabrik.core import paths
from fabrik.core.textproc import sfx_asset_hash
from fabrik.writing import elevenlabs_backend, sfx_library


def oneshots_dir(series):
    return os.path.join(series.output_dir, "sfx", "oneshots")


def collect_cue_descriptions(series):
    """Serienweit eindeutige Cue-Beschreibungen aus allen <Episode>_SFX_CUES.json."""
    descriptions = set()
    cue_files = sorted(glob.glob(os.path.join(series.output_dir, "*_SFX_CUES.json")))
    for cue_file in cue_files:
        with open(cue_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for cue in data.get("cues", []):
            desc = cue.get("description", "").strip()
            if desc:
                descriptions.add(desc)
    return cue_files, descriptions


def main():
    parser = argparse.ArgumentParser(description="One-Shot-SFX für die SFX-Cues einer Serie (ElevenLabs)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene SFX-Dateien neu generieren")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    cue_files, descriptions = collect_cue_descriptions(series)

    if not cue_files:
        print(f"Serie '{series.slug}' hat keine *_SFX_CUES.json in {series.output_dir}/ — "
              f"nichts zu tun (erst podcast_maker/batch im Drama-Modus vertonen lassen).")
        return
    if not descriptions:
        print(f"{len(cue_files)} SFX-Cue-Datei(en) gefunden, aber keine Cues darin — nichts zu tun.")
        return

    if not elevenlabs_backend.api_key_available():
        print("FEHLER: ELEVENLABS_API_KEY nicht gesetzt — 'export ELEVENLABS_API_KEY=...' vor dem Aufruf.")
        sys.exit(1)

    out_dir = oneshots_dir(series)
    os.makedirs(out_dir, exist_ok=True)
    print(f"Serie: {series.slug} — {len(descriptions)} eindeutige SFX-Cue(s) aus {len(cue_files)} Episode(n)")

    generated, skipped, failed = 0, 0, []
    for desc in sorted(descriptions):
        out_path = os.path.join(out_dir, f"{sfx_asset_hash(desc)}.mp3")
        if os.path.exists(out_path) and not args.force:
            skipped += 1
            continue
        try:
            sfx_library.resolve_or_generate(desc, "oneshots", out_path)
            print(f"  '{desc}' → sfx/oneshots/{os.path.basename(out_path)}")
            generated += 1
        except RuntimeError as exc:
            print(f"  '{desc}': FEHLER — {exc}")
            failed.append(desc)

    print(f"\n{generated} von {len(descriptions)} eindeutigen SFX-Cues generiert "
          f"({skipped} bereits vorhanden, {len(failed)} übersprungen).")
    if failed:
        print("Erneut starten, um fehlgeschlagene Cues nachzuholen (fertige werden übersprungen).")


if __name__ == "__main__":
    main()
