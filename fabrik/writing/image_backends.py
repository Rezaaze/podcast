"""OpenAI-Bildgenerierung für Charakter-Porträts/Szenenbilder.

Stdlib-only (urllib statt requests) — character_prompts.py läuft ohne
.venv, wie generate_episode.py/create_series.py; ein requests-Import hier
würde das brechen (siehe CLAUDE.md: core/writing müssen ohne venv laufen).

Braucht OPENAI_API_KEY in der Umgebung. Kein Key gesetzt = wer diese
Funktionen aufruft, bekommt eine klare RuntimeError statt eines kryptischen
Verbindungsfehlers.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
import uuid

API_URL = "https://api.openai.com/v1/images/generations"
EDIT_API_URL = "https://api.openai.com/v1/images/edits"
DEFAULT_MODEL = "gpt-image-1-mini"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "medium"
TIMEOUT_SECONDS = 180


def api_key_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def generate_image(prompt: str, size: str = DEFAULT_SIZE, quality: str = DEFAULT_QUALITY,
                    model: str = DEFAULT_MODEL) -> bytes:
    """Erzeugt ein Bild über die OpenAI Images API, gibt die rohen PNG-Bytes
    zurück (gpt-image-1-Familie liefert immer b64_json, keine URL)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY nicht gesetzt — 'export OPENAI_API_KEY=sk-...' vor dem Aufruf."
        )

    payload = json.dumps({
        "model": model, "prompt": prompt, "size": size,
        "quality": quality, "n": 1,
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Images API Fehler {exc.code}: {detail[:300]}") from exc
    except OSError as exc:
        # Fängt auch TimeoutError beim Lesen der Antwort ab (Zeitüberschreitung
        # WÄHREND resp.read(), nicht beim Verbindungsaufbau) — urllib wirft das
        # als rohen TimeoutError, NICHT als urllib.error.URLError, obwohl beide
        # von OSError erben. Ein einzelnes except OSError deckt URLError,
        # TimeoutError und sonstige Socket-/SSL-Fehler ab, statt bei jeder
        # Netzwerk-Unterbrechung den ganzen Batch abstürzen zu lassen.
        raise RuntimeError(f"OpenAI Images API nicht erreichbar oder Zeitüberschreitung: {exc}") from exc

    b64 = data["data"][0]["b64_json"]
    return base64.b64decode(b64)


def save_image(prompt: str, out_path: str, size: str = DEFAULT_SIZE,
                quality: str = DEFAULT_QUALITY, model: str = DEFAULT_MODEL) -> None:
    png_bytes = generate_image(prompt, size=size, quality=quality, model=model)
    with open(out_path, "wb") as f:
        f.write(png_bytes)


def _build_multipart(fields: dict, file_field: str, filename: str,
                      file_bytes: bytes, file_content_type: str) -> tuple[bytes, str]:
    """Baut einen multipart/form-data-Body von Hand (kein 'requests' erlaubt,
    urllib kann das nicht selbst) — gebraucht für /v1/images/edits, das ein
    Bild-Upload statt reinem JSON-Body erwartet."""
    boundary = f"----podcastfabrik{uuid.uuid4().hex}"
    lines = []
    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        lines.append(f"{value}\r\n".encode())
    lines.append(f"--{boundary}\r\n".encode())
    lines.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode())
    lines.append(f"Content-Type: {file_content_type}\r\n\r\n".encode())
    lines.append(file_bytes)
    lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode())
    return b"".join(lines), f"multipart/form-data; boundary={boundary}"


def edit_image(reference_png: bytes, prompt: str, size: str = DEFAULT_SIZE,
                quality: str = DEFAULT_QUALITY, model: str = DEFAULT_MODEL) -> bytes:
    """Verändert ein vorhandenes Bild über die OpenAI Images-Edit-API, statt
    es aus reinem Text neu zu erzeugen. Anders als generate_image() bekommt
    das Modell hier die tatsächlichen Pixel des Referenzbilds als Kontext —
    das hält Gesicht/Frisur/Kleidung über mehrere Bilder einer Figur hinweg
    deutlich konsistenter als eine komplett unabhängige Neugenerierung aus
    identischem Beschreibungstext (character_prompts.py nutzt das für die
    Emotions-Varianten: Neutral-Porträt zuerst per generate_image(), dann
    jede Emotion als edit_image() auf dieses Neutral-Bild)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY nicht gesetzt — 'export OPENAI_API_KEY=sk-...' vor dem Aufruf."
        )

    fields = {"model": model, "prompt": prompt, "size": size, "quality": quality, "n": "1"}
    body, content_type = _build_multipart(fields, "image", "reference.png", reference_png, "image/png")
    req = urllib.request.Request(
        EDIT_API_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Images-Edit API Fehler {exc.code}: {detail[:300]}") from exc
    except OSError as exc:
        # Siehe Kommentar in generate_image() — deckt auch TimeoutError beim
        # Lesen der (bei Edits oft größeren) Antwort ab.
        raise RuntimeError(f"OpenAI Images-Edit API nicht erreichbar oder Zeitüberschreitung: {exc}") from exc

    b64 = data["data"][0]["b64_json"]
    return base64.b64decode(b64)
