"""Stage B — Skripte schreiben (§ Stage B, §10.1).

**Eine** Kontinuitätsstrategie (§10.1 lean two), nicht drei: der section-Call sieht den
*vollen Episodenplan* + eine *laufende Zusammenfassung* der Vorepisoden. Damit kollabieren
Beat-Layer und schweres Review in eine Schicht; es bleibt nur ein *dünner* Post-Check für
das, was Planung strukturell nicht fangen kann (Prosa-Spoiler, Fakt-Konsistenz).

Jede fertige Section wird sofort geschrieben und ihr Status als State-Record (§10.3)
markiert — Resume überspringt fertige Sections. Section-Generierung nutzt das *starke*
Modell, der Post-Check das *billige* (§ Stage B Light-vs-Heavy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from factory.core.checkpoint import CheckpointStore
from factory.core.model import Model
from factory.core.retry import ValidationResult, run_with_retry
from factory.core.state import StateStore, Status
from factory.authoring.hazard import hazard_feedback, scan_hazards
from factory.authoring.phrase_guard import build_phrase_report
from factory.authoring.season_fold import season_fold
from factory.authoring.word_budget import accept_immediately_threshold, check_word_budget

SECTION_SCRIPT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["lines"],
    "properties": {
        "lines": {"type": "array", "items": {
            "type": "object", "required": ["speaker", "text"],
            "properties": {"speaker": {"type": "string"}, "text": {"type": "string"},
                           "style": {"type": "string"}, "speed": {"type": "number"}}}},
    },
}

REVIEW_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["findings"],
    "properties": {
        "findings": {"type": "array", "items": {
            "type": "object", "required": ["message"],
            "properties": {"message": {"type": "string"}, "section": {"type": "integer"}}}},
    },
}

_NARRATOR = "NARRATOR"


def section_text(script: Dict[str, Any]) -> str:
    return " ".join(line.get("text", "") for line in script.get("lines", []))


def _exempt_names(record: Dict[str, Any]) -> List[str]:
    names = [m["role"] for m in record.get("cast", [])]
    names += [loc["key"] for loc in record.get("locations", [])]
    return names


@dataclass
class SectionContext:
    episode_plan: List[Dict[str, Any]]      # ALLE Sections dieser Episode (voller Plan)
    running_summary: List[Dict[str, Any]]   # Zusammenfassung der Vorepisoden (Season-Fold)
    prior_sections: List[str]               # bereits geschriebene Sections dieser Episode (dünn)
    avoid_block: str                         # Phrase-Guard
    section_index: int
    language: str


def _section_prompt(record: Dict[str, Any], ep_index: int, ctx: SectionContext) -> str:
    import json
    sec = ctx.episode_plan[ctx.section_index]
    payload = {
        "write_section": sec,
        "full_episode_plan": ctx.episode_plan,      # §10.1: der ganze Plan, nicht nur der Vorgänger
        "prior_episodes_summary": ctx.running_summary,
        "prior_sections_this_episode": ctx.prior_sections,
    }
    prompt = "[SECTION]\n" + json.dumps(payload, sort_keys=True, ensure_ascii=False)
    if ctx.avoid_block:
        prompt += "\n\n" + ctx.avoid_block
    return prompt


def _validate_section(script: Dict[str, Any], target: int, language: str) -> ValidationResult:
    """Kombiniert Hazard-Checks + Wortbudget zu einem Ergebnis (schlimmstes gewinnt)."""
    hazards = scan_hazards(script.get("lines", []), narrator_role=_NARRATOR, language=language)
    if hazards:
        return ValidationResult(
            ok=False, fatal=False, badness=1.0 + len(hazards),
            detail="hazards: " + hazard_feedback(hazards),
        )
    return check_word_budget(section_text(script), target,
                             tokenize=lambda t: len(t.split()))


def write_section(
    record: Dict[str, Any],
    ep_index: int,
    ctx: SectionContext,
    model: Model,
    state: StateStore,
    checkpoints: CheckpointStore,
) -> Dict[str, Any]:
    """Schreibe (oder resume) eine Section. Sofort persistiert, Status als State-Record."""
    sec = ctx.episode_plan[ctx.section_index]
    unit_id = f"ep{ep_index}/sec{ctx.section_index}"

    if state.is_done(unit_id):
        cached = checkpoints.get(unit_id)
        if cached is not None:
            return cached   # Resume: fertige Section überspringen (§10.3, State ist die Wahrheit)

    target = int(sec.get("word_budget", 200))
    base = _section_prompt(record, ep_index, ctx)

    def gen(prompt: str) -> Dict[str, Any]:
        return model.generate_structured(prompt, SECTION_SCRIPT_SCHEMA, tier="strong")

    script = run_with_retry(
        gen,
        lambda s: _validate_section(s, target, ctx.language),
        base_prompt=base,
        max_attempts=3,
        accept_immediately_below=accept_immediately_threshold(target),
    )

    # Endstatus: sauber → COMPLETE, best-effort-Fallback → DEGRADED (§10.3, kein stilles done)
    final = _validate_section(script, target, ctx.language)
    status = Status.COMPLETE if final.ok else Status.DEGRADED
    checkpoints.put(unit_id, script)
    state.mark(unit_id, status, produced=unit_id, badness=final.badness, detail=final.detail)
    return script


def _repair_section(
    record: Dict[str, Any],
    ep_index: int,
    ctx: SectionContext,
    feedback: str,
    model: Model,
    state: StateStore,
    checkpoints: CheckpointStore,
) -> Dict[str, Any]:
    """Regeneriere EINE Section mit Review-Feedback; überschreibt Checkpoint+State.

    Anders als ``write_section`` ignoriert das bewusst den Resume-Cache — die alte Section
    IST der Fehler, den wir ersetzen. Hazard/Wortbudget-Validierung bleibt gleich."""
    sec = ctx.episode_plan[ctx.section_index]
    unit_id = f"ep{ep_index}/sec{ctx.section_index}"
    target = int(sec.get("word_budget", 200))
    base = _section_prompt(record, ep_index, ctx) + (
        "\n\nCONTINUITY/FACT FIX REQUIRED — the previous version of this section had these "
        "problems. Rewrite the section to resolve them, keeping everything else intact:\n"
        + feedback
    )

    def gen(prompt: str) -> Dict[str, Any]:
        return model.generate_structured(prompt, SECTION_SCRIPT_SCHEMA, tier="strong")

    script = run_with_retry(
        gen,
        lambda s: _validate_section(s, target, ctx.language),
        base_prompt=base,
        max_attempts=3,
        accept_immediately_below=accept_immediately_threshold(target),
    )
    final = _validate_section(script, target, ctx.language)
    status = Status.COMPLETE if final.ok else Status.DEGRADED
    checkpoints.put(unit_id, script)
    state.mark(unit_id, status, produced=unit_id, badness=final.badness, detail=final.detail)
    return script


def repair_episode(
    record: Dict[str, Any],
    ep_index: int,
    episode: Dict[str, Any],
    findings: List[Dict[str, Any]],
    running_summary: List[Dict[str, Any]],
    avoid_block: str,
    model: Model,
    state: StateStore,
    checkpoints: CheckpointStore,
) -> Dict[str, Any]:
    """Gate: Findings mit gültigem ``section``-Index → betroffene Sections neu schreiben.

    Findings ohne targetbaren Section-Index (episoden-weit) bleiben unangetastet — sie
    tauchen im Nach-Review wieder auf und werden dann ehrlich als überlebend gespeichert.
    Liefert die neu zusammengesetzte Episode."""
    plan = record["episodes"][ep_index]["sections"]
    language = record["identity"].get("language", "en")
    sections = list(episode["sections"])

    by_section: Dict[int, List[str]] = {}
    for f in findings:
        idx = f.get("section")
        if isinstance(idx, int) and 0 <= idx < len(plan) and idx < len(sections):
            by_section.setdefault(idx, []).append(f.get("message", ""))

    for idx in sorted(by_section):
        prior_texts = [" ".join(section_text(sections[j]).split()[-25:]) for j in range(idx)]
        ctx = SectionContext(
            episode_plan=plan, running_summary=running_summary,
            prior_sections=prior_texts, avoid_block=avoid_block,
            section_index=idx, language=language,
        )
        feedback = "\n".join(f"- {m}" for m in by_section[idx] if m)
        sections[idx] = _repair_section(record, ep_index, ctx, feedback, model, state, checkpoints)

    return {
        "episode": ep_index,
        "sections": sections,
        "text": " ".join(section_text(s) for s in sections),
        "summary": _episode_summary(record, ep_index, sections),
    }


def _episode_summary(record: Dict[str, Any], ep_index: int, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministische laufende Zusammenfassung (kein Extra-LLM-Call) für den Season-Fold."""
    ep = record["episodes"][ep_index]
    closing = section_text(sections[-1]) if sections else ""
    return {
        "episode": ep_index,
        "figure": ep.get("figure"),
        "theme": ep.get("theme"),
        "section_titles": [s.get("title") for s in ep.get("sections", [])],
        "closing_excerpt": " ".join(closing.split()[-25:]),   # dünner horizontaler Seam
    }


