"""Skript-Generierung via Claude CLI — Section für Section, mit Validierung
(Part-Marker, Längenbudget, im Drama-Modus zusätzlich das Sprecher-Tag-Format)
und Resume-Fähigkeit: jede fertige Section wird sofort in die Datei
geschrieben, ein abgebrochener Lauf setzt bei der ersten fehlenden fort."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from typing import Optional

from ..core import textproc
from ..core.claude_cli import parse_json_response, run_claude_process
from ..core.config import DEFAULTS
from ..core.history import record_figure
from ..core.paths import Series, template_dir
from .script_parser import ScriptFormatError, parse_drama_part

TIMEOUT_SECONDS = 300   # max. Wartezeit pro Claude-Aufruf
MAX_RETRIES     = 2     # Wiederholungsversuche bei Fehler oder schlechter Qualität — nur noch
                        # zwei, weil in der Praxis auch drei Versuche bei einer inhaltlich
                        # dünnen Szene nicht konvergieren (beobachtet: 200→176→192→191→189
                        # Einheiten bei Ziel 220) und am Ende ohnehin der Best-Effort-Fallback
                        # greift (siehe fallback_safe/badness in call_claude_with_retry) —
                        # jeder gestrichene Versuch spart einen kompletten Prompt (Template +
                        # Case-File + Beats), also den teuersten Posten des ganzen Laufs.
RETRY_DELAY     = 5     # Sekunden zwischen Versuchen
ESCALATION_FROM_ATTEMPT = 2  # ab diesem Versuch: schärferes, expliziteres Feedback — bei
                             # MAX_RETRIES=2 heißt das: der letzte Versuch bekommt die
                             # eindringlichere Formulierung, bevor der Fallback greift

WORD_COUNT_TOLERANCE = 15  # Untergrenze des Puffers um min/max — der effektive Puffer ist
                           # word_count_tolerance() (10% des Part-Minimums, mindestens dieser
                           # Wert): ein fixer 15-Einheiten-Puffer liegt bei üblichen Minima
                           # (250+) innerhalb der normalen Zählschwankung des Modells, d.h.
                           # Retries scheiterten an Rauschen statt an echten Problemen.


def word_count_tolerance(min_words: int) -> int:
    """Effektiver Puffer um das Wortbudget: 10% des Minimums, nie unter
    WORD_COUNT_TOLERANCE — relativ statt fix, damit enge section_words-
    Overrides und große Episoden-Minima denselben prozentualen Spielraum
    bekommen und eine komplette Section-Neugenerierung (voller Prompt inkl.
    Template + Case-File + Beats) nicht wegen Zähl-Rauschen anfällt."""
    return max(WORD_COUNT_TOLERANCE, min_words // 10)

_TAG_LINE_RE = re.compile(r'^\s*\[[^\]]*\]\s*$', re.MULTILINE)
_NOTE_RE = re.compile(r'^\s*\[NOTE:\s*(.+)\]\s*$', re.MULTILINE | re.IGNORECASE)
# .+ gierig: muss bis zur letzten ']' der Zeile reichen — sonst zerreißt ein
# zufälliges ']' MITTEN im Notiztext (z.B. eine Beispielklammer wie "[done]")
# den Match, siehe identische Begründung in fabrik/script_parser.py._TAG_RE.


def load_template(template_name: str, series=None) -> str:
    """Skript-Prompt laden — bevorzugt die Serien-Kopie unter references/
    (MWP: die Serie besitzt ihr eigenes, editierbares Prompt; Master-
    Änderungen unter templates/ erreichen nur NEUE Serien). Fallback aufs
    Master-Template mit Warnung, falls die Kopie fehlt."""
    template_file = os.path.join(template_dir(template_name), "PROMPT_TEMPLATE.md")
    if series is not None:
        series_copy = series.prompt_template_file()
        if os.path.exists(series_copy):
            template_file = series_copy
        else:
            print(f"⚠️  Kein references/PROMPT_TEMPLATE.md in Serie '{series.slug}' — "
                  f"nutze Master-Template templates/{template_name}/ (Workspace unvollständig?)")
    try:
        with open(template_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"FEHLER: {template_file} nicht gefunden.")
        sys.exit(1)
    marker = "--- TEMPLATE START ---"
    if marker not in content:
        print(f"FEHLER: '{marker}' nicht in {template_file} gefunden.")
        sys.exit(1)
    # rsplit: falls der Marker zusätzlich im Kommentar-Header erwähnt wird,
    # zählt nur das letzte (echte) Vorkommen
    return content.rsplit(marker, 1)[1].strip()


def count_length(text: str, mode: str) -> int:
    """Längenbudget-Zähler: Wörter (narration) bzw. sprachneutrale Einheiten
    (drama — CJK-Zeichen zählen einzeln, sonst wäre Chinesisch '3 Wörter').

    Im Drama-Modus werden reine Tag-Zeilen ([HOST], [SFX: ...], [NOTE: ...])
    vor dem Zählen entfernt — sonst zählen Sprechernamen, englische
    SFX-Beschreibungen und Vokabel-Notizen fälschlich als gesprochener
    Text und drücken das Budget künstlich an den Rand."""
    if mode == "drama":
        return textproc.count_length_units(_TAG_LINE_RE.sub('', text))
    return len(text.split())


def extract_vocab_notes(text: str) -> list[str]:
    """Sammelt alle [NOTE: ...]-Einträge aus bereits generiertem Skripttext,
    in Auftrittsreihenfolge, ohne Duplikate. Wird beim Bauen des nächsten
    Section-Prompts benutzt, um die Analysis-Section zu zwingen, wirklich
    JEDES geflaggte Vokabular abzudecken statt nur eine Teilauswahl."""
    seen = []
    for note in _NOTE_RE.findall(text):
        note = note.strip()
        if note and note not in seen:
            seen.append(note)
    return seen


def build_intro_spec(position, total, series_title, figure, prev_figure,
                     series_intro, intro_note, template="narration"):
    if position == 1:
        detail = intro_note if intro_note else series_intro
        return f"--- PART 1 --- MUST start with {detail}, before diving into {figure}."

    # Nur die NARRATOR-Templates — language_course hat sein eigenes
    # Recap-Muster über den HOST (siehe dessen intro_note-Konvention).
    if template in ("crime_drama", "soap_opera"):
        # Serien-Stilmittel "Was bisher geschah": ab Episode 2 eröffnet der
        # NARRATOR mit einem knappen Recap, BEVOR die erste Szene beginnt —
        # das Material dafür steckt in intro_note (Stand nach der Vorepisode).
        recap_basis = (f" Base the recap on this state of the story: {intro_note}"
                       if intro_note else "")
        return (
            f"--- PART 1 --- MUST open with a 'previously on {series_title}' "
            f"recap: 2-3 spoken [NARRATOR] lines summarizing where things stand "
            f"after the previous episode — concrete and character-focused, no "
            f"vague teasing — then move straight into the first scene."
            f"{recap_basis}"
        )

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


def resolve_section_cfg(cfg, episode, section_idx) -> dict:
    """Wendet episode['section_words'][section_idx] (falls gesetzt) auf eine
    Kopie von cfg an — erlaubt einzelnen Szenen ein eigenes Wortbudget statt
    des globalen format-Defaults für die ganze Episode (z.B. eine kurze
    Cliffhanger-Szene neben einer langen Dialog-Szene)."""
    overrides = episode.get("section_words")
    if not overrides or section_idx >= len(overrides) or not overrides[section_idx]:
        return cfg
    override = overrides[section_idx]
    resolved = dict(cfg)
    if "min" in override:
        resolved["min_words"] = override["min"]
    if "max" in override:
        resolved["max_words"] = override["max"]
    if "target" in override:
        resolved["words_target"] = override["target"]
    return resolved


def section_part_numbers(section_idx, parts_per_section) -> list[int]:
    """Part-Nummern einer Section (z.B. Section 0 bei 2 Parts/Section → [1, 2])."""
    first = section_idx * parts_per_section + 1
    return list(range(first, first + parts_per_section))


def build_voices_roster(voices: dict) -> str:
    """Rollen-Übersicht für den Drama-Prompt: Tag + Charakterbeschreibung."""
    lines = []
    for role, vcfg in voices.items():
        desc = vcfg.get("description") or vcfg.get("default_style") or ""
        lines.append(f"- [{role}]: {desc}".rstrip(": "))
    return "\n".join(lines)


def build_style_tag_rule(supports_style: bool) -> str:
    """Ersetzt {{STYLE_TAG_RULE}} in den Drama-Templates: nur wenn das
    konfigurierte TTS-Backend Style/Instruct rendert, wird Claude überhaupt
    gebeten, "style"-Regieanweisungen in die Sprecher-Tags zu schreiben —
    sonst wird das explizit untersagt (spart Tokens, Skript bleibt ehrlich
    darüber, was beim Vertonen tatsächlich ankommt)."""
    if supports_style:
        return ('- "style" is an optional acting instruction for the TTS voice (English, '
                'short, concrete). Use it whenever the emotional register shifts — this is '
                'a radio drama, the acting IS the storytelling.')
    return ('- This backend does NOT render acting/style instructions — do NOT include a '
            '"style" key in any tag (only [ROLE] or [ROLE | speed: ...]), even though the '
            'format example above shows one. It would be silently ignored at render time; '
            'convey emotion and register purely through word choice, punctuation, and line length.')


def build_course_spec(course: dict) -> str:
    return "\n".join(f"- {key.replace('_', ' ')}: {value}" for key, value in course.items())


def _build_single_case_block(case: dict) -> str:
    parts = []
    if case.get("solution"):
        parts.append(f"SOLUTION (author's compass — no character states this outright before the finale):\n  {case['solution']}")
    facts = case.get("objective_facts") or []
    if facts:
        parts.append("OBJECTIVE FACTS (undisputed, provable — not necessarily known to any character yet):\n" +
                     "\n".join(f"  - {f}" for f in facts))
    knowledge = case.get("character_knowledge") or {}
    if knowledge:
        know_lines = ["PER-CHARACTER KNOWLEDGE (the hard boundary — see rule below):"]
        for role, slice_ in knowledge.items():
            know_lines.append(f"  [{role}]")
            if slice_.get("knows"):
                know_lines.append("    knows: " + "; ".join(slice_["knows"]))
            if slice_.get("hides"):
                know_lines.append("    hides (conceals/lies about): " + "; ".join(slice_["hides"]))
            if slice_.get("believes_falsely"):
                know_lines.append("    wrongly believes: " + "; ".join(slice_["believes_falsely"]))
        parts.append("\n".join(know_lines))
    return "\n\n".join(parts)


def build_case_file_block(case) -> str:
    """Baut den CASE-FILE-Textblock aus episode['case'] (solution,
    objective_facts, character_knowledge pro Rolle) — die eigentliche
    Wissens-Trennung zwischen Figuren, die Widersprüche/Lügen organisch statt
    behauptet entstehen lassen soll.

    case ist entweder ein einzelnes Objekt (templates/crime_drama: EIN Fall)
    oder eine Liste solcher Objekte mit zusätzlichem 'label' (templates/
    soap_opera: mehrere parallele, unabhängig verfolgte Handlungsstränge)."""
    if not case:
        return "(no case file defined for this episode — write without an enforced knowledge split)"

    if isinstance(case, list):
        threads = []
        for thread in case:
            block = _build_single_case_block(thread)
            label = thread.get("label", "Untitled thread")
            threads.append(f"=== THREAD: {label} ===\n{block}" if block else f"=== THREAD: {label} ===\n(empty)")
        return "\n\n".join(threads) if threads else "(case file present but empty — write without an enforced knowledge split)"

    block = _build_single_case_block(case)
    return block if block else "(case file present but empty — write without an enforced knowledge split)"


def build_vocab_notes_block(notes: list[str]) -> str:
    if not notes:
        return "(none flagged yet)"
    return "\n".join(f"- {n}" for n in notes)


_BEAT_LINE_RE = re.compile(r'^\s*\d+\.\s*(.+)$', re.MULTILINE)


def build_beats_prompt(episodes, ep_idx, cfg, previous_beats_text: str) -> str:
    """Baut den Prompt für die Beat-Schicht: aus den Section-Einzeilern +
    case/character_knowledge (build_case_file_block(), unverändert
    wiederverwendet) + den Beats der VORIGEN Folge (Kontinuität) erzeugt
    Claude pro Szene 3-6 Klartext-Beats — was passiert und warum, ohne
    Dialogzeilen oder Stil. Siehe docs/beat-layer-design.md Abschnitt 3."""
    episode = episodes[ep_idx]
    sections = episode["sections"]
    sections_text = "\n".join(f"Scene {i+1}: {s}" for i, s in enumerate(sections))
    case_block = build_case_file_block(episode.get("case"))
    continuity = (
        f"Beats of the PREVIOUS episode, for continuity (do not repeat these, "
        f"build on where they leave off):\n\n{previous_beats_text}\n"
        if previous_beats_text else
        "(this is the first episode with beats — no previous-episode continuity to draw on)\n"
    )

    return (
        f"You are a story editor for a {cfg['language']} audio drama, working as "
        f"{cfg['persona']}. Your job here is NOT to write dialogue — it is to plan, "
        f"in plain language, what happens in each scene of this episode and why.\n\n"
        f"CASE FILE (the authoritative source of who knows what — the finished dialogue "
        f"must never contradict this):\n{case_block}\n\n"
        f"{continuity}\n"
        f"SCENES OF THIS EPISODE (one line each, to be expanded into beats):\n{sections_text}\n\n"
        f"For EACH scene, write 3 to 6 short, plain-language beats: what happens, who "
        f"lies or hides something and to whom, what shifts, what the audience learns that "
        f"a character does not know. NO dialogue lines, NO acting/style directions, NO "
        f"prose — just the bare logical/emotional beats, one numbered sentence each.\n\n"
        f"Output ONLY the beats, one block per scene, in this exact format:\n\n"
        f"--- SCENE 1 ---\n1. ...\n2. ...\n\n--- SCENE 2 ---\n1. ...\n\n"
        f"Write exactly {len(sections)} scene block(s), matching the scenes listed above "
        f"in order. Do not add commentary before or after."
    )


def parse_beats(output: str, expected_scenes: list[int]) -> dict[int, list[str]]:
    """Parst die Beat-Ausgabe in {Szenen-Index (1-basiert): [Beat, ...]} — analog
    zu extract_parts(), nur SCENE- statt PART-Marker und Beat-Zeilen statt
    Fließtext pro Block. Gibt nur tatsächlich gefundene Szenen zurück; der
    Aufrufer prüft Vollständigkeit gegen expected_scenes."""
    chunks = re.split(r'---\s*SCENE\s+(\d+)\s*---', output)
    scenes = {}
    for i in range(1, len(chunks), 2):
        num = int(chunks[i])
        block = chunks[i + 1] if i + 1 < len(chunks) else ""
        beats = [b.strip() for b in _BEAT_LINE_RE.findall(block) if b.strip()]
        if beats:
            scenes[num] = beats
    return {num: scenes[num] for num in expected_scenes if num in scenes}


def generate_beats(series: Series, ep_idx: int, episodes, force: bool, cfg: dict) -> Optional[dict[int, list[str]]]:
    """Generiert (oder lädt) die Beats einer Episode. EIN Claude-Call erzeugt
    die Beats aller Szenen der Folge auf einmal — Resume ist daher ein
    einfacher Existenz-Check auf der Beats-Datei (nicht das inkrementelle
    read_existing_parts-Muster, das für viele Calls über eine Datei hinweg
    gedacht ist). Nutzt den episoden-weiten cfg (nie resolve_section_cfg()'s
    Section-Kopie — es gibt an dieser Stelle noch keine Section-Schleife).

    Rückgabe: {Szenen-Index: [Beat, ...]} bei Erfolg (auch beim Laden einer
    vorhandenen Datei), oder None bei endgültigem Fehlschlag — dann wird
    KEINE Datei geschrieben, damit ein künftiger Lauf es erneut versucht
    (gleiche Disziplin wie review_episode_script)."""
    episode = episodes[ep_idx]
    episode_num = ep_idx + 1
    sections = episode["sections"]
    expected_scenes = list(range(1, len(sections) + 1))
    beats_file = series.beats_file(cfg["prefix"], episode_num)

    if os.path.exists(beats_file) and not force:
        print(f"  Beats bereits vorhanden: {os.path.basename(beats_file)} ✓")
        with open(beats_file, "r", encoding="utf-8") as f:
            return parse_beats(f.read(), expected_scenes)

    # Beats der vorigen Folge als Kontinuität — falls die Datei (noch) nicht
    # existiert (z.B. paralleler Lauf via --jobs>1, oder use_beats erst ab
    # dieser Folge aktiv), wird das nicht als Fehler behandelt, sondern als
    # "kein Kontinuitätskontext diesen Lauf" (siehe docs/beat-layer-design.md).
    previous_beats_text = ""
    if ep_idx > 0:
        prev_beats_file = series.beats_file(cfg["prefix"], ep_idx)
        if os.path.exists(prev_beats_file):
            with open(prev_beats_file, "r", encoding="utf-8") as f:
                previous_beats_text = f.read()

    print(f"\n  Beats generieren ({len(sections)} Szene(n)) ...")
    prompt = build_beats_prompt(episodes, ep_idx, cfg, previous_beats_text)

    for attempt in range(1, MAX_RETRIES + 1):
        output = call_claude(prompt, cfg["model"])
        if output:
            parsed = parse_beats(output, expected_scenes)
            if len(parsed) == len(expected_scenes):
                with open(beats_file, "w", encoding="utf-8") as f:
                    f.write(output.strip() + "\n")
                print(f"  ✓ Beats gespeichert: {os.path.basename(beats_file)}")
                return parsed
            print(f"  Versuch {attempt}/{MAX_RETRIES}: nur {len(parsed)}/{len(expected_scenes)} "
                  f"Szenen erkannt.")
        else:
            print(f"  Versuch {attempt}/{MAX_RETRIES}: keine Ausgabe.")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    print(f"  ⚠️  Beat-Generierung fehlgeschlagen — keine {os.path.basename(beats_file)} "
          f"geschrieben, Dialog-Schreiber nutzt diesen Lauf den bisherigen Vorschnitt-Kontext.")
    return None


def build_beats_context_block(beats: dict[int, list[str]], section_idx: int) -> str:
    """Baut den Beats-Kontextblock für den Dialog-Prompt: alle Szenen-Beats
    der Folge als Überblick, die aktuelle Szene markiert/hervorgehoben —
    ersetzt den bisherigen Vorschnitt-Prosa-Kontext, wenn Beats verfügbar
    sind (siehe docs/beat-layer-design.md, Abschnitt 'Nachbar-Kontext')."""
    lines = ["Beats for this episode (the scene plan — dramatize the CURRENT scene's beats "
              "into full dialogue; the other scenes' beats are shown only for continuity, "
              "do not write them now):"]
    for num in sorted(beats.keys()):
        marker = "  <-- WRITE THIS SCENE NOW" if num == section_idx + 1 else ""
        lines.append(f"\nScene {num}{marker}:")
        for beat in beats[num]:
            lines.append(f"  - {beat}")
    return "\n".join(lines)


def build_section_prompt(template, data, episodes, ep_idx, section_idx,
                          previous_content, cfg, beats: Optional[dict] = None):
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
                                   prev_figure, series_intro, intro_note,
                                   template=cfg.get("template", "narration"))
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
        # Drama-/Sprachkurs-Platzhalter — in Narration-Templates einfach nicht vorhanden
        "{{VOICES_ROSTER}}": build_voices_roster(cfg.get("voices", {})),
        "{{STYLE_TAG_RULE}}": build_style_tag_rule(cfg.get("supports_style", True)),
        "{{COURSE_SPEC}}": build_course_spec(cfg.get("course", {})),
        # Aus dem GESAMTEN bisherigen Skript extrahiert (nicht nur der
        # getrimmten Kontinuitäts-Kontext), damit Vokabular aus früheren
        # Sections nicht verloren geht, sobald der Kontext-Trim greift.
        "{{VOCAB_NOTES}}": build_vocab_notes_block(extract_vocab_notes(previous_content)),
        # Nur templates/crime_drama: pro Episode definierte Wissens-Trennung
        # zwischen den Figuren (episodes[n].case) — siehe build_case_file_block().
        "{{CASE_FILE}}": build_case_file_block(episode.get("case")),
    }

    prompt = template
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)

    if beats and (section_idx + 1) in beats:
        # Beat-Schicht aktiv und diese Szene hat Beats: alle Szenen-Beats der
        # Folge als Überblick + eigene Szene hervorgehoben, statt der bloßen
        # Vorschnitt-Prosa — schließt die Kontinuitätslücke (der Schreiber
        # sieht die ganze Folge, nicht nur die letzte Section).
        prompt += f"\n\n{build_beats_context_block(beats, section_idx)}\n"
    elif previous_content:
        # Fallback (use_beats aus, Beat-Generierung diesen Lauf fehlgeschlagen,
        # oder diese Szene fehlt im Beats-Dict): unverändertes Verhalten — nur
        # die letzte Section (parts_per_section Parts) als Kontext, Claude
        # braucht Kontinuität, nicht die volle Episoden-Historie.
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
        f"This section consists of exactly {cfg['parts_per_section']} part(s):\n"
        f"{markers}\n\n"
        f"Start immediately with --- PART {parts[0]} --- and end after --- PART {parts[-1]} ---. "
        f"Do not write any other parts. Do not add summaries or comments."
    )

    # Sprechstil der Section (aus episodes.json) in den Schreib-Prompt reichen,
    # damit Rhythmus und Intensität des Textes zur späteren Vertonung passen.
    # Nur Narration — im Drama-Modus stehen die Styles pro Zeile im Skript.
    # Nur wenn das konfigurierte TTS-Backend Style/Instruct überhaupt rendert
    # (cfg["supports_style"]) — sonst würde Claude Aufwand in Regie-
    # Anweisungen stecken, die beim Vertonen ohnehin verworfen werden.
    if cfg["mode"] == "narration" and cfg.get("supports_style", True):
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
            stdin=subprocess.DEVNULL,
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


def validate_parts(parts, expected_parts, cfg) -> tuple[bool, str, list[str], bool, int]:
    """Prüft ob alle erwarteten Parts vorhanden und im Längenbudget liegen;
    im Drama-Modus zusätzlich, ob jeder Part sauber parsebar ist (nur bekannte
    Sprecher, korrekte Tags). Toleriert eine Budget-Abweichung von
    word_count_tolerance() an den Rändern; ÜBERLÄNGE ist grundsätzlich kein
    Fehler mehr (nur eine Warnung) — ein zu langer Part macht die Episode beim
    Vertonen lediglich ein paar Sekunden länger, ein Retry dafür kostet einen
    kompletten Prompt (Template + Case-File + Beats) und ist es nie wert.

    Rückgabe: (ok, deutsche Konsolen-Kurzmeldung, englische Fehlerbilanz pro
    Part, fallback_safe, badness).

    fallback_safe ist True, wenn alle Parts vorhanden UND (im Drama-Modus)
    sauber parsebar sind — nur dann darf dieser Versuch, falls am Ende alle
    Retries das Wortbudget verfehlen, als Best-Effort-Fallback dienen (siehe
    call_claude_with_retry). Fehlende Parts oder ein FORMAT ERROR würden beim
    Vertonen crashen oder Inhalt verschlucken und sind NIE fallback-sicher.

    badness ist die Summe aller Wortbudget-Abweichungen (0 bei einem sauberen
    Pass) — dient dazu, unter mehreren unsauberen Versuchen den am wenigsten
    schlechten als Fallback auszuwählen.

    Die Fehlerbilanz (detail) wird bei einem Retry wörtlich ins
    Modell-Feedback übernommen — nur so weiß Claude, WELCHER Part WORAN
    gescheitert ist, statt beim nächsten Versuch erneut blind zu raten."""
    min_words, max_words = cfg["min_words"], cfg["max_words"]
    tolerance = word_count_tolerance(min_words)
    found = {num for num, _ in parts}
    missing = [num for num in expected_parts if num not in found]
    if missing:
        console = f"Part(s) {missing} fehlen komplett in der Ausgabe"
        detail = [f"Part {num}: MISSING from your output" for num in missing]
        return False, console, detail, False, 0

    ok = True
    console = ""
    detail = []
    fallback_safe = True
    badness = 0
    for num, text in parts:
        words = count_length(text, cfg["mode"])
        if words < min_words - tolerance:
            ok = False
            shortfall = min_words - words
            badness += shortfall
            console = console or f"Part {num} zu kurz ({words} Einheiten, minimum {min_words})"
            detail.append(f"Part {num}: {words} length units — TOO SHORT by {shortfall} units "
                          f"(has {words}, needs at least {min_words}, ideally {cfg['words_target']})")
        elif words > max_words + tolerance:
            # Überlänge kostet beim Hören nichts — akzeptieren statt einen
            # ganzen Regenerierungs-Prompt dafür zu verbrennen.
            print(f"  ⚠️  Part {num} überlang ({words} Einheiten, maximum {max_words}) — "
                  f"akzeptiert, kein Retry.")
            detail.append(f"Part {num}: {words} length units — over budget, accepted")
        else:
            detail.append(f"Part {num}: {words} length units — OK")

        if cfg["mode"] == "drama":
            try:
                parse_drama_part(text, voices=cfg["voices"], part_label=f"PART {num}")
            except ScriptFormatError as e:
                ok = False
                fallback_safe = False
                console = console or f"Part {num} hat ein Formatproblem: {e}"
                detail.append(f"Part {num}: FORMAT ERROR — {e}")

    return ok, console, detail, fallback_safe, badness


def call_claude_with_retry(prompt, expected_parts, cfg) -> Optional[list[tuple[int, str]]]:
    """Ruft Claude auf und wiederholt bei Fehler oder defekter Ausgabe.

    Manche Szenen sind inhaltlich einfach zu dünn, um verlässlich über ein
    Wortminimum zu kommen — auch mit mehreren Versuchen und eskalierendem
    Feedback (siehe Konsolen-Log: 200→176→192→191→189 Einheiten bei Ziel 220,
    keine Konvergenz). Statt die ganze Section nach MAX_RETRIES Fehlversuchen
    wegzuwerfen, wird der am wenigsten schlechte fallback-sichere Versuch
    (kein FORMAT ERROR, keine fehlenden Parts — siehe validate_parts)
    übernommen und deutlich als Kompromiss geloggt, statt die Episode
    komplett zu blockieren.

    Früher Fallback: verfehlt ein fallback-sicherer Versuch das Wortminimum
    nur knapp (Gesamtabweichung innerhalb eines weiteren Toleranzbandes),
    wird er SOFORT übernommen statt einen weiteren vollen Prompt (Template +
    Case-File + Beats) zu verbrennen — der Fallback hätte ihn nach allen
    Versuchen ohnehin genommen, ein Retry für ein paar fehlende Wörter ist
    das teuerste Sparpotenzial des ganzen Laufs."""
    feedback = ""
    best = None  # (badness, parts) — bester fallback-sicherer Versuch bisher
    early_accept = 2 * word_count_tolerance(cfg["min_words"])
    for attempt in range(1, MAX_RETRIES + 1):
        prefix = f"  Versuch {attempt}/{MAX_RETRIES}"

        output = call_claude(prompt + feedback, cfg["model"])
        if not output:
            print(f"{prefix}: Keine Ausgabe erhalten.")
        else:
            parts = extract_parts(output, expected_parts)
            ok, console_reason, detail, fallback_safe, badness = validate_parts(parts, expected_parts, cfg)
            if ok:
                return parts
            if fallback_safe and badness <= early_accept:
                print(f"{prefix}: Wortbudget knapp verfehlt (Abweichung {badness} Einheiten) — "
                      f"sofort übernommen statt neu zu generieren.")
                return parts
            if fallback_safe and (best is None or badness < best[0]):
                best = (badness, parts)
            print(f"{prefix}: Defekte Ausgabe — {console_reason}")
            detail_text = "\n".join(detail)
            escalation = ""
            if attempt >= ESCALATION_FROM_ATTEMPT:
                escalation = (
                    f"\n\nThis is attempt {attempt} and the length is STILL wrong — previous "
                    f"attempts did not fix it. Do not write a similarly-short draft again. "
                    f"Concretely add at least one more full beat to the flagged part(s): another "
                    f"line of dialogue exchange, a physical action, or a sensory/environmental "
                    f"detail — not just longer sentences. Count matters more than elegance here."
                )
            feedback = (
                f"\n\nIMPORTANT: Your previous attempt was rejected. Validation result per part:\n"
                f"{detail_text}\n\n"
                f"Every part MUST be between {cfg['min_words']} and {cfg['max_words']} length "
                f"units (target {cfg['words_target']}; one Chinese character or one Latin word "
                f"= one unit). Rewrite the full section, keeping the parts marked OK roughly "
                f"as they were and fixing only the flagged parts — expand with scene-setting "
                f"or sensory detail, never filler, and fix every FORMAT ERROR exactly as described."
                f"{escalation}"
            )

        if attempt < MAX_RETRIES:
            print(f"  Warte {RETRY_DELAY}s vor nächstem Versuch ...")
            time.sleep(RETRY_DELAY)

    if best is not None:
        badness, parts = best
        print(f"  ⚠️  Alle {MAX_RETRIES} Versuche verfehlten das Wortbudget — übernehme den am "
              f"wenigsten schlechten Versuch (Gesamtabweichung: {badness} Einheiten) statt die "
              f"Section komplett abzubrechen. Bei Bedarf manuell in der Skriptdatei nachbessern.")
        return parts

    print(f"  Alle {MAX_RETRIES} Versuche fehlgeschlagen.")
    return None


def read_existing_parts(output_file) -> tuple[set, str]:
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


def summarize_source_episode(text: str, persona: str, language: str, model: str) -> Optional[tuple[str, str]]:
    """Fasst bereits fertigen Quelltext (Story-Import, siehe import_story.py)
    zu einem episodes.json-tauglichen (figure, theme) zusammen — reine
    Metadaten-Extraktion, KEINE Plot-Erfindung: der Prompt verbietet
    explizit, Inhalte hinzuzudichten, die nicht im Text stehen."""
    excerpt = text if len(text) <= 6000 else text[:3000] + "\n\n[...]\n\n" + text[-3000:]
    prompt = (
        f"You are {persona}, preparing an existing, already-finished piece of "
        f"writing for a podcast series. Read the excerpt below and produce ONLY "
        f"metadata about it — do NOT invent plot, characters, or events beyond "
        f"what is in the text.\n\n"
        f"EXCERPT (may be truncated in the middle; do not assume anything about "
        f"the missing part):\n---\n{excerpt}\n---\n\n"
        f"Answer in {language}, in EXACTLY this format and nothing else:\n"
        f"TITLE: <a short, spoiler-free episode title, max 90 characters, no quotation marks>\n"
        f"THEME: <one rich sentence summarizing what this excerpt covers, spoiler-free>"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        output = call_claude(prompt, model)
        if output:
            match = re.search(r"TITLE:\s*(.+?)\s*THEME:\s*(.+)", output, re.DOTALL)
            if match:
                title = match.group(1).strip()
                theme = match.group(2).strip()
                if title and theme:
                    return title, theme
        print(f"  Versuch {attempt}/{MAX_RETRIES}: unbrauchbare Metadaten-Ausgabe.")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    return None


def generate_episode_meta(series: Series, ep_idx, data, episodes, force, cfg) -> bool:
    """Erzeugt Titel + Beschreibung für die Episode (z.B. für den Video-Upload)
    und schreibt sie nach scripts/<prefix>N_META.txt."""
    episode_num = ep_idx + 1
    episode = episodes[ep_idx]
    meta_file = series.meta_file(cfg["prefix"], episode_num)

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
        f"1. A title: atmospheric, curiosity-driven, maximum 90 characters, "
        f"no clickbait phrases like 'you won't believe', no quotation marks, "
        f"format 'Figure name — evocative hook'.\n"
        f"2. A description: 120 to 180 words, matching the tone of the "
        f"series. First sentence must hook immediately. Describe what the listener will "
        f"experience without spoiling the ending. Mention the series name once. "
        f"No hashtags, no emojis, no bullet points, no meta commentary.\n\n"
        f"Answer in EXACTLY this format and nothing else:\n"
        f"TITLE: <the title>\n"
        f"DESCRIPTION:\n<the description>"
    )

    print(f"\n  Generiere Titel & Beschreibung ...")
    for attempt in range(1, MAX_RETRIES + 1):
        # Reine Metadaten-Extraktion — läuft auf dem leichten Modell,
        # das kreative Schreiben bleibt auf generation.model.
        output = call_claude(prompt, cfg.get("light_model", cfg["model"]))
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


REVIEW_TIMEOUT_SECONDS = 300


def compute_review_timeout(script_text: str) -> int:
    """Skaliert das Review-Timeout mit der Skriptlänge — eine ~2000-Einheiten-
    Episode kann beim reinen Lesen+Bewerten schon über 280s brauchen (in der
    Praxis beobachtet), ein fixes 300s-Timeout ist da zu knapp. Grobe Formel
    analog zu create_series.py::compute_timeout, hier auf Zeichenlänge des
    fertigen Skripts statt Episodenzahl."""
    return min(1200, max(REVIEW_TIMEOUT_SECONDS, len(script_text) // 20))

EPISODE_REVIEW_PROMPT = """You are a continuity editor reviewing a FINISHED, fully-written radio
drama script for internal consistency — NOT for prose quality, pacing, or style.

