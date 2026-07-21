#!/usr/bin/env python3
"""Wählt per Claude 1–3 Teaser-Highlights (30–90s) pro vertonter Episode aus
und schreibt sie als editierbares <Episode>_HIGHLIGHTS.json neben die
Audio-Artefakte — die Vorlage für Lolfis 9:16-Teaser-Clips (TikTok/Reels).

Verwendung:
  python3 -m fabrik.cli.highlight_clips                  # alle vertonten Episoden
  python3 -m fabrik.cli.highlight_clips --episode 3      # nur Episode 3
  python3 -m fabrik.cli.highlight_clips --force          # vorhandene neu generieren
  (--series <slug> wie überall; Standard: data/series/LATEST)

Arbeitsweise: Input ist NICHT das Skript, sondern die satzweisen Cues aus
<Episode>_FULL_EPISODE_SUBS.json — die tragen den gesprochenen Text UND die
Timestamps. Claude bekommt die Cues nummeriert vorgelegt und antwortet mit
Cue-INDEX-Bereichen (start_cue/end_cue), nie mit rohen Zeiten; die
Millisekunden rechnet dieses Skript selbst aus den Cue-Grenzen. Damit sind
halluzinierte Timestamps strukturell ausgeschlossen und jeder Clip snappt
an Satzgrenzen.

Das geschriebene JSON ist ein Review-Gate im MWP-Sinn: von Hand editierbar
(start_ms/end_ms/hook anpassen), bevor Lolfi (lofi_clips.py) daraus rendert.
Lolfi liest nur start_ms/end_ms/hook — Handkorrekturen an den Zeiten
überleben also; start_cue/end_cue/why sind reine Doku.

Braucht kein .venv — nur die Claude CLI (wie generate_episode.py).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

from fabrik.core import config, paths
from fabrik.core.claude_cli import run_claude_process, parse_json_response
from fabrik.writing.script_writer import MAX_RETRIES, RETRY_DELAY

# Eigener, großzügigerer Timeout statt script_writer.TIMEOUT_SECONDS (300s):
# der Prompt trägt hunderte Cue-Zeilen (lange Episoden ~60k Zeichen), die
# Antwort ist winzig — die Zeit geht ins Prompt-Processing, nicht den Output.
TIMEOUT_SECONDS = 600

MIN_CLIP_S = 20    # harte Validierungsgrenzen; das Prompt verlangt 30–90s,
MAX_CLIP_S = 100   # etwas Toleranz, weil Cue-Grenzen nie exakt landen
MAX_HOOK_CHARS = 90


def highlights_path(series, episode_name):
    """<output_dir>/<Name>_FULL_EPISODE_HIGHLIGHTS.json — bewusst die
    SUBS-Namenskonvention (Infix _FULL_EPISODE bleibt erhalten, anders als
    bei _SPEAKERS.json): Lolfis Lookup ist damit ein reines
    splitext(audio)[0] + Suffix, ohne Stem-Stripping."""
    return os.path.join(series.output_dir, f"{episode_name}_FULL_EPISODE_HIGHLIGHTS.json")


def subs_path(series, episode_name):
    return os.path.join(series.output_dir, f"{episode_name}_FULL_EPISODE_SUBS.json")


def mp3_path(series, episode_name):
    return os.path.join(series.output_dir, f"{episode_name}_FULL_EPISODE.mp3")


def parse_meta_file(meta_path):
    """TITEL/BESCHREIBUNG (FRAGE wird hier ignoriert) aus <prefix>N_META.txt
    — Regex identisch zu fabrik/audio/pipeline.py::parse_meta_file, hier
    lokal gespiegelt, weil dieses CLI ohne venv laufen muss und
    fabrik/audio deshalb tabu ist (Import-Regel, siehe fabrik/core/CLAUDE.md)."""
    if not os.path.exists(meta_path):
        return None, None
    with open(meta_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"TITEL:\s*(.+?)\s*BESCHREIBUNG:\s*(.+?)(?:\n\s*FRAGE:\s*.+)?\s*$",
                      content, re.DOTALL)
    if not match:
        return None, None
    return match.group(1).strip(), match.group(2).strip()


def load_cues(path):
    """Cues aus der SUBS-JSON; None bei fehlender/kaputter Datei (Aufrufer
    überspringt die Episode mit Meldung, kein Abbruch des Batch)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  WARNUNG: {os.path.basename(path)} nicht lesbar ({exc}) — übersprungen.")
        return None
    cues = data.get("cues")
    if not isinstance(cues, list) or not cues:
        print(f"  WARNUNG: {os.path.basename(path)} enthält keine Cues — übersprungen.")
        return None
    return cues


