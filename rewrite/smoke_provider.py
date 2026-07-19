"""Minimaler Ein-Call-Smoketest für einen echten Provider.

Verifiziert: Auth + Antwort-Parsing + das Model-Protokoll — mit einem winzigen Schema,
also minimalem Verbrauch. Kein Workspace, keine Serie, keine Skripte — nur ein Call.

    cd rewrite && python3 smoke_provider.py            # CLI-Provider (Abo, kein venv nötig)
    cd rewrite && .venv/bin/python smoke_provider.py sdk   # anthropic SDK (API-Billing)
"""

from __future__ import annotations

import sys

SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "one_word_mood": {"type": "string"},
    },
    "required": ["ok", "one_word_mood"],
    "additionalProperties": False,
}

PROMPT = (
    "You are wiring-testing a JSON pipeline. Return ok=true and a single "
    "lowercase word for the mood of a rainy noir city in one_word_mood."
)


def main() -> int:
    provider = sys.argv[1] if len(sys.argv) > 1 else "cli"
    try:
        if provider == "cli":
            from factory.providers.claude_cli_model import ClaudeCliModel
            model = ClaudeCliModel()
        else:
            from factory.providers.anthropic_model import AnthropicModel
            model = AnthropicModel(max_tokens=200)
    except Exception as exc:  # pragma: no cover
        print(f"Provider-Init fehlgeschlagen ({provider}): {exc}", file=sys.stderr)
        return 2

    try:
        result = model.generate_structured(PROMPT, SCHEMA, tier="cheap")
    except Exception as exc:
        print(f"Call fehlgeschlagen: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    print("OK — structured output:", result)
    if not (isinstance(result, dict) and result.get("ok") is True):
        print("Warnung: unerwartete Form, aber Call lief.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
