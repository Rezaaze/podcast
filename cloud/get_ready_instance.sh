#!/bin/bash
# Liefert schnellstmöglich eine einsatzbereite Instanz: probiert zuerst der
# Reihe nach die gepoolten (gestoppten, bereits fertig eingerichteten)
# Instanzen aus .instance_pool per Resume -- das dauert nur Sekunden bis
# wenige Minuten, weil Setup+Modell-Download+Warmup (siehe
# onstart_qwen3_tts.sh) bereits erledigt sind. Erst wenn KEINE Pool-Instanz
# rechtzeitig bereit wird, fällt es auf race.sh zurück (komplette
# Neuvermietung mehrerer Kandidaten) und nimmt die gewonnene neue Instanz
# automatisch in den Pool auf (max. 2 Einträge).
#
# Nutzung: ./get_ready_instance.sh
# Ausgabe: NUR die Instanz-ID auf stdout (fuer $(...) in aufrufenden
# Scripten wie render_remote.sh), aller Fortschritt geht nach stderr.
# Setzt .last_instance_id auf die gefundene Instanz.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# vastai (pip --user) liegt in ~/.local/bin -- kann in minimalen
# Subprocess-PATHs (z.B. WebUI-Job) fehlen.
export PATH="${HOME}/.local/bin:${PATH}"
POOL_FILE="${SCRIPT_DIR}/.instance_pool"
MAX_POOL_SIZE=2
MAX_WAIT_SECONDS=180

touch "$POOL_FILE"
POOL_IDS=()
while IFS= read -r line; do
  [ -n "$line" ] && POOL_IDS+=("$line")
done < "$POOL_FILE"

is_ready() {
  local iid="$1" raw url
  raw=$(vastai show instances-v1 --raw 2>/dev/null) || return 1
  url=$(echo "$raw" | python3 "${SCRIPT_DIR}/get_gradio_url.py" "$iid" 2>/dev/null) || return 1
  [ -n "$url" ] && curl -sf -o /dev/null -m 10 "$url"
}

wait_ready() {
  local iid="$1" rounds=$((MAX_WAIT_SECONDS / 10)) i
  for i in $(seq 1 "$rounds"); do
    is_ready "$iid" && return 0
    sleep 10
  done
  return 1
}

TRIED_ALIVE=()
REMAINING=()
WINNER=""
for IID in "${POOL_IDS[@]}"; do
  if [ -n "$WINNER" ]; then
    REMAINING+=("$IID")
    continue
  fi
  # Läuft die Instanz bereits (z.B. weil sie gerade eben schon benutzt
  # wurde)? Dann direkt nehmen -- ein "vastai start" auf einer laufenden
  # Instanz kann fehlschlagen und würde sie fälschlich aus dem Pool werfen.
  if is_ready "$IID"; then
    echo "Pool-Instanz $IID läuft bereits und ist bereit." >&2
    WINNER="$IID"
    TRIED_ALIVE+=("$IID")
    continue
  fi
  echo "Versuche Pool-Instanz $IID zu resumen ..." >&2
  if ! vastai start instance "$IID" >/dev/null 2>&1; then
    echo "  $IID nicht mehr startbar -- wird aus dem Pool entfernt." >&2
    continue
  fi
  if wait_ready "$IID"; then
    WINNER="$IID"
    TRIED_ALIVE+=("$IID")
    echo "  $IID ist bereit." >&2
  else
    TRIED_ALIVE+=("$IID")
    echo "  $IID wurde nach ${MAX_WAIT_SECONDS}s nicht bereit -- nächster Kandidat." >&2
  fi
done

if [ -n "$WINNER" ]; then
  {
    printf '%s\n' "${TRIED_ALIVE[@]}"
    printf '%s\n' "${REMAINING[@]}"
  } > "$POOL_FILE"
  echo "$WINNER" > "${SCRIPT_DIR}/.last_instance_id"
  echo "$WINNER"
  exit 0
fi

echo "" >&2
echo "Kein Pool-Kandidat war rechtzeitig einsatzbereit -- weiche auf race.sh (Neuvermietung) aus." >&2
"${SCRIPT_DIR}/race.sh" 2 >&2

WINNER=$(cat "${SCRIPT_DIR}/.last_instance_id" 2>/dev/null)
if [ -z "$WINNER" ]; then
  echo "race.sh konnte keine Instanz bereitstellen." >&2
  exit 1
fi

NEW_POOL=("$WINNER" "${TRIED_ALIVE[@]}")
printf '%s\n' "${NEW_POOL[@]:0:$MAX_POOL_SIZE}" > "$POOL_FILE"
echo "Pool aktualisiert: $(tr '\n' ' ' < "$POOL_FILE")" >&2
echo "$WINNER"
