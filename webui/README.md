# Cockpit-WebUI

Lokales Web-Cockpit für beide Pipelines (Podcast-Fabrik + Lolfi): Skripte per
Klick ausführen mit Live-Log, Status-Dashboard, Copy-Paste-Blöcke für die
manuellen Schritte (Claude-Serien-Prompt, Lolfi-Bild/Kling/Suno-Prompts,
Anthology-Meta), Ordner direkt im Finder öffnen.

## Setup (einmalig)

```bash
cd webui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Start

```bash
webui/.venv/bin/python webui/app.py
```

Öffnet auf `http://127.0.0.1:5151`. Voraussetzung wie beim Rest der Pipeline:
`claude` CLI eingeloggt für alle Skript-Generierungs-Schritte, die venvs der
Einzelprojekte (`Podcast-Fabrik/.venv`, `Lolfi/.venv`) für Vertonung/Render.

Läuft ausschließlich auf localhost, kein Auth — reines Single-User-Tool.
