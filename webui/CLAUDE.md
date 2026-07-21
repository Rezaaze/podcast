# webui — Flask-Cockpit für Podcast-Fabrik

Flask (`app.py`) + Vanilla JS (`static/app.js`), Single-Page. Eigenes venv
(`webui/.venv`, Setup via `./start_webui.sh`), Port 5151 (`WEBUI_PORT`
überschreibt).

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
- **Jobs sind pro Serie parallelisierbar, außer bei geteilter TTS-Ressource:**
  `runner.py::_lock_key()`: AUTO_TTS_COMMANDS (`pf_podcast_maker`,
  `pf_batch`, `pf_generate_episode_all` — teilen sich den EINEN lokalen
  Pinokio/Qwen3-Prozess, `tts_control.py`s start/stop ist nicht
  Refcount-fähig) teilen sich EINEN gemeinsamen Sperr-Schlüssel
  (`_TTS_LOCK_KEY = "__tts__"`, nicht command_id-spezifisch — sonst könnten
  z.B. `pf_batch` und `pf_podcast_maker` trotzdem gleichzeitig laufen und
  sich den TTS-Server gegenseitig unter den Füßen wegziehen), GLOBAL über
  alle Serien. Alle anderen `pf_*`-Kommandos (Skripte schreiben,
  Bild-Prompts, Cover, Thumbnails, SFX-Plan, Highlights) sind reine
  `claude`-CLI-Aufrufe ohne geteilte Ressource und laufen pro
  `(command_id, series)` — zwei Serien können also gleichzeitig Skripte
  schreiben. `jobs.snapshot()` (`/api/jobs`) ist entsprechend nach
  Lock-Key geschlüsselt (nicht mehr 1:1 nach command_id!) — jeder Eintrag
  trägt zusätzlich `command_id`/`series` als Felder; bestehende Leser wie
  `status.py`/`app.py` suchen deshalb über `status.any_command_running()`
  (iteriert die Werte nach `command_id`) statt per Dict-Lookup.
  `app.js::syncRunningJobs` sperrt einen Button nur, wenn der laufende Job
  global ist (Schlüssel ohne `"::"`) ODER seine Serie mit der gerade
  ausgewählten übereinstimmt — läuft beim Serienwechsel sofort neu (nicht
  erst beim nächsten 4s-Poll).

## Parallelbetrieb: Isolation + Launcher

- Jedes Cockpit ist ein EIGENER `app.py`-Prozess auf eigenem Port (eigener
  `jobs = JobRegistry()`, eigene aktive Serie). Zwei Env-Vars entkoppeln die
  aktive Serie vom globalen `data/series/LATEST` (sonst biegen parallele
  Instanzen sich gegenseitig um — besonders beim Anlegen): `WEBUI_ISOLATED=1`
  (aktive Serie pro Prozess im Speicher `_active`, LATEST wird nie geschrieben)
  bzw. `WEBUI_SERIES=<slug>` (isoliert + fest gepinnt, Umschalter gesperrt).
  `/api/pf/series` liefert dazu `active`/`pinned`/`isolated`. create_series
  druckt `PF_CREATED_SERIES=<slug>`; der Client parst die Marker-Zeile aus dem
  SSE-Stream und übernimmt SIE (nicht den globalen LATEST) — sonst landet ein
  Cockpit bei parallelen Creates auf der Serie einer Schwester-Instanz.
