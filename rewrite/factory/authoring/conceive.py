"""Stage A — Conceive (decomposed): Canon → Arc → Episode-Concept (§ Stage A, §10.2).

Der Kern-Insight des Blueprints. Statt alle Episoden in einem (oder wenigen Batch-)Calls
zu schreiben, drei Tiers:

- **A1 Canon** (ein Call): Welt, Cast, Locations, Threads (frozen: label + resolution + facts).
- **A2 Arc** (ein Call, sieht Canon): weist jeden Turning-Point GENAU einer Episode zu +
  figure/theme je Episode. Damit wird ein Doppel-Climax *strukturell* unmöglich.
- **A3 Episode-Concept** (ein Call PRO Episode, parallel): sieht Canon + Arc + die eigenen
  zugewiesenen Turning-Points + eine **Exclusion-List** der fremden (§10.2 revidiert:
  Exclusion-List statt Nachbar-Summaries — die partielle Cross-Sicht war die Wurzelursache,
  die der Judge später teuer nachfing). Nie den Parallel-Output der Geschwister.

Jeder Tier ist eine eigene Checkpoint-Einheit (§2.10), gekeyt auf Call-Parameter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from factory.core.checkpoint import CheckpointStore, key_of
from factory.core.model import Model
from factory.core.queue import WorkQueue
from factory.core.retry import ValidationResult, run_with_retry
from factory.core.schema import SCHEMA_VERSION
from factory.core.validator import validate_series
from factory.authoring.detail_band import check_detail_band

# --- Schemas für die drei Tiers (structured output, §10.8) -------------------------

CANON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["cast", "threads"],
    "properties": {
        "cast": {"type": "array", "items": {
            "type": "object", "required": ["role", "voice"],
            "properties": {"role": {"type": "string"}, "voice": {"type": "string"}}}},
        "locations": {"type": "array", "items": {
            "type": "object", "required": ["key", "description"],
            "properties": {"key": {"type": "string"}, "description": {"type": "string"}}}},
        "threads": {"type": "array", "items": {
            "type": "object", "required": ["label", "resolution"],
            "properties": {"label": {"type": "string"}, "resolution": {"type": "string"},
                           "hard_facts": {"type": "array", "items": {"type": "string"}}}}},
    },
}

ARC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["turning_points", "episodes"],
    "properties": {
        "turning_points": {"type": "array", "items": {
            "type": "object", "required": ["id", "description", "episode"],
            "properties": {"id": {"type": "string"}, "description": {"type": "string"},
                           "episode": {"type": "integer"}}}},
        "episodes": {"type": "array", "items": {
            "type": "object", "required": ["figure", "theme"],
            "properties": {"figure": {"type": "string"}, "theme": {"type": "string"}}}},
    },
}

EPISODE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["sections"],
    "properties": {
        "sections": {"type": "array", "items": {
            "type": "object", "required": ["title", "what", "who", "thread", "word_budget"],
            "properties": {"title": {"type": "string"}, "what": {"type": "string"},
                           "who": {"type": "array", "items": {"type": "string"}},
                           "thread": {"type": "string"}, "location": {"type": "string"},
                           "word_budget": {"type": "integer"}, "turning_point": {"type": "string"}}}},
        "intro": {"type": "string"}, "outro": {"type": "string"},
    },
}

# Sprech-Richtwert für vertonte Dramen-Prosa (§14-Konstante): Minuten → Wortbudget.
WORDS_PER_MINUTE = 140


@dataclass
class ConceiveConfig:
    topic: str
    language: str = "en"
    mode: str = "drama"
    format: str = "crime_drama"
    narration_style: str = ""
    capabilities: Optional[List[str]] = None
    max_attempts: int = 3
    target_episodes: Optional[int] = None  # None = das Modell wählt die Staffellänge
    target_minutes: Optional[int] = None   # None = das Modell wählt die Episodenlänge


def _prompt(kind: str, payload: Dict[str, Any]) -> str:
    """Kompaktes, deterministisches Prompt. Die echten Prompt-Contracts leben später in
    references/; hier zählt, DASS Canon/Arc/Exclusion korrekt hineingereicht werden."""
    import json
    return f"[{kind}]\n" + json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _episode_exclusion_list(arc: Dict[str, Any], ep_index: int) -> List[Dict[str, Any]]:
    """Turning-Points, die NICHT in diese Episode gehören (§10.2 Exclusion-List)."""
    return [tp for tp in arc["turning_points"] if tp["episode"] != ep_index]


def _assigned_turning_points(arc: Dict[str, Any], ep_index: int) -> List[Dict[str, Any]]:
    return [tp for tp in arc["turning_points"] if tp["episode"] == ep_index]


def conceive(
    cfg: ConceiveConfig,
    model: Model,
    checkpoints: CheckpointStore,
    queue: Optional[WorkQueue] = None,
) -> Dict[str, Any]:
    """Führe den decomposed Pfad aus und liefere ein validiertes Series-Record.

    Jeder Tier ist checkpoint-gecacht: ein Re-Run regeneriert nur Fehlendes. Episoden
    laufen parallel über die Work-Queue (§10.7) — jede blind gegenüber den Geschwistern.
    """
    queue = queue or WorkQueue()

    # A1 — Canon (eine Checkpoint-Einheit)
    canon_key = key_of("canon", cfg.topic, cfg.format, cfg.language)
    canon = checkpoints.get_or_compute(
        canon_key,
        lambda: model.generate_structured(_prompt("CANON", {"topic": cfg.topic}), CANON_SCHEMA),
    )

    # A2 — Arc (sieht Canon; alloziert Turning-Points)
    arc_key = key_of("arc", cfg.topic, cfg.format, canon_key,
                     cfg.target_episodes, cfg.target_minutes)
    arc_payload: Dict[str, Any] = {"canon": canon}
    if cfg.target_episodes is not None:
        arc_payload["target_episodes"] = cfg.target_episodes
    if cfg.target_minutes is not None:
        arc_payload["target_minutes_per_episode"] = cfg.target_minutes
    arc = checkpoints.get_or_compute(
        arc_key,
        lambda: model.generate_structured(_prompt("ARC", arc_payload), ARC_SCHEMA),
    )
    n_episodes = len(arc["episodes"])

    # A3 — Episode-Concepts (parallel, jede mit Exclusion-List, checkpoint pro Episode)
    def make_episode(ep_index: int) -> Dict[str, Any]:
        ep_key = key_of("episode", cfg.topic, arc_key, ep_index)

        def compute() -> Dict[str, Any]:
            payload = {
                "episode_index": ep_index,
                "canon": canon,
                "arc_episode": arc["episodes"][ep_index],
                "assigned_turning_points": _assigned_turning_points(arc, ep_index),
                "exclude_turning_points": _episode_exclusion_list(arc, ep_index),
            }
            if cfg.target_minutes is not None:
                # Längenziel → Wortbudget-Summe; das Modell verteilt sie auf die Sections.
                payload["target_words_total"] = cfg.target_minutes * WORDS_PER_MINUTE
                payload["target_minutes"] = cfg.target_minutes
            base = _prompt("EPISODE", payload)

            def gen(prompt: str) -> Dict[str, Any]:
                return model.generate_structured(prompt, EPISODE_SCHEMA)

            def validate(concept: Dict[str, Any]) -> ValidationResult:
                band = check_detail_band(concept["sections"])
                if not band.ok:
                    # weiches Kriterium: mit Feedback retryen, nie fatal (§2.6)
                    return ValidationResult(ok=False, fatal=False, badness=len(band.offenders) + 1,
                                            detail=band.detail)
                return ValidationResult(ok=True, fatal=False, badness=0.0, detail="")

            return run_with_retry(gen, validate, base_prompt=base, max_attempts=cfg.max_attempts)

        return checkpoints.get_or_compute(ep_key, compute)

    concepts = queue.map(make_episode, list(range(n_episodes)))

    record = _assemble(cfg, canon, arc, concepts)
    return record


def _assemble(
    cfg: ConceiveConfig,
    canon: Dict[str, Any],
    arc: Dict[str, Any],
    concepts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Setze Canon + Arc + Episode-Concepts zum Series-Record zusammen (§ Stage A Assemble)."""
    caps = cfg.capabilities
    if caps is None:
        caps = ["needs_continuity_review", "has_knowledge_split"] if cfg.mode == "drama" else []

    episodes = []
    for ei, concept in enumerate(concepts):
        arc_ep = arc["episodes"][ei]
        episodes.append({
            "figure": arc_ep["figure"],
            "theme": arc_ep["theme"],
            "intro": concept.get("intro", ""),
            "outro": concept.get("outro", ""),
            "sections": concept["sections"],
        })

    identity = {
        "title": cfg.topic,
        "language": cfg.language,
        "mode": cfg.mode,
        "format": cfg.format,
    }
    if cfg.narration_style:
        identity["narration_style"] = cfg.narration_style

    return {
        "schema_version": SCHEMA_VERSION,
        "identity": identity,
        "cast": canon["cast"],
        "locations": canon.get("locations", []),
        "capabilities": caps,
        "threads": canon["threads"],
        "episodes": episodes,
    }
