"""TEST-GATE 1 — Migration: idempotent, fehlend⇒älteste, neues Feld⇒kein Fabrikat (§7.1)."""

import copy
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.migrate import (
    MigrationError,
    is_needs_backfill,
    migrate_record,
    record_version,
)
from factory.core.schema import SCHEMA_VERSION, minimal_valid_record
from factory.core.validator import validate_series


def _legacy_record() -> dict:
    """Ein PRE-Versionierungs-Record: kein schema_version, keine capabilities."""
    rec = minimal_valid_record()
    del rec["schema_version"]
    del rec["capabilities"]
    return rec


class MigrationTest(unittest.TestCase):
    def test_absent_version_is_oldest_not_current(self) -> None:
        self.assertEqual(record_version(_legacy_record()), 0)

    def test_migrates_legacy_to_current_and_validates(self) -> None:
        migrated = migrate_record(_legacy_record())
        self.assertEqual(record_version(migrated), SCHEMA_VERSION)
        # capabilities aus dem Format hergeleitet (crime_drama), nicht geraten
        self.assertIn("needs_continuity_review", migrated["capabilities"])
        self.assertTrue(validate_series(migrated).is_valid, msg=str(validate_series(migrated)))

    def test_idempotent(self) -> None:
        once = migrate_record(_legacy_record())
        twice = migrate_record(once)
        self.assertEqual(once, twice)

    def test_current_record_is_noop(self) -> None:
        rec = minimal_valid_record()
        self.assertEqual(migrate_record(rec), rec)

    def test_unknown_format_gets_needs_backfill_not_fabrication(self) -> None:
        rec = _legacy_record()
        rec["identity"]["format"] = "an_unheard_of_format"
        migrated = migrate_record(rec)
        # kein erfundener Wert — ein sichtbarer needs-backfill-Marker (§7.1, §10.3)
        self.assertTrue(is_needs_backfill(migrated["capabilities"]))

    def test_frozen_canon_is_carried_not_reinvented(self) -> None:
        rec = _legacy_record()
        rec["threads"][0]["resolution"] = "the gardener did it"
        migrated = migrate_record(rec)
        self.assertEqual(migrated["threads"][0]["resolution"], "the gardener did it")

    def test_does_not_mutate_input(self) -> None:
        rec = _legacy_record()
        before = copy.deepcopy(rec)
        migrate_record(rec)
        self.assertEqual(rec, before)

    def test_future_version_raises(self) -> None:
        rec = minimal_valid_record()
        rec["schema_version"] = SCHEMA_VERSION + 5
        with self.assertRaises(MigrationError):
            migrate_record(rec)


if __name__ == "__main__":
    unittest.main()
