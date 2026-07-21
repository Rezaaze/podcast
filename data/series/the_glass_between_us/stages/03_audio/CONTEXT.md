# Stage 03 — Audio

## Inputs
- Layer 4: `../02_scripts/output/ep<N>.txt` (+ `_META.txt` für ID3)
- Layer 4: `../01_concept/output/episodes.json` (Stimmen, Backend, Seeds,
  merge_anthology)
- Layer 3 (Serie): `../../assets/intro.mp3|outro.mp3|transition.mp3`
  (optional)
- Layer 3 (global): `data/voices/*.wav` (Clone-Referenzen)
- Extern: laufender TTS-Server laut `audio.api_url`

## Process
Chunken → TTS pro Chunk (Checkpoint-WAVs, resumierbar) → LUFS-Mastering →
Part-Merge zu MP3 → Postprocessing (SFX-Cues, Speaker-/Location-Timelines,
Untertitel). Voice-Manifest-Guard verhindert stille Stimmwechsel
mitten in der Serie. Details: `fabrik/audio/CLAUDE.md`.
Ausgeführt von: `.venv/bin/python -m fabrik.cli.batch` (alle) bzw.
`podcast_maker ep<N>.txt` (eine)

## Outputs
- `output/<Ep>_FULL_EPISODE.mp3` + `.srt`
- `output/<Ep>_SPEAKERS.json|.txt`, `<Ep>_LOCATIONS.json`,
  `<Ep>_SUBS.json`, `<Ep>_SFX_CUES.txt`, `<Ep>_..._PART_OFFSETS.json`
- `output/UPLOAD_INDEX.md`; bei merge_anthology zusätzlich
  `ANTHOLOGY_COMPLETE.*`
- Intern: `output/.checkpoints/`, `output/.cues/`, `output/.voices_manifest.json`

## Review-Gate danach
MP3s probehören; SFX-Cue-Sheet für manuelles DAW-Mixing nutzen. Eine
Episode neu vertonen = ihre MP3 + Checkpoints löschen und Stage erneut
laufen lassen. Stimmen ändern erst nach Löschen des Voice-Manifests
(bewusste Entscheidung, siehe Guard).
