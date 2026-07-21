# fabrik/core — stdlib-only Fundament

**Eiserne Regel:** Dieses Paket ist stdlib-only (paths, config, textproc,
history, claude_cli, workspace) und darf NIE aus `fabrik/audio/` importieren. Es muss
ohne jedes venv laufen — der Script-Generierungs-Pfad (`claude` CLI, kein
Python-Paket installiert) hängt daran.

## episodes.json — Single Source of Truth (`config.py`)

Jede Serie ist `data/series/<slug>/` mit einer `episodes.json`, die ALLES
steuert: Inhalt, Format, Voice-Modus, Audio-Backend-Konfig.

- `validate_data()` prüft exhaustiv: **jeder unbekannte Key = Warnung**
  (Tippfehler-Erkennung für AI-generiertes JSON), **jeder strukturell
  ungültige Wert = harter Fehler** vor Generierungsstart.
- `build_config()` flacht episodes.json + `DEFAULTS` in das `cfg`-Dict ab,
  das durch die gesamte Pipeline gereicht wird.
- `generation.review_model` (neu 17.07.2026): Modell fürs Episoden-Skript-
  Review; Default = `generation.model` (das GROSSE Schreibmodell) — die
  12-Serien-Analyse zeigte das light_model als Reviewer praktisch blind
  (8/8 leere Reviews trotz 25 realer Fehler). Beats-Review/Metadaten
  bleiben auf light_model.
- `data/series/LATEST` hält den Slug der Default-Serie; alle CLIs fallen
  darauf zurück, wenn `--series` fehlt.
- `validate_case_block()` ist **mode-agnostisch** — deshalb konnte
  media_analysis den `case`-Block ohne Codeänderung wiederverwenden.
  Nebenwirkung: Episode-Review und Beat-Layer gaten rein auf
  `episode.get("case")`, nicht auf `mode`.
- **`character_knowledge.ROLE` akzeptiert seit 17.07.2026 ZWEI Formen:**
  neu ein Fließtext-String (1-3 Sätze Wissensstand), alt weiterhin
  `{knows: [...], hides: [...], believes_falsely: [...]}` — beide werden
  von `validate_case_block()` geprüft und von
  `script_writer._build_single_case_block()` gleich in lesbaren Prompt-Text
  umgewandelt. Grund: weniger JSON-Verschachtelungstiefe senkt das
  Abriss-Risiko beim Generieren (Beleg: eine Messung zeigte, dass die
  freieren BEATS-Dateien trotzdem GRÖSSER sind als der strukturierte
  case-Block — Verschachtelung, nicht Textmenge, war der Zerbrechlichkeits-
  treiber). Der Staffel-Kanon (`label`/`solution`/`objective_facts`,
  siehe `check_case_drift`/`apply_case_canon` in fabrik/cli/CLAUDE.md)
  bleibt bewusst UNVERÄNDERT strikt — das ist der Teil, der Drift über
  Episoden hinweg verhindert.
- `VALID_SOURCE_VALUES`: `"source": "imported"` markiert import_story-
  Episoden; generate_episode überspringt für sie die Generierung.

## Voice-Regeln in config.py

- `BUILTIN_SPEAKER_ROSTER`: die exakt neun Stimmen, die der LOKALE
  Qwen3-Server tatsächlich anbietet — NICHT das offizielle Qwen3-Roster:
  "Ethan"/"Chelsie" existieren lokal nicht (dafür Ono_Anna/Sohee) und
  haben zweimal Produktionsläufe erst beim Vertonen scheitern lassen.
  Das Roster ist die EINE Quelle: create_series.py substituiert es als
  `{{VOICE_ROSTER}}` (crime_drama/soap_opera/shorts) bzw.
  `{{VOICE_ROSTER_COMPACT}}` (language_course) in die Creator-Templates —
  Roster-Änderungen also nur hier, nie in den Templates.
  `KNOWN_BUILTIN_SPEAKERS` ist das Validierungs-Superset (Roster + zwei
  gradio-Kleinschreibvarianten Ono_anna/Uncle_fu); unbekannte Namen sind
  nur eine Warnung bei `check` (Clones sind legal).
  Nur Ryan/Aiden sind akzentfreie native English speakers — alle anderen
  (inkl. ALLER Frauenstimmen) haben hörbaren Akzent; daher die
  ACCENT CASTING RULE in den Templates (siehe templates/CLAUDE.md).
