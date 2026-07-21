"""Eine Work-Queue, ein Concurrency-Limit (§10.7).

Ersetzt die vielen unkoordinierten Caps (per batch/job/section/episode) plus die
cross-process-Semaphore aus dem Altsystem. Genau *ein* globales Limit; alle Stufen
enqueuen hier. Reihenfolge der Ergebnisse ist stabil (Einreihungsreihenfolge),
unabhängig davon, welcher Worker zuerst fertig wird.

§9 Falle #7: Nicht die Parallelität war die Truncation-Ursache, sondern zu große
Einzel-Calls. Diese Queue drosselt Parallelität; klein-halten der Calls ist Sache der
Aufrufer (kleine Units statt großer Batches).
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Iterable, List, TypeVar

T = TypeVar("T")


class WorkQueue:
    """Bounded-concurrency Runner. I/O-bound (Modell-Calls) → Threads reichen.

    ``max_in_flight`` ist das einzige Concurrency-Limit im System (Start: 4–8, §14).
    """

    def __init__(self, max_in_flight: int = 6) -> None:
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be >= 1")
        self.max_in_flight = max_in_flight
        self._sema = threading.BoundedSemaphore(max_in_flight)
        self._peak_lock = threading.Lock()
        self._in_flight = 0
        self._peak = 0

    @property
    def peak_in_flight(self) -> int:
        """Höchste gleichzeitige Belegung — für Tests/Beobachtung."""
        return self._peak

    def _guarded(self, fn: Callable[..., T], args: tuple, kwargs: dict) -> T:
        self._sema.acquire()
        with self._peak_lock:
            self._in_flight += 1
            self._peak = max(self._peak, self._in_flight)
        try:
            return fn(*args, **kwargs)
        finally:
            with self._peak_lock:
                self._in_flight -= 1
            self._sema.release()

    def map(self, fn: Callable[[T], Any], items: Iterable[T]) -> List[Any]:
        """Führe ``fn`` über alle ``items`` mit gedeckelter Parallelität aus.

        Ergebnisliste in Eingabereihenfolge. Wirft eine Einzel-Exception erst nach
        Abschluss aller anderen (kein stilles Verschlucken) — der Aufrufer entscheidet
        über Retry/Fallback (das ist Sache der Retry-Schicht, nicht der Queue).
        """
        items = list(items)
        results: List[Any] = [None] * len(items)
        futures: List[tuple[int, Future]] = []
        # Genug Worker, damit das Semaphore (nicht der Pool) das Limit setzt.
        with ThreadPoolExecutor(max_workers=self.max_in_flight) as pool:
            for i, item in enumerate(items):
                fut = pool.submit(self._guarded, fn, (item,), {})
                futures.append((i, fut))
            first_exc: BaseException | None = None
            for i, fut in futures:
                try:
                    results[i] = fut.result()
                except BaseException as exc:  # noqa: BLE001 — bewusst gesammelt
                    if first_exc is None:
                        first_exc = exc
            if first_exc is not None:
                raise first_exc
        return results

    def submit_all(self, thunks: Iterable[Callable[[], Any]]) -> List[Any]:
        """Wie ``map``, aber über parameterlose Callables. Stabile Reihenfolge."""
        return self.map(lambda thunk: thunk(), list(thunks))
