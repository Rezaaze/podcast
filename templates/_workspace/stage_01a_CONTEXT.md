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
- `output/canon.json` — `series_title`, `language`, `mode`, `template`,
  `writer_persona`, `style_guidelines`, `voices`, `locations` (nur
  soap_opera), `format`, `generation`, `audio`, `output_prefix`,
  `series_intro`, `series_outro`, `threads`

`threads` ist die EINE Stelle, an der die Fakten jedes Handlungsstrangs
stehen (`label`/`solution`/`objective_facts`) — 01b und 01c referenzieren
sie nur noch über `label`, erfinden sie nie neu. crime_drama trägt genau
EINEN Thread (der eine durchgehende Fall der Staffel), soap_opera 2 bis 4
gleichzeitig laufende.

## Review-Gate danach

`canon.json` ist vor 01b editierbar (Stimmen tauschen, Thread-Fakten
schärfen, Orte anpassen) — Änderungen hier wirken auf die ganze Staffel,
weil 01b/01c sie als festen Kontext bekommen. Keine automatische Prüfung
vor 01b nötig; offensichtliche Fehler (fehlendes `label`, doppelte Voice)
fängt 01b beim Einlesen.