This is episode {position} of {total}. Its theme: {theme}

CASE FILE this episode was supposed to follow (the authoritative source of who knows what —
NOT what the characters actually said, just the plan):
{case_block}

The script below was written SECTION BY SECTION, each section seeing only the immediately
preceding section as context (never the whole episode at once) — so a character can drift
outside their knowledge slice without anyone "deciding" to break the rule. Check ONLY these
two things in the ACTUAL SCRIPT TEXT (not the case file above):

1. KNOWLEDGE VIOLATIONS: does any character say, imply, or visibly act on something outside
   their own knowledge slice for a thread they're involved in? A character who "hides"
   something may still act guarded, evasive, or lie convincingly about it — that is CORRECT,
   not a violation. Only flag an outright reveal, or an action/reaction that requires
   knowledge the case file says this character does not have.
2. PREMATURE SOLUTION: does any line state or unambiguously reveal a thread's "solution"
   before it is meant to surface — unless this episode is explicitly the one where that
   thread resolves?

Respond ONLY with valid JSON, no markdown fences, exactly:
{{"issues": [{{"part": <integer — the PART number the problem is IN, from its "--- PART N ---" "
              "marker>, "problem": "one short, specific sentence describing the problem, "
              "quoting or paraphrasing the offending line so it can be found and fixed"}}]}}

