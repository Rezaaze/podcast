# Drama Script Prompt Template — Shorts (mode: "drama", template: "shorts")
#
# Hook-first-Kurzform für vertikale Videos (TikTok/Reels): jede Episode ist
# 1–3 Minuten lang und wird von lofi_clips.py --full als EIN 9:16-Video
# gerendert (Burned-in-Captions satzweise, Location-Bild als Hintergrund,
# Porträt der sprechenden Rolle). Die Regeln hier unterscheiden sich bewusst
# von den langen Drama-Templates:
#   - Die ERSTE gesprochene Zeile jeder Episode ist der Hook (mitten im
#     Konflikt), nie Begrüßung/Szenenaufbau.
#   - NARRATOR: genau EINE ultrakurze Zeile pro Episode (PART 1, nach dem
#     Hook) statt der 1–2-Zeilen-Pflicht pro PART — Captions + Hintergrund
#     übernehmen im Video die Orientierung, jede Narrator-Sekunde kostet
#     Hook-Tempo.
#   - Kurze Sätze (≤ ~12 Wörter): sie werden satzweise als große Captions
#     eingeblendet; Schachtelsätze werden unlesbar.
#   - Letzter PART endet auf einer abgeschnittenen/unbeantworteten Zeile
#     (Sting) — kein Auflösen, kein Ausklang.
#   - episodes[n].case ist eine LISTE von Strängen (wie soap_opera, meist
#     nur einer) — build_case_file_block rendert "=== THREAD: ... ==="-Blöcke.
#
# Platzhalter (automatisch aus episodes.json befüllt):
#   {{PERSONA}} {{SERIES_TITLE}} {{LANGUAGE}} {{FIGURE_NAME}}
#   {{POSITION}} {{TOTAL}} {{THEME}}
#   {{PARTS_TOTAL}} {{SECTIONS_TOTAL}} {{PARTS_PER_SECTION}}
#   {{WORDS_TARGET}} {{WORDS_MIN}} {{WORDS_MAX}}
#   {{INTRO_SPEC}} {{OUTRO_SPEC}} {{SECTIONS}} {{STYLE_GUIDELINES}}
#   {{VOICES_ROSTER}}   → Rollen aus voices (Tag + Charakterbeschreibung)
#   {{STYLE_TAG_RULE}}  → aus cfg["supports_style"] (fabrik/core/config.py)
#   {{CASE_FILE}}       → aus episodes[n].case (Liste von THREAD-Blöcken)
#
# Alles unterhalb der TEMPLATE-START-Markierung ist der Prompt.

--- TEMPLATE START ---
You are {{PERSONA}}. We are creating the script for a serialized short-form audio drama titled "{{SERIES_TITLE}}" — every episode is a 1-3 minute vertical video for TikTok/Instagram Reels, fully voiced, where the first spoken line decides whether a stranger keeps watching or scrolls away.

We are currently writing the script for:
- Current Episode Position: EPISODE {{POSITION}} of {{TOTAL}}
- Episode Title: {{FIGURE_NAME}}
- Core Plot/Angle for this episode: {{THEME}}

The entire script is written in {{LANGUAGE}}.

CAST — these are the ONLY speaker tags you may use (spelling must match exactly):
{{VOICES_ROSTER}}

THREAD FILES — the season's continuing storyline(s). Read carefully:
{{CASE_FILE}}

THE CENTRAL RULE: no character may ever say, imply, or act on anything outside their own knowledge slice. A character who "hides" something must actively steer around it, deflect, or lie when asked — convincingly. A character who "believes falsely" speaks with full sincerity from within that wrong belief. The viewer assembles the truth faster than any character — that gap, compressed into minutes, is the entertainment.

THE DOUBLE DUTY (the whole craft of this format): this episode must work for a COLD VIEWER who has never seen the series — the local conflict must be clear within the first two lines, no prior knowledge required — while still advancing the season thread for followers. Serialized payoffs are a bonus layer, never a crutch. Never reference previous episodes explicitly ("as you said yesterday..." is fine if it works cold; "previously on" or recap lines are FORBIDDEN).

