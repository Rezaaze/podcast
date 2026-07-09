# Neutrales Podcast Script Prompt Template
#
# Dieses Template ist bewusst generisch — ALLE inhaltlichen Entscheidungen
# (Serie, Ton, Sprache, Format, Wortbudget) kommen aus episodes.json.
#
# Platzhalter (werden vom Skript automatisch aus episodes.json befüllt):
#   {{PERSONA}}            → writer_persona
#   {{SERIES_TITLE}}       → series_title
#   {{LANGUAGE}}           → language
#   {{FIGURE_NAME}}        → episodes[n].figure
#   {{POSITION}}           → Position dieser Figur (z.B. 2)
#   {{TOTAL}}              → Gesamtanzahl Figuren (z.B. 4)
#   {{THEME}}              → episodes[n].theme
#   {{PARTS_TOTAL}}        → Sections × format.parts_per_section
#   {{SECTIONS_TOTAL}}     → Anzahl Sections der Episode
#   {{PARTS_PER_SECTION}}  → format.parts_per_section
#   {{WORDS_TARGET}}       → format.words_per_part_target
#   {{WORDS_MIN}}          → format.words_per_part_min
#   {{WORDS_MAX}}          → format.words_per_part_max
#   {{INTRO_SPEC}}         → automatisch generiert (je nach Position)
#   {{OUTRO_SPEC}}         → automatisch generiert (je nach Position)
#   {{SECTIONS}}           → Sektions-Titel mit Part-Markern
#   {{STYLE_GUIDELINES}}   → style_guidelines als Aufzählung
#
# Alles unterhalb der TEMPLATE-START-Markierung ist der Prompt.

--- TEMPLATE START ---
You are {{PERSONA}}. We are creating the script for a multi-part anthology podcast series titled "{{SERIES_TITLE}}".

We are currently writing the script for:
- Current Figure Position: PERSON {{POSITION}} of {{TOTAL}}
- Name of this Figure: {{FIGURE_NAME}}
- Core Theme/Angle: {{THEME}}

The entire script must be written in {{LANGUAGE}}.

CRITICAL AUTOMATION SPECIFICATIONS:
The complete episode consists of exactly {{PARTS_TOTAL}} parts across {{SECTIONS_TOTAL}} sections. You will write one section ({{PARTS_PER_SECTION}} parts) at a time when instructed. Every part must start with its exact marker on a new line:
--- PART 1 ---
--- PART 2 ---
... and so on. Do not include any comments, stage directions, or descriptions around or inside these markers. Every part must end with a complete sentence.

MATHEMATICAL TARGET FOR RUNTIME:
Each of the {{PARTS_TOTAL}} PARTS must be between {{WORDS_TARGET}} words. This is a STRICT range: never write fewer than {{WORDS_MIN}} and never more than {{WORDS_MAX}} words per PART. Every episode in the series must have the same length, so treat this word budget as a hard constraint. Write dense prose — if you run over budget, cut ruthlessly instead of padding.

INTRO, OUTRO & TRANSFER SPECIFICATIONS:
{{INTRO_SPEC}}

{{OUTRO_SPEC}}

TRANSFERS BETWEEN PARTS: Craft the end of one part and the beginning of the next so that the transition feels seamless. Use dramaturgical cliffhangers or structural hooks.

Structure the script into these {{SECTIONS_TOTAL}} conceptual sections (each split into {{PARTS_PER_SECTION}} sequential parts):
{{SECTIONS}}

STYLE GUIDELINES:
{{STYLE_GUIDELINES}}

Keep this full context in mind. The section-specific instruction follows immediately below.
