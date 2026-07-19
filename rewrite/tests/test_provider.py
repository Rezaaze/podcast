"""TEST-GATE Provider — Anthropic-Adapter mit Fake-Client (kein anthropic-Paket, kein Netz).

Getestet wird die Adapter-Logik: Schema-Prep, Tier→Modell, structured-output-Extraktion,
refusal→fatal, JSON-Fehler→fatal. Der echte SDK-Call ist nur die dünne _create-Schicht.
"""

import json
import types
import unittest

from tests import _bootstrap  # noqa: F401

from factory.core.model import Model, StructuredOutputError
from factory.providers.anthropic_model import AnthropicModel
from factory.providers.schema_prep import prepare_schema_for_structured_output

_SCHEMA = {
    "type": "object",
    "required": ["title", "sections"],
    "properties": {
        "title": {"type": "string"},
        "sections": {"type": "array", "items": {
            "type": "object", "required": ["what"],
            "properties": {"what": {"type": "string"}}}},
    },
}


def _block(type_, **kw):
    return types.SimpleNamespace(type=type_, **kw)


def _message(text=None, stop_reason="end_turn", explanation=None):
    content = [_block("text", text=text)] if text is not None else []
    stop_details = types.SimpleNamespace(explanation=explanation) if explanation else None
    return types.SimpleNamespace(content=content, stop_reason=stop_reason, stop_details=stop_details)


class FakeMessages:
    def __init__(self, message):
        self._message = message
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._message


class FakeClient:
    def __init__(self, message):
        self.messages = FakeMessages(message)


class SchemaPrepTest(unittest.TestCase):
    def test_adds_additional_properties_false_recursively(self) -> None:
        prepared = prepare_schema_for_structured_output(_SCHEMA)
        self.assertFalse(prepared["additionalProperties"])
        self.assertFalse(prepared["properties"]["sections"]["items"]["additionalProperties"])

    def test_does_not_mutate_input(self) -> None:
        import copy
        before = copy.deepcopy(_SCHEMA)
        prepare_schema_for_structured_output(_SCHEMA)
        self.assertEqual(_SCHEMA, before)


class AnthropicModelTest(unittest.TestCase):
    def _model(self, message):
        return AnthropicModel(client=FakeClient(message), max_tokens=8000)

    def test_is_a_model(self) -> None:
        self.assertIsInstance(self._model(_message('{"title":"T","sections":[]}')), Model)

    def test_returns_parsed_object(self) -> None:
        m = self._model(_message('{"title":"T","sections":[{"what":"x"}]}'))
        out = m.generate_structured("prompt", _SCHEMA)
        self.assertEqual(out["title"], "T")

    def test_tier_selects_model_and_schema_is_prepared(self) -> None:
        client = FakeClient(_message('{"title":"T","sections":[]}'))
        m = AnthropicModel(client=client, max_tokens=8000)
        m.generate_structured("p", _SCHEMA, tier="cheap")
        call = client.messages.calls[0]
        self.assertEqual(call["model"], "claude-haiku-4-5")
        # Schema wurde für structured output vorbereitet
        sent = call["output_config"]["format"]["schema"]
        self.assertFalse(sent["additionalProperties"])
        self.assertEqual(call["output_config"]["effort"], "low")

    def test_strong_tier_uses_opus_and_thinking(self) -> None:
        client = FakeClient(_message('{"title":"T","sections":[]}'))
        AnthropicModel(client=client, max_tokens=8000).generate_structured("p", _SCHEMA, tier="strong")
        call = client.messages.calls[0]
        self.assertEqual(call["model"], "claude-opus-4-8")
        self.assertEqual(call["thinking"], {"type": "adaptive"})

    def test_refusal_is_fatal(self) -> None:
        m = self._model(_message(text=None, stop_reason="refusal", explanation="nope"))
        with self.assertRaises(StructuredOutputError):
            m.generate_structured("p", _SCHEMA)

    def test_no_text_block_is_fatal(self) -> None:
        m = self._model(_message(text=None, stop_reason="end_turn"))
        with self.assertRaises(StructuredOutputError):
            m.generate_structured("p", _SCHEMA)

    def test_invalid_json_is_fatal(self) -> None:
        m = self._model(_message("not json {"))
        with self.assertRaises(StructuredOutputError):
            m.generate_structured("p", _SCHEMA)

    def test_unknown_tier_raises(self) -> None:
        m = self._model(_message('{"title":"T","sections":[]}'))
        with self.assertRaises(ValueError):
            m.generate_structured("p", _SCHEMA, tier="medium")


if __name__ == "__main__":
    unittest.main()
