"""Subprocess-Ausführung für whitelisted Kommandos + SSE-Log-Streaming.

Ein Job = ein Subprocess (oder bei kind="pyfunc" ein direkter Python-Aufruf,
z.B. für die TTS-Start/Stop-Steuerung), läuft in einem Background-Thread.
Zeilen landen in einer Queue pro Job (inkl. Ring-Buffer für Replay bei
Reconnect). Nur ein laufender Job pro command_id gleichzeitig.
"""

import importlib
import json
import os
import queue
import re
import signal
import subprocess
import threading
import time
import uuid

from config import AUTO_TTS_COMMANDS, COMMANDS, current_series_dir, series_dir_for, OUTPUT_RELPATH

STEP_RE = re.compile(r"^\s*▶\s*Schritt\s+(\d+)\s*:\s*(.+)$")
# batch.py: "[2/5] Starte: figur2.txt → Figur2_FULL_EPISODE.mp3" bzw.
# "[2/5] Übersprungen (existiert): ..." — Episoden-Fortschritt fürs Log-Panel.
# Bewusst NUR diese beiden Formen: podcast_maker.py druckt ähnliche
# "[i/n] ..."-Zeilen, die aber Parts zählen, keine Episoden.
EPISODE_RE = re.compile(r"^\[(\d+)/(\d+)\]\s+(?:Starte|Übersprungen \(existiert\)):\s*(.+)$")
MAX_BUFFER_LINES = 2000


class ValidationError(Exception):
    pass


def resolve_pyfunc(dotted: str):
    module_name, func_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def build_argv(command_id: str, params: dict) -> tuple[list[str] | None, str | None]:
    """Baut argv + cwd aus der COMMANDS-Whitelist. Wirft ValidationError bei
    unbekannten/fehlenden Parametern statt irgendetwas vom Client roh zu
    übernehmen. Für kind="pyfunc" gibt es kein argv/cwd (None, None)."""
    if command_id not in COMMANDS:
        raise ValidationError(f"Unbekanntes Kommando: {command_id}")
    cmd = COMMANDS[command_id]
    schema = cmd.get("args_schema", [])
    allowed_keys = {entry[1] for entry in schema}
    unknown = set(params or {}) - allowed_keys
    if unknown:
        raise ValidationError(f"Unbekannte Parameter: {', '.join(sorted(unknown))}")

    if cmd["kind"] == "pyfunc":
        return None, None

    # "-u": erzwingt unbuffered stdout/stderr beim Kind-Prozess. Ohne das
    # puffert Python bei Pipe-Redirection (statt TTY) blockweise statt
    # zeilenweise -> print()-Ausgaben landen erst nach Prozessende oder
    # vollem Puffer bei uns, das SSE-Log wirkt "tot" obwohl der Job läuft.
    # Nicht-Python-Interpreter (z.B. bash, wo "-u" nounset heißt) setzen
    # "interpreter_args" in COMMANDS explizit.
    interp_args = cmd.get("interpreter_args", ["-u"])
    if "module" in cmd:
        argv = [cmd["interpreter"](), *interp_args, "-m", cmd["module"], *cmd.get("fixed_args", [])]
    else:
        argv = [cmd["interpreter"](), *interp_args, cmd["script"], *cmd.get("fixed_args", [])]

    for entry in schema:
        kind = entry[0]
        name = entry[1]
        value = (params or {}).get(name)
        if kind == "positional_required":
            # str(value).strip(): auch ein Nur-Leerzeichen-Topic aus dem
            # Textfeld zählt als fehlend, statt als "  " beim CLI zu landen.
            if value is None or not str(value).strip():
                raise ValidationError(f"Parameter '{name}' ist erforderlich")
            argv.append(str(value).strip())
        elif kind == "flag":
            cli_flag = entry[2]
            if value not in (None, ""):
                argv.append(cli_flag)
                argv.append(str(value))
        elif kind == "boolflag":
            cli_flag = entry[2]
            if value:
                argv.append(cli_flag)

    return argv, cmd["cwd"]


