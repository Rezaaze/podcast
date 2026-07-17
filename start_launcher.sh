#!/bin/bash
# Startet die Cockpit-Steuerung (Mini-Supervisor) — eine kleine Weboberfläche,
# über die du die 4 Podcast-Fabrik-Cockpits per Knopf starten/stoppen/neustarten
# kannst. Jedes Cockpit bleibt ein eigener Webserver auf eigenem Port.
#
# Nutzung:
#   ./start_launcher.sh
#   LAUNCHER_PORT=5150 LAUNCHER_COUNT=4 ./start_launcher.sh   # anpassbar

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBUI_DIR="$SCRIPT_DIR/webui"
VENV_DIR="$WEBUI_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Einmaliges Setup: erstelle webui/.venv ..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install -q -r "$WEBUI_DIR/requirements.txt"
fi

PORT="${LAUNCHER_PORT:-5150}"
URL="http://127.0.0.1:$PORT"

( for _ in $(seq 1 30); do
    if curl -s -o /dev/null "$URL"; then open "$URL" 2>/dev/null; break; fi
    sleep 0.3
  done ) &

echo "Starte Cockpit-Steuerung auf $URL ..."
cd "$WEBUI_DIR"
exec .venv/bin/python launcher.py
