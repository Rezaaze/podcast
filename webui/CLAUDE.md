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
- **Vertonungs-Ziel Lokal/Cloud** (`#pf-render-target`, localStorage
  `pfRenderTarget`): bei „cloud" schreibt `app.js::maybeCloudRewrite` die
  Buttons `pf_batch`/`pf_podcast_maker` beim Klick auf `pf_render_remote`
  um (`cloud/render_remote.sh`; Einzel-Episode wird `--only <datei>`,
  Checkbox `#pf-cloud-stop-after` wird `--stop-after`). `pf_render_remote`
  ist absichtlich NICHT in `AUTO_TTS_COMMANDS` (TTS läuft auf der
  vast.ai-Instanz) und läuft mit `interpreter_args: []` (bash — `-u` hieße
  dort nounset, siehe runner.py). Der große „Alles generieren"-Button
  vertont weiterhin immer lokal.
- **Parallel-Cloud-Button** (`pf_render_remote_parallel`, eigener Button
  „☁︎ Fehlende Episoden parallel in der Cloud vertonen" + Zahlenfeld
  `#pf-cloud-max-parallel` → `--max`): unabhängig vom Lokal/Cloud-
  Umschalter, wrappt `cloud/render_remote_parallel.sh` — erkennt fehlende
  Episoden selbst, rendert bis zu N gleichzeitig in Wellen (Instanzen
  werden nur einmal beschafft, über alle Wellen wiederverwendet). Details/
  Kostenlogik: cloud/README.md.
- Generier-Buttons tragen die Checkboxen `--fix`-Review
  (`#pf-fix-review`, `data-param-fix`) und `use_beats` (persistiert wie
  merge_anthology via `POST /api/pf/series/settings`; `GET /api/pf/series`
  liefert den Wert pro Serie, `updateUseBeatsCheckbox()` synct beim
  Serienwechsel).
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
