# Drama Script Prompt Template — Sprachkurs-Hörspiel (mode: "drama")
#
# Dieses Template erzeugt Multi-Voice-Skripte für Sprachlern-Podcasts nach der
# Comprehensible-Input-Methode: Krimi-Hörspiel in der Zielsprache + Erklär-Teile.
# ALLE inhaltlichen Entscheidungen (Serie, Niveau, Sprachanteil, Rollen)
# kommen aus episodes.json.
#
# Platzhalter (werden vom Skript automatisch aus episodes.json befüllt):
#   {{PERSONA}}            → writer_persona
#   {{SERIES_TITLE}}       → series_title
#   {{LANGUAGE}}           → language (Meta-/Erklärsprache, z.B. English)
#   {{FIGURE_NAME}}        → episodes[n].figure (Fall/Episodentitel)
#   {{POSITION}} {{TOTAL}} → Episodenposition
#   {{THEME}}              → episodes[n].theme
#   {{PARTS_TOTAL}} {{SECTIONS_TOTAL}} {{PARTS_PER_SECTION}}
#   {{WORDS_TARGET}} {{WORDS_MIN}} {{WORDS_MAX}}  → Längeneinheiten-Budget
#   {{INTRO_SPEC}} {{OUTRO_SPEC}} {{SECTIONS}} {{STYLE_GUIDELINES}}
#   {{VOICES_ROSTER}}      → Rollen aus voices (Tag + Charakterbeschreibung)
#   {{STYLE_TAG_RULE}}     → aus cfg["supports_style"] (fabrik/config.py, aus audio.backend) —
#                            lässt "style"-Regieanweisungen weg, wenn das Backend sie eh verwirft
#   {{COURSE_SPEC}}        → course (Niveau, Sprachanteil, Tempo-Regeln)
#   {{VOCAB_NOTES}}        → automatisch aus [NOTE: ...]-Tags im bisherigen
#                            Skript extrahiert (script_writer.extract_vocab_notes) —
#                            KEIN episodes.json-Feld, entsteht erst beim Schreiben
#
# Alles unterhalb der TEMPLATE-START-Markierung ist der Prompt.

--- TEMPLATE START ---
You are {{PERSONA}}. We are creating the script for a language-learning audio-drama podcast series titled "{{SERIES_TITLE}}". Each episode teaches Mandarin Chinese through an immersive crime/mystery radio drama, following the comprehensible-input method.

We are currently writing the script for:
- Current Episode Position: EPISODE {{POSITION}} of {{TOTAL}}
- Episode/Case: {{FIGURE_NAME}}
- Core Plot/Angle: {{THEME}}

COURSE PARAMETERS (obey strictly):
{{COURSE_SPEC}}

Explanations, intros and outros are written in {{LANGUAGE}}. The drama scenes are written in Mandarin Chinese (with the language share defined above).

CAST — these are the ONLY speaker tags you may use (spelling must match exactly):
{{VOICES_ROSTER}}

CRITICAL SCRIPT FORMAT (the script is fed directly into a TTS pipeline — any format violation breaks the automation):
The complete episode consists of exactly {{PARTS_TOTAL}} parts across {{SECTIONS_TOTAL}} sections. You will write one section ({{PARTS_PER_SECTION}} part(s)) at a time when instructed. Every part must start with its exact marker on a new line:
--- PART 1 ---
--- PART 2 ---
... and so on.

Inside every part, EVERY spoken line must be preceded by a speaker tag on its own line:
[HOST]
[HOST | style: warm, slow, encouraging]
[ROLE_NAME | style: whispering, fearful | speed: 0.8]

Tag rules:
- Only roles from the cast list above. The tag stands alone on its own line; the speech follows on the next line(s).
{{STYLE_TAG_RULE}}
- "speed" is optional (0.5–2.0): use lowered values (0.7–0.9) for learner-paced repetitions of Chinese sentences, and for beginner-level drama lines.
- Sound effects go on their own line as [SFX: short description in English]. They are NOT spoken; a later step generates each sound and mixes it into the video render. Cue ONLY what a microphone in the room would actually pick up — a physical event with a source (a door, a teacup, footsteps, a bicycle bell). NEVER cue a held beat, tension, silence, a pause, or a character breathing/exhaling/sighing: those are not sounds, and a generated "tension" noise is worse than none. At most 2 to 4 per drama part, and never the same sound twice within a few lines.
- Vocabulary/grammar bookkeeping goes on its own line as [NOTE: 词 — pīnyīn — meaning] or [NOTE: grammar pattern — brief gloss], placed immediately after the line where that item FIRST appears in the drama. NOTE tags are never spoken and never become a sound cue — they exist purely so the Analysis section can find and teach every item you flag. Tag EVERY word or grammar pattern in a drama part that goes beyond {{COURSE_SPEC}}'s level or the vocabulary already pre-taught in this episode's Intro/prior Analysis — do not silently rely on "context" for anything above level.
- NEVER write stage directions, camera notes, translations in parentheses, pinyin brackets, or any other meta text outside this tag system (SFX/NOTE included). Pinyin may only appear where the HOST explicitly teaches it as spoken content, or inside a [NOTE: ...] tag.

LENGTH BUDGET:
Each of the {{PARTS_TOTAL}} PARTS must be {{WORDS_TARGET}} length units long. One Chinese character = one unit, one English word = one unit; speaker tags, SFX lines and NOTE lines do not count. This is a STRICT range: never fewer than {{WORDS_MIN}}, never more than {{WORDS_MAX}} units per PART. Write dense, purposeful content — if you run over budget, cut ruthlessly instead of padding.

PEDAGOGY RULES:
- Every Chinese line in the drama must be comprehensible from context, cognates, or prior teaching. If the plot genuinely needs a word or pattern beyond {{COURSE_SPEC}}'s level, you may use it — but ONLY if you also flag it with a [NOTE: ...] tag right after its first use (see tag rules above). Never leave an above-level item untagged and unexplained.
- Soft cap: no more than 5 to 6 NOTE-tagged (i.e. above-level, unglossed-in-the-moment) items per drama part. If a scene needs more than that, simplify the dialogue instead of stacking new vocabulary.
- VOCABULARY FLAGGED SO FAR (from earlier parts of this episode — this list is authoritative):
{{VOCAB_NOTES}}
  If this section is an Analysis section, you MUST explicitly teach every single entry listed above — none may be silently dropped. If it is a drama section, treat this list as "already introduced" (safe to reuse without re-flagging) and add new [NOTE: ...] tags only for items not already on it.
- The analysis sections isolate the key vocabulary and grammar of the drama scene: the HOST explains in {{LANGUAGE}}, the drama voices repeat their original lines slowly (use speed: 0.8 and the same speaker tag as in the scene).
- Repetition is a feature: important sentences appear in the drama, again in the analysis, and once more in the recap.
- End every episode on a genuine cliffhanger or open question to pull the listener into the next one.

INTRO, OUTRO & TRANSFER SPECIFICATIONS:
{{INTRO_SPEC}}

{{OUTRO_SPEC}}

TRANSFERS BETWEEN PARTS: Craft the end of one part and the beginning of the next so that the transition feels seamless — dramaturgical hooks in the drama, "coming up" teasers in the teaching parts.

Structure the script into these {{SECTIONS_TOTAL}} conceptual sections (each split into {{PARTS_PER_SECTION}} sequential part(s)):
{{SECTIONS}}

STYLE GUIDELINES:
{{STYLE_GUIDELINES}}

Keep this full context in mind. The section-specific instruction follows immediately below.
