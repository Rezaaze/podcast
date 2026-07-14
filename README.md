# Podcast-Fabrik

Automatisierte Pipeline für Podcast-Serien: Claude schreibt die Skripte,
eine lokale Qwen3-TTS-API vertont sie, am Ende steht eine gemasterte MP3 pro
Episode plus eine Gesamt-Anthologie.

Zwei Modi (`episodes.json` → `mode`), fünf Templates (`episodes.json` →
`template`, wählt Creator-Prompt + Schreib-Prompt):

- **narration** (`mode: narration`, Template `narration`) — Ein Erzähler für
  die ganze Episode, Sprechstile pro Section. Das klassische
  True-Crime-/Anthologie-Format (Referenz: `data/series/dead_reckoning/`).
- **media_analysis** (`mode: narration`, Template `media_analysis`) — Ein
  Erzähler, aber mit fester Vier-Teil-Struktur statt freier Section-Zahl:
  Quellen-Vergleich (Macher-Intention vs. Publikums-Rezeption) →
  Psychologische Tiefenanalyse → Kernthese (eine benannte "Formel") →
  Ur-Muster (warum das Muster generell fasziniert). Zweckentfremdet
  `episodes[n].case` (`solution`/`objective_facts`, ohne
  `character_knowledge`) als Träger für These + Belege statt für die
  Wissens-Trennung zwischen Figuren, die crime_drama/soap_opera damit
  eigentlich abbilden. `--minutes` steuert hier NICHT die Section-Zahl
  (immer fix 4), sondern nur `format.words_per_part_target`. Siehe
  `templates/media_analysis/EPISODES_CREATOR_PROMPT.md`.
- **drama** (`mode: drama`) — Multi-Voice-Hörspiel: jede Skriptzeile trägt ein
  Sprecher-Tag mit eigener Stimme, Stilanweisung und Tempo;
  `[SFX: ...]`-Regieanweisungen werden nicht vertont, sondern als Cue-Sheet
  mit Timestamps für die DAW ausgegeben. Drei Templates nutzen diesen Modus:
  - **language_course** — Sprachkurs-Hörspiel (Chinesisch lernen durch
    Krimi-Szenen, Comprehensible Input), inkl. `[NOTE: ...]`-Vokabel-Tracking
    (Referenz: `data/series/tea_house_mysteries/`). Eigene `HOST`-Rolle führt durch
    die Episode.
  - **crime_drama** — reines Multi-Voice-Krimi-Hörspiel OHNE Sprachlern-Zweck,
    mit echter Wissens-Trennung zwischen den Figuren (`episodes[n].case`):
    jede Rolle bekommt ein eigenes `knows`/`hides`/`believes_falsely`-Slice,
    das in den Schreib-Prompt eingespeist wird — Widersprüche, Lügen und
    Missverständnisse sollen so organisch aus der Wissenslücke entstehen,
    statt vom Modell nur behauptet zu werden. Siehe
    `templates/crime_drama/EPISODES_CREATOR_PROMPT.md`.
  - **soap_opera** — Ensemble-Hörspiel mit mehreren parallelen
    Handlungssträngen statt einem Fall: `episodes[n].case` ist hier eine
    **Liste** von Strängen (je mit eigenem `label` + derselben
    Wissens-Trennung wie crime_drama), und die Anzahl der Sections pro
    Episode ist NICHT fest (4–7, je nachdem wie viele Stränge in der
    Episode Raum brauchen). Siehe `templates/soap_opera/EPISODES_CREATOR_PROMPT.md`.

  Beide (`crime_drama`, `soap_opera`) verlangen zusätzlich eine feste
  `NARRATOR`-Rolle (built-in Stimme, kein Voice-Clone): pure Audio-Formate
  ohne Bildspur brauchen 1–2 gesprochene Orientierungszeilen pro Part (wo,
  wann, wer ist da), sonst wirkt reiner Ensemble-Dialog schnell
  orientierungslos — `NARRATOR` ist keine Figur und bekommt kein
  `character_knowledge`-Slice.

Vier der fünf Templates (narration, language_course, crime_drama,
soap_opera) sind in der WebUI beim "Serie erstellen"-Schritt als Dropdown
wählbar; `media_analysis` aktuell nur per CLI-Flag `--template
media_analysis` (noch nicht im WebUI-Dropdown ergänzt). Das
Status-Dashboard zeigt Titel + aktives Template pro Serie unabhängig davon
für jede Serie korrekt an.

