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

  # Nur falls das Basis-Image doch mal kein passendes CUDA-Torch mitbringt:
  # gezielter Fallback statt pauschalem Neu-Download.
  if ! python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "=== Torch/CUDA aus Basis-Image nicht nutzbar -- installiere gezielt nach ==="
    uv pip install --system torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
        --index-url https://download.pytorch.org/whl/cu128
  fi

  touch "$SETUP_MARKER"
  echo "=== Setup abgeschlossen ==="
else
  echo "=== Environment bereits vorhanden (persistenter Datenträger) — Setup übersprungen ==="
fi

# Gradio bindet ohne server_name-Override standardmäßig nur auf 127.0.0.1 —
# von außerhalb des Containers (also von podcast_maker.py auf dem Mac) wäre
# der Server sonst über den gemappten Port nicht erreichbar.
export GRADIO_SERVER_NAME=0.0.0.0
export GRADIO_SERVER_PORT=7860

echo "=== Starte Qwen3-TTS Gradio-Server auf Port 7860 (Log: $LOG_FILE) ==="
nohup python3 app.py > "$LOG_FILE" 2>&1 &
disown

echo "=== onstart fertig — Server läuft im Hintergrund ==="
