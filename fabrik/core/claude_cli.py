"""Gemeinsamer Subprocess-Runner + JSON-Antwort-Parser für 'claude -p ...'-Aufrufe.

stdlib-only (wie der Rest von fabrik/core) — sicher überall importierbar,
auch ohne .venv. Wird von fabrik/cli/create_series.py und
fabrik/writing/script_writer.py genutzt (beide brauchen nur die claude-CLI,
kein venv)."""

import json
import re
import subprocess
import threading
import time
from typing import Optional

HEARTBEAT_SECONDS = 20


def run_claude_process(argv, timeout, label, heartbeat_seconds=HEARTBEAT_SECONDS):
    """Wie subprocess.run(), aber druckt alle heartbeat_seconds eine
    Lebenszeichen-Zeile, solange der Prozess noch läuft. Ein einzelner
    claude-Aufruf kann bei viel Text mehrere Minuten dauern und gibt von
    sich aus NICHTS aus, bis er fertig ist ('--output-format text' ist
    nicht-streamend) — ohne diesen Heartbeat sieht die Konsole/WebUI in der
    Zwischenzeit nichts und kann nicht unterscheiden, ob Claude noch
    arbeitet oder der Prozess hängt.

    Läuft proc.communicate() in einem Hintergrund-Thread (übernimmt sicheres
    gleichzeitiges Ausleeren von stdout/stderr, kein Deadlock-Risiko durch
    volle Pipe-Puffer) und pollt von hier aus nur, ob der Thread noch lebt.
    Wirft subprocess.TimeoutExpired wie subprocess.run() bei Zeitüberschreitung."""
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, stdin=subprocess.DEVNULL,
    )
    output = {}

    def _wait():
        output["stdout"], output["stderr"] = proc.communicate()

    worker = threading.Thread(target=_wait, daemon=True)
    worker.start()

    start = time.time()
    while worker.is_alive():
        worker.join(timeout=heartbeat_seconds)
        if worker.is_alive():
            elapsed = int(time.time() - start)
            if elapsed >= timeout:
                proc.kill()
                worker.join()
                raise subprocess.TimeoutExpired(argv, timeout)
            print(f"  ⏳ {label} … noch dabei ({elapsed}s vergangen, Timeout bei {timeout}s)", flush=True)

    return subprocess.CompletedProcess(argv, proc.returncode, output.get("stdout", ""), output.get("stderr", ""))


def _strip_markdown_fences(raw: str) -> str:
    """Entfernt einen umschließenden Markdown-Codefence-Block (```json ... ```
    o.ä.), falls vorhanden. Geteilt zwischen parse_json_response() und
    describe_json_error(), damit beide immer dieselbe Kandidatur sehen."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
    return raw


def parse_json_response(raw: str):
    """Extrahiert ein JSON-Objekt aus einer Claude-Textantwort (toleriert
    Markdown-Codefences und Text drumherum, versucht notfalls den größten
    {...}-Block). Gibt None zurück statt zu werfen — Aufrufer entscheiden
    selbst, ob ein Retry sinnvoll ist."""
    raw = _strip_markdown_fences(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None


def describe_json_error(raw: str) -> Optional[str]:
    """Diagnose-Ergänzung zu parse_json_response(): wenn die extrahierte {...}-Kandidatur
    an einem echten json.JSONDecodeError scheitert (nicht nur an fehlenden/zusätzlichen
    Markdown-Fences drumherum), liefert diese Funktion eine lesbare Fehlermeldung MIT
    Position und einem Kontext-Fenster um die Fehlerstelle — bei einer mehrere tausend
    Zeichen langen Antwort liegt ein Syntaxfehler oft mitten im Dokument, wo weder Anfang
    noch Ende der Antwort (die sonst übliche Diagnose) etwas verraten. Gibt None zurück,
    wenn gar kein {...}-Block gefunden wurde ODER die Kandidatur tatsächlich valide ist
    (dann ist der Fehler woanders, z.B. reiner Text ohne jedes JSON — Anfang/Ende bleibt
    dort die bessere Diagnose)."""
    stripped = _strip_markdown_fences(raw)

    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    candidate = stripped[start:end + 1]

    try:
        json.loads(candidate)
        return None
    except json.JSONDecodeError as e:
        window_start = max(0, e.pos - 100)
        window_end = min(len(candidate), e.pos + 100)
        window = candidate[window_start:window_end]
        return (f"JSON-Fehler: {e.msg} (Zeile {e.lineno}, Spalte {e.colno}, "
                f"Zeichen {e.pos} von {len(candidate)}):\n            ...{window}...")
