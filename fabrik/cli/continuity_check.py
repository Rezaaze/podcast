#!/usr/bin/env python3
"""Prüft die fertigen Skripte einer Serie deterministisch gegen ihren Kanon.

Reine Anzeige, kein Claude-Call, kein venv — analog PHRASE_REPORT.txt. Der
Report ist ein Review-Gate: er meldet, was ein Mensch sich ansehen sollte,
und repariert nichts von selbst.

Hintergrund (Messung 19.07.2026, docs/kontinuitaets-messung-2026-07-19.md):
in 16 Produktionsepisoden steckten 18 gegengeprüfte Kanon-Brüche, obwohl in
beiden Serien die Beat-Schicht lief. Rund die Hälfte davon ist ohne jeden
Modellaufruf auffindbar — erfundene Ortsnamen und Zeitangaben, die den
objective_facts widersprechen. Ein LLM-Prüfpanel hatte davon mehrere
übersehen und produzierte gleichzeitig 67% Falschbefunde.

Verwendung:
  python3 -m fabrik.cli.continuity_check [--series SLUG]

Stdlib-only.
"""

import argparse
import os

from fabrik.core import config, paths
from fabrik.writing import continuity

REPORT_FILENAME = "CONTINUITY_REPORT.txt"


def collect_scripts(series, prefix: str, episode_count: int) -> dict[int, str]:
    scripts: dict[int, str] = {}
    for idx in range(1, episode_count + 1):
        path = series.script_file(prefix, idx)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                scripts[idx] = handle.read()
    return scripts


def main():
    parser = argparse.ArgumentParser(
        description="Fertige Skripte deterministisch gegen den Serien-Kanon prüfen")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)

    prefix = data.get("output_prefix", config.DEFAULTS["output_prefix"])
    episodes = data.get("episodes") or []
    scripts = collect_scripts(series, prefix, len(episodes))
    if not scripts:
        print(f"Serie '{series.slug}': noch keine Skripte in {series.scripts_dir} — "
              f"erst generieren, dann prüfen.")
        return

    report = continuity.build_continuity_report(data, scripts)
    out_path = os.path.join(series.scripts_dir, REPORT_FILENAME)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(report)

    print(report)
    print(f"Geschrieben: {out_path}")


if __name__ == "__main__":
    main()
