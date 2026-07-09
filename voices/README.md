# Referenzaufnahme für Voice Clone (Windows/NVIDIA-Backend)

Der `gradio`-Backend (siehe `tts_backends.py`, `GradioBackend`) klont die Stimme
"MyVoice" nicht aus einem gespeicherten Server-Prompt (wie die Mac/MLX-Version),
sondern direkt aus einer Referenz-Audiodatei, die bei jedem API-Aufruf mitgeschickt
wird.

## Was hierher muss

1. Eine kurze, saubere Aufnahme der Stimme (WAV oder MP3, ~10–30 Sekunden,
   möglichst wenig Hintergrundrauschen) — z. B. `myvoice_ref.wav`.
2. Das exakte Transkript dieser Aufnahme als Text.

## Wo eintragen

In `episodes.json` unter `audio`:

```json
"ref_audio": "voices/myvoice_ref.wav",
"ref_text": "Das exakte Transkript der Referenzaufnahme..."
```

`ref_audio` ist relativ zum Projekt-Root (`Podcast-Fabrik/`).

## Woher bekomme ich die Aufnahme?

Diese Datei liegt ursprünglich nur auf dem Mac im Speicher des
Qwen3-TTS-MLX-Servers (als "gespeicherter Prompt" registriert) — nicht in diesem
Repo. Am einfachsten: die Original-Referenzaufnahme, mit der "MyVoice" damals in
der Mac-WebUI angelegt wurde, erneut heraussuchen und hier ablegen. Falls die
nicht mehr auffindbar ist, reicht auch eine neue kurze Aufnahme derselben Stimme.
