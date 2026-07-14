# fabrik/core — stdlib-only Fundament

**Eiserne Regel:** Dieses Paket ist stdlib-only (paths, config, textproc,
history, claude_cli) und darf NIE aus `fabrik/audio/` importieren. Es muss
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
- `data/series/LATEST` hält den Slug der Default-Serie; alle CLIs fallen
  darauf zurück, wenn `--series` fehlt.
- `validate_case_block()` ist **mode-agnostisch** — deshalb konnte
  media_analysis den `case`-Block ohne Codeänderung wiederverwenden.
  Nebenwirkung: Episode-Review und Beat-Layer gaten rein auf
  `episode.get("case")`, nicht auf `mode`.
- `VALID_SOURCE_VALUES`: `"source": "imported"` markiert import_story-
  Episoden; generate_episode überspringt für sie die Generierung.

## Voice-Regeln in config.py

- `KNOWN_BUILTIN_SPEAKERS`: die exakt neun Stimmen, die der LOKALE
  Qwen3-Server tatsächlich anbietet — NICHT das offizielle Qwen3-Roster:
  "Ethan"/"Chelsie" existieren lokal nicht (dafür Ono_Anna/Sohee) und
  haben zweimal Produktionsläufe erst beim Vertonen scheitern lassen;
  Roster-Änderungen immer auch in den drei Creator-Templates nachziehen
  (crime_drama/soap_opera/language_course listen die Stimmen wörtlich).
  Unbekannte Namen sind nur eine Warnung bei `check` (Clones sind legal).
  Nur Ryan/Aiden sind akzentfreie native English speakers — alle anderen
  (inkl. ALLER Frauenstimmen) haben hörbaren Akzent; daher die
  ACCENT CASTING RULE in den Templates (siehe templates/CLAUDE.md).
- **Harter Fehler**, wenn zwei `voices`-Rollen auf denselben `voice`-Namen
  auflösen — zwei Charaktere mit gleicher Stimme sind nie beabsichtigt.
- `NARRATOR` ist von der `character_knowledge`-Vollständigkeits-Warnung
  ausgenommen (crime_drama/soap_opera; built-in only, nie Clone).
- Seed-Warnung: built-in Speaker haben serverseitig KEINE Seed-Kontrolle;
  config.py warnt, wenn trotzdem einer gesetzt ist.
- `BACKEND_SUPPORTS_STYLE` (`rest`: ja, `kokoro`/`gradio`: nein) lebt
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
- `parse_json_response(raw)` strippt Markdown-Fences / greift den größten
  `{...}`-Block; gibt bei unparsebarem Input `None` zurück (wirft nie).
- **Retry-Disziplin:** Timeout oder Non-Zero-Exit eines `claude`-Calls, der
  eine Retry-Schleife füttert, muss *retryable* sein, nie `sys.exit()` —
  ein einzelner flakiger Call darf keinen Batch-Job töten. Nur "claude not
  found" und "not logged in (401)" sind unrecoverable und beenden sofort.
- **stdin-Gotcha:** jeder `subprocess`-Aufruf von `claude -p` braucht
  `stdin=subprocess.DEVNULL` — ohne hängt/erroret der CLI ("no stdin data
  received"), wenn der Elternprozess kein TTY-stdin hat, was exakt der Fall
  ist, wenn das WebUI Jobs spawnt (`webui/runner.py` nutzt Popen ohne
  `stdin=`). Bei jedem neuen `subprocess.run(["claude", ...])` beibehalten.

## textproc.py

- `count_length_units()`: sprachneutrale Längenmessung — 1 CJK-Zeichen =
  1 lateinisches Wort = 1 Einheit. Basis aller Wortbudget-Prüfungen.
- `chunk_prose_by_words()`: absatzbewusster Split, genutzt vom Audio-
  Chunking und von import_story (dort OHNE Minimum — Quelltext diktiert
  seine eigene Länge).
