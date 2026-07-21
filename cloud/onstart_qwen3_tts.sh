#!/bin/bash
# Läuft bei JEDEM Boot der vast.ai-Instanz (frischer Start UND nach "start"
# einer zuvor gestoppten Instanz). Idempotent: das eigentliche Setup läuft
# nur beim allerersten Mal -- danach existiert $REPO_DIR/.setup_done bereits
# und wird übersprungen, das ist der ganze Trick, um "schnell laden" zu
# erreichen, ohne ein eigenes Docker-Image bauen zu müssen (dafür fehlt auf
# dem MacBook der Plattenplatz).
set -e

WORKDIR="/workspace"
REPO_DIR="$WORKDIR/Qwen3-TTS"
LOG_FILE="$WORKDIR/qwen3-tts.log"
SETUP_MARKER="$REPO_DIR/.setup_done"

mkdir -p "$WORKDIR"

if [ ! -d "$REPO_DIR" ]; then
  echo "=== Repo wird geklont ==="
  git clone https://github.com/SUP3RMASS1VE/Qwen3-TTS.git "$REPO_DIR"
fi
cd "$REPO_DIR"

# Batch-Endpoint-Patch: IMMER versuchen (idempotent per Marker-Check im
# Script selbst), auch bei bereits fertig eingerichteten/resumten Instanzen
# -- die Demo-App der App hat von Haus aus keinen Batch-Endpoint, obwohl das
# zugrundeliegende Modell (qwen_tts.Qwen3TTSModel.generate_custom_voice)
# echtes Batching unterstuetzt (ein Forward-Pass fuer N Texte statt N
# einzelner Calls). Ohne den Patch bleibt die GPU bei paralleler Nutzung
# trotzdem bei ~11% Auslastung haengen, weil PyTorch nebenlaeufige Threads
# auf demselben CUDA-Default-Stream serialisiert -- gemessen ~13x schneller
# mit Batch=17 gegenueber Einzel-Calls (siehe cloud/README.md).
echo "=== Batch-Endpoint-Patch anwenden (idempotent) ==="
# Quoted Heredoc ('PYEOF', nicht "PYEOF"): bash fasst den Inhalt NICHT an
# (kein Escaping von $, ", \, Backticks) -- vermeidet die Falle von
# 'python3 -c "..."' mit verschachtelten bash+python-Escapes (\\n wurde dort
# beim ersten Versuch zu einem echten Zeilenumbruch und hätte in app.py
# einen Syntaxfehler erzeugt; per Diff gegen eine live getestete Patch-Version
# verifiziert).
python3 << 'PYEOF'
# Zwei unabhaengige, je fuer sich idempotente Patches (eigener Marker pro
# Funktion) -- Speaker-Batch UND Clone-Batch, damit beide Rollentypen
# (Built-in-Speaker wie Voice-Clone-Rollen, z.B. ein NARRATOR mit
# geklonter Stimme) echtes serverseitiges Batching bekommen, nicht nur
# einer davon. generate_voice_clone() unterstuetzt laut Docstring
# genauso Batch-Modus (ref_audio/ref_text werden automatisch auf alle
# Texte im Batch gebroadcastet, wenn nur EIN Wert statt einer Liste
# uebergeben wird -- passt exakt zu unserem Design: eine geteilte
# Voice-Clone-Identitaet pro Serie).

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

CUSTOM_MARKER = '# PODCAST_FABRIK_BATCH_PATCH'
CLONE_MARKER = '# PODCAST_FABRIK_CLONE_BATCH_PATCH'

