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


def _json_candidates(text: str):
    """Versucht ab JEDER '{'-Position in text einen JSON-Wert zu dekodieren
    (json.JSONDecoder.raw_decode -- liest genau EINEN Wert und ignoriert
    alles danach, im Gegensatz zu json.loads). Liefert pro Position ein
    (start, end, obj, error)-Tupel: bei Erfolg end/obj gesetzt und error
    None, bei Fehlschlag end/obj None und error das JSONDecodeError.

    Grund für "jede Position" statt nur der ersten '{': ein Modell hält sich
    trotz gegenteiliger Anweisung manchmal nicht an "nur JSON, kein
    Kommentar" und schreibt vorher ein kurzes Beispiel-Fragment, das selbst
    eine '{' enthält (z.B. ein einzelnes section_words-Objekt als
    Illustration) -- die erste '{' im Text ist dann NICHT die des
    eigentlich gemeinten Objekts. Geteilt zwischen parse_json_response()
    (nimmt die längste erfolgreiche Kandidatur) und describe_json_error()
    (zeigt den Fehler der am weitesten gekommenen Kandidatur, wenn keine
    einzige erfolgreich war)."""
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            obj, end = decoder.raw_decode(text, idx)
            yield idx, end, obj, None
        except json.JSONDecodeError as e:
            yield idx, None, None, e
        idx = text.find("{", idx + 1)


def parse_json_response(raw: str):
    """Extrahiert ein JSON-Objekt aus einer Claude-Textantwort (toleriert
    Markdown-Codefences, Text/Beispiel-Fragmente mit eigenen '{}' drumherum
    -- siehe _json_candidates()). Von allen an irgendeiner '{'-Position
    erfolgreich dekodierten Kandidaturen wird die LÄNGSTE genommen: das
    eigentlich gemeinte (volle) Objekt ist praktisch immer um Größenordnungen
    länger als ein kurzes Beispiel-Fragment. Gibt None zurück statt zu
    werfen — Aufrufer entscheiden selbst, ob ein Retry sinnvoll ist."""
    raw = _strip_markdown_fences(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    best = None  # (span, obj)
    for start, end, obj, error in _json_candidates(raw):
        if error is not None:
            continue
        span = end - start
        if best is None or span > best[0]:
            best = (span, obj)
    return best[1] if best else None


def describe_json_error(raw: str) -> Optional[str]:
    """Diagnose-Ergänzung zu parse_json_response(): wenn KEINE '{'-Kandidatur
    (siehe _json_candidates()) erfolgreich dekodiert, liefert diese Funktion
    eine lesbare Fehlermeldung MIT Position und einem Kontext-Fenster um die
    Fehlerstelle der am weitesten gekommenen Kandidatur (deren Fehlerposition
    am größten ist) — bei einer mehrere tausend Zeichen langen Antwort liegt
    ein Syntaxfehler oft mitten im Dokument, wo weder Anfang noch Ende der
    Antwort (die sonst übliche Diagnose) etwas verraten. Gibt None zurück,
    wenn gar keine '{' gefunden wurde ODER irgendeine Kandidatur tatsächlich
    erfolgreich dekodiert (dann liefert parse_json_response() bereits ein
    Ergebnis und dieser Fehlerpfad wird gar nicht erst aufgerufen)."""
    stripped = _strip_markdown_fences(raw)

    candidates = list(_json_candidates(stripped))
    if not candidates:
        return None
    if any(error is None for _s, _e, _o, error in candidates):
        return None

    # err.pos ist absolut in `stripped` (raw_decode(text, idx) zählt Positionen
    # relativ zum GESAMTEN text, nicht relativ zu idx) -- die am weitesten
    # gekommene Kandidatur ist die mit dem größten err.pos.
    err = max((c[3] for c in candidates), key=lambda e: e.pos)
    window_start = max(0, err.pos - 100)
    window_end = min(len(stripped), err.pos + 100)
    window = stripped[window_start:window_end]
    return (f"JSON-Fehler: {err.msg} (Zeile {err.lineno}, Spalte {err.colno}, "
            f"Zeichen {err.pos} von {len(stripped)}):\n            ...{window}...")
