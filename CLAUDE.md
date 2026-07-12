# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Podcast-Fabrik is an automated pipeline for producing podcast series: Claude
writes the scripts, a local Qwen3-TTS API voices them, and the result is a
mastered MP3 per episode plus a merged anthology. There is no build step and
no test suite — this is a set of Python CLI scripts orchestrated by a Flask
WebUI, plus vast.ai automation for renting cloud GPU when local TTS is too
slow.

A second, separate project — `~/Downloads/Lolfi` (video/music generation,
not in this repo) — shares the same WebUI cockpit (`webui/`). `webui/config.py`
hardcodes `LOLFI_DIR` pointing at it; don't be surprised by "lolfi_*" code
paths in `webui/`.

## Layout

Split by runtime environment and coupling, not by topic:

- `fabrik/core/` — stdlib-only (paths, config, textproc, history, claude_cli);
  safe to import everywhere, runs without any venv.
- `fabrik/writing/` — script generation; needs only the `claude` CLI.
- `fabrik/audio/` — voicing (`pipeline`, `tts_backends`); needs `.venv`
  (pydub, numpy, pyloudnorm, requests) + ffmpeg. core/writing must NEVER
  import from here — that would break the no-venv script-generation path.
- `fabrik/cli/` — the entry points, invoked as `python3 -m fabrik.cli.<name>`
  from the project root (the WebUI does exactly this via `"module"` entries
  in `webui/config.py::COMMANDS`).
- `webui/`, `cloud/` — independent subprojects (own venv / plain shell);
  they talk to the pipeline only via subprocess or not at all.
- `templates/` — the prompt "product definition"; iterated on without
  touching Python.
- `data/` — everything the pipeline produces or consumes as bulk assets:
  `data/series/<slug>/`, `data/voices/` (clone reference audio),
  `data/figure_history.json`, `data/archive/`. Mostly gitignored
  (`data/series/*/output/`, audio files, archive); the small series
  definitions/scripts stay tracked.

## Commands

