# Stage 01c — Episoden

Nur für `CASE_BASED_TEMPLATES` (crime_drama, soap_opera).

## Inputs
- Layer 4: `../01a_canon/output/canon.json` (Threads, Cast, Orte, Format)
- Layer 4: `../01b_arc/output/arc.json` (Wendepunkt-Zuteilung, Figure/Theme
  aller Episoden — nicht nur der eigenen, für Kontinuitäts-Kontext)
- Layer 3 (global): `templates/{{TEMPLATE}}/EPISODE_PROMPT.md`

## Process
EIN Claude-Call PRO EPISODE, alle parallel (`ThreadPoolExecutor`, wie
bisher die Batches) — jeder Call sieht `canon.json` + `arc.json` + seine
eine Episode, aber NIE die von anderen Episoden bereits generierten
Sections. Keine Batches mehr, also keine Batch-Grenze, an der die
Section-Tiefe kippen könnte (siehe Referenz-Tabelle in
`docs/konzept-stage-umbau.md`, T0.3). Pro Section wird deterministisch
geprüft, dass `what` im vorgegebenen Detailtiefe-Band liegt UND alle
Sections einer Episode im selben Band bleiben (ersetzt das alte
Post-hoc-Gate `check_section_detail` durch eine Prüfung, die VOR der
Übernahme greift, nicht danach). Retry mit Fehler-Feedback,
Best-Effort-Fallback wie bisher.

Ausgeführt automatisch als dritter Schritt von `create_series.py`, direkt
nach 01b; die N Episoden-Ergebnisse werden danach zu `episodes.json`
zusammengesetzt (Kanon-Top-Level-Felder + `threads` + `episodes[]`).

## Outputs
- `output/episodes.json` — **Single Source of Truth für ALLE weiteren
  Stages.** Enthält `threads` (aus canon.json übernommen) und pro Episode
  `figure`/`theme` (aus arc.json), `intro_note`/`outro_note`,
  `sections: [{title, what, who, thread, location, words}]`,
  `case: [{label, character_knowledge}]`.

Nach dieser Teilstage wird `canon.json`/`arc.json` von keiner weiteren
Stage mehr gelesen — alle drei Fakten-Ebenen sind in `episodes.json`
zusammengeführt.

## Review-Gate danach

`episodes.json` ist als Ganzes editierbar (wie bisher). Prüfen mit:
`python3 -m fabrik.cli.generate_episode check --series {{SLUG}}`

**Reconciliation-Hinweis:** Ein zusätzlicher, einmaliger Check NACH allen
01c-Aufrufen liest `arc.json` (falls noch vorhanden) gegen die fertigen
`sections`, um zu erkennen, ob ein Wendepunkt versehentlich in mehr als
einer Episode erzählt wurde (Doppel-Klimax) oder in keiner (verloren
gegangen) — Details: `fabrik/cli/CLAUDE.md`. Bei Handkorrekturen an
Sections nach diesem Punkt: kein erneuter automatischer Check, außer
`generate_episode check --fix` wird explizit erneut aufgerufen.