- **Harter Fehler**, wenn zwei `voices`-Rollen auf denselben `voice`-Namen
  auflösen — zwei Charaktere mit gleicher Stimme sind nie beabsichtigt.
- `NARRATOR` ist von der `character_knowledge`-Vollständigkeits-Warnung
  ausgenommen (crime_drama/soap_opera/shorts; built-in only, nie Clone).
- Seed-Warnung: built-in Speaker haben serverseitig KEINE Seed-Kontrolle;
  config.py warnt, wenn trotzdem einer gesetzt ist.
- `BACKEND_SUPPORTS_STYLE` (`rest`/`gradio`: ja, `kokoro`: nein — `gradio`
  gilt nur für den Built-in-Speaker-Pfad, Clones ignorieren Style eh) lebt
  **bewusst hier und nicht in tts_backends.py** — letzteres importiert
  requests/pydub und würde den No-venv-Pfad brechen. Treibt
  `cfg["supports_style"]`, mit dem script_writer Style-Anweisungen komplett
  wegläßt, wenn das Backend sie eh verwerfen würde.

## claude_cli.py — geteiltes Claude-CLI-Plumbing

Stdlib-only, genutzt von create_series.py und script_writer.py.

- `run_claude_process(argv, timeout, label)` ersetzt `subprocess.run()` für
  alles, was lange laufen kann: `proc.communicate()` in einem Background-
  Thread, Heartbeat-Zeile `⏳ <label> … noch dabei (Ns vergangen, Timeout
  bei Ts)` alle 20s — `--output-format text` streamt nicht, ohne Heartbeat
  sieht ein langer Call im Log identisch zu einem Hänger aus. Wirft
  `subprocess.TimeoutExpired` wie `subprocess.run()`.
- `parse_json_response(raw)` strippt Markdown-Fences, probiert dann JEDE
  `{`-Position im Text einzeln (`_json_decoder.raw_decode`) und nimmt die
  LÄNGSTE erfolgreiche Kandidatur — nicht nur "erste `{` bis letzte `}`":
  ein Modell hält sich trotz Anweisung manchmal nicht an "nur JSON, kein
  Kommentar" und schreibt vorher ein kurzes Beispiel-Fragment mit eigener
  `{}` (z.B. ein einzelnes section_words-Objekt zur Illustration) — die
  naive erste-`{`-Regel hätte das als Start genommen und wäre an "Extra
  data" gescheitert, obwohl das eigentlich gemeinte, viel längere Objekt
  direkt danach im Text stand. Gibt bei unparsebarem Input `None` zurück
  (wirft nie).
- **Retry-Disziplin:** Timeout oder Non-Zero-Exit eines `claude`-Calls, der
  eine Retry-Schleife füttert, muss *retryable* sein, nie `sys.exit()` —
  ein einzelner flakiger Call darf keinen Batch-Job töten. Nur "claude not
  found" und "not logged in (401)" sind unrecoverable und beenden sofort.
