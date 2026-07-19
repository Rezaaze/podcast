"""Repair-Dispatcher, split-by-scope (§2.9, §9 Falle #3).

Der teure Bug im Altsystem: ein naiver Dispatcher entscheidet am *schwächsten* Finding —
ein einziges scope-loses Finding kippt *alle* Findings in den Full-Rebuild, der bei großen
Serien zuverlässig truncatet. Fix: nach Scope teilen und jede Gruppe mit dem kleinstmöglichen
Call reparieren.

1. Findings **mit** Episodennummer → nur diese Episoden neu (+ kompakter Index des Rests).
2. Findings **ohne** Episodennummer → nur die Top-Level-Felder neu, nicht das (große) Array.
3. Nur was 1–2 nicht lösen konnten → Full-Rebuild als reines Sicherheitsnetz.

Jeder Pfad erkennt Truncation und bricht ab, statt ein Längenproblem blind zu retryen.
Partial success wird behalten, nie verworfen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol


@dataclass
class Finding:
    message: str
    episode: Optional[int] = None   # None ⇒ scope-los (Top-Level-Regel)


@dataclass
class Partition:
    by_episode: Dict[int, List[Finding]] = field(default_factory=dict)
    global_scoped: List[Finding] = field(default_factory=list)


def partition_findings(findings: List[Finding]) -> Partition:
    """Teile Findings nach Scope. Ein scope-loses Finding zieht die episoden-bezogenen
    NICHT mit in einen größeren Scope (das ist der ganze Punkt gegen §9 Falle #3)."""
    part = Partition()
    for f in findings:
        if f.episode is None:
            part.global_scoped.append(f)
        else:
            part.by_episode.setdefault(f.episode, []).append(f)
    return part


class TruncatedRepair(Exception):
    """Ein Repair-Call kam abgeschnitten zurück — nicht blind erneut versuchen."""


@dataclass
class RepairOutcome:
    record: Dict[str, Any]
    repaired_episodes: List[int] = field(default_factory=list)
    repaired_toplevel: bool = False
    did_full_rebuild: bool = False
    unresolved: List[Finding] = field(default_factory=list)
    truncated_scopes: List[str] = field(default_factory=list)


def dispatch_repair(
    record: Dict[str, Any],
    findings: List[Finding],
    *,
    repair_episodes: Callable[[Dict[str, Any], int, List[Finding]], Dict[str, Any]],
    repair_toplevel: Callable[[Dict[str, Any], List[Finding]], Dict[str, Any]],
    full_rebuild: Optional[Callable[[Dict[str, Any], List[Finding]], Dict[str, Any]]] = None,
    is_truncated: Callable[[Dict[str, Any]], bool] = lambda r: False,
) -> RepairOutcome:
    """Repariere ``record`` gegen ``findings`` mit dem jeweils kleinsten Scope.

    Truncation auf einem Scope: dieser Scope bleibt unrepariert (Partial success behalten),
    seine Findings landen in ``unresolved`` — NIE ein blinder Retry desselben Längenproblems.
    Full-Rebuild läuft nur, wenn übergeben UND wenn Scope-1/2 etwas offen ließen.
    """
    part = partition_findings(findings)
    out = RepairOutcome(record=dict(record))
    still_open: List[Finding] = []

    # 1) episoden-bezogen — jede Episode für sich, kleinster Call
    for ep, group in sorted(part.by_episode.items()):
        try:
            candidate = repair_episodes(out.record, ep, group)
            if is_truncated(candidate):
                raise TruncatedRepair(f"episode {ep}")
            out.record = candidate
            out.repaired_episodes.append(ep)
        except TruncatedRepair:
            out.truncated_scopes.append(f"episode:{ep}")
            still_open.extend(group)   # Partial behalten, Finding bleibt offen

    # 2) scope-los — nur Top-Level-Felder, nicht das große Episoden-Array
    if part.global_scoped:
        try:
            candidate = repair_toplevel(out.record, part.global_scoped)
            if is_truncated(candidate):
                raise TruncatedRepair("toplevel")
            out.record = candidate
            out.repaired_toplevel = True
        except TruncatedRepair:
            out.truncated_scopes.append("toplevel")
            still_open.extend(part.global_scoped)

    # 3) Full-Rebuild NUR als Netz für Ungelöstes (nie der Default)
    if still_open and full_rebuild is not None:
        try:
            candidate = full_rebuild(out.record, still_open)
            if is_truncated(candidate):
                raise TruncatedRepair("full")
            out.record = candidate
            out.did_full_rebuild = True
            still_open = []
        except TruncatedRepair:
            out.truncated_scopes.append("full")

    out.unresolved = still_open
    return out