## Struktur

Aufgeteilt nach Laufzeit-Umgebung, nicht nach Thema — `core`/`writing`
brauchen kein venv, `audio` schon:

```
fabrik/
  core/                   stdlib-only, überall importierbar (auch ohne venv)
    paths.py                Serien-Auflösung (data/series/<slug>/, data/series/LATEST)
    config.py                episodes.json laden + validieren
    textproc.py              Satz-Splitting (EN + Chinesisch), Chunking, Längeneinheiten
    history.py                data/figure_history.json lesen/schreiben
    claude_cli.py             gemeinsame Claude-CLI-Aufruf-Logik (Timeout, Heartbeat, JSON-Parsing)
  writing/                braucht nur die `claude` CLI, kein venv
    script_writer.py         Skript-Generierung, Episoden-/Beat-Review via Claude CLI
    script_parser.py         Drama-Format: [SPRECHER | style | speed], [SFX: ...]
    image_backends.py        gpt-image-1-mini-Anbindung (Porträts, Orte, Cover)
  audio/                  braucht .venv (pydub, numpy, pyloudnorm, requests) + ffmpeg
    pipeline.py               TTS-Chunks, LUFS-Mastering, Merge, ID3-Tags, Timelines
    tts_backends.py           Qwen3-TTS REST (Mac/MLX), Gradio (Windows/CUDA), Kokoro (mlx-audio)
  cli/                    Einstiegspunkte — alle via `python3 -m fabrik.cli.<name>`
    create_series.py         neue Serie anlegen (inkl. episodes.json via Claude)
    generate_episode.py      Skripte generieren
    podcast_maker.py         ein Skript vertonen
    batch.py                  alle Skripte vertonen + Anthologie mergen
    character_prompts.py     Porträt-Prompts pro Drama-Rolle (+ Bilder via OPENAI_API_KEY)
    location_prompts.py      Bild-Prompts pro Szenen-Ort (+ Bilder via OPENAI_API_KEY)
    cover_art.py              Serien-Cover generieren (braucht OPENAI_API_KEY)
    import_story.py           bestehenden Text als fertige Serie importieren, siehe unten
templates/
  narration/             Prompts für das Ein-Erzähler-Format
  media_analysis/        Prompts für die feste Vier-Teil-Analyse-Struktur
  language_course/       Prompts für Sprachkurs-Hörspiele (HSK-Niveaus)
  crime_drama/           Prompts für Multi-Voice-Krimi mit Fallakten
  soap_opera/            Prompts für Ensemble-Seifenoper mit parallelen Strängen
data/series/<slug>/           eine Serie = ein MWP-Workspace (beliebig viele parallel;
                         Ordnerstruktur = Pipeline, siehe docs/mwp-umbau-plan.md)
  CLAUDE.md / CONTEXT.md Workspace-Identität + Stage-Routing
  stages/01_concept/     CONTEXT.md (Vertrag) + output/episodes.json
                         (Single Source of Truth der Serie)
  stages/02_scripts/     CONTEXT.md + output/: generierte Skripte
                         (ep1.txt, ep1_META.txt, BEATS/REVIEWs)
  stages/03_audio/       CONTEXT.md + output/: MP3s, Checkpoints, SFX-Cue-Sheets,
                         Sprecher-Timelines (*_SPEAKERS.json/.txt), Orte-Timeline
                         (*_LOCATIONS.json), Untertitel (*.srt), Kapitel,
                         UPLOAD_INDEX.md
  stages/04_visuals/     CONTEXT.md + output/characters/ (ROLLE.png +
                         ROLLE_<emotion>.png + PROMPTS.txt), output/locations/
                         (ORT_KEY.png; nur bei Serien mit `locations`-Mapping)
  references/            PROMPT_TEMPLATE.md — die pro Serie editierbare Kopie
                         des Skript-Prompts (Master unter templates/ bleibt
                         unberührt) + EPISODES_CREATOR_PROMPT.md (Doku)
  assets/                intro.mp3 / outro.mp3 / transition.mp3 (optional:
                         Jingles + Szenenwechsel-Sting, automatisch eingesetzt)
data/series/LATEST            Slug der zuletzt angelegten Serie (Standard für alle CLIs)
webui/                   lokale Steuer-Oberfläche
cloud/                   vast.ai-GPU-Automation (siehe cloud/README.md)
```

