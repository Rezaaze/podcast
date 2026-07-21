"""TTS-Backends für die Vertonung.

Drei Implementierungen hinter einem gemeinsamen Interface
(check_api, resolve_voice, generate_chunk):

- RestBackend: Qwen3-TTS-MLX-WebUI-Enhanced (Mac, Apple Silicon), spricht das
  eigene /api/v1/... REST-API dieser Pinokio-App an.
- GradioBackend: SUP3RMASS1VE/Qwen3-TTS (Windows/NVIDIA, CUDA/PyTorch), reine
  Gradio-App ohne eigenes REST-API — Ansteuerung über gradio_client gegen zwei
  Funktionen der App: generate_voice_clone (EINE geklonte Stimme, episodes.json:
  audio.ref_audio/audio.ref_text) und generate_custom_voice (mehrere Built-in-
  Speaker, siehe GradioBackend.SPEAKERS) — Drama-Modus ist damit über diese
  App möglich, genau wie bei RestBackend.

  Die api_names "/generate_voice_clone"/"/generate_custom_voice" ergeben sich
  aus Gradios Standard-Namensvergabe (Funktionsname des click-Handlers, kein
  expliziter api_name im Quelltext der App). Beim ersten echten Lauf gegen eine
  laufende Instanz lohnt sich ein Abgleich per
  `gradio_client.Client(url).view_api()`, falls sich die App-Version ändert.
- KokoroBackend: Kokoro-MLX (Mac, Apple Silicon) über das `mlx-audio`-Paket
  (https://github.com/Blaizzy/mlx-audio). Läuft komplett lokal in-process,
  kein Server nötig — dafür lädt jeder podcast_maker.py-Lauf das Modell
  einmal selbst. Siehe KokoroBackend-Docstring für Einschränkungen.
"""

import base64
import io

import requests
from pydub import AudioSegment


