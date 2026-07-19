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
import subprocess
import threading
import time
import uuid

import psutil

from config import AUTO_TTS_COMMANDS, COMMANDS, current_series_dir, series_dir_for, OUTPUT_RELPATH


def _process_tree(pid: int) -> list:
    """Elternprozess + ALLE Nachkommen, rekursiv über die echte Eltern-Kind-Beziehung
    im Betriebssystem ermittelt (psutil), NICHT über Prozessgruppen-Mitgliedschaft.

    Grund: fabrik/core/claude_cli.py::run_claude_process startet jeden claude-Aufruf
    bewusst in einer EIGENEN Prozessgruppe (start_new_session=True), damit ein interner
    Timeout-Kill dort gezielt nur claude + seine Kindprozesse trifft, nie den
    aufrufenden Python-Prozess selbst (siehe dessen Docstring). Das heißt aber: ein
    laufender claude-Aufruf hängt NICHT mehr automatisch an der Prozessgruppe von
    create_series.py/generate_episode.py — ein reines os.killpg() auf die Gruppe des
    Jobs würde einen gerade laufenden claude-Unterprozess beim Abbrechen übersehen und
    im Hintergrund weiterlaufen lassen. Die rekursive Kindprozess-Suche über psutil
    findet ihn trotzdem, weil sie der echten Prozess-Hierarchie folgt statt der
    Gruppen-Zugehörigkeit."""
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return []
    try:
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    return [parent, *children]


def _signal_tree(pid: int, hard: bool = False):
    """Schickt SIGTERM (hard=False) oder SIGKILL (hard=True) an pid + alle
    Nachkommen (siehe _process_tree). Einzelne bereits verschwundene oder
    unzugängliche Prozesse werden stillschweigend übersprungen — das Gesamtbild
    (möglichst viel vom Baum beenden) ist wichtiger als ein einzelner Fehlschlag."""
    for proc in _process_tree(pid):
        try:
            proc.kill() if hard else proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

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
        elif kind == "boolflag_off":
            # Invertierte Checkbox für CLI-Flags mit Default AN (z.B. --fix seit
            # 17.07.2026): Checkbox angehakt = Default gilt (nichts anhängen),
            # ABGEWÄHLT = Abschalt-Flag (z.B. --no-fix) anhängen.
            #
            # FEHLENDER Schlüssel ist NICHT dasselbe wie "abgewählt" (Bugfix
            # 17.07.2026): schickt ein Client das Feld gar nicht mit, gilt der
            # CLI-Default, es wird nichts angehängt. Vorher hängte `if not value`
            # auch bei value=None das Abschalt-Flag an — ein Browser-Tab mit dem
            # HTML von VOR der Einführung von `data-param-fix` (Template-Edits
            # greifen erst beim Reload, siehe webui/CLAUDE.md) schickte 'fix'
            # nicht mit und schaltete damit die Reparatur still ab, obwohl die
            # Checkbox sichtbar angehakt war. Ergebnis in Produktion: drei frisch
            # erzeugte Serien mit zusammen 42 korrekt geflaggten, aber nie
            # applizierten Review-Befunden — der Default war de facto invertiert.
            # Gegenprobe: {'fix': True} -> kein Flag, {'fix': False} -> --no-fix,
            # {} -> kein Flag (vorher: --no-fix).
            cli_flag = entry[2]
            if name in (params or {}) and not value:
                argv.append(cli_flag)

    return argv, cmd["cwd"]


class Job:
    def __init__(self, job_id: str, command_id: str, argv: list[str] | None, cwd: str | None, kind: str,
                 checkpoints_dir: str | None = None, series: str | None = None):
        self.job_id = job_id
        self.command_id = command_id
        self.argv = argv
        self.cwd = cwd
        self.kind = kind
        # Nur für snapshot()/die WebUI-Anzeige (welche Serie läuft gerade
        # unter diesem Kommando) — die eigentliche Serien-Auflösung für den
        # Subprozess passiert längst über argv (--series-Flag).
        self.series = series
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
            # try/except um start/stop: wirft tts_control eine Exception,
            # terminiert dieser Thread sonst OHNE "done"-Event — und jeder
            # SSE-Subscriber hinge für immer in q.get() (Stream ohne Timeout).
            try:
                started = tts_control.start_tts(log=self._log)
            except Exception as exc:
                self._log(f"❌ TTS-Start fehlgeschlagen: {exc}")
                started = False
            if not started:
                self.state = "error"
                self._emit("done", {"returncode": -1})
                return

        self._run_subprocess()

        if self.command_id in AUTO_TTS_COMMANDS:
            import tts_control
            self._log("── Vertonung fertig, stoppe Qwen3-TTS wieder ──")
            try:
                tts_control.stop_tts(log=self._log)
            except Exception as exc:
                self._log(f"⚠️ TTS-Stopp fehlgeschlagen: {exc}")
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
                if os.name != "nt":
                    _signal_tree(self.process.pid)
                else:
                    try:
                        self.process.terminate()
                    except (ProcessLookupError, OSError):
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


_TTS_LOCK_KEY = "__tts__"  # ein gemeinsamer Schlüssel für ALLE AUTO_TTS_COMMANDS


