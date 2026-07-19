"""TEST-GATE 0 — Retry-Loop: fatal nie akzeptiert, best-effort-fallback, Feedback (§5)."""

import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.retry import (
    RetryExhausted,
    ValidationResult,
    run_with_retry,
)


def _ok() -> ValidationResult:
    return ValidationResult(ok=True, fatal=False, badness=0.0, detail="")


def _soft(badness: float, detail: str = "too short") -> ValidationResult:
    return ValidationResult(ok=False, fatal=False, badness=badness, detail=detail)


def _fatal(detail: str = "format error") -> ValidationResult:
    return ValidationResult(ok=False, fatal=True, badness=999.0, detail=detail)


class RetryLoopTest(unittest.TestCase):
    def test_first_ok_returns_immediately(self) -> None:
        calls = []
        out = run_with_retry(
            generate=lambda p: (calls.append(p) or "value"),
            validate=lambda v: _ok(),
            base_prompt="P",
            max_attempts=3,
        )
        self.assertEqual(out, "value")
        self.assertEqual(len(calls), 1)

    def test_fatal_is_never_accepted(self) -> None:
        # Alle Versuche fatal → kein sicherer Kandidat → RetryExhausted, kein Rückgabewert.
        with self.assertRaises(RetryExhausted):
            run_with_retry(
                generate=lambda p: "bad",
                validate=lambda v: _fatal(),
                base_prompt="P",
                max_attempts=3,
            )

    def test_best_effort_fallback_returns_least_bad_safe(self) -> None:
        # Drei weiche Fehlschläge unterschiedlicher badness → der beste sichere gewinnt.
        seq = iter([("a", _soft(5.0)), ("b", _soft(2.0)), ("c", _soft(9.0))])
        buf = {}

        def gen(_p: str) -> str:
            val, res = next(seq)
            buf["res"] = res
            buf["val"] = val
            return val

        out = run_with_retry(
            generate=gen,
            validate=lambda v: buf["res"],
            base_prompt="P",
            max_attempts=3,
        )
        self.assertEqual(out, "b")   # badness 2.0 ist am kleinsten

    def test_fatal_never_chosen_even_with_safe_present(self) -> None:
        # Reihenfolge: soft(3) dann fatal dann fatal → fällt auf den sicheren soft(3) zurück,
        # nie auf einen fatalen.
        seq = iter([("safe", _soft(3.0)), ("x", _fatal()), ("y", _fatal())])
        buf = {}

        def gen(_p: str) -> str:
            val, res = next(seq)
            buf["res"] = res
            return val

        out = run_with_retry(
            generate=gen,
            validate=lambda v: buf["res"],
            base_prompt="P",
            max_attempts=3,
        )
        self.assertEqual(out, "safe")

    def test_feedback_is_fed_back_into_prompt(self) -> None:
        prompts = []

        def gen(p: str) -> str:
            prompts.append(p)
            return "v"

        results = iter([_soft(1.0, "needs a concrete beat"), _ok()])
        run_with_retry(
            generate=gen,
            validate=lambda v: next(results),
            base_prompt="BASE",
            max_attempts=3,
        )
        # zweiter Prompt enthält den exakten Fehlertext des ersten Versuchs
        self.assertIn("needs a concrete beat", prompts[1])

    def test_escalation_note_appears_at_threshold(self) -> None:
        prompts = []

        def gen(p: str) -> str:
            prompts.append(p)
            return "v"

        run_with_retry(
            generate=gen,
            validate=lambda v: _soft(1.0),
            base_prompt="BASE",
            max_attempts=3,
            escalation_threshold=3,
            escalation_note="ESCALATED",
        )
        self.assertNotIn("ESCALATED", prompts[0])
        self.assertIn("ESCALATED", prompts[2])   # erst der 3. (Schwellen-)Versuch

    def test_accept_immediately_below_short_circuits(self) -> None:
        calls = []

        def gen(_p: str) -> str:
            calls.append(1)
            return "v"

        out = run_with_retry(
            generate=gen,
            validate=lambda v: _soft(0.5),
            base_prompt="P",
            max_attempts=5,
            accept_immediately_below=1.0,
        )
        self.assertEqual(out, "v")
        self.assertEqual(len(calls), 1)   # sofort akzeptiert, kein weiterer Versuch


if __name__ == "__main__":
    unittest.main()