if CUSTOM_MARKER not in src:
    FUNC = '''
''' + CUSTOM_MARKER + '''
def generate_custom_voice_batch(texts_json, language, speakers_json, instructs_json, model_size, seed):
    """Batch-Variante von generate_custom_voice: N Texte in EINEM
    Forward-Pass (self.model.generate() einmal fuer den ganzen Batch,
    kein Python-Loop) -- echte GPU-Parallelitaet statt seriellem
    Abarbeiten hinter demselben CUDA-Default-Stream.
    texts_json/speakers_json/instructs_json: JSON-Arrays gleicher Laenge."""
    import json as _json
    try:
        texts = _json.loads(texts_json)
        speakers = _json.loads(speakers_json)
        instructs = _json.loads(instructs_json)
    except Exception as e:
        return None, f"Error: ungueltiges JSON ({e})"

    if not texts:
        return None, "Error: keine Texte."
    if not (len(texts) == len(speakers) == len(instructs)):
        return None, (f"Error: Laengen ungleich (texts={len(texts)}, "
                       f"speakers={len(speakers)}, instructs={len(instructs)})")

    if seed == -1:
        seed = random.randint(0, 2147483647)
    seed = int(seed)
    set_seed(seed)

    tts = get_model("CustomVoice", model_size)

    speakers_norm = [s.lower().replace(" ", "_") for s in speakers]
    instructs_norm = [i.strip() if i else None for i in instructs]

    print(f"\\n{'='*50}")
    print(f"Batch Custom Voice Generation ({model_size}) -- {len(texts)} Chunks")
    print(f"{'='*50}")

    try:
        wavs, sr = tts.generate_custom_voice(
            text=[t.strip() for t in texts],
            language=language,
            speaker=speakers_norm,
            instruct=instructs_norm,
            non_streaming_mode=True,
            max_new_tokens=2048,
        )
    except Exception as e:
        print(f"Batch-Fehler: {type(e).__name__}: {e}")
        return None, f"Error: {type(e).__name__}: {e}"

    import tempfile
    import soundfile as sf
    paths = []
    for w in wavs:
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(f.name, w, sr)
        paths.append(f.name)

    total_duration = sum(len(w) / sr for w in wavs)
    status = f"Batch: {len(paths)} Clips, {total_duration:.1f}s Audio gesamt"
    print(status)
    return paths, status


'''
    src = src.replace('# Build Gradio UI\n', FUNC + '# Build Gradio UI\n', 1)

if CLONE_MARKER not in src:
    CLONE_FUNC = '''
''' + CLONE_MARKER + '''
def generate_voice_clone_batch(texts_json, ref_audio, ref_text, language, use_xvector_only, model_size, seed):
    """Batch-Variante von generate_voice_clone: N Texte in EINEM
    Forward-Pass, EIN geteiltes ref_audio/ref_text fuer den ganzen Batch
    (generate_voice_clone() broadcastet automatisch, wenn ref_audio/
    ref_text nicht als Liste kommen) -- passt zu GradioBackend: eine
    Voice-Clone-Identitaet pro Serie, mehrere Chunks/Rollen teilen sie
    sich."""
    import json as _json
    try:
        texts = _json.loads(texts_json)
    except Exception as e:
        return None, f"Error: ungueltiges JSON ({e})"

    if not texts:
        return None, "Error: keine Texte."

    audio_tuple = _audio_to_tuple(ref_audio)
    if audio_tuple is None:
        return None, "Error: Reference audio is required."
    if not use_xvector_only and (not ref_text or not ref_text.strip()):
        return None, "Error: Reference text is required when 'Use x-vector only' is not enabled."

    if seed == -1:
        seed = random.randint(0, 2147483647)
    seed = int(seed)
    set_seed(seed)

    tts = get_model("Base", model_size)

    print(f"\\n{'='*50}")
    print(f"Batch Voice Clone Generation ({model_size}) -- {len(texts)} Chunks")
    print(f"{'='*50}")

    try:
        wavs, sr = tts.generate_voice_clone(
            text=[t.strip() for t in texts],
            language=language,
            ref_audio=audio_tuple,
            ref_text=ref_text.strip() if ref_text else None,
            x_vector_only_mode=use_xvector_only,
            max_new_tokens=2048,
        )
    except Exception as e:
        print(f"Batch-Fehler: {type(e).__name__}: {e}")
        return None, f"Error: {type(e).__name__}: {e}"

    import tempfile
    import soundfile as sf
    paths = []
    for w in wavs:
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(f.name, w, sr)
        paths.append(f.name)

    total_duration = sum(len(w) / sr for w in wavs)
    status = f"Batch: {len(paths)} Clips, {total_duration:.1f}s Audio gesamt"
    print(status)
    return paths, status


'''
    src = src.replace('# Build Gradio UI\n', CLONE_FUNC + '# Build Gradio UI\n', 1)