def fmt_mmss(ms):
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def build_prompt(data, episode, cues, meta_title, meta_desc, feedback=None):
    series_title = data.get("series_title", "")
    language = data.get("language", "German")
    style = data.get("style_guidelines", "")

    cue_lines = "\n".join(
        f"[{i}] {fmt_mmss(c['start_ms'])}-{fmt_mmss(c['end_ms'])} {c.get('role', '?')}: {c.get('text', '')}"
        for i, c in enumerate(cues)
    )
    ep_bits = []
    if meta_title:
        ep_bits.append(f"Episode title: {meta_title}")
    if meta_desc:
        ep_bits.append(f"Episode description: {meta_desc}")
    theme = episode.get("theme") or episode.get("figure")
    if theme:
        ep_bits.append(f"Episode theme: {theme}")
    ep_block = "\n".join(ep_bits)

    prompt = (
        f"\"{series_title}\" is an audio drama podcast (dialogue language: {language}). "
        f"Series tone/style notes: {style}\n\n"
        f"{ep_block}\n\n"
        f"Below is the complete episode as numbered subtitle cues with "
        f"timestamps (mm:ss) and speaking role:\n\n{cue_lines}\n\n"
        f"I want to publish 30-90 second vertical teaser clips of this episode "
        f"on TikTok and Instagram Reels. Pick the 1-3 strongest CONTIGUOUS cue "
        f"ranges that work as teasers: a conflict peak, a sharp confrontation, "
        f"a cliffhanger line, an emotionally loaded exchange. Rules:\n"
        f"- Each range must be roughly 30-90 seconds long (use the timestamps).\n"
        f"- A range must work WITHOUT context: it should pull a cold viewer in, "
        f"not require knowing the plot.\n"
        f"- NEVER spoil a resolution, reveal, or ending — tease, don't tell.\n"
        f"- Ranges must not overlap.\n"
        f"- Prefer ranges that END on a hook (an unanswered question, an "
        f"interrupted accusation) rather than a resolved beat.\n"
        f"- For each clip write a short on-screen hook line (max {MAX_HOOK_CHARS} "
        f"characters, language: {language}) — the text overlay at the top of "
        f"the video that stops the scroll. No quotation marks around it.\n\n"
        f"Answer ONLY with JSON in exactly this shape (cue indices refer to "
        f"the [n] numbers above, both ends inclusive):\n"
        f'{{"clips": [{{"start_cue": 12, "end_cue": 31, '
        f'"hook": "...", "why": "one sentence"}}]}}'
    )
    if feedback:
        prompt += (
            f"\n\nYour previous answer was rejected for these reasons — "
            f"fix ALL of them:\n{feedback}"
        )
    return prompt


