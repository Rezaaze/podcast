"""TEST-GATE 1 — der eine Validator (§5, §10.4)."""

import copy
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.schema import minimal_valid_record
from factory.core.validator import validate_series


class ValidatorTest(unittest.TestCase):
    def test_minimal_record_is_valid(self) -> None:
        report = validate_series(minimal_valid_record())
        self.assertTrue(report.is_valid, msg=str(report))
        self.assertEqual(report.warnings, [])

    def test_missing_required_field_is_hard_error(self) -> None:
        rec = minimal_valid_record()
        del rec["threads"]
        report = validate_series(rec)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("structure" in e for e in report.errors))

    def test_wrong_schema_version_is_hard_error(self) -> None:
        rec = minimal_valid_record()
        rec["schema_version"] = 0
        report = validate_series(rec)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("migrate before validating" in e for e in report.errors))

    def test_duplicate_voice_is_hard_error(self) -> None:
        rec = minimal_valid_record()
        rec["cast"][1]["voice"] = rec["cast"][0]["voice"]   # zwei Rollen, eine Voice
        report = validate_series(rec)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("never share a voice" in e for e in report.errors))

    def test_dangling_thread_reference_is_hard_error(self) -> None:
        rec = minimal_valid_record()
        rec["episodes"][0]["sections"][0]["thread"] = "nonexistent"
        report = validate_series(rec)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("not found in threads" in e for e in report.errors))

    def test_unknown_capability_is_warning_not_error(self) -> None:
        rec = minimal_valid_record()
        rec["capabilities"].append("has_teleporter")
        report = validate_series(rec)
        self.assertTrue(report.is_valid)   # nur Warnung, kein Block
        self.assertTrue(any("has_teleporter" in w for w in report.warnings))

    def test_unknown_field_is_warning(self) -> None:
        rec = minimal_valid_record()
        rec["identity"]["colour"] = "blue"   # Typo/unbekannt
        report = validate_series(rec)
        self.assertTrue(report.is_valid)
        self.assertTrue(any("unknown field" in w and "colour" in w for w in report.warnings))

    def test_unknown_mode_is_warning(self) -> None:
        rec = minimal_valid_record()
        rec["identity"]["mode"] = "opera"
        report = validate_series(rec)
        self.assertTrue(report.is_valid)
        self.assertTrue(any("not a known mode" in w for w in report.warnings))

    def test_who_not_in_cast_is_warning(self) -> None:
        rec = minimal_valid_record()
        rec["episodes"][0]["sections"][0]["who"].append("STRANGER")
        report = validate_series(rec)
        self.assertTrue(report.is_valid)
        self.assertTrue(any("STRANGER" in w for w in report.warnings))

    def test_validator_does_not_mutate_input(self) -> None:
        rec = minimal_valid_record()
        before = copy.deepcopy(rec)
        validate_series(rec)
        self.assertEqual(rec, before)


if __name__ == "__main__":
    unittest.main()
