"""TEST-GATE 0 — Work-Queue: Limit hält, kein Deadlock, stabile Reihenfolge (§10.7)."""

import threading
import time
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.queue import WorkQueue


class WorkQueueTest(unittest.TestCase):
    def test_results_in_input_order(self) -> None:
        q = WorkQueue(max_in_flight=4)
        out = q.map(lambda x: x * x, [0, 1, 2, 3, 4, 5])
        self.assertEqual(out, [0, 1, 4, 9, 16, 25])

    def test_concurrency_limit_is_respected(self) -> None:
        q = WorkQueue(max_in_flight=3)
        active = 0
        lock = threading.Lock()
        observed_peak = 0

        def work(_x: int) -> int:
            nonlocal active, observed_peak
            with lock:
                active += 1
                observed_peak = max(observed_peak, active)
            time.sleep(0.02)     # Überlappung erzwingen
            with lock:
                active -= 1
            return _x

        q.map(work, list(range(12)))
        self.assertLessEqual(observed_peak, 3)   # nie mehr als das Limit
        self.assertLessEqual(q.peak_in_flight, 3)
        self.assertGreaterEqual(q.peak_in_flight, 2)  # aber wirklich parallel

    def test_no_deadlock_when_items_exceed_limit(self) -> None:
        q = WorkQueue(max_in_flight=2)
        out = q.map(lambda x: x + 1, list(range(50)))
        self.assertEqual(out, list(range(1, 51)))

    def test_exception_propagates_after_others_finish(self) -> None:
        q = WorkQueue(max_in_flight=4)
        done = []

        def work(x: int) -> int:
            if x == 3:
                raise ValueError("boom")
            done.append(x)
            return x

        with self.assertRaises(ValueError):
            q.map(work, list(range(6)))
        # die nicht-fehlerhaften liefen trotzdem alle durch (kein stilles Abwürgen)
        self.assertEqual(sorted(done), [0, 1, 2, 4, 5])

    def test_rejects_zero_concurrency(self) -> None:
        with self.assertRaises(ValueError):
            WorkQueue(max_in_flight=0)


if __name__ == "__main__":
    unittest.main()
