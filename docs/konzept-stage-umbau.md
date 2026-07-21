# Konzept-Stage-Umbau: Stage 01 zerlegen, Checks löschen

Stage 01 (`create_series.py`) entwirft heute die komplette Serie in EINEM
Claude-Aufruf — Welt, Cast, Casting, Staffelbogen und alle ~90 Szenen
gleichzeitig; bei großen Serien zerfällt der Aufruf in mehrere Batches, die
einander nicht sehen. Dieser Umbau zerlegt die Stage in drei kleine, je für
sich prüfbare Teilstages mit eigenem MD-Vertrag — und löscht dabei die
Prüf-Maschinerie, die es nur gibt, weil die Vorgabe bisher zu lose war.

Branch: `mwp-umbau` (Folgearbeit nach `docs/mwp-umbau-plan.md`).

## Der Befund (Datenlage 17.07.2026)

Die Analyse der drei am 17.07. erzeugten Serien plus die Nachmessung über
alle 15 Produktionsserien ergab drei Dinge, die alle auf Stage 01 zeigen:

1. **Die Section-Tiefe ist eine Eigenschaft des BATCHES, kein Zufall pro
   Episode** — und der stärkste verfügbare Prädiktor für Skript-Qualität.
   `the_understudy` (Batches 1-3/4-6/7-9/10): Ø 12.4/12.8/12.8 —
   4.2/4.0/3.8 — 6.9/7.0/7.2 — 22.5 Wörter pro Section. Innerhalb jedes
   Batches konstant, zwischen den Batches Faktor 6. Dasselbe in
   `the_glasshouse_vote` (ep1-6 Ø 18-23, ep7-10 Ø 3.7-4.1, Bruch exakt an
   der Grenze ep6/ep7) und spiegelbildlich in `the_founding_collection`
   (ep1-3 Ø 8-10, ep4-8 Ø 21-29). `seven_seats` ist gleichmäßig (Ø 15-25)
   und die sauberste Serie. Die Fehlerdichte folgt invers: glasshouse hat
   praktisch alle schweren Fehler in ep7-10, founding ~39 in ep1-4 gegen 2
   in ep8. Zwischen Ø 8 und Ø 13 liegt in den Daten NICHTS — es ist kein
   Regler, sondern ein Kippschalter: erzählte Szene oder blanker Titel.
2. **Der Kanon fixiert Fakten, nicht Ereignisse.** `case_canon` brachte die
   Kanon-Drift auf 0 (alle Threads über alle Episoden eine `solution`-
   Fassung). Trotzdem spielt `the_glasshouse_vote` Declans Geständnis
   zweimal: ep9 §5 heißt `"Declan's Turn"`, ep10 §4 heißt `"The Ledger Laid
   Bare"` — beide Titel lesen sich gleich gut als "Declan legt die Bücher
   offen", und sie stammen aus zwei verschiedenen Batches, die einander nie
   sehen. Kein Check konnte das fangen: die Fakten sind ja in beiden
   Fassungen identisch, `check_case_drift` steht auf 0. `the_understudy`
   hatte zwei Tage früher exakt dieselbe Signatur (Doppel-Klimax ep9/ep10,
   ep9 aus dem dünnen Batch, ep10 aus dem reichen).
