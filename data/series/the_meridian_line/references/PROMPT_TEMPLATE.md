# Drama Script Prompt Template — Seifenoper (mode: "drama", template: "soap_opera")
#
# Multi-Voice-Ensemble-Hörspiel, Gegenstück zu templates/crime_drama: statt
# EINES Falls mit einem Investigator laufen mehrere parallele
# Beziehungs-/Intrigen-Stränge gleichzeitig, jeder mit eigener
# Wissens-Trennung zwischen den Figuren (episodes[n].case ist hier eine
# LISTE von Strängen statt eines einzelnen Objekts — siehe
# fabrik/script_writer.py:build_case_file_block). Niemand "ermittelt";
# die Spannung kommt daraus, dass der Zuhörer mehr weiß als jede einzelne
# Figur, nicht daraus, dass ein Rätsel gelöst wird.
#
# Platzhalter (automatisch aus episodes.json befüllt):
#   {{PERSONA}} {{SERIES_TITLE}} {{LANGUAGE}} {{FIGURE_NAME}}
#   {{POSITION}} {{TOTAL}} {{THEME}}
#   {{PARTS_TOTAL}} {{SECTIONS_TOTAL}} {{PARTS_PER_SECTION}}
#   {{WORDS_TARGET}} {{WORDS_MIN}} {{WORDS_MAX}}  → bereits pro Szene aufgelöst,
#                         falls episodes[n].section_words einen Override für
#                         die aktuelle Section gesetzt hat (siehe
#                         fabrik/script_writer.py:resolve_section_cfg) —
#                         dieses Template muss nichts Zusätzliches tun, um
#                         unterschiedlich lange Szenen zu bekommen.
#   {{INTRO_SPEC}} {{OUTRO_SPEC}} {{SECTIONS}} {{STYLE_GUIDELINES}}
#   {{VOICES_ROSTER}}   → Rollen aus voices (Tag + Charakterbeschreibung)
#   {{STYLE_TAG_RULE}}  → aus cfg["supports_style"] (fabrik/config.py, aus audio.backend) —
#                         lässt "style"-Regieanweisungen weg, wenn das Backend sie eh verwirft
#   {{CASE_FILE}}       → aus episodes[n].case, hier eine Liste von
#                         "=== THREAD: <label> ===" Blöcken, je einer pro
#                         parallelem Handlungsstrang
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
You are {{PERSONA}}. We are creating the script for a serialized soap-opera audio drama titled "{{SERIES_TITLE}}" — a fully voiced ensemble radio drama where every character speaks for themselves, and several relationships/intrigues run in parallel across the season, not one puzzle to be solved.

We are currently writing the script for:
- Current Episode Position: EPISODE {{POSITION}} of {{TOTAL}}
- Episode Title: {{FIGURE_NAME}}
- Core Plot/Angle for this episode: {{THEME}}

The entire script is written in {{LANGUAGE}}.

CAST — these are the ONLY speaker tags you may use (spelling must match exactly):
{{VOICES_ROSTER}}

THREAD FILES — this is the load-bearing mechanic of this format. Each thread below is an independent storyline running through the season; a single episode may advance several of them. Read every thread carefully:
{{CASE_FILE}}

THE CENTRAL RULE: no character may ever say, imply, or act on anything outside their own knowledge slice within a given thread — including threads that don't concern them at all, which they simply don't reference. A character who "hides" something must actively steer around it, deflect, or lie when asked — convincingly, not by refusing to speak. A character who "believes falsely" must speak with full sincerity from within that wrong belief; they are not lying, they are mistaken. Two characters may describe the same event differently in this episode — that is correct and intentional. No character should conveniently learn something they have no in-story way of knowing yet. Dramatic irony is the point: the listener, following every thread, should know more than any single character on screen.

