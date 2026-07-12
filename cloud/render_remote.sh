#!/bin/bash
# Vertont eine komplette Serie AUF der gemieteten Instanz statt Chunk-für-
# Chunk übers Internet: Skripte + Referenz-Audio werden einmal hochgeladen,
# batch.py läuft remote gegen den Gradio-Server auf 127.0.0.1 (kein
# Internet-Hop pro Chunk mehr), danach wird nur output/ zurückgeholt.
#
# Nutzung: ./render_remote.sh <series_slug> [instance_id]
#          (instance_id optional -- Fallback wie bei den anderen Scripts:
#          die zuletzt mit rent.sh gemietete Instanz aus .last_instance_id)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REMOTE_ROOT="/workspace/podcast-fabrik"

SERIES="$1"
if [ -z "$SERIES" ]; then
  echo "Nutzung: $0 <series_slug> [instance_id]"
  exit 1
fi
INSTANCE_ID="${2:-$(cat "${SCRIPT_DIR}/.last_instance_id" 2>/dev/null)}"
if [ -z "$INSTANCE_ID" ]; then
  echo "Keine Instanz-ID angegeben und keine .last_instance_id gefunden."
  echo "Nutzung: $0 <series_slug> <instance_id>"
  exit 1
fi

SERIES_DIR="${REPO_ROOT}/data/series/${SERIES}"
EPISODES_JSON="${SERIES_DIR}/episodes.json"
if [ ! -f "$EPISODES_JSON" ]; then
  echo "FEHLER: ${EPISODES_JSON} nicht gefunden."
  exit 1
fi

# Fail-fast statt das Backend stillschweigend umzubiegen: dieser Workflow
# rendert remote gegen die Qwen3-TTS-Gradio-App der Instanz (GradioBackend) --
# sowohl narration (Voice Clone) als auch drama (Custom-Voice-Rollen aus
# GradioBackend.SPEAKERS) sind darüber möglich.
BACKEND=$(python3 -c "import json; print(json.load(open('${EPISODES_JSON}')).get('audio', {}).get('backend', 'rest'))")
if [ "$BACKEND" != "gradio" ]; then
  echo "FEHLER: audio.backend in ${EPISODES_JSON} ist '${BACKEND}', nicht 'gradio'."
  echo "  Dieser Workflow rendert remote gegen den Qwen3-TTS-Gradio-Server der Instanz --"
  echo "  dafür muss episodes.json bereits 'audio.backend: \"gradio\"' haben (+ ref_audio/ref_text für"
  echo "  Voice-Clone-Rollen, bzw. Built-in-Speaker-Namen aus GradioBackend.SPEAKERS für Drama-Rollen)."
  exit 1
fi

echo "=== SSH-Ziel für Instanz ${INSTANCE_ID} auflösen ==="
SSH_URL=$(vastai ssh-url "$INSTANCE_ID" 2>/dev/null)
if [ -z "$SSH_URL" ]; then
  echo "FEHLER: SSH-URL nicht verfügbar -- ist die Instanz gestartet? (cloud/status.sh prüfen)"
  exit 1
fi
# ssh://user@host:port -> user@host + port getrennt, weil rsync -e "ssh -p ..."
# eine reine user@host-Zieladresse braucht (kein ssh://-Schema).
HOSTPART="${SSH_URL#ssh://}"
USERHOST="${HOSTPART%:*}"
PORT="${HOSTPART##*:}"
SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$PORT")
RSYNC_SSH="ssh -p ${PORT} -o StrictHostKeyChecking=no -o ConnectTimeout=10"
echo "Ziel: ${USERHOST}:${PORT}"

echo ""
echo "=== Remote-Python-Abhängigkeiten prüfen (pydub, numpy, pyloudnorm, requests) ==="
ssh "${SSH_OPTS[@]}" "$USERHOST" "
  mkdir -p ${REMOTE_ROOT}
  if ! python3 -c 'import pydub, numpy, pyloudnorm, requests' 2>/dev/null; then
    echo 'Installiere fehlende Pakete ...'
    # uv statt pip (wie onstart_qwen3_tts.sh) -- umgeht 'externally-managed-
    # environment'-Fehler, den plain pip auf manchen Debian-Base-Images wirft.
    pip install --upgrade pip uv -q
    uv pip install --system -q pydub numpy pyloudnorm requests
  else
    echo 'Bereits vorhanden.'
  fi
"

