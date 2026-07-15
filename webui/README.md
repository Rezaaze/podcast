# Cockpit-WebUI

Lokales Web-Cockpit für die Podcast-Fabrik-Pipeline: Skripte per Klick
ausführen mit Live-Log, Status-Dashboard, Copy-Paste-Blöcke für die manuellen
Schritte (Claude-Serien-Prompt, Charakter-Porträt-Prompts, Anthology-Meta),
Ordner direkt im Finder öffnen.

Job-Steuerung: laufende Jobs überleben einen Browser-Reload (die Seite
verbindet sich automatisch wieder mit Log-Stream und Button-Zustand), lassen
sich über den ⏹-Button im Log-Panel abbrechen (beendet die ganze
Prozessgruppe inkl. Kindprozesse), und die langen Vertonungs-Jobs zeigen
Live-Fortschritt (Episode x/y + Chunk-Zähler aus den Checkpoints). Bei
Drama-Serien erscheint zusätzlich der Schritt "Charakter-Porträts" (Prompts
generieren → Bilder extern erzeugen → in characters/ ablegen, Status-Karte
zählt mit).

## Start (einfachster Weg)

```bash
./start_webui.sh
```

Richtet `webui/.venv` beim allerersten Mal automatisch ein, startet den
Server und öffnet den Browser automatisch, sobald er bereit ist. Anderer
Port: `WEBUI_PORT=5555 ./start_webui.sh`.

## Setup + Start manuell

```bash
cd webui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Öffnet auf `http://127.0.0.1:5151`. Voraussetzung wie beim Rest der Pipeline:
`claude` CLI eingeloggt für alle Skript-Generierungs-Schritte, das
Podcast-Fabrik-`.venv` für die Vertonung.

Läuft ausschließlich auf localhost, kein Auth — reines Single-User-Tool.
