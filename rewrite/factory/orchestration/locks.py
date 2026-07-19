"""Exklusiver Lock auf geteiltem Gerät (T7.2, §8).

Pures Authoring (LLM-only) darf für zwei Serien parallel laufen; alles, das *ein*
physisches Gerät teilt (ein lokaler TTS-Prozess), nimmt einen globalen Lock, damit sich
zwei solche Jobs das Gerät nicht gegenseitig unter den Füßen wegziehen.

Datei-basiert (``fcntl.flock``): der Lock ist prozessübergreifend und wird bei Prozess-Ende
automatisch frei — kein dauerhaft blockierter Lock nach hartem Kill.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
from typing import Iterator


class DeviceLock:
    """Exklusiver, prozessübergreifender Lock, identifiziert durch einen Gerätenamen.

    Zwei Halter desselben Namens serialisieren; verschiedene Namen laufen parallel.
    """

    def __init__(self, lock_dir: str, device: str = "tts") -> None:
        os.makedirs(lock_dir, exist_ok=True)
        self._path = os.path.join(lock_dir, f"{device}.lock")

    @contextlib.contextmanager
    def acquire(self) -> Iterator[None]:
        fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)   # blockiert, bis der Lock frei ist
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


@contextlib.contextmanager
def no_lock() -> Iterator[None]:
    """Kein Lock — für pures Authoring (parallel erlaubt)."""
    yield
