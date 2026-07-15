#!/bin/bash
# Vertont eine komplette Serie AUF der gemieteten Instanz statt Chunk-für-
# Chunk übers Internet: Skripte + Referenz-Audio werden einmal hochgeladen,
# batch.py läuft remote gegen den Gradio-Server auf 127.0.0.1 (kein
# Internet-Hop pro Chunk mehr), danach wird nur output/ zurückgeholt.
#
# Nutzung: ./render_remote.sh <series_slug> [instance_id] [--only <epN.txt>] [--stop-after]
#          (instance_id optional -- ohne Angabe holt/wartet dieses Script
#          über get_ready_instance.sh selbst eine einsatzbereite Instanz:
#          erst der Pool fertig eingerichteter Instanzen per Resume, nur
#          falls der komplett nicht bereit wird ein race.sh-Fallback mit
#          Neuvermietung. Explizite instance_id übersteuert das.)
#          --only <datei>: nur diese eine Skript-Datei vertonen
#          (podcast_maker statt batch) -- Datei relativ zum Skript-Output
#          der Serie, z.B. "ep3.txt".
#          --stop-after: Instanz nach dem Lauf pausieren (stop.sh) --
#          auch bei Fehler, ein erneuter Aufruf resumed sie in Sekunden
#          über den Pool.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REMOTE_ROOT="/workspace/podcast-fabrik"

# vastai (pip --user) liegt in ~/.local/bin -- das WebUI spawnt dieses
# Script mit einem minimalen PATH, in dem das fehlen kann.
export PATH="${HOME}/.local/bin:${PATH}"

SERIES="$1"
if [ -z "$SERIES" ]; then
  echo "Nutzung: $0 <series_slug> [instance_id] [--only <epN.txt>] [--stop-after]"
  exit 1
fi
shift
INSTANCE_ID=""
ONLY_FILE=""
STOP_AFTER=0
LOCAL_MASTER=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only)
      ONLY_FILE="$2"
      shift 2
      ;;
    --stop-after)
      STOP_AFTER=1
      shift
      ;;
    --local-master)
      # Remote NUR vertonen (GPU), Mastering/Merge/Jingle lokal auf dem Mac:
      # spart teure Instanz-Zeit, da alles Nicht-GPU nach dem Download läuft.
      LOCAL_MASTER=1
      shift
      ;;
    *)
      INSTANCE_ID="$1"
      shift
      ;;
  esac
done
if [ -z "$INSTANCE_ID" ]; then
  echo "=== Keine Instanz-ID angegeben -- hole eine einsatzbereite Instanz (Pool/Resume, sonst race.sh-Fallback) ==="
  INSTANCE_ID="$("${SCRIPT_DIR}/get_ready_instance.sh")"
fi
if [ -z "$INSTANCE_ID" ]; then
  echo "Keine Instanz verfügbar (get_ready_instance.sh ist fehlgeschlagen)."
  echo "Nutzung: $0 <series_slug> <instance_id>"
  exit 1
fi

SERIES_DIR="${REPO_ROOT}/data/series/${SERIES}"
# MWP-Workspace-Layout (siehe fabrik/core/paths.py::EPISODES_RELPATH /
# Series.output_dir) -- NICHT die alte flache Ablage.
EPISODES_RELPATH="stages/01_concept/output/episodes.json"
OUTPUT_RELPATH="stages/03_audio/output"
EPISODES_JSON="${SERIES_DIR}/${EPISODES_RELPATH}"
if [ ! -f "$EPISODES_JSON" ]; then
  echo "FEHLER: ${EPISODES_JSON} nicht gefunden."
  exit 1
fi

# Kein Fail-Fast mehr auf audio.backend: dieser Workflow rendert IMMER remote
# gegen die Qwen3-TTS-Gradio-App der Instanz (GradioBackend) -- die REMOTE-
# Kopie von episodes.json bekommt "backend": "gradio" weiter unten automatisch
# gepatcht (wie schon api_url), unabhängig davon, was lokal eingestellt ist.
# Die lokale Datei kann damit dauerhaft auf "rest" stehen (für den lokalen
# Pinokio/Qwen3-Server, Port 42003) -- kein manuelles Hin-und-Her-Schalten
# zwischen lokalem und Cloud-Rendern mehr nötig. Voice-Auflösung (Voice-Clone
# ref_audio/ref_text bzw. Built-in-Speaker-Namen aus GradioBackend.SPEAKERS
# für Drama-Rollen) prüft podcast_maker.py ohnehin zur Laufzeit gegen den
# tatsächlichen Backend -- kein Grund, das hier vorab zu duplizieren.

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
# --timeout=60: rsync bricht ab, wenn 60s lang keine Daten fließen, statt
# unbegrenzt zu haengen. -o ConnectTimeout deckt nur den SSH-Verbindungs-
# aufbau ab, NICHT eine spaeter einschlafende Verbindung -- genau das ist
# beim echten Cloud-Betrieb schon passiert: eine Instanz blieb per SSH
# erreichbar, aber ein laufender rsync-Transfer stand minutenlang bei
# exakt derselben Byte-Zahl (0% CPU) fest, bis er von Hand gekillt wurde.
RSYNC_TIMEOUT="--timeout=60"
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
rsync -avz --delete $RSYNC_TIMEOUT -e "$RSYNC_SSH" \
  "${REPO_ROOT}/fabrik/" "${USERHOST}:${REMOTE_ROOT}/fabrik/"

