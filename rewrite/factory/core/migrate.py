"""Schema-Migrationsrahmen (§7.1) — die single source of truth hat eine Lebensdauer.

Regeln (§7.1):
- Jeder Record trägt ``schema_version``. Fehlt es ⇒ **PRE-Versionierung** (Stufe 0),
  die *älteste* Migration, nie „aktuell". (Ein neues Feld als Zero-Value auf einem
  alten Record zu lesen ist genau die Drift-Falle, die das verhindert.)
- Migrationen sind **pur, forward-only, idempotent**: ``migrate_vN_to_vN+1(rec) → rec``,
  verkettet. Ein bereits aktuelles Record durchläuft nichts (No-op).
- Eine Migration **regeneriert nie Inhalt** (das bräche cast-once) — sie *reshaped* nur
  bestehende Struktur und füllt neue Felder mit explizitem Default oder einem
  ``needs-backfill``-Marker.
- **Frozen canon wird migriert, nie neu-abgeleitet** — sonst käme Fakt-Drift über eine
  Versionsgrenze zurück.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict

from factory.core.schema import SCHEMA_VERSION

# Marker für ein neues Pflichtfeld, das die Migration nicht herleiten kann (§7.1,
# §10.3): kein Fabrikat, sondern ein sichtbarer, resumbarer „muss nachgefüllt werden".
NEEDS_BACKFILL = {"__status__": "needs-backfill"}


def is_needs_backfill(value: Any) -> bool:
    return isinstance(value, dict) and value.get("__status__") == "needs-backfill"


def record_version(record: Dict[str, Any]) -> int:
    """Version eines Records. Fehlend ⇒ 0 (PRE-Versionierung, älteste Stufe)."""
    return int(record.get("schema_version", 0))


# --- konkrete Migrationen ---------------------------------------------------------

# Mapping altes Format → Default-Capabilities (§10.4). Einmaliges, inspizierbares
# Reshape während der Migration — KEINE Laufzeit-Ableitung aus der Datenform.
_FORMAT_DEFAULT_CAPS: Dict[str, list] = {
    "narration": [],
    "media_analysis": [],
    "language_course": ["has_knowledge_split"],
    "crime_drama": ["needs_continuity_review", "has_knowledge_split"],
    "soap_opera": ["needs_continuity_review", "has_knowledge_split", "reuses_locations"],
    "shorts": [],
}


def _migrate_0_to_1(record: Dict[str, Any]) -> Dict[str, Any]:
    """PRE-Versionierung → v1: schema_version setzen, capabilities *deklarieren* (§10.4).

    capabilities war implizit (aus „hat case-Block" abgeleitet). Die Migration macht sie
    explizit: aus dem Format hergeleitet, wo bekannt; sonst needs-backfill (nie geraten).
    """
    rec = copy.deepcopy(record)
    rec["schema_version"] = 1
    if "capabilities" not in rec:
        fmt = rec.get("identity", {}).get("format")
        if fmt in _FORMAT_DEFAULT_CAPS:
            rec["capabilities"] = list(_FORMAT_DEFAULT_CAPS[fmt])
        else:
            # unbekanntes Format → nicht raten, Marker setzen (§7.1)
            rec["capabilities"] = NEEDS_BACKFILL
    return rec


# Registry: from_version → migration-fn. Lücken sind ein Fehler (klare Diagnose).
MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    0: _migrate_0_to_1,
}


def migrate_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Migriere ein Record bis ``SCHEMA_VERSION``. Idempotent; aktuell ⇒ unverändert.

    Wirft ``MigrationError``, wenn eine nötige Stufe fehlt (statt still eine Version zu
    überspringen). Jede Stufe muss die Version *echt* erhöhen — sonst Schutz vor
    Endlosschleife.
    """
    rec = record
    guard = 0
    while record_version(rec) < SCHEMA_VERSION:
        v = record_version(rec)
        step = MIGRATIONS.get(v)
        if step is None:
            raise MigrationError(f"no migration registered from schema_version {v}")
        nxt = step(rec)
        if record_version(nxt) <= v:
            raise MigrationError(
                f"migration from {v} did not advance the version (got {record_version(nxt)})"
            )
        rec = nxt
        guard += 1
        if guard > 1000:   # Sicherheitsnetz gegen eine fehlerhafte Registry
            raise MigrationError("migration chain did not terminate")
    if record_version(rec) > SCHEMA_VERSION:
        raise MigrationError(
            f"record version {record_version(rec)} is newer than supported {SCHEMA_VERSION}"
        )
    return rec


class MigrationError(Exception):
    """Kein Migrationspfad, Nicht-Fortschritt, oder zu neues Record — nie still raten."""