Do not invent nitpicks — only report a problem a careful producer would actually flag on a
read-through. An empty list is a perfectly good answer.

SCRIPT TEXT:
{script_text}
"""


def review_episode_script(episode: dict, position: int, total: int, script_text: str, model: str):
    """Nachträglicher Konsistenz-Check EINER fertigen Episode gegen ihr eigenes
    case-File: prüft im tatsächlich geschriebenen Skripttext (nicht nur im Plan),
    ob eine Figur etwas außerhalb ihres Wissens-Slices verrät oder eine
    Thread-'solution' zu früh durchsickert.

    Grund: build_section_prompt() gibt jeder Section nur die UNMITTELBAR
    vorherige Section als Kontext mit, nie die ganze Episode auf einmal (siehe
    dortiger Kommentar) — ein sauberes case-File verhindert also nicht, dass
    sowas beim section-weisen Schreiben trotzdem passiert. Nur für Episoden mit
    'case' relevant (crime_drama/soap_opera); Episoden ohne case (narration/
    language_course) haben gar keine Wissens-Trennung, die verletzt werden
    könnte.

    Rückgabe: Liste von {"part": int, "problem": str} bei einem erfolgreichen
    Review (leere Liste = tatsächlich sauber), oder None wenn der Review-Lauf
    selbst fehlgeschlagen ist (Timeout, API-Fehler, unauswertbare Antwort) —
    diese Unterscheidung ist wichtig: [] und None sahen hier vorher beide wie
    'keine Auffälligkeiten' aus, obwohl None eigentlich heißt 'wir wissen es
    nicht', nicht 'alles sauber'. Ein Claude-Fehler hier lässt die fertige
    Episode nicht scheitern (das ist reine Nachträgliche QA), aber der
    Aufrufer muss None von einem echten leeren Befund unterscheiden können."""
    case = episode.get("case")
    if not case:
        return []

    prompt = EPISODE_REVIEW_PROMPT.format(
        position=position, total=total, theme=episode.get("theme", ""),
        case_block=build_case_file_block(case), script_text=script_text,
    )
    timeout = compute_review_timeout(script_text)
    argv = ["claude", "-p", prompt, "--output-format", "text", "--model", model, "--tools", ""]
    try:
        result = run_claude_process(argv, timeout, "Episoden-Review")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"  ⚠️  Episoden-Review fehlgeschlagen (Timeout nach {timeout}s).")
        return None
    if result.returncode != 0:
        print("  ⚠️  Episoden-Review fehlgeschlagen (Claude-Aufruf-Fehler).")
        return None
    parsed = parse_json_response(result.stdout.strip())
    if not isinstance(parsed, dict) or not isinstance(parsed.get("issues"), list):
        print("  ⚠️  Episoden-Review fehlgeschlagen (Antwort nicht auswertbar).")
        return None
    issues = []
    for i in parsed["issues"]:
        if isinstance(i, dict) and isinstance(i.get("part"), int) and i.get("problem"):
            issues.append({"part": i["part"], "problem": str(i["problem"])})
        else:
            # Altes/abweichendes Format (z.B. reiner String) — ohne Part-Nummer
            # nicht gezielt reparierbar, aber immer noch eine gültige Warnung.
            issues.append({"part": None, "problem": str(i)})
    return issues


BEATS_REVIEW_TIMEOUT_SECONDS = 120


def compute_beats_review_timeout(beats_text: str) -> int:
    """Wie compute_review_timeout(), aber für die kurze Beats-Textmenge statt
    fertiger Prosa — deutlich kleinerer Floor/Cap, da hier nur ein paar Dutzend
    Beat-Zeilen statt hunderter Wörter Prosa gelesen/bewertet werden."""
    return min(600, max(BEATS_REVIEW_TIMEOUT_SECONDS, len(beats_text) // 20))


BEATS_REVIEW_PROMPT = """You are a continuity editor reviewing a PRE-PROSE BEAT SHEET for a radio
drama episode — plain-language scene beats, not finished dialogue. Check ONLY whether the
PLANNED beats themselves violate the case file below, before any dialogue gets written from them.

