#!/bin/bash
# Startet das WebUI-Cockpit — richtet das venv beim allerersten Mal
# automatisch ein und öffnet den Browser, sobald der Server bereit ist.
#
# Nutzung:
#   ./start_webui.sh
#   WEBUI_PORT=5555 ./start_webui.sh   # anderer Port

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBUI_DIR="$SCRIPT_DIR/webui"
VENV_DIR="$WEBUI_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Einmaliges Setup: erstelle webui/.venv ..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install -q -r "$WEBUI_DIR/requirements.txt"
fi

PORT="${WEBUI_PORT:-5151}"
URL="http://127.0.0.1:$PORT"

# Browser erst öffnen, wenn der Server tatsächlich antwortet (im Hintergrund,
# blockiert den Serverstart nicht) — bricht nach ~10s ab, falls etwas hakt.
( for _ in $(seq 1 30); do
    if curl -s -o /dev/null "$URL"; then
      open "$URL" 2>/dev/null
      break
    fi
    sleep 0.3
  done ) &

echo "Starte WebUI auf $URL ..."
cd "$WEBUI_DIR"
exec .venv/bin/python app.py
