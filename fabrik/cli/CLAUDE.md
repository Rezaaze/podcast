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

## create_series.py

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
- Timeout skaliert: `compute_timeout` = 180s/Episode, Floor 900s, Cap
  3600s. Heartbeat alle 20s via `run_claude_process` (fabrik/core).
- **Batch-Pfad für große Case-Serien:** überschreiten crime_drama/
  soap_opera (`CASE_BASED_TEMPLATES`) zusammen
  `BATCH_THRESHOLD_EPISODE_MINUTES=200` Episodenminuten, weicht
  `skip_one_shot` auf `generate_series_batched` aus (episodes.json in
  mehreren Claude-Calls statt einem One-Shot am Output-Limit).

## generate_episode.py

- `check` — nur episodes.json validieren.
- `N [--force] [--fix] [--no-script-review]` — eine Episode; bei
  `"source": "imported"` wird die Generierung übersprungen und direkt
  `generate_episode_meta()` gerufen (Skript existiert schon).
- `all [--jobs N] [--force] [--fix] [--no-script-review]` — alle Episoden
  (Subprocess pro Episode), danach automatisch batch.py.
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
