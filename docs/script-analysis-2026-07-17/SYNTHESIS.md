# Gesamtsynthese: Skript-Analyse aller 12 Produktions-Serien (17.07.2026)

Methode: deterministische Checks über alle 112 Skripte (Wortbudgets,
Struktur, Sprecher, SFX-Hörbarkeit) + volle Tiefenlektüre jeder Episode
durch je einen Analyse-Agenten pro Serie, bewertet gegen den
Pipeline-Stand ihrer Entstehungszeit. Detail-Reports:
`per_series/<slug>_REPORT.md` in diesem Ordner.

## Ranking

| Datum | Serie | Urteil | korrigierbare Fehler | Kontinuitätsfehler |
|---|---|---|---|---|
| 17.07 | first_do_harm (shorts) | **8** | 7 | 2 |
| 11.07 | vanishing_signal | **7** | 21 | 10 |
| 13.07 | the_long_fare | 6 | 17 | 8 |
| 14.07 | the_curator_s_masterwork | 6 | 35 | 14 |
| 15.07 | borrowed_pulse | 6 | 22 | 12 |
| 16.07 | amity_hollow | 6 | 18 | 12 |
| 12.07 | chain_of_custody | 5 | 26 | 16 |
| 15.07 | the_understudy | 5 | 26 | 14 |
| 16.07 | discharged_cured | 5 | 34 | 15 |
| 16.07 | negative_space | 5 | 30 | 15 |
| 10.07 | facades | 4 | 22 | 16 |
| 16.07 | cured_by_design | 4 | 25 | 14 |

Summe: **283 korrigierbare Fehler**, davon **148 Kontinuitätsfehler**.

## Die 6 systemischen Muster (nach Schwere)

### 1. Konzept-Drift in episodes.json — die Wurzelursache Nr. 1 (NICHT gelöst, eher verschärft)
In 9 von 11 soap-Serien mutieren die case-Blöcke der episodes.json selbst
über die Staffel: Täter-/Zeugennamen, Alter, Beweisstücke, Zeitangaben und
sogar Geschlechter werden pro Episode oder pro Erzeugungs-Charge neu
erfunden statt fortgeschrieben (cured_by_design: 4 Direktorennamen on air;
discharged_cured: Täter Walter→Edmund→Arthur; borrowed_pulse: Drift exakt
an den Batch-Grenzen Ep1-3/4-6/7-9/10; amity_hollow: Drift pro
Episoden-PAAR). Der Skript-Writer schreibt die Widersprüche dann treu ab.
**Review + Beat-Layer haben das Problem nur verlagert:** facades (10.07)
driftete auf Skript-Ebene, die neuen Serien driften auf Konzept-Ebene —
`generate_series_batched` reicht den Kanon früherer Batches nicht bindend
weiter, und kein Check prüft case-Blöcke episodenübergreifend.

### 2. Finale-Amnesie
4 Serien vergessen im Finale vorherige Episoden: the_understudy hat den
Klimax DOPPELT mit entgegengesetztem Ausgang (Ep9 Verhaftung, Ep10 Täter
frei + erschossen); chain_of_custody Ep10 spult Ep8/9 zurück; the_long_fare
Ep10 resettet die Verfolgung; negative_space Ep7 vergisst das
Mid-Season-Reveal aus Ep5. Ursache: Section-Kontext = nur vorige Section,
Beats sehen nur die Beats der VORHERIGEN Episode — das Finale kennt den
tatsächlichen Stand von Ep8/9 nicht.

### 3. TTS-Hazards — Fehler, die man HÖRT (höchste Fix-Priorität bei Neu-Vertonung)
- **NARRATOR leakt interne Labels:** thread-Labels wörtlich vorgelesen
  (curator 22×, discharged_cured 11× inkl. "Scene Eleven",
  chain_of_custody 9× "The Captain's Ledger thread continues") — teils
  spoilernd ("Frame-Up" leakt Unschuld).
- **Falsche Stimme:** Nebenfiguren-Zeilen unter fremdem Sprecher-Tag
  (Bartender als ZOE_HAN, Empfangsdame als DIANA_CHEN, Reporter als PIKE,
  Verteidigerin als REID …) — in 5 Serien.
- **Mitgesprochene Regieanweisungen:** untagged Prosa/Klammer-Anweisungen,
  die das TTS als Dialog rendert (first_do_harm Ep5, the_long_fare Ep9 P4
  3×, cured_by_design 13 Stellen).

### 4. LLM-Review-Gate ist fast blind
Über alle Serien: Dutzende reale Fehler, aber die REVIEWs melden fast
immer "Keine Auffälligkeiten" (cured_by_design 8/8 leer trotz 25 Fehlern;
amity_hollow 7/8 leer trotz ~18). Die wenigen echten Funde wurden zudem
NICHT gefixt (first_do_harm 2/2 unbehoben, curator 1/1 unbehoben) — die
Serien liefen offenbar ohne `--fix`. Das Review prüft außerdem nur
episodenintern gegen den case — episodenübergreifende Fakten sieht es
strukturell nicht.

