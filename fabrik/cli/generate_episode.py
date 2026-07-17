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
from fabrik.writing import script_writer, thumbnail_writer

# Jede Episode läuft als eigener Subprozess (_run_episode_subprocess) und wartet dort fast
# ausschließlich auf 'claude'-Subprozess-Antworten (I/O-bound, siehe run_claude_process()) —
# CPU auf dieser Maschine ist praktisch nie der Flaschenhals, eher API-Latenz/-Rate-Limits.
# Bisher war der Default 2, ohne dokumentierten Grund; 4 nutzt die vorhandene Parallelität
# (mehrere gleichzeitige claude-Aufrufe sind unproblematisch, siehe auch BATCH_PARALLEL_CAP
# in create_series.py) besser aus, ohne bei kleinen Serien (len(episodes) < 4, siehe
# max_workers-Deckelung unten) mehr Jobs zu starten als es überhaupt Episoden gibt.
DEFAULT_JOBS = 4


def _run_episode_subprocess(ep_num: int, series_slug: str, force: bool, no_script_review: bool,
                            fix_review: bool, beats_ready: bool = False) -> tuple:
    """Führt eine einzelne Episode als separaten Prozess aus (für Parallelisierung)."""
    cmd = [sys.executable, "-m", "fabrik.cli.generate_episode",
           str(ep_num), "--series", series_slug]
    if force:
        cmd.append("--force")
    if no_script_review:
        cmd.append("--no-script-review")
    # Explizit in beide Richtungen durchreichen — der Subprocess hat denselben
    # Default (--fix an), aber implizites Vererben wäre fragil gegenüber
    # künftigen Default-Änderungen.
    cmd.append("--fix" if fix_review else "--no-fix")
    if beats_ready:
        cmd.append("--beats-ready")
    result = subprocess.run(cmd, check=False, cwd=paths.BASE_DIR)
    return ep_num, result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Podcast Script Generator — Section für Section"
    )
    parser.add_argument("episode", help="Episodennummer (1, 2, ...), 'all' oder 'check' (nur episodes.json validieren)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene Datei komplett neu generieren")
    parser.add_argument("--no-audio", action="store_true",
                        help="Nur 'all': die komplette Skript-Pipeline (Beats, Skripte, Review, "
                             "SFX-Plan) laufen lassen, aber VOR dem Vertonen stoppen (kein batch). "
                             "Für Parallelbetrieb mehrerer Serien/Cockpits, die sich den einen "
                             "lokalen TTS-Server nicht teilen können.")
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS, metavar="N",
                        help=f"Anzahl parallel generierter Episoden bei 'all' (Standard: "
                             f"{DEFAULT_JOBS} — I/O-bound, wartet meist nur auf 'claude'-"
                             f"Antworten, siehe Kommentar bei DEFAULT_JOBS)")
    parser.add_argument("--no-script-review", action="store_true",
                        help="Episoden-Review nach dem Schreiben überspringen (Wissens-Verstöße/"
                             "Spoiler-Leaks im fertigen Skripttext, nur bei case-basierten Templates)")
    # --fix ist seit der 12-Serien-Analyse (17.07.2026) der DEFAULT: alle
    # untersuchten Serien liefen ohne --fix, weshalb selbst korrekt geflaggte
    # Review-Befunde nie repariert wurden (z.B. first_do_harm: 2/2 Befunde
    # unbehoben im vertonten Skript). --no-fix schaltet die Reparatur ab.
    parser.add_argument("--fix", dest="fix", action="store_true", default=True,
                        help="Vom Episoden-Review gemeldete Parts automatisch reparieren "
                             "(Standard; schreibt nur die betroffenen Parts neu, danach "
                             "erneuter Review zur Bestätigung). Eine vorhandene REVIEW.txt "
                             "wird wiederverwendet: 'keine Auffälligkeiten' überspringt den "
                             "Review komplett, offene Befunde gehen direkt in die Reparatur "
                             "— kein Re-Review unveränderter Skripte.")
    parser.add_argument("--no-fix", dest="fix", action="store_false",
                        help="Automatische Review-Reparatur abschalten (Befunde werden nur "
                             "in der REVIEW.txt protokolliert)")
    # Intern ('all' → Subprocess): Beats wurden vom Elternprozess schon seriell
    # in Episodenreihenfolge vorgeneriert — nicht löschen/neu generieren, nur laden.
    parser.add_argument("--beats-ready", action="store_true", help=argparse.SUPPRESS)
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
    template = script_writer.load_template(cfg["template"], series=series)
    episodes = data["episodes"]

    print(f"Serie: \"{data.get('series_title', '?')}\" [{series.slug}] — {len(episodes)} Episoden")
    print(f"Format: {cfg['mode']}, {cfg['parts_per_section']} Parts/Section, "
          f"{cfg['min_words']}–{cfg['max_words']} Einheiten/Part (Ziel {cfg['words_target']}), "
          f"Sprache: {cfg['language']}, Modell: {cfg['model']}")

    if args.episode.lower() == "all":
        max_workers = max(1, min(args.jobs, len(episodes)))
        print(f"\nStarte {len(episodes)} Episode(n) mit {max_workers} parallelen Job(s) ...")

        # Beats-Vorlauf: Beats lesen die Beats der VORHERIGEN Episode als
        # Kontinuitätskontext — unter --jobs>1 wäre die Reihenfolge zufällig
        # (die dokumentierte Known Limitation). Deshalb hier erst alle
        # Beat-Sheets seriell in Episodenreihenfolge erzeugen (ein billiger
        # Call pro Episode), dann die teure Prosa parallel. Ein Fehlschlag
        # einzelner Beats ist wie bisher nicht fatal (Fallback im Subprocess).
        beats_ready = False
        if max_workers > 1 and cfg.get("use_beats") and any(ep.get("case") for ep in episodes):
            print("\nBeats-Vorlauf: generiere Beat-Sheets seriell in Episodenreihenfolge ...")
            for idx, ep in enumerate(episodes):
                if not ep.get("case") or ep.get("source") == "imported":
                    continue
                if args.force:
                    for stale in (series.beats_file(cfg["prefix"], idx + 1),
                                  series.beats_review_file(cfg["prefix"], idx + 1)):
                        if os.path.exists(stale):
                            os.remove(stale)
                script_writer.generate_beats(series, idx, episodes, False, cfg)
            beats_ready = True

        failed = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_episode_subprocess, idx + 1, series.slug, args.force,
                           args.no_script_review, args.fix, beats_ready): idx + 1
                for idx in range(len(episodes))
            }
            for future in concurrent.futures.as_completed(futures):
                ep_num, ok = future.result()
                if not ok:
                    failed.append(ep_num)

        print(f"\nFertig: {len(episodes)-len(failed)}/{len(episodes)} generiert.")

        # Phrasen-Frequenz-Report (deterministisch, gratis): serienweite Tics
        # ("barely audible" 57x etc.) als Review-Gate-Datei neben die Skripte —
        # der Wächter im Section-Prompt (avoid_block) verhindert nur Neues,
        # dieser Report zeigt den Ist-Zustand der ganzen Staffel.
        script_texts = {}
        for idx in range(1, len(episodes) + 1):
            sf = series.script_file(cfg["prefix"], idx)
            if os.path.exists(sf):
                with open(sf, "r", encoding="utf-8") as f:
                    script_texts[idx] = f.read()
        if script_texts:
            from fabrik.writing import phrase_stats
            report_path = os.path.join(os.path.dirname(series.script_file(cfg["prefix"], 1)),
                                       "PHRASE_REPORT.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(phrase_stats.build_phrase_report(
                    script_texts, exclude_words=phrase_stats.name_words(data)))
            print(f"Phrasen-Report: {os.path.basename(report_path)}")

        if failed:
            print(f"Fehlgeschlagen: Episode(n) {sorted(failed)}")
            print("batch wird nicht gestartet — erst alle Episoden generieren.")
        else:
            # SFX-Plan VOR batch: er entscheidet, welche [SFX: ...]-Cues überhaupt
            # klingen und ob ein Cue eine eigene Lücke VOR der nächsten Zeile
            # bekommt — das verändert die Episoden-MP3 selbst. Nachträglich
            # geplant hätte er auf eine fertige MP3 keinen Einfluss mehr (man
            # müsste sie löschen und neu vertonen). Deshalb hier, an derselben
            # Stelle und mit demselben Muster, mit dem auch batch gestartet wird.
            # Kein venv (Claude CLI, stdlib) — anders als batch.
            if data.get("mode") == "drama":
                print("\nStarte SFX-Plan (Sounddesign: Palette, Platzierung, Ambience) ...")
                cmd = [sys.executable, "-m", "fabrik.cli.sfx_plan", "--series", series.slug]
                if args.force:
                    # Neue Skripte = neue Cues an neuen Positionen: ein alter Plan
                    # wäre veraltet (podcast_maker würde ihn dank Text-Abgleich
                    # zwar nicht falsch anwenden, aber eben auch gar nicht).
                    cmd.append("--force")
                subprocess.run(cmd, check=False, cwd=paths.BASE_DIR)

            if args.no_audio:
                # Halt vor dem Vertonen: alle Skripte + SFX-Plan liegen bereit,
                # batch läuft bewusst NICHT. Für Parallelbetrieb mehrerer Serien,
                # die sich den einen lokalen TTS-Server nicht teilen können — die
                # Vertonung startet man danach gezielt (Cockpit-Knopf/batch/Cloud).
                print("\n✓ Skripte + SFX-Plan fertig — Vertonung übersprungen (--no-audio).")
                print("  Vertonen: .venv/bin/python -m fabrik.cli.batch "
                      f"--series {series.slug}")
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
            thumbnail_writer.generate_episode_thumbnail(series, num - 1, data, episodes, args.force, cfg)
            return

        ok = script_writer.generate_episode(series, num - 1, template, data, episodes,
                                            args.force, cfg, skip_review=args.no_script_review,
                                            fix_review=args.fix, beats_pregenerated=args.beats_ready)
        if ok:
            # Nice-to-have wie generate_episode_meta (das generate_episode()
            # bereits intern aufruft) — hier statt in script_writer.py, damit
            # thumbnail_writer.py von dort importieren kann, ohne einen
            # Zirkel-Import zu riskieren (call_claude/MAX_RETRIES/RETRY_DELAY
            # kommen aus script_writer.py, wie bei cover_art.py/location_prompts.py).
            thumbnail_writer.generate_episode_thumbnail(series, num - 1, data, episodes,
                                                        args.force, cfg)
            script = os.path.basename(series.script_file(cfg["prefix"], num))
            print(f"\nNächster Schritt: .venv/bin/python -m fabrik.cli.podcast_maker {script}")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