echo ""
echo "=== Hochladen: templates/ (config.validate_data prüft templates/<name>/ auf Existenz) ==="
rsync -avz --delete $RSYNC_TIMEOUT -e "$RSYNC_SSH" \
  "${REPO_ROOT}/templates/" "${USERHOST}:${REMOTE_ROOT}/templates/"

ssh "${SSH_OPTS[@]}" "$USERHOST" "mkdir -p ${REMOTE_ROOT}/data/series"
if [ -n "$ONLY_FILE" ]; then
  # --only rendert eine einzelne Episode -- die bereits FERTIG gerenderten
  # Episoden-MP3s/SRT/SUBS der anderen Episoden in stages/03_audio/output/
  # werden dafür nicht gebraucht (können zusammen zig-hundert MB sein) und
  # NICHT mit hochgeladen. Alles andere (Skripte, episodes.json, Checkpoints,
  # Cues, Voice-Manifest, + bereits vorhandene Teilergebnisse GENAU dieser
  # Episode fürs Resume) geht weiterhin mit.
  TARGET_PREFIX=$(python3 -c "import os; print(os.path.splitext(os.path.basename('${ONLY_FILE}'))[0].capitalize())")
  echo ""
  echo "=== Hochladen: data/series/${SERIES}/ OHNE fertige Episoden-Audios anderer Episoden (nur ${ONLY_FILE} -> Präfix ${TARGET_PREFIX}) ==="
  rsync -avz --exclude="/stages/03_audio/output/" $RSYNC_TIMEOUT -e "$RSYNC_SSH" \
    "${SERIES_DIR}/" "${USERHOST}:${REMOTE_ROOT}/data/series/${SERIES}/"
  ssh "${SSH_OPTS[@]}" "$USERHOST" "mkdir -p ${REMOTE_ROOT}/data/series/${SERIES}/stages/03_audio/output"
  rsync -avz $RSYNC_TIMEOUT -e "$RSYNC_SSH" \
    --include=".checkpoints/***" --include=".cues/***" --include=".voices_manifest.json" \
    --include="${TARGET_PREFIX}_*" --exclude="*" \
    "${SERIES_DIR}/stages/03_audio/output/" "${USERHOST}:${REMOTE_ROOT}/data/series/${SERIES}/stages/03_audio/output/"
else
  echo ""
  echo "=== Hochladen: data/series/${SERIES}/ (inkl. bereits vorhandenem output/ -- Resume-fähig) ==="
  rsync -avz $RSYNC_TIMEOUT -e "$RSYNC_SSH" \
    "${SERIES_DIR}/" "${USERHOST}:${REMOTE_ROOT}/data/series/${SERIES}/"
fi

echo ""
echo "=== Hochladen: data/voices/ (Referenz-Audio) ==="
ssh "${SSH_OPTS[@]}" "$USERHOST" "mkdir -p ${REMOTE_ROOT}/data/voices"
rsync -avz $RSYNC_TIMEOUT -e "$RSYNC_SSH" \
  "${REPO_ROOT}/data/voices/" "${USERHOST}:${REMOTE_ROOT}/data/voices/"

echo ""
echo "=== audio.backend/api_url in der REMOTE-Kopie auf gradio/127.0.0.1:7860 umbiegen ==="
# Nur die remote Kopie wird gepatcht -- die lokale episodes.json bleibt
# unverändert (bleibt z.B. dauerhaft auf "rest" für den lokalen
# Pinokio/Qwen3-Server, Port 42003, ohne manuelles Umschalten vor jedem
# Cloud-Lauf). "backend" wird IMMER auf "gradio" gezwungen, unabhängig vom
# lokalen Wert -- dieser Workflow rendert remote ausschließlich gegen die
# Qwen3-TTS-Gradio-App der Instanz.
ssh "${SSH_OPTS[@]}" "$USERHOST" "python3 -c \"
import json
path = '${REMOTE_ROOT}/data/series/${SERIES}/${EPISODES_RELPATH}'
with open(path) as f:
    data = json.load(f)