# Zwei UNABHAENGIGE Idempotenz-Checks (eigener Marker-String pro Button) --
# nicht denselben "not in src"-Check fuer beide Bloecke wiederverwenden:
# sonst wuerde ein zweiter Patch-Lauf (der nur den Clone-Block nachtraegt,
# weil CLONE_MARKER beim ersten Lauf noch fehlte) die GESAMTE UI_WIRING
# ueberspringen, weil der Speaker-Button-Text schon aus Lauf 1 da ist --
# genau der Bug, an dem das hier beim ersten Versuch scheiterte.
if 'batch_btn = gr.Button("batch")' not in src:
    SPEAKER_UI_WIRING = '''
                # PODCAST_FABRIK_BATCH_PATCH -- unsichtbare Batch-API, nutzt
                # dieselben Backend-Objekte wie die UI oben, nur mit
                # Listen-Eingaben statt Einzel-Text (siehe
                # generate_custom_voice_batch).
                with gr.Row(visible=False):
                    batch_texts_in = gr.Textbox(label="texts_json")
                    batch_speakers_in = gr.Textbox(label="speakers_json")
                    batch_instructs_in = gr.Textbox(label="instructs_json")
                    batch_language_in = gr.Textbox(label="language", value="Auto")
                    batch_model_size_in = gr.Textbox(label="model_size", value="1.7B")
                    batch_seed_in = gr.Number(label="seed", value=-1, precision=0)
                    batch_files_out = gr.File(label="batch_files", file_count="multiple")
                    batch_status_out = gr.Textbox(label="batch_status")
                    batch_btn = gr.Button("batch")
                batch_btn.click(
                    generate_custom_voice_batch,
                    inputs=[batch_texts_in, batch_language_in, batch_speakers_in,
                            batch_instructs_in, batch_model_size_in, batch_seed_in],
                    outputs=[batch_files_out, batch_status_out],
                )

    return demo, theme, css
'''
    src = src.replace('\n    return demo, theme, css\n', SPEAKER_UI_WIRING, 1)

if 'clone_batch_btn = gr.Button("clone_batch")' not in src:
    CLONE_UI_WIRING = '''
                # PODCAST_FABRIK_CLONE_BATCH_PATCH -- unsichtbare Batch-API
                # fuer Voice-Clone-Rollen (siehe generate_voice_clone_batch).
                with gr.Row(visible=False):
                    clone_batch_texts_in = gr.Textbox(label="texts_json")
                    clone_batch_audio_in = gr.Audio(label="ref_audio", type="numpy")
                    clone_batch_ref_text_in = gr.Textbox(label="ref_text")
                    clone_batch_language_in = gr.Textbox(label="language", value="Auto")
                    clone_batch_xvector_in = gr.Checkbox(label="use_xvector_only", value=False)
                    clone_batch_model_size_in = gr.Textbox(label="model_size", value="1.7B")
                    clone_batch_seed_in = gr.Number(label="seed", value=-1, precision=0)
                    clone_batch_files_out = gr.File(label="clone_batch_files", file_count="multiple")
                    clone_batch_status_out = gr.Textbox(label="clone_batch_status")
                    clone_batch_btn = gr.Button("clone_batch")
                clone_batch_btn.click(
                    generate_voice_clone_batch,
                    inputs=[clone_batch_texts_in, clone_batch_audio_in, clone_batch_ref_text_in,
                            clone_batch_language_in, clone_batch_xvector_in, clone_batch_model_size_in,
                            clone_batch_seed_in],
                    outputs=[clone_batch_files_out, clone_batch_status_out],
                )

    return demo, theme, css
'''
    src = src.replace('\n    return demo, theme, css\n', CLONE_UI_WIRING, 1)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)

print('Patch angewendet (Speaker-Batch:', CUSTOM_MARKER in src, '| Clone-Batch:', CLONE_MARKER in src, ')')
PYEOF

