#!/usr/bin/env python3
"""Cockpit-Steuerung — ein Mini-Supervisor für den Parallelbetrieb.

Jedes Podcast-Fabrik-Cockpit ist ein EIGENER Flask-Prozess auf einem eigenen
Port (5151, 5152, ...), mit eigenem Speicher (eigene aktive Serie, eigene
Job-Liste). Dieser Launcher ist eine kleine 5. Weboberfläche (Port 5150), die
diese Cockpit-Prozesse per Knopf startet/stoppt/neustartet — er fasst das
eigentliche WebUI (app.py) nicht an, er ruft es nur mehrfach auf.

Start:  ./start_launcher.sh   (oder  webui/.venv/bin/python webui/launcher.py)

Prozess-Modell:
- Cockpits laufen in einer EIGENEN Session (start_new_session=True) und
  überleben das Beenden des Launchers — ein versehentliches Schließen des
  Launcher-Terminals killt also keine laufende Generierung.
- Der Launcher merkt sich die PIDs in .launcher_state.json und adoptiert
  laufende Cockpits nach einem eigenen Neustart wieder (Stop bleibt möglich).
- „Serie (Pin)" leer  -> WEBUI_ISOLATED=1 (Cockpit legt eigene Serie an).
  gefüllt              -> WEBUI_SERIES=<slug> (fest auf bestehende Serie).
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time

from flask import Flask, Response, jsonify, request

WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(WEBUI_DIR, ".venv", "bin", "python")
LOG_DIR = os.path.join(WEBUI_DIR, ".launcher_logs")
STATE_FILE = os.path.join(WEBUI_DIR, ".launcher_state.json")

BASE_PORT = int(os.environ.get("LAUNCHER_BASE_PORT", 5151))
COUNT = int(os.environ.get("LAUNCHER_COUNT", 4))
LAUNCHER_PORT = int(os.environ.get("LAUNCHER_PORT", 5150))

os.makedirs(LOG_DIR, exist_ok=True)
_lock = threading.Lock()

# slot -> {"pid": int|None, "series": str|None}
_state = {}


def _port(slot):
    return BASE_PORT + slot


def _load_state():
    global _state
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _state = {int(k): v for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        _state = {}


def _save_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in _state.items()}, f, indent=2)


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _port_open(port):
    with socket.socket() as s:
        s.settimeout(0.25)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_slot(slot, series=None):
    with _lock:
        port = _port(slot)
        st = _state.get(slot, {})
        if _pid_alive(st.get("pid")) or _port_open(port):
            return  # läuft schon (von uns oder extern belegt) — nicht doppelt starten
        env = dict(os.environ, WEBUI_PORT=str(port))
        if series:
            env["WEBUI_SERIES"] = series
            env.pop("WEBUI_ISOLATED", None)
        else:
            env["WEBUI_ISOLATED"] = "1"
            env.pop("WEBUI_SERIES", None)
        logf = open(os.path.join(LOG_DIR, f"cockpit_{port}.log"), "w")
        proc = subprocess.Popen(
            [VENV_PY, "app.py"], cwd=WEBUI_DIR, env=env,
            stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,  # eigene Session: überlebt Launcher-Ende / dessen Ctrl+C
        )
        _state[slot] = {"pid": proc.pid, "series": series}
        _save_state()


def stop_slot(slot):
    with _lock:
        st = _state.get(slot, {})
        pid = st.get("pid")
        if _pid_alive(pid):
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            for _ in range(20):  # bis zu ~2s auf sauberes Ende warten
                if not _pid_alive(pid):
                    break
                time.sleep(0.1)
            if _pid_alive(pid):
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        _state[slot] = {"pid": None, "series": st.get("series")}
        _save_state()


def status():
    out = []
    for slot in range(COUNT):
        port = _port(slot)
        st = _state.get(slot, {})
        alive = _pid_alive(st.get("pid"))
        responding = _port_open(port)
        if responding:
            state = "running"
        elif alive:
            state = "starting"
        else:
            state = "stopped"
        out.append({
            "slot": slot,
            "port": port,
            "series": st.get("series"),
            "state": state,
            "url": f"http://127.0.0.1:{port}",
        })
    return out


app = Flask(__name__)


@app.get("/status")
def api_status():
    return jsonify(slots=status(), count=COUNT)


@app.post("/start")
def api_start():
    body = request.get_json(silent=True) or {}
    start_slot(int(body["slot"]), (body.get("series") or "").strip() or None)
    return ("", 204)


@app.post("/stop")
def api_stop():
    body = request.get_json(silent=True) or {}
    stop_slot(int(body["slot"]))
    return ("", 204)


@app.post("/restart")
def api_restart():
    body = request.get_json(silent=True) or {}
    slot = int(body["slot"])
    series = (body.get("series") or "").strip() or None
    stop_slot(slot)
    # kurz warten, bis der Port wirklich frei ist, sonst „läuft schon"-Guard
    for _ in range(20):
        if not _port_open(_port(slot)):
            break
        time.sleep(0.1)
    start_slot(slot, series)
    return ("", 204)


@app.post("/start-all")
def api_start_all():
    for slot in range(COUNT):
        start_slot(slot, (_state.get(slot, {}) or {}).get("series"))
    return ("", 204)


@app.post("/stop-all")
def api_stop_all():
    for slot in range(COUNT):
        stop_slot(slot)
    return ("", 204)


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Podcast-Fabrik — Cockpit-Steuerung</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.5 -apple-system,system-ui,sans-serif;
         background:#0f1115; color:#e6e8ec; padding:24px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:#8b93a1; margin:0 0 20px; font-size:13px; }
  .bar { display:flex; gap:10px; margin-bottom:20px; flex-wrap:wrap; }
  .card { background:#171a21; border:1px solid #262b36; border-radius:12px;
          padding:16px; margin-bottom:12px; }
  .card h2 { font-size:15px; margin:0 0 2px; display:flex; align-items:center; gap:10px; }
  .dot { width:10px; height:10px; border-radius:50%; background:#4a5160; flex:none; }
  .dot.running { background:#3fb950; box-shadow:0 0 8px #3fb95088; }
  .dot.starting { background:#d29922; box-shadow:0 0 8px #d2992288; }
  .dot.stopped { background:#4a5160; }
  .state { font-size:12px; color:#8b93a1; font-weight:normal; }
  .port { color:#6b7280; font-size:12px; font-weight:normal; }
  .controls { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; align-items:center; }
  input { background:#0f1115; border:1px solid #2c323d; color:#e6e8ec;
          border-radius:8px; padding:7px 10px; font-size:13px; width:190px; }
  button { border:1px solid #2c323d; background:#212630; color:#e6e8ec;
           border-radius:8px; padding:7px 14px; font-size:13px; cursor:pointer; }
  button:hover { background:#2a303c; }
  button.primary { background:#1f6feb; border-color:#1f6feb; }
  button.primary:hover { background:#2b7bf5; }
  button.danger { border-color:#4a2b2b; }
  button.danger:hover { background:#3a2323; }
  a.open { margin-left:auto; color:#58a6ff; text-decoration:none; font-size:13px; }
  a.open[aria-disabled="true"] { color:#4a5160; pointer-events:none; }
  .hint { color:#6b7280; font-size:12px; margin-top:16px; }
  label { font-size:12px; color:#8b93a1; }
</style></head><body>
<h1>Podcast-Fabrik — Cockpit-Steuerung</h1>
<p class="sub">Jedes Cockpit ist ein eigener Webserver auf eigenem Port. „Serie (Pin)" leer = das Cockpit legt seine eigene Serie an (isoliert); gefüllt = fest auf eine bestehende Serie.</p>
<div class="bar">
  <button class="primary" onclick="allStart()">▶ Alle starten</button>
  <button class="danger" onclick="allStop()">■ Alle stoppen</button>
</div>
<div id="slots"></div>
<p class="hint">Cockpits laufen in eigener Session weiter, auch wenn du den Launcher schließt. Logs: <code>webui/.launcher_logs/</code>.</p>
<script>
let built = false;
function el(tag, props={}, kids=[]) {
  const e = document.createElement(tag);
  Object.assign(e, props);
  for (const k of kids) e.append(k);
  return e;
}
function build(slots) {
  const root = document.getElementById("slots");
  root.innerHTML = "";
  for (const s of slots) {
    const dot = el("span", { className: "dot " + s.state });
    const stateLabel = el("span", { className: "state", textContent: label(s.state) });
    const title = el("h2", {}, [dot, document.createTextNode("Cockpit " + (s.slot+1) + " "),
                               el("span", { className:"port", textContent:"Port " + s.port }), stateLabel]);
    const input = el("input", { placeholder: "Serie (Pin, optional)", value: s.series || "",
                                id: "series-"+s.slot });
    const open = el("a", { className:"open", textContent:"Cockpit öffnen ↗", href: s.url, target:"_blank" });
    open.setAttribute("aria-disabled", s.state === "running" ? "false" : "true");
    const controls = el("div", { className:"controls" }, [
      el("label", { textContent:"Serie (Pin):" }), input,
      el("button", { className:"primary", textContent:"Start", onclick:()=>act("start", s.slot) }),
      el("button", { className:"danger", textContent:"Stop", onclick:()=>act("stop", s.slot) }),
      el("button", { textContent:"Neustart", onclick:()=>act("restart", s.slot) }),
      open,
    ]);
    root.append(el("div", { className:"card" }, [title, controls]));
  }
  built = true;
}
function label(state){ return state==="running" ? "läuft" : state==="starting" ? "startet…" : "gestoppt"; }
function update(slots) {
  for (const s of slots) {
    const card = document.getElementById("slots").children[s.slot];
    if (!card) return build(slots);
    card.querySelector(".dot").className = "dot " + s.state;
    card.querySelector(".state").textContent = label(s.state);
    const open = card.querySelector("a.open");
    open.setAttribute("aria-disabled", s.state === "running" ? "false" : "true");
    open.href = s.url;
  }
}
async function refresh() {
  const d = await (await fetch("/status")).json();
  if (!built || document.getElementById("slots").children.length !== d.slots.length) build(d.slots);
  else update(d.slots);
}
function seriesVal(slot){ const i = document.getElementById("series-"+slot); return i ? i.value.trim() : ""; }
async function act(kind, slot) {
  await fetch("/"+kind, { method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ slot, series: seriesVal(slot) }) });
  setTimeout(refresh, 400);
}
async function allStart(){ await fetch("/start-all",{method:"POST"}); setTimeout(refresh,400); }
async function allStop(){ await fetch("/stop-all",{method:"POST"}); setTimeout(refresh,400); }
refresh();
setInterval(refresh, 2000);
</script>
</body></html>"""


if __name__ == "__main__":
    _load_state()
    print(f"Cockpit-Steuerung auf http://127.0.0.1:{LAUNCHER_PORT} "
          f"({COUNT} Cockpits ab Port {BASE_PORT})")
    app.run(host="127.0.0.1", port=LAUNCHER_PORT, threaded=True, debug=False)
