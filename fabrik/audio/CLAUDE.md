# fabrik/audio — Vertonung (braucht .venv: pydub, numpy, pyloudnorm, requests + ffmpeg)

`fabrik/core/` und `fabrik/writing/` dürfen NIE von hier importieren — das
würde den No-venv-Pfad der Skript-Generierung brechen.

## Pipeline-Grundriss (`pipeline.py`, `tts_backends.py`)

podcast_maker.py/batch.py chunken jeden Skript-Part via
fabrik/core/textproc.py, schicken Chunks ans TTS-Backend, checkpointen jeden
gerenderten Chunk als WAV (`stages/03_audio/output/.checkpoints/`,
resumierbar wie die
Skript-Generierung), dann LUFS-Mastering und Merge zu finaler MP3 mit ID3.

- Drei Backends (`audio.backend` in episodes.json): `rest` (Qwen3-TTS-MLX,
  Apple Silicon, Default, **Pflicht für mode: drama**), `gradio`
  (Windows/CUDA via gradio_client, nur narration; auch der Weg zu einer
  gemieteten vast.ai-GPU), `kokoro` (mlx-audio, kein Style/Instruct).
- Jeder TTS-Call ist voll zustandslos (voice/style/speed explizit pro
  Chunk) — Generierungsreihenfolge hat keinen Einfluss auf Audioqualität,
  Batching nach Sprecher brächte nichts.
- Anthologie-Merge nutzt ffmpeg stream-copy — Episoden werden nie
  re-encodiert oder voll in RAM geladen.
- `batch.py` merged ab ≥2 fertigen Episoden zu `ANTHOLOGY_COMPLETE.mp3`;
  `audio.merge_anthology: false` (z. B. soap_opera: Episoden erscheinen
  einzeln) skippt Merge/Subtitle-Merge/Chapters/Anthologie-Meta, schreibt
  aber weiterhin per-Episode `UPLOAD_INDEX.md`. Auch als WebUI-Checkbox
  (persistiert in episodes.json via `POST /api/pf/series/settings`).

## Selbstheilung statt Stehenbleiben

- `batch.py::main()` fährt bis `BATCH_RETRY_ROUNDS=2` Zusatzrunden (20s
  Abstand) nur über die noch fehlschlagenden Episoden, bevor es aufgibt —
  ein transienter TTS-Schluckauf hieß früher "Episode liegt still, bis ein
  Mensch es merkt und neu klickt". Checkpoints/Part-WAVs fertiger Chunks
  bleiben erhalten, ein Rerun resumed mitten in der Episode.
- **Fehlschlag-Alarm:** endgültig gescheiterte Episoden schreibt batch.py
  nach `output/FAILED_EPISODES.json` (ein späterer erfolgreicher Lauf löscht
  den Marker) — `webui/status.py` liest ihn und die WebUI zeigt eine rote
  Statuskarte, statt dass der Fehlschlag nur als Log-Zeile verhallt.
- **Zweiter TTS-Server (optional):** `audio.secondary_api_url` lässt
  batch.py zwei Episoden parallel vertonen — zwei Worker an einer Queue,
  Worker 2 rendert via `podcast_maker --api-url`. Der zweite Server muss
  dieselben Stimmen/Clones anbieten; ist er beim Start nicht erreichbar
  (`url_reachable`, jede HTTP-Antwort zählt), läuft alles sequentiell über
  den Primär-Server. `episode_pairs` wird nach Episoden-Index sortiert
  aufgebaut, die Merge-Reihenfolge bleibt also stabil.
- `podcast_maker.py` retried `backend.check_api()` 3× im 10s-Abstand statt
  sofort abzubrechen: `webui/tts_control.py::start_tts` pollt zwar
  inzwischen `/health` nach dem Port (Modell-Load wird abgewartet), aber
  CLI-Läufe ohne WebUI-Start und Backends ohne /health-Endpoint brauchen
  das Netz weiterhin.

## Post-Merge-Crash-Sicherheit (wichtigste Invariante hier)

