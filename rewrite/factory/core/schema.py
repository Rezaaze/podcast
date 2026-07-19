"""Series-Record-Schema — die single source of truth (§3.1, §7).

Zwei §7-Lektionen sind hier eingebaut:
- **Flach vor tief.** Wissensslices sind Freitext (1–3 Sätze), keine tief geschachtelten
  Listen — Nestungstiefe (nicht Textmenge) bricht maschinen-generiertes JSON.
- **Drift-anfällige Fakten einfrieren, Rest frei lassen.** ``threads`` (Kanon: label +
  resolution + hard_facts) ist strikt und wird einmal geschrieben; Episoden-Zusätze
  dürfen lockere Prosa sein.

Capabilities werden **deklariert** (§10.4), nicht aus der Datenform abgeleitet. Ein
Feature (Continuity-Review, Knowledge-Split) gilt nur, wenn es hier explizit steht —
nie weil zufällig ein ``case``-Block vorhanden ist.
"""

from __future__ import annotations

from typing import Any, Dict

# Erhöht bei jeder inkompatiblen Schemaänderung; jede Erhöhung braucht eine Migration
# (siehe migrate.py). Fehlt das Feld auf einem Record, gilt er als PRE-Versionierung
# (älteste Migrationsstufe), nie als "aktuell" (§7.1).
SCHEMA_VERSION = 1

MODES = ("narration", "drama")

FORMATS = (
    "narration", "media_analysis",              # narration mode
    "language_course", "crime_drama", "soap_opera", "shorts",  # drama mode
)

# Deklarierbare Capabilities (§10.4). Unbekannte Werte → Warnung (Typo-Erkennung).
KNOWN_CAPABILITIES = (
    "needs_continuity_review",   # Stage B: Post-Check auf Spoiler/Fakt-Konsistenz
    "has_knowledge_split",       # per-Rolle-Wissensslice treibt Lügen/Widersprüche
    "has_beat_layer",            # (Alt-Feature) — im Rewrite ersetzt §10.1 dies i.d.R.
    "has_recap_opener",          # spätere Episoden öffnen mit "previously on"
    "reuses_locations",          # Ensemble-Formate mit wiederkehrenden Orten
)


# JSON-Schema-Teilmenge (type/required/properties/items) — passt zu
# factory.core.model.validate_against_schema. Struktur-Gate; Semantik prüft validator.py.
SERIES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["schema_version", "identity", "cast", "capabilities", "threads", "episodes"],
    "properties": {
        "schema_version": {"type": "integer"},
        "identity": {
            "type": "object",
            "required": ["title", "language", "mode", "format"],
            "properties": {
                "title": {"type": "string"},
                "language": {"type": "string"},
                "mode": {"type": "string"},
                "format": {"type": "string"},
                "narration_style": {"type": "string"},
                "style_guidelines": {"type": "string"},
            },
        },
        "cast": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["role", "voice"],
                "properties": {
                    "role": {"type": "string"},
                    "voice": {"type": "string"},
                    "style": {"type": "string"},
                    "speed": {"type": "number"},
                    "seed": {"type": "integer"},
                },
            },
        },
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["key", "description"],
                "properties": {
                    "key": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "capabilities": {"type": "array", "items": {"type": "string"}},
        "threads": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "resolution"],
                "properties": {
                    "label": {"type": "string"},
                    "resolution": {"type": "string"},
                    "hard_facts": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "episodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["figure", "sections"],
                "properties": {
                    "figure": {"type": "string"},
                    "theme": {"type": "string"},
                    "intro": {"type": "string"},
                    "outro": {"type": "string"},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["title", "what", "who", "thread", "word_budget"],
                            "properties": {
                                "title": {"type": "string"},
                                "what": {"type": "string"},
                                "who": {"type": "array", "items": {"type": "string"}},
                                "thread": {"type": "string"},
                                "location": {"type": "string"},
                                "word_budget": {"type": "integer"},
                            },
                        },
                    },
                    # case: Freitext-Wissensslice (§7 flach-vor-tief) — Objekt ODER Liste,
                    # daher hier bewusst nicht strikt typisiert.
                },
            },
        },
    },
}


def minimal_valid_record() -> Dict[str, Any]:
    """Kleinstes strukturell + semantisch gültiges Record — Basis für Tests/One-shot-Degeneration."""
    return {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "title": "Untitled",
            "language": "en",
            "mode": "drama",
            "format": "crime_drama",
        },
        "cast": [
            {"role": "NARRATOR", "voice": "voice_a"},
            {"role": "DETECTIVE", "voice": "voice_b"},
        ],
        "capabilities": ["needs_continuity_review", "has_knowledge_split"],
        "threads": [
            {"label": "the_case", "resolution": "the butler did it", "hard_facts": ["knife"]},
        ],
        "episodes": [
            {
                "figure": "DETECTIVE",
                "theme": "arrival",
                "sections": [
                    {
                        "title": "opening",
                        "what": "the detective arrives at the manor and meets the staff",
                        "who": ["DETECTIVE", "NARRATOR"],
                        "thread": "the_case",
                        "word_budget": 300,
                    }
                ],
            }
        ],
    }
