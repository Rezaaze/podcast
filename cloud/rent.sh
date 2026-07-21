#!/bin/bash
# Sucht einen verfügbaren RTX-5090-Server (nicht stur den billigsten,
# siehe pick_cheapest_offer.py: Preisspanne + PCIe-Bandbreite + bekannt
# zuverlässiger Host) und mietet ihn mit dem gespeicherten vast.ai-Template
# "podcast-fabrik-qwen3-tts". Das Template installiert Qwen3-TTS beim
# ALLERERSTEN Boot automatisch (dauert einige Minuten); danach die Instanz
# per stop.sh pausieren (Platte bleibt erhalten, kein Neu-Setup nötig)
# statt destroy.sh (löscht alles). Für den normalen Vertonungs-Workflow
# stattdessen get_ready_instance.sh nutzen (probiert erst den Pool fertig
# eingerichteter Instanzen) -- rent.sh ist der manuelle Einzel-Weg bzw.
# wird intern von race.sh verwendet.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_HASH="c2352e9ebc56ffd4b83b51c6d229363a"

# Abgleich, welche seit dem letzten Lauf getrackten Instanzen inzwischen
# verschwunden sind (destroyed -- egal ob automatisch oder von Hand) und
# Blacklist/Favoriten entsprechend aktualisieren, siehe machine_stats.py.
python3 "${SCRIPT_DIR}/machine_stats.py" reconcile

echo "Suche verfügbare RTX 5090 (verified Datacenter, zuverlässig, ausreichend Platz, >=1000 Mbit/s, schnelle PCIe-Anbindung bevorzugt, nur Osteuropa/Baltikum) ..."
OFFER_ID=$(vastai search offers 'gpu_name=RTX_5090 disk_space>=40 reliability>0.98 verified=true rentable=true inet_down>1000 inet_up>1000 geolocation in [PL,CZ,SK,HU,RO,BG,EE,LV,LT,UA,MD]' -o 'dph_total' --raw \
  | python3 "${SCRIPT_DIR}/pick_cheapest_offer.py")

echo "Miete Instanz auf Offer $OFFER_ID ..."
RESULT=$(vastai create instance "$OFFER_ID" --template_hash "$TEMPLATE_HASH" --disk 45 --raw)
echo "$RESULT"
INSTANCE_ID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['new_contract'])")

echo "$INSTANCE_ID" > "${SCRIPT_DIR}/.last_instance_id"
python3 "${SCRIPT_DIR}/machine_stats.py" record "$INSTANCE_ID"

echo ""
echo "Instanz $INSTANCE_ID wird eingerichtet — Setup läuft im Hintergrund (erster Start: einige Minuten)."
echo "Fortschritt/Verbindungsdaten prüfen:  ${SCRIPT_DIR}/status.sh"
echo "(Instanz-ID wurde in ${SCRIPT_DIR}/.last_instance_id gespeichert — die anderen Scripte finden sie automatisch.)"
