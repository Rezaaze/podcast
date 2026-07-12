#!/bin/bash
# Zeigt Status, öffentliche Adresse (für episodes.json: audio.api_url) und
# die letzten Zeilen des Setup-/Server-Logs einer gemieteten Instanz.
#
# Nutzung: ./cloud/status.sh [instance_id]   (ohne ID: nimmt die zuletzt
#                                              von rent.sh gemietete Instanz)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTANCE_ID="${1:-$(cat "${SCRIPT_DIR}/.last_instance_id" 2>/dev/null)}"

if [ -z "$INSTANCE_ID" ]; then
  echo "Keine Instanz-ID angegeben und keine .last_instance_id gefunden."
  echo "Nutzung: $0 <instance_id>"
  exit 1
fi

echo "=== vast.ai Instanz $INSTANCE_ID ==="
# "vastai show instance <id>" (Singular) liefert in manchen CLI-Versionen
# fälschlich null zurück -- "show instances-v1" (Plural) funktioniert
# zuverlässig, hier auf die gesuchte ID gefiltert.
vastai show instances-v1 --raw | python3 "${SCRIPT_DIR}/format_status.py" "$INSTANCE_ID"

echo ""
echo "=== Setup-/Server-Log (letzte 30 Zeilen) ==="
SSH_URL=$(vastai ssh-url "$INSTANCE_ID" 2>/dev/null)
if [ -n "$SSH_URL" ]; then
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$SSH_URL" \
    "tail -n 30 /workspace/qwen3-tts.log 2>/dev/null || echo '(noch keine Logdatei — Onstart läuft evtl. noch)'" \
    || echo "(SSH noch nicht bereit — in ein paar Sekunden erneut versuchen)"
else
  echo "(SSH-URL noch nicht verfügbar — Instanz startet evtl. noch hoch)"
fi
