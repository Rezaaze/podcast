# Podcast-Fabrik

Automatisierte Pipeline für Anthologie-Podcasts: Claude schreibt die Skripte,
eine lokale Qwen3-TTS-API vertont sie, am Ende steht eine gemasterte MP3 pro
Episode plus eine Gesamt-Anthologie.

## Workflow

```
EPISODES_CREATOR_PROMPT.md ──(Claude)──▶ episodes.json
episodes.json + PROMPT_TEMPLATE.md ──(generate_episode.py)──▶ figur1.txt, figur2.txt, ...
figurN.txt ──(podcast_maker.py)──▶ FigurN_FULL_EPISODE.mp3
alle Episoden ──(batch.py)──▶ ANTHOLOGY_COMPLETE.mp3
```

1. **Serie definieren:** `EPISODES_CREATOR_PROMPT.md` zusammen mit deiner
   Themenidee an Claude geben, die JSON-Antwort als `episodes.json` speichern.
   `episodes.json` ist die Single Source of Truth für alles — Serie, Figuren,
   Sprache, Stil, Wortbudget, Stimme, Pausen, Mastering.

2. **Skripte generieren** (nutzt die Claude CLI, kein venv nötig):

   ```bash
   python3 generate_episode.py check    # nur episodes.json validieren
   python3 generate_episode.py 1        # Episode 1 → figur1.txt
   python3 generate_episode.py all      # alle Episoden (parallel, --jobs N),
                                        # startet danach automatisch batch.py
   ```

   Jede Section wird einzeln generiert, validiert (Wortzahl, Part-Marker) und
   sofort in die Datei geschrieben — ein abgebrochener Lauf setzt beim
   Neustart bei der ersten fehlenden Section fort. `--force` generiert neu.

3. **Vertonen** (braucht das venv wegen pydub/numpy/pyloudnorm, und einen
   laufenden Qwen3-TTS-MLX-Server unter `audio.api_url`):

   ```bash
   .venv/bin/python podcast_maker.py figur1.txt   # eine Episode
   .venv/bin/python batch.py                      # alle + Anthologie-Merge
   ```

   Jeder Text-Chunk wird als Checkpoint-WAV gesichert
   (`podcast_output/.checkpoints/`) — auch hier kann jederzeit abgebrochen
   und fortgesetzt werden. Fertige Parts/Episoden werden übersprungen.

## Dateien

| Datei | Zweck |
|---|---|
| `episodes.json` | Komplette Podcast-Definition (Inhalt + Audio-Config) |
| `PROMPT_TEMPLATE.md` | Neutrales Prompt-Gerüst, Platzhalter aus episodes.json |
| `EPISODES_CREATOR_PROMPT.md` | Prompt, um eine neue episodes.json zu entwerfen |
| `generate_episode.py` | Skript-Generierung via Claude CLI (Section für Section) |
| `podcast_maker.py` | TTS, Chunk-Checkpoints, LUFS-Mastering, Episoden-MP3 |
| `batch.py` | Vertont alle Skripte und merged die Anthologie |
| `figurN.txt` | Generierte Episoden-Skripte (Präfix = `output_prefix`) |
| `podcast_output/` | MP3s und Checkpoints |

## Hinweise

- Der Episodenname wird aus dem Dateinamen abgeleitet (`figur1.txt` →
  `Figur1_FULL_EPISODE.mp3`) — `podcast_maker.py` und `batch.py` müssen sich
  darin einig sein, sonst wird doppelt vertont. `--name` überschreibt das.
- `section_styles` wirken nur bei Built-in-Speakern; geklonte Stimmen
  (Voice-Prompts) unterstützen in der aktuellen API-Version kein `instruct`.
- Parts werden verlustfrei als WAV zwischengespeichert; MP3-kodiert wird nur
  die fertige Episode. Die Anthologie entsteht per ffmpeg-Stream-Copy — ohne
  Re-Encode und ohne die Episoden in den RAM zu laden.
- Das venv ist Python 3.9 — `generate_episode.py` läuft mit jedem
  Python ≥ 3.9, `podcast_maker.py`/`batch.py` brauchen die venv-Pakete
  (pydub, numpy, pyloudnorm, requests, ffmpeg im PATH).

## Windows/NVIDIA-Setup

Auf dem Mac läuft die Vertonung gegen **Qwen3-TTS-MLX** (Apple-Silicon-only).
Auf Windows/NVIDIA gibt es dafür kein MLX — stattdessen läuft dasselbe
Qwen3-TTS-Modell über PyTorch/CUDA via
[SUP3RMASS1VE/Qwen3-TTS](https://github.com/SUP3RMASS1VE/Qwen3-TTS) (bzw. den
Pinokio-Wrapper `Qwen3-TTS-Pinokio`). Anders als die Mac-Version ist das eine
reine Gradio-App ohne eigenes REST-API — `podcast_maker.py` spricht sie über
`gradio_client` an (`tts_backends.py`, `GradioBackend`).

### 1. Qwen3-TTS installieren

Voraussetzungen: Python 3.10+, NVIDIA-GPU mit CUDA 12.8 (~8 GB VRAM für die
0.6B-Modelle, ~16 GB für 1.7B). Entweder per Pinokio (`Qwen3-TTS-Pinokio`
App installieren) oder manuell nach der Anleitung in
[SUP3RMASS1VE/Qwen3-TTS](https://github.com/SUP3RMASS1VE/Qwen3-TTS). Start
über `python app.py` — die Gradio-UI läuft dann auf `http://localhost:7860`.

### 2. Referenzaufnahme für die geklonte Stimme

Siehe [`voices/README.md`](voices/README.md) — Referenz-Audio + Transkript
für "MyVoice" müssen unter `voices/` abgelegt werden.

### 3. episodes.json umstellen

```json
"audio": {
  "backend": "gradio",
  "api_url": "http://127.0.0.1:7860",
  "ref_audio": "voices/myvoice_ref.wav",
  "ref_text": "Das exakte Transkript der Referenzaufnahme..."
}
```

`backend: "rest"` (Default) bleibt für die Mac/MLX-Version bestehen.

### 4. Vertonen

```
.venv\Scripts\python podcast_maker.py figur1.txt
.venv\Scripts\python batch.py
```

`gradio_client` ist bereits Teil des Projekts (in `.venv` installiert).
Voice-Clone unterstützt kein `instruct`/Style — `section_styles` aus
`episodes.json` werden mit diesem Backend ignoriert (identisches Verhalten
zur geklonten Stimme auf der Mac-Version).
