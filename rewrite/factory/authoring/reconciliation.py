"""Reconciliation als *deterministischer* Check (§10.2 revidiert).

Kein Multi-Vote-LLM-Judge: der Judge scheitert dieselbe Weise wie der Arc (Modell-
Mis-Allokation) → keine Unabhängigkeit → gestrichen. Was bleibt, ist die *unabhängige*
Degeneracy: ein billiger deterministischer Duplikat-Check — gleiche Turning-Point-ID in
zwei Episoden. Rein textuell, kein Modell.

Setup: der Arc alloziert jeden Turning-Point genau einer Episode (Feld ``episode``).
Sections, die einen Turning-Point inszenieren, benennen ihn per ``turning_point``-ID. Der
Check verifiziert die Allokations-Integrität über die fertigen Sections:

- **duplicated** — dieselbe TP-ID wird in Sections von >1 Episode inszeniert (Doppel-Climax).
- **missing** — eine allozierte TP-ID inszeniert keine Section.
- **misplaced** — eine TP-ID wird in einer anderen Episode inszeniert als der Arc zuweist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass
class ReconFinding:
    kind: str                    # "duplicated" | "missing" | "misplaced"
    turning_point: str
    episode: Optional[int]       # betroffene Episode (für den Repair-Dispatcher, §10.2/§2.9)
    detail: str


def reconcile(
    turning_points: Sequence[dict],
    episodes: Sequence[dict],
) -> List[ReconFinding]:
    """``turning_points``: [{id, episode, ...}]. ``episodes``: [{sections:[{turning_point?}]}].

    Rückgabe: Findings (leer = sauber). Jedes trägt eine Episodennummer, wo sinnvoll, damit
    der Repair-Dispatcher (§2.9) klein reparieren kann.
    """
    assigned: Dict[str, int] = {}
    for tp in turning_points:
        assigned[tp["id"]] = tp["episode"]

    # wo wird jede TP-ID tatsächlich inszeniert?
    staged: Dict[str, List[int]] = {}
    for ei, ep in enumerate(episodes):
        for sec in ep.get("sections", []):
            tp_id = sec.get("turning_point")
            if tp_id is not None:
                staged.setdefault(tp_id, []).append(ei)

    findings: List[ReconFinding] = []

    for tp_id, target_ep in assigned.items():
        eps = staged.get(tp_id, [])
        distinct = sorted(set(eps))
        if not distinct:
            findings.append(ReconFinding(
                kind="missing", turning_point=tp_id, episode=target_ep,
                detail=f"turning point {tp_id!r} allocated to episode {target_ep} but no section stages it",
            ))
            continue
        if len(distinct) > 1:
            findings.append(ReconFinding(
                kind="duplicated", turning_point=tp_id, episode=None,
                detail=f"turning point {tp_id!r} staged in episodes {distinct} — double-climax",
            ))
        for ei in distinct:
            if ei != target_ep:
                findings.append(ReconFinding(
                    kind="misplaced", turning_point=tp_id, episode=ei,
                    detail=f"turning point {tp_id!r} staged in episode {ei} but allocated to {target_ep}",
                ))
    return findings
