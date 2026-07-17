"""ElevenLabs-Sound-Generierung für Ambience-Loops und One-Shot-SFX.

Stdlib-only (urllib statt requests) — läuft wie image_backends.py ohne
.venv, im selben No-venv-Pfad wie generate_episode.py/create_series.py.
Die Lautheits-Normalisierung (siehe _normalize_loudness) nutzt trotzdem
KEINE zusätzliche Python-Paket-Abhängigkeit: sie schiebt die Bytes per
Subprocess durch das ffmpeg-Binary (ohnehin Systemvoraussetzung des
gesamten Projekts, unabhängig vom .venv) statt pydub/pyloudnorm zu
importieren.

Braucht ELEVENLABS_API_KEY in der Umgebung. Kein Key gesetzt = wer diese
Funktionen aufruft, bekommt eine klare RuntimeError statt eines kryptischen
Verbindungsfehlers.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

API_URL = "https://api.elevenlabs.io/v1/sound-generation"
TIMEOUT_SECONDS = 120

# ElevenLabs' Sound-Generation-API liefert stark inkonsistente Roh-
# Lautstärke je nach Prompt (in Produktion gemessen: -68.8 dB bis -29.6 dB
# mittlere Lautstärke zwischen verschiedenen Ambience-Loops derselben
# Serie) — ohne Normalisierung verschluckt Lolfis fester Mix-Faktor
# (LOCATION_AMBIENCE_VOLUME) die leisen Dateien komplett, während die
# lauten hörbar durchkommen. -23 LUFS (EBU R128) ist ein neutraler,
# branchenüblicher Zielwert für ein "rohes" Quell-Asset, das später noch
# gemischt/attenuiert wird — TP -1.5 verhindert Clipping nach dem MP3-
# Reencode, LRA 11 ist der loudnorm-Standardwert.
LOUDNORM_TARGET_LUFS = -23.0
LOUDNORM_TRUE_PEAK_DB = -1.5
LOUDNORM_LRA = 11.0
FFMPEG_TIMEOUT_SECONDS = 60

# ElevenLabs' Sound-Generation-API validiert hart auf maximal so viele
# Zeichen (HTTP 400 "text_too_long" sonst) — betrifft sowohl Ambience-Loop-
# Prompts (location_ambience.py) als auch One-Shot-SFX-Palette-Prompts
# (sfx_assets.py), beide gehen über generate_sound_effect(). EINE Quelle
# hier statt je einer eigenen Kappungs-Funktion pro Skript, nachdem genau
# diese Duplikation dazu geführt hat, dass der Fix zuerst nur in
# location_ambience.py landete und sfx_assets.py denselben Fehlschlag
# weiterhin riskierte.
MAX_PROMPT_CHARS = 450

# ElevenLabs' Sound-Generation-API lehnt duration_seconds < 0.5 hart ab (400
# "invalid_generation_settings"). fabrik/cli/sfx_plan.py's eigener
# MIN_ASSET_SECONDS lag bis 16.07.2026 bei 0.2 (der Planungs-Prompt empfahl
# sogar aktiv 0.2-0.4s für kurze Kontaktgeräusche wie einen Stiftklick) — ein
# in Produktion beobachteter Fehlschlag ("mouse_click" mit 0.4s/0.3s geplant).
# Sicherheitsnetz nach demselben Muster wie MAX_PROMPT_CHARS oben: EIN
# gemeinsamer Clamp hier (beide Aufrufer, ambience UND one-shots, laufen über
# generate_sound_effect()) statt sich auf einen korrekt kalibrierten Planer
# zu verlassen — ein bereits geschriebener Plan mit zu kurzen Werten (wie die
# beiden oben genannten Serien) funktioniert damit auch ohne Neu-Planung.
MIN_DURATION_SECONDS = 0.5


def fit_prompt(description: str, suffix: str = "", max_chars: int = MAX_PROMPT_CHARS) -> str:
    """Kappt description wortweise, falls description(+suffix) MAX_PROMPT_CHARS
    reißen würde. Ein optionales suffix (z.B. location_ambience.py's
    LOOP_SUFFIX, die Anti-Metronom/Anti-Einzelereignis-Regel für Loops)
    bleibt dabei IMMER vollständig erhalten — nur der beschreibende Teil
    davor wird bei Bedarf gekürzt."""
    tail = f", {suffix}" if suffix else ""
    budget = max_chars - len(tail)
    if len(description) > budget:
        description = description[:budget].rsplit(" ", 1)[0].rstrip(" ,;.")
    return f"{description}{tail}"


def _normalize_loudness(audio_bytes: bytes) -> bytes:
    """Normalisiert generierte Sound-Bytes auf LOUDNORM_TARGET_LUFS via
    ffmpeg (Subprocess, kein Python-Audio-Paket nötig). Bei jedem Fehler
    (ffmpeg fehlt, Timeout, kaputtes Audio) wird still auf die
    unnormalisierten Original-Bytes zurückgefallen — eine fehlgeschlagene
    Normalisierung darf nie die ganze Sound-Generierung zum Absturz
    bringen, ein leiser/lauter Ausreißer ist besser als gar kein Sound."""
    if shutil.which("ffmpeg") is None:
        print("  WARNUNG: ffmpeg nicht gefunden — Lautheits-Normalisierung übersprungen "
              "(Datei bleibt in ElevenLabs' Roh-Lautstärke).")
        return audio_bytes
    with tempfile.TemporaryDirectory() as tmp_dir:
        in_path = os.path.join(tmp_dir, "in.mp3")
        out_path = os.path.join(tmp_dir, "out.mp3")
        with open(in_path, "wb") as f:
            f.write(audio_bytes)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", in_path, "-af",
                 f"loudnorm=I={LOUDNORM_TARGET_LUFS}:TP={LOUDNORM_TRUE_PEAK_DB}:LRA={LOUDNORM_LRA}",
                 out_path],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS,
            )
            with open(out_path, "rb") as f:
                normalized = f.read()
            if not normalized:
                raise RuntimeError("ffmpeg lieferte eine leere Ausgabedatei.")
            return normalized
        except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
            print(f"  WARNUNG: Lautheits-Normalisierung fehlgeschlagen ({exc}) — "
                  f"Datei bleibt in ElevenLabs' Roh-Lautstärke.")
            return audio_bytes


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

    # Sicherheitsnetz: Aufrufer SOLLTEN fit_prompt() schon vorher anwenden
    # (die kennen den zu schützenden Suffix, hier ist er nicht bekannt) —
    # aber ein vergessener Aufruf soll nie einen harten API-Fehlschlag
    # produzieren, wenn eine blinde Kappung das genauso zuverlässig vermeidet.
    # Wirkt NACH jeder Hash-Berechnung beim Aufrufer (sfx_library.py hasht
    # die ungekürzte description) — kappt nur, was tatsächlich an
    # ElevenLabs geht, der Dateinamen-Vertrag bleibt unangetastet.
    if len(text) > MAX_PROMPT_CHARS:
        print(f"  WARNUNG: Prompt ist {len(text)} Zeichen (Limit {MAX_PROMPT_CHARS}) — "
              f"wortweise gekappt, bevor er an ElevenLabs geht.")
        text = fit_prompt(text)

    if duration_seconds is not None and duration_seconds < MIN_DURATION_SECONDS:
        print(f"  WARNUNG: geplante Dauer {duration_seconds}s liegt unter dem API-Minimum "
              f"({MIN_DURATION_SECONDS}s) — auf {MIN_DURATION_SECONDS}s angehoben.")
        duration_seconds = MIN_DURATION_SECONDS

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


def save_sound_effect(text: str, out_path: str, duration_seconds: float | None = None,
                      post_process=None) -> None:
    """post_process: optionales bytes->bytes, läuft NACH der Lautheits-
    Normalisierung (z.B. location_ambience.py's Loop-Nahtlos-Behandlung —
    nur für Loops relevant, deshalb hier als Hook statt fest verdrahtet)."""
    audio_bytes = generate_sound_effect(text, duration_seconds=duration_seconds)
    audio_bytes = _normalize_loudness(audio_bytes)
    if post_process is not None:
        audio_bytes = post_process(audio_bytes)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