Alle CLIs akzeptieren `--series <slug>`; ohne Flag gilt `data/series/LATEST`
(bzw. die einzige vorhandene Serie).

## Workflow

```
fabrik.cli.create_series "Thema" [--template language_course]  ──▶ stages/01_concept/output/episodes.json
fabrik.cli.generate_episode all        ──(Claude)──▶ stages/02_scripts/output/ep1.txt, ...
fabrik.cli.podcast_maker ep1.txt       ──(Qwen3-TTS)──▶ stages/03_audio/output/Ep1_FULL_EPISODE.mp3
fabrik.cli.batch                       ──▶ alle Episoden + ANTHOLOGY_COMPLETE.mp3
```

1. **Serie anlegen:**

   ```bash
   python3 -m fabrik.cli.create_series "Thema/Konzept"                              # Erzähler-Format
   python3 -m fabrik.cli.create_series "Ein bekannter Film: Marketing vs. Publikumsreaktion" --template media_analysis --episodes 5 --minutes 15
   python3 -m fabrik.cli.create_series "HSK 3-4 Detektiv-Serie" --template language_course
   python3 -m fabrik.cli.create_series "Vier WG-Mitbewohner, ein Geheimnis pro Zimmer" --template soap_opera --episodes 10 --minutes 25 --locations 6
   ```

   Erzeugt `data/series/<slug>/` samt validierter `episodes.json` und setzt
   `data/series/LATEST`. Nichts wird mehr archiviert — Serien existieren parallel.

   - `--episodes N` — Anzahl Episoden (Standard 3).
   - `--minutes M` — Ziel-Länge pro Episode in Minuten (Standard 35); steuert,
     wie viele Sections das Template pro Episode anlegt. Bei `soap_opera`
     variiert die Section-Zahl zusätzlich noch pro Episode (je nachdem wie
     viele Handlungsstränge in dieser Episode Raum brauchen).
   - `--locations L` — Anzahl wiederverwendbarer Szenen-Orte für die ganze
     Serie (Standard 4), nur wirksam bei Templates mit `locations`-Unterstützung
     (aktuell nur `soap_opera`).
   - `--no-review` — überspringt den zweiten Claude-Aufruf, der die fertige
     `episodes.json` gegen Spoiler-Leaks, Widersprüche, Akzent-Casting und
     Episoden-Überschneidungen prüft (ohne `--fix` nur Warnungen, nie
     blockierend).
   - `--fix` — vom Inhalts-Review gemeldete Probleme automatisch reparieren:
     ein weiterer Claude-Aufruf gibt die korrigierte `episodes.json` aus
     (nur die geflaggten Stellen geändert, sonst alles unverändert), danach
     läuft der Review erneut zur Bestätigung. Wirkungslos zusammen mit
     `--no-review`.

   **Alternative — bestehenden Text importieren statt erfinden lassen:**
   siehe [Story-Import](#story-import-bestehenden-text-statt-claude-erfinden-lassen)
   weiter unten, wenn du eine fertige Geschichte/einen alten Roman als
   Podcast willst statt Claude ein neues Thema schreiben zu lassen.

2. **Skripte generieren** (nutzt die Claude CLI, kein venv nötig):

   ```bash
   python3 -m fabrik.cli.generate_episode check    # nur episodes.json validieren
   python3 -m fabrik.cli.generate_episode 1        # Episode 1 → stages/02_scripts/output/<prefix>1.txt
   python3 -m fabrik.cli.generate_episode all      # alle Episoden (parallel, --jobs N),
                                        # startet danach automatisch batch.py
   ```

   Jede Section wird einzeln generiert, validiert (Längenbudget, Part-Marker,
   im Drama-Modus zusätzlich das Sprecher-Tag-Format) und sofort in die Datei
   geschrieben — ein abgebrochener Lauf setzt beim Neustart bei der ersten
   fehlenden Section fort. `--force` generiert neu.

   **Wortbudget pro Szene überschreiben:** `format.words_per_part_min/max`
   gilt standardmäßig für die ganze Episode einheitlich. Einzelne Episoden
   können das pro Section überschreiben (`episodes[n].section_words`, Liste
   parallel zu `sections`, `null` = Format-Default):

   ```json
   "section_words": [
     null,
     {"min": 150, "max": 300, "target": "180 to 250"},
     null
   ]
   ```

   **Episoden-Review + Autofix:** bei Serien mit `case` (crime_drama/
   soap_opera) schreibt jede Section nur mit der vorherigen Section als
   Kontext — eine Figur kann so trotz sauberem Plan aus ihrem Wissens-Slice
   herausrutschen oder ein Handlungsstrang-Geheimnis zu früh durchsickern.
   `--fix` lässt die fertige Episode danach gegen ihr eigenes `case`-File
   prüfen und schreibt betroffene Parts gezielt neu (Ergebnis pro Episode in
   `scripts/<prefix>N_REVIEW.txt`):

   ```bash
   python3 -m fabrik.cli.generate_episode 9 --fix     # eine Episode prüfen + reparieren
   python3 -m fabrik.cli.generate_episode all --fix   # für alle Episoden
   # --no-script-review überspringt die Prüfung komplett
   ```

   Nützlich, wenn eine Szene (z.B. eine kurze, gedämpfte Konfrontation)
   organisch kürzer werden will als der Rest der Episode — steht kein
   Minimum für diese Section, scheitert die Generierung sonst nach 3
   Retries an einem Budget, das der Inhalt nicht hergibt.

   **Beat-Schicht (optional, `generation.use_beats`):** die Episoden-Review
   oben prüft erst NACH dem teuren Prosa-Schreiben, ob eine Figur aus ihrem
   Wissens-Slice gerutscht ist. Die Beat-Schicht setzt davor an: ein
   zusätzlicher Claude-Call plant pro Folge zuerst kurze Klartext-Beats für
   jede Szene (was passiert, wer lügt, was verschiebt sich — ohne
   Dialogzeilen), sieht dabei die ganze Folge auf einmal statt nur der
   vorigen Section, und wird selbst auf Wissens-Verstöße/Spoiler-Leaks
   geprüft, bevor überhaupt Prosa entsteht:

   ```json
   "generation": {"use_beats": true}
   ```

   Nur für case-basierte Templates (crime_drama/soap_opera) wirksam, Default
   aus — bestehende Serien laufen unverändert weiter. Ergebnis pro Folge in
   `scripts/<prefix>N_BEATS.txt` (+ `_BEATS_REVIEW.txt`). Auch über die
   WebUI schaltbar (Checkbox neben "Alles generieren + vertonen +
   Anthologie"). Details: `docs/beat-layer-design.md`.

3. **Vertonen** (braucht das venv wegen pydub/numpy/pyloudnorm, und einen
   laufenden Qwen3-TTS-MLX-Server unter `audio.api_url`):

   ```bash
   .venv/bin/python -m fabrik.cli.podcast_maker ep1.txt   # eine Episode (Dateiname reicht)
   .venv/bin/python -m fabrik.cli.batch                   # alle + Anthologie-Merge
   ```

   Jeder Text-Chunk wird als Checkpoint-WAV gesichert
   (`output/.checkpoints/`) — auch hier kann jederzeit abgebrochen
   und fortgesetzt werden. Fertige Parts/Episoden werden übersprungen.

   Nebenprodukte jeder Vertonung:
   - `<Episode>_FULL_EPISODE.srt` — Untertitel (satzweise getaktet, im
     Drama-Modus mit Sprechernamen bei jedem Wechsel), bei YouTube als
     Untertitelspur hochladen. `batch.py` merged sie zur
     `ANTHOLOGY_COMPLETE.srt`.
   - Drama-Modus: `<Episode>_SPEAKERS.json/.txt` — Sprecher-Timeline (wer
     spricht wann, inkl. Style/Emotion der Zeile) und
     `<Episode>_SFX_CUES.txt` (siehe unten).
   - `batch.py` zusätzlich: `ANTHOLOGY_COMPLETE_CHAPTERS.json` und eine
     fertige YouTube-Kapitelliste im `UPLOAD_INDEX.md` (in die
     Videobeschreibung kopieren → anklickbare Kapitel).
   - Liegen `intro.mp3`/`outro.mp3`/`transition.mp3` im Serienordner, werden
     sie automatisch eingesetzt (Jingle am Anfang/Ende, Sting zwischen den
     Szenen); alle Timelines/Untertitel verschieben sich korrekt mit.

## Drama-Skriptformat (mode: "drama")

```
--- PART 1 ---

[HOST | style: warm, slow, teacher-like]
Welcome back to the tea house...

[SFX: rain against the window, distant thunder]

[LIN_QIU | style: suspicious, lowered voice | speed: 0.9]
你到底想说什么？
```

(`HOST` ist die feste Führungsrolle bei `language_course`; bei `crime_drama`/
`soap_opera` heißt die entsprechende, ebenfalls verpflichtende Rolle
`NARRATOR` — siehe oben.)

- Rollen und ihre Stimmen stehen in `episodes.json` unter `voices`:

  ```json
  "voices": {
    "HOST":    {"voice": "Ryan",    "default_style": "warm, patient teacher",
                "description": "the English-speaking guide of the show"},
    "LIN_QIU": {"voice": "Chelsie", "default_style": "calm, observant", "speed": 0.9,
                "description": "retired detective, runs the tea house"}
  }
  ```

- `style` pro Zeile überschreibt den `default_style` der Rolle (auch `tone`/
  `emotion` als Alias), `speed` (0.5–2.0) steuert das Sprechtempo — z.B. 0.8
  für Lerner-Wiederholungen. Der Style landet zusätzlich in der
  Sprecher-Timeline und steuert im Video die Emotions-Visualisierung
  (siehe "Video-Podcast" unten).
- `[SFX: ...]`-Zeilen werden beim Rendern mit ihrem Zeit-Offset protokolliert
  → `output/<Episode>_SFX_CUES.txt` (Timestamps `MM:SS.mmm`) für das Mixing
  in der DAW. **Wichtig:** das ist nur eine Cue-Liste für manuelles
  Nachmischen — die fertige MP3 enthält KEIN SFX-Audio, nur die gesprochenen
  Zeilen. Ohne DAW-Nachbearbeitung ist die Episode reine Sprache ohne Atmo.
- `[NOTE: 词 — pinyin — meaning]`-Zeilen (nur `template: language_course`) sind
  reine Autoren-Buchhaltung: Claude flaggt damit jedes Vokabular/Grammatik-
  Item, das über das Kursniveau oder bereits Gelehrtes hinausgeht. Nie
  vertont, nie gecuet — beim Schreiben der nächsten Section automatisch
  wieder eingesammelt und der Analysis-Section als Pflichtliste vorgelegt
  (`fabrik/writing/script_writer.py:extract_vocab_notes`), damit kein geflaggtes Wort
  unerklärt bleibt.
- Unbekannte Sprecher oder kaputte Tags brechen VOR dem ersten TTS-Call mit
  Part- und Zeilenangabe ab.
- Längenbudget zählt sprachneutral: 1 chinesisches Zeichen = 1 Einheit,
  1 englisches Wort = 1 Einheit; Sprecher-Tags, SFX- und NOTE-Zeilen zählen
  nicht mit.
- Drama braucht ein Mehrstimmen-Backend (REST oder Kokoro); das Gradio-
  Backend (eine geklonte Stimme) wird von der Validierung abgelehnt.
- `audio.pause_between_lines_ms` (Default 700) steuert die Pause bei
  Sprecherwechseln, `pause_between_chunks_ms` die innerhalb einer Zeile.

Referenz-Beispiel: `data/series/tea_house_mysteries/` (HSK 3–4 Pilot-Serie).

## Video-Podcast (Lolfi-Integration)

Das Schwester-Projekt `../Lolfi` (`lofi_system.py`) rendert aus der fertigen
Anthologie ein Video: geloopter Ambient-Clip als Bild, die Episode(n) als
Tonspur. Die Podcast-Fabrik liefert dafür automatisch alle Metadaten — Lolfi
findet sie neben der Tonspur im `output/`-Ordner der aktiven Serie:

- **Charakter-Porträts:** `python3 -m fabrik.cli.character_prompts` (oder der
  WebUI-Schritt "Charakter-Porträts") erzeugt pro Drama-Rolle einen
  Bild-Prompt mit einheitlichem Ensemble-Stil, dazu je eine Prompt-Variante
  pro Emotion (Wut/Angst/Trauer/Freude/Überraschung/Zärtlichkeit). Ist
  `OPENAI_API_KEY` gesetzt, werden die Bilder direkt über `gpt-image-1-mini`
  generiert und als `data/series/<slug>/characters/<ROLLE>.png` bzw.
  `<ROLLE>_<emotion>.png` abgelegt (`--no-images` erzwingt Prompts-only auch
  mit gesetztem Key); ohne Key bleibt es bei `characters/PROMPTS.txt` zum
  Einfügen in ein beliebiges Bildmodell. Lolfi blendet das Porträt unten
  links ein, solange die Figur spricht (Quelle: `*_SPEAKERS.json`), inkl.
  Namens-Label ("Mara Voss"), und wechselt automatisch zur passenden
  `_<emotion>.png`-Variante, sobald für die Zeile eine erkannt wird.
- **Szenen-Orte:** bei Serien mit `locations`-Mapping (`episodes.json`, z.B.
  `soap_opera`) erzeugt `python3 -m fabrik.cli.location_prompts` (oder der
  WebUI-Schritt "Szenen-Orte") dieselbe Prompt(+Bild)-Pipeline für
  Hintergrundbilder statt Porträts — `data/series/<slug>/locations/<ORT_KEY>.png`
  (Landscape, für den Video-Hintergrund), gleiches `OPENAI_API_KEY`/
  `--no-images`-Verhalten wie bei den Porträts. Lolfi tauscht den
  Video-Hintergrund passend zur gerade aktiven Szene, ohne manuelles
  Timestamping (Quelle: `*_LOCATIONS.json`, aus den Section-Grenzen
  abgeleitet); ohne Match läuft der normale Loop-Clip weiter.
- **Emotionen:** der Zeilen-Style wird per Keyword-Listen einer Emotion
  zugeordnet (Wut/Angst/Trauer/Freude/Überraschung/Zärtlichkeit) — farbiges
  Panel hinter dem Porträt + Emoji-Badge, nur für die Dauer der Spanne.
  Konfiguration: `EMOTIONS`-Tabelle in `lofi_system.py`.
- **Episodentitel-Karten:** beim Start jeder Episode wird ihr Titel oben
  mittig eingeblendet (weich gefadet; Quelle: `*_CHAPTERS.json` bzw. die
  META-Datei der Einzelepisode).
- **Untertitel & Kapitel:** `.srt` und YouTube-Kapitelliste (siehe oben)
  werden nicht ins Video gebrannt, sondern beim Upload mitgegeben.
- **Cover-Art:** `python3 -m fabrik.cli.cover_art` erzeugt einmalig ein
  1024×1024-Serien-Cover via `gpt-image-1-mini` (braucht `OPENAI_API_KEY`,
  kein Prompts-only-Fallback) und kopiert es standardmäßig zusätzlich in den
  Serien-Ordner der externen Backup-Platte
  (`/Volumes/NO NAME/Podcasts/<Serientitel>/`, wird bei Bedarf angelegt;
  `--no-copy` zum Abschalten).

Text-Einblendungen laufen über Pillow-gerenderte PNGs + ffmpeg `overlay`
(das Homebrew-ffmpeg hat keinen drawtext-Filter) — `pip install pillow`
genügt, ein Systemfont wird automatisch gefunden.

## Story-Import: bestehenden Text statt Claude erfinden lassen

`import_story.py` ist das Gegenstück zu `create_series.py`: für bereits
fertige Geschichten/alte Romane, bei denen Claude NICHTS am Inhalt erfinden
soll — nur Titel/Thema-Metadaten werden zusammengefasst, der Skripttext wird
1:1 übernommen und deterministisch (ohne Claude) in `--- PART k ---`-Chunks
aufgeteilt, exakt im Format, das `podcast_maker.py`/`batch.py` bereits
verstehen. Unterstützt aktuell nur `mode: narration` (keine Dialog→
Sprecher-Tag-Adaption).

```bash
python3 -m fabrik.cli.import_story roman.txt "Der alte Roman"                 # eine lange Datei, automatische Kapitel-Erkennung
python3 -m fabrik.cli.import_story kapitel_ordner/ "Serie aus Kapiteln"       # ein Ordner, eine Datei pro Episode
python3 -m fabrik.cli.import_story roman.txt "Titel" --split-on "^Kapitel \d+" # Kapitel-Regex erzwingen
python3 -m fabrik.cli.import_story roman.txt "Titel" --no-summary             # kein Claude-Call, Titel kommt aus Dateiname/Kapitelzeile
```

- **Ordner als Quelle:** jede Datei (alphabetisch sortiert) wird eine
  Episode, Inhalt 1:1.
- **Einzelne Datei als Quelle:** erst Kapitel-Erkennung per Regex (`Chapter
  N`, `Kapitel N`, Markdown-Header, `1. ...`), bei keinem Treffer Fallback
  nach Wortzahl (`--words-per-episode`, Default 4000) entlang von
  Absatzgrenzen.
- Jede Episode wird direkt nach `--words-per-part-max` (Default 520)
  wortbasiert in PARTs zerlegt — **kein Minimum erzwungen**, der letzte
  Chunk einer Episode darf kürzer sein; die Quelle bestimmt die Länge.
- Importierte Episoden bekommen `"source": "imported"` in `episodes.json` —
  `generate_episode.py` überspringt sie automatisch (Skript existiert schon),
  vertont sie aber ganz normal über `podcast_maker.py`/`batch.py`.
- `audio.voice` steht nach dem Import auf dem Platzhalter `"MyVoice"` — vor
  dem Vertonen auf eine tatsächlich vorhandene Stimme anpassen.
- Auch über die WebUI verfügbar: Schritt 1 → "Alternative: aus vorhandenem
  Text importieren".

## Kokoro-MLX als Backend (Alternative zu Qwen3-TTS)

[Kokoro](https://github.com/Blaizzy/mlx-audio) läuft komplett lokal über das
`mlx-audio`-Paket (Apple Silicon), ohne separaten Server — jeder
`podcast_maker.py`-Lauf lädt das Modell selbst beim ersten Chunk. Sinnvoll
als schnelle, serverlose Alternative oder um weitere Stimmen zur Auswahl zu
haben.

```bash
.venv/bin/pip install mlx-audio
```

```json
"audio": {
  "backend": "kokoro",
  "voice": "af_heart",
  "model_path": "mlx-community/Kokoro-82M-bf16",
  "language_code": "a"
}
```

Einschränkungen:
- **Kein `instruct`/Style** — Kokoro folgt keinen Stilanweisungen; `style`/
  `section_styles` werden ignoriert (wie bei Voice-Clone-Backends). `speed`
  funktioniert.
- Für den Drama-Modus trotzdem nutzbar: jede Rolle im `voices`-Mapping
  bekommt einfach eine andere Kokoro-Voice-ID, nur die Stilanweisung pro
  Zeile geht verloren.
- **Sprachabdeckung und Voice-IDs hängen von der installierten mlx-audio-
  Version/dem Modell ab** und wurden hier NICHT gegen eine feste Liste
  geprüft (ändert sich zwischen Versionen zu schnell) — welche Stimmen und
  Sprachen (`language_code`) verfügbar sind, in der mlx-audio-Doku bzw. via
  `python -m mlx_audio.tts.generate --help` nachsehen, bevor `audio.voice`
  gesetzt wird. Ein falscher Name schlägt erst beim ersten Chunk fehl, nicht
  schon beim Start.
- `fabrik/audio/tts_backends.py:KokoroBackend` ist der Integrationspunkt, falls
  sich die `mlx_audio`-API zwischen Versionen ändert.

## Hinweise

- Der Episodenname wird aus dem Dateinamen abgeleitet (`ep1.txt` →
  `Ep1_FULL_EPISODE.mp3`) — `podcast_maker.py` und `batch.py` müssen sich
  darin einig sein, sonst wird doppelt vertont. `--name` überschreibt das.
- Stilanweisungen (`instruct`) wirken nur bei Built-in-Speakern; geklonte
  Stimmen (Voice-Prompts) unterstützen in der aktuellen API-Version kein
  `instruct` — `speed` funktioniert für beide. Praxis-Erfahrung: Klone
  klingen dadurch für Mehr-Rollen-Dialog (mode: drama) oft unfassbar
  monoton, weil jede Zeile in derselben Prosodie wie die eine
  Referenzaufnahme herauskommt — für Dialog-Rollen built-in Speaker
  bevorzugen, Klone eher für Erzähler-/Ein-Stimmen-Rollen reservieren.
- Stimmnamen aus `voices.*.voice`/`audio.voice`, die Claude beim Anlegen
  einer Serie erfindet, existieren nicht garantiert auf dem TTS-Server —
  `generate_episode.py check` warnt bei unbekannten Built-in-Namen
  (`fabrik/core/config.py::KNOWN_BUILTIN_SPEAKERS`), und `podcast_maker.py` prüft
  vor dem ersten TTS-Call gegen den Server und listet verfügbare
  Alternativen auf, bricht aber sonst sauber ab statt stumm falsch zu
  vertonen.
- **Akzente:** von den neun Built-in-Stimmen sind nur Ryan und Aiden (beide
  männlich) akzentfreie Englisch-Muttersprachler — alle anderen (inkl. ALLER
  Frauenstimmen) sind chinesisch-nativ, ihr Akzent ist in jeder Zeile hörbar.
  Produktionssprache ist deshalb Englisch (bzw. Chinesisch im Sprachkurs);
  die Creator-Prompts der Drama-Templates enthalten eine ACCENT CASTING RULE
  (Akzent = Charaktermerkmal mit passender Biografie, NARRATOR bekommt
  Ryan/Aiden).
- Parts werden verlustfrei als WAV zwischengespeichert; MP3-kodiert wird nur
  die fertige Episode. Die Anthologie entsteht per ffmpeg-Stream-Copy — ohne
  Re-Encode und ohne die Episoden in den RAM zu laden.
- Das venv ist Python 3.9 — `generate_episode.py`/`create_series.py` laufen
  mit jedem Python ≥ 3.9, `podcast_maker.py`/`batch.py` brauchen die
  venv-Pakete (pydub, numpy, pyloudnorm, requests, ffmpeg im PATH).
- `data/figure_history.json` bleibt global im Root: Serien-übergreifende Warnung
  vor wiederverwendeten Figuren.

## Windows/NVIDIA-Setup

Auf dem Mac läuft die Vertonung gegen **Qwen3-TTS-MLX** (Apple-Silicon-only).
Auf Windows/NVIDIA gibt es dafür kein MLX — stattdessen läuft dasselbe
Qwen3-TTS-Modell über PyTorch/CUDA via
[SUP3RMASS1VE/Qwen3-TTS](https://github.com/SUP3RMASS1VE/Qwen3-TTS) (bzw. den
Pinokio-Wrapper `Qwen3-TTS-Pinokio`). Anders als die Mac-Version ist das eine
reine Gradio-App ohne eigenes REST-API — `podcast_maker.py` spricht sie über
`gradio_client` an (`fabrik/audio/tts_backends.py`, `GradioBackend`).

### 1. Qwen3-TTS installieren

Voraussetzungen: Python 3.10+, NVIDIA-GPU mit CUDA 12.8 (~8 GB VRAM für die
0.6B-Modelle, ~16 GB für 1.7B). Entweder per Pinokio (`Qwen3-TTS-Pinokio`
App installieren) oder manuell nach der Anleitung in
[SUP3RMASS1VE/Qwen3-TTS](https://github.com/SUP3RMASS1VE/Qwen3-TTS). Start
über `python app.py` — die Gradio-UI läuft dann auf `http://localhost:7860`.

### 2. Referenzaufnahme für die geklonte Stimme

Referenz-Audio + Transkript für "MyVoice" müssen unter `data/voices/` abgelegt
werden (`data/voices/myvoice_ref.wav` + `audio.ref_text` in episodes.json).

### 3. episodes.json umstellen

```json
"audio": {
  "backend": "gradio",
  "api_url": "http://127.0.0.1:7860",
  "ref_audio": "data/voices/myvoice_ref.wav",
  "ref_text": "Das exakte Transkript der Referenzaufnahme..."
}
```

`backend: "rest"` (Default) bleibt für die Mac/MLX-Version bestehen.
Achtung: nur für `mode: "narration"` — Drama braucht das REST-Backend.

### 4. Vertonen

```
.venv\Scripts\python -m fabrik.cli.podcast_maker ep1.txt
.venv\Scripts\python -m fabrik.cli.batch
```

`gradio_client` ist bereits Teil des Projekts (in `.venv` installiert).
Voice-Clone unterstützt kein `instruct`/Style — `section_styles` aus
`episodes.json` werden mit diesem Backend ignoriert.

## Cloud-GPU statt Laptop (vast.ai)

Wenn die Vertonung auf dem eigenen Rechner zu lange dauert: [`cloud/`](cloud/README.md)
enthält Scripte, um automatisch eine RTX 5090 auf vast.ai zu mieten (`rent.sh`),
darauf per Onstart-Script einmalig Qwen3-TTS einzurichten, danach nur noch
zu pausieren/fortzusetzen (`stop.sh`/`resume.sh` — Festplatte inkl. Modell
bleibt erhalten, kein erneutes Setup nötig) und ganz normal lokal per `batch.py`
gegen die gemietete GPU zu vertonen (`audio.backend: "gradio"` in `episodes.json`).
