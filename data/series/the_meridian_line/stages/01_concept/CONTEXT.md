# Stage 01 — Konzept

Nur für `CASE_BASED_TEMPLATES` (crime_drama, soap_opera) in drei
Teilstages zerlegt — Begründung: `docs/konzept-stage-umbau.md`. Die
anderen vier Templates (narration, media_analysis, language_course,
shorts) haben keine Threads/kein Batch-Problem und laufen weiterhin als
EIN Claude-Aufruf über `python3 -m fabrik.cli.create_series` direkt in
`output/episodes.json` — für sie gilt dieser Routing-Vertrag nicht, ihre
`episodes.json` entsteht ohne Teilstages.

## Teilstages (case-based Templates)

| Teilstage | Vertrag | Output |
|---|---|---|
| 01a — Kanon | `stage_01a_CONTEXT.md` | Checkpoint `canon.json` (kein Workspace-File) |
| 01b — Staffelbogen | `stage_01b_CONTEXT.md` | Checkpoint `arc.json` (kein Workspace-File) |
| 01c — Episoden | `stage_01c_CONTEXT.md` | `output/episodes.json` |

Jede Teilstage baut auf der vorigen auf (Kanon → Bogen → Episoden), läuft
aber automatisch INNERHALB EINES `create_series`-Aufrufs weiter — wie
vorher Skeleton+Batches, keine drei separaten CLI-Befehle und kein
Pausenpunkt zwischen den Teilstages. `canon.json`/`arc.json` sind reine
Checkpoints unter `data/.create_series_staging/` (Wiederaufsetzen bei
Abbruch), keine editierbaren Workspace-Dateien. Nur **`output/
episodes.json`** ist die Single Source of Truth für Stage 02+ und das
tatsächliche Review-Gate — `threads` steht dort top-level, die
Wendepunkt-Zuteilung aus `arc.json` ist in `figure`/`theme`/`sections`
jeder Episode eingeflossen.

Ausgeführt von: `python3 -m fabrik.cli.create_series "<topic>" --template
soap_opera` — das CLI erkennt `CASE_BASED_TEMPLATES` selbst und
durchläuft alle drei Teilstages automatisch in einem Aufruf.

## Review-Gate danach

`output/episodes.json` ist als Ganzes editierbar (Themen umformulieren,
Stimmen tauschen, section_words anpassen). Prüfen mit:
`python3 -m fabrik.cli.generate_episode check --series the_meridian_line`
