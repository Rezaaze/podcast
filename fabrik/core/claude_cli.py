"""Gemeinsamer Subprocess-Runner + JSON-Antwort-Parser für 'claude -p ...'-Aufrufe.

stdlib-only (wie der Rest von fabrik/core) — sicher überall importierbar,
auch ohne .venv. Wird von fabrik/cli/create_series.py und
fabrik/writing/script_writer.py genutzt (beide brauchen nur die claude-CLI,
kein venv)."""

import fcntl
import json
import os
import random
import re
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from typing import Optional

from .paths import DATA_DIR

HEARTBEAT_SECONDS = 20
# Notbremse für den Fall, dass selbst das Töten der ganzen Prozessgruppe (siehe
# _kill_process_tree) die stdout/stderr-Pipes nicht sofort freigibt (z.B. Rechte-
# Probleme, ungewöhnliches Timing) — lieber nach ein paar Sekunden eine klare
# Fehlermeldung als ein zweites Mal für immer hängen.
KILL_JOIN_GRACE_SECONDS = 10

# --- Systemweite Zählsemaphore für gleichzeitige 'claude'-Subprozesse -------
#
# Ursprünglicher Verdacht (16.07.2026): bei mehreren parallel laufenden WebUI-
# Cockpits (je eine Serie) feuert JEDES Cockpit intern schon eigene
# Parallelität ab (create_series' BATCH_PARALLEL_CAP=4, generate_episode.py's
# --jobs sowie script_writer.py's SECTION_PARALLEL_CAP=4 bei aktiven Beats) —
# diese Caps kennen sich gegenseitig nicht, sind pro Prozess gedacht. Bei 3
# Cockpits können so 10-15+ 'claude'-Prozesse gleichzeitig denselben Account
# treffen, was wie zufälliges Verhalten wirkte (mal schnell, mal Abbruch).
# GEPRÜFT und NICHT bestätigt: die komplette Log-Historie eines echten
# Mehr-Cockpit-Laufs (create_series + generate_episode + Reviews +
# Thumbnails, ~2000 Zeilen, teils 8+ parallele claude-Prozesse) zeigte KEINE
# einzige Rate-Limit-/429-/"overloaded"-Meldung — das tatsächliche Problem
# jener Session war abgeschnittenes JSON bei zu großen Batches (siehe
# generate_batch_with_retry()), keine Account-Drosselung. Diese Semaphore
# bleibt trotzdem als billige Notbremse bestehen (siehe
# DEFAULT_MAX_CONCURRENT_CLAUDE unten für die Begründung des hohen Defaults),
# nicht als Beleg für ein tatsächlich beobachtetes Drosselungsproblem.
#
# EIN gemeinsamer Flaschenhals in run_claude_process() (der einzige Ort, an
# dem überhaupt ein 'claude'-Subprozess entsteht — create_series.py UND
# script_writer.py laufen beide hier durch) begrenzt, wie viele 'claude'-
# Prozesse SYSTEMWEIT (über alle Cockpits/Serien/Threads hinweg) gleichzeitig
# laufen dürfen. Wer keinen Slot bekommt, wartet sichtbar (eigene Log-Zeile)
# statt unsichtbar beim Provider zu drosseln. Slot-Dateien statt In-Memory-
# Zähler, weil die Semaphore prozessübergreifend sein muss (Cockpits sind
# eigene Prozesse); fcntl.flock() gibt einen Slot automatisch frei, auch wenn
# der haltende Prozess hart abstürzt/gekillt wird (OS räumt beim Schließen
# des Deskriptors auf) — kein Risiko eines dauerhaft blockierten Slots.
CLAUDE_SLOTS_DIR = os.path.join(DATA_DIR, ".claude_slots")
# 16.07.2026: Startwert 6 war eine reine Vorsichtsmaßnahme OHNE Beleg, dass
# Account-seitige Drosselung tatsächlich auftritt — probehalber gegen die
# komplette Session-Historie eines echten 4-Cockpit-Laufs geprüft (~2000
# Log-Zeilen über create_series + generate_episode + Reviews + Thumbnails,
# mehrere Serien gleichzeitig, teils 8+ parallele claude-Prozesse): KEIN
# einziger Treffer für Rate-Limit/429/"overloaded"/"usage limit" — das
# tatsächliche Problem jener Session war abgeschnittenes JSON bei zu großen
# Batches (siehe generate_batch_with_retry()'s Halbierungs-Logik), nicht
# Account-Drosselung. Ein niedriger Default hätte also nur legitime
# Parallelarbeit gebremst, ohne irgendein reales Problem zu verhindern.
# Deshalb jetzt bewusst hoch angesetzt: eine reine Notbremse gegen einen
# echten Ausreißer (z.B. versehentlich 10+ Cockpits mit hohem --jobs
# gleichzeitig), keine Routine-Drosselung im Alltag mit wenigen Cockpits.
# PF_MAX_CONCURRENT_CLAUDE übersteuert in beide Richtungen, falls doch
# einmal echte Drosselung auftritt (Log-Zeile "Claude-CLI-Fehler"/"API-
# Fehler" mit 429/rate_limit/overloaded im Text — dafür runter regeln)
# oder falls sogar dieser Wert noch zu niedrig ist.
DEFAULT_MAX_CONCURRENT_CLAUDE = 20
_SLOT_POLL_SECONDS = 2
_SLOT_WARN_AFTER_SECONDS = 15  # keine Log-Zeile bei kurzem, normalem Anstehen


