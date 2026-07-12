#!/bin/bash
# Pausiert die Instanz: GPU-Abrechnung stoppt, die Festplatte (inkl. fertig
# eingerichtetem Qwen3-TTS + venv + heruntergeladenem Modell) bleibt erhalten
# und kostet nur noch den kleinen Storage-Preis. Zum Weitermachen: resume.sh.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTANCE_ID="${1:-$(cat "${SCRIPT_DIR}/.last_instance_id" 2>/dev/null)}"

if [ -z "$INSTANCE_ID" ]; then
  echo "Nutzung: $0 <instance_id>"
  exit 1
fi

vastai stop instance "$INSTANCE_ID"
echo "Instanz $INSTANCE_ID gestoppt — Festplatte bleibt erhalten (nur Storage-Kosten laufen weiter)."
echo "Wieder starten mit: ${SCRIPT_DIR}/resume.sh $INSTANCE_ID"
