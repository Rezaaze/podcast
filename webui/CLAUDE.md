# webui — Flask-Cockpit für Podcast-Fabrik UND Lolfi

Flask (`app.py`) + Vanilla JS (`static/app.js`), Single-Page mit zwei Tabs
(Podcast-Fabrik / Lolfi). Eigenes venv (`webui/.venv`, Setup via
`./start_webui.sh`), Port 5151 (`WEBUI_PORT` überschreibt).

Lolfi ist ein SEPARATES Projekt (`~/Downloads/Lolfi`, Video/Musik, nicht in
diesem Repo); `webui/config.py` hardcodet `LOLFI_DIR` — nicht wundern über
"lolfi_*"-Pfade.

## Architektur

- Kommandos zentral deklariert in `webui/config.py::COMMANDS` (id → Modul +
  Arg-Mapping), ausgeführt von `webui/runner.py::JobRegistry` als
  Subprocess, stdout via SSE an den Browser (`/api/stream/<job_id>`).
- `webui/status.py` pollt Dateisystem-Zustand (welche Skripte/Audios
  existieren) für Step-Wizard und Statuskarten.
- Aktive Serie ist Client-State, der nach `data/series/LATEST`
  durchschreibt (`/api/pf/series/active`) — CLI-Läufe außerhalb des WebUI
  nutzen denselben Default. `pf_create_series` und `pf_import_story`
  erzeugen NEUE Serien und sind vom auto-angehängten `series`-Param
  ausgenommen (`app.js::PF_SERIES_SCOPED_EXCLUDE`); jedes andere
  `pf_*`-Kommando bekommt die gewählte Serie automatisch injiziert.

## Gotchas (beide in Produktion gelernt)

- **Reload:** Flask läuft mit `debug=False`, aber `TEMPLATES_AUTO_RELOAD`
  ist an — Edits an `templates/*.html` und `static/*` greifen beim
  nächsten Browser-Reload; Python-Änderungen in `webui/*.py` brauchen
  einen Server-Neustart (kein Reloader).
- **Checkbox-Bug in `collectParams`:** `el.value` einer
  `<input type="checkbox">` ist IMMER `"on"`, egal ob gecheckt. Gefixt zu
  `el.type === "checkbox" ? el.checked : el.value` — aufgefallen erst mit
  der `--fix`-Checkbox, weil vorher kein Boolflag über den
  `data-param-*`-Pfad lief (die ältere merge_anthology-Checkbox hat einen
  eigenen Change-Listener). Bei neuen `data-param-*`-Controls beachten.
- `webui/tts_control.py::start_tts` wartet nach dem offenen Port zusätzlich
  auf `/health` (200 = Modell geladen; Server ohne /health-Endpoint: offener
  Port gilt als bereit). podcast_maker retried seinen Health-Check trotzdem
  weiter — für CLI-Läufe ohne WebUI-Start (siehe fabrik/audio/CLAUDE.md).
- Jobs werden ohne `stdin=` gespawnt — deshalb braucht jeder
  `claude`-Aufruf in der Pipeline `stdin=DEVNULL` (fabrik/core/CLAUDE.md).

## UI-Verhalten

- Log-Panel (`#log-panel`) startet eingeklappt, auto-expandiert bei
  Job-Start (`setLogOpen`); Status-Punkt im Header zeigt
  running/done/error auch eingeklappt.
- "Serie erstellen" spiegelt die create_series-Flags 1:1 (episodes,
  minutes, locations als Number-Inputs; `args_schema` in COMMANDS; für den
  "Block erzeugen"-Copy-Fallback `webui/prompt_blocks.py::
  build_series_prompt_block` / `/api/blocks/pf/series-prompt`).
- Nach erfolgreichem Create zeigt `#pf-series-review`
  (`app.js::showSeriesReview`) das Konzept mit "Behalten"/"Verwerfen".
  Discard = `POST /api/pf/series/discard`, löscht `series/<slug>/` NUR
  solange keine Skripte und keine Outputs existieren (Server-Guard) und
  repointet LATEST auf die zuletzt geänderte verbleibende Serie.
- "Szenen-Orte"-Step (`pf_location_prompts`) spiegelt den
  Charakter-Porträts-Step 1:1 (`status.py`s `locations`-Dict,
  `pf-step-locations` versteckt, außer die Serie hat `locations`).
- `pf_cover_art` (Button im Visuals-Bereich) wrappt `fabrik.cli.cover_art`
  (`--force`, braucht OPENAI_API_KEY); `status.py` meldet `cover_exists`
  (`.../04_visuals/output/cover.png`) für die Statuskarte.
