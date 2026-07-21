"""TEST-GATE 1 — Workspace-Layout, Pointer, atomare Slug-Reservierung (§3.2)."""

import os
import tempfile
import threading
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.workspace import (
    STAGES,
    SlugCollision,
    get_latest,
    list_series,
    open_series,
    reserve_series,
    set_latest,
)


class WorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = self._dir.name

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_reserve_scaffolds_all_stages(self) -> None:
        ws = reserve_series(self.root, "my_series")
        for stage in STAGES:
            self.assertTrue(os.path.isdir(ws.stage_output(stage)))
        self.assertTrue(os.path.isfile(ws.series_json()))

    def test_reserving_same_slug_twice_collides(self) -> None:
        reserve_series(self.root, "dup")
        with self.assertRaises(SlugCollision):
            reserve_series(self.root, "dup")

    def test_parallel_creators_only_one_wins(self) -> None:
        # Der Kernzweck der atomaren Reservierung (§3.2): kein stiller Doppel-Gewinn.
        winners = []
        errors = []
        barrier = threading.Barrier(8)

        def attempt() -> None:
            barrier.wait()   # alle gleichzeitig losfeuern
            try:
                reserve_series(self.root, "contested")
                winners.append(1)
            except SlugCollision:
                errors.append(1)

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(winners), 1)     # genau EIN Gewinner
        self.assertEqual(sum(errors), 7)

    def test_pointer_roundtrip(self) -> None:
        self.assertIsNone(get_latest(self.root))
        reserve_series(self.root, "s1")
        set_latest(self.root, "s1")
        self.assertEqual(get_latest(self.root), "s1")

    def test_open_missing_series_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            open_series(self.root, "ghost")

    def test_list_series_excludes_pointer_file(self) -> None:
        reserve_series(self.root, "a")
        reserve_series(self.root, "b")
        set_latest(self.root, "a")
        self.assertEqual(list_series(self.root), ["a", "b"])   # LATEST ist Datei, kein Ordner

    def test_unknown_stage_rejected(self) -> None:
        ws = reserve_series(self.root, "s")
        with self.assertRaises(ValueError):
            ws.stage_output("99_bogus")


if __name__ == "__main__":
    unittest.main()