def _max_concurrent_claude() -> int:
    try:
        return max(1, int(os.environ.get("PF_MAX_CONCURRENT_CLAUDE", DEFAULT_MAX_CONCURRENT_CLAUDE)))
    except ValueError:
        return DEFAULT_MAX_CONCURRENT_CLAUDE


@contextmanager
def _claude_slot(label: str):
    """Blockiert, bis einer von N Slot-Dateien exklusiv gelockt werden kann —
    N = _max_concurrent_claude(). Zufällige Versuchsreihenfolge vermeidet, dass
    alle wartenden Prozesse dieselbe Slot-Datei 'belagern' (thundering herd auf
    Slot 0). Absichtlich VOR dem Timeout-Fenster des eigentlichen Calls: die
    Wartezeit auf einen Slot zählt nicht gegen dessen TIMEOUT_SECONDS — sonst
    würde die Bremse selbst den Abbruch verursachen, den sie verhindern soll."""
    os.makedirs(CLAUDE_SLOTS_DIR, exist_ok=True)
    n = _max_concurrent_claude()
    wait_start = None
    warned = False
    while True:
        order = list(range(n))
        random.shuffle(order)
        for i in order:
            path = os.path.join(CLAUDE_SLOTS_DIR, f"slot_{i}.lock")
            f = open(path, "a")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                f.close()
                continue
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
            return
        if wait_start is None:
            wait_start = time.time()
        elif not warned and time.time() - wait_start >= _SLOT_WARN_AFTER_SECONDS:
            print(f"  ⏸  {label}: wartet auf einen freien Claude-Aufruf-Slot "
                  f"(alle {n} gleichzeitig belegt — mehrere Serien/Cockpits laufen "
                  f"parallel; PF_MAX_CONCURRENT_CLAUDE zum Anpassen) ...", flush=True)
            warned = True
        time.sleep(_SLOT_POLL_SECONDS)


def _kill_process_tree(proc: subprocess.Popen):
    """Beendet proc UND alle seine Kindprozesse — proc.kill() allein trifft nur den
    direkten claude-Prozess, nicht dessen eigene Subprozesse (claude startet in der
    Praxis selbst wieder Hilfsprozesse). Bleibt so ein Enkelprozess nach proc.kill()
    am Leben und hält das Schreibende der stdout/stderr-Pipe offen, blockiert
    proc.communicate() im Hintergrund-Thread für immer, weil es auf EOF wartet, das
    nie kommt — das war der eigentliche Grund für "Timeout, aber keine Antwort".

    Deshalb startet run_claude_process() den Prozess in einer EIGENEN Prozessgruppe
    (start_new_session=True) statt in der des Aufrufers: os.killpg() trifft dann
    zuverlässig die ganze claude-Nachkommenschaft. Wichtige Kehrseite: dadurch hängt
    dieser Prozessbaum NICHT mehr automatisch an der Prozessgruppe des aufrufenden
    Skripts (create_series.py/script_writer.py) — wer den AUFRUFER von außen abbricht
    (z.B. WebUI "Abbrechen"), muss diesen claude-Baum separat mit-terminieren. Löst
    webui/runner.py::Job.kill() bewusst über eine rekursive Kindprozess-Suche (psutil)
    statt über Prozessgruppen-Vererbung, genau deswegen."""
    if os.name == "nt":
        proc.kill()
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()  # Fallback, falls die Gruppe schon weg ist oder killpg nicht ging


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
    Wirft subprocess.TimeoutExpired wie subprocess.run() bei Zeitüberschreitung —
    siehe _kill_process_tree()'s Docstring für die Prozessgruppen-Begründung.

    Startet den Subprozess erst, sobald ein systemweiter Claude-Aufruf-Slot
    frei ist (siehe _claude_slot() oben) — das Warten auf einen Slot liegt
    bewusst VOR dem Start der Timeout-Uhr, zählt also nicht gegen `timeout`."""
    with _claude_slot(label):
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, stdin=subprocess.DEVNULL,
            start_new_session=(os.name != "nt"),
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
                    _kill_process_tree(proc)
                    worker.join(timeout=KILL_JOIN_GRACE_SECONDS)
                    if worker.is_alive():
                        # Extrem seltener Rand-Fall: Gruppe getötet, Pipes trotzdem noch
                        # offen. Thread bleibt als Daemon im Hintergrund (harmlos, blockiert
                        # den Prozess nicht weiter) — wir geben hier aber sauber auf, statt
                        # ein zweites Mal unbegrenzt zu warten.
                        print(f"  ⚠️  {label}: Prozessgruppe beendet, aber E/A-Thread reagiert "
                              f"nach {KILL_JOIN_GRACE_SECONDS}s immer noch nicht — gebe auf, "
                              f"Antwort wird verworfen.", flush=True)
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
