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
Plattenplatz, und vast.ai-Instanzen sind selbst schon Docker-Container ohne
verlässlichen Docker-in-Docker-Zugriff für Renter). Stattdessen: ein
Stock-PyTorch-Image + ein Onstart-Script, das beim allerersten Boot der
Instanz automatisch [Qwen3-TTS](https://github.com/SUP3RMASS1VE/Qwen3-TTS)
installiert UND per Testrender das Modell warmläuft (erzwingt den
HuggingFace-Download, bevor die Instanz als "bereit" gilt — sonst würde genau
dieser Download unbemerkt erst beim ersten echten `render_remote.sh`-Lauf
passieren). Dieser Modell-Download ist mit Abstand der größte Download im
ganzen Setup (apt/pip/git sind klein dagegen) und läuft über
[`hf_transfer`](https://github.com/huggingface/hf_transfer) statt der
langsamen Single-Connection-Downloads, die `huggingface_hub` sonst
standardmäßig nutzt — parallele Multi-Connection-Übertragung, spürbar
schneller bei großen Checkpoints. Der Trick gegen "Modell laden dauert ewig":
die Instanz danach
**stoppen statt löschen** — die Festplatte (inkl. venv + heruntergeladenem
Modell) bleibt erhalten, ein späterer Neustart überspringt das komplette
Setup+Warmup und ist in Sekunden wieder einsatzbereit.

**Gegen "keinen passenden Server finden"**: statt bei jedem Bedarf neu auf
dem Marktplatz zu suchen (Flakiness: Hosts fallen während des 5-15-minütigen
Setups oft weg), hält `get_ready_instance.sh` einen kleinen **Pool von 2
bereits fertig eingerichteten, gestoppten Instanzen** (`.instance_pool`) und
probiert die per Resume durch — das dauert Sekunden statt Minuten. Nur wenn
der GESAMTE Pool nicht rechtzeitig bereit wird, mietet es über `race.sh`
neu und füllt den Pool automatisch wieder auf. `render_remote.sh` ruft das
automatisch auf, wenn keine `instance_id` übergeben wird — kein manuelles
`resume.sh`/`status.sh`-Ratespiel mehr nötig.

**Gegen "die 5090 wird nicht ausgelastet" — echtes Batching statt paralleler
Requests:** `podcast_maker.py` schickte TTS-Chunks ursprünglich strikt
nacheinander ans Backend. Naheliegender erster Versuch, das zu
beschleunigen — mehrere Chunks per Threads gleichzeitig anfragen
(`audio.chunk_concurrency`) — brachte **null** Speedup: `nvidia-smi` zeigte
durchgehend nur ~11% GPU-Auslastung, weil PyTorch CUDA-Aufrufe aus
verschiedenen Python-Threads standardmäßig über denselben CUDA-Default-
Stream serialisiert — mehr gleichzeitige Client-Requests bedeuten dort nur
mehr Wartezeit, keine echte Parallelität. Die Demo-App
([SUP3RMASS1VE/Qwen3-TTS](https://github.com/SUP3RMASS1VE/Qwen3-TTS)) hat
außerdem keinen Batch-Endpoint — obwohl das zugrundeliegende Modell
(`qwen_tts.Qwen3TTSModel.generate_custom_voice`) echtes Batching
unterstützt (`text: Union[str, List[str]]`, EIN `model.generate()`-Call für
den ganzen Batch statt N einzelner Calls).

`onstart_qwen3_tts.sh` patcht deshalb bei jedem Boot (idempotent, zwei
unabhängige Marker-Checks) ZWEI zusätzliche Batch-Endpoints in die App:
`/generate_custom_voice_batch` (Built-in-Speaker, Modell "CustomVoice")
und `/generate_voice_clone_batch` (Voice-Clone-Rollen, Modell "Base" —
`qwen_tts.Qwen3TTSModel.generate_voice_clone` unterstützt laut Docstring
genauso Batch-Modus, `ref_audio`/`ref_text` werden automatisch auf alle
Texte im Batch gebroadcastet, wenn nur EIN Wert statt einer Liste kommt —
passt exakt zu unserem Design: eine geteilte Voice-Clone-Identität pro
Serie). `GradioBackend.generate_chunk_batch()` in `tts_backends.py`
routet je nach Job-Art an den passenden Endpoint; `podcast_maker.py`
bucketet Chunks VOR dem Windowing nach Stimm-Art (`by_kind`), weil ein
Batch-Call serverseitig nur EIN Modell bedienen kann — ein Skript, das
zwischen Built-in-Speaker- und Voice-Clone-Rollen wechselt (z.B. REID
neben einem geklonten NARRATOR), würde sonst gemischte Kinds in ein
Fenster packen und dem falschen Endpoint zuordnen.

**Stolperfalle beim Bauen:** Der `gr.Audio`-Input des Clone-Batch-Endpoints
muss `type="numpy"` sein (wie beim bereits vorhandenen Einzel-Endpoint),
NICHT `type="filepath"` — sonst bekommt `_audio_to_tuple()` in der App
einen Pfad-String statt der erwarteten `(sr, array)`-Form und meldet
fälschlich "Reference audio is required." trotz korrekt hochgeladener
Datei.

Gemessen auf einer gemieteten RTX 5090 (reine Built-in-Speaker-Chunks):

| Batch-Größe | s/Chunk | Speedup vs. sequenziell (~12s/Chunk) |
|---|---|---|
| 1 (sequenziell) | ~12.0 | 1× |
| 8 | 1.63 | ~7.4× |
| 17 | 0.92 | ~13× |
| 40 | 0.42 | ~29× |
| 100 | 0.23 | ~52× (danach OOM bei 120) |

Eine reine Built-in-Speaker-Episode (55 Chunks) sank damit End-to-End von
**10m 57s auf 2m 41s** bei `chunk_concurrency: 17`. Eine gemischte Episode
mit vielen Voice-Clone-NARRATOR-Zeilen (241 Chunks, `the_curator_s_masterwork`
Ep9) kam auf **~4,5s/Chunk im Schnitt** (inkl. Kaltstart-Ladezeit des
Base-Modells) — schwächerer, aber klar positiver Speedup ggü. der
Sequenziell-Baseline, weil das Base/Voice-Clone-Modell grundsätzlich
langsamer ist als CustomVoice und den Schnitt nach oben zieht.
**Empfohlener Produktions-Default: `audio.chunk_concurrency: 40`** —
deutlich unter der gemessenen OOM-Grenze (100-120 mit kurzen Testsätzen;
echte Skript-Chunks sind mit bis zu `chunk_max_chars: 350` länger und
brauchen pro Sequenz mehr VRAM, die reale Grenze liegt also niedriger als
die Testzahlen). Ein OOM-Fehler killt den ganzen Part, deshalb lieber
Sicherheitsabstand als das letzte Prozent Durchsatz.

## Einmalig: vast.ai-Template

Ist bereits angelegt (Name `podcast-fabrik-qwen3-tts-v8`, Hash in
`rent.sh`/`race.sh` hinterlegt). Zum Ansehen:

```bash
vastai search templates 'hash_id=<hash>' --raw   # "show template" gibt es in dieser CLI-Version nicht mehr
```

**Achtung:** `vastai update template <hash> --onstart-cmd "..."` schlägt
mit dieser vastai-CLI-Version (1.3.0) an einem serverseitigen Bug fehl
("Invalid Creator ID" trotz korrektem Account — die API vergleicht die
`creator_id` gegen ein nicht aufgelöstes SQLAlchemy-Column-Objekt statt der
eigenen User-ID). Falls sich `onstart_qwen3_tts.sh` künftig ändert: **kein
Update versuchen**, sondern ein neues Template per `vastai create template
...` anlegen (gleiche Flags wie beim bestehenden — Name/Image/Tag/Repo/Env/
Search-Params 1:1 übernehmen, nur `--onstart-cmd` austauschen) und den neuen
Hash in `rent.sh`/`race.sh` (`TEMPLATE_HASH=...`) eintragen. Das alte
Template bleibt dabei unverändert bestehen (kein Risiko, etwas kaputt zu
patchen).

## Workflow

```bash
cd cloud

# EINMALIG: Pool aus 2 fertig eingerichteten, vorgewärmten Instanzen
# aufbauen (kostet ab hier Geld!). Danach übernimmt get_ready_instance.sh
# das Verwalten -- dieser Schritt muss nur einmal (oder nach einem
# kompletten Pool-Ausfall) wiederholt werden.
./race.sh 2
./status.sh                    # prüfen, dass die Gewinner-Instanz wirklich läuft
./render_remote.sh <test_series>   # kurzer Testlauf zur Verifikation
./stop.sh                      # Gewinner-Instanz pausieren
# zweite Runde für die zweite Pool-Instanz:
./race.sh 2
./stop.sh
# beide Instanz-IDs in cloud/.instance_pool eintragen (eine ID pro Zeile)

# NORMALER WORKFLOW ab hier: get_ready_instance.sh holt automatisch eine
# einsatzbereite Instanz aus dem Pool (Sekunden), fällt nur bei komplettem
# Pool-Ausfall auf race.sh zurück. render_remote.sh ruft das selbst auf --
# manuelles resume.sh/status.sh-Ratespiel ist nicht mehr nötig.

# 1. Einmalig pro Serie: episodes.json auf backend "gradio" einstellen.
#    narration: Voice Clone (ref_audio/ref_text wie gehabt aus data/voices/).
#    drama: pro Rolle einen Built-in-Speaker-Namen aus GradioBackend.SPEAKERS
#    (fabrik/audio/tts_backends.py) unter voices.<ROLLE>.voice eintragen --
#    andere Namen fallen auf den (einen, geteilten) Voice-Clone-Pfad zurück.
#    chunk_concurrency: 40 fuer echtes Batching (siehe oben) -- wirkt auf
#    Built-in-Speaker- UND Voice-Clone-Rollen (getrennte Batch-Endpoints,
#    gemischte Kinds werden automatisch in getrennte Fenster bucketet).
#    api_url ist für render_remote.sh irrelevant (wird remote automatisch auf
#    127.0.0.1 gesetzt), nur für den alten Direkt-Weg unten gebraucht:
#      "audio": { "backend": "gradio", "chunk_concurrency": 40, "ref_audio": "...", "ref_text": "...", ... }

# 2. Serie remote vertonen: holt/wartet auf eine einsatzbereite Instanz,
#    lädt Skripte+Referenz-Audio hoch, rendert KOMPLETT auf der Instanz
#    (kein Internet-Hop pro Chunk), holt output/ zurück. Wiederholbar/
#    resumable -- ein Abbruch mittendrin lässt sich einfach erneut aufrufen.
./render_remote.sh <series_slug>

# 2b. Alternative: mehrere fehlende Episoden GLEICHZEITIG auf mehreren
#     Instanzen rendern (nur GPU-Minuten zählen, nicht Instanzen -- bei N
#     Episoden parallel auf N Instanzen dauert es ~1/N der Wanduhrzeit für
#     ~denselben Gesamtpreis). Erkennt fehlende Episoden automatisch:
./render_remote_parallel.sh <series_slug> --max 3

# 3. Fertig? Instanz PAUSIEREN (nicht löschen!) — sie bleibt im Pool,
#    es laufen nur noch die kleinen Storage-Kosten weiter:
./stop.sh

# Instanz endgültig nicht mehr gebraucht -> LÖSCHT die Festplatte
# (danach auch aus cloud/.instance_pool austragen):
./destroy.sh
```

### WebUI-Anbindung

Das WebUI (Step „Skripte generieren & vertonen" → Einzelschritte) hat einen
Umschalter **„Vertonen auf: Lokal / Cloud-GPU"**. Bei „Cloud" laufen die
beiden Vertonen-Buttons über das Kommando `pf_render_remote`
(`webui/config.py`), das genau dieses `render_remote.sh` aufruft — „Alle
vertonen" = ganze Serie, „Nur diese Episode" = `--only <datei>`. Die
Checkbox „Instanz danach pausieren" hängt `--stop-after` an. Bei `--only`
lädt `render_remote.sh` NICHT den ganzen Serien-Ordner hoch — bereits
fertig gerenderte Episoden-MP3s/SRT/SUBS anderer Episoden (können pro
Serie mehrere hundert MB sein) bleiben außen vor, nur Skripte,
`episodes.json`, Checkpoints/Cues und Teilergebnisse der Zielepisode gehen
mit (bei einer frischen Serie auf einer neuen Instanz macht das den
Unterschied zwischen ~500 KB und ~200 MB Upload). Das lokale
Pinokio/Qwen3-TTS wird dabei bewusst NICHT gestartet (Kommando ist nicht in
`AUTO_TTS_COMMANDS`). „Job abbrechen" im WebUI beendet nur die lokale
SSH-/rsync-Seite — der Remote-Lauf auf der Instanz rendert weiter und ein
erneuter Start resumed (Fertiges wird übersprungen), holt aber erst am Ende
wieder Ergebnisse zurück.

Zusätzlich gibt es dort den Button **„☁︎ Fehlende Episoden parallel in der
Cloud vertonen"** (Kommando `pf_render_remote_parallel`, Feld daneben
steuert `--max`) — wrappt `render_remote_parallel.sh` 1:1, unabhängig vom
Lokal/Cloud-Umschalter (rein cloud-basiert).

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
| `onstart_qwen3_tts.sh` | Läuft bei jedem Boot der Instanz. Setup+Warmup nur beim ersten Mal, danach nur Server-Start. |
| `get_ready_instance.sh` | **Haupteinstieg.** Probiert den Instanz-Pool per Resume durch, fällt nur bei komplettem Ausfall auf `race.sh` zurück und füllt den Pool danach wieder auf. |
| `rent.sh` | Sucht eine verfügbare RTX 5090 (Preisspanne + PCIe-Bandbreite + bekannt zuverlässiger Host), mietet sie mit dem gespeicherten Template. Manueller Einzel-Weg / von `race.sh` intern genutzt. |
| `race.sh [n]` | Mietet `n` Instanzen parallel, behält die zuerst bereite. Wird von `get_ready_instance.sh` als Fallback aufgerufen. |
| `status.sh [id]` | Zeigt Status, öffentliche Gradio-Adresse und die letzten Log-Zeilen. |
| `render_remote.sh <series_slug> [id] [--only <epN.txt>] [--stop-after]` | Ohne `id`: holt selbst eine einsatzbereite Instanz über `get_ready_instance.sh`. Lädt Skripte+Referenz-Audio hoch, rendert die Serie komplett remote (`batch.py` gegen `127.0.0.1`), holt `output/` zurück. `--only` vertont nur die eine Skript-Datei (`podcast_maker` statt `batch`) UND lädt dabei auch nur die für diese Episode nötigen Dateien hoch (nicht den ganzen Serien-Ordner inkl. fertiger Nachbar-Episoden — kann bei einer frischen Instanz den Unterschied zwischen ~500 KB und ~200 MB Upload machen). `--stop-after` pausiert die Instanz nach dem Lauf (auch bei Fehler). |
| `render_remote_parallel.sh <series_slug> [--max N] [--episodes ...]` | Erkennt automatisch alle Episoden ohne fertige `<Prefix>_FULL_EPISODE.mp3` und rendert bis zu `--max` (Standard 3) davon GLEICHZEITIG auf mehreren Instanzen (`render_remote.sh --only` pro Episode, in Wellen bei mehr fehlenden Episoden als `--max`). Instanzen werden nur EINMAL beschafft und über alle Wellen wiederverwendet (kein Neu-Setup pro Welle). Pool-Instanzen werden am Ende pausiert, zusätzlich gemietete Ad-hoc-Instanzen gelöscht. Fällt eine Instanz zwischen zwei Wellen aus, kommt ihre unfertige Episode zurück in die Warteschlange, die übrigen Instanzen übernehmen sie. |
| `stop.sh [id]` | Pausiert die Instanz (Festplatte bleibt erhalten). |
| `resume.sh [id]` | Startet eine gestoppte Instanz wieder (manueller Weg — `get_ready_instance.sh` macht das für den Pool automatisch). |
| `destroy.sh [id]` | Löscht die Instanz UND ihre Festplatte unwiderruflich (mit Sicherheitsabfrage). Danach auch aus `.instance_pool` austragen. |
| `.last_instance_id` | Zeigt auf die zuletzt verwendete Instanz, macht die ID-Angabe bei den anderen Scripts optional. |
| `.instance_pool` | Liste (eine ID pro Zeile) der vorgewärmten, für Resume vorgesehenen Instanzen — max. 2, von `get_ready_instance.sh` verwaltet. |

## Hinweise

- **Download-Robustheit:** Jeder `rsync`-Aufruf in `render_remote.sh` läuft
  mit `--timeout=60` (bricht ab, wenn 60s lang keine Daten fließen, statt
  unbegrenzt zu hängen — `ssh -o ConnectTimeout` deckt nur den
  Verbindungsaufbau ab, nicht eine später einschlafende Verbindung). Der
  finale Ergebnis-Download hat zusätzlich bis zu 3 Versuche (10s Pause
  dazwischen) — die teuerste Fehlerquelle wäre sonst eine bereits fertig
  gerenderte, aber nie heruntergeladene Episode. `--stop-after` läuft auch
  bei einem endgültig gescheiterten Download noch durch (kein Grund, die
  Instanz deswegen unnötig weiterlaufen zu lassen); der Script-Exit-Code
  bleibt trotzdem non-zero, ein erneuter Aufruf holt nur den Download nach
  (Rendern wird übersprungen, da schon fertig).
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
- **Angebotsauswahl** (`pick_cheapest_offer.py`/`race_pick_offers.py`) nimmt
  NICHT stur das billigste Angebot: `reliability`/`inet_down`/`inet_up`
  sagen nichts über die tatsächliche Rechenleistung ODER den echten
  Transfer-Durchsatz zu einem bestimmten Standort aus (zwei Hosts mit
  derselben GPU können durch limitierte PCIe-Anbindung unterschiedlich
  schnell rendern; `machine_id 58908` meldete z.B. 1.7-2 Gbit/s, lieferte
  beim Datei-Transfer zum Mac in Deutschland real aber nur 5-25 KB/s).
  Stattdessen: Preisspanne bis 15% über dem Minimum bilden, darin nach
  `pcie_bw` (PCIe-Bandbreite, Proxy für Rechenleistung) sortieren; taucht
  einer der bekannt zuverlässigen Hosts (`KNOWN_RELIABLE_MACHINE_IDS` —
  aktuell `machine_id 137831`, hohe Rechenleistung/Batching, und `55308`,
  zusätzlich mit echtem Transfertest zum Mac verifiziert, siehe Memory
  `vastai-stamm-instanz`) in der Spanne auf, wird er unabhängig vom
  `pcie_bw`-Wert bevorzugt. Neue verifizierte Hosts einfach zu dieser Menge
  in beiden Scripts hinzufügen.
- Manche Hosts scheitern kurz nach dem Mieten beim Setup/Boot und
  verschwinden von selbst wieder aus `vastai show instances-v1` (kostet nur
  eine minimale Storage-Gebühr, keine GPU-Zeit) — `race.sh` mietet deshalb
  mehrere Instanzen parallel und behält nur die erste, die tatsächlich
  bereit wird. `get_ready_instance.sh` versucht aber erst den Pool
  gestoppter, bereits fertig eingerichteter Instanzen per Resume, bevor es
  überhaupt neu mietet — der Normalfall braucht `race.sh` also gar nicht.
- **Manuelle SSH-Sessions (z.B. um app.py live nachzupatchen oder den
  Server neuzustarten) reißen auf manchen Hosts öfter mal transient ab**
  ("Connection ... closed by remote host", Exit 255) — mitten in einem
  `pkill && nohup ...`-Zweizeiler kann das den Kill ausführen, aber den
  Neustart verschlucken. Nach jedem Abbruch erst per `pgrep -af 'python3
  app.py'` den tatsächlichen Prozessstatus prüfen, statt dem eigenen
  vorherigen Kommando zu vertrauen — Kill und Start notfalls als zwei
  einzeln verifizierte SSH-Calls statt eines zusammengesetzten.
- `audio.ref_audio` in `episodes.json` bleibt der lokale Mac-Pfad
  (`data/voices/myvoice_ref.wav`) — `render_remote.sh` synct
  `data/voices/` einmal komplett zur Instanz, der Pfad bleibt dadurch remote
  identisch gültig. Für den alten Direkt-Weg lädt `gradio_client.handle_file()`
  in `tts_backends.py` die Referenzaufnahme stattdessen bei jedem einzelnen
  Request neu hoch.