def write_episode(
    record: Dict[str, Any],
    ep_index: int,
    model: Model,
    state: StateStore,
    checkpoints: CheckpointStore,
    running_summary: List[Dict[str, Any]],
    avoid_block: str,
) -> Dict[str, Any]:
    plan = record["episodes"][ep_index]["sections"]
    language = record["identity"].get("language", "en")
    written: List[Dict[str, Any]] = []
    prior_texts: List[str] = []

    for si in range(len(plan)):
        ctx = SectionContext(
            episode_plan=plan,
            running_summary=running_summary,
            prior_sections=list(prior_texts),
            avoid_block=avoid_block,
            section_index=si,
            language=language,
        )
        script = write_section(record, ep_index, ctx, model, state, checkpoints)
        written.append(script)
        prior_texts.append(" ".join(section_text(script).split()[-25:]))

    return {
        "episode": ep_index,
        "sections": written,
        "text": " ".join(section_text(s) for s in written),
        "summary": _episode_summary(record, ep_index, written),
    }


def review_episode(
    record: Dict[str, Any],
    ep_index: int,
    episode: Dict[str, Any],
    model: Model,
) -> List[Dict[str, Any]]:
    """Dünner Post-Check (§10.1): nur was Planung nicht fangen kann (Spoiler, Fakt-Konsistenz).

    Gated auf ``needs_continuity_review``. Nutzt das *billige* Modell (§ Stage B). Ein
    fehlendes Capability ⇒ kein Review (leere Liste), nie ein stilles "clean".
    """
    if "needs_continuity_review" not in record.get("capabilities", []):
        return []
    import json
    payload = {"threads": record["threads"], "episode_text": episode["text"]}
    result = model.generate_structured(
        "[REVIEW]\n" + json.dumps(payload, sort_keys=True, ensure_ascii=False),
        REVIEW_SCHEMA, tier="cheap",
    )
    return result["findings"]