audio = data.setdefault('audio', {})
audio['backend'] = 'gradio'
audio['api_url'] = 'http://127.0.0.1:7860'
with open(path, 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
\""

echo ""
# --local-master: remote NUR die TTS-Parts erzeugen (--skip-merge), das
# CPU-lastige Mastering/Merge/Jingle läuft nach dem Download lokal auf dem
# Mac -- so belegt nur die reine GPU-Vertonung die teure Instanz-Zeit.
SKIP_MERGE_FLAG=""
if [ "$LOCAL_MASTER" -eq 1 ]; then
  SKIP_MERGE_FLAG=" --skip-merge"
fi
if [ -n "$ONLY_FILE" ]; then
  echo "=== Vertone remote NUR ${ONLY_FILE} (podcast_maker.py)${SKIP_MERGE_FLAG:+ [nur Parts, Mastering lokal]} ==="
  REMOTE_RENDER_CMD="python3 -u -m fabrik.cli.podcast_maker ${ONLY_FILE} --series ${SERIES}${SKIP_MERGE_FLAG}"
else
  echo "=== Vertone remote (batch.py)${SKIP_MERGE_FLAG:+ [nur Parts, Mastering lokal]} ==="
  REMOTE_RENDER_CMD="python3 -u -m fabrik.cli.batch --series ${SERIES}${SKIP_MERGE_FLAG}"
fi
set +e
# PYTHONUNBUFFERED=1 (nicht nur "python3 -u" auf batch.py selbst) ist nötig,
# weil batch.py podcast_maker.py als EIGENEN Subprozess startet
# (subprocess.run([sys.executable, ...])) -- die Env-Variable vererbt sich
# an diesen Kindprozess, "-u" alleine auf dem Elternprozess nicht. Ohne das
# puffert podcast_maker.py seine prints komplett (stdout ist über SSH kein
# TTY) und im Log sieht es minutenlang aus wie eingefroren, obwohl im
# Hintergrund längst gerendert wird.
#
# Läuft im HINTERGRUND auf der Instanz (nohup + Exit-Code-Marker-Datei),
# statt den SSH-Aufruf blockierend abzuwarten: sonst liegen bei einer
# Mehr-Episoden-Serie längst fertige Episoden bis zum allerletzten Moment
# nur ungenutzt auf der Instanz -- ein Verbindungsabbruch kurz vor Ende
# würfe sie alle weg, weil noch nichts heruntergeladen wäre. Der Poll-Loop
# unten holt stattdessen schon während der laufenden Generierung ab, was
# fertig ist (Best-Effort, "|| true" -- der finale Download-Block weiter
# unten mit seinen 3 Versuchen bleibt die verbindliche, robuste Instanz).
REMOTE_LOG="${REMOTE_ROOT}/.render.log"
REMOTE_DONE="${REMOTE_ROOT}/.render_done"
# </dev/null ist Pflicht, nicht nur >/dev/null 2>&1: ssh schließt die
# Verbindung erst, wenn ALLE Filedeskriptoren des Remote-Kommandos (auch
# STDIN) geschlossen sind. UND: "cd X && nohup ... &" reicht dafür NICHT --
# bash backgroundet dabei die GANZE "cd && nohup"-Kette in einer impliziten
# Subshell, und genau DIESE Subshell hält noch die ursprüngliche STDIN der
# SSH-Sitzung offen (das </dev/null sitzt nur auf dem inneren nohup-Befehl,
# zu spät). Live gemessen: mit "cd &&" davor bleibt die SSH-Verbindung bis
# zum Ende des Hintergrundjobs offen (14s bei einem 10s-Testjob statt der
# üblichen ~4-5s reiner Verbindungsaufbau); OHNE das cd-Präfix (cd stattdessen
# INNERHALB des bash -c) kehrt sie sofort zurück, exakt wie erwartet. Deshalb
# hier bewusst nur EIN einziges "nohup bash -c '...' &" auf oberster Ebene,
# cd als erster Befehl innerhalb des bash -c-Strings statt davor.
ssh "${SSH_OPTS[@]}" "$USERHOST" "rm -f '${REMOTE_LOG}' '${REMOTE_DONE}'; nohup bash -c 'cd \"${REMOTE_ROOT}\" && PYTHONUNBUFFERED=1 ${REMOTE_RENDER_CMD} > \"${REMOTE_LOG}\" 2>&1; echo \$? > \"${REMOTE_DONE}\"' </dev/null >/dev/null 2>&1 & disown"
LAUNCH_EXIT=$?
if [ "$LAUNCH_EXIT" -ne 0 ]; then
  echo "FEHLER: Remote-Render konnte nicht gestartet werden (SSH-Verbindung fehlgeschlagen)."
  exit 1
fi

echo "=== Remote-Render läuft im Hintergrund -- lade fertige Episoden bereits jetzt zwischendurch ab ==="
POLL_SECONDS=30
LAST_TAIL_LINE=0
while true; do
  # Best-Effort-Zwischen-Download: Fehler hier sind nie fatal, der finale
  # Block unten holt am Ende ohnehin noch mal alles ab.
  rsync -avz $RSYNC_TIMEOUT -e "$RSYNC_SSH" \
    "${USERHOST}:${REMOTE_ROOT}/data/series/${SERIES}/${OUTPUT_RELPATH}/" "${SERIES_DIR}/${OUTPUT_RELPATH}/" \
    >/dev/null 2>&1 || true

  # Neue Log-Zeilen seit dem letzten Check zeigen, damit das WebUI-Log nicht
  # wie eingefroren aussieht, während im Hintergrund gerendert wird.
  NEW_LOG=$(ssh "${SSH_OPTS[@]}" "$USERHOST" "tail -n +$((LAST_TAIL_LINE + 1)) '${REMOTE_LOG}' 2>/dev/null" 2>/dev/null)
  if [ -n "$NEW_LOG" ]; then
    echo "$NEW_LOG"
    LAST_TAIL_LINE=$((LAST_TAIL_LINE + $(printf '%s\n' "$NEW_LOG" | wc -l)))
  fi

  DONE_CONTENT=$(ssh "${SSH_OPTS[@]}" "$USERHOST" "cat '${REMOTE_DONE}' 2>/dev/null")
  if [ -n "$DONE_CONTENT" ]; then
    BATCH_EXIT="$DONE_CONTENT"
    break
  fi
  sleep "$POLL_SECONDS"
done
set -e

echo ""
echo "=== Ergebnisse zurückholen: ${OUTPUT_RELPATH}/ ==="
mkdir -p "${SERIES_DIR}/${OUTPUT_RELPATH}"
# Remote output/ existiert evtl. noch nicht (z.B. wenn batch.py schon an der
# Config-Validierung scheiterte, vor series.ensure_dirs()) -- das ist dann
# kein zusätzlicher Fehler, nur nichts zum Zurückholen.
if ssh "${SSH_OPTS[@]}" "$USERHOST" "[ -d ${REMOTE_ROOT}/data/series/${SERIES}/${OUTPUT_RELPATH} ]"; then
  # Bis zu 3 Versuche: eine bereits fertig gerenderte Episode ist die
  # teuerste Sache in diesem ganzen Lauf (GPU-Minuten schon bezahlt) --
  # ein einzelner Verbindungsabbruch/Timeout beim Download darf sie nicht
  # kommentarlos verwerfen. rsync OHNE --partial: ein abgebrochener Versuch
  # lässt keine kaputte Datei unter dem finalen Namen liegen (Halbdateien
  # landen nur in einer verworfenen .tmp-Datei), ein Retry beginnt die
  # betroffene Datei also sauber neu statt eine Halbdatei fortzusetzen.
  DOWNLOAD_OK=0
  for attempt in 1 2 3; do
    if rsync -avz $RSYNC_TIMEOUT -e "$RSYNC_SSH" \
      "${USERHOST}:${REMOTE_ROOT}/data/series/${SERIES}/${OUTPUT_RELPATH}/" "${SERIES_DIR}/${OUTPUT_RELPATH}/"; then
      DOWNLOAD_OK=1
      break
    fi
    echo "WARNUNG: Download-Versuch ${attempt}/3 fehlgeschlagen (Verbindung abgebrochen/Timeout)."
    [ "$attempt" -lt 3 ] && { echo "  Erneuter Versuch in 10s ..."; sleep 10; }
  done
  if [ "$DOWNLOAD_OK" -ne 1 ]; then
    echo "FEHLER: Download nach 3 Versuchen fehlgeschlagen. Die fertig gerenderten Daten"
    echo "  liegen weiter auf ${USERHOST}:${REMOTE_ROOT}/data/series/${SERIES}/${OUTPUT_RELPATH}/"
    echo "  -- erneuter Aufruf von $0 ${SERIES} ${INSTANCE_ID}${ONLY_FILE:+ --only $ONLY_FILE} versucht"
    echo "  NUR den Download erneut (Rendern wird übersprungen, da bereits fertig)."
    # Absichtlich KEIN sofortiges exit hier -- --stop-after (falls gesetzt)
    # soll die Instanz trotzdem pausieren, statt wegen eines reinen
    # Download-Fehlers unnötig weiterzulaufen und Geld zu kosten. Der
    # Non-Zero-Exit kommt weiter unten, NACH dem Stop-Versuch.
    DOWNLOAD_FAILED=1
  fi
else
  echo "(kein Remote-output/ vorhanden -- nichts zurückzuholen)"
fi

if [ "$STOP_AFTER" -eq 1 ]; then
  echo ""
  echo "=== Instanz ${INSTANCE_ID} pausieren (--stop-after) ==="
  # Fehler beim Stoppen nicht zum Render-Fehler machen -- der Lauf selbst
  # ist ja durch, notfalls manuell cloud/stop.sh nachschieben.
  "${SCRIPT_DIR}/stop.sh" "$INSTANCE_ID" || echo "WARNUNG: stop.sh fehlgeschlagen -- Instanz läuft (und kostet) weiter!"
fi

if [ "${DOWNLOAD_FAILED:-0}" -eq 1 ]; then
  exit 1
fi

LOCAL_MASTER_EXIT=0
if [ "$LOCAL_MASTER" -eq 1 ]; then
  echo ""
  echo "=== Lokales Mastering auf dem Mac (--local-master) ==="
  # Die Instanz ist zu diesem Zeitpunkt schon pausiert (falls --stop-after) --
  # Mastering/Merge/Jingle brauchen keine GPU und laufen komplett lokal, ohne
  # dass die Instanz-Uhr weiterläuft.
  LOCAL_PY="${REPO_ROOT}/.venv/bin/python"
  if [ ! -x "$LOCAL_PY" ]; then
    echo "FEHLER: ${LOCAL_PY} nicht gefunden -- lokales venv (pydub/pyloudnorm/ffmpeg) nötig."
    echo "  Die Part-WAVs liegen in ${SERIES_DIR}/${OUTPUT_RELPATH}/ -- manuell fertigstellen mit:"
    if [ -n "$ONLY_FILE" ]; then
      echo "    .venv/bin/python -m fabrik.cli.podcast_maker ${ONLY_FILE} --series ${SERIES} --merge-only"
    else
      echo "    .venv/bin/python -m fabrik.cli.batch --series ${SERIES} --merge-only"
    fi
    exit 1
  fi
  if [ -n "$ONLY_FILE" ]; then
    ( cd "$REPO_ROOT" && "$LOCAL_PY" -m fabrik.cli.podcast_maker "$ONLY_FILE" --series "$SERIES" --merge-only )
  else
    ( cd "$REPO_ROOT" && "$LOCAL_PY" -m fabrik.cli.batch --series "$SERIES" --merge-only )
  fi
  LOCAL_MASTER_EXIT=$?
  if [ "$LOCAL_MASTER_EXIT" -ne 0 ]; then
    echo "WARNUNG: Lokales Mastering mit Fehler beendet (Exit ${LOCAL_MASTER_EXIT}) --"
    echo "  Part-WAVs liegen in ${SERIES_DIR}/${OUTPUT_RELPATH}/, erneut mit --merge-only mastern."
  fi
fi

if [ "$BATCH_EXIT" -ne 0 ]; then
  echo ""
  echo "WARNUNG: Remote-Vertonung mit Fehler beendet (Exit ${BATCH_EXIT})."
  echo "  Teilergebnisse/Checkpoints wurden trotzdem zurückgeholt -- $0 ${SERIES} ${INSTANCE_ID} erneut"
  echo "  ausführen, um fortzusetzen (bereits fertige Episoden/Parts werden übersprungen)."
  exit "$BATCH_EXIT"
fi

if [ "$LOCAL_MASTER_EXIT" -ne 0 ]; then
  exit "$LOCAL_MASTER_EXIT"
fi

echo ""
if [ "$LOCAL_MASTER" -eq 1 ]; then
  echo "Fertig -- remote vertont, lokal gemastert. Ergebnisse in ${SERIES_DIR}/${OUTPUT_RELPATH}/"
else
  echo "Fertig -- Ergebnisse liegen in ${SERIES_DIR}/${OUTPUT_RELPATH}/"
fi