echo ""
echo "=== Hochladen: fabrik/ (Code) ==="
rsync -avz --delete -e "$RSYNC_SSH" \
  "${REPO_ROOT}/fabrik/" "${USERHOST}:${REMOTE_ROOT}/fabrik/"

echo ""
echo "=== Hochladen: templates/ (config.validate_data prüft templates/<name>/ auf Existenz) ==="
rsync -avz --delete -e "$RSYNC_SSH" \
  "${REPO_ROOT}/templates/" "${USERHOST}:${REMOTE_ROOT}/templates/"

echo ""
echo "=== Hochladen: data/series/${SERIES}/ (inkl. bereits vorhandenem output/ -- Resume-fähig) ==="
ssh "${SSH_OPTS[@]}" "$USERHOST" "mkdir -p ${REMOTE_ROOT}/data/series"
rsync -avz -e "$RSYNC_SSH" \
  "${SERIES_DIR}/" "${USERHOST}:${REMOTE_ROOT}/data/series/${SERIES}/"

echo ""
echo "=== Hochladen: data/voices/ (Referenz-Audio) ==="
ssh "${SSH_OPTS[@]}" "$USERHOST" "mkdir -p ${REMOTE_ROOT}/data/voices"
rsync -avz -e "$RSYNC_SSH" \
  "${REPO_ROOT}/data/voices/" "${USERHOST}:${REMOTE_ROOT}/data/voices/"

echo ""
echo "=== audio.api_url in der REMOTE-Kopie auf 127.0.0.1:7860 umbiegen ==="
# Nur die remote Kopie wird gepatcht -- die lokale episodes.json bleibt
# unverändert (sie behält ihre öffentliche Adresse für den alten Direkt-Weg).
ssh "${SSH_OPTS[@]}" "$USERHOST" "python3 -c \"
import json
path = '${REMOTE_ROOT}/data/series/${SERIES}/episodes.json'
with open(path) as f:
    data = json.load(f)
data.setdefault('audio', {})['api_url'] = 'http://127.0.0.1:7860'
with open(path, 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
\""

echo ""
echo "=== Vertone remote (batch.py) -- läuft komplett lokal auf der Instanz ==="
set +e
# PYTHONUNBUFFERED=1 (nicht nur "python3 -u" auf batch.py selbst) ist nötig,
# weil batch.py podcast_maker.py als EIGENEN Subprozess startet
# (subprocess.run([sys.executable, ...])) -- die Env-Variable vererbt sich
# an diesen Kindprozess, "-u" alleine auf dem Elternprozess nicht. Ohne das
# puffert podcast_maker.py seine prints komplett (stdout ist über SSH kein
# TTY) und im Log sieht es minutenlang aus wie eingefroren, obwohl im
# Hintergrund längst gerendert wird.
ssh "${SSH_OPTS[@]}" "$USERHOST" "cd ${REMOTE_ROOT} && PYTHONUNBUFFERED=1 python3 -u -m fabrik.cli.batch --series ${SERIES}"
BATCH_EXIT=$?
set -e

echo ""
echo "=== Ergebnisse zurückholen: output/ ==="
mkdir -p "${SERIES_DIR}/output"
# Remote output/ existiert evtl. noch nicht (z.B. wenn batch.py schon an der
# Config-Validierung scheiterte, vor series.ensure_dirs()) -- das ist dann
# kein zusätzlicher Fehler, nur nichts zum Zurückholen.
if ssh "${SSH_OPTS[@]}" "$USERHOST" "[ -d ${REMOTE_ROOT}/data/series/${SERIES}/output ]"; then
  rsync -avz -e "$RSYNC_SSH" \
    "${USERHOST}:${REMOTE_ROOT}/data/series/${SERIES}/output/" "${SERIES_DIR}/output/"
else
  echo "(kein Remote-output/ vorhanden -- nichts zurückzuholen)"
fi

if [ "$BATCH_EXIT" -ne 0 ]; then
  echo ""
  echo "WARNUNG: batch.py ist remote mit Fehler beendet (Exit ${BATCH_EXIT})."
  echo "  Teilergebnisse/Checkpoints wurden trotzdem zurückgeholt -- $0 ${SERIES} ${INSTANCE_ID} erneut"
  echo "  ausführen, um fortzusetzen (bereits fertige Episoden/Parts werden übersprungen)."
  exit "$BATCH_EXIT"
fi

echo ""
echo "Fertig -- Ergebnisse liegen in ${SERIES_DIR}/output/"
