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

- [ ] **T0.1 Commit des Ist-Stands.** Der Working Tree trägt die
      17.07.-Fixes (Runner-`boolflag_off`, Reparatur-Dispatcher,
      Abriss-Erkennung, Checkpoint-Schlüssel, Geister-Review-Fix,
      `check_section_detail`). Erst committen, dann umbauen.
- [ ] **T0.2 Reparaturlauf abwarten.** `generate_episode all --no-audio
      --fix` über seven_seats/founding/glasshouse muss durch sein, sonst
      kollidieren Handkorrekturen mit laufenden Part-Reparaturen.
- [ ] **T0.3 Referenz-Datensatz einfrieren.** Die Section-Tiefen-Messung
      über alle 15 Serien als Tabelle in dieses Dokument, damit nach dem
      Umbau vergleichbar ist, ob 01c die Granularität wirklich stabilisiert.

### Phase 1 — Verträge schreiben (reine .md-Arbeit, gefahrlos)

- [ ] **T1.1** `templates/_workspace/stage_01_CONTEXT.md` wird Routing über
      die drei Teilstages.
- [ ] **T1.2** Drei neue Vertrags-MDs: `stage_01a_CONTEXT.md`,
      `stage_01b_CONTEXT.md`, `stage_01c_CONTEXT.md` — je Inputs / exakte
      Ausgabeform / Review-Gate.
- [ ] **T1.3** `templates/soap_opera/` + `templates/crime_drama/`: den
      Creator-Prompt in drei Prompt-Dateien zerlegen
      (`CANON_PROMPT.md`, `ARC_PROMPT.md`, `EPISODE_PROMPT.md`). Die
      übrigen vier Templates (narration, media_analysis, language_course,
      shorts) bleiben einstufig — sie haben keine Threads und kein
      Batch-Problem.
- [ ] **T1.4** `templates/CLAUDE.md` + `fabrik/cli/CLAUDE.md` nachziehen.

### Phase 2 — Schema (Code, aber ohne Generierung)

- [ ] **T2.1** `config.py`: `case_canon`/`threads` als Top-Level-Feld
      zulassen (heute in `VALID_TOP_KEYS` verboten und vor dem Speichern
      gelöscht); Validator dafür.
- [ ] **T2.2** `config.py`: Section-Objekt validieren (`what` Pflicht, `who`
      gegen `voices`, `thread` gegen `threads`, `location` gegen
      `locations`) — String-Sections weiter akzeptieren (Bestandsserien).
- [ ] **T2.3** Helfer `section_text(section)` in `fabrik/core/` — gibt bei
      Alt-Strings den String zurück, bei Objekten die erzählte Fassung.
      Die acht Lesestellen (`script_writer` ×5, `podcast_maker`,
      `sfx_plan`, `thumbnail_writer`, `location_prompts`) darauf umstellen.
- [ ] **T2.4** `build_case_file_block`: Label gegen `threads` auflösen, mit
      Fallback auf per-Episoden-Fakten (Alt-Serien).

### Phase 3 — Generierung (das Herzstück)

- [ ] **T3.1** `generate_canon()` + Validator + Retry (ersetzt
      `generate_skeleton_with_retry` teilweise).
- [ ] **T3.2** `generate_arc()` + Validator (Zuteilung eindeutig, Threads
      existieren) + Retry.
- [ ] **T3.3** `generate_episode_concept(n)` — ein Aufruf pro Episode,
      parallel über `ThreadPoolExecutor` (Muster aus
      `generate_series_batched` wiederverwenden, inkl. Checkpoint).
- [ ] **T3.4** Checkpoint auf die neue Struktur (canon/arc/episode-N
      einzeln); Schlüssel wie heute aus den Aufruf-Parametern
      (`_checkpoint_key`, NICHT aus dem substituierten Prompt).
- [ ] **T3.5** Die 227 Zeilen löschen (Tabelle oben) und den Batch-Apparat
      ausbauen.

### Phase 4 — Der eine verbleibende Check

- [ ] **T4.1** In `validate_parts`: Sprechtext ohne einen einzigen
      Buchstaben (`—`), Platzhalter-Text (`placeholder`/`TODO`/`TBD`),
      Nicht-ASCII außerhalb der Serien-Sprache, Markdown-Marker. Alles
      retryable, alles deterministisch. Belege: `seven_seats` ep2/ep6,
      `the_glasshouse_vote` ep2/ep5.

### Phase 5 — Verifikation

- [ ] **T5.1 Mini-Serie** (2 Episoden, soap_opera) durch alle drei
      Teilstages, `generate_episode check`, ein Skript schreiben.
- [ ] **T5.2 Echte Serie** (10 Episoden, soap_opera) — der Fall, der heute
      gescheitert ist. Messen: Section-Tiefe pro Episode (Ziel: gleichmäßig
      ≥ 13, keine Batch-Signatur), `turning_points` je genau einmal gespielt,
      Kanon-Drift strukturell unmöglich.
- [ ] **T5.3** Vergleich gegen T0.3 in dieses Dokument schreiben.

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
