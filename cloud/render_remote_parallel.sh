#!/bin/bash
# Vertont mehrere fehlende Episoden einer Serie PARALLEL auf mehreren
# vast.ai-Instanzen: eine render_remote.sh --only <epN.txt>-Instanz pro
# Episode, gleichzeitig gestartet. Episoden werden in Wellen zu je --max
# Instanzen abgearbeitet, bis keine mehr fehlt.
#
# WICHTIG: Die Instanzen werden nur EINMAL zu Beginn beschafft und über
# ALLE Wellen hinweg wiederverwendet (nicht pro Welle neu gemietet) -- bei
# z.B. 10 fehlenden Episoden und --max 3 (4 Wellen: 3+3+3+1) würden sonst
# Ad-hoc-Instanzen bis zu 4x den vollen Setup-/Modell-Warmup-Aufwand
# (5-15 Min. PRO Instanz) durchlaufen, nur um jeweils eine einzige Episode
# zu rendern. So läuft der Setup-Aufwand nur einmal pro Instanz, danach
# wird sie Welle für Welle mit der jeweils nächsten Episode neu gefüttert.
#
# Instanzbeschaffung (einmalig zu Beginn):
#   1. Bereits vorgewärmte Instanzen aus .instance_pool per Resume --
#      bleiben Teil des dauerhaften Pools, werden am ENDE nur pausiert
#      (stop.sh).
#   2. Fehlende Slots werden ZUSÄTZLICH gemietet (bevorzugt bekannt
#      zuverlässige Hosts, siehe race_pick_offers.py) -- diese Ad-hoc-
#      Instanzen sind NICHT Teil des dauerhaften Pools und werden am ENDE
#      wieder GELÖSCHT (destroy), damit keine Storage-Kosten für Instanzen
#      liegen bleiben, die nur für diesen einen Parallel-Batch gemietet
#      wurden. Gesamtkosten bleiben dadurch nahe an "gleiche GPU-Minuten
#      wie sequenziell", nur auf weniger Wanduhrzeit verteilt -- siehe
#      cloud/README.md.
#
# Fällt eine Instanz zwischen zwei Wellen aus (verschwindet z.B. komplett,
# siehe cloud/README.md "Manche Hosts scheitern..."), wird sie aus dem
# aktiven Arbeits-Set entfernt (nicht mehr für weitere Wellen genutzt) und
# ihre gerade unvollendete Episode kommt zurück vorn in die Warteschlange
# -- die verbleibenden Instanzen übernehmen sie in der nächsten Welle.
#
# Nutzung: ./render_remote_parallel.sh <series_slug> [--max N] [--episodes ep6.txt,ep7.txt,...]
#          --max (Standard 3): wie viele Instanzen gleichzeitig laufen dürfen.
#          --episodes: explizite Liste statt automatischer Erkennung
#          fehlender Episoden (Skript vorhanden, aber keine
#          <Prefix>_FULL_EPISODE.mp3 in stages/03_audio/output/).
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# vastai (pip --user) liegt in ~/.local/bin -- kann in minimalen
# Subprocess-PATHs (z.B. WebUI-Job) fehlen.
export PATH="${HOME}/.local/bin:${PATH}"
TEMPLATE_HASH="c2352e9ebc56ffd4b83b51c6d229363a"

python3 "${SCRIPT_DIR}/machine_stats.py" reconcile

SERIES="$1"
if [ -z "$SERIES" ]; then
  echo "Nutzung: $0 <series_slug> [--max N] [--episodes ep6.txt,ep7.txt,...]"
  exit 1
fi
shift
MAX_PARALLEL=3
EPISODES_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --max)
      MAX_PARALLEL="$2"
      shift 2
      ;;
    --episodes)
      EPISODES_ARG="$2"
      shift 2
      ;;
    *)
      echo "Unbekanntes Argument: $1"
      exit 1
      ;;
  esac
done