def _lock_key(command_id: str, params: dict) -> str:
    """Eindeutigkeits-Schlüssel für die 'läuft bereits'-Sperre.

    AUTO_TTS_COMMANDS teilen sich den EINEN lokalen TTS-Prozess (Pinokio/
    Qwen3) — tts_control.start_tts()/stop_tts() sind nicht Refcount-fähig,
    zwei gleichzeitige TTS-gebundene Jobs würden sich gegenseitig den Server
    unter den Füßen wegziehen (Job A beendet, stoppt TTS, während Job B noch
    synthetisiert). Alle Mitglieder von AUTO_TTS_COMMANDS teilen sich deshalb
    EINEN gemeinsamen Schlüssel (nicht command_id-spezifisch — sonst könnten
    z.B. pf_batch und pf_podcast_maker trotzdem gleichzeitig laufen), GLOBAL
    über alle Serien.

    Alle anderen pf_*-Kommandos (Skripte schreiben, Bild-Prompts, Cover,
    Thumbnails, SFX-Plan, ...) sind reine `claude`-CLI-Aufrufe pro Serie ohne
    geteilte Ressource — der Schlüssel wird zusätzlich nach 'series'
    aufgeschlüsselt, damit z.B. zwei Serien gleichzeitig Skripte schreiben
    können, statt sich global zu blockieren."""
    if command_id in AUTO_TTS_COMMANDS:
        return _TTS_LOCK_KEY
    series = (params or {}).get("series") or ""
    return f"{command_id}::{series}" if series else command_id


class JobRegistry:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._running_by_key: dict[str, str] = {}
        self._lock = threading.Lock()

    def start(self, command_id: str, params: dict) -> str:
        argv, cwd = build_argv(command_id, params)

        job_id = uuid.uuid4().hex[:12]
        kind = COMMANDS[command_id]["kind"]
        checkpoints_dir = None
        if COMMANDS[command_id].get("poll_checkpoints"):
            series_dir = series_dir_for((params or {}).get("series")) or current_series_dir()
            if series_dir:
                checkpoints_dir = os.path.join(series_dir, OUTPUT_RELPATH, ".checkpoints")
        job = Job(job_id, command_id, argv, cwd, kind, checkpoints_dir=checkpoints_dir,
                 series=(params or {}).get("series"))

        # Check-and-register muss ATOMAR sein (ein Lock-Block, nicht
        # is_running() + separater with-Block) — sonst können zwei parallele
        # Requests für denselben lock_key beide die Prüfung passieren, bevor
        # eine von beiden sich einträgt, und zwei Subprozesse für denselben
        # Slot spawnen.
        lock_key = _lock_key(command_id, params)
        with self._lock:
            running_id = self._running_by_key.get(lock_key)
            running_job = self._jobs.get(running_id) if running_id else None
            if running_job and running_job.state == "running":
                series = (params or {}).get("series")
                is_series_scoped = lock_key == f"{command_id}::{series}"
                if is_series_scoped:
                    detail = f" für Serie '{series}'"
                elif running_job.command_id != command_id:
                    # Globale Sperre (z.B. TTS), aber ein ANDERES Kommando
                    # hält sie gerade — sonst klingt die Meldung wie ein
                    # Selbst-Konflikt, obwohl z.B. pf_batch pf_podcast_maker
                    # blockiert (geteilter lokaler TTS-Prozess).
                    detail = (f" (blockiert durch '{running_job.command_id}'"
                             f"{f' für Serie {running_job.series!r}' if running_job.series else ''})")
                else:
                    detail = ""
                raise ValidationError(f"'{command_id}' läuft bereits{detail}")
            self._jobs[job_id] = job
            self._running_by_key[lock_key] = job_id
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

    def kill(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or not job.process:
            return False
        if os.name != "nt":
            # Rekursiver Tree-Kill statt Prozessgruppe (siehe _process_tree):
            # erreicht auch verschachtelte claude-Aufrufe, die sich bewusst in
            # eine eigene Gruppe ausgeklinkt haben.
            _signal_tree(job.process.pid)
        else:
            job.process.terminate()

        def _escalate():
            time.sleep(KILL_ESCALATE_SECONDS)
            if job.process.poll() is None:
                if os.name != "nt":
                    # Baum neu ermitteln statt den von oben wiederzuverwenden —
                    # zwischenzeitlich könnten neue Kindprozesse entstanden sein,
                    # und bereits beendete sind ohnehin kein Problem (siehe
                    # _signal_tree's NoSuchProcess-Handling).
                    _signal_tree(job.process.pid, hard=True)
                else:
                    try:
                        job.process.kill()
                    except (ProcessLookupError, OSError):
                        pass

        threading.Thread(target=_escalate, daemon=True).start()
        return True

    def snapshot(self) -> dict:
        """Läuft aktuell etwas, geschlüsselt nach `_lock_key()` — bei
        AUTO_TTS_COMMANDS ist das schlicht der command_id (global, wie
        bisher; bestehende Leser wie status.py greifen unverändert per
        `running_commands.get("pf_batch", ...)` darauf zu). Bei allen
        anderen pf_*-Kommandos ist der Schlüssel `"<command_id>::<series>"`
        — mehrere Serien können also gleichzeitig unter demselben
        command_id auftauchen; jeder Eintrag trägt zusätzlich `command_id`/
        `series`, damit die WebUI pro Button UND pro Serie den richtigen
        Lauf erkennt (`app.js::syncRunningJobs`)."""
        with self._lock:
            result = {}
            for lock_key, job_id in self._running_by_key.items():
                job = self._jobs.get(job_id)
                if job:
                    result[lock_key] = {
                        "job_id": job_id,
                        "command_id": job.command_id,
                        "series": job.series,
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