def validate_clips(clips, cues):
    """Liefert eine Fehlerliste (leer = gültig). Fehlertexte gehen wörtlich
    als Feedback in den Retry — daher konkret formulieren."""
    errors = []
    if not isinstance(clips, list) or not clips:
        return ["'clips' must be a non-empty list (1-3 entries)."]
    if len(clips) > 3:
        errors.append(f"Too many clips ({len(clips)}) — return at most 3.")

    spans = []
    for n, clip in enumerate(clips, start=1):
        if not isinstance(clip, dict):
            errors.append(f"Clip {n}: must be an object.")
            continue
        start, end = clip.get("start_cue"), clip.get("end_cue")
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"Clip {n}: start_cue/end_cue must be integers.")
            continue
        if not (0 <= start < len(cues)) or not (0 <= end < len(cues)):
            errors.append(f"Clip {n}: cue index out of range 0..{len(cues) - 1}.")
            continue
        if start > end:
            errors.append(f"Clip {n}: start_cue ({start}) > end_cue ({end}).")
            continue
        dur_s = (cues[end]["end_ms"] - cues[start]["start_ms"]) / 1000.0
        if not (MIN_CLIP_S <= dur_s <= MAX_CLIP_S):
            errors.append(
                f"Clip {n}: duration {dur_s:.0f}s is outside {MIN_CLIP_S}-{MAX_CLIP_S}s "
                f"— pick a longer/shorter cue range (target 30-90s)."
            )
        hook = clip.get("hook")
        if not isinstance(hook, str) or not hook.strip():
            errors.append(f"Clip {n}: 'hook' must be a non-empty string.")
        elif len(hook.strip()) > MAX_HOOK_CHARS:
            errors.append(f"Clip {n}: hook is {len(hook.strip())} chars — max {MAX_HOOK_CHARS}.")
        spans.append((start, end, n))

    spans.sort()
    for (s1, e1, n1), (s2, e2, n2) in zip(spans, spans[1:]):
        if s2 <= e1:
            errors.append(f"Clips {n1} and {n2} overlap (cues {s1}-{e1} vs {s2}-{e2}).")
    return errors


