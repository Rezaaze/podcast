# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository. Es ist bewusst kurz (Layer 0+1): Details leben in
Bereichs-CLAUDE.md-Dateien, die Claude Code automatisch lädt, sobald in dem
Bereich gearbeitet wird — Routing-Tabelle unten.

## What this is

Podcast-Fabrik ist eine automatisierte Pipeline für Podcast-Serien: Claude
schreibt die Skripte, eine lokale Qwen3-TTS-API vertont sie, Ergebnis ist
eine gemasterte MP3 pro Episode (+ optional Anthologie-Merge). Kein
Build-Step, **keine Test-Suite, kein Linter** — Python-CLI-Skripte,
orchestriert von einem Flask-WebUI, plus vast.ai-Automation für Cloud-GPU-TTS.

Ein zweites, separates Projekt — `~/Downloads/Lolfi` (Video/Musik, nicht in
diesem Repo) — teilt sich das WebUI-Cockpit; `webui/config.py` hardcodet
`LOLFI_DIR`.

**⚠️ Aktueller Umbau:** Das Repo wird nach dem Model Workspace Protocol
umgebaut (Branch `mwp-umbau`) — Plan und Task-Stand in
`docs/mwp-umbau-plan.md`. Vor Arbeit an Pfaden in `fabrik/` dort den
Phasen-Stand prüfen.

## Layout

Getrennt nach Laufzeitumgebung und Kopplung, nicht nach Thema:

| Bereich | Inhalt | Umgebung |
|---|---|---|
| `fabrik/core/` | paths, config, textproc, history, claude_cli | stdlib-only, überall importierbar |
| `fabrik/writing/` | Skript-Generierung, Reviews, Beats | nur `claude` CLI |
| `fabrik/audio/` | Vertonung, TTS-Backends, Mastering | `.venv` + ffmpeg |
| `fabrik/cli/` | Entry-Points (`python3 -m fabrik.cli.<name>`) | je nach Ziel |
| `webui/`, `cloud/` | eigenständige Subprojekte | eigenes venv / Shell |
| `templates/` | Prompt-"Produktdefinition", 5 Templates | reine .md |
| `data/` | Serien, Voices, figure_history, Archiv | meist gitignored |

**Import-Regel (hart):** `fabrik/core/` und `fabrik/writing/` dürfen NIE aus
`fabrik/audio/` importieren — das bräche den No-venv-Pfad der
Skript-Generierung.

## Kommandos

```bash
# 1. Serie erzeugen (schreibt data/series/<slug>/episodes.json via Claude CLI)
python3 -m fabrik.cli.create_series "Topic" [--episodes N] [--minutes M] [--locations L] [--template T] [--no-review] [--fix]
# 1b. Fertigen Text importieren statt erfinden (nur narration)
python3 -m fabrik.cli.import_story <ordner-oder-datei> "Titel" [--no-summary]

# 2. Skripte schreiben (claude CLI, kein venv)
python3 -m fabrik.cli.generate_episode check|N|all [--jobs N] [--force] [--fix] [--no-script-review]

# 3. Vertonen (.venv + ffmpeg + laufender TTS-Server laut audio.api_url)
.venv/bin/python -m fabrik.cli.podcast_maker ep1.txt
.venv/bin/python -m fabrik.cli.batch

# 3b/3c. Bild-Prompts (claude CLI; PNGs direkt bei gesetztem OPENAI_API_KEY)
python3 -m fabrik.cli.character_prompts [--force]
python3 -m fabrik.cli.location_prompts [--force]

# Alle CLIs: --series <slug>, sonst data/series/LATEST.

# WebUI (steuert dieses Projekt + Lolfi), Port 5151
./start_webui.sh

# Cloud-GPU (vast.ai) für schnelleres TTS — cloud/README.md
cd cloud && ./rent.sh && ./status.sh   # ./stop.sh ./resume.sh ./destroy.sh
```

## Routing — wo die Details stehen

| Wenn du arbeitest an … | lies |
|---|---|
| episodes.json-Schema, validate_data, Voices-Regeln, claude_cli-Plumbing | `fabrik/core/CLAUDE.md` |
| Skript-Generierung, Retry/Fallback, Wortbudget, Episode-Review, Beat-Layer | `fabrik/writing/CLAUDE.md` |
| Vertonung, Backends, Checkpoints, Post-Merge-Safety, Timelines, Voice-Manifest, Seed | `fabrik/audio/CLAUDE.md` |
| CLI-Flags, create_series-Verhalten, import_story, Bild-Prompt-CLIs | `fabrik/cli/CLAUDE.md` |
| WebUI, COMMANDS/JobRegistry/SSE, Lolfi-Kopplung, UI-Gotchas | `webui/CLAUDE.md` |
| Template-Anatomie, die 5 Formate, Accent-Casting, NARRATOR-Regel | `templates/CLAUDE.md` |
| Beat-Layer-Design-Begründung | `docs/beat-layer-design.md` |
| MWP-Umbau (Plan, Ziel-Layout, Task-Stand) | `docs/mwp-umbau-plan.md` |

## Top-Gotchas (gelten überall)

- **`stdin=subprocess.DEVNULL`** bei jedem `claude -p`-Subprocess — sonst
  hängt der CLI, wenn der Elternprozess kein TTY-stdin hat (genau so
  spawnt das WebUI jeden Job). Details: `fabrik/core/CLAUDE.md`.
- Lange Claude-Calls immer über `fabrik/core/claude_cli.py::
  run_claude_process` (Heartbeat) laufen lassen; Timeouts/Fehler in
  Retry-Schleifen sind retryable, nie `sys.exit()` — nur "claude not
  found"/"not logged in" brechen ab.
- WebUI: HTML/JS/CSS-Edits greifen per Browser-Reload,
  `webui/*.py`-Änderungen brauchen einen Server-Neustart.
- Es gibt keine Tests — Verifikation läuft über Smoke-Runs (Mini-Serie,
  `generate_episode check`, WebUI-Durchklick).
