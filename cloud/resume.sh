#!/bin/bash
# Startet eine zuvor gestoppte Instanz neu. Da die Festplatte erhalten blieb,
# überspringt das Onstart-Script Setup/Modell-Download und der Gradio-Server
# ist innerhalb weniger Sekunden/Minuten wieder erreichbar (statt erneut alles
# zu installieren). Danach status.sh für die neue öffentliche Adresse prüfen
# — die kann sich nach einem Stop/Start-Zyklus ändern.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTANCE_ID="${1:-$(cat "${SCRIPT_DIR}/.last_instance_id" 2>/dev/null)}"

if [ -z "$INSTANCE_ID" ]; then
  echo "Nutzung: $0 <instance_id>"
  exit 1
fi

vastai start instance "$INSTANCE_ID"
echo "Instanz $INSTANCE_ID startet ... Status/URL prüfen mit: ${SCRIPT_DIR}/status.sh $INSTANCE_ID"