This is episode {position} of {total}. Its theme: {theme}

CASE FILE this episode is supposed to follow (the authoritative source of who knows what):
{case_block}

The beats below were generated in ONE call that saw the whole episode at once, but still check
for these two things in the ACTUAL BEATS TEXT (not the case file above):

1. KNOWLEDGE VIOLATIONS: does any beat have a character reveal, act on, or openly state
   something outside their own knowledge slice for a thread they're involved in? A character
   who "hides" something may still act guarded, evasive, or lie about it — that is CORRECT, not
   a violation. Only flag a beat that has a character outright reveal something, or react in a
   way that requires knowledge the case file says they don't have.
2. PREMATURE SOLUTION: does any beat state or unambiguously reveal a thread's "solution" before
   it is meant to surface — unless this episode is explicitly the one where that thread resolves?

Respond ONLY with valid JSON, no markdown fences, exactly:
{{"issues": [{{"scene": <integer — the SCENE number the problem is IN, from its "--- SCENE N ---" "
              "marker>, "problem": "one short, specific sentence describing the problem, "
              "quoting or paraphrasing the offending beat so it can be found and fixed"}}]}}

Do not invent nitpicks — only report a problem a careful producer would actually flag on a
read-through. An empty list is a perfectly good answer.

BEATS TEXT:
{beats_text}
"""


def review_episode_beats(episode: dict, position: int, total: int, beats_text: str, model: str):
    """Wie review_episode_script(), aber auf der kurzen Beats-Textmenge statt
    der fertigen Prosa — Logikfehler (Wissens-Verstoß, Spoiler-Leak) fliegen so
    VOR dem teuren Dialog-Schreiben auf statt erst danach (siehe
    docs/beat-layer-design.md, 'Der doppelte Gewinn'). Gleiche None-vs-[]-
    Disziplin wie dort: None = Review-Lauf selbst fehlgeschlagen (Timeout/API-
    Fehler/unauswertbar), [] = tatsächlich sauber. Warn-only, kein Auto-Repair
    (das wäre unangefragter Scope für V1)."""
    case = episode.get("case")
    if not case:
        return []

    prompt = BEATS_REVIEW_PROMPT.format(
        position=position, total=total, theme=episode.get("theme", ""),
        case_block=build_case_file_block(case), beats_text=beats_text,
    )
    timeout = compute_beats_review_timeout(beats_text)
    argv = ["claude", "-p", prompt, "--output-format", "text", "--model", model, "--tools", ""]
    try:
        result = run_claude_process(argv, timeout, "Beats-Review")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"  ⚠️  Beats-Review fehlgeschlagen (Timeout nach {timeout}s).")
        return None
    if result.returncode != 0:
        print("  ⚠️  Beats-Review fehlgeschlagen (Claude-Aufruf-Fehler).")
        return None
    parsed = parse_json_response(result.stdout.strip())
    if not isinstance(parsed, dict) or not isinstance(parsed.get("issues"), list):
        print("  ⚠️  Beats-Review fehlgeschlagen (Antwort nicht auswertbar).")
        return None
    issues = []
    for i in parsed["issues"]:
        if isinstance(i, dict) and isinstance(i.get("scene"), int) and i.get("problem"):
            issues.append({"scene": i["scene"], "problem": str(i["problem"])})
        else:
            issues.append({"scene": None, "problem": str(i)})
    return issues


def extract_part_text(script_text: str, part_num: int) -> Optional[str]:
    match = re.search(
        rf'--- PART {part_num} ---\n\n(.*?)(?=--- PART \d+ ---|\Z)', script_text, re.DOTALL
    )
    return match.group(1).strip() if match else None


def replace_part_in_script(output_file: str, part_num: int, new_text: str) -> bool:
    """Ersetzt genau einen Part in der Skriptdatei durch neuen Text — per
    Ersetzungs-FUNKTION statt -String, damit Backslashes/Gruppen-Referenzen
    im (von Claude erzeugten) new_text nicht versehentlich als Regex-
    Rückverweise interpretiert werden."""
    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(rf'--- PART {part_num} ---\n\n.*?(?=--- PART \d+ ---|\Z)', re.DOTALL)
    new_block = f'--- PART {part_num} ---\n\n{new_text.strip()}\n\n'
    new_content, n = pattern.subn(lambda _m: new_block, content, count=1)
    if n == 0:
        return False
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


REPAIR_PROMPT = """You are revising ONE part of an already-finished radio drama script to fix a
specific continuity problem a reviewer flagged. Nothing else about the episode changes — same
characters, same scene, same events — only the flagged problem gets fixed.