`merge_parts_to_episode` löscht die Part-WAVs sofort nach dem Schreiben der
Episoden-MP3 und persistiert `part_offsets` VOR dem Return nach
`<Episode>_PART_OFFSETS.json` (`part_offsets_path`/`load_part_offsets`).
Grund: die vier Post-Merge-Schritte (SFX-Cue-Sheet, Speaker-Timeline,
Untertitel, Location-Timeline) lesen kleine Per-Part-JSONs und liefen
früher ungeschützt NACH dem Point of no Return — ein Raise dort (z. B.
truncated Side-File nach Kill mitten im Write) ließ die MP3 als "fertig"
und die WAVs als gelöscht zurück, und der einzige Resume-Check
(`if os.path.exists(episode_path): return`) übersprang die Episode für
immer ohne die fehlenden Metadaten je nachzuholen. Fix:

1. Jeder Post-Merge-Schritt einzeln in try/except
   (`podcast_maker.py::run_postprocessing` — warnt und macht weiter).
2. `run_postprocessing` läuft auch, wenn die Episoden-MP3 schon existiert,
   mit den persistierten `part_offsets` statt der (gelöschten) WAVs —
   billig und idempotent, keine Re-Vertonung.
3. Episoden von vor diesem Fix haben kein `_PART_OFFSETS.json` → beim
   Resume nur ID3-Tagging (Offsets ohne Original-WAVs nicht
   rekonstruierbar).

## SFX, Assets, Untertitel, Timelines

- `[SFX: ...]`-Cues werden **nie ins Audio gemischt** — nur mit Timestamps
  nach `output/<Episode>_SFX_CUES.txt` geloggt (manuelles DAW-Mixing).
  Genau deshalb verlangen die Drama-Templates gesprochene
  NARRATOR-Orientierungszeilen (siehe templates/CLAUDE.md).
- Optionale Serien-Assets `intro.mp3|outro.mp3|transition.mp3` (Jingle
  Anfang/Ende, Sting statt Inter-Part-Stille); die von
  `merge_parts_to_episode` gelieferten Offsets schließen sie ein, alle
  Cue-Sheets bleiben korrekt.
- Untertitel pro Render: `<Episode>_FULL_EPISODE.srt` (satzweise,
  Sprechername-Präfix bei Rollenwechsel — für YouTube) + `_SUBS.json`,
  dessen Cues zusätzlich ein sauberes (unpräfixtes) `"role"`-Feld tragen —
  bewusst getrennt vom .srt-Text; Lolfi zeigt damit die gesprochene Zeile
  als Dialog-Bubble neben dem Porträt (nur für Cues im aktiven
  Porträt-Fenster der Rolle). batch.py merged zu
  `ANTHOLOGY_COMPLETE.srt` und schreibt `ANTHOLOGY_COMPLETE_CHAPTERS.json`
  + YouTube-Kapitelliste in `UPLOAD_INDEX.md`.
- **Speaker-Timeline (nur drama):** `<Episode>_SPEAKERS.json` (+ .txt),
  Per-Part-Cache in `output/.cues/*_speakers.json`. Spans mergen nur
  innerhalb gleicher Rolle+Style (Lolfi mappt Style→Emotion via EMOTIONS-
  Keyword-Listen: Farbpanel, Emoji-Badge und Porträt-Variante
  `<ROLE>_<emotion>.png`). Zusätzlich `scenes`-Array
  (`build_scene_presence`): pro PART die Menge aller dort sprechenden
  Rollen = wer in der Szene ANWESEND ist — Lolfi zeigt damit auch die
  Zuhörer-Porträts. Rein aus `part_offsets` abgeleitet, kein Extra-Prompt.
- **Location-Timeline (mode-unabhängig, eigene Datei):**
  `build_location_timeline` löst pro PART den Section-Index
  (`part_idx // parts_per_section`) gegen `section_locations` auf →
  `<Episode>_LOCATIONS.json`. batch.py merged zu
  `ANTHOLOGY_COMPLETE_LOCATIONS.json` (nur bei merge_anthology). Lolfi
  wechselt damit den Video-Hintergrund pro Szene (Fallback: Standard-Loop
  bei Lücken/unbekannten Keys). Vollständig additiv — Serien ohne
  `locations` rendern exakt wie vorher.
