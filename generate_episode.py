#!/usr/bin/env python3
"""
Automatisierter Podcast-Script-Generator via Claude CLI.
Generiert jede Section einzeln und schreibt sie sofort in die Datei.

Verwendung:
  python generate_episode.py 1          # Episode 1 → figur1.txt
  python generate_episode.py all        # Alle Episoden nacheinander
  python generate_episode.py 1 --force  # Komplett neu generieren

Konfiguration:
  episodes.json       → komplette Podcast-Definition: Serie, Figuren, Sprache,
                        Stil, Format (Parts/Section, Wortbudget), Modell, Audio
  PROMPT_TEMPLATE.md  → neutrales Prompt-Gerüst; Platzhalter werden aus
                        episodes.json befüllt

Dieses Skript ist bewusst inhalts-neutral: alles, was den Podcast ausmacht,
steht in episodes.json.
"""

import subprocess
import sys
import os
import re
import json
import argparse
import time
from datetime import datetime
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "PROMPT_TEMPLATE.md")
EPISODES_FILE = os.path.join(SCRIPT_DIR, "episodes.json")
FIGURE_HISTORY_FILE = os.path.join(SCRIPT_DIR, "figure_history.json")

TIMEOUT_SECONDS = 300   # max. Wartezeit pro Claude-Aufruf
MAX_RETRIES     = 3     # Wiederholungsversuche bei Fehler oder schlechter Qualität
RETRY_DELAY     = 5     # Sekunden zwischen Versuchen

# Fallbacks, falls episodes.json einzelne Schlüssel nicht definiert
DEFAULTS = {
    "language": "English",
    "writer_persona": "a brilliant scriptwriter for high-end documentaries",
    "style_guidelines": [],
    "parts_per_section": 2,
    "words_per_part_min": 430,
    "words_per_part_max": 520,
    "words_per_part_target": "450 to 500",
    "model": "claude-sonnet-5",
    "output_prefix": "figur",
}


def load_template() -> str:
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    marker = "--- TEMPLATE START ---"
    if marker not in content:
        print(f"FEHLER: '{marker}' nicht in PROMPT_TEMPLATE.md gefunden.")
        sys.exit(1)
    # rsplit: falls der Marker zusätzlich im Kommentar-Header erwähnt wird,
    # zählt nur das letzte (echte) Vorkommen
    return content.rsplit(marker, 1)[1].strip()