- `webui/launcher.py` (Start: `./start_launcher.sh`, Port 5150) ist ein
  Mini-Supervisor: Weboberfläche mit Start/Stop/Neustart je Cockpit. Spawnt
  `app.py` mit `WEBUI_PORT`/`WEBUI_ISOLATED`|`WEBUI_SERIES`, `start_new_session
  =True` (Cockpits überleben Launcher-Ende), merkt PIDs in
  `.launcher_state.json` (Re-Adoption nach Launcher-Neustart). Stopp vor der
  Vertonung: der Button „Alle Skripte generieren (ohne Vertonen)" ruft
  `generate_episode all --no-audio` (nicht in `AUTO_TTS_COMMANDS`).

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
- **`boolflag_off`: fehlendes Feld ≠ abgewählt** (Bugfix 17.07.2026, teuerster
  Produktionsfehler des Tages). `build_argv` las `value = params.get(name)` und
  hängte bei `if not value` das Abschalt-Flag an — `None` (Feld gar nicht
  geschickt) verhielt sich damit wie „Checkbox aus" und INVERTIERTE den
  CLI-Default. Zusammen mit dem Reload-Gotcha oben ist das scharf: ein
  Browser-Tab, der noch das HTML von vor der Einführung von `data-param-fix`
  hält, schickt `fix` nicht mit → `--no-fix` → die Reparatur läuft nie, obwohl
  die Checkbox sichtbar angehakt ist. Ergebnis in Produktion: drei frisch
  erzeugte Serien (the_glasshouse_vote 23, the_founding_collection 12,
  seven_seats 7) mit zusammen **42 korrekt geflaggten, aber nie applizierten**
  Review-Befunden — die Analyse las das zunächst als „Auto-Fix kaputt", dabei
  war die Reparatur intakt und wurde bloß nie aufgerufen. Jetzt:
  `if name in (params or {}) and not value`. Für JEDES künftige `boolflag_off`
  gilt: fehlt der Schlüssel, gilt der CLI-Default.
- `webui/tts_control.py::start_tts` wartet nach dem offenen Port zusätzlich
  auf `/health` (200 = Modell geladen; Server ohne /health-Endpoint: offener
  Port gilt als bereit). podcast_maker retried seinen Health-Check trotzdem
  weiter — für CLI-Läufe ohne WebUI-Start (siehe fabrik/audio/CLAUDE.md).
- Jobs werden ohne `stdin=` gespawnt — deshalb braucht jeder
  `claude`-Aufruf in der Pipeline `stdin=DEVNULL` (fabrik/core/CLAUDE.md).

## UI-Verhalten

- **Pro-Episode-Statuskarte (16.07.2026 überarbeitet):** vorher standen nur
  Skript/Audio in der Episode-Karte, Thumbnails/Highlights/SFX (letzteres gab
  es noch gar nicht) in verstreuten Serien-weiten Aggregat-Karten — "was fehlt
  noch zu Folge N" ließ sich nicht auf einen Blick beantworten.
  `status.py::pf_status()` liefert jetzt pro Episode zusätzlich
  `thumbnail_state`, `highlights_state`, `sfx_state`; `app.js::
  episodeDetailLine()`/`worstEpState()` fassen das in EINER Karte zusammen
  (Randfarbe = schlechtester Einzelzustand). Zwei Dimensionen sind bewusst
  bedingt sichtbar statt immer "offen" zu zeigen: `highlights_state` ist
  `"none"` (ausgeblendet), solange die Episode nicht vertont ist (highlight_
  clips.py braucht die Timing-Cues aus der Vertonung); `sfx_state` ist
  `"none"`, wenn kein SFX-Plan existiert oder diese Episode `keine` behaltenen
  Cues hat — kein Fehlzustand, nur "hier gibt's nichts zu prüfen". Die alte
  Aggregat-Karte "Episoden-Thumbnails" ist entfallen (Detail steckt jetzt pro
  Episode); eine neue "Sounddesign"-Karte (nur Drama-Serien) zeigt stattdessen
  `<Episoden mit fertigem SFX>/<Episoden mit Cues>` bzw. einen Hinweis, falls
  noch kein `sfx_plan` gelaufen ist. SFX-Abdeckung pro Episode vergleicht
  `SFX_PLAN.json`s behaltene Cues (Feld `asset_key`) gegen tatsächlich
  vorhandene Dateien in `sfx/oneshots/` — Hash-Herleitung (Plan-Feld `asset`,
  sonst `sfx_asset_hash(prompt)`) MUSS mit `fabrik/cli/sfx_assets.py::
  jobs_from_plan()` übereinstimmen, sonst zeigt das Cockpit eine Datei als
  fehlend, die podcast_maker/Lolfi längst unter einem anderen Namen finden.
- Log-Panel (`#log-panel`) startet eingeklappt, auto-expandiert bei
  Job-Start (`setLogOpen`); Status-Punkt im Header zeigt
  running/done/error auch eingeklappt.
