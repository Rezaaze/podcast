#!/bin/bash
# ACHTUNG: löscht die Instanz UND ihre Festplatte unwiderruflich — danach
# muss beim nächsten Mieten (rent.sh) das komplette Setup (Torch/CUDA-Install,
# Modell-Download) erneut laufen. Für "nur pausieren" stattdessen stop.sh
# benutzen.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTANCE_ID="${1:-$(cat "${SCRIPT_DIR}/.last_instance_id" 2>/dev/null)}"

if [ -z "$INSTANCE_ID" ]; then
  echo "Nutzung: $0 <instance_id>"
  exit 1
fi

read -p "Instanz $INSTANCE_ID WIRKLICH endgültig löschen (inkl. Festplatte)? [y/N] " confirm
if [ "$confirm" != "y" ]; then
  echo "Abgebrochen."
  exit 0
fi

vastai destroy instance "$INSTANCE_ID"
rm -f "${SCRIPT_DIR}/.last_instance_id"
echo "Instanz $INSTANCE_ID gelöscht."
