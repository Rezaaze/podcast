# fabrik/cli — Entry-Points

Aufruf immer als Modul vom Projekt-Root: `python3 -m fabrik.cli.<name>`
(das WebUI macht exakt das via `"module"`-Einträge in
`webui/config.py::COMMANDS`). Alle CLIs außer create_series/import_story
(die legen neue Serien an und schreiben LATEST) akzeptieren
`--series <slug>`; ohne wird `data/series/LATEST` genutzt (oder die
einzige Serie).

| CLI | Zweck | braucht |
|---|---|---|
| create_series | episodes.json via Claude erzeugen | claude CLI |
| import_story | fertigen Text als Serie importieren | claude CLI |
| generate_episode | Skripte schreiben (`check`/`N`/`all`) | claude CLI |
| podcast_maker / batch | vertonen (eine/alle Episoden) | .venv + ffmpeg + TTS-Server |
| character_prompts / location_prompts / cover_art | Bild-Prompts (+ PNGs bei OPENAI_API_KEY) | claude CLI (Bilder: stdlib urllib, kein venv) |
| episode_thumbnails | dramatisches, spoilerfreies Poster-Thumbnail pro Episode (16:9 + 1:1) | claude CLI (Bilder: stdlib urllib, kein venv) |
| highlight_clips | Teaser-Highlights (30–90s) für 9:16-Clips auswählen | claude CLI |
| sfx_plan | SFX-Cues kuratieren: Palette + Platzierung + Lautstärke | claude CLI |
| sfx_assets / location_ambience | die Sounds dazu generieren (ElevenLabs) | ELEVENLABS_API_KEY, stdlib urllib |
| library_audit | Near-Miss-Kandidaten in den Asset-Bibliotheken auflisten (reine Anzeige) | stdlib-only |

## create_series.py

**⚠️ In Umbau (Branch `mwp-umbau`, Plan: `docs/konzept-stage-umbau.md`):**
für `CASE_BASED_TEMPLATES` wird der Ein-Schuss-/Batch-Mechanismus unten
durch drei kleine, aufeinander aufbauende Calls ersetzt (Kanon → Bogen →
Episoden einzeln parallel) — Vertrag bereits geschrieben
(`templates/_workspace/stage_01{a,b,c}_CONTEXT.md`,
`templates/{crime_drama,soap_opera}/{CANON,ARC,EPISODE}_PROMPT.md`), der
Generierungscode in `create_series.py` (unten beschrieben) läuft zum
Zeitpunkt dieses Absatzes noch auf dem ALTEN Batch-Pfad — dieser Abschnitt
wird erst nach Phase 3 des Umbau-Plans überschrieben, nicht schon jetzt,
um keine Dokumentation zu schreiben, die dem tatsächlichen Code
widerspricht.

`python3 -m fabrik.cli.create_series "Topic" [--episodes N] [--minutes M]
[--locations L] [--template T] [--no-review] [--fix]`

`--template` nimmt jeden Ordnernamen unter `templates/` (kein argparse-
`choices`); aktuell: narration, media_analysis, language_course,
crime_drama, soap_opera, shorts.

- `--minutes` steuert die Episodenlänge: `estimate_section_count()` leitet
  die Section-Zahl aus minutes (WORDS_PER_MINUTE=150) und den
  `parts_per_section`/`words_per_part_target`-Literalen des Templates ab —
  kein Template hardcodet mehr eine Section-Zahl. Warnt laut bei
  unparsebaren Format-Werten. (media_analysis-Sonderfall: siehe
  templates/CLAUDE.md — dort skaliert --minutes nur die Wortziele.)
- `--locations` steuert, wie viele wiederverwendbare Szenen-Orte
  soap_opera erfindet; von Templates ohne Location-Support ignoriert.
- **`generate_with_retry` (MAX_ATTEMPTS=3):** ungültiges JSON,
  `validate_data`-Fehler UND falsche Episodenzahl werden wörtlich in den
  nächsten Versuch zurückgefüttert (gleiches Muster wie
  `call_claude_with_retry` beim Skript-Writer) — Count-Mismatch ist ein
  retryable ERROR, keine Warnung. Timeout/transienter CLI-Fehler ist
  ebenfalls retryable (ohne Feedback — es gibt nichts zu korrigieren);
  nur "claude not found"/"not logged in" brechen sofort ab.
