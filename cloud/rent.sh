#!/bin/bash
# Sucht den günstigsten verfügbaren RTX-5090-Server und mietet ihn mit dem
# gespeicherten vast.ai-Template "podcast-fabrik-qwen3-tts". Das Template
# installiert Qwen3-TTS beim ALLERERSTEN Boot automatisch (dauert einige
# Minuten); danach die Instanz per stop.sh pausieren (Platte bleibt
# erhalten, kein Neu-Setup nötig) statt destroy.sh (löscht alles).
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_HASH="5e86232eb1812a3891eae5329cb2b25b"

echo "Suche günstigste verfügbare RTX 5090 (verified Datacenter, zuverlässig, ausreichend Platz, >=1000 Mbit/s) ..."
OFFER_ID=$(vastai search offers 'gpu_name=RTX_5090 disk_space>=40 reliability>0.98 verified=true rentable=true inet_down>1000 inet_up>1000' -o 'dph_total' --raw \
  | python3 "${SCRIPT_DIR}/pick_cheapest_offer.py")

echo "Miete Instanz auf Offer $OFFER_ID ..."
RESULT=$(vastai create instance "$OFFER_ID" --template_hash "$TEMPLATE_HASH" --disk 45 --raw)
echo "$RESULT"
INSTANCE_ID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['new_contract'])")

echo "$INSTANCE_ID" > "${SCRIPT_DIR}/.last_instance_id"

echo ""
echo "Instanz $INSTANCE_ID wird eingerichtet — Setup läuft im Hintergrund (erster Start: einige Minuten)."
echo "Fortschritt/Verbindungsdaten prüfen:  ${SCRIPT_DIR}/status.sh"
echo "(Instanz-ID wurde in ${SCRIPT_DIR}/.last_instance_id gespeichert — die anderen Scripte finden sie automatisch.)"