CASE FILE (authoritative source of who knows what):
{case_block}

FLAGGED PROBLEM IN PART {part_num}:
{problem}

CURRENT TEXT OF PART {part_num} — rewrite this, fixing ONLY the flagged problem. Keep
everything else as close to the original as possible: which characters are present, the scene
setting, the tone, the overall length, every other line of dialogue:
{current_text}

Output ONLY the corrected part, starting with its marker on its own line:
--- PART {part_num} ---
Do not add any other parts, commentary, or explanation before or after it.
"""


def repair_part(episode: dict, part_num: int, problem: str, cfg: dict, script_text: str) -> Optional[str]:
    """Schreibt EINEN Part gezielt neu, um einen vom Episoden-Review gemeldeten
    Wissens-Verstoß/Spoiler-Leak zu beheben — läuft durch dieselbe Validierung
    (Wortbudget, Format, Retry, Best-Effort-Fallback) wie call_claude_with_retry
    bei der Erstgenerierung. Gibt den neuen Text zurück, oder None bei
    endgültigem Fehlschlag (Part bleibt in dem Fall unverändert)."""
    current_text = extract_part_text(script_text, part_num)
    if current_text is None:
        print(f"    ⚠️  Part {part_num} nicht im Skript gefunden — Reparatur übersprungen.")
        return None

    section_idx = (part_num - 1) // cfg["parts_per_section"]
    section_cfg = resolve_section_cfg(cfg, episode, section_idx)

    prompt = REPAIR_PROMPT.format(
        case_block=build_case_file_block(episode.get("case")),
        part_num=part_num, problem=problem, current_text=current_text,
    )
    result = call_claude_with_retry(prompt, [part_num], section_cfg)
    return result[0][1] if result else None


def apply_episode_fixes(series: Series, ep_idx: int, episode: dict, cfg: dict, issues: list) -> int:
    """Repariert jeden vom Review gemeldeten Part (mit bekannter Part-Nummer)
    einzeln und schreibt ihn direkt in die Skriptdatei zurück. Gibt die
    Anzahl erfolgreich reparierter Parts zurück."""
    output_file = series.script_file(cfg["prefix"], ep_idx + 1)
    fixed = 0
    for issue in issues:
        part_num = issue.get("part")
        problem = issue.get("problem", "")
        if part_num is None:
            print(f"    ⚠️  Hinweis ohne Part-Nummer, nicht automatisch reparierbar: {problem[:80]}")
            continue
        print(f"    🔧 Repariere Part {part_num}: {problem[:80]}")
        with open(output_file, "r", encoding="utf-8") as f:
            script_text = f.read()
        new_text = repair_part(episode, part_num, problem, cfg, script_text)
        if new_text and replace_part_in_script(output_file, part_num, new_text):
            fixed += 1
            print(f"    ✓ Part {part_num} repariert.")
        else:
            print(f"    ⚠️  Reparatur von Part {part_num} fehlgeschlagen — Part bleibt unverändert.")
    return fixed


def generate_episode(series: Series, ep_idx, template, data, episodes, force, cfg,
                     skip_review: bool = False, fix_review: bool = False) -> bool:
    episode_num = ep_idx + 1
    figure = episodes[ep_idx]["figure"]
    sections = episodes[ep_idx]["sections"]
    num_sections = len(sections)
    output_file = series.script_file(cfg["prefix"], episode_num)
    series.ensure_dirs()

    print(f"\n{'='*55}")
    print(f"Episode {episode_num}: {figure}")
    print(f"{'='*55}")

    if force and os.path.exists(output_file):
        os.remove(output_file)
        print("Vorhandene Datei gelöscht (--force).")

    use_beats = cfg.get("use_beats") and episodes[ep_idx].get("case")
    if use_beats and force:
        for stale_file in (series.beats_file(cfg["prefix"], episode_num),
                           series.beats_review_file(cfg["prefix"], episode_num)):
            if os.path.exists(stale_file):
                os.remove(stale_file)

    # Beat-Schicht: EIN Call/Folge erzeugt Klartext-Beats aller Szenen vorab —
    # nur für case-basierte Templates (crime_drama/soap_opera) und nur wenn
    # generation.use_beats aktiv ist. Ein Fehlschlag hier ist NICHT fatal:
    # beats bleibt None, build_section_prompt() fällt dann auf den bisherigen
    # Vorschnitt-Kontext zurück (siehe docs/beat-layer-design.md).
    beats = generate_beats(series, ep_idx, episodes, force, cfg) if use_beats else None

    # LLM-basierte Beat-Prüfung: Wissens-Verstöße/Spoiler-Leaks auf den kurzen
    # Beats statt teurer Prosa (siehe review_episode_beats()). Warn-only, kein
    # Auto-Repair — nur wenn Beats diesen Lauf tatsächlich vorliegen.
    if use_beats and beats:
        beats_review_file = series.beats_review_file(cfg["prefix"], episode_num)
        if os.path.exists(beats_review_file) and not force:
            print(f"  Beats-Review bereits vorhanden: {os.path.basename(beats_review_file)} ✓")
        else:
            print(f"\n  Beats-Review (Wissens-Verstöße/Spoiler-Leaks in den Beats) ...")
            beats_file = series.beats_file(cfg["prefix"], episode_num)
            with open(beats_file, "r", encoding="utf-8") as f:
                beats_text = f.read()
            beats_issues = review_episode_beats(episodes[ep_idx], episode_num, len(episodes),
                                                beats_text, cfg.get("light_model", cfg["model"]))
            if beats_issues is None:
                # Review-Lauf selbst fehlgeschlagen — KEINE Datei schreiben, damit ein
                # künftiger Lauf es erneut versucht (gleiche Disziplin wie REVIEW.txt).
                print(f"  ⚠️  Beats-Review konnte nicht durchgeführt werden — keine "
                      f"{os.path.basename(beats_review_file)} geschrieben, ein erneuter Lauf "
                      f"versucht es wieder.")
            else:
                with open(beats_review_file, "w", encoding="utf-8") as f:
                    if beats_issues:
                        lines = [f"Scene {i['scene']}: {i['problem']}" if i.get("scene") is not None
                                 else i["problem"] for i in beats_issues]
                        f.write(f"{len(beats_issues)} Hinweis(e):\n\n" +
                               "\n".join(f"- {l}" for l in lines) + "\n")
                    else:
                        f.write("Keine Auffälligkeiten.\n")
                if beats_issues:
                    print(f"  ⚠️  Beats-Review: {len(beats_issues)} Hinweis(e) — Beats bleiben "
                          f"trotzdem unverändert (kein Auto-Repair), Details in "
                          f"{os.path.basename(beats_review_file)}:")
                    for i in beats_issues:
                        label = f"Scene {i['scene']}: " if i.get("scene") is not None else ""
                        print(f"    - {label}{i['problem']}")
                else:
                    print(f"  ✅  Beats-Review: keine Auffälligkeiten.")

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

        section_cfg = resolve_section_cfg(cfg, episodes[ep_idx], sec_idx)

        print(f"\n  Section {sec_idx+1}/{num_sections}: \"{section_title}\"")
        print(f"  → Generiere Part {section_parts[0]} bis Part {section_parts[-1]} "
              f"({section_cfg['min_words']}-{section_cfg['max_words']} Einheiten/Part) ...")

        prompt = build_section_prompt(
            template, data, episodes, ep_idx, sec_idx, previous_content, section_cfg,
            beats=beats,
        )

        parts = call_claude_with_retry(prompt, section_parts, section_cfg)
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

        words = sum(count_length(t, cfg["mode"]) for _, t in parts)
        print(f"  ✓ Parts {section_parts[0]}–{section_parts[-1]} gespeichert (~{words} Einheiten)")

    total_words = count_length(previous_content, cfg["mode"])
    print(f"\n  Fertig: {os.path.basename(output_file)} (~{total_words} Einheiten total)")

    record_figure(figure, data.get("series_title", ""))

    # Titel & Beschreibung sind nice-to-have — ein Fehlschlag hier lässt die
    # Episode nicht scheitern (Skript erneut starten generiert sie nach).
    generate_episode_meta(series, ep_idx, data, episodes, force, cfg)

    # Episoden-Review: nur für Episoden mit 'case' (crime_drama/soap_opera) —
    # ohne case gibt es keine Wissens-Trennung, die verletzt werden könnte.
    # Läuft auf dem FERTIGEN Skripttext (previous_content enthält alle Parts
    # dieser Episode), nicht blockierend, ein Fehlschlag lässt die Episode
    # nicht scheitern — reine QA nach dem Schreiben.
    if not skip_review and episodes[ep_idx].get("case"):
        review_file = series.review_file(cfg["prefix"], episode_num)
        if os.path.exists(review_file) and not force and not fix_review:
            print(f"  Episoden-Review bereits vorhanden: {os.path.basename(review_file)} ✓")
        else:
            print(f"\n  Episoden-Review (Wissens-Verstöße/Spoiler-Leaks im fertigen Skript) ...")
            issues = review_episode_script(episodes[ep_idx], episode_num, len(episodes),
                                           previous_content, cfg.get("light_model", cfg["model"]))

            if issues and fix_review:
                fixable = [i for i in issues if i.get("part") is not None]
                print(f"  🔧 {len(issues)} Hinweis(e) ({len(fixable)} automatisch reparierbar) — "
                      f"repariere betroffene Parts ...")
                fixed = apply_episode_fixes(series, ep_idx, episodes[ep_idx], cfg, issues)
                print(f"  {fixed}/{len(fixable)} Part(s) repariert — Review erneut, um den Fix zu bestätigen ...")
                with open(output_file, "r", encoding="utf-8") as f:
                    updated_text = f.read()
                reviewed_again = review_episode_script(episodes[ep_idx], episode_num, len(episodes),
                                                       updated_text, cfg.get("light_model", cfg["model"]))
                if reviewed_again is not None:
                    issues = reviewed_again
                else:
                    print(f"  ⚠️  Bestätigungs-Review nach der Reparatur fehlgeschlagen — die "
                          f"ursprünglichen Befunde bleiben als offen protokolliert (die betroffenen "
                          f"Parts wurden aber schon repariert, ggf. jetzt schon behoben).")

            if issues is None:
                # Review-Lauf selbst fehlgeschlagen (Timeout/API-Fehler/unauswertbar) — NICHT als
                # "keine Auffälligkeiten" verbuchen und keine REVIEW.txt schreiben, sonst kehrt ein
                # künftiger Lauf (review_file existiert ja "erfolgreich") nie wieder zurück, um es
                # erneut zu versuchen.
                print(f"  ⚠️  Episoden-Review konnte nicht durchgeführt werden — keine REVIEW.txt "
                      f"geschrieben, ein erneuter Lauf versucht es wieder.")
            else:
                with open(review_file, "w", encoding="utf-8") as f:
                    if issues:
                        lines = [f"Part {i['part']}: {i['problem']}" if i.get("part") is not None
                                 else i["problem"] for i in issues]
                        f.write(f"{len(issues)} Hinweis(e):\n\n" + "\n".join(f"- {l}" for l in lines) + "\n")
                    else:
                        f.write("Keine Auffälligkeiten.\n")
                if issues:
                    print(f"  ⚠️  Episoden-Review: {len(issues)} Hinweis(e) — Episode bleibt trotzdem fertig, "
                          f"Details in {os.path.basename(review_file)}:")
                    for i in issues:
                        label = f"Part {i['part']}: " if i.get("part") is not None else ""
                        print(f"    - {label}{i['problem']}")
                else:
                    print(f"  ✅  Episoden-Review: keine Auffälligkeiten.")

    return True