- **Best-Effort-Fallback** (Gegenstück zu validate_parts' fallback_safe):
  sind alle Versuche schema-sauber und nur die Episodenzahl daneben, wird
  der Versuch mit der nächstliegenden Zahl genommen statt abzubrechen —
  nur ein echter validate_data-Fehler disqualifiziert einen Versuch, ein
  falscher Count allein nie. `sys.exit(1)` nur, wenn über alle Versuche
  keiner fallback-sicher war.
- **`check_section_detail()` — Section-Tiefe als Retry-Gate (17.07.2026).**
  Nur für `CASE_BASED_TEMPLATES`: deren EPISODES_CREATOR_PROMPT.md verlangt
  wörtlich `"section title 1 (scene description, name which thread it belongs
  to)"`, während narration ausdrücklich einen TITEL will ("The Hook & The Man
  with a Thousand Faces") — der Check erzwingt also nur den Template-Vertrag,
  deshalb das Gate. Meldet jede Episode mit Ø < `SECTION_DETAIL_MIN_AVG_WORDS`
  (=10) Wörtern pro Section als retryable Fehler MIT Feedback
  (`SECTION_DETAIL_FEEDBACK` zeigt ein Positiv- und drei Negativbeispiele);
  läuft im Ein-Schuss-Pfad (`generate_with_retry`, fallback-SICHER, geht aber in
  `badness` ein, damit der Best-Effort den erzähltesten Versuch nimmt) UND pro
  Batch (`generate_batch_with_retry`, `start_num=start` → echte Episodennummer).
  **Bewusst NICHT in `config.validate_data()`:** das ist ein
  Generierungs-Qualitätsgate, kein Schema. Dort eingebaut wären 6 von 11
  Bestands-Soap-Serien ab sofort ungültig und `generate_episode` würde sie
  verweigern.

  **Warum das die zweitwichtigste Wurzelursache ist** (Nachmessung 17.07.2026
  über 15 Produktionsserien): die Section-Tiefe ist der stärkste verfügbare
  Prädiktor für Skript-Qualität — und sie ist eine Eigenschaft des BATCHES, kein
  Zufall pro Episode. `the_understudy` (Batches 1-3/4-6/7-9/10): Ø 12.4/12.8/12.8
  — 4.2/4.0/3.8 — 6.9/7.0/7.2 — 22.5. Innerhalb jedes Batches konstant, zwischen
  den Batches um den Faktor 6 verschieden; jeder Batch ist eben ein eigener
  Claude-Aufruf und nichts fixierte die Granularität. Dasselbe Muster in
  `the_glasshouse_vote` (ep1-6 Ø 18-23, ep7-10 Ø 3.7-4.1) und spiegelbildlich in
  `the_founding_collection` (ep1-3 Ø 8-10, ep4-8 Ø 21-29). Die Fehlerdichte folgt
  invers: glasshouse ~alle schweren Fehler in ep7-10, founding ~39 in ep1-4 vs. 2
  in ep8, `seven_seats` (gleichmäßig Ø 15-25) die sauberste Serie.
  **Der Kausalpfad:** aus `"Declan's Turn"` (ep9) und `"The Ledger Laid Bare"`
  (ep10) kann kein Writer ableiten, welche der beiden das Geständnis tragen soll
  — beide Titel lesen sich gleich gut als "Declan legt die Bücher offen", und die
  zwei Batches sehen einander nie (nur das gemeinsame Skeleton). Ergebnis: das
  Geständnis wird zweimal gespielt. `case_canon` verhindert das NICHT — es
  fixiert Fakten (Täter/Beweise/Daten), nicht die Ereignis-Zuteilung; deshalb ist
  `check_case_drift` bei 0, während der Klimax doppelt läuft: die Zahlen stimmen
  ja in beiden Fassungen. Genau dieselbe Signatur hatte `the_understudy` zwei
  Tage früher (Doppel-Klimax ep9/ep10, ep9 dünn/ep10 reich) — unbemerkt, weil
  nichts danach suchte. Der Beat-Layer BEMERKT die Kollision übrigens (ep10s
  Beats schreiben "He tells the board everything *this time*"), kann sie aber
  nicht auflösen: er muss für jede Section aus episodes.json Beats liefern und
  darf keine streichen.
- **`check_section_words_gaps()` läuft IMMER** (auch mit `--no-review`:
  lokal, gratis, deterministisch): flaggt bei soap_opera jedes
  `section_words.min`, das weniger als `SECTION_WORDS_MIN_GAP=80` Wörter
  unter `format.words_per_part_min` liegt. Produktions-Lektion: ein
  "sharp confrontation"-Override mit nur 10–20% Abschlag ließ den
  Skript-Writer zuverlässig unterschießen — dieselben Sections failten
  über alle Eskalationsstufen, bis der Override selbst als Ursache
  identifiziert war. Das soap_opera-Creator-Prompt wurde entsprechend
  verschärft (kurzer Beat = ~100–200 Wörter, kein kosmetischer Rabatt);
  der Check ist das Sicherheitsnetz, falls das Planungsmodell es doch tut.
- **`review_series`** (LLM, skippbar via `--no-review`): Spoiler vor dem
  Finale, Widersprüche objective_facts/character_knowledge,
  Accent-Casting-Regel, Episoden-Überlappung, und (Check 5) dieselbe
  section_words-Diskrepanz in Prosaform — als Zweitschicht behalten, war
  aber für den numerischen Fall allein unzuverlässig (übersah in einem
  echten 10-Episoden-Review ALLE Instanzen), daher hat der
  deterministische Check Priorität. Findings sind warn-only —
- **AUSSER mit `--fix`:** `repair_series()` behebt die gemeldeten Findings
  (Format seit 17.07.2026: `[{"episodes": [int, ...], "problem": str}]`,
  liefert `review_series()` UND `check_case_drift()` gleichermaßen).
  **Dispatcher-Logik: Befunde werden nach Geltungsbereich AUFGETEILT** und
  jede Gruppe mit dem kleinstmöglichen Aufruf repariert (die Schritte bauen
  aufeinander auf, der zweite sieht das Ergebnis des ersten):
  1. Befunde MIT Episodennummer → `_repair_series_episodes()`: schickt nur
     die BETROFFENEN Episoden (plus ein kompakter Serien-Index aus
     Figur/Thema/Thread-Labels der übrigen als Kontext), analog zu
     `repair_part()`/`apply_episode_fixes()` beim Skript-Writer, nur auf
     episodes.json-Ebene. Danach `_reconcile_case_canon_from_siblings()`:
     erzwingt, dass `solution`/`objective_facts` der reparierten Episoden zur
     ersten UNVERÄNDERTEN Episode desselben Thread-Labels passen (ersetzt
     `apply_case_canon()`, das hier nicht mehr greift — `case_canon` ist zu
     diesem Zeitpunkt längst aus `data` entfernt).
  2. Befunde OHNE Episodennummer (Akzent-Casting über `voices` & Co.) →
     `_repair_series_globals()`: schickt NUR die Top-Level-Felder ohne
     `episodes` (ein paar KB statt >100 KB). Harte Prompt-Regel: die
     Rollen-KEYS in `voices` bleiben identisch — die Episoden referenzieren
     sie in `character_knowledge` und werden hier nicht angefasst;
     `validate_data()` fängt eine Umbenennung zusätzlich ab.
  3. Nur was Schritt 1/2 NICHT hinbekommen haben → `_repair_series_full()`,
     der alte Weg, der die KOMPLETTE episodes.json in einem Call neu ausgibt.
     Reines Auffangnetz. Bei nur teilweisem Erfolg gibt `repair_series()` den
     bereits verbesserten Stand zurück (nicht None) — Teilerfolge zu
     verwerfen wäre schlechter als sie zu behalten.

  **Warum die Aufteilung (Bugfix 17.07.2026, Nutzer-Symptom "bei 10 Episoden
  gibt es Probleme"):** vorher entschied der Dispatcher am SCHWÄCHSTEN
  Befund — ein einziger Fund ohne Episodenbezug kippte ALLE Befunde in den
  vollen Umbau. Da Akzent-Casting konstruktionsbedingt nie eine
  Episodennummer trägt (es hängt am Top-Level-`voices`), landete praktisch
  jeder `--fix`-Lauf im Komplettumbau. Der hat weder Kanon-Slimming noch
  Batch-Aufteilung, muss >100 KB ausgeben und riss bei 10 Episoden
  zuverlässig ab — nach drei Minuten Generierung bis zu 90 Minuten
  scheinbarer Stillstand (3 × `compute_timeout(10)`=1800s blinde Retries).
  6–8 Episoden liefen durch, weil das Dokument dort noch ~70–90 KB groß ist.
  Gemessen nach dem Fix (echte 10-Episoden-Serie, Spoiler-Fund in Ep. 7 +
  Akzent-Fund): 117s, beide Reparaturen im ersten Versuch, nur Episode 7
  verändert.
  **Abriss-Erkennung in ALLEN Reparatur-Pfaden:** `response_looks_truncated()`
  fehlte hier bis 17.07.2026 komplett (nur die Generierungspfade hatten sie).
  Jetzt brechen `_repair_series_episodes()` und `_repair_series_full()` beim
  ersten Abriss ab, statt ein Längenproblem blind mit Feedback zu wiederholen.
  Alle drei Wege re-validieren strukturell (eigene MAX_ATTEMPTS-Schleife,
  gleiches Feedback-Muster). Bekommt keiner eine gültige Korrektur hin, bleibt
  das Original unangetastet und die Findings werden gedruckt.
- **Checkpoint-Reihenfolge (Bugfix 17.07.2026):** der Batch-Checkpoint
  (siehe unten) wird ERST nach dem erfolgreichen Speichern der Serie
  gelöscht, nicht schon direkt nach Skeleton+Batches — Review und
  Reparatur laufen dazwischen und sind selbst potenziell lange
  Claude-Aufrufe; ein Abbruch dort hätte sonst die schon fertige
  Skeleton+Batch-Arbeit verloren.
- **Slug-Reservierung:** `paths.reserve_unique_series()` legt den Wurzelordner
  atomar an (`exist_ok=False`) — der leere Ordner IST die Reservierung und
  schließt die TOCTOU-Lücke bei mehreren parallelen Cockpits (`list_series()`
  sieht einen Ordner ohne episodes.json nicht, zwei Läufe mit demselben Titel
  hätten sonst denselben Slug gewählt). Schlägt Scaffolding/Schreiben danach
  fehl oder bricht der Nutzer ab, gibt `main()` die Reservierung per
  `shutil.rmtree` wieder frei (`except BaseException`, deckt auch
  KeyboardInterrupt/SIGTERM aus dem Cockpit ab) — sonst bliebe eine unsichtbare
  Leiche zurück, die den Slug dauerhaft verbrennt (nächste Serie desselben
  Titels hieße `..._2`). Aufgeräumt wird ausschließlich die eigene, gerade
  angelegte Reservierung. `import_story.py` nutzt weiterhin das ältere,
  nicht-atomare `paths.unique_slug()`.
- Creator-Templates tragen einen expliziten `{{FIGURE_HISTORY}}`-
  Platzhalter (`build_prompt` errort laut, wenn er fehlt UND der Legacy-
  ALREADY-USED-FIGURES-Regex nicht greift — kein stilles Auslassen).
- Timeout skaliert: `compute_timeout` = 180s/Episode, Floor 900s, Cap
  3600s. Heartbeat alle 20s via `run_claude_process` (fabrik/core).
- **Batch-Checkpoint (17.07.2026, Nutzer-Feedback "viel Ausfall/Zeitverlust"):**
  `generate_series_batched()` speichert Skeleton und jeden erfolgreichen Batch
  unter `data/.create_series_staging/<hash>/`. **Schlüssel = Hash der AUFRUF-
  Parameter** (Thema/Template/Episodenzahl/Minuten/Orte/Modell/case_based,
  `_checkpoint_key()`), berechnet in `main()` und an
  `generate_series_batched()` durchgereicht — dieselbe Funktion räumt den
  Ordner am Ende von `main()` wieder auf. **NICHT über den fertig
  substituierten Prompt hashen** (bis 17.07.2026 genau so, und dadurch in der
  Praxis wirkungslos): dort steckt via `build_prompt()` die komplette
  FIGURE_HISTORY drin — eine global wachsende Datei, die JEDER
  `generate_episode`-Lauf einer BELIEBIGEN anderen Serie fortschreibt. Bei
  mehreren parallelen Cockpits änderte sich der Prompt-Text im Minutentakt,
  der Hash mit ihm, und ein Rerun fand seinen eigenen Checkpoint nie wieder
  (Nutzer-Symptom 17.07.2026: "er generiert gerade das Skeleton wieder,
  warum?" — 7 fremde figure_history-Einträge in den 30 Min. seit dem
  Fehllauf). Inhaltlich veraltet der Checkpoint dadurch nicht: die Figuren
  dieser Serie sind längst gewählt, die Historie ist im Prompt nur eine
  "nimm diese nicht"-Liste; ein Treffer kann höchstens eine inzwischen
  woanders vergebene Figur wiederholen — dafür gibt es
  `history.warn_on_repeated_figures()`. Scheitert danach EIN Batch endgültig (alle Retries +
  Halbierungen erschöpft), bricht der Lauf wie bisher mit `sys.exit(1)` ab,
  aber ein **identischer** Rerun (`_cached_batch()`) lädt Skeleton und alle
  bereits erfolgreichen Batches von Platte und generiert nur noch den
  fehlenden Teil. **Gelöscht wird der Ordner ERST ganz am Ende von `main()`**,
  NACHDEM die Serie tatsächlich auf Platte geschrieben ist (nach
  `paths.write_latest(slug)`) — NICHT schon direkt nach erfolgreichem
  `generate_series_batched()`. Bugfix 17.07.2026 (Nutzer-Symptom: "kommt immer
  dieser Teil" bei jedem Abbruch+Neustart): `main()` lässt nach Skeleton+Batches
  noch Inhalts-Review und ggf. `--fix`-Reparatur laufen — beides eigene, oft
  lange Claude-Aufrufe. Ein zu früh gelöschter Checkpoint (ursprünglich direkt
  in `generate_series_batched()`) ließ einen Abbruch WÄHREND Review/Reparatur
  die komplette, bereits fertige Skeleton+Batch-Arbeit verlieren — bei jedem
  erneuten Versuch begann die teuerste Phase wieder bei null. Ein korrupter/
  unvollständiger Checkpoint-Eintrag blockiert nie (führt nur zur
  Neu-Generierung dieses einen Teils). Bewusst NUR im Batch-Pfad: der
  Ein-Schuss-Pfad (`generate_with_retry`) ist atomar (eine Antwort, ganz oder
  gar nicht) und fällt bei Scheitern ohnehin auf den Batch-Pfad zurück — dort
  gibt es keinen Teil-Fortschritt, der sich zu retten lohnt. Kein Flag zum
  Erzwingen einer Neu-Generierung nötig (jede Parameter-Änderung ändert den
  Hash automatisch); ein bewusst frischer Lauf trotz identischer Parameter:
  `rm -rf data/.create_series_staging/`.
- **Staffel-Kanon im Batch-Pfad (17.07.2026):** Wurzelursache Nr. 1 der
  12-Serien-Analyse (docs/script-analysis-2026-07-17/) war Konzept-Drift —
  jeder Batch erfand die case-Blöcke unabhängig neu (cured_by_design: vier
  Namen für denselben Antagonisten, Drift exakt an Batch-Grenzen; im
  Ein-Schuss-Pfad sind solutions dagegen wortgleich über alle Episoden).
  Fix in drei Schichten: (1) das Skeleton enthält bei CASE_BASED_TEMPLATES
  ein Pflichtfeld `case_canon` (Threads mit label/solution/objective_facts,
  EINMAL final festgelegt; `validate_skeleton(case_based=True)`); (2)
  `EXPAND_BATCH_PROMPT` verpflichtet jeden Batch auf wörtliche Kopie;
  (3) `apply_case_canon()` normalisiert nach dem Zusammensetzen
  deterministisch zurück (Code statt LLM-Hoffnung) und `case_canon` wird
  vor dem Speichern entfernt (kein episodes.json-Feld).
  `apply_case_canon()` matcht über das Label; ein Fall OHNE Label matcht einen
  Ein-Thread-Kanon (crime_drama: `case` ist ein einzelnes Objekt, ein Fall =
  ein Thread). Ein Thread MIT abweichendem Label matcht dagegen NIE, auch
  nicht bei nur einem Kanon-Thread (Fix 17.07.2026, vorher entschied allein
  die Anzahl): das ist keine fehlende Zuordnung, sondern eine Umbenennung —
  sie still zu kanonisieren gäbe dem Thread die richtigen Fakten unter dem
  FALSCHEN Namen, und weil das Ergebnis dann sauber aussieht, bliebe es
  unbemerkt (`check_case_drift` vergleicht Episoden untereinander, nicht
  gegen den Kanon: benennen alle Episoden einheitlich um, fällt es nirgends
  mehr auf).
  Seit dem Latenz-Umbau (ebenfalls 17.07.2026) geben Batches `solution`/
  `objective_facts` gar nicht mehr aus (nur label + character_knowledge) —
  `apply_case_canon()` injiziert sie mechanisch; das halbiert grob die
  Antwortgröße und damit das Abriss-Risiko. Threads ohne Kanon-Treffer
  (erfundenes/umbenanntes Label) werden laut gewarnt.
  **`check_case_drift(data)` läuft IMMER** (wie check_section_words_gaps,
  auch mit --no-review, auch im Ein-Schuss-Pfad): meldet abweichende
  solution/objective_facts pro Thread-Label und Einzel-Episoden-Labels
  (Umbenennungs-Verdacht); mit `--fix` gehen Befunde an `repair_series()`.
- **Batch-Pfad für große Case-Serien:** überschreiten crime_drama/
  soap_opera (`CASE_BASED_TEMPLATES`) zusammen
  `BATCH_THRESHOLD_EPISODE_MINUTES=120` Episodenminuten (17.07.2026 von
  200 gesenkt — der Graubereich riss im Ein-Schuss oft ab und verbrannte
  Minuten, bevor der Batch-Pfad ohnehin übernahm), weicht
  `skip_one_shot` auf `generate_series_batched` aus (episodes.json in
  mehreren Claude-Calls statt einem One-Shot am Output-Limit).
  **Abriss-Erkennung (`response_looks_truncated`):** eine lange, an keiner
  `{`-Position dekodierbare Antwort (oder ein "continuing in the next
  reply") ist ein Längen-, kein Inhaltsproblem — Feedback-Retries können
  das nie beheben. Der Ein-Schuss bricht dann sofort zum Batch-Pfad ab,
  ein Batch überspringt seine Restversuche und halbiert direkt.
  `compute_batch_size()` skaliert die Episoden/Batch nur mit Minuten — bei
  vielen `case`-Threads/`character_knowledge` (viele Rollen, viele parallele
  Storylines) skaliert der tatsächliche Output aber nicht rein
  minuten-proportional (siehe dessen Docstring), ein Batch kann also trotz
  "sicherer" Minutenzahl zu groß geraten. Beleg aus Produktion (16.07.2026):
  ein soap_opera-Batch von 2 Episoden lieferte wiederholt eine mehrere
  tausend Zeichen lange Antwort, die an KEINER `{`-Position vollständig
  dekodierbar war — klares Indiz für eine mitten in der Struktur
  abgeschnittene Antwort, nicht für API-Drosselung. **Deshalb halbiert
  `generate_batch_with_retry()` einen Batch automatisch**, wenn alle
  `MAX_ATTEMPTS` Versuche bei der aktuellen Größe scheitern (rekursiv, endet
  spätestens bei count=1) — ein kleinerer Batch braucht eine kürzere Antwort
  und bekommt sein eigenes frisches Versuchs-Budget, statt denselben zu
  großen Versuch blind zu wiederholen.
- **Systemweite Claude-Aufruf-Bremse:** `fabrik/core/claude_cli.py::
  _claude_slot()` begrenzt zusätzlich, wie viele `claude`-Subprozesse
  GLEICHZEITIG über alle Cockpits/Serien/Threads hinweg laufen dürfen
  (`PF_MAX_CONCURRENT_CLAUDE`, Default **20** — hoch angesetzt als reine
  Notbremse, siehe fabrik/core/CLAUDE.md: die ursprüngliche Sorge vor
  Account-Drosselung bei mehreren Cockpits war anhand echter Session-Logs
  NICHT belegbar, das tatsächliche Problem war die Batch-Halbierung oben).
  Kein Ersatz dafür, nur Ergänzung für den Fall, dass doch einmal echte
  Drosselung auftritt (erkennbar an `⚠️ Claude-CLI-Fehler`/`API-Fehler` mit
  429/rate_limit/overloaded im Text).

## generate_episode.py

- `check` — nur episodes.json validieren.
- `N [--force] [--no-fix] [--no-script-review]` — eine Episode; bei
  `"source": "imported"` wird die Generierung übersprungen und direkt
  `generate_episode_meta()` gerufen (Skript existiert schon).
- `all [--jobs N] [--force] [--no-fix] [--no-script-review]` — alle Episoden
  (Subprocess pro Episode), danach automatisch batch.py.
- **`--fix` ist seit 17.07.2026 DEFAULT** (`--no-fix` schaltet ab): alle 12
  analysierten Serien liefen ohne --fix, korrekt geflaggte Review-Befunde
  blieben deshalb unbehoben im vertonten Material. Der `all`-Pfad reicht
  die Entscheidung explizit als `--fix`/`--no-fix` an die Subprozesse durch.
- Nach `all` schreibt der Elternprozess `PHRASE_REPORT.txt` (deterministische
  Phrasen-/Style-Tic-Zählung, fabrik/writing/phrase_stats.py) neben die
  Skripte — reine Anzeige, Review-Gate.
- `--fix`/Review-Semantik und Beats: siehe fabrik/writing/CLAUDE.md.
- Jede Episode bekommt automatisch eine `<prefix>N_META.txt`
  (Titel/Beschreibung/Zuschauer-Frage, `script_writer.generate_episode_meta`)
  — die Frage ist bewusst spoilerfrei (ans Episoden-Thema/-Dilemma
  gebunden, aber ohne Auflösung/Twist), landet über
  `pipeline.parse_meta_file` in `batch.py::generate_upload_index` als
  „Frage an die Zuschauer" in `UPLOAD_INDEX.md` — dort zum Copy-Paste in
  Videobeschreibung/Community-Post. Ältere `_META.txt` ohne `FRAGE:`-Feld
  liefern `None` (kein Fehler, die Zeile fehlt dann nur im Index).

## import_story.py

Gegenstück zu create_series für fertigen Text (alte Romane etc.), bei dem
Claude nichts erfinden darf. **Nur narration-Mode.**

- Zwei Quellformen: Ordner (eine Datei = eine Episode, wörtlich) oder eine
  lange Datei (Auto-Split via Kapitelüberschrift-Regexes, Fallback
  absatzbewusster Wortzahl-Split, `textproc.chunk_prose_by_words`).
  Feintuning über `--split-on`, `--words-per-episode`,
  `--words-per-part-max`, `--parts-per-section`, `--language`,
  `--template`.
- Pro Episode genau EIN Claude-Call (`summarize_source_episode`, nur
  Titel+Theme, light_model); `--no-summary` schaltet auch den ab (dann
  null Claude-Calls). PART-Chunking deterministisch OHNE Minimum —
  der Quelltext diktiert seine Länge.
- Episoden bekommen `"source": "imported"`; podcast_maker/batch brauchen
  keinerlei Anpassung (lesen nur die fertige Skriptdatei). Beat-Layer wird
  strukturell übersprungen (kein Generierungspfad).

## character_prompts.py / location_prompts.py

- `character_prompts [--force]` →
  `data/series/<slug>/stages/04_visuals/output/characters/PROMPTS.txt`;
  mit `OPENAI_API_KEY` zusätzlich direkt `<ROLE>.png` via gpt-image-1-mini
  (`fabrik/writing/image_backends.py`, stdlib urllib, kein venv);
  `--no-images` erzwingt prompts-only. NARRATOR ausgenommen.
- Pro Rolle zusätzlich eine Variante je Emotion — `<ROLE>_<emotion>.png`
  für anger/fear/sadness/joy/surprise/love/vulnerability (spiegelt Lolfis
  EMOTIONS-Keys exakt; von Hand synchron gehalten, kein Shared Import).
  **Kostenbremse (16.07.2026):** `find_used_emotions()` scannt zwar weiter
  alle 7 möglichen Emotionen aus den Skripten, `MAX_EMOTIONS_PER_ROLE=4`
  behält davon pro Rolle nur die HÄUFIGSTEN (nicht projektweit dieselben 4
  für alle — eine Rolle mit Liebes-Subplot behält "love", auch wenn andere
  Rollen es nie brauchen). Fehlende Emotionen fallen wie bisher aufs
  Neutral-Porträt zurück (kein Crash, auch nicht bei einem externen
  Video-Export, der eine gestrichene Emotion abfragt).
- **Rerun-Fix:** eine vorhandene PROMPTS.txt blockiert den Lauf nicht mehr.
  Früher hieß "existiert" = "fertig" — die Datei entsteht aber auch im
  Text-only-Modus, also erreichte ein nachträglich gesetzter API-Key die
  Bildgenerierung nie. Jetzt: `parse_prompts_file()` liest die Blöcke
  zurück (tolerant gegen die `(→ characters/...)`-Annotation) und
  verwendet sie ohne redundanten Claude-Call wieder, außer es fehlen
  Blöcke, die die aktuellen Skripte brauchen (z. B. neue Emotion) — und
  fällt IMMER zur Bild-Schleife durch, die per Datei skippt, was existiert.
- `location_prompts [--force]` spiegelt das 1:1 pro Location-Key statt
  Rolle (1536x1024 Landscape — Video-Hintergrund, kein Porträt), gleiche
  Key-/`--no-images`-Logik. No-op mit Meldung, wenn episodes.json keine
  `locations` hat (nur soap_opera fragt danach).
- `cover_art [--force] [--no-copy]` erzeugt EIN Serien-Cover
  (`.../04_visuals/output/cover.png`); braucht zwingend `OPENAI_API_KEY`
  (kein prompts-only-Modus wie bei den beiden anderen).

## episode_thumbnails.py

Dramatisches, spoilerfreies Poster-Thumbnail pro Episode — kurze Hook-Zeile
(2–5 Wörter, movie-poster-artig) + ein Symbol-Motiv im Cover-Art-Stil (keine
Nahaufnahme-Gesichter, gleiche `masterpiece, painted lo-fi animation
style`-Stilfamilie), je einmal im Querformat (16:9, `1536x1024`, Video-
Upload) und quadratisch (1:1, `1024x1024`, Podcast-Episodenbild).

- **Läuft automatisch** am Ende jeder Episoden-Generierung
  (`fabrik/cli/generate_episode.py`, sowohl im normalen als auch im
  `"source": "imported"`-Zweig — direkt nach dem jeweiligen
  `generate_episode_meta`-Aufruf) — genau wie Titel/Beschreibung ein
  nice-to-have: ein Fehlschlag lässt die Episode NICHT scheitern. Ohne
  `OPENAI_API_KEY` wird der Schritt übersprungen (kein Fehler), sonst würde
  jeder Lauf ohne gesetzten Key als "fehlgeschlagen" markiert.
- Logik lebt in `fabrik/writing/thumbnail_writer.py` (NICHT in
  `script_writer.py` selbst — der Aufruf sitzt eine Ebene höher in
  `generate_episode.py`, weil `thumbnail_writer.py` `call_claude`/
  `MAX_RETRIES`/`RETRY_DELAY` aus `script_writer.py` importiert, wie
  `cover_art.py`/`location_prompts.py` es auch tun; ein Import in die
  Gegenrichtung wäre ein Zirkel-Import).
  **Ein Claude-Text-Call, zwei Bild-Calls:** ein Bildprompt wird EINMAL
  erzeugt (fürs Querformat UND das Quadrat gemeinsam formuliert — Fokuspunkt
  und Text zentriert genug für beide Crops) und dann für BEIDE Größen an
  gpt-image-1-mini geschickt.
- Hook-Zeile und Bildprompt laufen auf `light_model` (reine Text-/
  Prompt-Arbeit, kein kreatives Schreiben). Die Hook-Zeile bekommt dieselbe
  Spoilerfrei-Regel wie die Zuschauer-Frage aus `generate_episode_meta`
  (darf Ende/Twist/Auflösung nicht verraten), max. 40 Zeichen.
- Standalone: `python3 -m fabrik.cli.episode_thumbnails [--episode N]
  [--force] [--series SLUG]` — zum Nachholen (Key erst später gesetzt) oder
  gezielten Neu-Generieren einzelner Episoden, ohne das ganze Skript neu zu
  schreiben (`--episode`-Pattern wie `highlight_clips.py`). Anders als beim
  automatischen Pfad bricht das Standalone-CLI OHNE Key hart ab (`sys.exit`)
  — hier ist die Bildgenerierung der ganze Zweck des Aufrufs, kein
  Nebenprodukt.
- Ausgabe: `stages/04_visuals/output/thumbnails/<prefix>N_wide.png` +
  `<prefix>N_square.png`. Idempotent pro Datei: existiert eine der beiden
  Größen schon, wird nur die fehlende nachgeholt (kein `--force` nötig für
  einen reinen Teil-Fehlschlag-Retry).
- WebUI-Knopf: `#pf-step-thumbnails` (`pf_episode_thumbnails`, optionales
  Episoden-Nummer-Feld + `--force`-Checkbox, siehe webui/CLAUDE.md).

## highlight_clips.py

Wählt per Claude 1–3 Teaser-Highlights (30–90s) pro VERTONTER Episode und
schreibt `<Name>_FULL_EPISODE_HIGHLIGHTS.json` nach `stages/03_audio/output/`
— das Review-Gate vor Lolfis 9:16-Teaser-Render (`lofi_clips.py`).

- Input ist die `_SUBS.json` (satzweise Cues MIT Timing), nicht das Skript.
  Claude antwortet mit **Cue-INDEX-Bereichen** (`start_cue`/`end_cue`), nie
  mit rohen Zeiten — die Millisekunden rechnet das CLI aus den Cue-Grenzen
  (kein Halluzinations-Risiko, Snapping an Satzgrenzen garantiert).
- Validierung (1–3 Clips, Dauer 20–100s, Hook ≤90 Zeichen, keine
  Überlappung) wird bei Verstoß wörtlich ins Retry-Prompt zurückgefüttert
  (MAX_RETRIES aus script_writer); Timeout/API-Fehler retryable.
- Läuft auf `generation.model` (kreativ — narratives Urteil + Hook-Zeile),
  NICHT light_model; eigener 600s-Timeout (Prompt trägt hunderte Cues).
- Idempotent: vorhandene Datei wird nur gelistet, `--force` regeneriert.
  Lolfi liest NUR `clips[].start_ms/end_ms/hook` — Hand-Edits an den
  Zeiten überleben (Vertrag: Kopplungstabelle in Lolfi/CLAUDE.md).
- `parse_meta_file` ist lokal gespiegelt (Original in fabrik/audio/
  pipeline.py — für dieses venv-freie CLI tabu, Import-Regel).

## Die SFX-Kette: sfx_plan → podcast_maker → sfx_assets → Lolfi

**Was automatisch läuft:** `generate_episode all` ruft bei Drama-Serien
(`mode: "drama"`, also crime_drama/soap_opera — narration-Templates haben
keine SFX-Cues) `sfx_plan` selbst auf — nach den Skripten, VOR `batch`
(mit `--force`, wenn die Skripte neu generiert wurden). Das ist keine Bequemlichkeit, sondern Pflicht: der Plan entscheidet
über Lücken IN der Episoden-MP3, nachträglich geplant hätte er auf eine fertige
MP3 keinen Einfluss mehr. **`sfx_assets`/`location_ambience` laufen bewusst
NICHT automatisch** (ElevenLabs kostet pro Lauf) — sie werden von Hand
aufgerufen, bevor Lolfi rendert.

Nicht automatisch ist der Einzel-Episoden-Pfad: `generate_episode <N>` und
`podcast_maker` allein planen NICHT. Wer einzeln arbeitet, ruft `sfx_plan`
selbst auf, bevor er vertont — sonst laufen die Cues im Alt-Verhalten (auf dem
Zeilenstart, ohne Drops). Alle drei CLIs haben dafür Knöpfe im WebUI-Cockpit
(`#pf-step-sound`, siehe webui/CLAUDE.md).

`sfx_plan` ist der Schritt, der zwischen "Claude schreibt `[SFX: ...]` ins
Skript" und "ffmpeg legt eine MP3 auf ms X" lange gefehlt hat. Ohne ihn war
die Auswahl zwar nicht zufällig, aber auch kein Plan: jeder Cue-Freitext
wurde 1:1 an ElevenLabs geschickt, landete auf dem ERSTEN WORT der nächsten
Zeile und auf einer pauschalen Lautstärke.

`python3 -m fabrik.cli.sfx_plan [--force]` → `stages/02_scripts/output/
SFX_PLAN.json` (serienweit, aus den Skripten abgeleitet — deshalb bei den
Skripten und schon VOR dem Vertonen lauffähig). Der Plan ist ein
Review-Gate: von Hand editierbar. **Ohne `--force` ist der Lauf
inkrementell:** ein vorhandener Plan wird nur um Episoden ergänzt, die ihm
fehlen (neue Skripte, frühere Fehlschläge aus `unplanned_episodes`) —
geplante Episoden und Handkorrekturen bleiben unangetastet, die neuen
Episoden werden auf die vorhandene Palette verpflichtet. `--force` plant
ALLES neu (Handkorrekturen gehen verloren).

- **Ein Claude-Call pro Episode, Palette wächst mit** (seriell, wie der
  Beats-Vorlauf in generate_episode.py): Episode N sieht die Assets aus
  1..N-1 und wird auf Wiederverwendung verpflichtet — deshalb klingt der
  Türknall in Episode 7 wie der in Episode 1. Ein Call für die ganze Serie
  wäre am Output-Limit gescheitert (Produktionsserie: 793 Cues).
- Input ist ein durchnummeriertes **Cue-Inventar** (Cue + Zeile davor/
  danach), nicht das Skript; Claude antwortet mit Cue-INDIZES (Muster wie
  highlight_clips) und kann so keine Cues erfinden.
- Pro Cue: `keep` (Nicht-Geräusche wie "a beat, tension held" oder
  "X exhales, shaky" fliegen raus), `asset_key`, `placement`
  (`before`/`under`, siehe fabrik/audio/CLAUDE.md), `gain`.
  `MAX_KEPT_CUES_PER_PART=5` ist die Dichte-Bremse — als Prompt-Regel UND
  als Validierung, die in den Retry zurückgefüttert wird.
- **`duration_s`-Untergrenze (16.07.2026 gefixt):** `MIN_ASSET_SECONDS=0.5`
  (vorher 0.2) — die ElevenLabs Sound-Generation-API lehnt < 0.5s hart ab
  (400 "invalid_generation_settings"), der alte Prompt empfahl aber aktiv
  0.2-0.4s für kurze Kontaktgeräusche. `elevenlabs_backend.py::
  generate_sound_effect()` klemmt zusätzlich auf API-Ebene (deckt auch
  ältere, schon geschriebene Pläne mit zu kurzen Werten ab, ohne Neu-Planung
  — betroffene Serien laufen jetzt einfach durch).
- Das `locations`-Mapping geht mit ins Prompt, mit der Ansage, dass diese
  Orte bereits eine durchgehende Ambience-Schleife haben — Wind/Möwen/Regen
  werden dadurch verworfen statt doppelt zu klingen. Erstes Produktions-
  Ergebnis: von 15 Cues blieben 9, alle 6 Drops waren Atmosphäre, die die
  Location-Ambience schon trägt.
- **Der Plan ist optional.** Fehlt er (oder scheitert eine Episode: sie
  landet in `unplanned_episodes`), verhält sich die ganze Kette exakt wie
  vorher — Cue auf dem Zeilenstart, Lolfi hasht den Cue-Text. Nichts an
  bestehenden Serien bricht. Gescheiterte Episoden holt der nächste
  `sfx_plan`-Lauf (ohne `--force`) automatisch nach.
- **Stale-Guard:** der Plan adressiert Cues über ihre POSITION (episode,
  part, n-ter Cue im Part). Wird ein Skript neu generiert, kann an derselben
  Position ein ANDERER Cue stehen — `podcast_maker::resolve_cue` vergleicht
  deshalb zusätzlich den Cue-Text und ignoriert den Eintrag bei Abweichung
  (Warnung + Alt-Verhalten). Ein veralteter Plan kann also nie den falschen
  Sound platzieren, nur gar keinen. Kur: `sfx_plan --force`.
- **Dateinamen-Vertrag:** mit Plan liegt die MP3 unter
  `sfx_asset_hash(<Palette-Prompt>)`, NICHT unter dem Hash des Cue-Texts.
  podcast_maker schreibt den Namen als `asset`-Feld in die
  `_SFX_CUES.json`, Lolfi liest ihn von dort (Hash nur noch Fallback).
  Wer `prompt` im Plan von Hand ändert, muss `--force` laufen lassen — der
  Hash wird nicht automatisch nachgezogen.

`sfx_assets` generiert daraufhin die **Palette** (kuratierter Prompt +
geplante Dauer) statt roher Cue-Texte und spart die Sounds, die gar keine
sind. Ohne Plan bleibt der Alt-Pfad (Cue-Texte aus den `_SFX_CUES.json`,
also erst nach dem Vertonen möglich).

### Ambience-Teil desselben Plans

Zweiter Claude-Call in `sfx_plan` (unabhängig von den Cues; Quelle sind die
`sections` + `section_locations` aus episodes.json, NICHT die Skripte —
deshalb ein Call für die ganze Serie statt einer pro Episode). Er schreibt
`ambience.variants` + `ambience.sections` in denselben Plan.

- Vorher hatte jeder Ort EINE Schleife für die ganze Serie: ein stilles
  Frühstück und eine Mitternachts-Eskalation im selben Raum klangen
  identisch. Jetzt bekommt jeder Ort bis zu
  `MAX_AMBIENCE_VARIANTS_PER_LOCATION=3` Stimmungen, und jede Szene wird
  einer zugewiesen. Das Prompt verlangt ausdrücklich, KEINE Stimmungen zu
  erfinden, die die Szenen nicht hergeben — bei `the_wildrose_inheritance`
  (2 Episoden) kam korrekt 1 Variante pro Ort zurück, bei `the_long_fare`
  (10 Episoden) 12 Varianten für 6 Orte (THE_SEDAN: fahrend-im-Regen /
  Leerlauf am erzwungenen Halt / geparkt bei Morgengrauen).
- Loops enthalten per Prompt-Regel **keine Einzelereignisse** — ein Türknall
  in einer 20s-Schleife knallt alle 20 Sekunden erneut.
- `location_ambience` generiert daraus `sfx/ambience/<VARIANTE>.mp3` UND
  weiterhin `sfx/ambience/<ORT_KEY>.mp3` als Fallback (Lolfi nimmt die
  Variante, sonst den Ort, sonst die alte Zufalls-Baseline).
  `AMBIENCE_GEN_DURATION_SECONDS` ist von 10s auf 20s hoch — 10s waren bei
  einer 4-Minuten-Szene 24 Wiederholungen und damit hörbar ein Metronom.
- `podcast_maker` hängt die Variante als Feld `ambience` an die Spans der
  `<Episode>_LOCATIONS.json`. **Ein Stimmungswechsel bricht eine Spanne
  auf**, auch wenn der Ort derselbe bleibt — sonst könnte Lolfi mittendrin
  nicht überblenden.
