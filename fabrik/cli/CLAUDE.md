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

`python3 -m fabrik.cli.create_series "Topic" [--episodes N] [--minutes M]
[--locations L] [--template T] [--no-review] [--fix]`

`--template` nimmt jeden Ordnernamen unter `templates/` (kein argparse-
`choices`); aktuell: narration, media_analysis, language_course,
crime_drama, soap_opera, shorts. Zwei grundverschiedene Generierungspfade,
je nach `template in CASE_BASED_TEMPLATES` (= crime_drama/soap_opera):

- `--minutes` steuert die Episodenlänge: `estimate_section_count()`
  (Ein-Schuss-Pfad) bzw. `estimate_section_count_from_format()`
  (case-based Pfad, liest aus dem bereits generierten `canon.format` statt
  aus einer Template-Datei) leiten die Section-Zahl aus minutes
  (WORDS_PER_MINUTE=150) und `parts_per_section`/`words_per_part_target`
  ab. Warnt laut bei unparsebaren Format-Werten. (media_analysis-
  Sonderfall: siehe templates/CLAUDE.md — dort skaliert --minutes nur die
  Wortziele.)
- `--locations` steuert, wie viele wiederverwendbare Szenen-Orte
  soap_opera erfindet; von Templates ohne Location-Support ignoriert.

### Nicht-CASE_BASED_TEMPLATES: Ein-Schuss (`generate_with_retry`)

