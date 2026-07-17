You are the same showrunner, now writing the SCENE-LEVEL CONCEPT for exactly ONE episode of this crime-drama season. You do NOT see any other episode's sections — only the season's fixed canon and arc below. Stay strictly within what THIS episode owns.

CANON (series world, cast, the case's `solution`/`objective_facts` — ground truth, do not restate or alter it):
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
      "title": "string — short scene label, e.g. 'The Interview Room'",
      "what": "string — a NARRATED scene beat, {{SECTION_WORDS_MIN}} to {{SECTION_WORDS_MAX}} words: what actually happens, what's said or discovered, what changes by the end of the scene. Not a title restated as a sentence — an outsider reading only this line should be able to picture the scene.",
      "who": ["ROLE_NAME_FROM_VOICES", "..."],
      "thread": "string — must exactly match the single threads[].label from the canon",
      "words": null
    }
  ],
  "case": [
    {
      "label": "string — must exactly match the threads[].label from the canon",
      "character_knowledge": {
        "ROLE_NAME_FROM_VOICES": "string — this character's knowledge state, in 1-3 plain sentences: what they genuinely know and may freely reveal or act on, what they know but deliberately conceal/downplay/lie about (and briefly why), and anything specific they wrongly believe (and why that misunderstanding makes sense from their limited view). Write it as prose, not as separate categories — cover only what's dramatically relevant to THIS episode."
      }
    }
  ]
}

SCHEMA RULES:
- sections: roughly {{SECTION_COUNT}} scenes for this episode (±1), chosen by YOU based on scene/plot needs — a tense confrontation episode may need fewer, longer scenes than one juggling many leads.
- `what` DETAIL BAND (hard contract, this is what keeps pacing even): every section's `what` must be {{SECTION_WORDS_MIN}} to {{SECTION_WORDS_MAX}} words long, and all sections in this episode must sit in a SIMILAR register within that band — do not write three richly narrated scenes and then one bare fragment. A bare title, a one-clause stub, or a section that just restates its `title` in sentence form is INVALID, not merely terse.
- who: every name must be a role key from `canon.voices` (NARRATOR excluded — it is never a scene participant). A scene with a character who has no `voices` entry is invalid.
- thread: must be the canon's single thread label (there is only one case). If this episode's assigned turning_point(s) exist, at least one section must actually narrate that turning_point's `event`, and no section may narrate a turning_point assigned to a DIFFERENT episode.
- words: OPTIONAL override. Use `null` for a section that should just use the episode-wide `format` defaults, or an object `{"min": N, "max": M, "target": "N to M"}` for a scene that genuinely needs a different pace than the rest. Do not over-use this. BE HONEST about how short "shorter" is: a deliberately short override's min must be at least 80-120 words below `canon.format.words_per_part_min` — if you would not commit to a number meaningfully below the default, leave it `null` instead.
- case: exactly one entry, for the canon's single thread. `case.character_knowledge`: EVERY key in `canon.voices` EXCEPT "NARRATOR" must appear here — every speaking character has a knowledge slice this episode, including the investigator (they too should have blind spots and wrong assumptions early on).
- Do NOT include `section_styles` or `location`/`section_locations` — crime_drama has no location-background feature.

DRAMATURGY PRINCIPLE (this is the whole point of this format): contradictions between what different characters say are a FEATURE. A witness and a suspect should be able to describe the same event differently — one lying, one simply wrong, one genuinely not knowing the piece the listener needs. Never let a character's dialogue leak knowledge outside their own `character_knowledge` slice, and never let this episode narrate, resolve, or telegraph-as-if-already-resolved a turning_point that the arc assigned to a different episode.
