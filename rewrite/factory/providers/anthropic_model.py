"""Echter Model-Adapter gegen das Anthropic-SDK (§10.8) — erfüllt das Model-Protokoll.

Ersetzt das alte Subprocess-Interface durch structured output: die Claude-API garantiert
schema-konformes JSON (``output_config.format``), womit JSON-Scavenging, Heartbeat, der
stdin-Trick und die Slot-Semaphore entfallen. Der validate→retry→feedback-Loop (retry.py)
bleibt bewusst darüber — structured output garantiert *parsebares*, nie *korrektes* JSON.

Braucht `pip install anthropic` und Credentials (ANTHROPIC_API_KEY oder `ant auth login`).
Wird nicht von den stdlib-Unit-Tests importiert; die pure Schema-Vorbereitung (schema_prep)
ist separat getestet. Modell-IDs Stand 2026-07 (claude-api-Skill): Opus 4.8 / Haiku 4.5.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from factory.core.model import StructuredOutputError
from factory.providers.schema_prep import prepare_schema_for_structured_output

# Light-vs-Heavy (§ Stage B): starkes Modell für Kreativarbeit, billiges für Reviews/Metadaten.
TIER_MODELS = {
    "strong": "claude-opus-4-8",
    "cheap": "claude-haiku-4-5",
}
TIER_EFFORT = {
    "strong": "high",
    "cheap": "low",
}

# Ab hier streamt der SDK, damit große Ausgaben nicht in HTTP-Timeouts laufen (claude-api-Skill).
STREAM_ABOVE_MAX_TOKENS = 16000


class AnthropicModel:
    """Konkrete Model-Implementierung. ``generate_structured`` liefert schema-konformes dict.

    ``client`` wird injiziert (Default: ``anthropic.Anthropic()`` — löst Credentials aus der
    Umgebung/`ant auth login` auf). So bleibt der Adapter ohne Netzwerk konstruierbar/mockbar.
    """

    def __init__(
        self,
        client: Any = None,
        *,
        max_tokens: int = 8000,
        tier_models: Optional[Dict[str, str]] = None,
        use_thinking: bool = True,
    ) -> None:
        if client is None:
            import anthropic  # lazy: nur nötig, wenn ein echter Client gebaut wird
            client = anthropic.Anthropic()
        self.client = client
        self.max_tokens = max_tokens
        self.tier_models = dict(tier_models or TIER_MODELS)
        self.use_thinking = use_thinking

    def _model_for(self, tier: str) -> str:
        if tier not in self.tier_models:
            raise ValueError(f"unknown tier {tier!r}; known: {sorted(self.tier_models)}")
        return self.tier_models[tier]

    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        *,
        tier: str = "strong",
    ) -> Dict[str, Any]:
        model = self._model_for(tier)
        output_config: Dict[str, Any] = {
            "format": {"type": "json_schema", "schema": prepare_schema_for_structured_output(schema)},
            "effort": TIER_EFFORT.get(tier, "high"),
        }
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "output_config": output_config,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.use_thinking and tier == "strong":
            kwargs["thinking"] = {"type": "adaptive"}

        message = self._create(kwargs)

        # Fatal im Sinne von retry.py: würde Downstream crashen / kein verwertbarer Inhalt.
        if getattr(message, "stop_reason", None) == "refusal":
            detail = getattr(getattr(message, "stop_details", None), "explanation", "") or "safety refusal"
            raise StructuredOutputError(f"model refused: {detail}")

        text = self._first_text(message)
        if text is None:
            raise StructuredOutputError(f"no text block in response (stop_reason={getattr(message,'stop_reason',None)})")
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            # Sollte bei erzwungenem Schema praktisch nie passieren — dann ist es fatal.
            raise StructuredOutputError(f"structured output was not valid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise StructuredOutputError(f"structured output was not a JSON object: {type(obj).__name__}")
        return obj

    def _create(self, kwargs: Dict[str, Any]) -> Any:
        """Streamt bei großem max_tokens (Timeout-Schutz), sonst normaler Create."""
        if self.max_tokens > STREAM_ABOVE_MAX_TOKENS and hasattr(self.client.messages, "stream"):
            with self.client.messages.stream(**kwargs) as stream:
                return stream.get_final_message()
        return self.client.messages.create(**kwargs)

    @staticmethod
    def _first_text(message: Any) -> Optional[str]:
        for block in getattr(message, "content", []) or []:
            if getattr(block, "type", None) == "text":
                return getattr(block, "text", None)
        return None
