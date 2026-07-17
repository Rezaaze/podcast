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
| 01a — Kanon | `stage_01a_CONTEXT.md` | `01a_canon/output/canon.json` |
| 01b — Staffelbogen | `stage_01b_CONTEXT.md` | `01b_arc/output/arc.json` |
| 01c — Episoden | `stage_01c_CONTEXT.md` | `01c_episodes/output/episodes.json` |

Jede Teilstage baut auf der vorigen auf (Kanon → Bogen → Episoden) und hat
ihr eigenes Review-Gate — zwischen den Teilstages darf von Hand editiert
werden, genau wie zwischen den nummerierten Haupt-Stages. Nur
**`01c_episodes/output/episodes.json`** ist die Single Source of Truth für
Stage 02+; `canon.json`/`arc.json` werden danach nicht mehr gelesen (ihre
Fakten/Zuteilungen sind in `episodes.json` eingeflossen — `threads` steht
dort weiterhin top-level, `arc.json` selbst nicht).

Ausgeführt von: `python3 -m fabrik.cli.create_series "<topic>" --template
{{TEMPLATE}}` — das CLI erkennt `CASE_BASED_TEMPLATES` selbst und
durchläuft alle drei Teilstages automatisch in einem Aufruf; die Aufteilung
ist intern (Checkpointing, Review-Gates), nicht drei separate CLI-Befehle.

## Review-Gate danach

`01c_episodes/output/episodes.json` ist als Ganzes editierbar (Themen
umformulieren, Stimmen tauschen, section_words anpassen). Prüfen mit:
`python3 -m fabrik.cli.generate_episode check --series {{SLUG}}`