- **Systemweite Zählsemaphore** (`_claude_slot()`, `CLAUDE_SLOTS_DIR =
  data/.claude_slots/`): begrenzt, wie viele `claude`-Subprozesse GLEICHZEITIG
  über ALLE Cockpits/Serien/Threads hinweg laufen dürfen
  (`PF_MAX_CONCURRENT_CLAUDE`, Default **20**). Ursprünglicher Verdacht
  (16.07.2026, Parallelbetrieb mehrerer WebUI-Cockpits): jedes Cockpit
  parallelisiert intern schon selbst (create_series' `BATCH_PARALLEL_CAP=4`,
  `--jobs`/`SECTION_PARALLEL_CAP=4`) — diese Caps kennen sich gegenseitig
  nicht, bei 3 Cockpits könnten so 10-15+ `claude`-Prozesse gleichzeitig
  denselben Account treffen. **Geprüft und NICHT bestätigt:** die komplette
  Log-Historie eines echten Mehr-Cockpit-Laufs (~2000 Zeilen, teils 8+
  parallele Prozesse) zeigte keine einzige Rate-Limit-/429-Meldung — das
  tatsächliche Problem jener Session war abgeschnittenes JSON bei zu großen
  Batches (siehe `generate_batch_with_retry()` in fabrik/cli/CLAUDE.md), keine
  Account-Drosselung. Default deshalb bewusst hoch: reine Notbremse gegen
  einen echten Ausreißer (z.B. 10+ Cockpits gleichzeitig mit hohem `--jobs`),
  keine Routine-Drosselung bei wenigen Cockpits. Ein niedrigerer Default hätte
  nur legitime Parallelarbeit gebremst, ohne ein reales Problem zu verhindern.
  Slot-Dateien (`fcntl.flock`, zufällige Versuchsreihenfolge gegen
  Thundering-Herd) statt In-Memory-Zähler, weil die Semaphore
  prozessübergreifend sein muss; ein Slot wird beim Schließen des
  Deskriptors automatisch frei, auch nach hartem Kill/Crash des Halters —
  kein dauerhaft blockierter Slot möglich. Das Warten auf einen Slot liegt
  bewusst VOR dem Start der Timeout-Uhr in `run_claude_process()` (zählt
  nicht gegen `timeout`), ab `_SLOT_WARN_AFTER_SECONDS` erscheint eine
  eigene Log-Zeile ("wartet auf einen freien Claude-Aufruf-Slot") statt
  stillem Anstehen. Ein ECHTES Drosselungsproblem zeigt sich anders: als
  `⚠️ Claude-CLI-Fehler`/`API-Fehler`-Zeile mit 429/rate_limit/overloaded im
  Text (aus `call_claude()`s Fehlerausgabe) — danach `PF_MAX_CONCURRENT_CLAUDE`
  gezielt runterregeln, statt präventiv niedrig zu starten.
- **stdin-Gotcha:** jeder `subprocess`-Aufruf von `claude -p` braucht
  `stdin=subprocess.DEVNULL` — ohne hängt/erroret der CLI ("no stdin data
  received"), wenn der Elternprozess kein TTY-stdin hat, was exakt der Fall
  ist, wenn das WebUI Jobs spawnt (`webui/runner.py` nutzt Popen ohne
  `stdin=`). Bei jedem neuen `subprocess.run(["claude", ...])` beibehalten.

## paths.py / workspace.py — MWP-Workspace

- `paths.Series` kapselt das Stage-Layout `data/series/<slug>/stages/
  01_concept … 04_visuals` (`EPISODES_RELPATH = stages/01_concept/output/
  episodes.json`, Skripte unter `stages/02_scripts/output/`, Audio unter
  `stages/03_audio/output/`). `resolve_series()`/`add_series_arg()` sind
  die eine Auflösung des `--series`-Flags (Fallback LATEST bzw. einzige
  Serie, Abbruch bei Mehrdeutigkeit).
- `workspace.scaffold_workspace()` stanzt die CONTEXT/CLAUDE-Verträge aus
  `templates/_workspace/` in einen neuen Serien-Ordner und kopiert die
  Template-Prompts nach `references/`; idempotent, überschreibt nie.

## textproc.py

- `count_length_units()`: sprachneutrale Längenmessung — 1 CJK-Zeichen =
  1 lateinisches Wort = 1 Einheit. Basis aller Wortbudget-Prüfungen.
- `chunk_prose_by_words()`: absatzbewusster Split, genutzt vom Audio-
  Chunking und von import_story (dort OHNE Minimum — Quelltext diktiert
  seine eigene Länge).