```bash
# 1. Create a new series (writes data/series/<slug>/episodes.json via Claude CLI)
python3 -m fabrik.cli.create_series "Topic/concept" [--episodes N] [--minutes M] [--locations L] [--template narration|media_analysis|language_course|crime_drama|soap_opera] [--no-review] [--fix]
#     --minutes steers per-episode length: create_series.py::estimate_section_count derives the
#     section count each template asks Claude for from minutes (WORDS_PER_MINUTE=150) and the
#     template's own parts_per_section/words_per_part_target — no template hardcodes a section
#     count anymore. --locations steers how many reusable scene locations soap_opera invents
#     (see "Locations" below); ignored by templates that don't support locations yet.
#     Generation runs through generate_with_retry (up to MAX_ATTEMPTS=3): invalid JSON,
#     validate_data errors AND a wrong episode count are fed back verbatim into the next
#     attempt (same pattern as the script writer's call_claude_with_retry) — a count
#     mismatch is a retryable ERROR now, not a warning. Best-effort fallback (mirrors
#     validate_parts()'s fallback_safe/badness on the script-writer side): if every attempt
#     is schema-clean (validate_data finds nothing) but only the episode count is off, the
#     attempt with the closest count is used instead of aborting — only a real validate_data
#     error (would crash generate_episode.py's own validation later) disqualifies an attempt
#     from the fallback; a wrong count alone never does. The hard sys.exit(1) only fires if
#     no attempt was ever fallback-safe across all MAX_ATTEMPTS tries. After structural validation,
#     check_section_words_gaps() runs UNCONDITIONALLY (even with --no-review, it's a
#     local, free, deterministic check, no Claude call): for soap_opera episodes, it
#     flags any non-null section_words.min that's less than SECTION_WORDS_MIN_GAP=80
#     words below the episode-wide format.words_per_part_min — a "sharp confrontation"
#     override that's only a 10-20% token trim reliably makes the script writer
#     undershoot it during generation (confirmed in production: script_writer.py's
#     call_claude_with_retry kept failing the same handful of sections even after
#     escalating feedback, until this was traced to the override itself being too
#     close to the default). soap_opera's own creator prompt was tightened the same
#     way (EPISODES_CREATOR_PROMPT.md: a genuinely short beat means ~100-200 words,
#     not a cosmetic discount off the default) so NEW series shouldn't need the
#     warning at all — this check is the safety net for when the planning model does
#     it anyway. A second, LLM-based pass (review_series, skippable via --no-review)
#     additionally checks spoiler leaks before the finale, contradictions across
#     objective_facts/character_knowledge, the accent-casting rule, episode overlap,
#     and (its own check 5) the same section_words/description mismatch in prose form
#     — kept as a secondary layer since it can catch phrasing-level mismatches the
#     pure number comparison can't, but proved unreliable for the numeric case alone
#     (missed all instances in a real 10-episode series review) hence the dedicated
#     deterministic check taking priority. Findings are warnings only and never block the
#     series from being written — UNLESS --fix is passed: repair_series() then sends the
#     complete episodes.json back to Claude together with the flagged problems and an
#     instruction to change ONLY what's needed to fix them, re-validates the result
#     structurally (its own MAX_ATTEMPTS retry loop with the same error-feedback pattern
#     as generate_with_retry), and re-runs review_series on the result to confirm the fix
#     actually landed — the document-level counterpart to repair_part()/--fix on the
#     episode-review side. Unlike repair_part(), episodes.json has no addressable
#     "--- PART N ---" unit to patch, so the whole (comparatively small) object is
#     regenerated each time instead of a surgical sub-edit. A repair that never becomes
#     structurally valid across the retry loop leaves the original data untouched — the
#     pre-repair episodes.json gets written, and the original review findings are printed
#     as-is. Creator templates carry an explicit {{FIGURE_HISTORY}} placeholder
#     (build_prompt errors loudly if a template lacks it AND the legacy
#     ALREADY-USED-FIGURES regex fails, instead of silently skipping history
#     injection; estimate_section_count warns loudly on unparseable format values too).
#     Per-call timeout scales with episode count (compute_timeout: 120s/episode, 600s
#     floor, 1800s cap) instead of a fixed value — a 10-episode soap_opera genuinely
#     needs more than the 600s a 3-episode anthology needs. A timeout or transient
#     Claude-CLI error is retryable (generate_with_retry treats it like invalid JSON,
#     no feedback appended since there's no content to correct), NOT a sys.exit — only
#     "claude not found"/"not logged in" abort immediately. A heartbeat line prints
#     every 20s while a call is in flight (fabrik/core/claude_cli.py::run_claude_process)
#     since '--output-format text' gives no output at all until the call finishes,
#     which otherwise looks identical to a hang in the console/WebUI log.

# 1b. Or import an already-finished text instead of having Claude invent one
#     (narration mode only — see "Story import" below)
python3 -m fabrik.cli.import_story <folder-or-file> "Series Title" [--no-summary]

# 2. Generate scripts (needs the `claude` CLI installed and logged in, no venv needed)
python3 -m fabrik.cli.generate_episode check          # validate episodes.json only
python3 -m fabrik.cli.generate_episode 1 [--fix] [--no-script-review]   # one episode
python3 -m fabrik.cli.generate_episode all [--jobs N] [--force] [--fix] [--no-script-review]   # all episodes, then auto-runs batch.py
#     --fix: after writing, review the finished episode against its own case/character_knowledge
#     (case-based templates only) and auto-repair any flagged part; --no-script-review skips the
#     review entirely. See "Episode review" below.

# 3. Voice the scripts (needs .venv: pydub, numpy, pyloudnorm, requests, ffmpeg in PATH,
#    and a running Qwen3-TTS server matching audio.api_url in episodes.json)
.venv/bin/python -m fabrik.cli.podcast_maker ep1.txt   # one episode (filename is enough)
.venv/bin/python -m fabrik.cli.batch                   # all episodes + anthology merge

# 3b. Portrait prompts for the video overlays (drama series; Claude CLI, no venv)
python3 -m fabrik.cli.character_prompts [--force]      # writes data/series/<slug>/characters/PROMPTS.txt
#     If OPENAI_API_KEY is set, also generates characters/<ROLE>.png directly
#     via gpt-image-1-mini (fabrik/writing/image_backends.py, stdlib urllib,
#     no venv needed) — pass --no-images to force prompts-only even with a key set.

# 3c. Location background prompts (series with "locations" in episodes.json; Claude CLI, no venv)
python3 -m fabrik.cli.location_prompts [--force]       # writes data/series/<slug>/locations/PROMPTS.txt
#     Mirrors character_prompts.py exactly, one image prompt per location key instead of per
#     role (1536x1024, landscape — used as a video background, not a bust portrait); same
#     OPENAI_API_KEY/--no-images behavior. No-ops with a message if episodes.json has no
#     "locations" (most series don't — only templates that ask for it, currently soap_opera).

# All CLIs accept --series <slug>; without it, data/series/LATEST is used (or the
# only series present).

# WebUI (controls both this project and Lolfi)
./start_webui.sh                            # sets up webui/.venv on first run, opens browser
# manual: cd webui && .venv/bin/python app.py   (port 5151, WEBUI_PORT env overrides)

# Cloud GPU (vast.ai) for faster TTS — see cloud/README.md for the full workflow
cd cloud && ./rent.sh && ./status.sh        # rent + wait for setup
./stop.sh / ./resume.sh                     # pause/resume, disk (incl. model) persists
./destroy.sh                                # permanently deletes the instance + disk
```

There is no test suite and no linter configured in this repo.

**WebUI gotcha:** Flask runs with `debug=False` in `webui/app.py`, but
`TEMPLATES_AUTO_RELOAD` is enabled — edits to `webui/templates/*.html` and
`webui/static/*` are picked up on the next browser reload without a server
restart. Python module edits in `webui/*.py` still need a server restart
(no reloader).

**Claude CLI gotcha:** `call_claude()` (in `fabrik/writing/script_writer.py` and
`create_series.py`) passes `stdin=subprocess.DEVNULL` — without it, `claude
-p` hangs/errors ("no stdin data received") when spawned from a process
whose own stdin isn't a TTY, which is exactly how the WebUI launches every
job (`webui/runner.py::JobRegistry` uses `subprocess.Popen` with no
`stdin=`). Keep this on any new `subprocess.run(["claude", ...])` call site.

**Shared Claude-CLI plumbing (`fabrik/core/claude_cli.py`):** stdlib-only,
used by both `create_series.py` and `script_writer.py`. `run_claude_process(argv,
timeout, label)` replaces a plain `subprocess.run()` for any call that might
run long (series/episode-review generation can take minutes): it runs
`proc.communicate()` in a background thread and prints a `⏳ <label> …
noch dabei (Ns vergangen, Timeout bei Ts)` line every 20s from the main
thread — `--output-format text` is non-streaming, so without this a long
call looks identical to a hang in the console/WebUI log. Raises
`subprocess.TimeoutExpired` like `subprocess.run()` would. `parse_json_response(raw)`
strips markdown fences / grabs the largest `{...}` block, returns `None`
(never raises) on unparseable input. A timeout or non-zero exit from a
`claude` call that feeds a retry loop (`generate_with_retry` in
create_series.py, `call_claude_with_retry` in script_writer.py) must be
*retryable*, not a `sys.exit()` — a single flaky/slow call shouldn't kill an
otherwise-recoverable batch job; only "claude not found" and "not logged in
(401)" are truly unrecoverable and exit immediately.

