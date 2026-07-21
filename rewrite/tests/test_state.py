"""TEST-GATE 0 — Per-Unit-State-Record (§10.3, §9 Falle #1+#6)."""

import tempfile
import unittest

from tests import _bootstrap  # noqa: F401  (setzt sys.path)

from factory.core.state import StateStore, Status, UnitState


class StateRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.store = StateStore(self._dir.name)

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_absent_state_is_not_done(self) -> None:
        # Kernregel: fehlender State ⇒ NICHT fertig, NICHT clean.
        self.assertIsNone(self.store.get("u1"))
        self.assertFalse(self.store.is_done("u1"))

    def test_only_complete_counts_as_done(self) -> None:
        self.store.mark("u1", Status.UNKNOWN)
        self.assertFalse(self.store.is_done("u1"))     # unknown ≠ clean
        self.store.mark("u1", Status.DEGRADED)
        self.assertFalse(self.store.is_done("u1"))     # degraded ist resumbar
        self.store.mark("u1", Status.COMPLETE)
        self.assertTrue(self.store.is_done("u1"))       # nur COMPLETE ist fertig

    def test_degraded_is_resumable_state_not_silent_lie(self) -> None:
        # "Datei da, Status degraded" ist ein normaler Zustand, kein verstecktes done.
        self.store.mark("u1", Status.DEGRADED, produced="ep1.txt", reason="too short")
        st = self.store.get("u1")
        assert st is not None
        self.assertEqual(st.status, Status.DEGRADED)
        self.assertEqual(st.produced, "ep1.txt")
        self.assertEqual(st.meta["reason"], "too short")
        self.assertFalse(st.is_done())

    def test_roundtrip_json(self) -> None:
        st = UnitState("u9", Status.COMPLETE, produced="x", meta={"k": 1})
        again = UnitState.from_json(st.to_json())
        self.assertEqual(st, again)

    def test_write_is_atomic_and_overwrites(self) -> None:
        self.store.mark("u1", Status.UNKNOWN)
        self.store.mark("u1", Status.COMPLETE, produced="final")
        st = self.store.get("u1")
        assert st is not None
        self.assertTrue(st.is_done())
        self.assertEqual(st.produced, "final")


if __name__ == "__main__":
    unittest.main()
