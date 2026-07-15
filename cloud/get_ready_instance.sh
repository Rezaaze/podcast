#!/bin/bash
# Liefert schnellstmöglich eine einsatzbereite Instanz: probiert zuerst der
# Reihe nach die gepoolten (gestoppten, bereits fertig eingerichteten)
# Instanzen aus .instance_pool per Resume -- das dauert nur Sekunden bis
# wenige Minuten, weil Setup+Modell-Download+Warmup (siehe
# onstart_qwen3_tts.sh) bereits erledigt sind. Ist der Pool leer/keine
# Pool-Instanz rechtzeitig bereit, wird gezielt EIN Angebot auf der
# bevorzugten Stamm-Instanz (PREFERRED_MACHINE_ID, siehe Memory
# 'vastai-stamm-instanz') gesucht -- kein Retry/Polling, ein einzelner
# Suchaufruf: ist die Maschine gerade nicht als Angebot gelistet (anderweitig
# vermietet/offline), wird SOFORT auf race.sh (Neuvermietung mehrerer
# Kandidaten) ausgewichen, ohne auf sie zu warten. Die gewonnene Instanz
# (ob bevorzugte Maschine oder race.sh-Sieger) landet automatisch im Pool
# (max. 2 Einträge).
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
TEMPLATE_HASH="c2352e9ebc56ffd4b83b51c6d229363a"
# 55308: die zweifach verifizierte EU-Stamm-Instanz (Estland) -- siehe
# Memory 'vastai-stamm-instanz' / KNOWN_RELIABLE_MACHINE_IDS in
# pick_cheapest_offer.py/race_pick_offers.py. Dort ist sie nur eine weiche
# Präferenz unter mehreren Kandidaten; hier wird sie gezielt zuerst
# versucht, bevor überhaupt geracet wird.
PREFERRED_MACHINE_ID=55308
PREFERRED_SETUP_WAIT_SECONDS=1200

python3 "${SCRIPT_DIR}/machine_stats.py" reconcile

touch "$POOL_FILE"
POOL_IDS=()
while IFS= read -r line; do
  [ -n "$line" ] && POOL_IDS+=("$line")
done < "$POOL_FILE"

is_ready() {
  # WICHTIG: 'vastai show instances-v1 --raw' DIREKT in get_gradio_url.py
  # pipen, NICHT über eine Bash-Variable umleiten (raw=$(...); echo "$raw" |
  # ...) -- das große, mehrere KB lange 'onstart'-Feld (das komplette
  # onstart_qwen3_tts.sh als JSON-String) übersteht den Bash-Variable/
  # echo-Umweg nicht zuverlässig und kommt am anderen Ende als kaputtes JSON
  # an ('Invalid control character'), was get_gradio_url.py mangels
  # Fehlerausgabe (2>/dev/null) lautlos zum Absturz bringt -- is_ready()
  # meldete dadurch JEDE Instanz dauerhaft als "nicht bereit", auch
  # tatsächlich längst laufende (im vast.ai-Dashboard "Connected"). Direktes
  # Pipen umgeht den Bash-Variable-Roundtrip komplett und ist reproduzierbar
  # stabil (siehe Session-Log).
  local iid="$1" url
  url=$(vastai show instances-v1 --raw 2>/dev/null \
    | python3 "${SCRIPT_DIR}/get_gradio_url.py" "$iid" 2>/dev/null) || return 1
  [ -n "$url" ] && curl -sf -o /dev/null -m 10 "$url"
}

wait_ready() {
  local iid="$1" wait_seconds="${2:-$MAX_WAIT_SECONDS}" rounds=$((wait_seconds / 10)) i
  for i in $(seq 1 "$rounds"); do
    is_ready "$iid" && return 0
    sleep 10
  done
  return 1
}