if [ ! -f "$SETUP_MARKER" ]; then
  echo "=== Erststart: Environment wird aufgesetzt (einmalig, dauert einige Minuten) ==="
  apt-get update -qq
  apt-get install -y -qq ffmpeg sox >/dev/null

  # Kein eigenes venv: das Basis-Image (pytorch/pytorch:*-cuda12.8-*) bringt
  # bereits ein funktionierendes Torch+CUDA-12.8-Environment mit -- ein
  # frisches venv würde das nicht erben und Torch samt allen nvidia-cuda-*
  # Wheels (mehrere GB) unnötig neu herunterladen. Der Container selbst ist
  # schon die Isolationsgrenze, ein zusätzliches venv bringt hier nichts.
  pip install --upgrade pip uv -q
  uv pip install --system -r requirements.txt
  # gradio_client wird nur fuer den Warmup-Call unten gebraucht (nicht
  # zwingend eine requirements.txt-Abhaengigkeit des Servers selbst).
  # hf_transfer beschleunigt den (mit Abstand groessten) Download im ganzen
  # Setup -- die Modell-Weights von HuggingFace -- durch parallele
  # Multi-Connection-Uebertragung statt der langsamen Single-Connection
  # requests-Downloads, die huggingface_hub sonst standardmaessig nutzt.
  uv pip install --system -q gradio_client hf_transfer

  # Nur falls das Basis-Image doch mal kein passendes CUDA-Torch mitbringt:
  # gezielter Fallback statt pauschalem Neu-Download.
  if ! python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "=== Torch/CUDA aus Basis-Image nicht nutzbar -- installiere gezielt nach ==="
    uv pip install --system torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
        --index-url https://download.pytorch.org/whl/cu128
  fi
  echo "=== Environment-Setup abgeschlossen ==="
else
  echo "=== Environment bereits vorhanden (persistenter Datenträger) — Setup übersprungen ==="
fi

# Gradio bindet ohne server_name-Override standardmäßig nur auf 127.0.0.1 —
# von außerhalb des Containers (also von podcast_maker.py auf dem Mac) wäre
# der Server sonst über den gemappten Port nicht erreichbar.
export GRADIO_SERVER_NAME=0.0.0.0
export GRADIO_SERVER_PORT=7860
# Gilt fuer den Server-Prozess selbst (app.py laedt das Modell beim ersten
# generate-Aufruf) UND fuer den Warmup-Call weiter unten -- muss deshalb
# schon vor "nohup python3 app.py" gesetzt sein, nicht erst beim Warmup.
export HF_HUB_ENABLE_HF_TRANSFER=1

echo "=== Starte Qwen3-TTS Gradio-Server auf Port 7860 (Log: $LOG_FILE) ==="
nohup python3 app.py > "$LOG_FILE" 2>&1 &
disown

echo "=== Warte auf Server-Start ==="
for i in $(seq 1 60); do
  if curl -sf -o /dev/null -m 3 "http://127.0.0.1:7860/"; then
    break
  fi
  sleep 5
done

# .setup_done gilt erst NACH einem erfolgreichen Testrender als gesetzt --
# vorher hat "Setup fertig" nur bedeutet "Server-Prozess gestartet", nicht
# "Modell von HuggingFace heruntergeladen und einsatzbereit im Cache". Ohne
# diesen Warmup würde genau dieser Download unbemerkt erst beim ERSTEN
# echten render_remote.sh-Call passieren -- ein versteckter, potenziell
# langer Kaltstart mitten im eigentlichen Vertonungs-Lauf.
if [ ! -f "$SETUP_MARKER" ]; then
  echo "=== Warmup: erzwinge Modell-Download/-Cache mit einem Testrender ==="
  python3 -c "
from gradio_client import Client
client = Client('http://127.0.0.1:7860')
audio_path, status = client.predict(
    text='Warmup.',
    language='Auto',
    speaker='Vivian',
    instruct='',
    model_size='1.7B',
    seed=-1,
    api_name='/generate_custom_voice',
)
if not audio_path:
    raise SystemExit(f'Warmup fehlgeschlagen: {status}')
print('Warmup erfolgreich:', status)
"
  touch "$SETUP_MARKER"
  echo "=== Setup + Warmup abgeschlossen — Instanz ist voll einsatzbereit ==="
else
  echo "=== Warmup bereits erledigt (persistenter Modell-Cache) — übersprungen ==="
fi

echo "=== onstart fertig — Server läuft im Hintergrund ==="