CRITICAL SCRIPT FORMAT (the script is fed directly into a TTS pipeline — any format violation breaks the automation):
The complete episode consists of exactly {{PARTS_TOTAL}} parts across {{SECTIONS_TOTAL}} sections. You will write one section ({{PARTS_PER_SECTION}} part(s)) at a time when instructed. Every part must start with its exact marker on a new line:
--- PART 1 ---
--- PART 2 ---
... and so on.

Inside every part, EVERY spoken line must be preceded by a speaker tag on its own line — using ONLY the exact role names from the CAST list above:
[CHARACTER_NAME | style: measured, guarded]
[CHARACTER_NAME | style: barely holding it together | speed: 1.05]

Tag rules:
- Only roles from the cast list above. The tag stands alone on its own line; the speech follows on the next line(s).
{{STYLE_TAG_RULE}}
- "speed" is optional (0.5–2.0) for pacing (hesitation, urgency, a controlled/rehearsed delivery).
- Sound effects go on their own line as [SFX: short description in English]. Never spoken — they never appear in the podcast MP3; a later step generates each sound and mixes it into the video render. Use AT MOST 2 per episode, only where a single sound genuinely lands a beat (a door, a phone buzzing). Cue ONLY what a microphone would actually pick up — never a held beat, tension, silence, or a character breathing/exhaling: those are not sounds. Never rely on SFX for orientation.
- NEVER write stage directions, camera notes, or any other meta text outside this tag system.

HOOK-FIRST OPENING (PART 1 only — this rule outranks everything else):
The episode opens MID-CONFLICT. The very first spoken line is the hook: an accusation, a revelation, a dangerous question, a line clearly said to the wrong person — delivered by a CHARACTER, not the narrator. No greeting, no scene-setting, no easing in. If the first line would not stop a stranger mid-scroll, it is the wrong line.
Directly AFTER that hook line, insert exactly ONE short [NARRATOR] line (maximum 12 words) anchoring who/where — e.g. "Her sister's kitchen. Two hours after the funeral." — then never use [NARRATOR] again for the rest of the episode. The NARRATOR never explains feelings, never reveals the thread's solution.
Parts after PART 1 open directly with dialogue — no narrator, no re-orientation.

CAPTION-DRIVEN SENTENCES: every sentence is burned into the video as a large on-screen caption, one sentence at a time. Keep sentences SHORT — aim for 12 words or fewer, one thought per sentence. Break long thoughts into separate sentences. Fragments are allowed and encouraged. A nested sub-clause sentence becomes an unreadable wall of caption text.

THE STING (final part only): the episode ends on a cut-off — an unanswered question, an interrupted confession, a name spoken just before the cut. The LAST line is the sting; nothing resolves after it, no reaction, no outro line. Follow the OUTRO spec below.

LENGTH BUDGET:
Each of the {{PARTS_TOTAL}} PARTS must be {{WORDS_TARGET}} words long (speaker tags and SFX lines do not count). STRICT range: never fewer than {{WORDS_MIN}}, never more than {{WORDS_MAX}} words per PART. This format is MINIMAL by design — every line must earn its second. If you run over budget, cut ruthlessly instead of padding; if a beat feels thin, sharpen the conflict instead of adding filler lines.

INTRO, OUTRO & TRANSFER SPECIFICATIONS:
{{INTRO_SPEC}}

{{OUTRO_SPEC}}

TRANSFERS BETWEEN PARTS: parts cut hard, like a vertical-video edit — end a part on a charged line, open the next mid-motion. No bridging narration.

Structure the script into these {{SECTIONS_TOTAL}} conceptual sections (each split into {{PARTS_PER_SECTION}} sequential part(s)):
{{SECTIONS}}

STYLE GUIDELINES:
{{STYLE_GUIDELINES}}

Keep this full context in mind. The section-specific instruction follows immediately below.
