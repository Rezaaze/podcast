# Media-Analysis Podcast Script Prompt Template
#
# Wie templates/narration/PROMPT_TEMPLATE.md, zusätzlich mit {{CASE_FILE}}:
#   {{CASE_FILE}} → episode.case (solution = Kernthese/Struktur-Formel dieser
#                   Episode, objective_facts = stützende Belege aus dem
#                   Quellmaterial) — kein character_knowledge, da Solo-Format.
#
# Alle anderen Platzhalter identisch zu narration/PROMPT_TEMPLATE.md.
#
# Stolperkante: weil dieses Template einen case-Block hat, greift
# generation.use_beats auch hier (Beat-Layer gated auf episode.case, nicht
# auf mode) — der Beat-Prompt ist aber szenen-/dialogorientiert und für
# dieses Solo-Essay-Format nur bedingt sinnvoll. use_beats für
# media_analysis-Serien im Zweifel auslassen.

--- TEMPLATE START ---
You are {{PERSONA}}. We are creating the script for a multi-part anthology podcast series titled "{{SERIES_TITLE}}", where each episode deconstructs one work or phenomenon through a fixed four-part analytical lens: source comparison, psychological deep-dive, core thesis, and the broader ur-pattern.

We are currently writing the script for:
- Current Episode Position: EPISODE {{POSITION}} of {{TOTAL}}
- Subject of this Episode: {{FIGURE_NAME}}
- Core Analytical Angle: {{THEME}}

The entire script must be written in {{LANGUAGE}}.

ANALYTICAL FRAMEWORK FOR THIS EPISODE (your backbone — build the argument toward this across the four sections, don't just state it outright in section 1):
{{CASE_FILE}}

CRITICAL AUTOMATION SPECIFICATIONS:
The complete episode consists of exactly {{PARTS_TOTAL}} parts across {{SECTIONS_TOTAL}} sections. You will write one section ({{PARTS_PER_SECTION}} parts) at a time when instructed. Every part must start with its exact marker on a new line:
--- PART 1 ---
--- PART 2 ---
... and so on. Do not include any comments, stage directions, or descriptions around or inside these markers. Every part must end with a complete sentence.

MATHEMATICAL TARGET FOR RUNTIME:
Each of the {{PARTS_TOTAL}} PARTS must be {{WORDS_TARGET}} words long. This is a STRICT range: never write fewer than {{WORDS_MIN}} and never more than {{WORDS_MAX}} words per PART. Write dense, precise prose — if you run over budget, cut ruthlessly instead of padding.

INTRO, OUTRO & TRANSFER SPECIFICATIONS:
{{INTRO_SPEC}}

{{OUTRO_SPEC}}

TRANSFERS BETWEEN PARTS: Craft the end of one part and the beginning of the next so the argument builds continuously — each section should feel like the next logical step in the analysis, not a new topic.

Structure the script into these {{SECTIONS_TOTAL}} conceptual sections (each split into {{PARTS_PER_SECTION}} sequential parts):
{{SECTIONS}}

STYLE GUIDELINES:
{{STYLE_GUIDELINES}}

COPYRIGHT: Never quote source interviews/reviews verbatim beyond a short phrase (~10 words); paraphrase and attribute instead.

Keep this full context in mind. The section-specific instruction follows immediately below.
