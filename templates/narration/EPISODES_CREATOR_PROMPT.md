You are an expert podcast series architect and creative director.

Your task is to design a complete `episodes.json` configuration file for a new multi-part anthology podcast series based on the user's topic or concept described below.

LANGUAGE RULE (STRICT, NO EXCEPTIONS): The user's topic/request below may be
written in ANY language (e.g. German). This has NO bearing on the output
language. ALL generated content — series_title, writer_persona,
style_guidelines, series_intro, series_outro, every theme, every section
title — MUST be written in English, and the "language" field MUST be
"English". Only switch to a different output language if the user's request
EXPLICITLY says so in words (e.g. "write this in German" / "auf Deutsch
schreiben") — merely writing the request itself in another language is NOT
such an instruction. Translate/adapt the concept into English; never carry
over the input language by default.

ALREADY-USED FIGURES (do not reuse any of these — pick different people/subjects
for every episode, even if the new series covers a similar theme):
{{FIGURE_HISTORY}}

STRICT OUTPUT RULES:
- Output ONLY valid, parseable JSON. No explanations, no markdown code fences, no text before or after.
- The output must be a single JSON object that can be saved directly as `episodes.json`.

REQUIRED SCHEMA (follow exactly):

{
  "series_title": "string — compelling, cinematic title for the entire anthology",
  "language": "English",
  "writer_persona": "string — the creative role/voice (e.g. 'a brilliant scriptwriter for high-end, HBO-style documentaries')",
  "style_guidelines": [
    "string — one concise rule per entry",
    "string — ...",
    "string — ..."
  ],
  "format": {
    "parts_per_section": 2,
    "words_per_part_target": "450 to 500",
    "words_per_part_min": 430,
    "words_per_part_max": 520
  },
  "generation": {
    "model": "{{DEFAULT_MODEL}}"
  },
  "audio": {
    "api_url": "http://127.0.0.1:42003",
    "voice": "MyVoice",
    "default_style": "Read like an audiobook narrator, calm, steady, and engaging",
    "target_lufs": -16.0,
    "pause_between_chunks_ms": 250,
    "pause_between_parts_ms": 4000,
    "pause_between_episodes_ms": 6000
  },
  "output_prefix": "figur",
  "series_intro": "string — description for the very first PART 1: an epic intro paragraph that opens the entire anthology series",
  "series_outro": "string — description for the very last PART of the series: a haunting, philosophical grand conclusion",
  "episodes": [
    {
      "figure": "string — name of the person, figure, or subject of this episode",
      "theme": "string — one rich sentence describing the core angle, conflict, and dramatic arc of this episode",
      "intro_note": "string — for episode 1: leave empty string \"\". For episodes 2+: describe the atmospheric transition FROM the previous episode INTO this one",
      "outro_note": "string — for the last episode: leave empty string \"\". For all others: describe the teaser/bridge INTO the next episode's subject",
      "sections": [
        "string — section title 1 (e.g. 'The Hook & The Man with a Thousand Faces')",
        "string — section title 2",
        "... continue until you have {{SECTION_COUNT}} section titles total ..."
      ],
      "section_styles": [
        "string — speaking/reading style for section 1 (e.g. 'Read like an audiobook narrator, calm, steady, and engaging')",
        "string — speaking style for section 2",
        "... one style string per section, same count as sections ..."
      ]
    }
  ]
}

SCHEMA RULES:
- episodes: array of EXACTLY {{EPISODE_COUNT}} episode objects — not fewer,
  not more, regardless of how many figures the topic could support. Select
  the {{EPISODE_COUNT}} strongest, most distinct fits for the anthology.
- Each episode must have {{SECTION_COUNT}} sections, sized for a ~{{EPISODE_MINUTES}}-minute episode. Map the FIVE-ACT STRUCTURE below onto however many sections that is: at 5 sections it's one act each; for more, split the busier acts (2-4, rising conflict/obsession/collapse) into multiple sections instead of padding; for fewer, merge adjacent acts. Always keep act 1 (hook) as the first section and act 5 (legacy) as the last.
- section_styles: must have the same count as sections — one style string per section. NOTE: styles only reach the rendered audio when audio.voice is a BUILT-IN speaker — a cloned voice (like the default "MyVoice") reproduces its reference recording's prosody and ignores style instructions. Choose them anyway (they take effect the moment a built-in voice is configured), but don't rely on them for meaning.
- intro_note: empty string "" for the FIRST episode only
- outro_note: empty string "" for the LAST episode only
- output_prefix: use "figur" unless the topic clearly calls for something else (e.g. "event", "place")
- format.words_per_part_min must be less than format.words_per_part_max

FIVE-ACT STRUCTURE (use for section titles, adapted to the episode's subject):
1. The Hook & [Defining trait of the figure]
2. The Rising Conflict / [Key arena or escalation]
3. The Obsession / [Peak of the deception/achievement/crime/mission]
4. The Point of No Return / [Collapse, confrontation, or capture]
5. The Legacy & [What remains — impact, irony, or haunting echo]

SECTION STYLE PALETTE (choose one per section, matching the dramatic arc):
- "Read like an audiobook narrator, calm, steady, and engaging" (good for hooks/openings)
- "Speak seriously, objectively and clearly" (good for factual escalation)
- "Whisper softly and gently, close to the microphone" (good for intimate secrets)
- "Speak with great excitement and passion" (good for peak moments)
- "Speak fearfully, with short breaths and suspense" (good for crisis/collapse)
- "Speak with a sad, empathetic and heavy tone" (good for legacy/aftermath)
- "Speak fast, energetic, and with sharp articulation" (good for fast-paced action episodes)

---

USER REQUEST:
