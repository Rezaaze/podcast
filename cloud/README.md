# Cloud-GPU (vast.ai) — RTX 5090 mieten statt auf dem Laptop vertonen

Vertont die bereits generierten Skripte (`figur1.txt`, `figur2.txt`, ...)
massiv schneller, indem die eigentliche TTS-Berechnung an eine gemietete
RTX 5090 auf [vast.ai](https://vast.ai) ausgelagert wird — über den bereits
vorhandenen `GradioBackend` in [`tts_backends.py`](../fabrik/audio/tts_backends.py).

Empfohlen: **`render_remote.sh`** lädt Skripte + Referenz-Audio einmal auf
die Instanz hoch und lässt `batch.py` dort **komplett remote** laufen (gegen
den Gradio-Server auf `127.0.0.1`) — kein Internet-Hop mehr pro TTS-Chunk,
nur Skripte hoch + fertige Episoden runter (siehe Workflow-Schritt 4).
Alternativ (z.B. für einen schnellen Konnektivitätstest vor einem großen
Lauf) kann `podcast_maker.py`/`batch.py` weiterhin lokal auf dem Mac laufen
und direkt gegen die öffentliche Adresse der Instanz sprechen — dann geht
aber jeder einzelne Chunk übers Internet (siehe "Alter Direkt-Weg" unten).

Es wird **kein eigenes Docker-Image gebaut** (dafür fehlt auf dem MacBook der
Plattenplatz). Stattdessen: ein Stock-PyTorch-Image + ein Onstart-Script, das
beim allerersten Boot der Instanz automatisch [Qwen3-TTS](https://github.com/SUP3RMASS1VE/Qwen3-TTS)
installiert. Der Trick gegen "Modell laden dauert ewig": die Instanz danach
**stoppen statt löschen** — die Festplatte (inkl. venv + heruntergeladenem
Modell) bleibt erhalten, ein späterer Neustart überspringt das komplette
Setup und ist in Sekunden wieder einsatzbereit.

## Einmalig: vast.ai-Template

Ist bereits angelegt (Name `podcast-fabrik-qwen3-tts`, Hash in `rent.sh`
hinterlegt). Zum Ansehen/Ändern:

```bash
vastai show template <hash>
vastai update template <hash> --onstart-cmd "$(cat onstart_qwen3_tts.sh)"   # falls das Script angepasst wird
```

## Workflow

```bash
cd cloud

# 1. Günstigste verfügbare RTX 5090 suchen + mieten (kostet ab hier Geld!)
./rent.sh

# 2. Warten bis Setup fertig (erster Start: ca. 5-15 Min. für venv + Torch +
#    Modell-Download beim ersten TTS-Call). Status/Log/öffentliche Adresse:
./status.sh

# 3. Einmalig episodes.json der Serie auf backend "gradio" einstellen.
#    narration: Voice Clone (ref_audio/ref_text wie gehabt aus data/voices/).
#    drama: pro Rolle einen Built-in-Speaker-Namen aus GradioBackend.SPEAKERS
#    (fabrik/audio/tts_backends.py) unter voices.<ROLLE>.voice eintragen --
#    andere Namen fallen auf den (einen, geteilten) Voice-Clone-Pfad zurück.
#    api_url ist für render_remote.sh irrelevant (wird remote automatisch auf
#    127.0.0.1 gesetzt), nur für den alten Direkt-Weg unten gebraucht:
#      "audio": { "backend": "gradio", "ref_audio": "...", "ref_text": "...", ... }

# 4. Serie remote vertonen: lädt Skripte+Referenz-Audio hoch, rendert
#    KOMPLETT auf der Instanz (kein Internet-Hop pro Chunk), holt output/
#    zurück. Wiederholbar/resumable -- ein Abbruch mittendrin lässt sich
#    einfach erneut aufrufen.
./render_remote.sh <series_slug>

# 5. Fertig? Instanz PAUSIEREN (nicht löschen!) — Setup bleibt erhalten,
#    es laufen nur noch die kleinen Storage-Kosten weiter:
./stop.sh

# 6. Nächstes Mal wieder vertonen: einfach fortsetzen (Sekunden statt Minuten,
#    kein erneutes Setup/Modell-Download nötig), Status prüfen, dann render_remote.sh:
./resume.sh
./status.sh
./render_remote.sh <series_slug>

# Instanz endgültig nicht mehr gebraucht -> LÖSCHT die Festplatte:
./destroy.sh
```

### Alter Direkt-Weg (ohne render_remote.sh)

Für einen schnellen Konnektivitätstest oder falls remote-Ausführung mal
nicht in Frage kommt: `podcast_maker.py`/`batch.py` laufen stattdessen ganz
normal lokal auf dem Mac und sprechen direkt gegen die öffentliche Adresse
der Instanz — dann geht aber **jeder einzelne TTS-Chunk übers Internet**
(inkl. Re-Upload der Referenz-Audiodatei bei jedem Request), was bei langen
Serien spürbaren Overhead bedeutet.

```bash
# episodes.json: audio.api_url auf die öffentliche Adresse aus status.sh setzen
#   "audio": { "backend": "gradio", "api_url": "http://<ip>:<port>", ... }
cd ..
.venv/bin/python -m fabrik.cli.batch
```

Die öffentliche IP:Port-Kombination ändert sich nach jedem Stop/Start —
für diesen Weg nach `resume.sh` immer `status.sh` prüfen und `episodes.json`
neu eintragen (für `render_remote.sh` nicht nötig, siehe oben).

## Dateien

| Datei | Zweck |
|---|---|
| `onstart_qwen3_tts.sh` | Läuft bei jedem Boot der Instanz. Setup nur beim ersten Mal, danach nur Server-Start. |
| `rent.sh` | Sucht günstigste verfügbare RTX 5090, mietet sie mit dem gespeicherten Template. |
| `status.sh [id]` | Zeigt Status, öffentliche Gradio-Adresse und die letzten Log-Zeilen. |
| `render_remote.sh <series_slug> [id]` | Lädt Skripte+Referenz-Audio hoch, rendert die Serie komplett remote (`batch.py` gegen `127.0.0.1`), holt `output/` zurück. |
| `stop.sh [id]` | Pausiert die Instanz (Festplatte bleibt erhalten). |
| `resume.sh [id]` | Startet eine gestoppte Instanz wieder. |
| `destroy.sh [id]` | Löscht die Instanz UND ihre Festplatte unwiderruflich (mit Sicherheitsabfrage). |
| `.last_instance_id` | Wird von `rent.sh` geschrieben, macht die ID-Angabe bei den anderen Scripts optional. |

## Hinweise

- Ohne Instanz-ID-Argument nutzen `status.sh`/`render_remote.sh`/`stop.sh`/
  `resume.sh`/`destroy.sh` automatisch die zuletzt mit `rent.sh` gemietete
  Instanz (`.last_instance_id`).
- `render_remote.sh` ist pro `(series_slug, instance_id)`-Paar unabhängig —
  mehrere Serien auf mehreren gemieteten Instanzen (z.B. per `race.sh`
  parallel gemietet) lassen sich einfach mit mehreren `render_remote.sh`-
  Aufrufen nebeneinander rendern, ohne dass sich die Läufe in die Quere
  kommen (jede Serie lebt remote wie lokal unter `data/series/<slug>/`).
- Filter in `rent.sh`/`race.sh` (`gpu_name=RTX_5090 disk_space>=40
  reliability>0.98 verified=true inet_down>1000 inet_up>1000`) bei Bedarf
  anpassen, z.B. wenn gerade keine 5090 verfügbar ist. `verified=true`
  beschränkt die Suche auf von vast.ai geprüfte Datacenter-Hosts statt
  beliebiger Privat-Hosts — stabiler, aber eine kleinere Auswahl (und meist
  etwas teurer als der günstigste Community-Host). `inet_down`/`inet_up`
  (Mbit/s, vom Host selbst gemessen) filtert Angebote mit schlechter
  Anbindung heraus — wichtig für den einmaligen Upload/Download in
  `render_remote.sh`, seit die einzelnen TTS-Chunks nicht mehr übers
  Internet gehen aber weniger kritisch als früher.
- Manche Hosts scheitern kurz nach dem Mieten beim Setup/Boot und
  verschwinden von selbst wieder aus `vastai show instances-v1` (kostet nur
  eine minimale Storage-Gebühr, keine GPU-Zeit) — `race.sh` mietet deshalb
  mehrere Instanzen parallel und behält nur die erste, die tatsächlich
  bereit wird.
- `audio.ref_audio` in `episodes.json` bleibt der lokale Mac-Pfad
  (`data/voices/myvoice_ref.wav`) — `render_remote.sh` synct
  `data/voices/` einmal komplett zur Instanz, der Pfad bleibt dadurch remote
  identisch gültig. Für den alten Direkt-Weg lädt `gradio_client.handle_file()`
  in `tts_backends.py` die Referenzaufnahme stattdessen bei jedem einzelnen
  Request neu hoch.
