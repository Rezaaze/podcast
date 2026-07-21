# Stage 01a — Kanon

Nur für `CASE_BASED_TEMPLATES` (crime_drama, soap_opera).

## Inputs
- Topic-Brief des Users (CLI-Argument, nicht persistiert)
- Layer 3 (global): `templates/{{TEMPLATE}}/CANON_PROMPT.md`
- Layer 3 (global): `data/figure_history.json` — bereits verwendete Figuren

## Process
EIN Claude-Call entwirft Welt, Cast, Orte (nur soap_opera) und die
Fakten-Threads der Staffel — noch KEINE Episoden, keine Sections, keine
Wendepunkt-Zuteilung. Strukturvalidierung + Retry-Schleife mit
Fehler-Feedback (gleiches Muster wie bisher `generate_with_retry`).

Ausgeführt automatisch als erster Schritt von:
`python3 -m fabrik.cli.create_series "<topic>" --template {{TEMPLATE}}`

## Outputs
- Checkpoint (kein Workspace-File): `data/.create_series_staging/<hash>/
  canon.json` — `series_title`, `language`, `mode`, `template`,
  `writer_persona`, `style_guidelines`, `voices`, `locations` (nur
  soap_opera), `format`, `generation`, `audio`, `output_prefix`,
  `series_intro`, `series_outro`, `threads`

`threads` ist die EINE Stelle, an der die Fakten jedes Handlungsstrangs
stehen (`label`/`solution`/`objective_facts`) — 01b und 01c referenzieren
sie nur noch über `label`, erfinden sie nie neu. crime_drama trägt genau
EINEN Thread (der eine durchgehende Fall der Staffel), soap_opera 2 bis 4
gleichzeitig laufende.

## Kein separates Review-Gate

01a/01b/01c laufen automatisch nacheinander INNERHALB EINES
`create_series`-Aufrufs (wie zuvor Skeleton+Batches) — `canon.json`
selbst ist nur ein Checkpoint zum Wiederaufsetzen bei einem Abbruch, kein
von Hand editierbares Zwischenprodukt. Der tatsächliche Review-Gate bleibt
wie bisher die fertige `episodes.json` nach 01c (siehe stage_01c_CONTEXT.md)
— `threads`/`case`/Sections sind dort vollständig zusammengeführt.
