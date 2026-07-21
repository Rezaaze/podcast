#!/usr/bin/env python3
"""Erzeugt/erneuert Episoden-Thumbnails von Hand — die automatische
Generierung läuft bereits am Ende jeder Episoden-Generierung
(fabrik/cli/generate_episode.py, sofern OPENAI_API_KEY gesetzt ist). Dieses
CLI ist für Nachholen (Key wurde erst später gesetzt) und gezieltes
Neu-Generieren (--force) einzelner Episoden gedacht, ohne das ganze Skript
neu zu schreiben.

Verwendung:
  python3 -m fabrik.cli.episode_thumbnails                    # alle fehlenden
  python3 -m fabrik.cli.episode_thumbnails --episode 3         # nur Episode 3
  python3 -m fabrik.cli.episode_thumbnails --force             # alle neu generieren
  python3 -m fabrik.cli.episode_thumbnails --series thin_walls

Braucht kein .venv — nur die Claude CLI (wie character_prompts.py); die
Bildgenerierung selbst nutzt nur stdlib (urllib), kein zusätzliches Paket.
"""

import argparse
import sys

from fabrik.core import config, paths
from fabrik.writing import image_backends, thumbnail_writer


def main():
    parser = argparse.ArgumentParser(
        description="Dramatische, spoilerfreie Episoden-Thumbnails (16:9 + 1:1) generieren")
    parser.add_argument("--episode", type=int, default=None, metavar="N",
                        help="Nur Episode N (Standard: alle Episoden)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene Thumbnails neu generieren")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)
    cfg = config.build_config(data)
    episodes = data.get("episodes", [])

    if args.episode is not None and not (1 <= args.episode <= len(episodes)):
        print(f"FEHLER: --episode {args.episode} — Serie hat Episoden 1..{len(episodes)}.")
        sys.exit(1)

    if not image_backends.api_key_available():
        print("FEHLER: OPENAI_API_KEY nicht gesetzt — Thumbnails brauchen die Bild-API.")
        sys.exit(1)

    targets = [args.episode] if args.episode is not None else range(1, len(episodes) + 1)
    ok = failed = 0
    for num in targets:
        print(f"\nEpisode {num} ({episodes[num - 1]['figure']}):")
        if thumbnail_writer.generate_episode_thumbnail(series, num - 1, data, episodes,
                                                        args.force, cfg):
            ok += 1
        else:
            failed += 1

    print(f"\nFertig: {ok}/{len(targets)} Episode(n).")
    if failed:
        print(f"Fehlgeschlagen: {failed} — erneut starten (fertige Thumbnails werden übersprungen).")
        sys.exit(1)


if __name__ == "__main__":
    main()
