# MWP-Pfad-Inventur (T2.2) — Pflicht-Checkliste für Phase 3–5

Jede Zeile wird beim Umbau abgehakt. Neue Pfade beziehen sich auf das
Ziel-Layout aus `mwp-umbau-plan.md`:

- `stages/01_concept/output/episodes.json`
- `stages/02_scripts/output/` (statt `scripts/`)
- `stages/03_audio/output/` (statt `output/`, inkl. `.checkpoints/`, `.cues/`)
- `stages/04_visuals/output/characters/` bzw. `.../locations/` (statt
  `characters/`, `locations/`)
- `references/` (Template-Kopien), `assets/` (intro/outro/transition.mp3)

**Zentraler Befund:** Fast alle Konsumenten gehen durch
`fabrik/core/paths.py::Series` oder bauen `os.path.join(series_dir, "<fix>")`
mit denselben fünf Ordnernamen. Der Umbau konzentriert sich auf paths.py +
eine Handvoll Join-Stellen.

## 1. Zentral: fabrik/core/paths.py (T3.1) — eine Änderung wirkt überall

- [x] `Series.__init__`: `episodes_file` → `stages/01_concept/output/episodes.json`
- [x] `Series.__init__`: `scripts_dir` → `stages/02_scripts/output`
- [x] `Series.__init__`: `output_dir` → `stages/03_audio/output`
      (`checkpoint_dir`/`cues_dir` hängen daran und folgen automatisch)
- [x] `Series.__init__`: `anthology_meta_file` (liegt in scripts_dir, folgt)
- [x] NEU: `visuals_dir`, `characters_dir`, `locations_dir`,
      `references_dir`, `assets_dir`, `stage_context_file(n)`
- [x] `ensure_dirs()`: legt den ganzen `stages/`-Baum an
- [x] `list_series()`: prüft `episodes.json` am NEUEN Ort
- [x] `Series.root`-Konsumenten prüfen (grep `series.root`)

## 2. fabrik/ — Stellen, die an paths.py vorbei joinen

- [x] `fabrik/cli/character_prompts.py:144` — `join(series.root, "characters")`
      → `series.characters_dir`
- [x] `fabrik/cli/location_prompts.py:43` — `join(series.root, "locations")`
      → `series.locations_dir`
- [x] `fabrik/cli/podcast_maker.py:~901` — `find_audio_asset(series, ...)`
      (sucht intro/outro/transition; Quelle prüfen) → `series.assets_dir`
- [x] `fabrik/cli/create_series.py` — Scaffolding NEU (T3.2): stages-Baum,
      CONTEXT.md-Befüllung, Template-Kopie nach `references/`
- [x] `fabrik/cli/import_story.py` — gleiches Scaffolding (T3.4)
- [x] `fabrik/writing/script_writer.py` — Prompt-Quelle: `template_dir(name)`
      → `series.references_dir/PROMPT_TEMPLATE.md` (T3.3)
- [x] `fabrik/cli/cover_art.py` — Ablageort prüfen → 04_visuals

Bereits sauber (folgen paths.py automatisch, nur nachtesten):
`podcast_maker.py::voices_manifest_path` (output_dir), Cue-/Subs-Caches
(cues_dir), `batch.py` UPLOAD_INDEX (output_dir),
`pipeline.py::_PART_OFFSETS` (vom Episodenpfad abgeleitet),
`history.py`/`figure_history.json` (global, bleibt).

## 3. webui/ (T4.1/T4.2) — baut Pfade selbst aus series_dir

- [x] `webui/config.py:27` — Serien-Listing via `<dir>/episodes.json`
- [x] `webui/config.py:70` — `episodes_json_path()`
- [x] `webui/status.py:48–53` — scripts_dir / episodes.json / output_dir /
      checkpoints_dir
- [x] `webui/status.py:92` — characters_dir
- [x] `webui/status.py:108` — locations_dir
- [x] `webui/status.py:139–140` — ANTHOLOGY_META.txt / UPLOAD_INDEX.md
- [x] `webui/status.py:161, 214` — Episoden-MP3-Listing (`output/`)
- [x] `webui/prompt_blocks.py:105–180` — characters/, locations/,
      scripts/ANTHOLOGY_META.txt, output/UPLOAD_INDEX.md
- [x] `webui/runner.py:279` — `output/.checkpoints`-Polling
- [x] `webui/app.py:43, 77` — episodes.json-Zugriffe
- [x] `webui/app.py:102–105` — Discard-Guard (scripts/*.txt + output/)
      → muss `stages/*/output/` prüfen
- [x] `webui/folders.py:41–42` — "Ordner öffnen"-Subdir-Map
      (pf_output/pf_characters/pf_locations) → neue Stage-Pfade, ggf. pro
      Stage ein Eintrag (Review-Gate-Links, T4.3)

**Empfehlung für T4.x:** webui soll `fabrik.core.paths` importieren
(stdlib-only, kein venv-Konflikt) statt das Layout ein zweites Mal zu
kennen — dann kann es nicht wieder divergieren.

## 4. Lolfi (`~/Downloads/Lolfi`, T5.1) — separates Repo!

- [x] `lofi_system.py:~58` — Auflösung "output/-Ordner der aktiven Serie"
      (data/series/LATEST → `<slug>/output/`) → `stages/03_audio/output/`
- [x] `lofi_system.py:~101` — `characters/`-Ordner der Serie
      → `stages/04_visuals/output/characters/`
- [x] `lofi_system.py:~294` — `series/<slug>/locations/<ORT_KEY>.png`
      → `stages/04_visuals/output/locations/`
- [x] `generate_prompts.py` — 4 Fundstellen prüfen (vermutlich nur
      Doku/Kommentare, sonst anpassen)
- Dateinamens-Konventionen (`*_FULL_EPISODE.mp3`, `*_SPEAKERS.json`,
  `*_SUBS.json`, `*_LOCATIONS.json`, `*_CHAPTERS.json`) bleiben
  unverändert — nur die Ordner wandern.

## 5. Sonstiges

- [x] `.gitignore` — neue Muster: `data/series/*/stages/*/output/*`
      ignorieren, ABER `!data/series/*/stages/01_concept/output/episodes.json`
      (Negativ-Pattern, sonst verschwinden Serien-Definitionen aus Git).
      Provisorisch direkt nach T3.2 setzen, final in T6.3.
- [ ] `README.md` + Root-`CLAUDE.md` + Bereichs-CLAUDE.md — Pfadangaben
      aktualisieren (T6.3)
- [x] `webui/prompt_blocks.py::build_series_prompt_block` — erwähnt
      Zielpfade im manuellen Copy-Block? Prüfen.
- Nicht betroffen: `cloud/` (spricht nur mit dem TTS-Server, keine
  Serien-Pfade), `data/voices/`, `data/figure_history.json`,
  `templates/<name>/` (bleibt Master-Quelle; NEU dazu:
  `templates/_workspace/`).
