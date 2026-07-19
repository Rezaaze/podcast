"""Der EINE Series-Record-Validator (§5, §10.4).

Validierungs-Policy (§5):
- **Struktur-invalid → harter Fehler** *vor* jeder Arbeit (würde Downstream crashen).
- **Legal aber verdächtig → Warnung.**
- **Unbekanntes Feld → Warnung** (Typo-Erkennung für maschinen-generiertes JSON).

Genau *eine* Stelle: die Concept-Generierung (Stage A) validiert später, indem sie ein
Kandidat-Record baut und ``validate_series`` darauf laufen lässt — nie eine zweite,
divergierende Prüf-Logik. Das ist die §5-„one validator reused everywhere"-Regel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from factory.core.model import validate_against_schema
from factory.core.schema import (
    FORMATS,
    KNOWN_CAPABILITIES,
    MODES,
    SCHEMA_VERSION,
    SERIES_SCHEMA,
)


@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)     # hart: blockiert Arbeit
    warnings: List[str] = field(default_factory=list)   # verdächtig/unbekannt: erlaubt

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def __str__(self) -> str:
        lines = [f"ERROR: {e}" for e in self.errors]
        lines += [f"warn:  {w}" for w in self.warnings]
        return "\n".join(lines) or "OK"


def _collect_unknown_fields(obj: Any, schema: Dict[str, Any], path: str, out: List[str]) -> None:
    """Sammle Pfade, an denen ein dict Schlüssel hat, die das Schema nicht kennt.

    Nur dort, wo das Schema ``properties`` deklariert — Blöcke wie ``case`` (bewusst
    unstrukturiert) haben keine properties und werden nicht gescannt.
    """
    if isinstance(obj, dict):
        props = schema.get("properties")
        if props is not None:
            for key in obj:
                if key not in props:
                    out.append(f"{path}.{key}")
            for key, sub in props.items():
                if key in obj:
                    _collect_unknown_fields(obj[key], sub, f"{path}.{key}", out)
    elif isinstance(obj, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(obj):
                _collect_unknown_fields(item, item_schema, f"{path}[{i}]", out)


def validate_series(record: Dict[str, Any]) -> ValidationReport:
    report = ValidationReport()

    # 1) Struktur (harte Fehler, vor allem anderen).
    struct_err = validate_against_schema(record, SERIES_SCHEMA)
    if struct_err is not None:
        report.errors.append(f"structure: {struct_err}")
        return report   # ohne gültige Struktur ist Semantik sinnlos

    # 2) Schema-Version (§7.1): ein Record hier soll AKTUELL sein; Altversionen gehören
    #    erst durch migrate.py. Falsche Version ist ein harter Fehler mit klarer Ansage.
    version = record["schema_version"]
    if version != SCHEMA_VERSION:
        report.errors.append(
            f"schema_version {version} != current {SCHEMA_VERSION} — migrate before validating"
        )

    identity = record["identity"]

    # 3) Mode/Format bekannt? (Typo-Erkennung → Warnung, nicht hart.)
    if identity["mode"] not in MODES:
        report.warnings.append(f"identity.mode {identity['mode']!r} is not a known mode {MODES}")
    if identity["format"] not in FORMATS:
        report.warnings.append(f"identity.format {identity['format']!r} is not a known format")

    # 4) Zwei Rollen → dieselbe Voice = harter Fehler (§3.1, § Stage C Voice-Guard).
    seen: Dict[str, str] = {}
    for member in record["cast"]:
        voice = member["voice"]
        if voice in seen:
            report.errors.append(
                f"voice {voice!r} maps to both {seen[voice]!r} and {member['role']!r} "
                f"— two roles may never share a voice"
            )
        else:
            seen[voice] = member["role"]

    # 5) Capabilities deklariert & bekannt (§10.4). Unbekannt → Warnung (Typo).
    for cap in record["capabilities"]:
        if cap not in KNOWN_CAPABILITIES:
            report.warnings.append(f"unknown capability {cap!r}")

    # 6) Referentielle Integrität: jede section.thread muss in threads existieren.
    #    Ein Verweis ins Leere bricht Downstream → harter Fehler.
    thread_labels = {t["label"] for t in record["threads"]}
    role_names = {m["role"] for m in record["cast"]}
    for ei, ep in enumerate(record["episodes"]):
        for si, sec in enumerate(ep["sections"]):
            where = f"episodes[{ei}].sections[{si}]"
            if sec["thread"] not in thread_labels:
                report.errors.append(
                    f"{where}.thread {sec['thread']!r} not found in threads {sorted(thread_labels)}"
                )
            for who in sec["who"]:
                if who not in role_names:
                    # nur Warnung: ein Statist muss nicht zwingend im Cast stehen
                    report.warnings.append(f"{where}.who {who!r} is not a cast role")

    # 7) Unbekannte Felder überall → Warnungen (§5 Typo-Erkennung).
    unknown: List[str] = []
    _collect_unknown_fields(record, SERIES_SCHEMA, "$", unknown)
    for pth in unknown:
        report.warnings.append(f"unknown field {pth}")

    return report
