"""Cockpit-Isolation (T7.4, §8).

Mehrere Steuer-Instanzen entkoppeln ihre „aktive Serie" vom globalen Pointer, damit sie
sich nicht gegenseitig den Zustand überschreiben — besonders während der Erzeugung. Ein
Create-Schritt meldet seinen neuen Slug auf dem eigenen Stream; die richtige Instanz
adoptiert ihn.
"""

from __future__ import annotations

from typing import Optional

from factory.core.workspace import get_latest


class Cockpit:
    """Eine Steuer-Instanz mit eigener aktiver Serie, entkoppelt vom globalen LATEST-Pointer."""

    def __init__(self, root: str) -> None:
        self.root = root
        self._active: Optional[str] = None

    def adopt(self, slug: str) -> None:
        """Diese Instanz übernimmt eine (z.B. gerade erzeugte) Serie — ohne den globalen
        Pointer zu ändern, den andere Instanzen benutzen."""
        self._active = slug

    @property
    def active(self) -> Optional[str]:
        """Eigene aktive Serie, sonst Fallback auf den globalen Pointer (§8)."""
        if self._active is not None:
            return self._active
        return get_latest(self.root)
