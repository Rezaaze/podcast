"""Missing-⇒-default (T7.5, §8, §9 Falle #6).

Ein *fehlendes* Feld ist nicht dasselbe wie eine *unchecked* Box. Ein fehlendes Flag auf
„off" zu defaulten kann still einen CLI-Default invertieren. Regel: fehlender Key ⇒ der
übergebene Default, immer. Ein *vorhandener* Wert (auch ``False``) gilt.
"""

from __future__ import annotations

from typing import Any, Mapping, TypeVar

T = TypeVar("T")


def get_flag(mapping: Mapping[str, Any], key: str, default: T) -> T:
    """``mapping[key]`` wenn vorhanden (auch ``False``/``None``), sonst ``default``.

    Explizit KEIN ``mapping.get(key) or default`` — das würde ein bewusstes ``False``
    oder ``0`` als „fehlt" behandeln.
    """
    return mapping[key] if key in mapping else default