def load_episodes() -> dict:
    try:
        with open(EPISODES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"FEHLER: episodes.json nicht gefunden: {EPISODES_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"FEHLER: episodes.json ist kein gültiges JSON.")
        print(f"  Zeile {e.lineno}, Spalte {e.colno}: {e.msg}")
        sys.exit(1)


# Erlaubte Schlüssel — unbekannte Schlüssel (z.B. KI-Tippfehler) erzeugen eine Warnung
VALID_TOP_KEYS = {
    "series_title", "language", "writer_persona", "style_guidelines",
    "format", "generation", "audio", "output_prefix",
    "series_intro", "series_outro", "episodes",
}
VALID_FORMAT_KEYS = {
    "parts_per_section", "words_per_part_target",
    "words_per_part_min", "words_per_part_max",
}
VALID_GENERATION_KEYS = {"model"}
VALID_AUDIO_KEYS = {
    "api_url", "voice", "default_style", "target_lufs",
    "pause_between_chunks_ms", "pause_between_parts_ms", "pause_between_episodes_ms",
    "backend", "ref_audio", "ref_text", "model_size", "language", "chunk_gap",
}
VALID_EPISODE_KEYS = {
    "figure", "theme", "intro_note", "outro_note", "sections", "section_styles",
}


def validate_data(data) -> tuple[list[str], list[str]]:
    """Prüft episodes.json vollständig und liefert (Fehler, Warnungen).

    Ziel: Jede fehlerhafte oder mehrdeutige Eingabe (z.B. von einer KI
    generiert) wird VOR dem Start klar benannt, statt später kryptisch
    abzustürzen oder stumm mit Defaults weiterzulaufen."""
    errors: list[str] = []
    warnings: list[str] = []

    def is_int(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def is_str_list(v):
        return isinstance(v, list) and all(isinstance(s, str) and s.strip() for s in v)

    if not isinstance(data, dict):
        return ["Top-Level von episodes.json muss ein JSON-Objekt sein"], []

    for key in data:
        if key not in VALID_TOP_KEYS:
            warnings.append(f"Unbekannter Schlüssel '{key}' — wird ignoriert (Tippfehler?)")

    # --- Top-Level-Strings ---
    if not isinstance(data.get("series_title"), str) or not data.get("series_title", "").strip():
        errors.append("'series_title' fehlt oder ist kein nicht-leerer String")
    for key in ("language", "writer_persona", "series_intro", "series_outro"):
        if key in data and (not isinstance(data[key], str) or not data[key].strip()):
            errors.append(f"'{key}' muss ein nicht-leerer String sein")

    prefix = data.get("output_prefix")
    if prefix is not None:
        if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
            errors.append("'output_prefix' muss ein String aus Buchstaben, Zahlen, '-' oder '_' sein (wird Teil der Dateinamen)")

    if "style_guidelines" in data and not is_str_list(data["style_guidelines"]):
        errors.append("'style_guidelines' muss eine Liste nicht-leerer Strings sein")

    # --- format ---
    fmt = data.get("format", {})
    if not isinstance(fmt, dict):
        errors.append("'format' muss ein Objekt sein")
        fmt = {}
    for key in fmt:
        if key not in VALID_FORMAT_KEYS:
            warnings.append(f"Unbekannter Schlüssel 'format.{key}' — wird ignoriert (Tippfehler?)")
    pps = fmt.get("parts_per_section", DEFAULTS["parts_per_section"])
    if not is_int(pps) or pps < 1:
        errors.append("'format.parts_per_section' muss eine ganze Zahl >= 1 sein")
    min_w = fmt.get("words_per_part_min", DEFAULTS["words_per_part_min"])
    max_w = fmt.get("words_per_part_max", DEFAULTS["words_per_part_max"])
    if not is_int(min_w) or min_w < 1:
        errors.append("'format.words_per_part_min' muss eine ganze Zahl >= 1 sein")
    if not is_int(max_w) or max_w < 1:
        errors.append("'format.words_per_part_max' muss eine ganze Zahl >= 1 sein")
    if is_int(min_w) and is_int(max_w) and min_w >= max_w:
        errors.append(f"'format.words_per_part_min' ({min_w}) muss kleiner als 'words_per_part_max' ({max_w}) sein")
    if "words_per_part_target" in fmt and (not isinstance(fmt["words_per_part_target"], str) or not fmt["words_per_part_target"].strip()):
        errors.append("'format.words_per_part_target' muss ein nicht-leerer String sein (z.B. \"450 to 500\")")

    # --- generation ---
    gen = data.get("generation", {})
    if not isinstance(gen, dict):
        errors.append("'generation' muss ein Objekt sein")
        gen = {}
    for key in gen:
        if key not in VALID_GENERATION_KEYS:
            warnings.append(f"Unbekannter Schlüssel 'generation.{key}' — wird ignoriert (Tippfehler?)")
    if "model" in gen and (not isinstance(gen["model"], str) or not gen["model"].strip()):
        errors.append("'generation.model' muss ein nicht-leerer String sein")

    # --- audio ---
    audio = data.get("audio", {})
    if not isinstance(audio, dict):
        errors.append("'audio' muss ein Objekt sein")
        audio = {}
    for key in audio:
        if key not in VALID_AUDIO_KEYS:
            warnings.append(f"Unbekannter Schlüssel 'audio.{key}' — wird ignoriert (Tippfehler?)")
    for key in ("voice", "default_style"):
        if key in audio and (not isinstance(audio[key], str) or not audio[key].strip()):
            errors.append(f"'audio.{key}' muss ein nicht-leerer String sein")
    if "api_url" in audio and (not isinstance(audio["api_url"], str)
                               or not re.match(r"https?://", audio["api_url"])):
        errors.append("'audio.api_url' muss eine URL sein (z.B. \"http://127.0.0.1:42003\")")
    if "target_lufs" in audio and not is_num(audio["target_lufs"]):
        errors.append("'audio.target_lufs' muss eine Zahl sein (z.B. -16.0)")
    for key in ("pause_between_chunks_ms", "pause_between_parts_ms", "pause_between_episodes_ms"):
        if key in audio and (not is_int(audio[key]) or audio[key] < 0):
            errors.append(f"'audio.{key}' muss eine ganze Zahl >= 0 sein (Millisekunden)")

    # --- episodes ---
    episodes = data.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        errors.append("'episodes' fehlt oder ist keine nicht-leere Liste")
        episodes = []

    section_counts = set()
    for i, ep in enumerate(episodes):
        path = f"episodes[{i}]"
        if not isinstance(ep, dict):
            errors.append(f"'{path}' muss ein Objekt sein")
            continue
        for key in ep:
            if key not in VALID_EPISODE_KEYS:
                warnings.append(f"Unbekannter Schlüssel '{path}.{key}' — wird ignoriert (Tippfehler?)")
        for key in ("figure", "theme"):
            if not isinstance(ep.get(key), str) or not ep.get(key, "").strip():
                errors.append(f"'{path}.{key}' fehlt oder ist kein nicht-leerer String")
        for key in ("intro_note", "outro_note"):
            if key in ep and not isinstance(ep[key], str):
                errors.append(f"'{path}.{key}' muss ein String sein (leerer String \"\" = keine Vorgabe)")

        secs = ep.get("sections")
        if not is_str_list(secs) or not secs:
            errors.append(f"'{path}.sections' fehlt oder ist keine nicht-leere Liste von Strings")
            continue
        section_counts.add(len(secs))

        styles = ep.get("section_styles")
        if styles is not None:
            if not is_str_list(styles):
                errors.append(f"'{path}.section_styles' muss eine Liste nicht-leerer Strings sein")
            elif len(styles) != len(secs):
                errors.append(
                    f"'{path}.section_styles' hat {len(styles)} Einträge, aber es gibt "
                    f"{len(secs)} Sections — pro Section genau ein Style"
                )
        else:
            warnings.append(f"'{path}.section_styles' fehlt — alle Parts bekommen den audio.default_style")

    if len(section_counts) > 1:
        warnings.append(
            f"Episoden haben unterschiedlich viele Sections ({sorted(section_counts)}) — "
            f"die Episoden werden dadurch unterschiedlich lang"
        )

    return errors, warnings


def validate_or_exit(data):
    """Druckt alle Warnungen/Fehler; bricht bei Fehlern ab, bevor etwas Teures startet."""
    errors, warnings = validate_data(data)
    for w in warnings:
        print(f"WARNUNG: {w}")
    if errors:
        print(f"\nFEHLER: episodes.json hat {len(errors)} Problem(e):")
        for e in errors:
            print(f"  - {e}")
        print("\nBitte episodes.json korrigieren und erneut starten.")
        sys.exit(1)


def load_figure_history() -> list[dict]:
    if not os.path.exists(FIGURE_HISTORY_FILE):
        return []
    try:
        with open(FIGURE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_figure_history(history: list[dict]):
    with open(FIGURE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def warn_on_repeated_figures(data: dict):
    """Prüft, ob eine Figur der aktuellen Serie bereits in einer FRÜHEREN,
    ANDEREN Serie vorkam — merkt sich alle Figuren dauerhaft in
    figure_history.json, damit dieselbe Figur nicht in immer neuen Podcasts
    wieder auftaucht. Blockiert nicht (könnte ein bewusstes Crossover sein),
    warnt aber deutlich."""
    history = load_figure_history()
    series_title = data.get("series_title", "")
    used_elsewhere = {
        h["figure"]: h["series_title"]
        for h in history
        if h["series_title"] != series_title
    }
    for ep in data.get("episodes", []):
        figure = ep.get("figure")
        if figure in used_elsewhere:
            print(f"⚠️  WARNUNG: Figur '{figure}' kam bereits in der Serie "
                  f"\"{used_elsewhere[figure]}\" vor — figure_history.json prüfen.")


def record_figure(figure: str, series_title: str):
    """Trägt eine erfolgreich generierte Figur dauerhaft in die Historie ein
    (einmal pro Figur+Serie, kein Duplikat bei erneutem Lauf derselben Episode)."""
    history = load_figure_history()
    if any(h["figure"] == figure and h["series_title"] == series_title for h in history):
        return
    history.append({
        "figure": figure,
        "series_title": series_title,
        "created": datetime.now().isoformat(timespec="seconds"),
    })
    save_figure_history(history)


def build_config(data) -> dict:
    """Extrahiert die Format-/Generierungs-Konfiguration aus episodes.json."""
    fmt = data.get("format", {})
    gen = data.get("generation", {})
    return {
        "language": data.get("language", DEFAULTS["language"]),
        "persona": data.get("writer_persona", DEFAULTS["writer_persona"]),
        "style_guidelines": data.get("style_guidelines", DEFAULTS["style_guidelines"]),
        "parts_per_section": fmt.get("parts_per_section", DEFAULTS["parts_per_section"]),
        "min_words": fmt.get("words_per_part_min", DEFAULTS["words_per_part_min"]),
        "max_words": fmt.get("words_per_part_max", DEFAULTS["words_per_part_max"]),
        "words_target": fmt.get("words_per_part_target", DEFAULTS["words_per_part_target"]),
        "model": gen.get("model", DEFAULTS["model"]),
        "prefix": data.get("output_prefix", DEFAULTS["output_prefix"]),
    }


def build_intro_spec(position, total, series_title, figure, prev_figure,
                     series_intro, intro_note):
    if position == 1:
        detail = intro_note if intro_note else series_intro
        return f"--- PART 1 --- MUST start with {detail}, before diving into {figure}."
    else:
        if intro_note:
            detail = intro_note[0].lower() + intro_note[1:]
        else:
            detail = (
                f"a brief, atmospheric recap of the anthology's core theme and a seamless "
                f"transition from {prev_figure}'s story into {figure}'s world"
            )
        return f"--- PART 1 --- must start with {detail}."


def build_outro_spec(position, total, next_figure, series_outro, outro_note,
                     last_part):
    if position == total:
        detail = outro_note if outro_note else series_outro
        return f"--- PART {last_part} --- MUST end with {detail}."
    else:
        tease = outro_note if outro_note else f"the next figure: {next_figure}"
        return (
            f"--- PART {last_part} --- MUST end with a powerful outro and explicitly tease {tease}."
        )


def section_part_numbers(section_idx, parts_per_section) -> list[int]:
    """Part-Nummern einer Section (z.B. Section 0 bei 2 Parts/Section → [1, 2])."""
    first = section_idx * parts_per_section + 1
    return list(range(first, first + parts_per_section))


def build_section_prompt(template, data, episodes, ep_idx, section_idx,
                          previous_content, cfg):
    episode = episodes[ep_idx]
    total = len(episodes)
    position = ep_idx + 1
    figure = episode["figure"]
    prev_figure = episodes[ep_idx - 1]["figure"] if ep_idx > 0 else None
    next_figure = episodes[ep_idx + 1]["figure"] if ep_idx < total - 1 else None
    sections = episode["sections"]

    pps = cfg["parts_per_section"]
    parts_total = len(sections) * pps
    parts = section_part_numbers(section_idx, pps)
    section_title = sections[section_idx]

    series_title  = data.get("series_title", "")
    series_intro  = data.get("series_intro", "an epic intro for the entire anthology series")
    series_outro  = data.get("series_outro", "a grand conclusion for the entire series")
    intro_note    = episode.get("intro_note", "")
    outro_note    = episode.get("outro_note", "")

    intro_spec = build_intro_spec(position, total, series_title, figure,
                                   prev_figure, series_intro, intro_note)
    outro_spec = build_outro_spec(position, total, next_figure,
                                   series_outro, outro_note, parts_total)

    all_sections_text = "\n".join(
        f"Section {i+1}: {s} ("
        + " and ".join(f"--- PART {n} ---" for n in section_part_numbers(i, pps))
        + ")"
        for i, s in enumerate(sections)
    )

    style_guidelines_text = "\n".join(f"- {g}" for g in cfg["style_guidelines"])

    replacements = {
        "{{PERSONA}}": cfg["persona"],
        "{{SERIES_TITLE}}": series_title,
        "{{LANGUAGE}}": cfg["language"],
        "{{FIGURE_NAME}}": figure,
        "{{POSITION}}": str(position),
        "{{TOTAL}}": str(total),
        "{{THEME}}": episode["theme"],
        "{{PARTS_TOTAL}}": str(parts_total),
        "{{SECTIONS_TOTAL}}": str(len(sections)),
        "{{PARTS_PER_SECTION}}": str(pps),
        "{{WORDS_TARGET}}": cfg["words_target"],
        "{{WORDS_MIN}}": str(cfg["min_words"]),
        "{{WORDS_MAX}}": str(cfg["max_words"]),
        "{{INTRO_SPEC}}": intro_spec,
        "{{OUTRO_SPEC}}": outro_spec,
        "{{SECTIONS}}": all_sections_text,
        "{{STYLE_GUIDELINES}}": style_guidelines_text,
    }

    prompt = template
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)

    if previous_content:
        # Only pass the last section (previous_parts_per_section parts) as context —
        # Claude needs continuity, not the full episode history.
        prev_parts = re.findall(r'--- PART \d+ ---\n\n.*?(?=--- PART \d+ ---|\Z)',
                                previous_content, re.DOTALL)
        context = "".join(prev_parts[-cfg["parts_per_section"]:]).strip() if prev_parts else previous_content
        prompt += (
            f"\n\nHere is the immediately preceding section of this episode "
            f"(do NOT repeat this, continue seamlessly from where it left off):\n\n"
            f"{context}\n"
        )

    markers = "\n".join(f"--- PART {n} ---" for n in parts)
    prompt += (
        f"\n\nNow write ONLY Section {section_idx + 1}: \"{section_title}\".\n"
        f"This section consists of exactly {pps} part(s):\n"
        f"{markers}\n\n"
        f"Start immediately with --- PART {parts[0]} --- and end after --- PART {parts[-1]} ---. "
        f"Do not write any other parts. Do not add summaries or comments."
    )

    # Sprechstil der Section (aus episodes.json) in den Schreib-Prompt reichen,
    # damit Rhythmus und Intensität des Textes zur späteren Vertonung passen.
    styles = episode.get("section_styles")
    if styles and section_idx < len(styles):
        prompt += (
            f"\n\nVOCAL DELIVERY: This section will later be narrated in this exact "
            f"vocal style: \"{styles[section_idx]}\". Shape the prose to support that "
            f"delivery — sentence length, rhythm, and emotional intensity must make "
            f"this way of speaking feel natural. Do NOT include stage directions, "
            f"sound cues, or any meta text; express the delivery purely through the writing."
        )

    return prompt


def call_claude(prompt, model) -> Optional[str]:
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text",
             "--model", model, "--tools", ""],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
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


def extract_parts(output, expected_parts) -> list[tuple[int, str]]:
    chunks = re.split(r'---\s*PART\s+(\d+)\s*---', output)
    parts = {}
    for i in range(1, len(chunks), 2):
        num = int(chunks[i])
        text = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
        parts[num] = text
    return [(num, parts[num]) for num in expected_parts if num in parts]


WORD_COUNT_TOLERANCE = 15  # Puffer um min/max — vermeidet komplette Section-Neugenerierung
                           # (kostet 2 volle Parts an Tokens) wegen weniger Wörter Differenz


def validate_parts(parts, expected_parts, min_words, max_words) -> tuple[bool, str, list[str]]:
    """Prüft ob alle erwarteten Parts vorhanden und im Wortzahl-Fenster liegen.
    Toleriert eine kleine Abweichung (WORD_COUNT_TOLERANCE) an den Rändern —
    430 vs. 429 Wörter ist inhaltlich irrelevant und keine komplette
    Neugenerierung wert.

    Rückgabe: (ok, deutsche Konsolen-Kurzmeldung, englische Wortzahl-Bilanz
    pro Part). Die Bilanz wird bei einem Retry wörtlich ins Modell-Feedback
    übernommen — nur so weiß Claude, WELCHER Part um WIEVIEL Wörter daneben
    lag, statt beim nächsten Versuch erneut blind zu raten."""
    found = {num for num, _ in parts}
    missing = [num for num in expected_parts if num not in found]
    if missing:
        console = f"Part(s) {missing} fehlen komplett in der Ausgabe"
        detail = [f"Part {num}: MISSING from your output" for num in missing]
        return False, console, detail

    ok = True
    console = ""
    detail = []
    for num, text in parts:
        words = len(text.split())
        if words < min_words - WORD_COUNT_TOLERANCE:
            ok = False
            console = console or f"Part {num} zu kurz ({words} Wörter, minimum {min_words})"
            detail.append(f"Part {num}: {words} words — TOO SHORT (needs {min_words}-{max_words})")
        elif words > max_words + WORD_COUNT_TOLERANCE:
            ok = False
            console = console or f"Part {num} zu lang ({words} Wörter, maximum {max_words})"
            detail.append(f"Part {num}: {words} words — TOO LONG (needs {min_words}-{max_words})")
        else:
            detail.append(f"Part {num}: {words} words — OK")
    return ok, console, detail


def call_claude_with_retry(prompt, expected_parts, cfg) -> Optional[list[tuple[int, str]]]:
    """Ruft Claude auf und wiederholt bei Fehler oder defekter Ausgabe."""
    feedback = ""
    for attempt in range(1, MAX_RETRIES + 1):
        prefix = f"  Versuch {attempt}/{MAX_RETRIES}"

        output = call_claude(prompt + feedback, cfg["model"])
        if not output:
            print(f"{prefix}: Keine Ausgabe erhalten.")
        else:
            parts = extract_parts(output, expected_parts)
            ok, console_reason, detail = validate_parts(parts, expected_parts,
                                        cfg["min_words"], cfg["max_words"])
            if ok:
                return parts
            print(f"{prefix}: Defekte Ausgabe — {console_reason}")
            detail_text = "\n".join(detail)
            feedback = (
                f"\n\nIMPORTANT: Your previous attempt was rejected. Actual word count per part:\n"
                f"{detail_text}\n\n"
                f"Every part MUST be between {cfg['min_words']} and {cfg['max_words']} words "
                f"(target {cfg['words_target']}). Rewrite the full section, keeping the parts "
                f"marked OK roughly as they were and expanding/trimming only the parts marked "
                f"TOO SHORT/TOO LONG — add scene-setting, sensory detail, or dialogue-adjacent "
                f"narration to expand, never filler."
            )

        if attempt < MAX_RETRIES:
            print(f"  Warte {RETRY_DELAY}s vor nächstem Versuch ...")
            time.sleep(RETRY_DELAY)

    print(f"  Alle {MAX_RETRIES} Versuche fehlgeschlagen.")
    return None


def read_existing_parts(output_file) -> tuple[set[int], str]:
    """Liest bereits geschriebene Parts aus einer vorhandenen Datei.

    Doppelte Part-Nummern (z.B. nach Abbruch mitten im Schreiben einer
    Section und anschließender Neugenerierung) werden bereinigt: die letzte
    Version gewinnt, die Datei wird sortiert neu geschrieben — sonst würde
    der doppelte Part später doppelt vertont."""
    if not os.path.exists(output_file):
        return set(), ""
    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = re.findall(r'--- PART (\d+) ---\n\n(.*?)(?=--- PART \d+ ---|\Z)',
                        content, re.DOTALL)
    nums = [int(n) for n, _ in blocks]
    if len(nums) != len(set(nums)):
        latest = {int(n): text.strip() for n, text in blocks}
        content = "".join(f"--- PART {n} ---\n\n{latest[n]}\n\n"
                          for n in sorted(latest))
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        dupes = sorted({n for n in nums if nums.count(n) > 1})
        print(f"  Doppelte Parts {dupes} in {os.path.basename(output_file)} bereinigt "
              f"(letzte Version behalten).")
        return set(latest), content

    return set(nums), content


def generate_episode_meta(ep_idx, data, episodes, force, cfg) -> bool:
    """Erzeugt Titel + Beschreibung für die Episode (z.B. für den Video-Upload)
    und schreibt sie nach figurN_META.txt."""
    episode_num = ep_idx + 1
    episode = episodes[ep_idx]
    meta_file = os.path.join(SCRIPT_DIR, f"{cfg['prefix']}{episode_num}_META.txt")

    if os.path.exists(meta_file) and not force:
        print(f"  Titel & Beschreibung bereits vorhanden: {os.path.basename(meta_file)} ✓")
        return True

    sections_text = "\n".join(f"- {s}" for s in episode["sections"])
    prompt = (
        f"You are {cfg['persona']}. The podcast series \"{data.get('series_title', '')}\" "
        f"has an episode about {episode['figure']}.\n\n"
        f"Core theme: {episode['theme']}\n\n"
        f"The episode covers these chapters:\n{sections_text}\n\n"
        f"Write metadata for publishing this episode as a video/podcast, "
        f"entirely in {cfg['language']}:\n"
        f"1. A title: dark, atmospheric, curiosity-driven, maximum 90 characters, "
        f"no clickbait phrases like 'you won't believe', no quotation marks, "
        f"format 'Figure name — evocative hook'.\n"
        f"2. A description: 120 to 180 words, matching the dark storyteller tone of the "
        f"series. First sentence must hook immediately. Describe what the listener will "
        f"experience without spoiling the ending. Mention the series name once. "
        f"No hashtags, no emojis, no bullet points, no meta commentary.\n\n"
        f"Answer in EXACTLY this format and nothing else:\n"
        f"TITLE: <the title>\n"
        f"DESCRIPTION:\n<the description>"
    )

    print(f"\n  Generiere Titel & Beschreibung ...")
    for attempt in range(1, MAX_RETRIES + 1):
        output = call_claude(prompt, cfg["model"])
        if output:
            match = re.search(r"TITLE:\s*(.+?)\s*DESCRIPTION:\s*(.+)", output, re.DOTALL)
            if match:
                title = match.group(1).strip()
                description = match.group(2).strip()
                if title and len(title) <= 120 and len(description.split()) >= 60:
                    with open(meta_file, "w", encoding="utf-8") as f:
                        f.write(f"TITEL:\n{title}\n\nBESCHREIBUNG:\n{description}\n")
                    print(f"  ✓ Titel & Beschreibung gespeichert: {os.path.basename(meta_file)}")
                    print(f"    → {title}")
                    return True
        print(f"  Versuch {attempt}/{MAX_RETRIES}: unbrauchbare Metadaten-Ausgabe.")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    print(f"  Titel & Beschreibung fehlgeschlagen — Skript ist trotzdem fertig.")
    return False


def generate_episode(ep_idx, template, data, episodes, force, cfg) -> bool:
    episode_num = ep_idx + 1
    figure = episodes[ep_idx]["figure"]
    sections = episodes[ep_idx]["sections"]
    num_sections = len(sections)
    output_file = os.path.join(SCRIPT_DIR, f"{cfg['prefix']}{episode_num}.txt")

    print(f"\n{'='*55}")
    print(f"Episode {episode_num}: {figure}")
    print(f"{'='*55}")

    if force and os.path.exists(output_file):
        os.remove(output_file)
        print("Vorhandene Datei gelöscht (--force).")

    # Bereits geschriebene Parts erkennen → Resume-Fähigkeit
    existing_parts, previous_content = read_existing_parts(output_file)
    if existing_parts and not force:
        print(f"  Gefundene Parts in Datei: {sorted(existing_parts)} — überspringe fertige Sections.")

    for sec_idx, section_title in enumerate(sections):
        section_parts = section_part_numbers(sec_idx, cfg["parts_per_section"])

        # Section überspringen wenn alle Parts bereits vorhanden
        if all(p in existing_parts for p in section_parts):
            print(f"\n  Section {sec_idx+1}/{num_sections}: \"{section_title}\" — bereits vorhanden, übersprungen ✓")
            continue

        print(f"\n  Section {sec_idx+1}/{num_sections}: \"{section_title}\"")
        print(f"  → Generiere Part {section_parts[0]} bis Part {section_parts[-1]} ...")

        prompt = build_section_prompt(
            template, data, episodes, ep_idx, sec_idx, previous_content, cfg
        )

        parts = call_claude_with_retry(prompt, section_parts, cfg)
        if parts is None:
            print(f"  Section {sec_idx+1} endgültig fehlgeschlagen. Abbruch.")
            print(f"  Tipp: Skript erneut starten — fertige Sections werden übersprungen.")
            return False

        # Sofort in Datei schreiben
        with open(output_file, "a", encoding="utf-8") as f:
            for num, text in parts:
                block = f"--- PART {num} ---\n\n{text}\n\n"
                f.write(block)
                previous_content += block
                existing_parts.add(num)

        words = sum(len(t.split()) for _, t in parts)
        print(f"  ✓ Parts {section_parts[0]}–{section_parts[-1]} gespeichert (~{words} Wörter)")

    total_words = len(previous_content.split())
    print(f"\n  Fertig: {cfg['prefix']}{episode_num}.txt (~{total_words} Wörter total)")

    record_figure(figure, data.get("series_title", ""))

    # Titel & Beschreibung sind nice-to-have — ein Fehlschlag hier lässt die
    # Episode nicht scheitern (Skript erneut starten generiert sie nach).
    generate_episode_meta(ep_idx, data, episodes, force, cfg)
    return True


def _run_episode_subprocess(ep_num: int, force: bool) -> tuple[int, bool]:
    """Führt eine einzelne Episode als separaten Prozess aus (für Parallelisierung)."""
    cmd = [sys.executable, os.path.abspath(__file__), str(ep_num)]
    if force:
        cmd.append("--force")
    result = subprocess.run(cmd, check=False)
    return ep_num, result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Podcast Script Generator — Section für Section"
    )
    parser.add_argument("episode", help="Episodennummer (1, 2, ...), 'all' oder 'check' (nur episodes.json validieren)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene Datei komplett neu generieren")
    parser.add_argument("--jobs", type=int, default=2, metavar="N",
                        help="Anzahl parallel generierter Episoden bei 'all' (Standard: 2)")
    args = parser.parse_args()

    template = load_template()
    data = load_episodes()
    validate_or_exit(data)
    warn_on_repeated_figures(data)

    if args.episode.lower() == "check":
        print("episodes.json ist gültig ✓")
        return

    episodes = data["episodes"]
    series = data.get("series_title", "?")
    cfg = build_config(data)

    print(f"Serie: \"{series}\" — {len(episodes)} Episoden")
    print(f"Format: {cfg['parts_per_section']} Parts/Section, "
          f"{cfg['min_words']}–{cfg['max_words']} Wörter/Part (Ziel {cfg['words_target']}), "
          f"Sprache: {cfg['language']}, Modell: {cfg['model']}")

    if args.episode.lower() == "all":
        import concurrent.futures
        max_workers = max(1, min(args.jobs, len(episodes)))
        print(f"\nStarte {len(episodes)} Episode(n) mit {max_workers} parallelen Job(s) ...")

        failed = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_episode_subprocess, idx + 1, args.force): idx + 1
                for idx in range(len(episodes))
            }
            for future in concurrent.futures.as_completed(futures):
                ep_num, ok = future.result()
                if not ok:
                    failed.append(ep_num)

        print(f"\nFertig: {len(episodes)-len(failed)}/{len(episodes)} generiert.")
        if failed:
            print(f"Fehlgeschlagen: Episode(n) {sorted(failed)}")
            print("batch.py wird nicht gestartet — erst alle Episoden generieren.")
        else:
            print("\nStarte batch.py ...")
            venv_python = os.path.join(SCRIPT_DIR, ".venv", "bin", "python")
            python = venv_python if os.path.exists(venv_python) else sys.executable
            subprocess.run([python, os.path.join(SCRIPT_DIR, "batch.py")], check=False)
    else:
        try:
            num = int(args.episode)
        except ValueError:
            print(f"FEHLER: '{args.episode}' ist keine gültige Zahl.")
            sys.exit(1)
        if num < 1 or num > len(episodes):
            print(f"FEHLER: Episode {num} existiert nicht (1–{len(episodes)}).")
            sys.exit(1)
        ok = generate_episode(num - 1, template, data, episodes, args.force, cfg)
        if ok:
            print(f"\nNächster Schritt: python podcast_maker.py {cfg['prefix']}{num}.txt")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
