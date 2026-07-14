# templates — die Prompt-"Produktdefinition"

Jedes Template lebt in `templates/<name>/` mit zwei Dateien, iteriert wird
hier ohne Python anzufassen:

- `EPISODES_CREATOR_PROMPT.md` — erzeugt via create_series.py die komplette
  episodes.json in einem Schuss. Muss `{{FIGURE_HISTORY}}` enthalten
  (build_prompt errort sonst laut) und die Literale
  `parts_per_section`/`words_per_part_target` irgendwo im Schema-Block
  (estimate_section_count parst sie für die --minutes-Skalierung).
  **Single-Source-Platzhalter** (build_prompt substituiert aus
  `fabrik/core/config.py`, nie wörtlich in Templates pflegen — die
  Chelsie-Lektion): `{{DEFAULT_MODEL}}` (alle fünf Templates, aus
  `DEFAULTS["model"]`), `{{VOICE_ROSTER}}` (Bullet-Liste,
  crime_drama/soap_opera) und `{{VOICE_ROSTER_COMPACT}}` (Fließtext,
  language_course) aus `BUILTIN_SPEAKER_ROSTER`. Unersetzte
  `{{...}}`-Platzhalter werden beim Erstellen laut angewarnt.
- `PROMPT_TEMPLATE.md` — das Per-Section-Skript-Prompt,
  `{{PLACEHOLDER}}`-substituiert von
  `fabrik/writing/script_writer.py::build_section_prompt`.

## Zwei Modes, sechs Templates

**`mode: "narration"`** — ein Erzähler, Stile pro Section (`section_styles`):

- `narration` — klassisches Anthologie-/True-Crime-Format; Section-Zahl
  skaliert dynamisch mit `--minutes` (Fünf-Akt-Struktur im Creator-Prompt,
  auf beliebig viele Sections gemappt).
- `media_analysis` — psychologische/kulturelle Dekonstruktion: ein Werk/
  Phänomen pro Episode durch eine FIXE Vier-Teil-Linse (Source Comparison →
  Psychological Deep-Dive → Core Thesis → Ur-Pattern), die NICHT mit
  --minutes skaliert — --minutes weitet nur `words_per_part_target`
  (direkt im Creator-Prompt gerechnet; estimate_section_count läuft
  harmlos ungenutzt mit, sein Regex braucht die Literale nur irgendwo).
  Zweckentfremdet den `case`-Block (`solution` = These der Episode,
  `objective_facts` = Belege; `character_knowledge` bewusst weggelassen —
  Solo-Narrator). Weil validate_case_block/build_case_file_block
  mode-agnostisch sind, brauchte das Template null Codeänderung — und
  bekommt Episode-Review (`--fix`) und Beat-Layer "gratis" (beide gaten
  auf `episode.get("case")`), anders als narration/language_course.
  Achtung beim Beat-Layer: der Beat-Prompt ist szenenorientiert und passt
  nur bedingt zum Solo-Essay — `use_beats` hier im Zweifel auslassen.

**`mode: "drama"`** — multi-voice, `[SPEAKER | style: ... | speed: ...]`-Tags
pro Zeile, `[SFX: ...]`-Cues werden nur geloggt, nie vertont:

- `language_course` — Mandarin-Lern-Hörspiel; `[NOTE: wort — pinyin —
  bedeutung]`-Zeilen werden vor TTS gestrippt und der nächsten Section
  via extract_vocab_notes wieder vorgelegt.
- `crime_drama` — ein durchgehender Fall pro Staffel; `episodes[n].case`
  ist EIN Objekt (`solution`, `objective_facts`,
  `character_knowledge: {ROLE: {knows, hides, believes_falsely}}`), über
  alle Episoden konsistent, nur das Wissen wächst. Der Knowledge-Split
  lässt Widersprüche/Lügen organisch entstehen statt behauptet zu werden.
