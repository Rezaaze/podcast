"""ElevenLabs-Sound-Generierung für Ambience-Loops und One-Shot-SFX.

Stdlib-only (urllib statt requests) — läuft wie image_backends.py ohne
.venv, im selben No-venv-Pfad wie generate_episode.py/create_series.py.

Braucht ELEVENLABS_API_KEY in der Umgebung. Kein Key gesetzt = wer diese
Funktionen aufruft, bekommt eine klare RuntimeError statt eines kryptischen
Verbindungsfehlers.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API_URL = "https://api.elevenlabs.io/v1/sound-generation"
TIMEOUT_SECONDS = 120


def api_key_available() -> bool:
    return bool(os.environ.get("ELEVENLABS_API_KEY"))


def generate_sound_effect(text: str, duration_seconds: float | None = None) -> bytes:
    """Erzeugt einen Sound-Effekt über die ElevenLabs Sound-Generation-API,
    gibt die rohen MP3-Bytes zurück (anders als OpenAI Images liefert diese
    API die Audio-Bytes direkt im Response-Body, kein JSON+b64)."""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY nicht gesetzt — 'export ELEVENLABS_API_KEY=...' vor dem Aufruf."
        )

    body = {"text": text}
    if duration_seconds is not None:
        body["duration_seconds"] = duration_seconds
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=payload, method="POST",
        headers={"xi-api-key": api_key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ElevenLabs Sound-Generation-API Fehler {exc.code}: {detail[:300]}") from exc
    except OSError as exc:
        # Fängt auch TimeoutError beim Lesen der Antwort ab (Zeitüberschreitung
        # WÄHREND resp.read(), nicht beim Verbindungsaufbau) — siehe identischer
        # Kommentar in image_backends.py::generate_image.
        raise RuntimeError(f"ElevenLabs API nicht erreichbar oder Zeitüberschreitung: {exc}") from exc


def save_sound_effect(text: str, out_path: str, duration_seconds: float | None = None) -> None:
    audio_bytes = generate_sound_effect(text, duration_seconds=duration_seconds)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
