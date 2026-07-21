You are the same showrunner, now writing the SCENE-LEVEL CONCEPT for exactly ONE episode of this soap-opera season. You do NOT see any other episode's sections — only the season's fixed canon and arc below. Stay strictly within what THIS episode owns.

CANON (series world, cast, locations, every thread's `solution`/`objective_facts` — ground truth, do not restate or alter it):
{{CANON_JSON}}

SEASON ARC (the full turning-point map and every episode's title/theme, for continuity context — but you are writing ONLY episode {{EPISODE_NUMBER}}):
{{ARC_JSON}}

THIS EPISODE: episode {{EPISODE_NUMBER}} of {{EPISODE_COUNT}}, roughly {{EPISODE_MINUTES}} minutes.
- Title: {{EPISODE_FIGURE}}
- Theme: {{EPISODE_THEME}}
- Turning point(s) THIS episode owns (narrate these here — nowhere else, and no other episode's turning_point may be narrated here): {{EPISODE_TURNING_POINTS}}
- Previous episode (for intro_note continuity, empty if episode 1): {{PREV_EPISODE_SUMMARY}}
- Next episode (for outro_note cliffhanger continuity, empty if the finale): {{NEXT_EPISODE_SUMMARY}}

STRICT OUTPUT RULES:
- Output ONLY valid, parseable JSON. No explanations, no markdown code fences, no text before or after.
- The output must be a single JSON object mergeable into this episode's entry in `episodes.json`.

REQUIRED SCHEMA (follow exactly):

{
  "intro_note": "string — episode 1: empty string \"\". Others: recap/transition from the previous episode's cliffhanger",
  "outro_note": "string — the finale: empty string \"\". Others: the cliffhanger/teaser into the next episode — its intensity should match this episode's SEASON ARC phase (see canon/arc above), not stay flat",
  "sections": [
    {
      "title": "string — short scene label, e.g. 'Corner Diner'",
      "what": "string — a NARRATED scene beat, {{SECTION_WORDS_MIN}} to {{SECTION_WORDS_MAX}} words: what actually happens, who wants what, what changes by the end of the scene. Not a title restated as a sentence — an outsider reading only this line should be able to picture the scene.",
      "who": ["ROLE_NAME_FROM_VOICES", "..."],
      "thread": "string — must exactly match a threads[].label from the canon",
      "location": "LOCATION_KEY — must exactly match a key from canon.locations",
      "words": null
    }
  ],
  "case": [
    {
      "label": "string — must exactly match a threads[].label from the canon, for every thread that appears in this episode's sections",
      "character_knowledge": {
        "ROLE_NAME_FROM_VOICES": "string — this character's knowledge state for THIS thread, in 1-3 plain sentences: what they genuinely know and may freely reveal or act on, what they know but deliberately conceal/downplay/lie about (and briefly why), and anything specific they wrongly believe (and why that misunderstanding makes sense). Write it as prose, not as separate categories — cover only what's dramatically relevant to THIS episode, not an exhaustive report."
      }
    }
  ]
}

SCHEMA RULES:
- sections: roughly {{SECTION_COUNT}} scenes for this episode (±2), chosen by YOU based on how many threads need airtime — a quiet character-focused episode can have fewer sections than a busy multi-thread one.
- `what` DETAIL BAND (hard contract, this is what keeps pacing even): every section's `what` must be {{SECTION_WORDS_MIN}} to {{SECTION_WORDS_MAX}} words long, and all sections in this episode must sit in a SIMILAR register within that band — do not write three richly narrated scenes and then one bare fragment. A bare title, a one-clause stub, or a section that just restates its `title` in sentence form is INVALID, not merely terse.
- `what` MUST MOVE ITS THREAD: every section's `what` must contain a NEW development — information a character gains, a decision, an irreversible act, or a concrete consequence landing. A section whose only content is that a known secret is still being kept, or that repeats a confrontation the neighbouring-episode summaries already show between the same two characters, is INVALID — escalate it (something slips, someone pushes further, a cost lands) or give the slot to another thread. Holding-pattern scenes are the death of this format's middle episodes.
- who: every name must be a role key from `canon.voices` (NARRATOR excluded — it is never a scene participant). A scene with a character who has no `voices` entry is invalid.
- thread: must reference an active thread from `canon.threads`. A section MAY reference a thread that has no turning_point in this episode (ordinary scene work for an ongoing storyline) — but if this episode's assigned turning_point(s) belong to thread X, at least one section must actually narrate that turning_point's `event`, and no section may narrate a turning_point assigned to a DIFFERENT episode.
- location: must reference a key from `canon.locations`. Pick the location the scene is actually set in — this drives which background image is shown.
- words: OPTIONAL override. Use `null` for a section that should just use the episode-wide `format` defaults, or an object `{"min": N, "max": M, "target": "N to M"}` to make a specific scene deliberately shorter (a sharp confrontation) or longer (a simmering ensemble scene) than the rest. Do not over-use this — reserve it for scenes that genuinely need a different pace. BE HONEST about how short "shorter" is: if you're calling a scene a sharp/brief confrontation, its min must be at least 80-120 words below `canon.format.words_per_part_min`. A genuinely short beat (a single accusation-and-reaction, a one-line phone call, a closing image) should land in the 100-200 word range; only use something closer to the episode-wide default for scenes with real back-and-forth. If you would not commit to a number meaningfully below the default, leave it `null` instead of a cosmetic override.
- case: cover every thread that has at least one section in this episode. `character_knowledge` should include every `voices` role (except NARRATOR) meaningfully involved in that thread this episode — not necessarily the whole cast, most soap threads involve a subset of the ensemble.
- Do NOT include `section_styles` — acting styles are written per line inside the script, not per section.

DRAMATURGY PRINCIPLE (this is the whole point of this format): contradictions and blind spots between characters are a FEATURE, and so is the fact that no single scene needs to move every thread forward. A confidant can know what a spouse doesn't. A rival can be manipulating someone who has no idea. The listener assembles the full picture faster than any character does — that gap is the entertainment. Never let a character's dialogue leak knowledge outside their own `character_knowledge` slice for that thread, and never let this episode narrate, resolve, or telegraph-as-if-already-resolved a turning_point that the arc assigned to a different episode.
