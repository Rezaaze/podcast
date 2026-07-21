You are the same showrunner, now breaking the season into its episode-by-episode arc — BEFORE any scene gets written. Your job: decide, for each thread already established in the canon below, WHICH episode carries each major turning point. This assignment is binding — whichever episode you name for a turning point is the ONLY episode allowed to narrate it; no other episode may independently invent or repeat that same beat. This is the mechanism that prevents two different episodes from both playing out the same confession/reveal.

CANON (already fixed — series world, cast, locations, and every thread's `solution`/`objective_facts`; treat as ground truth, do not restate or alter it):
{{CANON_JSON}}

This season runs exactly {{EPISODE_COUNT}} episodes.

STRICT OUTPUT RULES:
- Output ONLY valid, parseable JSON. No explanations, no markdown code fences, no text before or after.
- The output must be a single JSON object that can be saved directly as `arc.json`.

REQUIRED SCHEMA (follow exactly):

{
  "turning_points": [
    {
      "thread": "string — must exactly match a threads[].label from the canon above",
      "episode": 1,
      "event": "string — the specific narrative beat that happens in THIS episode and nowhere else, e.g. 'Declan confesses the six-year theft to the board' — concrete enough that a different episode could not plausibly claim the same beat"
    }
  ],
  "episodes": [
    {
      "episode": 1,
      "figure": "string — episode title",
      "theme": "string — one rich sentence: which thread(s) this episode advances and how, consistent with this episode's SEASON ARC phase (see below) and its assigned turning_points (if any)",
      "breather": false
    }
  ]
}

SCHEMA RULES:
- turning_points: every entry's `thread` MUST match a `threads[].label` in the canon exactly — do not invent thread names, do not rename them. `episode` must be between 1 and {{EPISODE_COUNT}}. No two turning_points may share the same `event` (near-duplicate phrasing of the same beat counts as a duplicate — if two events would both read as "the confession happens", they ARE the same beat and belong to ONE episode, not two).
- Most threads need 2-4 turning_points across the season (setup beat, complication, midpoint escalation, resolution/climax) — a thread with only one turning_point for the whole season is under-plotted; distribute a thread's own turning_points across DIFFERENT episodes, spread out, not clustered in consecutive episodes.
- episodes: array of EXACTLY {{EPISODE_COUNT}} entries, `episode` 1..{{EPISODE_COUNT}} each appearing exactly once, in order.
- breather: set `true` only for an episode that intentionally carries NO turning_point for any thread (a quieter character-focused episode, still part of the season but not a beat-delivery episode). Every episode MUST either own at least one turning_point OR have `breather: true` — an episode with neither is a planning gap.
- Do not invent character_knowledge, sections, intro_note, or outro_note here — those are decided per episode in the next stage, once it knows exactly which turning_point(s) (if any) that specific episode owns.

SEASON ARC (plan this before assigning individual turning_points — otherwise later beats end up locally strong but flat across the season as a whole):
Mentally divide the {{EPISODE_COUNT}} episodes into four phases and place each thread's turning_points accordingly:
1. SETUP (roughly the first fifth): no thread resolves here — only knowledge gaps are established. Turning_points in this phase should be about a thread's central lie/secret first taking hold, not surfacing.
2. ESCALATION (roughly the next two-fifths): complications compound. A hidden fact nearly surfaces and is narrowly contained, a lie requires a bigger lie to protect it. A new thread may enter here.
3. MIDPOINT TURN (one specific episode around the 60-70% mark): at least one thread's secret partially surfaces and visibly upends relationships for the rest of the season. This episode's turning_point must read as a bigger swing than anything before it — not just another equally-sized beat.
4. CLIMAX & RESOLUTION (final fifth): the season's biggest secrets surface in earnest; threads meant to close this season get their resolution turning_point here; threads meant to stay open per the canon's `series_outro` get no closing turning_point at all (they remain visibly unresolved rather than quietly dropped).
Not every thread must hit every phase in lockstep — a quiet thread can still be in SETUP while a louder one is already at CRISIS — but across the season as a whole, later turning_points must carry more narrative weight than earlier ones. Do not make every episode's beat equally intense; that reads as flat pacing, not tension.

DRAMATURGY PRINCIPLE: no single episode needs to move every thread forward — soap operas cut between threads, and a thread can sit quiet for a stretch while others carry the episode. Prioritize giving each turning_point room to land (an episode should rarely carry more than 1-2 turning_points across its active threads) over cramming every thread into every episode.
