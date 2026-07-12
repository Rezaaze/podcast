# Stage 02 — Skripte

## Inputs
- Layer 4: `../01_concept/output/episodes.json` (Episoden, Sections, case,
  Wortbudgets, Stimmen)
- Layer 3 (Serie): `../../references/PROMPT_TEMPLATE.md` — das
  Skript-Prompt dieser Serie
- Bei `use_beats`: eigene `output/ep<N>_BEATS.txt` der Vorepisode
  (Kontinuität)

## Process
Pro Section ein Claude-Call (Retry mit Fehler-Feedback, Wortbudget-
Validierung, Best-Effort-Fallback). Optional Beats vorab und Episode-Review
(`--fix`) danach. Details: `fabrik/writing/CLAUDE.md`.
Ausgeführt von: `python3 -m fabrik.cli.generate_episode N|all --series {{SLUG}} [--fix]`

## Outputs
- `output/ep<N>.txt` — Skript mit `--- PART k ---`-Markern
- `output/ep<N>_META.txt` — Titel/Beschreibung (ID3/Upload)
- `output/ep<N>_BEATS.txt`, `_BEATS_REVIEW.txt`, `_REVIEW.txt` (optional)
- `output/ANTHOLOGY_META.txt` (Serien-Meta, bei Anthologie-Formaten)

## Review-Gate danach
Skripte sind reine Textdateien — Dialogzeilen umschreiben ist erlaubt und
erwünscht (Format `[SPEAKER | style: ...]` bzw. Fließtext beibehalten).
Gelöschte PART-Dateien/-Abschnitte werden beim Re-Run neu generiert;
existierende bleiben unangetastet.
