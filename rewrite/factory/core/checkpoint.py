"""Checkpoint-Store (§ Stage A): unabhängige Cache-Einheiten, gekeyt auf Call-Parameter.

Canon, Arc und jedes Episode-Concept sind eigene gecachte Einheiten. Ein permanenter
Fehler einer Einheit lässt die anderen intakt; ein identischer Re-Run regeneriert nur
das Fehlende. Gekeyt wird auf die *Call-Parameter* (nicht den substituierten Prompt),
damit eine harmlose Prompt-Umformulierung den Cache nicht invalidiert.

Der Checkpoint wird bewusst erst *nach* erfolgreichem Schreiben der Serie gelöscht —
Review/Repair dazwischen sind selbst lange Calls (§ Stage A).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from typing import Any, Callable, Dict, Optional


def key_of(*parts: Any) -> str:
    """Stabiler Schlüssel aus Call-Parametern (Reihenfolge-treu, JSON-kanonisch)."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class CheckpointStore:
    def __init__(self, root: str) -> None:
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, key: str) -> str:
        safe = key.replace(os.sep, "__").replace("/", "__")
        return os.path.join(self.root, f"{safe}.json")

    def get(self, key: str) -> Optional[Any]:
        path = self._path(key)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def put(self, key: str, payload: Any) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp, self._path(key))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        """Cache-Hit → sofort zurück (nur Fehlendes wird regeneriert). Sonst compute+put."""
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        self.put(key, value)
        return value

    def clear(self) -> None:
        """Erst NACH erfolgreichem Serien-Schreiben aufrufen (§ Stage A)."""
        if os.path.isdir(self.root):
            shutil.rmtree(self.root)
        os.makedirs(self.root, exist_ok=True)
