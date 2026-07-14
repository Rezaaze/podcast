# Drama Script Prompt Template — Fallakten-Krimi (mode: "drama", template: "crime_drama")
#
# Multi-Voice-Krimi-Hörspiel OHNE Sprachlern-Zweck (Gegenstück zu
# language_course): jede Figur bekommt über episodes.json ein eigenes
# Wissens-Slice (case.character_knowledge) — Widersprüche, Lügen und
# Missverständnisse sollen daraus ORGANISCH entstehen, statt vom Modell nur
# behauptet zu werden. Der Kern: Claude schreibt zwar weiterhin alle Figuren
# in einem Aufruf, aber der Prompt macht explizit, was jede Figur NICHT
# wissen darf.
#
# Platzhalter (automatisch aus episodes.json befüllt):
#   {{PERSONA}} {{SERIES_TITLE}} {{LANGUAGE}} {{FIGURE_NAME}}
#   {{POSITION}} {{TOTAL}} {{THEME}}
#   {{PARTS_TOTAL}} {{SECTIONS_TOTAL}} {{PARTS_PER_SECTION}}
#   {{WORDS_TARGET}} {{WORDS_MIN}} {{WORDS_MAX}}
#   {{INTRO_SPEC}} {{OUTRO_SPEC}} {{SECTIONS}} {{STYLE_GUIDELINES}}
#   {{VOICES_ROSTER}}   → Rollen aus voices (Tag + Charakterbeschreibung)
#   {{STYLE_TAG_RULE}}  → aus cfg["supports_style"] (fabrik/config.py, aus audio.backend) —
#                         lässt "style"-Regieanweisungen weg, wenn das Backend sie eh verwirft
#   {{CASE_FILE}}       → aus episodes[n].case (fabrik/script_writer.py:build_case_file_block) —
#                         KEIN Platzhalter im Sinne eines direkten JSON-Feldes,
#                         sondern zu lesbarem Text zusammengesetzt
#
# Beats-Kontext (generation.use_beats: true, siehe docs/beat-layer-design.md):
#   Kein {{...}}-Platzhalter (genau wie der bisherige Vorschnitt-Kontext auch
#   keiner ist) — build_section_prompt() hängt nach der Platzhalter-
#   Substitution einen Block mit allen Szenen-Beats der Folge an (aktuelle
#   Szene markiert), statt der bisherigen Vorschnitt-Prosa. Nur wenn Beats für
#   diese Folge vorliegen; sonst unverändertes Vorschnitt-Fallback.
#
# Alles unterhalb der TEMPLATE-START-Markierung ist der Prompt.

--- TEMPLATE START ---
You are {{PERSONA}}. We are creating the script for a serialized crime-drama audio podcast titled "{{SERIES_TITLE}}" — a fully voiced radio drama where every character speaks for themselves.

We are currently writing the script for:
- Current Episode Position: EPISODE {{POSITION}} of {{TOTAL}}
- Episode/Case: {{FIGURE_NAME}}
- Core Plot/Angle: {{THEME}}

The entire script is written in {{LANGUAGE}}.

CAST — these are the ONLY speaker tags you may use (spelling must match exactly):
{{VOICES_ROSTER}}

CASE FILE — this is the load-bearing mechanic of this format. Read it carefully:
{{CASE_FILE}}

THE CENTRAL RULE: no character may ever say, imply, or act on anything outside their own knowledge slice above. A character who "hides" something must actively steer around it, deflect, or lie when asked — convincingly, not by refusing to speak. A character who "believes falsely" must speak with full sincerity from within that wrong belief; they are not lying, they are mistaken, and should not be written as if they suspect they're wrong. If two characters describe the same event differently in this episode, that is correct and intentional — do not let them "sync up" their stories, and do not have any character conveniently learn something they have no in-story way of knowing yet. The investigator role does NOT know the solution either, unless their own knowledge slice explicitly says so — they piece things together across episodes exactly like the listener does.

CRITICAL SCRIPT FORMAT (the script is fed directly into a TTS pipeline — any format violation breaks the automation):
The complete episode consists of exactly {{PARTS_TOTAL}} parts across {{SECTIONS_TOTAL}} sections. You will write one section ({{PARTS_PER_SECTION}} part(s)) at a time when instructed. Every part must start with its exact marker on a new line:
--- PART 1 ---
--- PART 2 ---
... and so on.

Inside every part, EVERY spoken line must be preceded by a speaker tag on its own line — using ONLY the exact role names from the CAST list above (there is no implicit "[HOST]" role unless it is explicitly listed there):
[DETECTIVE_NAME | style: measured, probing]
[SUSPECT_NAME | style: too calm, rehearsed | speed: 0.95]

Tag rules:
- Only roles from the cast list above. The tag stands alone on its own line; the speech follows on the next line(s).
{{STYLE_TAG_RULE}}
- "speed" is optional (0.5–2.0) for pacing (hesitation, urgency, a controlled/rehearsed delivery).
- Sound effects and atmosphere go on their own line as [SFX: short description in English]. Never spoken — they become a cue sheet for the audio engineer, NOT mixed into the final audio automatically. Use them deliberately, 2 to 5 per dramatic part, but never rely on them alone to convey where/when a scene is — say it out loud instead (see NARRATOR rule below). For an action that repeats (e.g. multiple gunshots), add a trailing repeat count: [SFX: gunshot x3, 0.4s apart] triggers the sound three times, 0.4 seconds apart. Omit the interval for a tight burst: [SFX: gunshot x3]. Do not use "xN" anywhere else in the description — it is only recognized as a repeat count at the very end of the line.
- NEVER write stage directions, camera notes, or any other meta text outside this tag system.

ORIENTATION (this is pure audio — the listener has no visual scene information and cannot see who is speaking beyond voice timbre): EVERY part must open with 1 to 2 short [NARRATOR] lines establishing where we are, roughly when, and who is present, before any character speaks — even mid-episode parts that continue the same scene as the previous part need at least a one-line reminder. The FIRST time a named character becomes central to a scene anywhere in the episode, fold one short clause naming their role or relationship to the case/story into that opening orientation (e.g. "the lead detective", "the victim's brother", "her defense attorney") — not their full backstory, just enough that a first-time listener isn't left guessing who they are to the case and to the people already introduced. Do this once per character per episode; don't repeat it on their later appearances in the same episode. NARRATOR never explains what a character is feeling or thinking, never reveals plot the listener shouldn't have yet, and never speaks again mid-scene once the dialogue has started (it may return briefly at a hard scene/location cut within the same part). Keep these lines terse and neutral — this is orientation, not narration-driven storytelling.

LENGTH BUDGET:
Each of the {{PARTS_TOTAL}} PARTS must be {{WORDS_TARGET}} words long (speaker tags and SFX lines do not count). STRICT range: never fewer than {{WORDS_MIN}}, never more than {{WORDS_MAX}} words per PART. Write dense, purposeful dialogue — if you run over budget, cut ruthlessly instead of padding.

INTRO, OUTRO & TRANSFER SPECIFICATIONS:
{{INTRO_SPEC}}

{{OUTRO_SPEC}}

TRANSFERS BETWEEN PARTS: craft the end of one part and the beginning of the next so the transition feels seamless — dramaturgical cliffhangers or structural hooks.

Structure the script into these {{SECTIONS_TOTAL}} conceptual sections (each split into {{PARTS_PER_SECTION}} sequential part(s)):
{{SECTIONS}}

STYLE GUIDELINES:
{{STYLE_GUIDELINES}}

Keep this full context in mind. The section-specific instruction follows immediately below.
