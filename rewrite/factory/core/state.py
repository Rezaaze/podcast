"""Per-Unit-State-Record (§10.3) — der Ersatz für "Datei existiert ⇒ fertig".

Kernregel (§5, §9 Falle #1 + #6): Abwesenheit eines State ist *nicht* "clean" und
*nicht* "done". Nur ``Status.COMPLETE`` gilt als fertig; ``DEGRADED`` und ``UNKNOWN``
sind normale resumbare Zustände, kein stilles "passed". Ein Check, der nicht laufen
konnte, schreibt ``UNKNOWN`` — nie eine leere Datei, die "sauber" vortäuscht.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class Status(str, Enum):
    COMPLETE = "complete"   # fertig und akzeptiert — der EINZIGE "done"-Zustand
    DEGRADED = "degraded"   # da, aber unter Ziel (best-effort) — resumbar
    UNKNOWN = "unknown"     # Check/Erzeugung lief nicht — resumbar, NIE "clean"


@dataclass
class UnitState:
    unit_id: str
    status: Status
    produced: Optional[str] = None      # *was* erzeugt wurde (Pfad/Beschreibung)
    meta: dict = field(default_factory=dict)

    def is_done(self) -> bool:
        """Nur COMPLETE ist fertig. Das ist die ganze Pointe von §10.3."""
        return self.status is Status.COMPLETE

    def to_json(self) -> str:
        d = asdict(self)
        d["status"] = self.status.value
        return json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "UnitState":
        d = json.loads(text)
        return cls(
            unit_id=d["unit_id"],
            status=Status(d["status"]),
            produced=d.get("produced"),
            meta=d.get("meta", {}),
        )


class StateStore:
    """Dateibasierter Speicher: ein JSON-State pro Unit unter ``root/<unit_id>.state.json``.

    Resume liest den State, nicht die Existenz einer Output-Datei. Schreiben ist
    atomar (temp + rename), damit ein Crash mitten im Schreiben nie einen halben
    State hinterlässt.
    """

    def __init__(self, root: str) -> None:
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, unit_id: str) -> str:
        safe = unit_id.replace(os.sep, "__")
        return os.path.join(self.root, f"{safe}.state.json")

    def get(self, unit_id: str) -> Optional[UnitState]:
        """State oder ``None``. None heißt "nie erzeugt" — NICHT "clean"."""
        path = self._path(unit_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return UnitState.from_json(fh.read())

    def is_done(self, unit_id: str) -> bool:
        """True nur bei existierendem State mit Status COMPLETE.

        Fehlender State ⇒ False. "Datei da, Status unknown/degraded" ⇒ False
        (resumbar). Das ersetzt jede "os.path.exists ⇒ fertig"-Inferenz.
        """
        st = self.get(unit_id)
        return st is not None and st.is_done()

    def put(self, state: UnitState) -> None:
        path = self._path(state.unit_id)
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(state.to_json())
            os.replace(tmp, path)   # atomar
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def mark(
        self,
        unit_id: str,
        status: Status,
        produced: Optional[str] = None,
        **meta: Any,
    ) -> UnitState:
        st = UnitState(unit_id=unit_id, status=status, produced=produced, meta=dict(meta))
        self.put(st)
        return st
