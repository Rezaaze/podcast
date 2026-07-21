"""Modell-Interface mit erzwungenem structured output (§10.8).

Die größte Einzel-Reduktion inzidenteller Komplexität im Rewrite: ein Interface, das
ein JSON-Schema *erzwingt* und ein validiertes Objekt zurückgibt. Damit entfallen aus
dem Altsystem: JSON-Scavenging ("längstes gültiges {…}"), Heartbeat, der stdin-Trick,
die Slot-Semaphore. "Das JSON parst immer" wird zur Voraussetzung statt zum Kampf.

Was NICHT entfällt (§10.8-Carve-out): der validate→retry→feedback-Loop (retry.py) —
structured output garantiert *parsebares*, nie *korrektes* JSON.

Dieses Modul definiert nur das *Interface* plus ein ``FakeModel`` für deterministische
Tests. Der echte Provider-Adapter ist bewusst separat (austauschbar, §9 "incidental").
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable


class StructuredOutputError(Exception):
    """Rückgabe verletzt das geforderte Schema — nach Provider-Retries unrettbar.

    Für den Aufrufer ist das ein *fatal*-Fall im Sinne von retry.py: würde einen
    Downstream-Parser crashen. (Beim echten Provider mit erzwungenem Schema sollte das
    praktisch nie auftreten — genau das ist der Sinn von §10.8.)
    """


@runtime_checkable
class Model(Protocol):
    """Vertrag jedes Modell-Adapters.

    ``generate_structured`` MUSS ein Objekt liefern, das ``schema`` erfüllt, oder
    ``StructuredOutputError`` werfen. ``tier`` erlaubt die Light-vs-Heavy-Wahl
    (§ StageB): billiges Modell für Metadaten/Reviews, starkes für Kreativarbeit.
    """

    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        *,
        tier: str = "strong",
    ) -> Dict[str, Any]: ...


def validate_against_schema(obj: Any, schema: Dict[str, Any]) -> Optional[str]:
    """Minimaler JSON-Schema-Check (Teilmenge: type, required, properties, items).

    Rückgabe: ``None`` bei gültig, sonst ein menschenlesbarer Fehlergrund. Bewusst
    klein gehalten — der echte Provider erzwingt das Schema serverseitig; dies ist das
    lokale Sicherheitsnetz und die Grundlage von ``FakeModel``.
    """
    return _check(obj, schema, path="$")


_TYPES: Dict[str, tuple] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "null": (type(None),),
}


def _check(obj: Any, schema: Dict[str, Any], path: str) -> Optional[str]:
    t = schema.get("type")
    if t is not None:
        expected = _TYPES.get(t)
        if expected is None:
            return f"{path}: unknown schema type {t!r}"
        # bool ist in Python ein int-Subtyp — für "integer"/"number" ausschließen
        if t in ("integer", "number") and isinstance(obj, bool):
            return f"{path}: expected {t}, got boolean"
        if not isinstance(obj, expected):
            return f"{path}: expected {t}, got {type(obj).__name__}"

    if t == "object" or (t is None and isinstance(obj, dict)):
        if isinstance(obj, dict):
            for key in schema.get("required", []):
                if key not in obj:
                    return f"{path}: missing required field {key!r}"
            props = schema.get("properties", {})
            for key, sub in props.items():
                if key in obj:
                    err = _check(obj[key], sub, f"{path}.{key}")
                    if err:
                        return err

    if t == "array" and isinstance(obj, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for idx, item in enumerate(obj):
                err = _check(item, item_schema, f"{path}[{idx}]")
                if err:
                    return err
    return None


class FakeModel:
    """Skriptbares Modell für Tests — kein Netzwerk, deterministisch.

    Man reiht Antworten ein; jeder ``generate_structured``-Call nimmt die nächste.
    Antworten dürfen ``dict`` (wird gegen das Schema geprüft) oder ein Callable
    ``(prompt, schema) -> dict`` sein (um auf das Feedback im Prompt zu reagieren —
    so testet man den Retry-Loop). Verletzt eine Antwort das Schema, wird
    ``StructuredOutputError`` geworfen, genau wie ein echter Adapter es müsste.
    """

    def __init__(
        self,
        responses: Optional[List[Any]] = None,
        *,
        router: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        enforce_schema: bool = True,
    ) -> None:
        self._responses: List[Any] = list(responses or [])
        self._router = router
        self.enforce_schema = enforce_schema
        self.calls: List[Dict[str, Any]] = []   # Protokoll für Assertions
        self._lock = threading.Lock()            # thread-safe für parallele Queue-Calls

    def queue(self, response: Any) -> "FakeModel":
        self._responses.append(response)
        return self

    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        *,
        tier: str = "strong",
    ) -> Dict[str, Any]:
        with self._lock:
            self.calls.append({"prompt": prompt, "schema": schema, "tier": tier})
            if self._router is not None:
                # Router-Modus: mappt Prompt-Inhalt → Antwort. Reihenfolge-unabhängig,
                # daher tauglich für parallele (nicht-deterministisch geordnete) Calls.
                producer: Any = self._router
            else:
                if not self._responses:
                    raise AssertionError("FakeModel: no more scripted responses queued")
                producer = self._responses.pop(0)
        obj = producer(prompt, schema) if callable(producer) else producer
        if self.enforce_schema:
            err = validate_against_schema(obj, schema)
            if err is not None:
                raise StructuredOutputError(err)
        return obj