def build_backend(audio_config):
    kind = audio_config.get("backend", "rest")
    if kind == "gradio":
        return GradioBackend(audio_config)
    if kind == "kokoro":
        return KokoroBackend(audio_config)
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

    def resolve_voice(self, voice_name, seed=None):
        """Löst den Stimmennamen auf: zuerst geklonte Stimmen (Prompts), dann
        Built-in-Speaker. Rückgabe: ("prompt", prompt_id, seed), ("speaker", name, seed)
        oder (None, verfügbare_stimmen, None).

        seed wird nur durchgereicht, nicht hier geprüft — generate_chunk()
        nutzt ihn ausschließlich für kind == "prompt" (siehe dort: der Server
        bietet einen 'seed'-Parameter nur auf dem Streaming-Endpunkt
        /api/v1/base/generate-with-prompt/stream an, für Built-in-Speaker
        (/api/v1/custom-voice/generate) existiert in dieser API-Version gar
        kein seed-Feld — dort wird er also stillschweigend ignoriert)."""
        available = []
        try:
            resp = requests.get(f"{self.base_url}/api/v1/base/prompts", timeout=self.connect_timeout)
            if resp.ok:
                for p in resp.json().get("prompts", []):
                    if p.get("name") == voice_name:
                        return "prompt", p["prompt_id"], seed
                    available.append(f"{p.get('name')} (geklont)")
        except requests.RequestException as exc:
            # Unterschied zu "Stimme nicht in der Liste" bewusst sichtbar machen —
            # sonst sieht ein Verbindungsfehler hier identisch aus wie eine
            # tatsächlich leere/nicht vorhandene Stimme (available bleibt []).
            print(f"  WARNUNG: {self.base_url}/api/v1/base/prompts nicht erreichbar ({exc}) "
                  f"— geklonte Stimmen werden bei der Auflösung übersprungen.")
        try:
            resp = requests.get(f"{self.base_url}/api/v1/custom-voice/speakers", timeout=self.connect_timeout)
            if resp.ok:
                for s in resp.json().get("speakers", []):
                    if s.get("name") == voice_name:
                        return "speaker", voice_name, seed
                    available.append(f"{s.get('name')} (built-in)")
        except requests.RequestException as exc:
            print(f"  WARNUNG: {self.base_url}/api/v1/custom-voice/speakers nicht erreichbar ({exc}) "
                  f"— Built-in-Speaker werden bei der Auflösung übersprungen.")
        return None, available, None

    def generate_chunk(self, voice, text, style=None, speed=None):
        """Ein einzelner Generierungsversuch (kein Retry — das übernimmt der
        Aufrufer zusammen mit der Plausibilitätsprüfung). Gibt bei Fehlern
        (None, fehlermeldung) zurück, sonst (AudioSegment, None).

        voice: Tupel aus resolve_voice() (kind, voice_id, seed). Geklonte
        Stimmen (prompt) unterstützen in dieser API-Version keine
        Style-Anweisungen; nur Built-in-Speaker bekommen den Style als
        'instruct' mit. speed funktioniert für beide.

        seed (nur bei kind == "prompt" wirksam): setzt vor jedem Chunk denselben
        MLX-Zufallszustand zurück (Server: mx.random.seed(seed)) — reduziert
        Timbre-/Prosodie-Drift derselben geklonten Stimme über viele Chunks
        hinweg. Dafür wird statt des einfachen /generate-with-prompt-Aufrufs
        die Streaming-Variante /generate-with-prompt/stream angesprochen, die
        als einzige dieser API einen seed-Parameter kennt; die Chunks werden
        hier zu einem einzigen AudioSegment zusammengefügt. Für Built-in-
        Speaker (kind == "speaker") gibt es in dieser API-Version keinen
        seed-Parameter überhaupt — hier wird seed ignoriert."""
        kind, voice_id, seed = voice
        speed = speed if speed else 1.0
        if kind == "prompt":
            if seed is not None:
                return self._generate_with_prompt_streamed(voice_id, text, speed, seed)
            url = f"{self.base_url}/api/v1/base/generate-with-prompt"
            payload = {"prompt_id": voice_id, "text": text, "language": "Auto", "speed": speed}
        else:
            url = f"{self.base_url}/api/v1/custom-voice/generate"
            payload = {
                "text": text,
                "speaker": voice_id,
                "instruct": style if style else self.default_style,
                "language": "Auto",
                "speed": speed,
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

    def _generate_with_prompt_streamed(self, prompt_id, text, speed, seed):
        """Ruft /api/v1/base/generate-with-prompt/stream auf (SSE) — der
        einzige Endpunkt dieser API, der einen 'seed' entgegennimmt. chunk_size
        wird bewusst größer als der Text gewählt, damit der Server den Text
        NICHT nochmal intern zerlegt (das Chunking auf Satzebene übernimmt
        bereits podcast_maker.py/textproc.py) — ein Chunk hier soll genau
        einem generate_chunk()-Aufruf entsprechen. Fügt trotzdem robust
        mehrere 'chunk'-Events zu einem AudioSegment zusammen, falls der
        Server doch mehr als einen sendet."""
        import json as json_module

        url = f"{self.base_url}/api/v1/base/generate-with-prompt/stream"
        payload = {
            "prompt_id": prompt_id,
            "text": text,
            "language": "Auto",
            "speed": speed,
            "chunk_size": max(500, len(text) + 10),
            "seed": seed,
        }
        try:
            response = requests.post(
                url, json=payload, stream=True,
                timeout=(self.connect_timeout, self.read_timeout),
            )
            if response.status_code != 200:
                return None, f"Fehler {response.status_code} – {response.text[:100]}"

            segment = AudioSegment.empty()
            got_audio = False
            error = None
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                event = json_module.loads(line[len("data: "):])
                etype = event.get("type")
                if etype == "chunk":
                    audio_bytes = base64.b64decode(event["audio"])
                    segment += AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
                    got_audio = True
                elif etype == "error":
                    error = event.get("error", "Unbekannter Stream-Fehler")
                elif etype == "done":
                    break
            if error:
                return None, error
            if not got_audio:
                return None, "Leere Streaming-Antwort von API."
            return segment, None
        except requests.exceptions.ConnectTimeout:
            return None, f"API nicht erreichbar (Timeout nach {self.connect_timeout}s)"
        except requests.exceptions.ReadTimeout:
            return None, f"API hängt – keine Antwort nach {self.read_timeout}s"
        except Exception as e:
            return None, str(e)


class GradioBackend:
    """SUP3RMASS1VE/Qwen3-TTS (Windows/NVIDIA, CUDA) über gradio_client.

    Unterstützt zwei Pfade der App, analog zu RestBackend:
    - Voice Clone (episodes.json: audio.ref_audio, audio.ref_text) — EINE
      geteilte geklonte Stimme für alle Rollen, die auf sie auflösen; kein
      Style/Instruct, kein Tempo (die App bietet dafür keine Parameter an).
    - Custom Voice / Built-in-Speaker (SPEAKERS unten) — mehrere Rollen mit
      unterschiedlichen Stimmen, Style/Instruct wird unterstützt (laut
      App-UI nur beim 1.7B-Modell), Tempo weiterhin NICHT.
    resolve_voice() entscheidet pro Rollenname, welcher Pfad greift — der
    Drama-Modus (mehrere Built-in-Stimmen) ist damit über dieses Backend
    möglich, eine geklonte Stimme bleibt weiterhin auf eine einzige
    Identität pro Serie begrenzt (ein gemeinsames ref_audio/ref_text).
    """

    # Speaker-Roster DIESER konkreten App (app.py::SPEAKERS auf GitHub) —
    # unabhängig vom Roster des lokalen Mac-Servers (config.py::
    # KNOWN_BUILTIN_SPEAKERS), da ein anderes Projekt mit anderem
    # Modell-Build läuft (z.B. "Ono_anna"/"Sohee" statt "Ethan"/"Chelsie").
    # Bei einer neuen App-Version per gradio_client.Client(url).view_api()
    # gegenprüfen.
    SPEAKERS = {"Aiden", "Dylan", "Eric", "Ono_anna", "Ryan", "Serena", "Sohee", "Uncle_fu", "Vivian"}

    def __init__(self, audio_config):
        self.base_url = audio_config.get("api_url", "http://127.0.0.1:7860").rstrip("/")
        self.ref_audio = audio_config.get("ref_audio")
        self.ref_text = audio_config.get("ref_text")
        self.model_size = audio_config.get("model_size", "1.7B")
        self.language = audio_config.get("language", "Auto")
        self.chunk_gap = audio_config.get("chunk_gap", 0.0)
        self._client = None
        self._speaker_lookup = {s.lower(): s for s in self.SPEAKERS}

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

    def resolve_voice(self, voice_name, seed=None):
        """Built-in-Speaker zuerst (Name aus SPEAKERS, case-insensitive
        gematcht), sonst Voice-Clone-Fallback (ref_audio/ref_text — EINE
        geteilte Identität für alle so aufgelösten Rollen).

        seed wird nur durchgereicht, damit das Tupel-Format zu den anderen
        Backends passt — generate_chunk() ignoriert ihn für BEIDE Pfade:
        weder generate_voice_clone noch generate_custom_voice dieser App
        nehmen einen seed-Parameter von außen entgegen."""
        canonical = self._speaker_lookup.get(voice_name.strip().lower())
        if canonical:
            return "speaker", canonical, seed
        if not self.ref_audio:
            return None, [f"audio.ref_audio fehlt in episodes.json (oder einen Built-in-Speaker "
                          f"aus {', '.join(sorted(self.SPEAKERS))} verwenden)"], None
        if not self.ref_text:
            return None, ["audio.ref_text fehlt in episodes.json"], None
        return "clone", voice_name, seed

    def generate_chunk(self, voice, text, style=None, speed=None):
        """Ein einzelner Generierungsversuch. speed wird für BEIDE Pfade
        ignoriert (weder Voice Clone noch Custom Voice dieser App bieten
        einen Tempo-Parameter an). style (instruct) wirkt nur bei
        kind == "speaker" — Voice Clone kennt kein instruct.
        Gibt (AudioSegment, None) oder (None, fehlermeldung) zurück.

        voice: Tupel (kind, voice_id, seed) aus resolve_voice() — seed wird
        hier NICHT verwendet (siehe resolve_voice-Docstring)."""
        kind, voice_id, _seed = voice
        if kind == "speaker":
            return self._generate_custom_voice(voice_id, text, style)

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
                max_chunk_chars=500,  # Chunking übernimmt bereits podcast_maker.py (App-Maximum: 500)
                chunk_gap=self.chunk_gap,
                seed=-1,
                api_name="/generate_voice_clone",
            )
            if audio_path:
                return AudioSegment.from_file(audio_path), None
            return None, status
        except Exception as e:
            return None, str(e)

    def _generate_custom_voice(self, speaker, text, style):
        """Ruft /generate_custom_voice auf (Built-in-Speaker-Pfad der App,
        app.py::generate_custom_voice) — api_name folgt Gradios Standard-
        Namensvergabe wie bei generate_voice_clone (siehe dortigen
        Docstring), bei einer neuen App-Version gegen view_api() prüfen."""
        try:
            client = self._get_client()
            audio_path, status = client.predict(
                text=text,
                language=self.language,
                speaker=speaker,
                instruct=style or "",
                model_size=self.model_size,
                seed=-1,
                api_name="/generate_custom_voice",
            )
            if audio_path:
                return AudioSegment.from_file(audio_path), None
            return None, status
        except Exception as e:
            return None, str(e)

    def supports_batch(self, jobs):
        """True nur wenn ALLE Jobs im Batch DIESELBE Art sind (nur 'speaker'
        oder nur 'clone') — beide haben einen gepatchten Batch-Endpoint
        (siehe cloud/onstart_qwen3_tts.sh::PODCAST_FABRIK_BATCH_PATCH bzw.
        PODCAST_FABRIK_CLONE_BATCH_PATCH), aber EIN Forward-Pass kann nicht
        beide Modelle (CustomVoice vs. Base) gleichzeitig bedienen — gemischte
        Batches (z.B. Built-in-Speaker-Rollen neben einer Voice-Clone-Rolle
        im selben Fenster) fallen auf einzelne generate_chunk()-Aufrufe
        zurück. Der Aufrufer (podcast_maker.py) bucketet deshalb VOR dem
        Windowing nach Art, nicht nur nach chunk_concurrency-Fenstergröße."""
        kinds = {voice[0] for voice, _text, _style, _speed in jobs}
        return kinds <= {"speaker", "clone"} and len(kinds) == 1

    def generate_chunk_batch(self, jobs):
        """EIN Forward-Pass für mehrere Chunks gleichzeitig, über die von
        cloud/onstart_qwen3_tts.sh in die App gepatchten Batch-Endpoints —
        echte GPU-Parallelität (self.model.generate() einmal für den ganzen
        Batch) statt N sequenzieller Calls, die serverseitig ohnehin
        denselben CUDA-Default-Stream teilen und sich damit gegenseitig
        blockieren (siehe cloud/README.md für die Messung: ~13x schneller
        bei Batch=17 gegenüber Einzel-Calls). Built-in-Speaker-Jobs gehen an
        /generate_custom_voice_batch, Voice-Clone-Jobs (EINE geteilte
        Identität für alle Chunks im Batch) an /generate_voice_clone_batch.

        jobs: Liste von (voice, text, style, speed) Tupeln, ALLE mit
        demselben voice[0] (Aufrufer garantiert das via supports_batch()).
        Gibt (Liste von AudioSegment|None in Job-Reihenfolge, Fehlermeldung
        oder None) zurück — bei komplettem Fehlschlag lauter None-Einträge,
        damit der Aufrufer pro Chunk denselben Fehlerpfad wie bei
        generate_chunk() nehmen kann."""
        kind = jobs[0][0][0]
        if kind == "clone":
            return self._generate_voice_clone_batch(jobs)
        return self._generate_custom_voice_batch(jobs)

    def _generate_custom_voice_batch(self, jobs):
        import json
        texts = [text for _voice, text, _style, _speed in jobs]
        speakers = [voice[1] for voice, _text, _style, _speed in jobs]
        instructs = [style or "" for _voice, _text, style, _speed in jobs]
        try:
            client = self._get_client()
            paths, status = client.predict(
                json.dumps(texts), self.language, json.dumps(speakers), json.dumps(instructs),
                self.model_size, -1,
                api_name="/generate_custom_voice_batch",
            )
            if not paths or len(paths) != len(jobs):
                return [None] * len(jobs), status
            return [AudioSegment.from_file(p) for p in paths], None
        except Exception as e:
            return [None] * len(jobs), str(e)

    def _generate_voice_clone_batch(self, jobs):
        import json
        from gradio_client import handle_file
        texts = [text for _voice, text, _style, _speed in jobs]
        try:
            client = self._get_client()
            paths, status = client.predict(
                json.dumps(texts), handle_file(self.ref_audio), self.ref_text,
                self.language, False, self.model_size, -1,
                api_name="/generate_voice_clone_batch",
            )
            if not paths or len(paths) != len(jobs):
                return [None] * len(jobs), status
            return [AudioSegment.from_file(p) for p in paths], None
        except Exception as e:
            return [None] * len(jobs), str(e)


