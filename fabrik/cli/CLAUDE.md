# fabrik/cli — Entry-Points

Aufruf immer als Modul vom Projekt-Root: `python3 -m fabrik.cli.<name>`
(das WebUI macht exakt das via `"module"`-Einträge in
`webui/config.py::COMMANDS`). Alle CLIs akzeptieren `--series <slug>`;
ohne wird `data/series/LATEST` genutzt (oder die einzige Serie).

| CLI | Zweck | braucht |
|---|---|---|
| create_series | episodes.json via Claude erzeugen | claude CLI |
| import_story | fertigen Text als Serie importieren | claude CLI |
| generate_episode | Skripte schreiben (`check`/`N`/`all`) | claude CLI |
| podcast_maker / batch | vertonen (eine/alle Episoden) | .venv + ffmpeg + TTS-Server |
| character_prompts / location_prompts / cover_art | Bild-Prompts (+ PNGs bei OPENAI_API_KEY) | claude CLI (Bilder: stdlib urllib, kein venv) |

## create_series.py

`python3 -m fabrik.cli.create_series "Topic" [--episodes N] [--minutes M]
[--locations L] [--template narration|media_analysis|language_course|crime_drama|soap_opera]
[--no-review] [--fix]`

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
- **AUSSER mit `--fix`:** `repair_series()` schickt die komplette
  episodes.json + Findings zurück an Claude ("ändere NUR was nötig ist"),
  re-validiert strukturell (eigene MAX_ATTEMPTS-Schleife, gleiches
  Feedback-Muster) und re-reviewt das Ergebnis. Anders als `repair_part()`
  gibt es keine adressierbare PART-Einheit — das ganze (kleine) Objekt
  wird regeneriert. Wird die Reparatur nie strukturell gültig, bleibt das
  Original unangetastet und die ursprünglichen Findings werden gedruckt.
- Creator-Templates tragen einen expliziten `{{FIGURE_HISTORY}}`-
  Platzhalter (`build_prompt` errort laut, wenn er fehlt UND der Legacy-
  ALREADY-USED-FIGURES-Regex nicht greift — kein stilles Auslassen).
- Timeout skaliert: `compute_timeout` = 120s/Episode, Floor 600s, Cap
  1800s. Heartbeat alle 20s via `run_claude_process` (fabrik/core).

## generate_episode.py

- `check` — nur episodes.json validieren.
- `N [--fix] [--no-script-review]` — eine Episode; bei
  `"source": "imported"` wird die Generierung übersprungen und direkt
  `generate_episode_meta()` gerufen (Skript existiert schon).
- `all [--jobs N] [--force] [--fix] [--no-script-review]` — alle Episoden
  (Subprocess pro Episode), danach automatisch batch.py.
- `--fix`/Review-Semantik und Beats: siehe fabrik/writing/CLAUDE.md.

## import_story.py

Gegenstück zu create_series für fertigen Text (alte Romane etc.), bei dem
Claude nichts erfinden darf. **Nur narration-Mode.**

- Zwei Quellformen: Ordner (eine Datei = eine Episode, wörtlich) oder eine
  lange Datei (Auto-Split via Kapitelüberschrift-Regexes, Fallback
  absatzbewusster Wortzahl-Split, `textproc.chunk_prose_by_words`).
- Pro Episode genau EIN Claude-Call (`summarize_source_episode`, nur
  Titel+Theme, light_model); PART-Chunking deterministisch OHNE Minimum —
  der Quelltext diktiert seine Länge.
- Episoden bekommen `"source": "imported"`; podcast_maker/batch brauchen
  keinerlei Anpassung (lesen nur die fertige Skriptdatei). Beat-Layer wird
  strukturell übersprungen (kein Generierungspfad).

## character_prompts.py / location_prompts.py

- `character_prompts [--force]` → `data/series/<slug>/characters/PROMPTS.txt`;
  mit `OPENAI_API_KEY` zusätzlich direkt `<ROLE>.png` via gpt-image-1-mini
  (`fabrik/writing/image_backends.py`, stdlib urllib, kein venv);
  `--no-images` erzwingt prompts-only. NARRATOR ausgenommen.
- Pro Rolle zusätzlich eine Variante je Emotion — `<ROLE>_<emotion>.png`
  für anger/fear/sadness/joy/surprise/love/vulnerability (spiegelt Lolfis
  EMOTIONS-Keys exakt; von Hand synchron gehalten, kein Shared Import).
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