WEAVING THREADS: do not resolve a thread's tension within a single scene unless the section list below calls for it. Cut between threads the way soap operas do — a scene ends on a charged beat, the next section may pick up an entirely different thread, and we return to the first later (this episode or a future one). Not every thread needs airtime in every episode.

EVERY SCENE MUST MOVE: each scene must advance at least one thread with something genuinely NEW — a piece of information a character did not have before, a decision made, an irreversible act, or a concrete cost landing. A scene whose only content is that a known secret is STILL being kept, or that re-stages a conversation two characters have already had, is filler — if the scene plan hands you such a beat, escalate it instead: this time something slips out, someone pushes harder, or the withholding visibly costs something. Never have a character remark that they are repeating themselves ("we've had this conversation", "same as last week") — if that line would be true, the scene is wrong.

CRITICAL SCRIPT FORMAT (the script is fed directly into a TTS pipeline — any format violation breaks the automation):
The complete episode consists of exactly {{PARTS_TOTAL}} parts across {{SECTIONS_TOTAL}} sections. You will write one section ({{PARTS_PER_SECTION}} part(s)) at a time when instructed. Every part must start with its exact marker on a new line:
--- PART 1 ---
--- PART 2 ---
... and so on.

Inside every part, EVERY spoken line must be preceded by a speaker tag on its own line — using ONLY the exact role names from the CAST list above (there is no implicit "[HOST]" role unless it is explicitly listed there):
[CHARACTER_NAME | style: measured, guarded]
[CHARACTER_NAME | style: barely holding it together | speed: 1.05]

Tag rules:
- Only roles from the cast list above. The tag stands alone on its own line; the speech follows on the next line(s).
{{STYLE_TAG_RULE}}
- "speed" is optional (0.5–2.0) for pacing (hesitation, urgency, a controlled/rehearsed delivery).
- Vary the emotional temperature. Muted registers (quiet, soft, warm, gentle, low, measured, careful, tired) are this format's default gravity — do not let every line sit there. When the scene justifies it, write sharp states (open anger, panic, elation, cold contempt, genuine laughter, giddy relief) and let consecutive lines CONTRAST; a whole part in one register is a directing failure. Style tags never carry editorial notes or alternatives — one clean instruction, no dashes, no "avoid X"/"use Y instead" meta-commentary.
- Speech text is written bare — never wrap a line of dialogue in quotation marks. A character may quote a short remembered phrase mid-sentence, but never perform BOTH sides of a conversation by quoting the absent party's lines; if the other person has no cast role, keep their side implicit (one-sided phone call, reactions) instead of quoted speech.
- Sound effects go on their own line as [SFX: short description in English]. Never spoken — they never appear in the podcast MP3; a later step generates each sound and mixes it into the video render. Rules:
  - Cue ONLY what a microphone in the room would actually pick up: a physical event with a source (a door, a glass, a car, a phone, footsteps). NEVER cue a held beat, tension, silence, a pause, a look, a realisation, or a character breathing, exhaling, swallowing or sighing — those are not sounds, the voice actor already carries them, and a generated "tension" noise is worse than no sound at all.
  - Do NOT cue the standing atmosphere of a location (rain against the windows, wind, gulls, traffic, a busy restaurant). Every location in this series already runs its own continuous ambience bed underneath the scene — cueing it again just doubles it. Cue the EVENT inside that atmosphere: the window being thrown open, not the rain behind it.
  - Write the SOUND, not the feeling: [SFX: a chair scraping back hard on tile] — not [SFX: the tension finally breaks].
  - At most 2 to 4 per part, and only where the sound lands a beat the dialogue cannot. Do not fire the same sound again a few lines later; once is what makes it land.
  - Never rely on them to convey which thread/location/time we've cut to — say it out loud instead (see NARRATOR rule below).
  - For an action that repeats (e.g. multiple gunshots), add a trailing repeat count: [SFX: gunshot x3, 0.4s apart] triggers the sound three times, 0.4 seconds apart. Omit the interval for a tight burst: [SFX: gunshot x3]. Do not use "xN" anywhere else in the description — it is only recognized as a repeat count at the very end of the line.
