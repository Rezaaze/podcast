"""TTS-Backends für podcast_maker.py/batch.py.

Zwei Implementierungen hinter einem gemeinsamen Interface
(check_api, resolve_voice, generate_chunk):

- RestBackend: Qwen3-TTS-MLX-WebUI-Enhanced (Mac, Apple Silicon), spricht das
  eigene /api/v1/... REST-API dieser Pinokio-App an.
- GradioBackend: SUP3RMASS1VE/Qwen3-TTS (Windows/NVIDIA, CUDA/PyTorch), reine
  Gradio-App ohne eigenes REST-API — Ansteuerung über gradio_client gegen die
  Voice-Clone-Funktion (generate_voice_clone). Erwartet eine Referenz-Audiodatei
  + deren Transkript (episodes.json: audio.ref_audio / audio.ref_text).

  Der api_name "/generate_voice_clone" ergibt sich aus Gradios Standard-Namens-
  vergabe (Funktionsname des click-Handlers, kein expliziter api_name im
  Quelltext der App). Beim ersten echten Lauf gegen eine laufende Instanz lohnt
  sich ein Abgleich per `gradio_client.Client(url).view_api()`, falls sich die
  App-Version ändert.
"""

import base64
import io

import requests
from pydub import AudioSegment


def build_backend(audio_config):
    kind = audio_config.get("backend", "rest")
    if kind == "gradio":
        return GradioBackend(audio_config)
    return RestBackend(audio_config)


class RestBackend:
    """Qwen3-TTS-MLX-WebUI-Enhanced REST-API (Mac)."""

    def __init__(self, audio_config, connect_timeout=10, read_timeout=90):
        self.base_url = audio_config.get("api_url", "http://127.0.0.1:42003").rstrip("/")
        self.default_style = audio_config.get(
            "default_style", "Read like an audiobook narrator, calm, steady, and engaging"
        )
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def check_api(self):
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=self.connect_timeout)
            return resp.status_code < 500
        except Exception:
            return False

    def resolve_voice(self, voice_name):
        """Löst den Stimmennamen auf: zuerst geklonte Stimmen (Prompts), dann
        Built-in-Speaker. Rückgabe: ("prompt", prompt_id), ("speaker", name)
        oder (None, verfügbare_stimmen)."""
        available = []
        try:
            resp = requests.get(f"{self.base_url}/api/v1/base/prompts", timeout=self.connect_timeout)
            if resp.ok:
                for p in resp.json().get("prompts", []):
                    if p.get("name") == voice_name:
                        return "prompt", p["prompt_id"]
                    available.append(f"{p.get('name')} (geklont)")
        except Exception:
            pass
        try:
            resp = requests.get(f"{self.base_url}/api/v1/custom-voice/speakers", timeout=self.connect_timeout)
            if resp.ok:
                for s in resp.json().get("speakers", []):
                    if s.get("name") == voice_name:
                        return "speaker", voice_name
                    available.append(f"{s.get('name')} (built-in)")
        except Exception:
            pass
        return None, available

    def generate_chunk(self, voice, text, style=None):
        """Ein einzelner Generierungsversuch (kein Retry — das übernimmt der
        Aufrufer zusammen mit der Plausibilitätsprüfung). Gibt bei Fehlern
        (None, fehlermeldung) zurück, sonst (AudioSegment, None).

        voice: Tupel aus resolve_voice(). Geklonte Stimmen (prompt)
        unterstützen in dieser API-Version keine Style-Anweisungen; nur
        Built-in-Speaker bekommen den Style als 'instruct' mit."""
        kind, voice_id = voice
        if kind == "prompt":
            url = f"{self.base_url}/api/v1/base/generate-with-prompt"
            payload = {"prompt_id": voice_id, "text": text, "language": "Auto", "speed": 1.0}
        else:
            url = f"{self.base_url}/api/v1/custom-voice/generate"
            payload = {
                "text": text,
                "speaker": voice_id,
                "instruct": style if style else self.default_style,
                "language": "Auto",
                "speed": 1.0,
            }

        try:
            response = requests.post(url, json=payload, timeout=(self.connect_timeout, self.read_timeout))
            if response.status_code == 200:
                audio_b64 = response.json().get("audio", "")
                audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""
                if audio_bytes:
                    return AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav"), None
                return None, "Leere Antwort von API."
            return None, f"Fehler {response.status_code} – {response.text[:100]}"
        except requests.exceptions.ConnectTimeout:
            return None, f"API nicht erreichbar (Timeout nach {self.connect_timeout}s)"
        except requests.exceptions.ReadTimeout:
            return None, f"API hängt – keine Antwort nach {self.read_timeout}s"
        except Exception as e:
            return None, str(e)


class GradioBackend:
    """SUP3RMASS1VE/Qwen3-TTS (Windows/NVIDIA, CUDA) über gradio_client.

    Unterstützt aktuell nur Voice Clone (episodes.json: audio.ref_audio,
    audio.ref_text) — kein Built-in-Speaker/Style-Modus, da die aktuelle
    Stimme des Projekts eine geklonte Stimme ist.
    """

    def __init__(self, audio_config):
        self.base_url = audio_config.get("api_url", "http://127.0.0.1:7860").rstrip("/")
        self.ref_audio = audio_config.get("ref_audio")
        self.ref_text = audio_config.get("ref_text")
        self.model_size = audio_config.get("model_size", "1.7B")
        self.language = audio_config.get("language", "Auto")
        self.chunk_gap = audio_config.get("chunk_gap", 0.0)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from gradio_client import Client
            self._client = Client(self.base_url)
        return self._client

    def check_api(self):
        try:
            self._get_client()
            return True
        except Exception:
            return False

    def resolve_voice(self, voice_name):
        """Bei GradioBackend/Voice-Clone gibt es keine serverseitige
        Stimmenliste — die Referenzaufnahme kommt aus episodes.json."""
        if not self.ref_audio:
            return None, ["audio.ref_audio fehlt in episodes.json"]
        if not self.ref_text:
            return None, ["audio.ref_text fehlt in episodes.json"]
        return "clone", voice_name

    def generate_chunk(self, voice, text, style=None):
        """Ein einzelner Generierungsversuch. style wird ignoriert (Voice
        Clone unterstützt kein 'instruct'). Gibt (AudioSegment, None) oder
        (None, fehlermeldung) zurück."""
        from gradio_client import handle_file

        try:
            client = self._get_client()
            audio_path, status = client.predict(
                ref_audio=handle_file(self.ref_audio),
                ref_text=self.ref_text,
                target_text=text,
                language=self.language,
                use_xvector_only=False,
                model_size=self.model_size,
                max_chunk_chars=1000,  # Chunking übernimmt bereits podcast_maker.py
                chunk_gap=self.chunk_gap,
                seed=-1,
                api_name="/generate_voice_clone",
            )
            if audio_path:
                return AudioSegment.from_file(audio_path), None
            return None, status
        except Exception as e:
            return None, str(e)