### 5. LLM-Tics / Phrasen-Inflation
"barely audible" (57× long_fare, 31× vanishing_signal), style "quiet"
134× (discharged_cured), "fifty years" 41×, "ten years" 75×, "Not yet"
als Szenenschluss 33× (understudy), wortgleiche Deflection-Sätze 4-10×.
Dazu Szenen-Templates in Schleife (5 fast identische Ritual-Szenen).

### 6. Wortbudget-Unterschreitungen (bekannt, unkritisch)
13-25 pro Serie über alle Generationen — das dokumentierte
Best-Effort-Fallback-Verhalten; inhaltlich meist dünn geplante Szenen.

## Was die Pipeline-Evolution GEBRACHT hat (Stärken)

- **SFX-Hörbarkeits-Regel (14.07): voller Erfolg** — 42-66 schlechte Cues
  pro Serie davor, 1-12 danach; amity_hollows 12 sind größtenteils nur ein
  "…, then silence"-Suffix-Tic.
- **shorts-Template (17.07): auf Anhieb die sauberste Serie** (8/10, 0
  deterministische Befunde, Hook/NARRATOR/Sting-Regeln fast perfekt).
- **Dialog-/Szenenhandwerk konstant hoch** über ALLE Generationen:
  unterscheidbare Figurenstimmen, Subtext statt Exposition, starke
  Antagonisten (Voss, Cipher, Han, Boru, Moorhouse), elegante
  Stimmen-Ökonomie (einseitige Telefonate, Narrator-Paraphrasen).
- **Editier-Vertrag/hides-Disziplin (16.07) greift:** Geheimnisse werden
  gezeigt statt ausgeplaudert; Wissens-Slices episodenintern fast fehlerfrei.
- **Beat-Treue hoch** (chain_of_custody 1:1 verifiziert) — die Beats selbst
  sind gut, ihr Input (case-Blöcke) ist das Problem.
- Recaps: nur 1 echter Ausfall in 97 Pflicht-Episoden (chain_of_custody
  Ep4); 2 der 3 deterministischen Flags waren Regex-Fehlalarme.

## Empfohlene Pipeline-Fixes (verhindern die Fehlerklassen künftig)

1. **Kanon-Weitergabe im Batch-Pfad:** `generate_series_batched` muss die
   case-Blöcke/Namen/Daten des ersten Batches als BINDENDEN Kanon in alle
   Folge-Batch-Prompts geben + deterministischer Nachlauf-Check
   (Namen/Zahlen-Diff über die case-Blöcke aller Episoden).
2. **Kanon-Datei für den Skript-Writer:** ein kompaktes, wachsendes
   FACTS.md (Namen, Daten, Orte, Zeitachse, Stand je Episodenende) als
   Prompt-Zusatz — schließt Finale-Amnesie und Zeitachsen-Drift.
3. **Deterministischer TTS-Hazard-Check in validate_parts:** (a) Prosa
   ohne Sprecher-Tag mitten im PART = Fehler, (b) NARRATOR-Zeilen gegen
   thread-Labels der episodes.json greppen, (c) Regieanweisungs-Heuristik
   (kurze 3.-Person-Sätze mit Figurennamen im eigenen Tag).
4. **Review-Gate härten:** Cross-Episode-Facts in den Review-Prompt
   (Kanon-Datei mitgeben); prüfen, ob light_model für das Review zu
   schwach ist; `--fix` standardmäßig aktivieren.
5. **Phrasen-Frequenz-Check** (deterministisch, gratis): Top-N-n-Gramme
   über die Staffel zählen, Ausreißer als Warnung in den Retry/Review.

## Fix-Aufwand pro Serie (Top-Prioritäten der Agenten)

Bereits vertont (facades, vanishing_signal, chain_of_custody — Alt-Layout,
fertig gerendert): Fixes lohnen nur bei geplanter Neu-Vertonung.
Neueste Generation (16./17.07, vermutlich noch nicht/teilweise vertont):
hier zuerst fixen — cured_by_design (Kanon-Patch ~15 Zeilen + Ep8-Reparatur),
discharged_cured (3 Namens-Patches + Sprecher-Fix Ep2),
negative_space (Ep7-Anschluss + Cold-Case-Vereinheitlichung),
amity_hollow (Enkelin/Lian/Finale-Geographie),
first_do_harm (2 Kleinst-Edits Ep5 + hides-Entscheidung Ep3).
Die vollständigen priorisierten Listen mit PART-Nummern und Zitaten stehen
in den Einzel-Reports.