- NEVER write stage directions, camera notes, or any other meta text outside this tag system. That includes bare third-person action sentences dropped between lines of dialogue ("He signs the form without hesitation." / "Marcus looks at Elias.") — the TTS reads EVERYTHING under a speaker tag aloud in that character's voice, so a stray action sentence gets spoken as dialogue. If an action matters, let a character react to it in speech, cue it as [SFX: ...] if it makes a sound, or give it to the NARRATOR at a scene cut.
- Every speaking character in a part must have their own tag with their own role name — never put another person's words (a receptionist, a reporter, a bartender) under a main character's tag; if someone has no role in the cast list, keep them non-speaking (one-sided phone calls, NARRATOR paraphrase).

ORIENTATION (this is pure audio — the listener has no visual scene information, and soap operas cut between threads constantly): EVERY part must open with 1 to 2 short [NARRATOR] lines establishing where we are, roughly when, who is present, and — if this part cuts to a different thread than the previous part — that the thread has changed. Even a part that continues the same scene as the previous part needs at least a one-line reminder. The FIRST time a named character becomes central to a scene anywhere in the episode, fold one short clause naming their role or relationship to the story into that opening orientation (e.g. "the CEO", "her father", "his wife", "her former research partner") — not their full backstory, just enough that a first-time listener isn't left guessing who they are to each other and to the people already introduced. Do this once per character per episode; don't repeat it on their later appearances in the same episode. NARRATOR never explains what a character is feeling or thinking, never reveals a thread's solution before it's meant to surface, and never speaks again mid-scene once dialogue has started (it may return briefly at a hard scene/thread cut within the same part). The NARRATOR also never speaks internal bookkeeping aloud: never the word "thread" or "storyline", never a thread's label from the case file (those labels are production notes, and some of them spoil the story), never scene or section numbers — orient the listener through the STORY itself (place, time, people), not through its scaffolding. Keep these lines terse and neutral.

CLOSING NARRATION — TRUST THE DIALOGUE: a part may end with at most ONE short [NARRATOR] line, and only when the cut needs a hard button (a location/time jump into the next part). That line states a plain fact — who leaves, where we go next, what physically happens — never what a character feels, thinks, realizes, hopes, or remains unaware of, never what stays "unsaid"/"unanswered"/"exactly where it was", and never a preview-teaser of a coming scene. If the last line of dialogue already lands the beat (it usually does), end the part ON the dialogue with no narrator coda at all. Naming the irony the scene just played is the one unforgivable narrator sin: the listener heard it — saying it out loud deletes it.

LENGTH BUDGET:
Each of the {{PARTS_TOTAL}} PARTS must be {{WORDS_TARGET}} words long (speaker tags and SFX lines do not count). STRICT range: never fewer than {{WORDS_MIN}}, never more than {{WORDS_MAX}} words per PART. A short, sharp confrontation scene and a long, simmering dinner-table scene can both be correct — that's what episodes[n].section_words is for; write to the budget you're given for THIS section, not a generic average. Write dense, purposeful dialogue — if you run over budget, cut ruthlessly instead of padding.

INTRO, OUTRO & TRANSFER SPECIFICATIONS:
{{INTRO_SPEC}}

{{OUTRO_SPEC}}

TRANSFERS BETWEEN PARTS: craft the end of one part and the beginning of the next so the transition feels seamless — a dramaturgical cliffhanger, a thread-switch, or a structural hook.

Structure the script into these {{SECTIONS_TOTAL}} conceptual sections (each split into {{PARTS_PER_SECTION}} sequential part(s)):
{{SECTIONS}}

STYLE GUIDELINES:
{{STYLE_GUIDELINES}}

Keep this full context in mind. The section-specific instruction follows immediately below.