# Ein einzelner, gezielter Suchaufruf auf PREFERRED_MACHINE_ID -- kein
# Retry/Polling auf Verfügbarkeit (siehe Kopfkommentar). Gibt bei Erfolg die
# neue Instanz-ID auf stdout aus, sonst nichts (leerer stdout = "nicht
# verfügbar, weiter mit race.sh").
try_preferred_machine() {
  if [ -n "$(python3 "${SCRIPT_DIR}/machine_stats.py" is-blacklisted "$PREFERRED_MACHINE_ID")" ]; then
    echo "Bevorzugte Maschine ${PREFERRED_MACHINE_ID} ist gerade blacklisted -- weiche auf race.sh aus." >&2
    return 1
  fi
  echo "Suche Angebot auf bevorzugter Maschine ${PREFERRED_MACHINE_ID} ..." >&2
  local offer_id
  offer_id=$(vastai search offers "gpu_name=RTX_5090 disk_space>=40 rentable=true machine_id=${PREFERRED_MACHINE_ID}" -o 'dph_total' --raw \
    | python3 -c "import json,sys; o=json.load(sys.stdin); print(o[0]['id']) if o else None" 2>/dev/null)
  if [ -z "$offer_id" ] || [ "$offer_id" = "None" ]; then
    echo "  Maschine ${PREFERRED_MACHINE_ID} hat gerade kein Angebot -- weiche auf race.sh aus." >&2
    return 1
  fi
  echo "  Angebot $offer_id gefunden -- miete ..." >&2
  local result iid
  result=$(vastai create instance "$offer_id" --template_hash "$TEMPLATE_HASH" --disk 45 --raw 2>&1) || {
    echo "  Miete fehlgeschlagen: $result -- weiche auf race.sh aus." >&2
    return 1
  }
  iid=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('new_contract',''))" 2>/dev/null)
  if [ -z "$iid" ]; then
    echo "  Miete fehlgeschlagen: $result -- weiche auf race.sh aus." >&2
    return 1
  fi
  python3 "${SCRIPT_DIR}/machine_stats.py" record "$iid"
  echo "  Instanz $iid gemietet -- warte auf Setup (bis zu $((PREFERRED_SETUP_WAIT_SECONDS / 60)) Min.) ..." >&2
  if wait_ready "$iid" "$PREFERRED_SETUP_WAIT_SECONDS"; then
    echo "$iid"
    return 0
  fi
  echo "  $iid wurde nicht rechtzeitig bereit -- lösche und weiche auf race.sh aus." >&2
  vastai destroy instance "$iid" >/dev/null 2>&1 || true
  return 1
}

# Verwaiste, bereits laufende Instanzen mit unserem Template finden, die
# NICHT im Pool stehen -- z.B. eine race.sh-Instanz, deren Rennen ein
# vorheriger Lauf nicht sauber zu Ende brachte (Prozess abgebrochen/
# gekillt, bevor der Sieger in .instance_pool eingetragen wurde), oder eine
# von Hand über die vast.ai-Konsole gestartete Instanz. Ohne das würde eine
# bereits laufende, bezahlte Instanz nie gefunden -- get_ready_instance.sh
# würde stattdessen immer wieder neu vermieten, obwohl längst etwas
# Nutzbares existiert.
ORPHAN_IDS=()
while IFS= read -r oid; do
  [ -n "$oid" ] || continue
  skip=0
  for existing in "${POOL_IDS[@]}"; do
    [ "$existing" = "$oid" ] && skip=1 && break
  done
  [ "$skip" -eq 0 ] && ORPHAN_IDS+=("$oid")
done < <(vastai show instances-v1 --raw 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for i in d.get('instances') or []:
    if i.get('template_hash_id') == '${TEMPLATE_HASH}':
        print(i.get('id'))
" 2>/dev/null)
if [ "${#ORPHAN_IDS[@]}" -gt 0 ]; then
  echo "Verwaiste laufende Instanz(en) gefunden (nicht im Pool): ${ORPHAN_IDS[*]} -- zuerst versuchen." >&2
  POOL_IDS=("${ORPHAN_IDS[@]}" "${POOL_IDS[@]}")
fi

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
echo "Kein Pool-Kandidat war rechtzeitig einsatzbereit." >&2

WINNER=$(try_preferred_machine || true)
if [ -n "$WINNER" ]; then
  echo "$WINNER" > "${SCRIPT_DIR}/.last_instance_id"
else
  echo "Weiche auf race.sh (Neuvermietung mehrerer Kandidaten) aus." >&2
  "${SCRIPT_DIR}/race.sh" 2 >&2
  WINNER=$(cat "${SCRIPT_DIR}/.last_instance_id" 2>/dev/null)
fi

if [ -z "$WINNER" ]; then
  echo "Weder die bevorzugte Maschine noch race.sh konnten eine Instanz bereitstellen." >&2
  exit 1
fi

NEW_POOL=("$WINNER" "${TRIED_ALIVE[@]}")
printf '%s\n' "${NEW_POOL[@]:0:$MAX_POOL_SIZE}" > "$POOL_FILE"
echo "Pool aktualisiert: $(tr '\n' ' ' < "$POOL_FILE")" >&2
echo "$WINNER"
