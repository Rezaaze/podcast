"""Schema-Vorbereitung für Anthropic structured output (pure, stdlib, testbar).

Die Claude-API verlangt für ``output_config.format`` / ``json_schema``, dass **jedes
Objekt `additionalProperties: false` trägt** (Struktur-Garantie). Unsere internen Schemas
(factory.core.schema, conceive, script_writer) definieren das nicht — dieser Helfer fügt
es rekursiv ein, ohne die Schemas selbst zu verändern (arbeitet auf einer Kopie).

Nicht unterstützte JSON-Schema-Constraints (minLength, minimum, …) kommen in unseren
Schemas nicht vor; falls doch, würde die API sie ablehnen — dann hier strippen.
"""

from __future__ import annotations

import copy
from typing import Any, Dict


def prepare_schema_for_structured_output(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Kopiere ``schema`` und setze ``additionalProperties: false`` an jedem Objekt-Knoten."""
    prepared = copy.deepcopy(schema)
    _annotate(prepared)
    return prepared


def _annotate(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            node.setdefault("additionalProperties", False)
            for sub in node.get("properties", {}).values():
                _annotate(sub)
        elif node.get("type") == "array":
            items = node.get("items")
            if items is not None:
                _annotate(items)
        else:
            # anyOf/allOf/oneOf-Zweige mitnehmen
            for key in ("anyOf", "allOf", "oneOf"):
                for sub in node.get(key, []):
                    _annotate(sub)