def call_claude(prompt, model, label, effort=None):
    """Wie script_writer.call_claude, aber mit dem längeren lokalen Timeout.
    stdin=DEVNULL + Heartbeat übernimmt run_claude_process; nur 'claude not
    found' und 401 brechen ab, alles andere ist retryable (None)."""
    argv = ["claude", "-p", prompt, "--output-format", "text",
            "--model", model, "--tools", ""]
    if effort:
        argv += ["--effort", effort]
    try:
        result = run_claude_process(argv, TIMEOUT_SECONDS, label)
    except FileNotFoundError:
        print("FEHLER: 'claude' nicht gefunden → Claude Code installieren.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"  Timeout nach {TIMEOUT_SECONDS}s.")
        return None
    if result.returncode != 0:
        output = (result.stderr.strip() or result.stdout.strip())[:500]
        if "401" in output or "authentication" in output.lower():
            print("  FEHLER: Nicht eingeloggt → 'claude' im Terminal öffnen und /login ausführen.")
            sys.exit(1)
        print(f"  API-Fehler (exit {result.returncode}): {output}")
        return None
    return result.stdout.strip() or None


def generate_highlights(data, episode, episode_name, cues, meta_title, meta_desc, model):
    """Ein Claude-Call mit Validierungs-Retry (Fehler wörtlich zurückgefüttert,
    Muster wie call_claude_with_retry). None, wenn alle Versuche scheitern."""
    feedback = None
    for attempt in range(1, MAX_RETRIES + 1):
        prompt = build_prompt(data, episode, cues, meta_title, meta_desc, feedback)
        output = call_claude(prompt, model, f"Highlights {episode_name}")
        if output is None:
            print(f"  Versuch {attempt}/{MAX_RETRIES}: keine Ausgabe.")
        else:
            parsed = parse_json_response(output)
            if parsed is None:
                feedback = "Answer was not parseable JSON. Return ONLY the JSON object."
                print(f"  Versuch {attempt}/{MAX_RETRIES}: kein parsebares JSON.")
            else:
                clips = parsed.get("clips")
                errors = validate_clips(clips, cues)
                if not errors:
                    return clips
                feedback = "\n".join(f"- {e}" for e in errors)
                print(f"  Versuch {attempt}/{MAX_RETRIES}: {len(errors)} Validierungsfehler:")
                for e in errors:
                    print(f"    - {e}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
    return None


def write_highlights(out_file, episode_name, clips, cues):
    """Schreibt das editierbare Artefakt. start_ms/end_ms sind aus den
    Cue-Grenzen GERECHNET (nie von Claude) — das ist der Snapping-Vertrag."""
    entries = []
    for n, clip in enumerate(sorted(clips, key=lambda c: c["start_cue"]), start=1):
        start_ms = cues[clip["start_cue"]]["start_ms"]
        end_ms = cues[clip["end_cue"]]["end_ms"]
        entries.append({
            "index": n,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_s": round((end_ms - start_ms) / 1000.0, 1),
            "start_cue": clip["start_cue"],
            "end_cue": clip["end_cue"],
            "hook": clip["hook"].strip(),
            "why": (clip.get("why") or "").strip(),
        })
    payload = {
        "episode": f"{episode_name}_FULL_EPISODE",
        "hinweis": ("Von Hand editierbar: start_ms/end_ms/hook anpassen, dann "
                    "Teaser-Clips rendern (Lolfi: lofi_clips.py). Lolfi liest nur "
                    "start_ms/end_ms/hook. --force generiert neu."),
        "clips": entries,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return entries


def print_clips(entries, source):
    for e in entries:
        print(f"  Clip {e['index']}: {fmt_mmss(e['start_ms'])}-{fmt_mmss(e['end_ms'])} "
              f"({e['duration_s']:.0f}s) — „{e['hook']}“ {source}")


def main():
    parser = argparse.ArgumentParser(
        description="Teaser-Highlights (30-90s) pro Episode per Claude auswählen")
    parser.add_argument("--episode", type=int, default=None, metavar="N",
                        help="Nur Episode N (Standard: alle vertonten Episoden)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene HIGHLIGHTS.json neu generieren")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)

    prefix = data.get("output_prefix", config.DEFAULTS["output_prefix"])
    episodes = data.get("episodes", [])
    model = data.get("generation", {}).get("model", config.DEFAULTS["model"])

    if args.episode is not None and not (1 <= args.episode <= len(episodes)):
        print(f"FEHLER: --episode {args.episode} — Serie hat Episoden 1..{len(episodes)}.")
        sys.exit(1)

    targets = [args.episode] if args.episode is not None else range(1, len(episodes) + 1)
    done = skipped = failed = 0

    for i in targets:
        episode = episodes[i - 1]
        episode_name = f"{prefix}{i}".capitalize()
        out_file = highlights_path(series, episode_name)

        if not os.path.exists(mp3_path(series, episode_name)) or \
           not os.path.exists(subs_path(series, episode_name)):
            if args.episode is not None:
                print(f"FEHLER: Episode {i} ist nicht vertont (MP3/SUBS fehlen in "
                      f"{series.output_dir}) — erst vertonen, dann Highlights wählen.")
                sys.exit(1)
            continue  # Batch-Modus: unvertonte Episoden still auslassen

        print(f"Episode {i} ({episode_name}):")

        if os.path.exists(out_file) and not args.force:
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    existing = json.load(f).get("clips", [])
            except (OSError, json.JSONDecodeError):
                existing = []
            print(f"  Highlights bereits vorhanden ({os.path.basename(out_file)}, "
                  f"--force zum Neu-Generieren):")
            print_clips(existing, "")
            skipped += 1
            continue

        cues = load_cues(subs_path(series, episode_name))
        if cues is None:
            failed += 1
            continue

        meta_title, meta_desc = parse_meta_file(series.meta_file(prefix, i))
        print(f"  {len(cues)} Cues, Modell: {model} ...")
        clips = generate_highlights(data, episode, episode_name, cues,
                                    meta_title, meta_desc, model)
        if clips is None:
            print(f"  FEHLER: Episode {i} — kein gültiges Ergebnis nach "
                  f"{MAX_RETRIES} Versuchen (später erneut starten).")
            failed += 1
            continue

        entries = write_highlights(out_file, episode_name, clips, cues)
        print(f"  Gespeichert: {out_file}")
        print_clips(entries, "")
        done += 1

    print(f"\nFertig: {done} generiert, {skipped} vorhanden, {failed} fehlgeschlagen.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