SERIES_DIR="${REPO_ROOT}/data/series/${SERIES}"
SCRIPTS_DIR="${SERIES_DIR}/stages/02_scripts/output"
OUTPUT_DIR="${SERIES_DIR}/stages/03_audio/output"
if [ ! -d "$SCRIPTS_DIR" ]; then
  echo "FEHLER: ${SCRIPTS_DIR} nicht gefunden."
  exit 1
fi

MISSING=()
if [ -n "$EPISODES_ARG" ]; then
  IFS=',' read -ra MISSING <<< "$EPISODES_ARG"
else
  while IFS= read -r fname; do
    MISSING+=("$fname")
  done < <(python3 -c "
import os, re
scripts_dir = '${SCRIPTS_DIR}'
output_dir = '${OUTPUT_DIR}'
pat = re.compile(r'^[A-Za-z]+\d+\.txt\$')
for fname in sorted(os.listdir(scripts_dir)):
    if not pat.match(fname):
        continue
    stem = os.path.splitext(fname)[0]
    prefix = stem.capitalize()  # muss identisch zu podcast_maker.py/batch.py::episode_name_from_file sein
    mp3 = os.path.join(output_dir, f'{prefix}_FULL_EPISODE.mp3')
    if not os.path.exists(mp3):
        print(fname)
")
fi

if [ "${#MISSING[@]}" -eq 0 ]; then
  echo "Keine fehlenden Episoden -- alles bereits vertont."
  exit 0
fi

echo "Fehlende Episoden (${#MISSING[@]}): ${MISSING[*]}"
echo "Max. parallele Instanzen: ${MAX_PARALLEL}"

POOL_FILE="${SCRIPT_DIR}/.instance_pool"
touch "$POOL_FILE"

is_ready() {
  # Direkt pipen statt über eine Bash-Variable umleiten -- siehe
  # get_ready_instance.sh für die Begründung (großes 'onstart'-Feld
  # übersteht den Variable/echo-Umweg nicht zuverlässig, macht is_ready()
  # sonst lautlos permanent blind).
  local iid="$1" url
  url=$(vastai show instances-v1 --raw 2>/dev/null \
    | python3 "${SCRIPT_DIR}/get_gradio_url.py" "$iid" 2>/dev/null) || return 1
  [ -n "$url" ] && curl -sf -o /dev/null -m 10 "$url"
}

wait_ready() {
  local iid="$1" rounds=60 i
  for i in $(seq 1 "$rounds"); do
    is_ready "$iid" && return 0
    sleep 15
  done
  return 1
}

# ============================================================
# Phase 1: Instanzen EINMALIG beschaffen (Pool-Resume + Ad-hoc-Miete bis
# max_parallel), Ergebnis ist das feste Arbeits-Set für alle Wellen.
# ALL_IDS/ALL_ADHOC = vollständige Roster-Historie für die Endaufräumung
# (auch Instanzen, die später als "tot" aus ACTIVE_IDS fliegen, müssen am
# Ende noch gestoppt/gelöscht werden).
# ============================================================
WAVE_SIZE_CAP="$MAX_PARALLEL"
[ "${#MISSING[@]}" -lt "$WAVE_SIZE_CAP" ] && WAVE_SIZE_CAP="${#MISSING[@]}"

echo ""
echo "=== Instanzen beschaffen (Ziel: ${WAVE_SIZE_CAP}) ==="
ALL_IDS=()
ALL_ADHOC=()
POOL_IDS=()
while IFS= read -r line; do
  [ -n "$line" ] && POOL_IDS+=("$line")
done < "$POOL_FILE"

for IID in "${POOL_IDS[@]}"; do
  [ "${#ALL_IDS[@]}" -ge "$WAVE_SIZE_CAP" ] && break
  echo "Resume Pool-Instanz ${IID} ..."
  vastai start instance "$IID" >/dev/null 2>&1 || true
  ALL_IDS+=("$IID")
  ALL_ADHOC+=("0")
done

NEED_MORE=$((WAVE_SIZE_CAP - ${#ALL_IDS[@]}))
if [ "$NEED_MORE" -gt 0 ]; then
  echo "Miete ${NEED_MORE} zusätzliche Ad-hoc-Instanz(en) ..."
  while IFS= read -r OFFER_ID; do
    [ -z "$OFFER_ID" ] && continue
    RESULT=$(vastai create instance "$OFFER_ID" --template_hash "$TEMPLATE_HASH" --disk 45 --raw 2>&1) || continue
    IID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('new_contract',''))" 2>/dev/null)
    [ -n "$IID" ] || continue
    echo "  -> Ad-hoc-Instanz ${IID}"
    python3 "${SCRIPT_DIR}/machine_stats.py" record "$IID"
    ALL_IDS+=("$IID")
    ALL_ADHOC+=("1")
  done < <(vastai search offers 'gpu_name=RTX_5090 disk_space>=40 reliability>0.98 verified=true rentable=true inet_down>1000 inet_up>1000 geolocation in [PL,CZ,SK,HU,RO,BG,EE,LV,LT,UA,MD]' -o 'dph_total' --raw 2>/dev/null \
    | python3 "${SCRIPT_DIR}/race_pick_offers.py" "$NEED_MORE")
fi

if [ "${#ALL_IDS[@]}" -eq 0 ]; then
  echo "FEHLER: Keine Instanz verfügbar -- breche ab."
  exit 1
fi

echo "Warte, bis alle ${#ALL_IDS[@]} Instanz(en) bereit sind (bis zu 15 Min. pro Instanz) ..."
ACTIVE_IDS=()
ACTIVE_ADHOC=()
for i in "${!ALL_IDS[@]}"; do
  IID="${ALL_IDS[$i]}"
  if wait_ready "$IID"; then
    echo "  ${IID} bereit."
    ACTIVE_IDS+=("$IID")
    ACTIVE_ADHOC+=("${ALL_ADHOC[$i]}")
  else
    echo "  WARNUNG: Instanz ${IID} wurde nicht rechtzeitig bereit -- bleibt für spätere Aufräumung vorgemerkt, wird aber nicht zum Rendern genutzt."
  fi
done

if [ "${#ACTIVE_IDS[@]}" -eq 0 ]; then
  echo "FEHLER: Keine Instanz wurde bereit -- breche ab (Roster wird trotzdem aufgeräumt)."
fi

# ============================================================
# Phase 2: Wellen -- dasselbe ACTIVE_IDS-Set wird wiederverwendet, bis die
# Episoden-Warteschlange leer ist oder keine aktive Instanz mehr übrig ist.
# ============================================================
QUEUE=("${MISSING[@]}")
FAILED_CONTENT=()

while [ "${#QUEUE[@]}" -gt 0 ] && [ "${#ACTIVE_IDS[@]}" -gt 0 ]; do
  WAVE_N="${#ACTIVE_IDS[@]}"
  [ "${#QUEUE[@]}" -lt "$WAVE_N" ] && WAVE_N="${#QUEUE[@]}"
  WAVE=("${QUEUE[@]:0:$WAVE_N}")
  QUEUE=("${QUEUE[@]:$WAVE_N}")

  echo ""
  echo "=== Welle: ${WAVE[*]} (auf ${ACTIVE_IDS[*]:0:$WAVE_N}) ==="

  PIDS=()
  STATUS_FILES=()
  for i in "${!WAVE[@]}"; do
    EP="${WAVE[$i]}"
    IID="${ACTIVE_IDS[$i]}"
    STATUS_FILE=$(mktemp)
    STATUS_FILES+=("$STATUS_FILE")
    (
      "${SCRIPT_DIR}/render_remote.sh" "$SERIES" "$IID" --only "$EP" 2>&1 \
        | while IFS= read -r line; do echo "[${EP}@${IID}] ${line}"; done
      echo "${PIPESTATUS[0]}" > "$STATUS_FILE"
    ) &
    PIDS+=("$!")
  done

  for PID in "${PIDS[@]}"; do
    wait "$PID"
  done

  # -- Auswertung: tote Instanzen aus ACTIVE_IDS entfernen (Episode zurück
  # in die Queue), lebendige Instanzen bleiben für die nächste Welle aktiv.
  NEW_ACTIVE_IDS=()
  NEW_ACTIVE_ADHOC=()
  RETRY_EPS=()
  for i in "${!WAVE[@]}"; do
    EP="${WAVE[$i]}"
    IID="${ACTIVE_IDS[$i]}"
    ADHOC="${ACTIVE_ADHOC[$i]}"
    CODE=$(cat "${STATUS_FILES[$i]}" 2>/dev/null || echo 1)
    rm -f "${STATUS_FILES[$i]}"
    if [ "$CODE" = "0" ]; then
      NEW_ACTIVE_IDS+=("$IID")
      NEW_ACTIVE_ADHOC+=("$ADHOC")
      continue
    fi
    if is_ready "$IID"; then
      echo "WARNUNG: ${EP} auf Instanz ${IID} mit Fehler beendet (Exit ${CODE}), Instanz aber noch erreichbar -- inhaltlicher Fehler, kein Instanz-Ausfall. Nicht automatisch retried."
      FAILED_CONTENT+=("$EP")
      NEW_ACTIVE_IDS+=("$IID")
      NEW_ACTIVE_ADHOC+=("$ADHOC")
    else
      echo "WARNUNG: Instanz ${IID} nach ${EP} nicht mehr erreichbar -- gilt als ausgefallen, wird aus dem Arbeits-Set entfernt. ${EP} kommt zurück in die Warteschlange."
      RETRY_EPS+=("$EP")
    fi
  done
  # Instanzen, die NICHT in dieser Welle liefen (weil ACTIVE_IDS > WAVE_N
  # nie vorkommt hier, da WAVE_N = min(#QUEUE,#ACTIVE_IDS) -- alle aktiven
  # Instanzen laufen in jeder Welle mit, kein Sonderfall nötig).
  ACTIVE_IDS=("${NEW_ACTIVE_IDS[@]}")
  ACTIVE_ADHOC=("${NEW_ACTIVE_ADHOC[@]}")
  if [ "${#RETRY_EPS[@]}" -gt 0 ]; then
    QUEUE=("${RETRY_EPS[@]}" "${QUEUE[@]}")
  fi
done

if [ "${#QUEUE[@]}" -gt 0 ]; then
  echo ""
  echo "WARNUNG: ${#QUEUE[@]} Episode(n) konnten nicht gerendert werden (keine aktive Instanz mehr übrig): ${QUEUE[*]}"
  echo "  Erneuter Aufruf von $0 versucht sie automatisch erneut."
fi

# ============================================================
# Phase 3: Einmalige Aufräumung am Ende -- über das VOLLSTÄNDIGE Roster
# (ALL_IDS), nicht nur die zuletzt noch aktiven, damit auch zwischenzeitlich
# ausgefallene Instanzen sauber behandelt werden (destroy auf einer bereits
# verschwundenen Instanz schlägt harmlos fehl, siehe Warnung unten).
# ============================================================
echo ""
echo "=== Instanzen aufräumen ==="
for i in "${!ALL_IDS[@]}"; do
  IID="${ALL_IDS[$i]}"
  ADHOC="${ALL_ADHOC[$i]}"
  if [ "$ADHOC" = "1" ]; then
    echo "Lösche Ad-hoc-Instanz ${IID} ..."
    vastai destroy instance "$IID" -y >/dev/null 2>&1 || echo "  WARNUNG: Löschen fehlgeschlagen (evtl. schon weg) -- manuell prüfen (cloud/status.sh ${IID})."
  else
    echo "Pausiere Pool-Instanz ${IID} ..."
    "${SCRIPT_DIR}/stop.sh" "$IID" || echo "  WARNUNG: Pausieren fehlgeschlagen -- manuell prüfen (cloud/status.sh ${IID})."
  fi
done

if [ "${#FAILED_CONTENT[@]}" -gt 0 ]; then
  echo ""
  echo "Episoden mit inhaltlichem Renderfehler (Instanz war erreichbar, Job aber fehlgeschlagen): ${FAILED_CONTENT[*]}"
  echo "  Log/episodes.json prüfen, dann erneut aufrufen."
fi

echo ""
echo "Fertig."