## Architecture

### Single source of truth: `episodes.json`

Every series is a folder `data/series/<slug>/` containing `episodes.json`, which
drives everything: content, format, voice mode, audio backend config. It is
loaded/validated exhaustively by `fabrik/core/config.py::validate_data` — any
unknown key becomes a warning (typo detection for AI-generated JSON), any
structurally invalid value becomes a hard error before generation starts.
`fabrik/core/config.py::build_config` flattens `episodes.json` + `DEFAULTS` into
the `cfg` dict threaded through the rest of the pipeline.

`data/series/LATEST` holds the slug of the default series; all CLIs fall back to
it when `--series` is omitted. Series are never archived/moved automatically
— they coexist under `data/series/<slug>/` indefinitely (`data/archive/` only holds
pre-multi-series-layout leftovers).

### Two modes, five templates

- `mode: "narration"` — single narrator, styles vary per section
  (`section_styles`). Two templates use this mode:
  - `narration` — the classic anthology/true-crime format; section count
    scales dynamically with `--minutes` via `estimate_section_count()`
    (Five-Act structure baked into the creator prompt, mapped onto however
    many sections that yields).
  - `media_analysis` — psychological/cultural deconstruction format: one
    work or phenomenon per episode, run through a FIXED four-part lens
    (Source Comparison → Psychological Deep-Dive → Core Thesis →
    Ur-Pattern) that does NOT scale with `--minutes` — `--minutes` instead
    only widens `format.words_per_part_target`, computed directly in the
    creator prompt's own instructions rather than via
    `estimate_section_count()`'s section-count scaling (which still runs
    harmlessly unused for this template, since its regex only needs
    `parts_per_section`/`words_per_part_target` literals to exist somewhere
    in the schema block, not to be the *final* values). Repurposes the
    `case` block (`solution` = the episode's analytical thesis,
    `objective_facts` = supporting evidence; `character_knowledge`
    deliberately omitted — solo-narrator format, no character cast) that
    `crime_drama`/`soap_opera` normally use for knowledge-splits —
    `validate_case_block()`/`build_case_file_block()`
    (`fabrik/core/config.py`/`fabrik/writing/script_writer.py`) are mode-
    agnostic, so adding this template needed zero code changes, just the
    two prompt files under `templates/media_analysis/`. Side effect of
    reusing `case`: episode review (`--fix`) and the beat layer
    (`generation.use_beats`) both gate purely on `episode.get("case")`, not
    on `mode` (see "Episode review"/"Beat layer" below) — so
    `media_analysis` episodes get both "for free" too, unlike plain
    `narration`/`language_course` episodes, which carry no `case` and skip
    both.
- `mode: "drama"` — multi-voice, `[SPEAKER | style: ... | speed: ...]` tags
  per line, `[SFX: ...]` cues logged (not voiced) to a per-episode cue sheet.
  Three templates use this mode:
  - `language_course` — Mandarin-learning audio drama, `[NOTE: word — pinyin
    — meaning]` vocab-tracking lines are stripped before TTS and re-surfaced
    to the next section's prompt via `extract_vocab_notes`.
  - `crime_drama` — one continuous case per season; `episodes[n].case` is a
    **single object** (`solution`, `objective_facts`,
    `character_knowledge: {ROLE: {knows, hides, believes_falsely}}`) that
    stays consistent across all episodes, only the per-character knowledge
    grows. This knowledge split is what makes contradictions/lies emerge
    organically instead of being asserted by the model.
  - `soap_opera` — same knowledge-split mechanic, but `episodes[n].case` is a
    **list** of independent threads (each with its own `label` + the same
    sub-schema), since a soap episode advances several parallel storylines
    at once rather than solving one case. Section count is chosen per episode
    (not fixed even within one series) based on how many threads need airtime
    that episode — every template's section count now scales with
    `--minutes` (see `create_series.py` above), but soap_opera additionally
    varies it episode-to-episode on top of that.

  Voice casting: the local Qwen3-TTS app has exactly nine built-in speakers
  (`fabrik/core/config.py::KNOWN_BUILTIN_SPEAKERS`; unknown names only warn at
  `check`, since clones are legal). Only Ryan/Aiden are accent-free native
  English speakers — all others (incl. ALL female voices) are Chinese-native
  and their accent is audible in every rendered line, so the creator prompts
  carry an ACCENT CASTING RULE: accents must be diegetic (character biography
  explains them) or the setting must make them unremarkable; NARRATOR should
  get Ryan or Aiden.

  `crime_drama` and `soap_opera` both require a fixed `NARRATOR` role in
  `voices` (built-in speaker only, never a voice clone — `fabrik/core/config.py`
  excludes it from the `character_knowledge`-completeness warning). Pure
  audio with no visual scene info gets disorienting fast with only character
  dialogue, so `PROMPT_TEMPLATE.md` for both requires 1-2 spoken `[NARRATOR]`
  orientation lines (who/where/when) at the start of every PART. Learned the
  hard way: `[SFX: ...]` cues are logged to a cue sheet only, never mixed
  into the rendered audio (see Audio pipeline below) — without NARRATOR,
  scene changes have zero audible signal at all.

Each template lives in `templates/<name>/` with two files:
`EPISODES_CREATOR_PROMPT.md` (fed to Claude by `create_series.py` to
generate the whole `episodes.json` in one shot) and `PROMPT_TEMPLATE.md`
(the per-section script-writing prompt, `{{PLACEHOLDER}}`-substituted by
`fabrik/writing/script_writer.py::build_section_prompt`).

### Script generation is section-by-section, resumable

