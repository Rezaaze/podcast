"""Model-Adapter über die `claude`-CLI (Abo-Auth, kein API-Key) — erfüllt das Model-Protokoll.

Alternative zu ``anthropic_model.py`` für Nutzer, die über ihr Claude-**Abo** laufen
wollen (``claude -p`` als Subprozess) statt über das SDK + API-Billing. Bewusst
selbst-enthalten: KEIN Import aus ``fabrik/`` — der Rewrite bleibt isoliert (§2). Die
CLI-Plumbing (stdin-DEVNULL-Gotcha, Heartbeat, JSON-Scavenging) ist hier eigenständig
nachgebaut.

Trade-off ggü. §10.8: die CLI erzwingt KEIN Schema. Statt garantiert parsebarem JSON
holen wir das längste gültige ``{…}`` aus der Textantwort (Scavenging, wie im Altsystem).
Der ``retry.py``-Loop über dem Modell prüft den *Inhalt*; dieses Modul kümmert sich um
den *Transport*: es retryt transiente Fehler (Timeout, leere/unparsebare Antwort) intern
ein paar Mal, bevor es aufgibt — nur „not logged in"/„not found" brechen sofort ab.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from factory.core.model import StructuredOutputError

# Light-vs-Heavy (§ Stage B). Bewusst auf "sonnet" GEPINNT statt None (= impliziter
# CLI-Default): Der Default kann sich mit einer neuen CLI-Version oder einem Plan-Wechsel
# ändern, und ein stiller Sprung auf ein teureres Modell würde auf dem Abo-Pfad unbemerkt
# Kontingent verbrennen. Explizit > implizit, wenn Kosten dranhängen.
# Weitere Ersparnis wäre {"cheap": "haiku"} für Reviews/Metadaten — Abwägung: In der
# 12-Serien-Analyse des Altsystems wurde ein schwächeres Review-Modell praktisch blind
# (8/8 leere Reviews trotz 25 realer Fehler). Deshalb hier NICHT vorschnell heruntergestuft.
TIER_MODELS: Dict[str, Optional[str]] = {"strong": "sonnet", "cheap": "sonnet"}

HEARTBEAT_SECONDS = 20
DEFAULT_TIMEOUT = 600           # ein einzelner Kreativ-Call kann Minuten dauern
KILL_JOIN_GRACE_SECONDS = 10
TRANSIENT_RETRIES = 3           # transiente Transport-Fehler intern, bevor fatal

_JSON_INSTRUCTION = (
    "\n\nReturn ONLY a single JSON object that conforms to this JSON schema. "
    "No prose, no markdown fences, no commentary before or after — just the object.\n"
    "SCHEMA:\n"
)


class ClaudeCliNotAvailable(StructuredOutputError):
    """`claude` fehlt oder ist nicht eingeloggt — unrecoverable, nie retryen."""


class ClaudeCliModel:
    """Konkrete Model-Implementierung über ``claude -p``. Liefert ein schema-nahes dict.

    Erzwingt das Schema nicht serverseitig — der ``retry.py``-Loop darüber validiert den
    Inhalt. Transiente Transportfehler werden intern ``transient_retries``-mal wiederholt.
    """

    def __init__(
        self,
        *,
        cli_path: str = "claude",
        tier_models: Optional[Dict[str, Optional[str]]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        heartbeat_seconds: int = HEARTBEAT_SECONDS,
        transient_retries: int = TRANSIENT_RETRIES,
        extra_args: Optional[List[str]] = None,
    ) -> None:
        self.cli_path = cli_path
        self.tier_models = dict(tier_models or TIER_MODELS)
        self.timeout = timeout
        self.heartbeat_seconds = heartbeat_seconds
        self.transient_retries = max(1, transient_retries)
        self.extra_args = list(extra_args or [])

    def _model_for(self, tier: str) -> Optional[str]:
        if tier not in self.tier_models:
            raise ValueError(f"unknown tier {tier!r}; known: {sorted(self.tier_models)}")
        return self.tier_models[tier]

    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        *,
        tier: str = "strong",
    ) -> Dict[str, Any]:
        full_prompt = prompt + _JSON_INSTRUCTION + json.dumps(schema)
        argv = [self.cli_path, "-p", full_prompt, "--output-format", "text"]
        model = self._model_for(tier)
        if model:
            argv += ["--model", model]
        argv += self.extra_args

        last_detail = ""
        for attempt in range(1, self.transient_retries + 1):
            label = f"claude:{tier}#{attempt}"
            try:
                completed = self._run(argv, label)
            except FileNotFoundError as exc:
                raise ClaudeCliNotAvailable(f"`{self.cli_path}` not found: {exc}") from exc
            except subprocess.TimeoutExpired:
                last_detail = f"timeout after {self.timeout}s"
                continue

            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            if completed.returncode != 0:
                low = (stderr + stdout).lower()
                if "not logged in" in low or "401" in low or "please run" in low and "login" in low:
                    raise ClaudeCliNotAvailable(f"claude not logged in: {stderr.strip()[:200]}")
                last_detail = f"exit {completed.returncode}: {stderr.strip()[:200]}"
                continue

            obj = _parse_json_response(stdout)
            if obj is None:
                last_detail = "no parseable JSON object in CLI output"
                continue
            if not isinstance(obj, dict):
                last_detail = f"CLI output was not a JSON object: {type(obj).__name__}"
                continue
            return obj

        raise StructuredOutputError(
            f"claude CLI produced no usable JSON after {self.transient_retries} attempts: {last_detail}"
        )

    def _run(self, argv: List[str], label: str) -> subprocess.CompletedProcess:
        """subprocess.run()-Ersatz mit stdin=DEVNULL-Gotcha + Heartbeat + Timeout-Kill."""
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, stdin=subprocess.DEVNULL,
            start_new_session=(os.name != "nt"),
        )
        out: Dict[str, str] = {}

        def _wait() -> None:
            out["stdout"], out["stderr"] = proc.communicate()

        worker = threading.Thread(target=_wait, daemon=True)
        worker.start()
        start = time.time()
        while worker.is_alive():
            worker.join(timeout=self.heartbeat_seconds)
            if worker.is_alive():
                elapsed = int(time.time() - start)
                if elapsed >= self.timeout:
                    _kill_process_tree(proc)
                    worker.join(timeout=KILL_JOIN_GRACE_SECONDS)
                    raise subprocess.TimeoutExpired(argv, self.timeout)
                print(f"  ⏳ {label} … noch dabei ({elapsed}s, Timeout bei {self.timeout}s)", flush=True)

        return subprocess.CompletedProcess(
            argv, proc.returncode, out.get("stdout", ""), out.get("stderr", "")
        )


def _kill_process_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name != "nt":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:  # pragma: no cover
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def _strip_markdown_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
    return raw


def _json_candidates(text: str):
    """Dekodiert ab JEDER '{'-Position genau EINEN Wert (raw_decode) — toleriert Text
    oder Beispiel-Fragmente ums eigentliche Objekt herum."""
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            obj, end = decoder.raw_decode(text, idx)
            yield idx, end, obj
        except json.JSONDecodeError:
            pass
        idx = text.find("{", idx + 1)


def _parse_json_response(raw: str) -> Optional[Any]:
    """Längstes gültiges JSON-Objekt aus der Textantwort (wie fabrik). None wenn keins."""
    stripped = _strip_markdown_fences(raw)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    best: Optional[Tuple[int, Any]] = None
    for start, end, obj in _json_candidates(stripped):
        span = end - start
        if best is None or span > best[0]:
            best = (span, obj)
    return best[1] if best else None