- `soap_opera` — gleiche Mechanik, aber `case` ist eine LISTE unabhängiger
  Threads (je `label` + gleiches Sub-Schema): eine Soap-Episode treibt
  mehrere Storylines parallel. Section-Zahl wird ZUSÄTZLICH pro Episode
  gewählt (wie viele Threads brauchen Sendezeit). `locations`-Support
  (Anzahl via `--locations`).
- `shorts` — Hook-first-Kurzform für 9:16-Videos (TikTok/Reels, Rendern:
  `lofi_clips.py --full` in Lolfi): 1–3-Min-Episoden, 3 Sections × 1 Part
  (Hook → Turn → Sting), `words_per_part_target` "70 to 120". `case` als
  LISTE (meist 1 Micro-Thread, soap-Schema), `locations`-Support (Bilder =
  Video-Hintergründe). **Bewusste Abweichungen von den langen
  Drama-Templates:** die erste gesprochene Zeile ist der Hook (nie
  Begrüßung/Szenenaufbau), NARRATOR nur EINE ≤12-Wort-Zeile pro Episode
  (Captions/Hintergrund orientieren im Video), kurze Sätze (≤~12 Wörter,
  werden satzweise als Captions eingebrannt), Episodenende = harter
  Sting-Schnitt. Deshalb KEIN "previously on"-Recap-Gate — stattdessen
  eigene shorts-Zweige in `build_intro_spec`/`build_outro_spec`
  (script_writer.py), die intro_note/outro_note als Autoren-Kontext bzw.
  Sting-Vorgabe durchreichen statt als Sprech-Anweisung (das generische
  "MUST start with <intro>" hätte Hook-first direkt widersprochen).

## Regeln, die in den Prompts stehen (und warum)

- **ACCENT CASTING RULE:** nur Ryan/Aiden sind akzentfrei; Akzente müssen
  diegetisch sein (Biografie erklärt sie) oder das Setting macht sie
  unauffällig. Hintergrund: fabrik/core/CLAUDE.md (KNOWN_BUILTIN_SPEAKERS).
- **NARRATOR-Pflicht** (crime_drama/soap_opera): fixe Rolle in `voices`.
  PROMPT_TEMPLATE.md verlangt 1–2 gesprochene `[NARRATOR]`-
  Orientierungszeilen (wer/wo/wann) am Anfang jedes PART — hart gelernt:
  SFX werden nie gemischt, ohne NARRATOR hat ein Szenenwechsel NULL
  hörbares Signal. **Beide Templates verlangen jetzt einen Built-in-
  Speaker (Ryan/Aiden bevorzugt)**, kein Voice-Clone mehr — soap_opera
  nutzte bis 2026-07-14 bewusst den festen Clone `morgan`, wurde aber auf
  Built-in umgestellt (Speed-Gewinn beim Cloud-Rendern, ~10x schneller pro
  Chunk als das Voice-Clone-Modell, siehe cloud/README.md). Style/
  Instruct wird für die Rolle NARRATOR unabhängig von Built-in/Clone IMMER
  ignoriert (`build_drama_jobs` in podcast_maker.py erzwingt
  `style=None`) — Style/Emotion klang auf der Erzähler-Rolle hörbar "off"
  (User-Feedback), siehe Memory `narrator-style-override`.
- **section_words-Lektion:** ein Override, der nur 10–20% unter dem
  Episoden-Default liegt, lässt den Writer zuverlässig unterschießen —
  ein wirklich kurzer Beat heißt ~100–200 Wörter, kein kosmetischer
  Rabatt. Deterministisch abgesichert durch `check_section_words_gaps()`
  (SECTION_WORDS_MIN_GAP=80, siehe fabrik/cli/CLAUDE.md).
- Episoden ≥2 in crime_drama/soap_opera öffnen mit gescriptetem
  "previously on"-Recap (build_intro_spec, template-gated;
  language_course behält seine HOST-Konvention).