`fabrik/writing/script_writer.py::generate_episode` iterates `episode["sections"]`
(scenes), and for each one calls Claude once via `call_claude_with_retry`
(up to `MAX_RETRIES=2`, feeding back per-part validation errors on retry —
`ESCALATION_FROM_ATTEMPT=2` sharpens the feedback wording on the last
attempt: "this is attempt N and STILL wrong, add a concrete beat, don't just
write longer sentences"). Each finished section is written to
`scripts/<prefix>N.txt` immediately — `--- PART k ---` markers make partial
files resumable: a re-run skips sections whose parts already exist.
Continuity context passed to the model is only the *previous* section's
parts, not the whole episode/series history — cross-episode continuity is
carried entirely through hand/AI-authored `intro_note`/`outro_note`/`theme`/
`case`, not automatic memory (see "Episode review" below for the gap this
opens up).

Length budget is enforced per PART (`format.words_per_part_min/max`,
sprache-neutral via `fabrik/core/textproc.py::count_length_units` — 1 CJK char =
1 Latin word = 1 unit) and can be overridden per-section via the optional
`episodes[n].section_words[i]` (`{min, max, target}` or `null`), resolved by
`fabrik/writing/script_writer.py::resolve_section_cfg` before both prompt-building
and validation — this is how a short confrontation scene and a long dialogue
scene coexist in one episode. The tolerance band around min/max is
`word_count_tolerance()` (10% of the part minimum, floor 15) rather than a
fixed 15 units — a fixed buffer sat inside the model's normal counting noise
at typical minima, so retries were triggered by noise, not real problems.
**Overshooting max is never a retry** (`validate_parts` accepts it with a
console warning): an over-long part just makes the episode a few seconds
longer at render time, while regenerating it costs a full prompt (template +
case file + beats) — only TOO SHORT and format errors trigger retries.

**Best-effort fallback instead of a hard abort:** some scenes are
content-thin enough that the model can't reliably clear the word minimum
even across `MAX_RETRIES` attempts with escalating feedback (observed in
production: 5 attempts oscillating 176-232 units against a 220 minimum,
never converging — the reason MAX_RETRIES was cut from 3 to 2). `validate_parts()`
returns `(ok, console, detail, fallback_safe, badness)` — `fallback_safe` is
`False` only for missing parts or a `ScriptFormatError` (would crash the TTS
parser, never usable), `badness` is the summed word-budget shortfall. If every
retry fails on word count but at least one was `fallback_safe`,
`call_claude_with_retry` uses the least-bad one instead of returning `None` and
aborting the whole episode — a format violation is *never* accepted this way,
only a missed word target. **Early fallback:** a fallback-safe attempt whose
badness is within `2 * word_count_tolerance()` is accepted *immediately*
(no further retry) — the fallback would have taken it anyway after all
attempts, so the extra full-prompt regeneration bought nothing.

**Light model for non-creative calls (`generation.light_model`, default
`claude-haiku-4-5`):** episode title/description (`generate_episode_meta`),
both LLM reviews (`review_episode_script`, `review_episode_beats`) and
`import_story`'s metadata summarization run on the light model — pure
extraction/checking tasks. Creative writing (sections, beats, `repair_part`)
stays on `generation.model`.

**Episode review (`--fix` on `generate_episode.py`):** because each section
only sees the *previous* section, not the whole episode, a character can
drift outside their `case`/`character_knowledge` slice or a thread's
`solution` can leak early even when the plan itself is clean.
`script_writer.py::review_episode_script` runs a second Claude call on the
*finished* script text (gated on `episode.get("case")`, not on `mode` —
plain `narration`/`language_course` episodes carry no `case` and have no
knowledge-split to violate, so they skip this; `media_analysis` episodes do
carry a `case` and get reviewed the same as `crime_drama`/`soap_opera`),
asking for structured
`{"issues": [{"part": N, "problem": "..."}]}`. Timeout scales with script
length (`compute_review_timeout`, 300-1200s) since reviewing ~2000 units of
prose can itself take minutes. Returns `None` (not `[]`) on any failure
(timeout/API error/unparseable) — `generate_episode()` must NOT write a
`<prefix>N_REVIEW.txt` in that case, or a future run would see the file
"exists" and never retry; `None` vs. `[]` is the difference between "we
don't know" and "genuinely clean". With `--fix`, each flagged part with a
known number is rewritten in isolation by `repair_part()` (same
`call_claude_with_retry` validation as first-draft writing, prompt shows
only the current text + the flagged problem, asks for a surgical fix) and
spliced back into the script file via `replace_part_in_script()` (regex
replace using a replacement *function*, not a string — avoids backslash/
group-reference misinterpretation of arbitrary Claude-generated text), then
the whole episode is reviewed again to confirm the fix actually landed.
Review results are idempotent/cached in `<prefix>N_REVIEW.txt` (skipped on
a re-run unless `--force` or `--fix`); `--no-script-review` skips the step
entirely. Both flags thread through `generate_episode.py all`'s per-episode
subprocess parallelism.

**Beat layer (`generation.use_beats: true`, opt-in, default off):** closes
the same continuity gap as the episode review above, but *before* the
expensive per-section prose is written instead of after. Gated on
`cfg["use_beats"] and episode.get("case")` (both — case-less templates like
plain `narration`/`language_course` never reach this path, while
`media_analysis` does since its episodes carry a `case`; `import_story`
episodes skip it structurally since they never call `generate_episode()`'s
generation path at all). See `docs/beat-layer-design.md` for the full
design rationale. Also settable from the WebUI (checkbox next to "Alles
generieren + vertonen + Anthologie", same `POST /api/pf/series/settings`
persistence as the `merge_anthology` checkbox — `webui/app.py`'s
`GET /api/pf/series` exposes the current value per series, `app.js`'s
`updateUseBeatsCheckbox()` keeps it in sync on series switch).

For each episode with the flag on, `script_writer.py::generate_beats` makes
ONE Claude call that sees every section one-liner of the episode + the
`case`/`character_knowledge` block (`build_case_file_block()`, reused
as-is) + the *previous* episode's beats text for continuity, and asks for
3-6 plain-language beats per scene (what happens and why — no dialogue, no
style) in `--- SCENE N ---`-marked blocks, parsed by `parse_beats()` and
written to `scripts/<prefix>N_BEATS.txt`. Resume is a plain existence check
(skipped unless `--force`) rather than the incremental `read_existing_parts`
scheme used for PART files, since one call produces the whole file at once
— there's nothing to resume mid-way through. A failed/unparseable beat call
is *not* fatal: `generate_beats()` returns `None`, writes no file, and
`build_section_prompt()` falls back to its original previous-section-prose
context for that run, exactly as if `use_beats` were off.

When beats exist, `build_section_prompt()` replaces the old "immediately
preceding section" prose block with all of the episode's scene beats as an
overview, the current scene's beats marked `<-- WRITE THIS SCENE NOW` —
this is what lets the dialogue writer plan across the whole episode instead
of seeing only the last section, closing the continuity gap the episode
review above can only catch after the fact. Without beats for this episode
(flag off, generation failed, or this specific scene missing from the
parsed dict) the function falls through unchanged to the original
prose-context block — fully backward compatible.

A second, LLM-based review (`review_episode_beats()`, structurally
identical to `review_episode_script()`: same `run_claude_process` +
`parse_json_response`, same `None` = failed run vs. `[]` = genuinely clean
discipline, warn-only, no auto-repair) runs on the *beats* text right after
generation, writing `<prefix>N_BEATS_REVIEW.txt` — catching a knowledge
violation or premature spoiler on a handful of beat lines is far cheaper
than catching the same problem later in 2000 words of finished prose.
`--force` removes both `<prefix>N_BEATS.txt` and
`<prefix>N_BEATS_REVIEW.txt` before regenerating, the same way it wipes the
main script file.

**Known limitation:** `generate_episode.py all --jobs N` submits all
per-episode subprocesses up front (`ThreadPoolExecutor`), so beats
continuity (reading the *previous* episode's `<prefix>N_BEATS.txt`) is only
reliable when episodes are generated in order — a single-episode
invocation per run, or a completed prior pass. Under parallel `--jobs > 1`
a missing previous-episode beats file is treated as "no continuity context
this run" (an info log, not an error), never a crash or a block.

### Audio pipeline (`fabrik/audio/pipeline.py`, `fabrik/audio/tts_backends.py`)

`podcast_maker.py`/`batch.py` (need `.venv`) chunk each script part via
`fabrik/core/textproc.py`, send chunks to a TTS backend, checkpoint each rendered
chunk as WAV (`output/.checkpoints/`, resumable like script generation), then
LUFS-master and merge to a final MP3 with ID3 tags. Three backends
(`audio.backend` in episodes.json): `rest` (Qwen3-TTS-MLX on Apple Silicon,
default, required for `mode: drama`), `gradio` (Windows/CUDA via
`gradio_client`, narration-mode only, also used to reach a rented vast.ai
GPU), `kokoro` (mlx-audio, no style/instruct support). The anthology merge
uses ffmpeg stream-copy — episodes are never re-encoded or loaded fully into
RAM. Each TTS call is fully stateless (voice/style/speed passed explicitly
per chunk) — generation order has no effect on audio quality, so there's no
benefit to batching by speaker instead of the current strict script order.

`batch.py` merges all episodes into one `ANTHOLOGY_COMPLETE.mp3` by default
once ≥2 episodes are done — set `audio.merge_anthology: false` in
episodes.json to skip this for series whose format wants standalone episodes
instead of one continuous anthology (e.g. `soap_opera`, where each episode is
published separately). When skipped, `batch.py` still writes per-episode
`UPLOAD_INDEX.md` entries, just no anthology merge/subtitle-merge/chapters/
anthology-meta. Also settable from the WebUI (checkbox next to "Alles
generieren + vertonen + Anthologie", persists straight into episodes.json via
`POST /api/pf/series/settings`).

**`batch.py` self-heals across a full run instead of stopping after one
failed episode:** a single flaky chunk (transient TTS timeout/hiccup mid-run)
used to mark only that one episode as failed for the whole invocation — the
rest kept going, but the failed episode(s) just sat there until the user
noticed and manually reran `batch.py` (checkpoints/Part-WAVs from the failed
episode's completed chunks are preserved, so a rerun resumes mid-episode, not
from scratch). Now `main()` runs up to `BATCH_RETRY_ROUNDS=2` additional
passes (20s apart, `BATCH_RETRY_DELAY`) over just the still-failing episodes
before finally giving up and printing the list — turns "silently stuck,
needs a human to notice and re-click" into "recovers on its own from
transient failures". `podcast_maker.py`'s own `backend.check_api()` got the
same treatment: a single failed health check right after an auto-start
(`webui/tts_control.py::start_tts` only waits for the PORT to open, not for
the model to finish loading — the health endpoint can briefly still error)
used to abort the whole episode immediately; now it retries 3 more times,
10s apart, before giving up.

**Post-merge crash safety:** `merge_parts_to_episode` deletes the Part-WAVs
immediately after writing the episode MP3 and persists the returned
`part_offsets` to `<Episode>_PART_OFFSETS.json` (`pipeline.py::
part_offsets_path`/`load_part_offsets`) *before* returning. Reason: the four
post-merge steps (SFX cue sheet, speaker timeline, subtitles, location
timeline) all read small per-part JSON side-files with a plain `json.load()`
and used to run unprotected right after the MP3/Part-WAV point of no
return — if any one of them raised (e.g. a truncated side-file from an
earlier kill mid-write), `podcast_maker.py` would crash with the MP3 already
"done" and the Part-WAVs already gone, and the *only* resume check
(`if os.path.exists(episode_path): return`) would then skip that episode
forever without ever retrying the missing metadata. Fixed by wrapping each
post-merge step individually in try/except (`podcast_maker.py::
run_postprocessing`, prints a warning and continues instead of crashing) and
by re-running `run_postprocessing` even when the episode MP3 already exists,
using the persisted `part_offsets` instead of the (now-deleted) Part-WAVs —
cheap and idempotent, no re-vertonung needed. Episodes rendered before this
fix have no `_PART_OFFSETS.json`; those fall back to ID3-tagging only on
resume (no way to reconstruct offsets without the original WAVs).

`fabrik/core/config.py::BACKEND_SUPPORTS_STYLE` (`rest`: yes, `kokoro`/`gradio`:
no) drives `cfg["supports_style"]`, which `fabrik/writing/script_writer.py` uses to
skip asking Claude for style/instruct directions entirely when the
configured backend would just discard them (`build_style_tag_rule()` for
drama's `{{STYLE_TAG_RULE}}` placeholder, a guard on the narration-mode
`VOCAL DELIVERY` paragraph). Deliberately defined in `config.py`, not
`tts_backends.py` — the latter imports `requests`/`pydub`, which would break
`generate_episode.py`/`create_series.py` running without `.venv`.

`[SFX: ...]` cues are **never mixed into the rendered audio** — only logged
to `output/<Episode>_SFX_CUES.txt` with timestamps for manual DAW mixing.

The part merge also honors optional per-series audio assets
(`data/series/<slug>/intro.mp3|outro.mp3|transition.mp3` — jingle at episode
start/end, sting replacing the inter-part silence; offsets returned by
`merge_parts_to_episode` include them, so all cue sheets stay correct), and
every render writes **subtitles**: `<Episode>_FULL_EPISODE.srt` (chunk texts
split per sentence, speaker names prefixed on role change in drama) plus a
`_SUBS.json` that `batch.py` merges into `ANTHOLOGY_COMPLETE.srt`. The JSON
cues additionally carry a clean (unprefixed) `"role"` field per cue —
deliberately separate from the `.srt` text, which keeps the name-on-role-
change prefix for YouTube — that Lolfi's `lofi_system.py` reads to show the
spoken line as a per-sentence dialogue bubble next to the speaking
character's portrait (only for cues whose timing actually falls inside that
role's active portrait window, see below). `batch.py`
also writes `ANTHOLOGY_COMPLETE_CHAPTERS.json` + a ready-to-paste YouTube
chapter list into `UPLOAD_INDEX.md`. Lolfi consumes CHAPTERS/SPEAKERS for
episode-title cards and portrait overlays with name labels (text rendered via
Pillow to PNG + ffmpeg `overlay` — the Homebrew ffmpeg has no drawtext).
In crime_drama/soap_opera, episodes ≥2 open with a scripted `[NARRATOR]`
"previously on" recap (`build_intro_spec`, template-gated so
language_course keeps its own HOST recap convention).

In drama mode the same assembly pass also records **who speaks when** (and
with which per-line `style` — spans merge only within the same role+style,
since Lolfi maps the style to an emotion via keyword lists in `EMOTIONS` and
shows a colored panel behind the portrait + emoji badge for the span):
`output/<Episode>_SPEAKERS.json` (+ human-readable `.txt`), per-part data
cached in `output/.cues/*_speakers.json` like the SFX cues. `batch.py`
combines them (episode durations + merge pause) into
`ANTHOLOGY_COMPLETE_SPEAKERS.json`. Consumed by Lolfi's `lofi_system.py`,
which overlays character portraits from `data/series/<slug>/characters/<ROLE>.png`
whenever that role speaks (`character_prompts.py` writes the per-role
portrait prompts, and — if `OPENAI_API_KEY` is set — generates the PNGs
itself via `gpt-image-1-mini`/`fabrik/writing/image_backends.py`; without a
key it's still prompts-only, paste into any image model of your choice,
NARRATOR excluded either way). Alongside the neutral portrait,
`character_prompts.py` also generates one variant per emotion —
`<ROLE>_<emotion>.png` for `anger`/`fear`/`sadness`/`joy`/`surprise`/`love`/
`vulnerability` (mirrors Lolfi's `EMOTIONS` keys exactly, kept in sync by
hand since there's no shared import between the two codebases). Lolfi
classifies each speaking span's `style` text into one of these emotions
already (previously only for a colored panel/emoji badge) and now also
swaps the displayed portrait to the matching `<ROLE>_<emotion>.png` for
that span, falling back to the neutral image when a span's emotion has no
generated variant.

A vorhandene `characters/PROMPTS.txt` reused instead of blocking a rerun:
`character_prompts.py` used to treat "`PROMPTS.txt` exists" as "nothing left
to do" and return immediately — but that file is written even in text-only
mode (no `OPENAI_API_KEY`), so setting the key afterward and rerunning just
printed "already exists" without ever reaching image generation. Now an
existing file's blocks are parsed back (`parse_prompts_file()`, same block
format as `parse_blocks()` but tolerant of the `(→ characters/...)` file
annotation) and reused as-is (no redundant Claude call) unless it's missing
blocks the current scripts now need (e.g. a newly-used emotion) — either
way, the function always falls through to the image-generation loop
afterward, which has its own per-file skip-if-exists check and therefore
only fills in whatever PNGs are actually missing.

`<Episode>_SPEAKERS.json` also carries a `scenes` array
(`podcast_maker.py::build_scene_presence`, `batch.py`'s anthology variant
merges it the same way as `spans`): for each PART, the set of roles that
speak *anywhere* in that PART — i.e. who's present in the scene, not just
who's talking at this exact instant. This is what lets Lolfi show not only
the current speaker but also who they're speaking *to* (small "listener"
portraits for the other present roles, swapping live as the conversation
turns) — derived purely from PART boundaries already known from
`merge_parts_to_episode`'s `part_offsets`, no extra Claude prompt needed.
Voice-cloned roles (`resolve_voice()` returns `"prompt"`/`"clone"` kind)
ignore `style` entirely and only ever reproduce the prosody of their one
reference recording — fine for a narrator, sounds flat for multi-character
drama dialogue; prefer built-in speakers for `voices.*` roles when possible.

**Locations (reusable scene backgrounds for the video):** optional top-level
`locations: {ORT_KEY: {name, description}, ...}` in `episodes.json` — defined
once per series (currently only the `soap_opera` template asks Claude for
this, count controlled by `create_series.py --locations`), referenced from
`episodes[n].section_locations[i]` (one key per section, or `null` to keep
whatever location was last active — parallel array to `section_styles`/
`section_words`, same length-validation pattern in `config.py`). Like
`voices`/`character_prompts.py`, `location_prompts.py` turns each location's
`description` into an image-generation prompt (`data/series/<slug>/
locations/PROMPTS.txt`, auto-generates `<ORT_KEY>.png` via gpt-image-1-mini
if `OPENAI_API_KEY` is set — landscape 1536x1024, no venv needed).

No manual timestamping needed: `podcast_maker.py::build_location_timeline`
resolves each PART's section index (`part_idx // parts_per_section`) against
`section_locations`, reusing the exact `part_offsets` machinery that already
drives `build_scene_presence` for speaker timelines, and writes
`output/<Episode>_LOCATIONS.json` (`{"locations": [{start_ms, end_ms,
location}, ...]}` — a *separate* file from `_SPEAKERS.json` since locations
are mode-independent, unlike the drama-only speaker timeline). `batch.py`
merges it into `ANTHOLOGY_COMPLETE_LOCATIONS.json` the same way it merges
speaker timelines, when `merge_anthology: true`. Lolfi's `lofi_system.py`
consumes this to swap the video background per scene instead of looping a
single clip for the whole episode (falls back to the standard loop clip for
any gap or unmatched location key, e.g. before the first location appears or
during the end-padding tail) — plus a short fading name-label overlay at
each change, same Pillow→PNG→ffmpeg-`overlay` mechanism as the existing
title cards. Entirely additive: a series without `locations` renders exactly
as before.

**Voice consistency, hard-blocked:** two independent guards make it
structurally hard for a role to end up with the wrong/a drifting voice.
(1) `config.py::validate_data` hard-errors if two different `voices` roles
resolve to the same underlying `voice` name — same voice for two characters
means the listener can't tell them apart, never intentional. (2) Checkpoints/
Part-WAVs/finished episode MP3s are cached purely by filename
(`podcast_maker.py`), not by the voice config that produced them — editing
`voices.<ROLE>.voice` after some episodes are already rendered would
otherwise silently make the rest of the series use the new voice while old
episodes keep the old one, with nothing noticing. `podcast_maker.py::
check_voice_consistency` closes this: on every run it compares the current
`voices`/`audio.voice` config against `output/.voices_manifest.json` and
**hard-exits before touching any file** if a role's resolved voice/speed/seed
changed — the user must explicitly revert `episodes.json` or intentionally
re-render the affected episodes and delete the stale manifest, never a silent
mixed-voice series.

**Baseline is written only after voices are confirmed resolvable, not on
first invocation:** `check_voice_consistency()` only *compares* against
`.voices_manifest.json` (no-ops if it doesn't exist yet) — the actual write
is a separate function, `commit_voice_manifest()`, called only after the TTS
backend is reachable AND every role's voice name resolved successfully,
right before the render loop starts. Reason: `check_voice_consistency()` used
to run at the very top of `main()` and write the manifest immediately on
first invocation, before the backend/voice-name checks below it ever ran —
a run that failed seconds later (unresolvable voice name, unreachable
server, zero bytes of audio produced) still left behind a manifest recording
that broken config as "already rendered". Fixing a typo'd voice name in
episodes.json afterward would then hard-fail against that phantom baseline
even though nothing had ever actually been rendered with it.

**Voice consistency / seed:** `resolve_voice()` now returns a 3-tuple
`(kind, voice_id, seed)` everywhere (`RestBackend`, `GradioBackend`,
`KokoroBackend`). `voices.<ROLE>.seed` (drama) / `audio.seed` (narration,
or fallback default for roles without their own seed) in `episodes.json`
only has an effect for `RestBackend` + cloned/prompt voices (`kind ==
"prompt"`): the local Qwen3-TTS-MLX-WebUI-Enhanced server only exposes a
`seed` parameter on its streaming endpoint
(`/api/v1/base/generate-with-prompt/stream`), not on the plain
`/api/v1/custom-voice/generate` (built-in speakers) or
`/api/v1/base/generate-with-prompt` (non-streaming clone) endpoints Fabrik
otherwise uses — so `RestBackend.generate_chunk` transparently switches to
the streaming variant whenever a seed is resolved for a `"prompt"` voice,
resetting `mx.random.seed()` before generation to reduce timbre/prosody
drift of the same cloned voice across many chunks. Built-in speakers have
no server-side seed control at all (config.py warns if you set one
anyway); `GradioBackend`/`KokoroBackend` accept/pass through `seed` for
tuple-shape uniformity but don't act on it (see their `resolve_voice`
docstrings). `check_voice_consistency`'s `.voices_manifest.json` drift
guard also tracks `seed` now, alongside `voice`/`speed` — changing it
mid-series after episodes are already rendered hard-fails the same way a
changed voice name would.

### Story import (`import_story.py`) — bypasses generation, not just prompting

Counterpart to `create_series.py` for already-finished text (old novels,
existing stories) where Claude must not invent content. `narration` mode
only. Two source shapes: a folder (one file = one episode, verbatim) or a
single long file (auto-split into episodes via chapter-heading regexes,
falling back to a paragraph-aware word-count split,
`textproc.chunk_prose_by_words`). Per episode, only a single Claude call
happens (`script_writer.py::summarize_source_episode`, title+theme metadata
only, explicitly forbidden from inventing plot) — the actual PART-chunking
is done deterministically by `chunk_prose_by_words` with **no minimum**
enforced (unlike the generative path's `WORD_COUNT_TOLERANCE`-gated retry
loop), since the source text dictates its own length.

Imported episodes get `"source": "imported"` in `episodes.json`
(`VALID_SOURCE_VALUES` in `fabrik/core/config.py`) — `generate_episode.py`'s
single-episode path checks this and skips straight to
`generate_episode_meta()` instead of calling `script_writer.generate_episode`,
since `scripts/<prefix>N.txt` already exists. `podcast_maker.py`/`batch.py`
need no changes at all; they only ever read the finished script file.

### WebUI (`webui/`)

Flask app (`app.py`) + vanilla JS (`static/app.js`) single-page cockpit with
two tabs (Podcast-Fabrik / Lolfi). Commands are declared centrally in
`webui/config.py::COMMANDS` (id → script + arg mapping) and executed via
`webui/runner.py::JobRegistry`, which runs each as a subprocess and streams
stdout to the browser over SSE (`/api/stream/<job_id>`); `webui/status.py`
polls filesystem state (which scripts/audio exist) to drive the step
wizard/status cards. The active series selection is client-side state that
also writes through to `data/series/LATEST` (`/api/pf/series/active`), so CLI
runs outside the WebUI pick up the same default. `pf_create_series` and
`pf_import_story` both create a NEW series and are excluded from the
auto-appended `series` param (`app.js::PF_SERIES_SCOPED_EXCLUDE`) — every
other `pf_*` command gets the currently-selected series injected
automatically.

The log panel (`#log-panel`) starts collapsed and auto-expands on job start
(`app.js::setLogOpen`); a status dot in its header reflects running/done/
error even while collapsed, so collapsing it to reclaim screen space never
hides whether something failed.

"Serie erstellen" mirrors `create_series.py`'s CLI flags 1:1: episode count,
`--minutes` and `--locations` are separate number inputs, threaded through
`args_schema` in `webui/config.py::COMMANDS["pf_create_series"]` and (for the
"Block erzeugen" manual-copy fallback) `webui/prompt_blocks.py::
build_series_prompt_block` / `/api/blocks/pf/series-prompt`. After a
successful create, a review panel (`#pf-series-review`, `app.js::
showSeriesReview`) shows the generated concept (title, template, episode
figures) with "Behalten"/"Verwerfen" — discard calls `POST /api/pf/series/
discard`, which deletes `series/<slug>/` ONLY while it contains no scripts
and no output files (server-side guard, a worked-on series can never be
discarded this way) and repoints `LATEST` to the most recently modified
remaining series. A "Szenen-Orte"
step (`pf_location_prompts`, mirrors the Charakter-Porträts step/status
fields 1:1 — `webui/status.py`'s `locations` dict, `pf-step-locations`
hidden unless the active series has any) only appears for series with a
non-empty `locations` mapping. Lolfi's render step has an episode dropdown
(`#lolfi-episode-select`, fed by `webui/status.py::
_list_podcast_episode_files`, passed as `--episode <filename>` to
`lofi_system.py`), the single "▶ Video rendern" button (dropdown empty =
automatic: anthology preferred, else one arbitrary episode) and "▶ Alle
Episoden einzeln rendern" (`lolfi_render_all`, `lofi_system.py --all`) —
needed because `find_podcast_episodes()` picks exactly one file by
plain filename sort when there's no anthology (`merge_anthology: false`
series), which is `Ep10` before `Ep2` for a 10-episode series, not the
intuitive first episode; `--all` renders every episode found instead of just
that one. "Alles generieren + vertonen + Anthologie" and "Nur diese Episode
generieren" both take a "Wissens-Verstöße/Spoiler-Leaks ... reparieren
(--fix)" checkbox (`#pf-fix-review`, `data-param-fix`) — wires to
`generate_episode.py --fix`, see "Episode review" above. Adding this
checkbox surfaced a real bug in `app.js::collectParams`: it read `el.value`
for every `data-param-*` element, which for an `<input type="checkbox">` is
always `"on"` regardless of whether it's checked — no boolflag control had
used this path before (the pre-existing "Anthologie zusammenfügen" checkbox
has its own dedicated change-listener, not `data-param-*`), so it went
unnoticed. Fixed to branch on `el.type === "checkbox" ? el.checked :
el.value`. The Lolfi tab also has a standalone "🏛 Facades-Hintergrundbilder"
utility block (`lolfi_regenerate_facades`, `~/Downloads/Lolfi/
regenerate_facades.py`) — series-specific, not part of the numbered wizard
steps: re-generates the 4 fixed "Facades" location stills
(`prompts/FACADES_STANDARD_SCENES.md`) from their already-written image
prompts via `gpt-image-1-mini`, without touching the prompts/scene concepts
themselves. Lolfi's background loop is a static image-derived clip in
`video/baseline_normal/` (auto-created by `generate_prompts.py` with
`OPENAI_API_KEY`); the Kling.ai prompt workflow was removed entirely —
`video/baseline/` (ping-pong for animated clips) still works if a clip is
placed there manually, but no tooling produces one anymore.