class Job:
    def __init__(self, job_id: str, command_id: str, argv: list[str] | None, cwd: str | None, kind: str,
                 checkpoints_dir: str | None = None):
        self.job_id = job_id
        self.command_id = command_id
        self.argv = argv
        self.cwd = cwd
        self.kind = kind
        # series/<slug>/output/.checkpoints — vorab aufgelöst (statt im
        # Polling-Thread zu raten), da mehrere Serien parallel existieren
        # können und "podcast_output/" seit der Serien-Migration nicht mehr
        # der feste Pfad ist.
        self.checkpoints_dir = checkpoints_dir
        self.state = "running"  # running | done | error
        self.returncode = None
        self.started_at = time.time()
        self.buffer: list[dict] = []
        self.subscribers: list[queue.Queue] = []
        self.process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._stop_polling = False

    def _emit(self, event: str, data: dict):
        payload = {"event": event, "data": data}
        with self._lock:
            self.buffer.append(payload)
            if len(self.buffer) > MAX_BUFFER_LINES:
                self.buffer = self.buffer[-MAX_BUFFER_LINES:]
            subs = list(self.subscribers)
        for sub in subs:
            sub.put(payload)

    def subscribe(self) -> queue.Queue:
        q = queue.Queue()
        with self._lock:
            for payload in self.buffer:
                q.put(payload)
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def _log(self, line: str):
        self._emit("log", {"line": line})

    def run(self):
        if self.kind == "pyfunc":
            self._run_pyfunc()
            return

        if self.command_id in AUTO_TTS_COMMANDS:
            import tts_control
            self._log("── Qwen3-TTS wird für die Vertonung benötigt ──")
            if not tts_control.start_tts(log=self._log):
                self.state = "error"
                self._emit("done", {"returncode": -1})
                return

        self._run_subprocess()

        if self.command_id in AUTO_TTS_COMMANDS:
            import tts_control
            self._log("── Vertonung fertig, stoppe Qwen3-TTS wieder ──")
            tts_control.stop_tts(log=self._log)
            self._emit("done", {"returncode": self.returncode})

    def _run_pyfunc(self):
        func = resolve_pyfunc(COMMANDS[self.command_id]["pyfunc"])
        try:
            ok = func(log=self._log)
        except Exception as exc:
            self._log(f"❌ Fehler: {exc}")
            ok = False
        self.state = "done" if ok else "error"
        self.returncode = 0 if ok else 1
        self._emit("done", {"returncode": self.returncode})

    def _run_subprocess(self):
        try:
            self.process = subprocess.Popen(
                self.argv, cwd=self.cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=1, text=True,
                # Eigene Prozessgruppe: batch.py/generate_episode.py starten
                # selbst wieder Subprozesse — kill() muss die ganze Gruppe
                # beenden, sonst laufen die Enkel nach "Abbrechen" weiter.
                start_new_session=(os.name != "nt"),
                # PYTHONUNBUFFERED (statt nur "-u") vererbt sich auch an
                # Python-Subprozesse, die dieses Skript selbst wieder startet
                # (z.B. batch.py -> podcast_maker.py) — "-u" allein wirkt nur
                # auf den direkt gestarteten Interpreter, nicht auf Enkel.
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except OSError as exc:
            self.state = "error"
            self._log(f"❌ Start fehlgeschlagen: {exc}")
            self._emit("done", {"returncode": -1})
            return

        checkpoint_thread = None
        if self.checkpoints_dir:
            checkpoint_thread = threading.Thread(target=self._poll_checkpoints, daemon=True)
            checkpoint_thread.start()

        try:
            buf = ""
            assert self.process.stdout is not None
            while True:
                chunk = self.process.stdout.read(1)
                if chunk == "" and self.process.poll() is not None:
                    break
                if chunk in ("\n", "\r"):
                    if buf.strip():
                        self._handle_line(buf)
                    buf = ""
                elif chunk:
                    buf += chunk
            if buf.strip():
                self._handle_line(buf)

            self.returncode = self.process.wait()
            self.state = "done" if self.returncode == 0 else "error"
        except Exception as exc:
            # Ohne dieses Netz stirbt der Job-Thread hier stillschweigend:
            # state bleibt "running", nie kommt ein "done"-Event an — jeder
            # SSE-Subscriber (stream() blockiert auf q.get()) hängt für immer.
            self.state = "error"
            self._log(f"❌ Interner Fehler beim Lesen der Job-Ausgabe: {exc}")
            if self.process.poll() is None:
                try:
                    if os.name != "nt":
                        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    else:
                        self.process.terminate()
                except (ProcessLookupError, PermissionError, OSError):
                    pass
            self.returncode = self.process.poll()
        finally:
            if checkpoint_thread:
                self._stop_polling = True

        # done-Event: bei AUTO_TTS_COMMANDS erst nach dem TTS-Stop in run()
        # emittieren, damit der Log-Stream sauber durchläuft; sonst hier.
        if self.command_id not in AUTO_TTS_COMMANDS:
            self._emit("done", {"returncode": self.returncode})

    def _handle_line(self, line: str):
        self._log(line)
        if self.kind == "cr_steps":
            m = STEP_RE.match(line)
            if m:
                self._emit("step", {"step": int(m.group(1)), "label": m.group(2).strip()})
        m = EPISODE_RE.match(line)
        if m:
            self._emit("episode", {"current": int(m.group(1)), "total": int(m.group(2)),
                                   "name": m.group(3).strip()})

    def _poll_checkpoints(self):
        """Für podcast_maker.py: pollt series/<slug>/output/.checkpoints/ und
        meldet die Anzahl vorhandener Chunk-Dateien als groben Live-Fortschritt,
        statt eine erfundene Prozentzahl aus \\r-Text zu parsen."""
        checkpoints_dir = self.checkpoints_dir
        last_count = -1
        while not self._stop_polling:
            count = 0
            active_part = None
            if checkpoints_dir and os.path.isdir(checkpoints_dir):
                try:
                    parts = sorted(os.listdir(checkpoints_dir))
                    if parts:
                        active_part = parts[-1]
                        part_dir = os.path.join(checkpoints_dir, active_part)
                        count = len([f for f in os.listdir(part_dir) if f.endswith(".wav")])
                except OSError:
                    pass
            if count != last_count:
                self._emit("progress", {"part": active_part, "chunks": count})
                last_count = count
            time.sleep(1)


MAX_RETAINED_JOBS = 100  # verhindert unbegrenztes Wachstum von _jobs über die Serverlaufzeit
KILL_ESCALATE_SECONDS = 5  # SIGTERM -> SIGKILL-Frist für Prozessbäume, die SIGTERM ignorieren


class JobRegistry:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._running_by_command: dict[str, str] = {}
        self._lock = threading.Lock()

    def is_running(self, command_id: str) -> bool:
        with self._lock:
            job_id = self._running_by_command.get(command_id)
            if not job_id:
                return False
            job = self._jobs.get(job_id)
            return bool(job and job.state == "running")

    def start(self, command_id: str, params: dict) -> str:
        argv, cwd = build_argv(command_id, params)

        job_id = uuid.uuid4().hex[:12]
        kind = COMMANDS[command_id]["kind"]
        checkpoints_dir = None
        if COMMANDS[command_id].get("poll_checkpoints"):
            series_dir = series_dir_for((params or {}).get("series")) or current_series_dir()
            if series_dir:
                checkpoints_dir = os.path.join(series_dir, OUTPUT_RELPATH, ".checkpoints")
        job = Job(job_id, command_id, argv, cwd, kind, checkpoints_dir=checkpoints_dir)

        # Check-and-register muss ATOMAR sein (ein Lock-Block, nicht
        # is_running() + separater with-Block) — sonst können zwei parallele
        # Requests für dieselbe command_id beide die Prüfung passieren, bevor
        # eine von beiden sich einträgt, und zwei Subprozesse für denselben
        # Slot spawnen.
        with self._lock:
            running_id = self._running_by_command.get(command_id)
            running_job = self._jobs.get(running_id) if running_id else None
            if running_job and running_job.state == "running":
                raise ValidationError(f"'{command_id}' läuft bereits")
            self._jobs[job_id] = job
            self._running_by_command[command_id] = job_id
            self._prune_locked()

        thread = threading.Thread(target=job.run, daemon=True)
        thread.start()
        return job_id

    def _prune_locked(self):
        """Entfernt die ältesten ABGESCHLOSSENEN Jobs, sobald _jobs über
        MAX_RETAINED_JOBS wächst — jeder Job trägt bis zu MAX_BUFFER_LINES
        Zeilen Buffer, ohne diese Grenze wächst der Speicherverbrauch über
        die Serverlaufzeit unbegrenzt. Muss unter self._lock aufgerufen
        werden. Läuft nie laufenden Jobs weg."""
        if len(self._jobs) <= MAX_RETAINED_JOBS:
            return
        finished = sorted(
            (j for j in self._jobs.values() if j.state != "running"),
            key=lambda j: j.started_at,
        )
        excess = len(self._jobs) - MAX_RETAINED_JOBS
        for job in finished[:excess]:
            del self._jobs[job.job_id]

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    @staticmethod
    def _signal_process_group(process: subprocess.Popen, sig: int):
        """Schickt sig an die ganze Prozessgruppe (siehe start_new_session in
        _run_subprocess — batch.py/generate_episode.py starten selbst wieder
        Subprozesse, ein Signal nur an den direkten Kindprozess ließe die
        Enkel weiterlaufen). Fällt auf den einzelnen Prozess zurück, wenn die
        Gruppe nicht (mehr) ansprechbar ist. Nur für os.name != "nt" — unter
        Windows gibt es keine Prozessgruppen-Signale, siehe kill()."""
        try:
            os.killpg(os.getpgid(process.pid), sig)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.terminate()
            except (ProcessLookupError, OSError):
                pass

    def kill(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or not job.process:
            return False
        if os.name != "nt":
            self._signal_process_group(job.process, signal.SIGTERM)
        else:
            job.process.terminate()

        def _escalate():
            time.sleep(KILL_ESCALATE_SECONDS)
            if job.process.poll() is None:
                if os.name != "nt":
                    self._signal_process_group(job.process, signal.SIGKILL)
                else:
                    try:
                        job.process.kill()
                    except (ProcessLookupError, OSError):
                        pass

        threading.Thread(target=_escalate, daemon=True).start()
        return True

    def snapshot(self) -> dict:
        with self._lock:
            result = {}
            for command_id, job_id in self._running_by_command.items():
                job = self._jobs.get(job_id)
                if job:
                    result[command_id] = {
                        "job_id": job_id,
                        "state": job.state,
                        "started_at": job.started_at,
                    }
            return result

    def stream(self, job_id: str):
        """Generator für eine SSE-Response: liest Events aus der Job-Queue
        (inkl. Replay des bisherigen Buffers) bis das done-Event kommt."""
        job = self.get(job_id)
        if not job:
            yield "event: error\ndata: {}\n\n"
            return
        q = job.subscribe()
        try:
            while True:
                payload = q.get()
                yield f"event: {payload['event']}\ndata: {json.dumps(payload['data'])}\n\n"
                if payload["event"] == "done":
                    break
        finally:
            job.unsubscribe(q)
