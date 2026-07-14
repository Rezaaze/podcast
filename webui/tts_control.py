"""Startet/stoppt die Pinokio-verwaltete Qwen3-TTS-App für podcast_maker.py/batch.py.

Pinokios pterm-CLI kennt nur search/status/run/open/logs/upload/which/stars/
registry/download — kein 'stop'. Der zuverlässige Weg, die TTS-Ressourcen
(RAM/GPU — MLX auf dem Mac, CUDA/VRAM auf Windows) wieder freizugeben, ist
daher: den tatsächlichen TTS-Serverprozess (erkennbar am gebundenen Port aus
episodes.json audio.api_url) zu beenden. Pinokios interne Shell-Session bleibt
danach zwar kosmetisch als "running" vermerkt, ein erneutes 'pterm run'
startet den Server darin aber trotzdem sauber neu (verifiziert auf macOS).

App-Start/-Stop von Pinokio selbst (nicht nur der TTS-Server) läuft
plattformabhängig: macOS nutzt `open -a`/`osascript`, Windows `taskkill` +
den bekannten Installationspfad, da es dort kein osascript/pkill gibt.
"""

import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request

from config import PF_DIR, current_episodes_json

IS_WINDOWS = platform.system() == "Windows"

TTS_APP_ID = "Qwen3-TTS-MLX-WebUI-Enhanced.git"
PINOKIO_CONTROL_URL = "http://127.0.0.1:42000"
PINOKIO_START_TIMEOUT = 60
TTS_START_TIMEOUT = 180