- In crime_drama/soap_opera öffnen Episoden ≥2 mit einem gescripteten
  `[NARRATOR]`-"previously on"-Recap (`build_intro_spec`, template-gated —
  language_course behält seine HOST-Recap-Konvention).

## Stimm-Konsistenz — zwei harte Guards

1. `config.py::validate_data` hard-errort bei zwei Rollen mit derselben
   Stimme (siehe fabrik/core/CLAUDE.md).
2. Checkpoints/Part-WAVs/MP3s sind rein nach DATEINAME gecacht, nicht nach
   Voice-Konfig — ein späteres Editieren von `voices.<ROLE>.voice` würde
   sonst still eine Mixed-Voice-Serie erzeugen.
   `podcast_maker.py::check_voice_consistency` vergleicht darum bei jedem
   Lauf gegen `output/.voices_manifest.json` und **hard-exitet vor dem
   ersten Dateizugriff**, wenn sich voice/speed/seed einer Rolle geändert
   hat. Ausweg nur explizit: episodes.json zurücksetzen ODER betroffene
   Episoden bewusst neu rendern und das stale Manifest löschen.
3. **Baseline erst nach bestätigter Auflösbarkeit:**
   `check_voice_consistency()` VERGLEICHT nur (no-op ohne Manifest); der
   Write ist separat — `commit_voice_manifest()` läuft erst, wenn das
   Backend erreichbar ist UND jeder Rollen-Voice-Name aufgelöst wurde,
   direkt vor der Render-Schleife. Früher schrieb der Check das Manifest
   sofort beim ersten Aufruf — ein Sekunden später gescheiterter Lauf
   (Tippfehler im Voice-Namen, Server down) hinterließ die kaputte Konfig
   als "already rendered", und der spätere Fix hard-failte gegen diese
   Phantom-Baseline, obwohl nie etwas gerendert worden war.

## Seed / Voice-Clones

- `resolve_voice()` liefert überall das 3-Tupel `(kind, voice_id, seed)`.
- `voices.<ROLE>.seed` (drama) / `audio.seed` (narration bzw. Fallback)
  wirkt NUR bei `RestBackend` + Clone-Stimmen (`kind == "prompt"`): der
  lokale Qwen3-Server exponiert `seed` nur auf dem Streaming-Endpoint
  `/api/v1/base/generate-with-prompt/stream` — `RestBackend.generate_chunk`
  wechselt transparent dorthin, sobald für eine prompt-Stimme ein Seed
  aufgelöst ist (reduziert Timbre-/Prosodie-Drift derselben Clone-Stimme
  über viele Chunks). Gradio/Kokoro nehmen `seed` nur der Tupel-Form wegen
  entgegen und ignorieren ihn (siehe deren resolve_voice-Docstrings).
- Clone-Rollen ignorieren `style` komplett und reproduzieren nur die
  Prosodie ihrer einen Referenzaufnahme — okay für einen Narrator, klingt
  flach für Drama-Dialog; für `voices.*`-Rollen built-in Speaker
  bevorzugen.
- **NARRATOR ignoriert `style` IMMER, auch als Built-in-Speaker:**
  `build_drama_jobs()` in `podcast_maker.py` erzwingt `style=None` für
  `item.speaker == "NARRATOR"`, unabhängig von Skript-Style-Tags oder
  `role_cfg.default_style`. Grund: Style/Emotion-Instruct klingt auf der
  Erzähler-Rolle hörbar "off" — anders als bei Dialog-Rollen, wo Emotion
  den Zeilen Substanz gibt. Betrifft nur den drama-Modus (case-basierte
  Templates); der narration-Modus-Narrator (`NARRATOR_ROLE`-Sentinel,
  section_styles) ist davon unberührt. Gilt (Stand jetzt) nur für
  `GradioBackend` sauber — `RestBackend.generate_chunk` fällt bei
  `style=None` auf `self.default_style` zurück statt komplett stumm zu
  bleiben (kein Narrator-Sonderfall dort, bewusst nicht angefasst, siehe
  Memory `narrator-style-override`).
