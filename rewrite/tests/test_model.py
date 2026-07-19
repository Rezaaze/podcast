"""TEST-GATE 0 — Modell-Interface & structured output (§10.8)."""

import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.model import (
    FakeModel,
    Model,
    StructuredOutputError,
    validate_against_schema,
)

_EPISODE_SCHEMA = {
    "type": "object",
    "required": ["title", "sections"],
    "properties": {
        "title": {"type": "string"},
        "count": {"type": "integer"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["what"],
                "properties": {"what": {"type": "string"}},
            },
        },
    },
}


class SchemaValidatorTest(unittest.TestCase):
    def test_valid_object_passes(self) -> None:
        obj = {"title": "T", "count": 2, "sections": [{"what": "x"}]}
        self.assertIsNone(validate_against_schema(obj, _EPISODE_SCHEMA))

    def test_missing_required_field(self) -> None:
        err = validate_against_schema({"title": "T"}, _EPISODE_SCHEMA)
        self.assertIn("sections", err or "")

    def test_wrong_type(self) -> None:
        obj = {"title": 5, "sections": []}
        err = validate_against_schema(obj, _EPISODE_SCHEMA)
        self.assertIn("expected string", err or "")

    def test_boolean_is_not_integer(self) -> None:
        obj = {"title": "T", "count": True, "sections": []}
        err = validate_against_schema(obj, _EPISODE_SCHEMA)
        self.assertIn("boolean", err or "")

    def test_nested_array_item_error(self) -> None:
        obj = {"title": "T", "sections": [{"nope": 1}]}
        err = validate_against_schema(obj, _EPISODE_SCHEMA)
        self.assertIn("what", err or "")


class FakeModelTest(unittest.TestCase):
    def test_is_a_model(self) -> None:
        self.assertIsInstance(FakeModel(), Model)

    def test_returns_scripted_response(self) -> None:
        m = FakeModel([{"title": "T", "sections": [{"what": "x"}]}])
        out = m.generate_structured("prompt", _EPISODE_SCHEMA)
        self.assertEqual(out["title"], "T")
        self.assertEqual(m.calls[0]["tier"], "strong")

    def test_schema_violation_raises(self) -> None:
        m = FakeModel([{"title": "T"}])   # sections fehlt
        with self.assertRaises(StructuredOutputError):
            m.generate_structured("prompt", _EPISODE_SCHEMA)

    def test_callable_response_sees_prompt(self) -> None:
        # So testet man den Retry-Loop mit einem "reagierenden" Modell.
        def responder(prompt: str, schema: dict) -> dict:
            title = "FIXED" if "FAILED" in prompt else "first"
            return {"title": title, "sections": [{"what": "x"}]}

        m = FakeModel([responder, responder])
        first = m.generate_structured("base", _EPISODE_SCHEMA)
        second = m.generate_structured("base FAILED: too short", _EPISODE_SCHEMA)
        self.assertEqual(first["title"], "first")
        self.assertEqual(second["title"], "FIXED")

    def test_tier_is_recorded(self) -> None:
        m = FakeModel([{"title": "T", "sections": []}])
        m.generate_structured("p", _EPISODE_SCHEMA, tier="cheap")
        self.assertEqual(m.calls[0]["tier"], "cheap")


if __name__ == "__main__":
    unittest.main()
