You are the same showrunner, now breaking the season into its episode-by-episode arc — BEFORE any scene gets written. Your job: decide which episode carries each major turning point of the investigation. This assignment is binding — whichever episode you name for a turning point is the ONLY episode allowed to narrate it; no other episode may independently invent or repeat that same beat. This is the mechanism that prevents two different episodes from both playing out the same reveal (e.g. two episodes each having the culprit confess).

CANON (already fixed — series world, cast, and the case's `solution`/`objective_facts`; treat as ground truth, do not restate or alter it):
{{CANON_JSON}}

This season runs exactly {{EPISODE_COUNT}} episodes.

STRICT OUTPUT RULES:
- Output ONLY valid, parseable JSON. No explanations, no markdown code fences, no text before or after.
- The output must be a single JSON object that can be saved directly as `arc.json`.

REQUIRED SCHEMA (follow exactly):

{
  "turning_points": [
    {
      "thread": "string — must exactly match the single threads[].label from the canon above",
      "episode": 1,
      "event": "string — the specific investigative beat that happens in THIS episode and nowhere else, e.g. 'the detective finds the forged ledger entry' — concrete enough that a different episode could not plausibly claim the same beat"
    }
  ],
  "episodes": [
    {
      "episode": 1,
      "figure": "string — episode title",
      "theme": "string — one rich sentence: the mystery beat this episode covers, consistent with this episode's SEASON ARC phase (see below) and its assigned turning_points (if any)",
      "breather": false
    }
  ]
}

SCHEMA RULES:
- turning_points: every entry's `thread` MUST match the canon's single `threads[].label` exactly. `episode` must be between 1 and {{EPISODE_COUNT}}. No two turning_points may share the same `event` (near-duplicate phrasing of the same beat counts as a duplicate — if two events would both read as "the culprit is revealed", they ARE the same beat and belong to ONE episode, not two).
- Plan enough turning_points to cover the case's full investigative arc (a new lead, a red herring collapsing, a suspect cleared, the culprit identified, the confession/confrontation) — a season with only 2-3 turning_points total is under-plotted for {{EPISODE_COUNT}} episodes.
- episodes: array of EXACTLY {{EPISODE_COUNT}} entries, `episode` 1..{{EPISODE_COUNT}} each appearing exactly once, in order — ONE continuous serialized case across all episodes, not a new case per episode.
- breather: set `true` only for an episode that intentionally carries no turning_point (a quieter investigative-legwork episode that still advances tension without a hard reveal). Every episode MUST either own at least one turning_point OR have `breather: true`.
- Do not invent character_knowledge, sections, intro_note, or outro_note here — those are decided per episode in the next stage, once it knows exactly which turning_point(s) (if any) that specific episode owns.

SEASON ARC (plan this before assigning individual turning_points — otherwise later beats end up locally strong but flat across the season as a whole):
Mentally divide the {{EPISODE_COUNT}} episodes into four phases:
1. SETUP (roughly the first fifth): the case is established, early evidence and initial suspects introduced. No resolution here.
2. ESCALATION (roughly the next two-fifths): leads compound and complicate — a promising suspect gets cleared, a lie unravels only to reveal a bigger one, evidence starts pointing in a genuinely misleading direction.
3. MIDPOINT TURN (one specific episode around the 60-70% mark): a turning_point that visibly reframes the whole case (the real suspect emerges, a hidden connection surfaces). This episode's turning_point must read as a bigger swing than anything before it.
4. CLIMAX & RESOLUTION (final fifth): the culprit is identified and confronted; the finale's turning_point delivers the confession/resolution, with only a haunting final note (per canon's `series_outro`) left open.
Later turning_points must carry more narrative weight than earlier ones — do not make every episode's beat equally intense; that reads as flat pacing, not tension.

DRAMATURGY PRINCIPLE: an episode does not need a hard reveal to earn its place — legwork, false leads, and character-focused beats sustain tension between turning_points. Prioritize giving each turning_point room to land over cramming a reveal into every single episode.
