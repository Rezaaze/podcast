"""Single-Source-Substitution (§5, §2.1).

Fakten, die in Prompts auftauchen müssen (Voice-Roster, Modellnamen, Limits), werden zur
Build-Zeit über Platzhalter injiziert — nie von Hand in Templates gepflegt. Ein Template
kann so nicht von der Realität abdriften; ein Fakt ändert sich an genau einer Stelle.
**Nicht ersetzte Platzhalter warnen laut** (statt still ein ``{{...}}`` ins Prompt zu lassen).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@dataclass
class Substitution:
    text: str
    unreplaced: List[str] = field(default_factory=list)   # Platzhalter ohne Fakt
    unused: List[str] = field(default_factory=list)       # Fakten ohne Platzhalter

    @property
    def ok(self) -> bool:
        return not self.unreplaced


def substitute(template: str, facts: Dict[str, Any]) -> Substitution:
    """Ersetze ``{{key}}`` durch ``facts[key]``. Sammle unersetzte Platzhalter.

    Unersetzte Platzhalter bleiben als ``{{key}}`` im Text stehen UND werden in
    ``unreplaced`` gemeldet, damit der Aufrufer laut warnen/abbrechen kann.
    """
    used: set = set()

    def repl(match: "re.Match[str]") -> str:
        name = match.group(1)
        if name in facts:
            used.add(name)
            return str(facts[name])
        return match.group(0)   # unverändert lassen — wird als unreplaced gemeldet

    text = _PLACEHOLDER.sub(repl, template)
    unreplaced = sorted({m.group(1) for m in _PLACEHOLDER.finditer(text)})
    unused = sorted(set(facts) - used)
    return Substitution(text=text, unreplaced=unreplaced, unused=unused)