3. **Der Vertrag ist dort am dünnsten, wo die Entscheidungen fallen.**
   `stage_01_CONTEXT.md`: 21 Zeilen, Process = "Claude entwirft die
   komplette Serie in einem Schuss". `stage_02_CONTEXT.md`: 82 Zeilen. Die
   Stage, die nur ausführt, ist viermal genauer spezifiziert als die, die
   alles festlegt. Alle schweren Fehler des Tages entstanden in Stage 01;
   Stage 02 hat ein fehlerhaftes Konzept treu abgeschrieben. Der Beat-Layer
   hat die Kollision sogar BEMERKT (ep10s Beats schreiben "He tells the
   board everything *this time*"), konnte sie aber nicht auflösen — er muss
   für jede Section aus episodes.json Beats liefern und darf keine
   streichen.

Die MD-Vorgaben sind dabei nicht falsch. `EPISODES_CREATOR_PROMPT.md`
verlangt wörtlich `"section title 1 (scene description, name which thread it
belongs to)"`. Das Modell lieferte `"The Ledger Laid Bare"`. Die Vorgabe war
korrekt — nur unverbindlich, weil ein freier String beides erlaubt.

## Ehrliche Einordnung: was der Umbau bringt (und was nicht)

**Bringt:** drei Fehlerklassen wechseln von "wird überwacht" zu "ist nicht
darstellbar" — Kanon-Drift (es gibt nichts mehr zu duplizieren),
Doppel-Klimax (jeder Wendepunkt ist genau einer Episode zugeteilt, und die
Zuteilung steht in jedem Folge-Prompt), Titel-statt-Szene (`what` ist
Pflichtfeld). Netto **−227 Zeilen Prüfcode**. Kleinere Antworten pro Aufruf
senken zusätzlich den Abriss-Druck, der den ganzen Batch-Apparat überhaupt
nötig gemacht hat.

**Bringt NICHT:** gegen Modell-Schluder hilft keine Vorgabe — `问题` mitten
im englischen Satz, `kititchen`, `placeholder` unter fremdem Sprecher-Tag.
Das ist kein Interpretationsspielraum, das ist Rauschen. Dafür bleibt genau
EIN billiger deterministischer Check (Nicht-ASCII/Markdown/Platzhalter im
Sprechtext, T4.1). Einer, kein wachsender Stapel.

**Kostet:** mehr Claude-Aufrufe in Stage 01 (bei einer 10er-Serie ~12 statt
4), dafür kleine und gleichmäßige; sie laufen parallel wie die Batches
heute, die Laufzeit bleibt vergleichbar. `create_series.py` wird faktisch
neu geschrieben. Bestandsserien bleiben unangetastet (Fallunterscheidung
beim Lesen, kein Migrationslauf).

## Ziel-Layout: Stage 01 in drei Teilstages

```
stages/01_concept/
  CONTEXT.md            Routing über die drei Schritte
  01a_canon/
    CONTEXT.md          Vertrag: Welt, Cast, Orte, Threads
    output/canon.json
  01b_arc/
    CONTEXT.md          Vertrag: Wendepunkte, je EINER Episode zugeteilt
    output/arc.json
  01c_episodes/
    CONTEXT.md          Vertrag: Sections als Objekte, gegen canon+arc
    output/episodes.json   <- bleibt Single Source of Truth für Stage 02+
```

Jede Teilstage: ein Claude-Aufruf mit kleiner Antwort, eigener Validator,
eigene Retry-Schleife mit Fehler-Feedback (Muster wie heute), eigenes
Review-Gate zum Handeditieren. Der MD-Vertrag jeder Teilstage nennt Inputs,
die EXAKTE Ausgabeform und das Gate — kurz und genau statt lang und
ungefähr.

### 01a — Kanon (ein Aufruf, klein)

`canon.json`: `series_title`, `language`, `mode`, `template`,
`writer_persona`, `style_guidelines`, `voices`, `locations`, `format`,
`generation`, `audio`, `series_intro`, `series_outro` — plus:

```json
"threads": [
  { "label": "The Missing Dues",
    "solution": "…",
    "objective_facts": ["…"] }
]
```

**Die Fakten stehen ab hier genau einmal.** Kein `apply_case_canon`, kein
`check_case_drift`, kein `_reconcile_case_canon_from_siblings`.

### 01b — Staffelbogen (ein Aufruf, klein)

`arc.json`: pro Thread die Wendepunkte, jeder genau EINER Episode zugeteilt.

```json
"turning_points": [
  { "thread": "The Missing Dues", "episode": 9,
    "event": "Declan confesses the six-year theft to the board" }
]
```

Plus pro Episode `figure` + `theme` (das heutige Skeleton). Deterministisch
prüfbar: jeder `thread` existiert in `canon.json`; jede `episode` liegt im
Bereich; kein `event` doppelt; jede Episode trägt mindestens einen
Wendepunkt oder ist ausdrücklich als Atempause markiert.

`arc.json` geht in JEDEN 01c-Prompt. Das ist derselbe Trick, der bei den
Fakten die Drift auf 0 gebracht hat — nur auf Ereignisse angewandt.

### 01c — Episoden (ein Aufruf PRO EPISODE, parallel)

Keine Batches mehr, also keine Batch-Grenzen, an denen die Granularität
kippt. Jeder Aufruf sieht `canon.json` + `arc.json` + seine eine Episode.

```json
"sections": [
  { "title": "Corner Diner",
    "what": "Liwei meets Iggy Chen for the first time in person, eager to prove the co-op will move fast",
    "who": ["LIWEI_CASTELLAN", "IGGY_CHEN"],
    "thread": "The Missing Dues",
    "location": "CORNER_DINER",
    "words": null }
]
```

- `what` ist **Pflicht** → ein Titel ist keine gültige Section mehr.
- `who` muss Cast-Rollen aus `canon.json` nennen → eine Szene mit einer
  Nicht-Cast-Figur fällt im Konzept auf, statt später als `placeholder`
  unter fremdem Tag zu landen (`seven_seats` ep2).
- `thread` muss ein `canon.threads[].label` treffen → erfundene Labels
  sterben sofort.
- `location` und `words` wandern INS Objekt → die drei heute per Index
  gekoppelten Parallel-Arrays (`sections` / `section_words` /
  `section_locations`) und ihre Längenprüfungen entfallen.

Episoden tragen weiterhin `case` als Liste von `{label,
character_knowledge}` — also genau das, was das Modell im Batch-Pfad ohnehin
schon liefert. `solution`/`objective_facts` werden NICHT mehr hineinkopiert.

## Was gelöscht wird

| Funktion | Datei | Zeilen | wird überflüssig durch |
|---|---|---|---|
| `apply_case_canon` | create_series.py | 47 | 01a: Fakten stehen einmal |
| `check_case_drift` | create_series.py | 69 | 01a: nichts zu driften |
| `_reconcile_case_canon_from_siblings` | create_series.py | 29 | 01a: Kanon bleibt erhalten |
| `check_section_detail` | create_series.py | 44 | 01c: `what` ist Pflichtfeld |
| `check_section_words_gaps` | create_series.py | 38 | 01c: `words` im Section-Objekt |
| **Summe** | | **227** | |

Dazu schrumpft `validate_case_block` (70 Zeilen): Fakten werden einmal in
`canon.json` geprüft statt pro Episode. `build_skeleton_prompt` /
`validate_skeleton` / `generate_batch_with_retry` / `compute_batch_size` /
`BATCH_PARALLEL_CAP` / die Halbierungs-Rekursion werden von 01b/01c abgelöst.

**Bleibt und muss bleiben:** `validate_data` (das Schema selbst),
`validate_parts` (Wortbudget/Format), `response_looks_truncated`,
`find_narrator_leaks`, die drei LLM-Reviews. Das sind Prüfungen gegen ein
Modell, nicht gegen selbstgemachte Redundanz.

## Phasen und Tasks

### Phase 0 — Absichern

- [x] **T0.1 Commit des Ist-Stands.** Der Working Tree trug die
      17.07.-Fixes (Runner-`boolflag_off`, Reparatur-Dispatcher,
      Abriss-Erkennung, Checkpoint-Schlüssel, Geister-Review-Fix,
      `check_section_detail`) — committet (17.07., "Ist-Stand vor
      Stage-01-Umbau").
- [x] **T0.2 Reparaturlauf abwarten.** Keine `generate_episode --fix`-
      Prozesse liefen mehr (geprüft via `ps aux`) — nichts zu kollidieren.
- [x] **T0.3 Referenz-Datensatz einfrieren.** Section-Tiefe pro Episode
      (Ø `count_length_units` je Section) über alle Case-based-Serien
      (`soap_opera`/`crime_drama`/`shorts`) mit vorhandener episodes.json,
      Stand 17.07.2026 — Basis für den Vergleich in Phase 5 (T5.3).
      Faktor = max/min innerhalb der Serie; ≥3 markiert als Batch-Cliff
      (deckt sich mit dem Befund oben: kein Gradient, ein Kippschalter).

      | Serie | Template | Eps | min | max | Faktor | Section-Tiefe pro Episode |
      |---|---|---|---|---|---|---|
      | chain_of_custody | soap_opera | 10 | 3.0 | 32.1 | **10.7** ⚠️ | 21.8, 20.5, 20.6, 23.2, 21.7, 21.8, 3.8, 3.6, 3.0, 32.1 |
      | mwp_smoke | soap_opera | 10 | 3.0 | 32.1 | **10.7** ⚠️ | 21.8, 20.5, 20.6, 23.2, 21.7, 21.8, 3.8, 3.6, 3.0, 32.1 |
      | the_long_fare | soap_opera | 10 | 3.5 | 23.0 | **6.5** ⚠️ | 21.5, 20.2, 23.0, 14.5, 14.8, 16.2, 3.9, 3.5, 4.4, 17.7 |
      | the_understudy | soap_opera | 10 | 3.8 | 21.5 | **5.7** ⚠️ | 12.4, 12.7, 12.6, 4.2, 4.0, 3.8, 6.9, 7.0, 7.2, 21.5 |
      | the_glasshouse_vote | soap_opera | 10 | 3.7 | 23.4 | **6.4** ⚠️ | 18.3, 21.3, 23.4, 16.6, 20.9, 17.4, 4.1, 3.9, 3.9, 3.7 |
      | the_founding_collection | soap_opera | 8 | 7.2 | 27.3 | **3.8** ⚠️ | 9.5, 8.5, 7.2, 27.3, 23.8, 25.7, 20.5, 20.3 |
      | negative_space | soap_opera | 8 | 7.2 | 21.0 | 2.9 | 8.2, 7.2, 21.0, 19.4, 17.5, 16.4, 17.6, 18.9 |
      | borrowed_pulse | soap_opera | 10 | 8.1 | 20.8 | 2.6 | 19.1, 19.5, 20.8, 16.9, 16.9, 17.1, 8.5, 8.1, 8.2, 20.6 |
      | cured_by_design | soap_opera | 8 | 9.1 | 22.1 | 2.4 | 19.8, 21.1, 21.3, 22.1, 15.4, 13.6, 10.1, 9.1 |
      | amity_hollow | soap_opera | 8 | 13.6 | 25.3 | 1.9 | 17.7, 19.5, 24.0, 23.5, 14.9, 13.6, 23.1, 25.3 |
      | seven_seats | soap_opera | 6 | 14.0 | 24.2 | 1.7 | 16.2, 17.0, 14.0, 17.9, 21.7, 24.2 |
      | discharged_cured | soap_opera | 8 | 12.6 | 20.6 | 1.6 | 19.2, 20.4, 20.6, 19.4, 14.8, 12.6, 16.4, 16.8 |
      | the_curator_s_masterwork | soap_opera | 10 | 16.4 | 23.9 | 1.5 | 20.8, 20.2, 20.5, 16.9, 16.4, 18.9, 23.9, 23.5, 22.7, 23.8 |
      | vanishing_signal | soap_opera | 10 | 10.7 | 14.7 | 1.4 | 12.1, 11.3, 12.8, 10.9, 10.7, 10.8, 10.7, 12.8, 11.6, 14.7 |
      | facades | soap_opera | 10 | 23.4 | 31.3 | 1.3 | 27.8, 28.2, 25.2, 26.5, 25.2, 23.4, 27.0, 26.2, 26.0, 31.3 |
      | the_wildrose_inheritance | soap_opera | 2 | 32.5 | 38.7 | 1.2 | 38.7, 32.5 |
      | first_do_harm | shorts | 5 | 37.7 | 42.7 | 1.1 | 42.7, 37.7, 40.7, 41.0, 38.3 |
      | stitched | shorts | 2 | 29.0 | 31.0 | 1.1 | 31.0, 29.0 |

      5 von 17 Serien tragen den Batch-Cliff (Faktor ≥3) — deckungsgleich
      mit dem im Befund oben genannten Sample. `mwp_smoke` ist eine
      1:1-Kopie von `chain_of_custody` (Smoke-Test-Fixture), zählt separat
      mit, weil beide unabhängig regeneriert werden könnten.

### Phase 1 — Verträge schreiben (reine .md-Arbeit, gefahrlos)

- [x] **T1.1** `templates/_workspace/stage_01_CONTEXT.md` wird Routing über
      die drei Teilstages.
- [x] **T1.2** Drei neue Vertrags-MDs: `stage_01a_CONTEXT.md`,
      `stage_01b_CONTEXT.md`, `stage_01c_CONTEXT.md` — je Inputs / exakte
      Ausgabeform / Review-Gate. Korrigiert nach Phase-3-Erkenntnis:
      canon.json/arc.json sind Checkpoint-Zwischenstand, kein eigenes
      Workspace-Review-Gate (siehe dort).
- [x] **T1.3** `templates/soap_opera/` + `templates/crime_drama/`: den
      Creator-Prompt in drei Prompt-Dateien zerlegt
      (`CANON_PROMPT.md`, `ARC_PROMPT.md`, `EPISODE_PROMPT.md`), alte
      `EPISODES_CREATOR_PROMPT.md` in Phase 3 gelöscht (erst nachdem der
      Code sie nicht mehr brauchte). Die übrigen vier Templates bleiben
      einstufig.
- [x] **T1.4** `templates/CLAUDE.md` + `fabrik/cli/CLAUDE.md` nachgezogen
      (Phase 1 UND nochmal vollständig in Phase 3, als der tatsächliche
      Code stand).

### Phase 2 — Schema (Code, aber ohne Generierung) ✅ abgeschlossen 17.07.2026

- [x] **T2.1** `config.py`: `threads` als Top-Level-Feld zugelassen
      (`VALID_TOP_KEYS`); Validator reicht durch `validate_case_block`.
      (`case_canon` bewusst NICHT aufgenommen — das war ein rein
      Batch-internes Konzept, das mit dem Batch-Apparat in Phase 3
      komplett entfiel.)
- [x] **T2.2** `config.py`: Section-Objekt-Form validiert (`is_section_list`/
      `is_object_section_list`, `what` Pflicht, `who` gegen `voices`,
      `thread` gegen `threads`, `location` gegen `locations`, `words`
      wiederverwendet `validate_words_value`) — String-Sections bleiben
      gültig, 17 Bestandsserien gegengeprüft (0 neue Fehler).
- [x] **T2.3** `fabrik/core/sections.py` (neu): `section_text`/
      `section_title`/`section_location`/`section_words_override`. Alle 8
      Lesestellen umgestellt: `script_writer.py` (×7 Stellen, nicht ×5 wie
      geschätzt — `resolve_section_cfg`, `build_beats_prompt`,
      `build_section_prompt`, `generate_episode_meta`, Hauptschleife,
      `_generate_sections_parallel`), `podcast_maker.py`
      (`get_section_locations`), `sfx_plan.py` (`collect_sections`),
      `thumbnail_writer.py`. `location_prompts.py` liest entgegen der
      ursprünglichen Annahme gar kein `section_locations` (nur den
      Top-Level-`locations`-Block) — keine Änderung nötig.
- [x] **T2.4 entfällt ersatzlos** — siehe Phase-3-Log: Fakten-Injektion
      passiert beim episodes.json-Zusammenbau (Ersatz für
      `apply_case_canon`), nicht bei jedem `build_case_file_block()`-Lese-
      zugriff. `episode.case[]` trägt dadurch schon vollständig
      `solution`/`objective_facts`, `build_case_file_block` blieb
      unangetastet.

### Phase 3 — Generierung (das Herzstück) ✅ abgeschlossen 17.07.2026

- [x] **T3.1** `generate_canon()` + `validate_canon()` + Retry.
- [x] **T3.2** `generate_arc()` + `validate_arc()` (Zuteilung eindeutig,
      Threads existieren, kein Event doppelt, jede Episode Wendepunkt oder
      `breather`) + Retry.
- [x] **T3.3** `generate_episode_concept(n)` — ein Aufruf pro Episode,
      parallel über `ThreadPoolExecutor` (`EPISODE_CONCEPT_PARALLEL_CAP=4`).
- [x] **T3.4** Checkpoint auf die neue Struktur: `_cached_unit()`
      verallgemeinert `_cached_batch` für canon/arc/episode-N einzeln,
      Schlüssel weiterhin `_checkpoint_key()` aus den Aufruf-Parametern.
- [x] **T3.5** Die 227 Zeilen (plus Batch-Apparat: `compute_batch_size`,
      `build_skeleton_prompt`/`validate_skeleton`/
      `generate_skeleton_with_retry`, `generate_batch_with_retry`,
      `generate_series_batched`, `EXPAND_BATCH_PROMPT`) gelöscht.
      **Design-Abweichung ggü. Plan:** `threads` ist jetzt bei BEIDEN
      Templates eine Liste (crime_drama: genau 1 Eintrag statt eines
      Einzelobjekts) — vereinheitlicht die Section-`thread`-Validierung
      gegen `threads[].label` ohne Template-Fallunterscheidung im Schema.
      Fakten-Injektion (`solution`/`objective_facts` aus `canon.threads` in
      jedes `episode.case[]`) ersetzt `apply_case_canon()` beim Zusammenbau
      in `generate_case_based_series()` — `build_case_file_block()` musste
      dafür NICHT angefasst werden (T2.4 entfiel dadurch ersatzlos).

### Phase 4 — Rausch-Check + Reconciliation-Pass ✅ abgeschlossen 17.07.2026

- [x] **T4.1** `find_noise()` in `validate_parts`: Sprechtext ohne
      Buchstaben, Platzhalter (`placeholder`/`TODO`/`TBD`), Markdown-Reste,
      fremdsprachige Zeichen (Han/Hiragana-Katakana/Hangul) außerhalb der
      Serien-Sprache. Retryable, deterministisch. Gegen 236 Parts aus
      seven_seats + the_understudy getestet: 1 echter Fund (Interpunktion-
      only-Zeile), 0 False Positives.
- [x] **Ergänzung ggü. ursprünglichem Plan** (aus separater Recherche zu
      vergleichbaren Long-Form-Generierungsproblemen, siehe Session vom
      17.07.2026): `check_turning_point_coverage()` — Reconciliation-Pass
      NACH allen 01c-Calls, ein LLM-Judge liest `arc.json` gegen die
      fertigen Sections, mit 5x Self-Consistency-Voting (FlawedFictions-
      Muster) gegen Judge-Rauschen. Fügt sich unverändert in
      `repair_series()` ein.

### Phase 5 — Verifikation ✅ abgeschlossen 17.07.2026

- [x] **T5.1 Mini-Serie** (2 Episoden, soap_opera, `common_grounds`) durch
      alle drei Teilstages, `generate_episode check` grün, Skript für
      Episode 1 tatsächlich geschrieben (Beats + 4 Sections parallel,
      Metadaten) — sauberer, gut lesbarer Dialog, keine Format-/Noise-
      Funde. Reconciliation-Check: 5/5 Voting-Läufe sauber.
- [x] **T5.2 Echte Serie** (10 Episoden, soap_opera, `the_meridian_blend`,
      genau der Fall, der im Ein-Schuss-/Batch-Modus zuverlässig
      scheiterte) — Kanon + Bogen je ein Call, alle 10 Episoden-Konzepte
      im ERSTEN Versuch erfolgreich (keine Retries nötig), Reconciliation-
      Check 5/5 Voting-Läufe sauber ("jeder Wendepunkt genau einmal
      erzählt"), Inhalts-Review fand 2 echte Akzent-Casting-Befunde (keine
      False Positives), `generate_episode check` grün.
- [x] **T5.3 Vergleich gegen T0.3:**

      | Serie | Eps | min avg | max avg | Faktor |
      |---|---|---|---|---|
      | **the_meridian_blend (NEU, 01a/01b/01c)** | 10 | 19.3 | 26.2 | **1.35** |
      | facades (beste Alt-Serie) | 10 | 23.4 | 31.3 | 1.3 |
      | chain_of_custody (schlechteste Alt-Serie) | 10 | 3.0 | 32.1 | 10.7 |

      `the_meridian_blend` liegt auf dem Niveau der BESTEN Alt-Serie —
      ohne dass irgendein Batch-Mechanismus mehr existiert, der eine
      Section-Tiefe-Grenze ziehen könnte. Kanon-Drift strukturell
      verifiziert unmöglich (`solution` pro Thread: exakt 1 distinkter Text
      über alle 10 Episoden, programmatisch geprüft). Kontinuität nicht
      separat gemessen (kein Vorher-Nachher-Datenpunkt verfügbar), aber
      kein Hinweis auf das im Plan befürchtete Risiko in den beiden
      generierten Skripten.

## Rückwärtskompatibilität

Alt-Serien (`sections` als String, `case` mit per-Episoden-Fakten, kein
`threads`) bleiben lesbar: `section_text()` reicht Strings durch,
`build_case_file_block` fällt auf die Episoden-Fakten zurück,
`validate_data` akzeptiert beide Formen. Kein Migrationslauf, kein Stichtag.
Die 15 Bestandsserien laufen unverändert weiter — sechs davon tragen den
Section-Defekt (`the_understudy` 6/10 Episoden, `the_glasshouse_vote` 4/10,
`the_long_fare` 3/10, `borrowed_pulse` 3/10, `the_founding_collection` 2/8,
`negative_space` 2/8), drei davon sind bereits vertont. Der Umbau repariert
sie NICHT; er verhindert die nächste.

## Risiken

- **Mehr Aufrufe = mehr Fehlerquellen pro Lauf.** Gegenmittel: der
  Checkpoint (T3.4) macht jeden Teilschritt einzeln wiederaufsetzbar — heute
  schon der wichtigste Zeitretter, künftig noch feingranularer.
- **01c pro Episode könnte Kontinuität VERSCHLECHTERN**, weil kein Aufruf
  mehr die Nachbarepisoden im Volltext sieht. Gegenmittel: `arc.json` ist
  genau dieser geteilte Kontext, und es ist verbindlicher als die heutigen
  Skeleton-Themen. Muss in T5.2 gemessen werden — wenn die Kontinuität
  leidet, ist der Ausweg 01c mit Nachbar-Kontext (vorherige+nächste Episode
  als Kurzfassung), nicht zurück zu Batches.
- **Das Section-Objekt berührt acht Lesestellen.** Gegenmittel: `section_text()`
  als einziger Zugriffspunkt (T2.3); die Lesestellen ändern sich einzeilig.
- **Scope-Falle:** narration/media_analysis/language_course/shorts NICHT
  mitumbauen. Sie haben keine Threads, kein Batch-Problem und legitime
  Titel-Sections ("The Hook & The Man with a Thousand Faces"). Der Umbau
  gilt nur für `CASE_BASED_TEMPLATES`.