- **Sounddesign-Step** (`#pf-step-sound`) mit drei Knöpfen: `pf_sfx_plan`
  (Claude; Checkbox `#pf-sfx-plan-force` → `--force`), `pf_sfx_assets` und
  `pf_location_ambience` (beide ElevenLabs). Zwei Dinge, die man beim
  Anfassen wissen muss:
  - `sfx_plan` läuft bei Drama-Serien (`mode: drama`) ohnehin AUTOMATISCH
    in `generate_episode all` (also
    hinter dem großen „Alles generieren"-Button) — und zwar VOR `batch`,
    weil er Stille-Lücken in die Episoden-MP3 einfügt. Der Knopf hier ist
    nur für Einzel-Episoden und fürs Neu-Planen. Ihn in eine Kette NACH dem
    Vertonen zu hängen wäre wirkungslos (die MP3 ist dann schon fertig).
  - Die beiden ElevenLabs-Knöpfe **kosten pro Lauf Guthaben** und sind
    deshalb bewusst in keiner Automatik. Sie brauchen `ELEVENLABS_API_KEY`
    in der Umgebung des WebUI-Prozesses (der erbt sie von der Shell, die
    `start_webui.sh` gestartet hat — ein Key, der nur in einer anderen Shell
    exportiert wurde, fehlt hier). Fertige Sounds werden übersprungen, ein
    zweiter Klick kostet also nichts.
- **Vertonungs-Ziel Lokal/Cloud** (`#pf-render-target`, localStorage
  `pfRenderTarget`): bei „cloud" schreibt `app.js::maybeCloudRewrite` die
  Buttons `pf_batch`/`pf_podcast_maker` beim Klick auf `pf_render_remote`
  um (`cloud/render_remote.sh`; Einzel-Episode wird `--only <datei>`,
  Checkbox `#pf-cloud-stop-after` wird `--stop-after`, Checkbox
  `#pf-cloud-local-master` wird `--local-master` — Mastering/Post-
  Processing dann lokal statt auf der Instanz; beide Checkboxen blendet
  `syncRenderTargetUI` nur bei Ziel „cloud" ein). `pf_render_remote`
  ist absichtlich NICHT in `AUTO_TTS_COMMANDS` (TTS läuft auf der
  vast.ai-Instanz) und läuft mit `interpreter_args: []` (bash — `-u` hieße
  dort nounset, siehe runner.py). Der große „Alles generieren"-Button
  vertont weiterhin immer lokal.
- **Parallel-Cloud-Button** (`pf_render_remote_parallel`, eigener Button
  „☁︎ Fehlende Episoden parallel in der Cloud vertonen" + Zahlenfeld
  `#pf-cloud-max-parallel` → `--max`): unabhängig vom Lokal/Cloud-
  Umschalter, wrappt `cloud/render_remote_parallel.sh` — erkennt fehlende
  Episoden selbst, rendert bis zu N gleichzeitig in Wellen (Instanzen
  werden nur einmal beschafft, über alle Wellen wiederverwendet). Das
  Schema kennt zusätzlich `--episodes` (explizite Liste; aktuell ohne
  UI-Feld). Details/Kostenlogik: cloud/README.md.
- **Server-Pool (Scouting):** „Nächsten Server mieten" (`pf_cloud_rent` →
  `cloud/rent.sh` als normaler Job; in `PF_SERIES_SCOPED_EXCLUDE`, kein
  series-Param) + Liste `#pf-cloud-pool` aus `GET /api/cloud/instances`
  (vastai-Live-Instanzen gemerged mit `cloud/.machine_stats.json`).
  ★ Favorit / ✗ Verwerfen posten `POST /api/cloud/machine`
  (favorite|unfavorite|reject; reject destroyt optional die Instanz) →
  `machine_stats.py`-Subcommands. `manual=True` schützt das Urteil vor
  der 10-Min-Heuristik, `avoid=True` meidet die Maschine dauerhaft in
  jeder Offer-Suche. Manuell beurteilte Maschinen bleiben immer gelistet
  (sonst wäre „Favorit entfernen" im UI nicht umkehrbar).
- Generier-Buttons tragen die Checkboxen `--fix`-Review
  (`#pf-fix-review`, `data-param-fix`) und `use_beats` (persistiert wie
  merge_anthology via `POST /api/pf/series/settings`; `GET /api/pf/series`
  liefert den Wert pro Serie, `updateUseBeatsCheckbox()` synct beim
  Serienwechsel).
- **Teaser-Clips-Step (Lolfi-Tab, Schritt 5):** `pf_highlight_clips`
  (Episoden-NUMMER via `#pf-highlight-episode`, leer = alle vertonten)
  schreibt die HIGHLIGHTS.json, „📂 Audio-Output" ist das Review-Gate zum
  Hand-Editieren, `lolfi_clips` (nutzt das Episoden-Dropdown aus Schritt 4,
  Dateinamen-Fragment) rendert die 9:16-Clips nach `video/output/`.
  Checkbox `#lolfi-clips-full` (`--full`) rendert stattdessen die GANZE
  Episode als ein 9:16-Video — der Weg für nativ kurze Serien
  (create_series mit 1–3 Minuten), keine Highlights-Auswahl nötig.
  `status.py` liefert dazu das `highlights`-Dict (vertonte Episoden vs.
  Episoden mit HIGHLIGHTS.json).
- Lolfi-Tab: Episoden-Dropdown (`#lolfi-episode-select`, gefüttert von
  `status.py::_list_podcast_episode_files`, wird `--episode <filename>`),
  "▶ Video rendern" (Dropdown leer = Automatik: Anthologie bevorzugt,
  sonst die numerisch ERSTE Einzel-Episode — seit Lolfi-Commit 6f15ed1
  natürliche Sortierung, Ep2 vor Ep10) und "▶ Alle Episoden einzeln
  rendern" (`lolfi_render_all`,
  `lofi_system.py --all`) als Ausweg für merge_anthology:false-Serien.
- Lolfis Hintergrund-Loop ist ein statischer Clip in
  `video/baseline_normal/` (auto-erzeugt von generate_prompts.py mit
  OPENAI_API_KEY); der Kling.ai-Workflow wurde entfernt —
  `video/baseline/` (Ping-Pong) funktioniert nur noch mit manuell
  platziertem Clip.
