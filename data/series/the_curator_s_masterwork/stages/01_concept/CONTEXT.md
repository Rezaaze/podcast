# Stage 01 — Konzept

## Inputs
- Topic-Brief des Users (CLI-Argument, nicht persistiert)
- Layer 3 (global): `templates/soap_opera/EPISODES_CREATOR_PROMPT.md`
- Layer 3 (global): `data/figure_history.json` — bereits verwendete Figuren

## Process
Claude entwirft die komplette Serie in einem Schuss: Figuren/Fälle,
Episoden-Themen, Sections, Stimmen-Casting (Accent-Casting-Regel!),
section_words/section_locations. Strukturvalidierung + optionales
LLM-Review, Retry-Schleife mit Fehler-Feedback.
Ausgeführt von: `python3 -m fabrik.cli.create_series "<topic>" --template soap_opera`

## Outputs
- `output/episodes.json` — Single Source of Truth für ALLE weiteren Stages

## Review-Gate danach
episodes.json ist als Ganzes editierbar (Themen umformulieren, Stimmen
tauschen, section_words anpassen). Prüfen mit:
`python3 -m fabrik.cli.generate_episode check --series the_curator_s_masterwork`