- "Serie erstellen" spiegelt die create_series-Flags 1:1 (episodes,
  minutes, locations als Number-Inputs; `args_schema` in COMMANDS; für den
  "Block erzeugen"-Copy-Fallback `webui/prompt_blocks.py::
  build_series_prompt_block` / `/api/blocks/pf/series-prompt` — inkl.
  `locations`). Das Template-Dropdown wird NICHT mehr hart in index.html
  gepflegt: `config.list_templates()` enumeriert `templates/*/
  EPISODES_CREATOR_PROMPT.md` bei jedem Seitenaufruf (neue Templates
  erscheinen ohne Server-Neustart; Beschreibungen in
  `config.TEMPLATE_DESCRIPTIONS`). Das Orte-Feld ist nur sichtbar, wenn
  der Creator-Prompt des gewählten Templates `{{LOCATION_COUNT}}` enthält
  (`data-locations` an den Options, `app.js::syncLocationsVisibility`).
- Nach erfolgreichem Create zeigt `#pf-series-review`
  (`app.js::showSeriesReview`) das Konzept mit "Behalten"/"Verwerfen".
  Discard = `POST /api/pf/series/discard`, löscht `series/<slug>/` NUR
  solange keine Skripte und keine Outputs existieren (Server-Guard) und
  repointet LATEST auf die zuletzt geänderte verbleibende Serie; der
  Client merkt sich beim Klick auf "Serie erstellen" die vorher aktive
  Serie (`preCreateSlug`) und stellt sie nach Discard wieder her
  (Dropdown + LATEST).
- "Szenen-Orte"-Step (`pf_location_prompts`) spiegelt den
  Charakter-Porträts-Step 1:1 (`status.py`s `locations`-Dict,
  `pf-step-locations` versteckt, außer die Serie hat `locations`).
- `pf_cover_art` (Button im Visuals-Bereich) wrappt `fabrik.cli.cover_art`
  (`--force`, braucht OPENAI_API_KEY); `status.py` meldet `cover_exists`
  (`.../04_visuals/output/cover.png`) für die Statuskarte.
- **Episoden-Thumbnails-Step** (`#pf-step-thumbnails`, `pf_episode_thumbnails`
  → `fabrik.cli.episode_thumbnails`): dramatisches, spoilerfreies
  Poster-Thumbnail pro Episode (Hook-Zeile + Symbol-Motiv, 16:9 + 1:1) —
  läuft AUTOMATISCH am Ende jeder Episoden-Generierung mit (siehe
  fabrik/cli/CLAUDE.md), der Knopf hier ist nur zum Nachholen (Key erst
  später gesetzt) oder gezielten `--force`-Neu-Generieren einzelner
  Episoden über das Nummernfeld (`#pf-thumbnails-episode`, optional, leer =
  alle). `status.py` liefert `thumbnails.{ready,total}` (beide Größen pro
  Episode vorhanden) für die Statuskarte.
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
- Generier-Buttons tragen die Checkboxen Review-Fix
  (`#pf-fix-review`, seit 17.07.2026 DEFAULT ANGEHAKT und invertiert
  verdrahtet: CLI-Default ist `--fix`, die Checkbox abwählen hängt
  `--no-fix` an — neuer `args_schema`-Kind `boolflag_off` in runner.py)
  und `use_beats` (persistiert wie
  merge_anthology via `POST /api/pf/series/settings`; `GET /api/pf/series`
  liefert den Wert pro Serie, `updateUseBeatsCheckbox()` synct beim
  Serienwechsel).
- **Teaser-Highlights-Step** (`#pf-step-highlights`): `pf_highlight_clips`
  (Episoden-NUMMER via `#pf-highlight-episode`, leer = alle vertonten)
  schreibt die HIGHLIGHTS.json (Zeiten + Hook-Text) neben die MP3, „📂
  Audio-Output" ist das Review-Gate zum Hand-Editieren — Weiterverarbeitung
  (Clips schneiden) läuft außerhalb der WebUI, in einem Video-Editor nach
  Wahl. `status.py` liefert dazu das `highlights`-Dict (vertonte Episoden
  vs. Episoden mit HIGHLIGHTS.json).