@dataclass
class SeriesScript:
    episodes: List[Dict[str, Any]] = field(default_factory=list)
    reviews: Dict[int, List[Dict[str, Any]]] = field(default_factory=dict)
    phrase_reports: List[str] = field(default_factory=list)


def write_series(
    record: Dict[str, Any],
    model: Model,
    state: StateStore,
    checkpoints: CheckpointStore,
    *,
    max_repair_passes: int = 1,
) -> SeriesScript:
    """Schreibe alle Episoden im Season-Fold (§10.5): jede sieht das Aggregat der vorigen.

    Review-Gate (§ Stage B): jedes Post-Check-Finding mit Section-Index wird durch
    Neuschreiben der Section behoben (``max_repair_passes``, gebunden gegen Endlosschleifen),
    dann nach-reviewt. Nur *überlebende* Findings landen in ``out.reviews`` — kein stilles
    Verschlucken erkannter Widersprüche mehr."""
    out = SeriesScript()
    exempt = _exempt_names(record)

    def step(ep: Dict[str, Any], i: int, prior: List[Dict[str, Any]]) -> Dict[str, Any]:
        prior_texts = [p["text"] for p in prior]
        report = build_phrase_report(prior_texts, exempt_names=exempt)
        running_summary = [p["summary"] for p in prior]
        episode = write_episode(record, i, model, state, checkpoints,
                                running_summary, report.avoid_block)
        out.phrase_reports.append(report.report)

        findings = review_episode(record, i, episode, model)
        passes = 0
        while findings and passes < max_repair_passes:
            episode = repair_episode(record, i, episode, findings, running_summary,
                                     report.avoid_block, model, state, checkpoints)
            findings = review_episode(record, i, episode, model)
            passes += 1
        if findings:
            out.reviews[i] = findings   # was einen Repair-Pass überlebt hat — ehrlich vermerkt
        return episode

    out.episodes = season_fold(record["episodes"], step)
    return out
