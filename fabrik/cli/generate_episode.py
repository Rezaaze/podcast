#!/usr/bin/env python3
"""
Automatisierter Podcast-Script-Generator via Claude CLI.
Generiert jede Section einzeln und schreibt sie sofort in die Datei.

Verwendung (vom Projekt-Root aus):
  python3 -m fabrik.cli.generate_episode 1                     # Episode 1 der aktuellen Serie
  python3 -m fabrik.cli.generate_episode all                   # Alle Episoden (parallel, --jobs N)
  python3 -m fabrik.cli.generate_episode check                 # nur episodes.json validieren
  python3 -m fabrik.cli.generate_episode 1 --series tee_haus   # explizite Serie
  python3 -m fabrik.cli.generate_episode 1 --force             # Komplett neu generieren

Jede Serie lebt in data/series/<slug>/ (episodes.json + scripts/ + output/);
ohne --series wird data/series/LATEST bzw. die einzige vorhandene Serie genutzt.
Die eigentliche Logik liegt in fabrik/writing bzw. fabrik/core.
"""

import argparse
import concurrent.futures
import os
import subprocess
import sys

from fabrik.core import config, history, paths
from fabrik.writing import script_writer


def _run_episode_subprocess(ep_num: int, series_slug: str, force: bool, no_script_review: bool,
                            fix_review: bool) -> tuple:
    """Führt eine einzelne Episode als separaten Prozess aus (für Parallelisierung)."""
    cmd = [sys.executable, "-m", "fabrik.cli.generate_episode",
           str(ep_num), "--series", series_slug]
    if force:
        cmd.append("--force")
    if no_script_review:
        cmd.append("--no-script-review")
    if fix_review:
        cmd.append("--fix")
    result = subprocess.run(cmd, check=False, cwd=paths.BASE_DIR)
    return ep_num, result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Podcast Script Generator — Section für Section"
    )
    parser.add_argument("episode", help="Episodennummer (1, 2, ...), 'all' oder 'check' (nur episodes.json validieren)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene Datei komplett neu generieren")
    parser.add_argument("--jobs", type=int, default=2, metavar="N",
                        help="Anzahl parallel generierter Episoden bei 'all' (Standard: 2)")
    parser.add_argument("--no-script-review", action="store_true",
                        help="Episoden-Review nach dem Schreiben überspringen (Wissens-Verstöße/"
                             "Spoiler-Leaks im fertigen Skripttext, nur bei case-basierten Templates)")
    parser.add_argument("--fix", action="store_true",
                        help="Vom Episoden-Review gemeldete Parts automatisch reparieren "
                             "(schreibt nur die betroffenen Parts neu, danach erneuter Review "
                             "zur Bestätigung) — läuft auch, wenn schon eine REVIEW.txt existiert")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)
    history.warn_on_repeated_figures(data)

    if args.episode.lower() == "check":
        print(f"episodes.json der Serie '{series.slug}' ist gültig ✓")
        return

    cfg = config.build_config(data)
    template = script_writer.load_template(cfg["template"])
    episodes = data["episodes"]

    print(f"Serie: \"{data.get('series_title', '?')}\" [{series.slug}] — {len(episodes)} Episoden")
    print(f"Format: {cfg['mode']}, {cfg['parts_per_section']} Parts/Section, "
          f"{cfg['min_words']}–{cfg['max_words']} Einheiten/Part (Ziel {cfg['words_target']}), "
          f"Sprache: {cfg['language']}, Modell: {cfg['model']}")

    if args.episode.lower() == "all":
        max_workers = max(1, min(args.jobs, len(episodes)))
        print(f"\nStarte {len(episodes)} Episode(n) mit {max_workers} parallelen Job(s) ...")

        failed = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_episode_subprocess, idx + 1, series.slug, args.force,
                           args.no_script_review, args.fix): idx + 1
                for idx in range(len(episodes))
            }
            for future in concurrent.futures.as_completed(futures):
                ep_num, ok = future.result()
                if not ok:
                    failed.append(ep_num)

        print(f"\nFertig: {len(episodes)-len(failed)}/{len(episodes)} generiert.")
        if failed:
            print(f"Fehlgeschlagen: Episode(n) {sorted(failed)}")
            print("batch wird nicht gestartet — erst alle Episoden generieren.")
        else:
            print("\nStarte batch ...")
            venv_python = os.path.join(paths.BASE_DIR, ".venv", "bin", "python")
            python = venv_python if os.path.exists(venv_python) else sys.executable
            subprocess.run([python, "-m", "fabrik.cli.batch",
                            "--series", series.slug], check=False, cwd=paths.BASE_DIR)
    else:
        try:
            num = int(args.episode)
        except ValueError:
            print(f"FEHLER: '{args.episode}' ist keine gültige Zahl.")
            sys.exit(1)
        if num < 1 or num > len(episodes):
            print(f"FEHLER: Episode {num} existiert nicht (1–{len(episodes)}).")
            sys.exit(1)

        episode = episodes[num - 1]
        if episode.get("source") == "imported":
            script_file = series.script_file(cfg["prefix"], num)
            if not os.path.exists(script_file):
                print(f"FEHLER: Episode {num} ist als 'imported' markiert, aber "
                      f"{os.path.basename(script_file)} fehlt — erneut mit import_story.py importieren.")
                sys.exit(1)
            print(f"\nEpisode {num}: \"{episode['figure']}\" — bereits importiert "
                  f"(import_story.py), Skript-Generierung übersprungen ✓")
            script_writer.generate_episode_meta(series, num - 1, data, episodes, args.force, cfg)
            return

        ok = script_writer.generate_episode(series, num - 1, template, data, episodes,
                                            args.force, cfg, skip_review=args.no_script_review,
                                            fix_review=args.fix)
        if ok:
            script = os.path.basename(series.script_file(cfg["prefix"], num))
            print(f"\nNächster Schritt: .venv/bin/python -m fabrik.cli.podcast_maker {script}")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