class KokoroBackend:
    """Kokoro-MLX (Mac, Apple Silicon) über das `mlx-audio`-Paket
    (https://github.com/Blaizzy/mlx-audio, `pip install mlx-audio`).

    Läuft OHNE separaten Server: generate_chunk() lädt das Modell einmalig
    in-process (lazy, beim ersten Aufruf) und synthetisiert direkt — dafür
    trägt jeder podcast_maker.py-Prozess die Ladezeit selbst.

    Einschränkungen ggü. Qwen3-TTS:
    - Kein 'instruct'/Style. Kokoro folgt keinen Stilanweisungen — 'style'
      wird ignoriert, genau wie bei Voice-Clone-Backends. resolve_voice()
      gibt bewusst den eigenen kind "kokoro" zurück (nicht "speaker"),
      damit podcast_maker.py den fehlenden Style-Support korrekt meldet
      statt fälschlich "instruct aktiv" zu behaupten.
    - Mehrere unterschiedliche Stimmen funktionieren trotzdem (für den
      Drama-Modus) — jede Rolle bekommt einfach eine andere Kokoro-Voice-ID
      zugewiesen; nur die Stilanweisung pro Zeile geht dabei verloren.
    - Sprachabdeckung hängt vom installierten Kokoro-Modell/mlx-audio
      ab und ändert sich zwischen Versionen — diese Klasse validiert
      Stimmennamen NICHT gegen eine feste Liste. Ein falscher Name schlägt
      erst beim ersten generate_chunk() mit der Fehlermeldung von mlx-audio
      fehl, nicht schon bei resolve_voice(). Verfügbare Voice-IDs vor dem
      ersten Lauf prüfen (siehe README/mlx-audio-Doku).

    episodes.json:
      "audio": {
        "backend": "kokoro",
        "voice": "af_heart",
        "model_path": "mlx-community/Kokoro-82M-bf16",  # optional, das ist der Default
        "language_code": "a"  # optional: a=amerik. Englisch, b=brit. Englisch, ... (siehe Kokoro-Doku)
      }
    """

    def __init__(self, audio_config):
        self.model_path = audio_config.get("model_path", "mlx-community/Kokoro-82M-bf16")
        self.lang_code = audio_config.get("language_code", "a")
        self.sample_rate = audio_config.get("sample_rate", 24000)
        # Kein Server/keine URL — nur für die generische "Prüfe Verbindung..."-
        # Meldung in podcast_maker.py, die bei allen Backends backend.base_url liest.
        self.base_url = f"lokal (mlx-audio): {self.model_path}"
        self._model = None

    def _get_model(self):
        if self._model is None:
            from mlx_audio.tts.utils import load_model
            self._model = load_model(self.model_path)
        return self._model

    def check_api(self):
        """Kein Netzwerk-Ping möglich (lokales Modell, kein Server) — der
        einzige echte Check ist, das Modell tatsächlich zu laden. Das kann
        beim ersten Aufruf mehrere Sekunden dauern (Gewichte laden)."""
        try:
            self._get_model()
            return True
        except Exception:
            return False

    def resolve_voice(self, voice_name, seed=None):
        """Keine Server-Stimmenliste — Kokoro-Stimmen gehören zum Modell-
        Download und sind nicht dynamisch abfragbar. Wird ungeprüft
        durchgereicht (siehe Klassen-Docstring).

        seed wird nur fürs einheitliche Tupel-Format akzeptiert — generate_chunk()
        hier setzt aktuell keinen mlx-audio-Zufallsstate, ignoriert ihn also."""
        if not voice_name:
            return None, ["audio.voice fehlt in episodes.json (Kokoro-Voice-ID, z.B. 'af_heart')"], None
        return "kokoro", voice_name, seed

    def generate_chunk(self, voice, text, style=None, speed=None):
        """style wird ignoriert (kein instruct-Support). Gibt (AudioSegment,
        None) oder (None, fehlermeldung) zurück.

        voice: Tupel (kind, voice_id, seed) — seed wird hier nicht verwendet
        (siehe resolve_voice-Docstring)."""
        _, voice_id, _seed = voice
        try:
            import numpy as np
            model = self._get_model()
            chunks = []
            for result in model.generate(
                text=text,
                voice=voice_id,
                speed=speed or 1.0,
                lang_code=self.lang_code,
            ):
                chunks.append(np.asarray(result.audio))
            if not chunks:
                return None, "Kokoro lieferte kein Audio zurück."
            samples = np.concatenate(chunks)
            pcm = (samples * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
            segment = AudioSegment(data=pcm, sample_width=2,
                                   frame_rate=self.sample_rate, channels=1)
            return segment, None
        except ImportError:
            return None, ("mlx-audio nicht installiert — 'pip install mlx-audio' "
                          "(bzw. ins .venv) für Kokoro-Support.")
        except Exception as e:
            return None, str(e)
