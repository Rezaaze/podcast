#!/bin/bash
# Automatisiert eine komplette neue Staffel (3 Episoden) von der Themenidee
# bis kurz vor den manuellen Schritt (Bild/Kling/Suno erzeugen + Dateien
# nach Lolfi kopieren). Bricht bei jedem Fehler sofort ab (set -e).
#
# Nutzung:
#   ./new_series.sh "Thema/Konzept der neuen Serie"

set -e

TOPIC="$1"
if [ -z "$TOPIC" ]; then
  echo "Nutzung: ./new_series.sh \"Thema/Konzept der neuen Serie\""
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOLFI_DIR="$HOME/Downloads/Lolfi"

cd "$SCRIPT_DIR"

echo "=========================================="
echo "1/4  Neue episodes.json erzeugen"
echo "=========================================="
python3 create_series.py "$TOPIC"

echo ""
echo "=========================================="
echo "2/4  Skripte generieren + vertonen + Anthologie (automatisch verkettet)"
echo "=========================================="
python3 generate_episode.py all

echo ""
echo "=========================================="
echo "3/4  Neue Lolfi-Szene erzeugen (düster-gemütlich, nie wiederholend)"
echo "=========================================="
(cd "$LOLFI_DIR" && python3 generate_scene.py)

echo ""
echo "=========================================="
echo "4/4  Bild- + Video-Loop-Prompts für die Szene erzeugen"
echo "=========================================="
(cd "$LOLFI_DIR" && python3 generate_prompts.py --scene-file szene.txt --style lofi)

echo ""
echo "=========================================="
echo "  Automatisierung fertig — ab hier manuell:"
echo "=========================================="
echo "  1. Bild-Prompt bei einem Bildmodell erzeugen -> Grundlagebild"
echo "  2. Grundlagebild als Referenz in Kling: Loop-Prompt als 5s-Clip generieren"
echo "     -> nach ${LOLFI_DIR}/video/baseline/ kopieren"
echo "  3. Musik-Bett bei Suno erzeugen -> nach ${LOLFI_DIR}/music/ kopieren"
echo "  4. cd ${LOLFI_DIR} && python3 lofi_system.py"