narration/media_analysis/language_course/shorts erzeugen die komplette
`episodes.json` in EINEM Claude-Call. **`generate_with_retry`
(MAX_ATTEMPTS=3):** ungültiges JSON, `validate_data`-Fehler UND falsche
Episodenzahl werden wörtlich in den nächsten Versuch zurückgefüttert
(gleiches Muster wie `call_claude_with_retry` beim Skript-Writer) —
Count-Mismatch ist ein retryable ERROR, keine Warnung. Timeout/transienter
CLI-Fehler ist ebenfalls retryable (ohne Feedback); nur "claude not
found"/"not logged in" brechen sofort ab. **Best-Effort-Fallback**
(Gegenstück zu validate_parts' fallback_safe): sind alle Versuche
schema-sauber und nur die Episodenzahl daneben, wird der Versuch mit der
nächstliegenden Zahl genommen statt abzubrechen. `sys.exit(1)`, wenn über
alle Versuche keiner fallback-sicher war — kein Batch-Ausweichpfad mehr
(siehe Umbau unten), diese vier Templates sind klein genug, dass er in der
Praxis nie gebraucht wurde.

### CASE_BASED_TEMPLATES: Kanon → Staffelbogen → Episoden (Stage-01-Umbau, 17.07.2026)

**Ersetzt seit diesem Umbau (Begründung + Referenzdaten:
`docs/konzept-stage-umbau.md`) den früheren Ein-Schuss-/Batch-Mechanismus
komplett** (227+ Zeilen gelöscht: `apply_case_canon`, `check_case_drift`,
`check_section_detail`, `check_section_words_gaps`, der ganze
Skeleton/Batch-Apparat). Wurzelursache des alten Mechanismus: die
Section-Tiefe war eine Eigenschaft des BATCHES, kein Zufall pro Episode
(`the_understudy`: Ø 12.4/12.8/12.8 — 4.2/4.0/3.8 — 6.9/7.0/7.2 — 22.5,
exakt an den Batch-Grenzen) — aus zwei Titeln wie `"Declan's Turn"` (ep9)
und `"The Ledger Laid Bare"` (ep10) konnte kein Writer ableiten, welche
Episode ein Geständnis tragen soll, wenn die beiden Batches einander nie
sehen. `case_canon` (Fakten) verhinderte das NICHT — es fixierte
Täter/Beweise, nicht die Ereignis-ZUTEILUNG.

`generate_case_based_series()` (main()'s Einstiegspunkt für diesen Pfad)
orchestriert drei Teilstages, jede mit eigenem Retry+Validierung und
eigenem Checkpoint (`_cached_unit()`, s.u.):

1. **`generate_canon()`** (01a, ein Call) → `canon.json`: Welt, Cast,
   Orte, und `threads` — die EINE Stelle, an der Fakten eines
   Handlungsstrangs stehen (`label`/`solution`/`objective_facts`).
   `validate_canon()` baut dafür ein Kandidat-Dokument mit einer
   Platzhalter-Episode und lässt `config.validate_data()` die schwere
   Arbeit machen (Wiederverwendung statt Duplikation), ergänzt nur die
   Thread-Anzahl-Regel (crime_drama genau 1, soap_opera 2-4).
2. **`generate_arc()`** (01b, ein Call, sieht `canon.json`) → `arc.json`:
   `turning_points: [{thread, episode, event}]` — **jeder Wendepunkt
   genau EINER Episode zugeteilt**, das ist der Mechanismus, der einen
   Doppel-Klimax strukturell unmöglich macht (analog zu einem
   Writers'-Room-Breakdown: die Zuteilung steht fest, BEVOR einzelne
   Episoden geschrieben werden). `validate_arc()` prüft deterministisch:
   jeder `thread` existiert in `canon.threads`, jede Episode 1..N kommt
   genau einmal vor, kein `event` dupliziert sich (Text-Vergleich), jede
   Episode hat ≥1 Wendepunkt oder `breather: true`.
3. **`generate_episode_concept()`** (01c, EIN Call PRO EPISODE, parallel
   über `ThreadPoolExecutor`, `EPISODE_CONCEPT_PARALLEL_CAP=4`) → pro
   Episode `sections: [{title, what, who, thread, location, words}]` +
   `case: [{label, character_knowledge}]` + `intro_note`/`outro_note`.
   Jeder Call sieht `canon.json` + `arc.json` (+ die eigenen Wendepunkte,
   + Nachbar-Episoden-Kurzfassung für Kontinuität), aber NIE die parallel
   generierten Sections anderer Episoden — keine Batch-Grenze mehr, an
   der die Granularität kippen könnte.
   **`validate_episode_concept()`** — Detailtiefe-Band als PRO-Section-Gate
   (CONCOCT-Lektion, ersetzt das alte, nachträgliche
   `check_section_detail`): jedes `what` muss zwischen `SECTION_WORDS_MIN`
   (12) und `SECTION_WORDS_MAX` (30) Länge-Einheiten liegen (sprachneutral,
   `textproc.count_length_units`), UND die Streuung innerhalb einer Episode
   darf Faktor 3 nicht überschreiten (max/min der Section-Längen) — beides
   führt VOR der Übernahme zum Retry mit Feedback, nicht erst danach.

**Zusammenbau** (Ende von `generate_case_based_series()`): Kanon-Felder +
`threads` + pro Episode `figure`/`theme` (aus `arc.json`) +
`sections`/`case`/`intro_note`/`outro_note` (aus dem 01c-Ergebnis). Jeder
`case`-Eintrag bekommt `solution`/`objective_facts` aus
`canon.threads[label]` injiziert — der Ersatz für das alte
`apply_case_canon()`, nur ohne Drift-Risiko: die Fakten stehen in
`canon.threads` bereits EINMAL final fest, 01c liefert pro Episode nur
noch `label`+`character_knowledge`. Danach ein finaler
`config.validate_data()`-Sicherheitsnetz-Check auf dem Gesamtdokument.

**Checkpoint (`_cached_unit()`):** canon/arc/jedes Episoden-Konzept sind
eigene Einheiten unter `data/.create_series_staging/<hash>/{canon,arc,
episode_N}.json` — verallgemeinert das alte `_cached_batch`-Muster
(Schlüssel weiterhin `_checkpoint_key()`: Hash der AUFRUF-Parameter, NICHT
des substituierten Prompts, aus demselben FIGURE_HISTORY-Grund wie zuvor).
Ein optionales `validate_fn` verwirft einen Checkpoint, der seit einer
Code-Änderung nicht mehr zum Schema passt (Muster aus dem alten
Skeleton-Checkpoint). Scheitert eine Episode endgültig, bleiben die
übrigen bereits generierten Einheiten erhalten — ein identischer Rerun
generiert nur die fehlenden neu. Gelöscht wird der Ordner ERST nach
erfolgreichem Schreiben der Serie (`_clear_checkpoint`, in `main()`,
NACH `paths.write_latest`) — Review/Reparatur laufen dazwischen und
sind selbst potenziell lange Claude-Aufrufe.

**Reconciliation-Pass (`check_turning_point_coverage()`, Phase 4 des
Umbau-Plans):** läuft NACH allen 01c-Calls, einmal pro Serie, als
LLM-Judge-Call — liest `arc.json`s `turning_points` gegen die fertigen
Sections aller Episoden und entscheidet pro Wendepunkt: `ok` (genau in der
zugeteilten Episode erzählt), `duplicate` (zusätzlich in einer anderen
Episode) oder `missing` (in keiner). **Self-Consistency-Voting**
(FlawedFictions-Muster gegen dokumentiertes LLM-Judge-Rauschen): derselbe
Call läuft 5x (`votes`), ein Fund zählt nur, wenn dasselbe
(Wendepunkt, Verdikt, betroffene Episoden) in mindestens 4 von 5 Läufen
(`threshold`) übereinstimmt — ein einzelner abweichender Lauf wird
verworfen statt sofort einen Fund auszulösen. Rückgabeform identisch zu
`review_series()`/dem gelöschten `check_case_drift()`:
`[{"episodes": [int], "problem": str}]`, läuft in `main()` daher durch
denselben `repair_series()`-Dispatcher wie das Inhalts-Review — bei
`--fix` wird die betroffene Episode (bzw. bei einem Doppel-Klimax die
ZUSÄTZLICHE, nicht die ursprünglich zugeteilte) gezielt neu generiert.
Ohne `arc.json` (Nicht-CASE_BASED_TEMPLATES) läuft dieser Check nicht
— `main()` setzt `arc = None` in diesem Fall.

### Gemeinsam für beide Pfade

- **`review_series`** (LLM, skippbar via `--no-review`): Spoiler vor dem
  Finale, Widersprüche objective_facts/character_knowledge,
  Accent-Casting-Regel, Episoden-Überlappung. Findings sind warn-only —
- **AUSSER mit `--fix`:** `repair_series()` behebt die gemeldeten Findings
  (Format: `[{"episodes": [int, ...], "problem": str}]`).
  **Dispatcher-Logik: Befunde werden nach Geltungsbereich AUFGETEILT** und
  jede Gruppe mit dem kleinstmöglichen Aufruf repariert (die Schritte bauen
  aufeinander auf, der zweite sieht das Ergebnis des ersten):
  1. Befunde MIT Episodennummer → `_repair_series_episodes()`: schickt nur
     die BETROFFENEN Episoden (plus ein kompakter Serien-Index aus
     Figur/Thema/Thread-Labels der übrigen als Kontext), analog zu
     `repair_part()`/`apply_episode_fixes()` beim Skript-Writer, nur auf
     episodes.json-Ebene. Danach `_reconcile_case_canon_from_siblings()`:
     erzwingt, dass `solution`/`objective_facts` der reparierten Episoden
     zur ersten UNVERÄNDERTEN Episode desselben Thread-Labels passen — bei
     NEU generierten (case-based) Serien ein reiner No-op (die Felder
     stehen dort schon einmalig in `threads`, nicht mehr pro Episode
     dupliziert), bleibt aber für Alt-Serien mit dem Vor-Umbau-Schema
     wirksam.
  2. Befunde OHNE Episodennummer (Akzent-Casting über `voices` & Co.) →
     `_repair_series_globals()`: schickt NUR die Top-Level-Felder ohne
     `episodes` (ein paar KB statt >100 KB). Harte Prompt-Regel: die
     Rollen-KEYS in `voices` bleiben identisch — die Episoden referenzieren
     sie in `character_knowledge` und werden hier nicht angefasst;
     `validate_data()` fängt eine Umbenennung zusätzlich ab.
  3. Nur was Schritt 1/2 NICHT hinbekommen haben → `_repair_series_full()`,
     der volle Dokument-Umbau in einem Call. Reines Auffangnetz. Bei nur
     teilweisem Erfolg gibt `repair_series()` den bereits verbesserten
     Stand zurück (nicht None) — Teilerfolge zu verwerfen wäre schlechter
     als sie zu behalten.

  **Warum die Aufteilung (Bugfix 17.07.2026, Nutzer-Symptom "bei 10
  Episoden gibt es Probleme"):** vorher entschied der Dispatcher am
  SCHWÄCHSTEN Befund — ein einziger Fund ohne Episodenbezug kippte ALLE
  Befunde in den vollen Umbau, der bei 10 Episoden (>100 KB Ausgabe)
  zuverlässig abriss. Gemessen nach dem Fix (echte 10-Episoden-Serie,
  Spoiler-Fund + Akzent-Fund): 117s, beide Reparaturen im ersten Versuch,
  nur die betroffene Episode verändert.
  **Abriss-Erkennung in ALLEN Reparatur-Pfaden:** `response_looks_truncated()`
  — `_repair_series_episodes()` und `_repair_series_full()` brechen beim
  ersten Abriss ab, statt ein Längenproblem blind mit Feedback zu
  wiederholen. Alle drei Wege re-validieren strukturell (eigene
  MAX_ATTEMPTS-Schleife). Bekommt keiner eine gültige Korrektur hin, bleibt
  das Original unangetastet und die Findings werden gedruckt.
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
- Creator-/Kanon-Templates tragen einen expliziten `{{FIGURE_HISTORY}}`-
  Platzhalter (`build_prompt`/`build_canon_prompt` errort laut, wenn er
  fehlt UND der Legacy-ALREADY-USED-FIGURES-Regex nicht greift).
- Timeout skaliert: `compute_timeout` = 180s/Episode, Floor 900s, Cap
  3600s (Kanon/Bogen: `episode_count`; ein Episoden-Konzept:
  `compute_timeout(1)`). Heartbeat alle 20s via `run_claude_process`
  (fabrik/core). `compute_batch_timeout` (kleinerer Floor) lebt weiter,
  aber nur noch für `_repair_series_episodes()`/`_repair_series_globals()`.
- **Systemweite Claude-Aufruf-Bremse:** `fabrik/core/claude_cli.py::
  _claude_slot()` begrenzt zusätzlich, wie viele `claude`-Subprozesse
  GLEICHZEITIG über alle Cockpits/Serien/Threads hinweg laufen dürfen
  (`PF_MAX_CONCURRENT_CLAUDE`, Default **20** — hoch angesetzt als reine
  Notbremse, siehe fabrik/core/CLAUDE.md).

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