def _pterm_path() -> str:
    found = shutil.which("pterm")
    if found:
        return found
    config_path = os.path.expanduser("~/.pinokio/config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            home = json.load(f).get("home")
        if home:
            candidate = os.path.join(home, "bin", "npm", "bin", "pterm")
            if os.path.exists(candidate):
                return candidate
    raise RuntimeError("pterm nicht gefunden — ist Pinokio installiert?")


def _pterm_json(*args, timeout=15) -> dict:
    pterm = _pterm_path()
    result = subprocess.run([pterm, *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"pterm {' '.join(args)} fehlgeschlagen: {(result.stderr or result.stdout).strip()[:300]}")
    return json.loads(result.stdout)


def get_tts_port() -> int:
    episodes_json = current_episodes_json()
    if not episodes_json:
        return 42003
    with open(episodes_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    api_url = data.get("audio", {}).get("api_url", "http://127.0.0.1:42003")
    m = re.search(r":(\d+)", api_url)
    return int(m.group(1)) if m else 42003


def pinokio_reachable() -> bool:
    try:
        urllib.request.urlopen(f"{PINOKIO_CONTROL_URL}/", timeout=2)
        return True
    except Exception:
        return False


def _launch_pinokio() -> None:
    if IS_WINDOWS:
        # Pinokio installiert sich üblicherweise nach %LOCALAPPDATA%\Programs\pinokio.
        candidate = os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "Programs", "pinokio", "Pinokio.exe"
        )
        if os.path.exists(candidate):
            subprocess.Popen([candidate], close_fds=True)
        else:
            # Fallback: über die Windows-Programmauflösung starten (funktioniert,
            # wenn Pinokio im PATH/App-Verzeichnis registriert ist).
            subprocess.run(["cmd", "/c", "start", "", "Pinokio"], check=False)
    else:
        subprocess.run(["open", "-a", "Pinokio"], check=False)


def ensure_pinokio_running(log=print) -> bool:
    if pinokio_reachable():
        return True
    log("Pinokio läuft nicht — starte Pinokio ...")
    _launch_pinokio()
    deadline = time.time() + PINOKIO_START_TIMEOUT
    while time.time() < deadline:
        if pinokio_reachable():
            log("Pinokio ist erreichbar.")
            return True
        time.sleep(1)
    log("❌ Pinokio konnte nicht rechtzeitig gestartet werden.")
    return False


def tts_status(probe: bool = True) -> dict:
    """Live-Status der Qwen3-TTS-App. probe=True erzwingt einen echten
    HTTP-Check statt der zwischengespeicherten Log-Erkennung (kann sonst
    'ready: true' melden, obwohl der Prozess längst beendet ist)."""
    args = ["status", TTS_APP_ID]
    if probe:
        args += ["--probe", "--timeout=5000"]
    try:
        return _pterm_json(*args, timeout=10)
    except Exception:
        return {"running": False, "ready": False, "state": "unknown"}


def is_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _probe_health(port: int) -> str:
    """'ready': /health antwortet 200. 'no-endpoint': der Server antwortet per
    HTTP, kennt aber kein /health (z.B. anderes Backend auf dem Port) — dann
    bleibt der offene Port das beste verfügbare Signal. 'loading': Verbindung
    schlägt fehl oder 5xx — Port offen, Modell lädt noch."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
            return "ready" if resp.status == 200 else "no-endpoint"
    except urllib.error.HTTPError as e:
        return "loading" if e.code >= 500 else "no-endpoint"
    except Exception:
        return "loading"


def _wait_for_health(port: int, timeout: float, log) -> bool:
    """Nach dem offenen Port aufs GELADENE Modell warten: der Port geht auf,
    bevor der Health-Endpoint gesund ist (podcast_maker retried deshalb bisher
    blind 3×10s — bei langsamem Modell-Load ein falsches 'Server tot')."""
    deadline = time.time() + timeout
    loading_reported = False
    while time.time() < deadline:
        status = _probe_health(port)
        if status == "ready":
            log("✅ Qwen3-TTS ist bereit (Health-Endpoint antwortet).")
            return True
        if status == "no-endpoint":
            log("Kein /health-Endpoint auf diesem Server — offener Port gilt als bereit.")
            return True
        if not loading_reported:
            log("Port offen, Modell lädt noch — warte auf /health ...")
            loading_reported = True
        time.sleep(3)
    log("❌ Qwen3-TTS: Health-Endpoint wurde nicht rechtzeitig bereit (Timeout).")
    return False


def start_tts(log=print) -> bool:
    """Qwen3-TTS ist in Pinokio als Auto-Start-App konfiguriert (startet von
    selbst, sobald Pinokio hochfährt). Diese Funktion muss also nur Pinokio
    öffnen (falls nicht schon offen) und warten, bis der Port erreichbar ist
    UND der Health-Endpoint das geladene Modell bestätigt. Meldet sich der
    Port nach einer Weile trotzdem nicht, wird 'pterm run' als Fallback
    nachgeschoben (z.B. falls Auto-Start mal deaktiviert war)."""
    if not ensure_pinokio_running(log):
        return False

    port = get_tts_port()
    if is_port_listening(port):
        log(f"Qwen3-TTS läuft bereits auf Port {port}.")
        return _wait_for_health(port, 60, log)

    log("Warte auf Qwen3-TTS (Auto-Start durch Pinokio) ...")
    fallback_triggered = False
    deadline = time.time() + TTS_START_TIMEOUT
    while time.time() < deadline:
        if is_port_listening(port):
            log(f"Port {port} offen.")
            return _wait_for_health(port, max(30.0, deadline - time.time()), log)
        # Nach einem Drittel der Wartezeit ohne Erfolg: explizit anstoßen,
        # falls Auto-Start aus irgendeinem Grund nicht gegriffen hat.
        if not fallback_triggered and time.time() > deadline - (TTS_START_TIMEOUT * 2 / 3):
            fallback_triggered = True
            log("Kein Auto-Start erkannt — stoße Qwen3-TTS manuell an ...")
            pterm = _pterm_path()
            subprocess.Popen(
                [pterm, "run", TTS_APP_ID,
                 "--default", "run.js?mode=Default", "--default", "run.js", "--default", "install.js"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        time.sleep(3)
    log("❌ Qwen3-TTS wurde nicht rechtzeitig bereit (Timeout).")
    return False


def _kill_port_owner(port: int) -> None:
    if IS_WINDOWS:
        try:
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
        except FileNotFoundError:
            pass
    else:
        try:
            result = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                                     capture_output=True, text=True, timeout=10)
            for pid in result.stdout.split():
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except (ProcessLookupError, ValueError):
                    continue
        except FileNotFoundError:
            pass


def _quit_pinokio_gracefully() -> None:
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/IM", "Pinokio.exe"], capture_output=True)
    else:
        subprocess.run(
            ["osascript", "-e", 'tell application "Pinokio" to quit'],
            capture_output=True, text=True, timeout=15,
        )


def _force_kill_pinokio() -> None:
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/IM", "Pinokio.exe", "/F"], capture_output=True)
    else:
        subprocess.run(["pkill", "-x", "Pinokio"], capture_output=True)


def stop_tts(log=print) -> bool:
    """Beendet Qwen3-TTS UND die komplette Pinokio-App (nicht nur den
    TTS-Prozess) — sonst laufen weiter Electron/Chromium-Helper-Prozesse im
    Hintergrund und verbrauchen Ressourcen, obwohl die eigentliche
    TTS-Nutzung vorbei ist. Da die App auf Auto-Start konfiguriert ist,
    genügt ein einfaches erneutes Öffnen von Pinokio beim nächsten Start_tts()."""
    port = get_tts_port()
    _kill_port_owner(port)

    if not pinokio_reachable() and not is_port_listening(port):
        log("Pinokio läuft bereits nicht (mehr).")
        return True

    log("Beende Pinokio (inkl. Qwen3-TTS) ...")
    _quit_pinokio_gracefully()

    deadline = time.time() + 20
    while time.time() < deadline:
        if not pinokio_reachable():
            log("🛑 Pinokio beendet — Ressourcen frei.")
            return True
        time.sleep(1)

    log("⚠️  Pinokio antwortete nicht — erzwinge Beenden ...")
    _force_kill_pinokio()
    time.sleep(2)
    if not pinokio_reachable():
        log("🛑 Pinokio beendet — Ressourcen frei.")
        return True
    log("❌ Pinokio konnte nicht beendet werden.")
    return False
