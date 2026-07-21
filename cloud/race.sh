#!/bin/bash
# Mietet mehrere RTX-5090-Instanzen GLEICHZEITIG (Standard: 5, per
# race_pick_offers.py aus einer Preisspanne + PCIe-Bandbreite + bekannt
# zuverlässigem Host ausgewählt statt stur der billigsten), wartet bis der
# Gradio-Server der ERSTEN tatsächlich antwortet, behält nur diese und
# löscht den Rest sofort wieder. Löst das Problem einzelner Hosts, die beim
# Docker-Pull/Setup hängen bleiben oder ewig brauchen -- kostet nur ein paar
# Minuten Parallel-Miete auf den "Verlierern" (typisch < $0.50 insgesamt).
# Für den normalen Vertonungs-Workflow get_ready_instance.sh nutzen -- das
# probiert erst den Pool bereits fertig eingerichteter Instanzen und ruft
# race.sh nur als Fallback auf, wenn der komplette Pool nicht bereit wird.
#
# Nutzung: ./race.sh [anzahl]   (Standard: 5)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_HASH="c2352e9ebc56ffd4b83b51c6d229363a"
N="${1:-5}"
MAX_WAIT_MINUTES=20

python3 "${SCRIPT_DIR}/machine_stats.py" reconcile

echo "Suche die $N günstigsten verfügbaren RTX 5090 (verified Datacenter, >=1000 Mbit/s, nur Osteuropa/Baltikum) ..."
OFFER_IDS=()
while IFS= read -r line; do
  [ -n "$line" ] && OFFER_IDS+=("$line")
done < <(vastai search offers 'gpu_name=RTX_5090 disk_space>=40 reliability>0.98 verified=true rentable=true inet_down>1000 inet_up>1000 geolocation in [PL,CZ,SK,HU,RO,BG,EE,LV,LT,UA,MD]' -o 'dph_total' --raw \
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
# Datei statt Bash-Variable für die rohe JSON-Antwort: das große 'onstart'-
# Feld (komplettes onstart_qwen3_tts.sh als JSON-String) übersteht einen
# Bash-Variable/echo-Umweg nicht zuverlässig (kommt als kaputtes JSON an,
# 'Invalid control character') -- macht die Bereitschaftsprüfung sonst
# lautlos permanent blind, siehe get_ready_instance.sh. Eine echte Datei
# ist stabil UND behält die Optimierung "ein API-Call pro Runde für alle
# Kandidaten" (direktes Pipen pro IID würde das auf N Calls/Runde erhöhen).
RAW_FILE="$(mktemp)"
trap 'rm -f "$RAW_FILE"' EXIT
ROUNDS=$((MAX_WAIT_MINUTES * 60 / 15))
for round in $(seq 1 "$ROUNDS"); do
  vastai show instances-v1 --raw 2>/dev/null > "$RAW_FILE"
  for IID in "${INSTANCE_IDS[@]}"; do
    URL=$(python3 "${SCRIPT_DIR}/get_gradio_url.py" "$IID" < "$RAW_FILE" 2>/dev/null) || continue
    # -m 10 statt frueher 3: die Gradio-Startseite braucht ueber die
    # oeffentliche Adresse beobachtet ~5s zum Antworten -- ein 3s-Timeout
    # meldete einen laengst fertigen Server faelschlich als "nicht bereit".
    if [ -n "$URL" ] && curl -sf -o /dev/null -m 10 "$URL"; then
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
# Nur der Sieger wird getrackt -- die Verlierer werden gleich gelöscht, WEIL
# sie das Rennen verloren haben, nicht weil ihre Maschine sich als kaputt
# erwiesen hätte (sonst würden schnelle, aber knapp zu spät fertige Hosts
# fälschlich blacklisted).
python3 "${SCRIPT_DIR}/machine_stats.py" record "$WINNER"

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
