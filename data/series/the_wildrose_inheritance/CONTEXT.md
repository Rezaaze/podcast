# Routing — Serie the_wildrose_inheritance

| Stage | Aufgabe | Output | Kommando |
|---|---|---|---|
| `stages/01_concept/` | Serienkonzept (Figuren/Fälle/Stimmen) | `episodes.json` | `python3 -m fabrik.cli.create_series` (hat diese Serie erzeugt) |
| `stages/02_scripts/` | Episodenskripte schreiben | `ep<N>.txt` + META/BEATS/REVIEW | `python3 -m fabrik.cli.generate_episode N\|all --series the_wildrose_inheritance` |
| `stages/03_audio/` | Vertonung + Mastering + Timelines | `*_FULL_EPISODE.mp3`, SRT, SPEAKERS/LOCATIONS/SUBS | `.venv/bin/python -m fabrik.cli.podcast_maker` / `batch` |
| `stages/04_visuals/` | Porträts, Orts-Hintergründe, Cover | `characters/`, `locations/` PNGs + PROMPTS.txt | `python3 -m fabrik.cli.character_prompts` / `location_prompts` |

Geteilte Ressourcen:

- `references/` — Layer 3, stabil über alle Läufe: `PROMPT_TEMPLATE.md`
  (das Skript-Prompt DIESER Serie — hier editieren, um den Ton der Serie
  zu ändern; Master unter `templates/soap_opera/` bleibt unberührt),
  `EPISODES_CREATOR_PROMPT.md` (Doku: womit das Konzept erzeugt wurde).
- `assets/` — optional `intro.mp3` / `outro.mp3` / `transition.mp3`.
- Global (außerhalb dieses Workspace): `data/voices/` (Clone-Referenzen),
  `data/figure_history.json` (Figuren-Sperrliste über alle Serien).

**Review-Gates:** nach jeder Stage kann der Output geprüft und editiert
werden, bevor die nächste läuft. Die Pipeline resumed dateibasiert — was
existiert, wird nicht neu erzeugt (`--force` erzwingt Neuerzeugung).
