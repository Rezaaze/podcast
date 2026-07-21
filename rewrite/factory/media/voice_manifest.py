"""Voice-Consistency-Guard am neuen Series-Record (T4.5, §9 Falle #5).

Audio wird nach *Dateiname* gecacht, nicht nach Voice-Konfig — ein späteres Editieren
von ``cast[role].voice`` würde sonst still eine Mixed-Voice-Serie erzeugen. Darum: ein
committetes Manifest (voice/speed/seed pro Rolle) wird bei jedem Lauf verglichen und der
Lauf **hard-stoppt vor dem ersten Dateizugriff**, wenn sich etwas geändert hat.

Reine dict-Logik — daher stdlib-testbar, unabhängig vom Audio-Kern. Der Vergleich ist ein
No-op ohne committetes Manifest; der Baseline-Write (``build_manifest``) darf erst laufen,
wenn das Backend erreichbar ist UND alle Voices aufgelöst sind (Reihenfolge liegt beim
Aufrufer — siehe voicing.py).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class VoiceDrift(Exception):
    """Committete Voice-Konfig weicht vom aktuellen Record ab — Lauf hart stoppen."""

    def __init__(self, drift: List[str]) -> None:
        super().__init__("voice manifest drift: " + "; ".join(drift))
        self.drift = drift


def build_manifest(record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """role → {voice, speed, seed}. Die einzufrierende Baseline."""
    manifest: Dict[str, Dict[str, Any]] = {}
    for m in record.get("cast", []):
        manifest[m["role"]] = {
            "voice": m.get("voice"),
            "speed": m.get("speed"),
            "seed": m.get("seed"),
        }
    return manifest


def diff_manifest(
    committed: Dict[str, Dict[str, Any]],
    current: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Menschenlesbare Drift-Liste (leer = konsistent)."""
    drift: List[str] = []
    for role, cur in current.items():
        if role not in committed:
            drift.append(f"new role {role!r} not in committed manifest")
            continue
        old = committed[role]
        for field in ("voice", "speed", "seed"):
            if old.get(field) != cur.get(field):
                drift.append(f"{role}.{field}: {old.get(field)!r} → {cur.get(field)!r}")
    for role in committed:
        if role not in current:
            drift.append(f"role {role!r} removed from record")
    return drift


def check_voice_consistency(
    record: Dict[str, Any],
    committed: Optional[Dict[str, Dict[str, Any]]],
) -> None:
    """Vergleich + Hard-Stop bei Drift. No-op, wenn noch kein Manifest committet ist.

    Wirft ``VoiceDrift`` — vom Aufrufer VOR jedem Dateizugriff aufzurufen.
    """
    if committed is None:
        return   # erste Vertonung: nichts zu vergleichen (Baseline wird erst danach committet)
    drift = diff_manifest(committed, build_manifest(record))
    if drift:
        raise VoiceDrift(drift)
