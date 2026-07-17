# Stage 01b — Staffelbogen

Nur für `CASE_BASED_TEMPLATES` (crime_drama, soap_opera).

## Inputs
- Layer 4: `../01a_canon/output/canon.json` (Threads, Cast, Format)
- Layer 3 (global): `templates/{{TEMPLATE}}/ARC_PROMPT.md`

## Process
EIN Claude-Call teilt jeden Thread-Wendepunkt genau EINER Episode zu und
legt pro Episode Titel (`figure`) + Thema (`theme`) fest — das ist der
Trick, der Kanon-Drift auf 0 gebracht hat (`threads` in canon.json), jetzt
auf EREIGNISSE angewandt: solange zwei Episoden nie unabhängig denselben
Wendepunkt beanspruchen dürfen, kann kein Doppel-Klimax entstehen.
Deterministisch geprüft (Retry mit Fehler-Feedback): jeder `thread`
existiert in `canon.threads`, jede `episode` liegt im Bereich, kein
`event` doppelt, jede Episode hat ≥1 Wendepunkt oder ist ausdrücklich als
Atempause markiert.

Ausgeführt automatisch als zweiter Schritt von `create_series.py`, direkt
nach 01a.

## Outputs
- `output/arc.json` — `turning_points: [{thread, episode, event}]` +
  `episodes: [{episode, figure, theme, breather?}]`

`arc.json` geht in JEDEN 01c-Prompt (jede Episode sieht die volle
Zuteilung, nicht nur ihre eigene) — das verhindert, dass zwei Episoden
denselben Wendepunkt für sich beanspruchen, ohne dass sie sich gegenseitig
sehen müssten.

## Review-Gate danach

`arc.json` ist vor 01c editierbar (Wendepunkt in eine andere Episode
verschieben, Titel/Thema schärfen, Atempausen markieren). Wendepunkte
NICHT von Hand duplizieren oder streichen, ohne den betroffenen Thread in
`canon.json` gegenzuprüfen — 01c generiert sonst eine Episode, die einen
inzwischen verwaisten Wendepunkt erzählen soll.
