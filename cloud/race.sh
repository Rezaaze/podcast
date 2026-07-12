#!/bin/bash
# Mietet mehrere RTX-5090-Instanzen GLEICHZEITIG (Standard: 5), wartet bis
# der Gradio-Server der ERSTEN tatsächlich antwortet, behält nur diese und
# löscht den Rest sofort wieder. Löst das Problem einzelner Hosts, die beim
# Docker-Pull/Setup hängen bleiben oder ewig brauchen -- kostet nur ein paar
# Minuten Parallel-Miete auf den "Verlierern" (typisch < $0.50 insgesamt).
#
# Nutzung: ./race.sh [anzahl]   (Standard: 5)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_HASH="5e86232eb1812a3891eae5329cb2b25b"
N="${1:-5}"
MAX_WAIT_MINUTES=20

echo "Suche die $N günstigsten verfügbaren RTX 5090 (verified Datacenter, >=1000 Mbit/s) ..."
OFFER_IDS=()
while IFS= read -r line; do
  [ -n "$line" ] && OFFER_IDS+=("$line")
done < <(vastai search offers 'gpu_name=RTX_5090 disk_space>=40 reliability>0.98 verified=true rentable=true inet_down>1000 inet_up>1000' -o 'dph_total' --raw \
  | python3 "${SCRIPT_DIR}/race_pick_offers.py" "$N")

if [ "${#OFFER_IDS[@]}" -eq 0 ]; then
  echo "Keine Angebote gefunden."
  exit 1
fi

INSTANCE_IDS=()
for OFFER_ID in "${OFFER_IDS[@]}"; do
  echo "Miete Instanz auf Offer $OFFER_ID ..."
  RESULT=$(vastai create instance "$OFFER_ID" --template_hash "$TEMPLATE_HASH" --disk 45 --raw 2>&1) || {
    echo "  Fehlgeschlagen: $RESULT"
    continue
  }
  IID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('new_contract',''))" 2>/dev/null)
  if [ -n "$IID" ]; then
    INSTANCE_IDS+=("$IID")
    echo "  -> Instanz $IID"
  else
    echo "  Fehlgeschlagen: $RESULT"
  fi
done

if [ "${#INSTANCE_IDS[@]}" -eq 0 ]; then
  echo "Keine Instanz konnte gemietet werden."
  exit 1
fi

printf '%s\n' "${INSTANCE_IDS[@]}" > "${SCRIPT_DIR}/.race_instance_ids"
echo ""
echo "Gemietete Instanzen: ${INSTANCE_IDS[*]}"
echo "Warte, bis die erste Instanz ihren Gradio-Server bereit hat (max. ${MAX_WAIT_MINUTES} Min.) ..."

WINNER=""
WINNER_URL=""
ROUNDS=$((MAX_WAIT_MINUTES * 60 / 15))
for round in $(seq 1 "$ROUNDS"); do
  RAW=$(vastai show instances-v1 --raw 2>/dev/null)
  for IID in "${INSTANCE_IDS[@]}"; do
    URL=$(echo "$RAW" | python3 "${SCRIPT_DIR}/get_gradio_url.py" "$IID" 2>/dev/null) || continue
    if [ -n "$URL" ] && curl -sf -o /dev/null -m 3 "$URL"; then
      WINNER="$IID"
      WINNER_URL="$URL"
      break 2
    fi
  done
  echo "  [$(date +%H:%M:%S)] noch keine Instanz bereit ..."
  sleep 15
done

if [ -z "$WINNER" ]; then
  echo ""
  echo "Keine Instanz wurde innerhalb von ${MAX_WAIT_MINUTES} Minuten bereit."
  echo "Instanzen laufen weiter (kosten Geld!) -- manuell prüfen: ${SCRIPT_DIR}/status.sh <id>"
  echo "IDs: ${INSTANCE_IDS[*]}"
  exit 1
fi

echo ""
echo "🏆 Instanz $WINNER ist zuerst bereit: $WINNER_URL"
echo "$WINNER" > "${SCRIPT_DIR}/.last_instance_id"

echo "Lösche die restlichen Instanzen ..."
for IID in "${INSTANCE_IDS[@]}"; do
  if [ "$IID" != "$WINNER" ]; then
    if vastai destroy instance "$IID" >/dev/null 2>&1; then
      echo "  Instanz $IID gelöscht."
    else
      echo "  Instanz $IID konnte nicht gelöscht werden (evtl. schon weg) -- manuell prüfen."
    fi
  fi
done
rm -f "${SCRIPT_DIR}/.race_instance_ids"

echo ""
echo "Fertig. Gewinner-Instanz: $WINNER"
echo "In episodes.json eintragen:"
echo "  \"audio\": { \"backend\": \"gradio\", \"api_url\": \"${WINNER_URL}\", ... }"
