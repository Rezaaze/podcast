#!/usr/bin/env python3
"""Vertont ein Episoden-Skript zur fertigen, gemasterten MP3.

Verwendung:
  .venv/bin/python podcast_maker.py figur1.txt                # Datei in scripts/ der aktuellen Serie
  .venv/bin/python podcast_maker.py series/x/scripts/ep1.txt  # oder voller Pfad
  .venv/bin/python podcast_maker.py figur1.txt --series dead_reckoning

Zwei Modi (episodes.json "mode"):
  narration  Ein Sprecher für die ganze Episode, Styles pro Section
             (section_styles) — das bisherige Verhalten.
  drama      Multi-Voice-Hörspiel: jede Skriptzeile trägt ihr Sprecher-Tag
             ([HOST | style: ... | speed: ...]), Stimmen kommen aus dem
             voices-Mapping. [SFX: ...]-Zeilen werden nicht vertont, sondern
             mit ihrem Zeit-Offset in <Episode>_SFX_CUES.txt protokolliert
             (für das spätere Mixing in der DAW).

Jeder Text-Chunk wird als Checkpoint-WAV gesichert — ein abgebrochener Lauf
setzt beim Neustart fort. Fertige Parts/Episoden werden übersprungen.
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import sys
import time

from pydub import AudioSegment

from fabrik.audio import pipeline as audio
from fabrik.audio.tts_backends import build_backend
from fabrik.cli import sfx_plan
from fabrik.core import config, paths, sections as sec, textproc
from fabrik.writing.script_parser import ScriptFormatError, parse_drama_part

FADE_MS = 15
NARRATOR_ROLE = "__narrator__"
PAUSE_ONLY_SILENCE_MS = 500  # Ersatz-Stille für Chunks ohne sprechbaren Text

# Fester Instruct-Text für den Drama-NARRATOR (siehe build_drama_jobs) —
# BEWUSST kein None: "kein Style" bedeutet je nach Backend etwas anderes,
# aber nie wirklich "neutral". RestBackend.generate_chunk fällt bei
# style=None auf audio.default_style zurück (in Produktion z.B. "Speak
# clearly and with dramatic weight" — das Gegenteil von neutral).
# GradioBackend (Cloud-Renders, cloud/render_remote.sh erzwingt dieses
# Backend IMMER) schickt bei None einen LEEREN Instruct-String — das
# Modell bekommt gar keine Anweisung und driftet unbegleitet über viele
# Chunks hinweg in Tonfall/Tempo, statt konsistent ruhig zu bleiben. Ein
# fester, wirklich neutraler Text verankert die Stimme bei BEIDEN Backends
# gleich, bypasst aber weiterhin bewusst Skript-Style-Tags/default_style
# (unverändert gegenüber der alten None-Logik).
NARRATOR_STYLE = ("Read in a calm, neutral, steady narrator voice — "
                   "no dramatic emphasis, no emotional coloring")

# Lücke, die ein placement="before"-Cue vor der nächsten Sprecherzeile bekommt
# (siehe fabrik/cli/sfx_plan.py): der Sound soll VOR der Reaktion hörbar sein,
# nicht auf dem ersten Wort liegen. Aus der Asset-Dauer abgeleitet und
# gedeckelt — eine 3s-Textur würde die Szene sonst zerreißen.
SFX_LEAD_MIN_MS = 300
SFX_LEAD_MAX_MS = 1200

# Fallbacks — werden in main() aus episodes.json überschrieben
CHUNK_MAX_CHARS = 350

# Optionale Wiederholungs-Syntax am Ende einer [SFX: ...]-Beschreibung,
# z.B. "gunshot x3, 0.4s apart" — für Aktionen, die mehrfach hörbar sein
# sollen (Skript-Prompt-Doku: templates/*/PROMPT_TEMPLATE.md). Ans
# Stringende verankert (\s*$), damit NUR ein trailing "xN"-Token matcht,
# nie "x3" mitten im Fließtext.
_SFX_REPEAT_RE = re.compile(
    r'(?i)\s*[x×]\s*(\d+)\s*(?:,\s*([\d.]+)\s*s(?:ec(?:onds)?)?\s*apart)?\s*$'
)
MAX_SFX_REPEAT = 8  # Schutz gegen Tippfehler/Runaway-Zahl in der xN-Angabe


def parse_sfx_repeat(desc):
    """'gunshot x3, 0.4s apart' -> ('gunshot', 3, 0.4)
    'gunshot x3' -> ('gunshot', 3, 0.0) — alle Trigger auf demselben ms
    'city traffic' -> ('city traffic', 1, 0.0) — kein Treffer, unverändert."""
    match = _SFX_REPEAT_RE.search(desc)
    if not match:
        return desc, 1, 0.0
    count = min(int(match.group(1)), MAX_SFX_REPEAT)
    if count < 1:
        return desc, 1, 0.0
    interval_s = float(match.group(2)) if match.group(2) else 0.0
    clean_desc = desc[:match.start()].strip()
    return clean_desc, count, interval_s


def expand_sfx_cue(cue, base_ms):
    """Ein Cue -> Liste von {"ms", "description", ...}-Einträgen, eine pro
    Wiederholung (parse_sfx_repeat), zeitlich versetzt um interval_s.
    asset/gain aus dem SFX-Plan (falls vorhanden) hängen an jeder Wiederholung
    — sie sind der Vertrag mit Lolfis Mixing."""
    clean_desc, count, interval_s = parse_sfx_repeat(cue["description"])
    interval_ms = int(interval_s * 1000)
    entries = []
    for i in range(count):
        entry = {"ms": base_ms + i * interval_ms, "description": clean_desc}
        if cue.get("asset"):
            entry["asset"] = cue["asset"]
        if cue.get("gain") is not None:
            entry["gain"] = cue["gain"]
        entries.append(entry)
    return entries


def resolve_cue(desc, plan_cues, plan_assets, episode_num, part_idx, ordinal, stale=None):
    """Ein roher [SFX: ...]-Text + seine Position -> der Cue, wie er vertont
    wird — None, wenn der SFX-Plan ihn verwirft (keep=false: kein Geräusch,
    zu dicht, doppelt).

    OHNE Plan (plan_cues leer, oder Episode/Position nicht im Plan) fällt der
    Cue auf das alte Verhalten zurück: placement "under", kein asset, kein
    gain — Lolfi hasht dann wie bisher den Cue-Text. Der Plan ist optional,
    ein fehlender darf nie eine Vertonung blockieren.

    STALE-GUARD: Der Plan adressiert Cues über ihre POSITION (episode, part,
    n-ter Cue im Part). Wird ein Skript neu generiert, sitzt an derselben
    Position womöglich ein anderer Cue — der Plan würde dann still den
    falschen Sound mit der falschen Lautstärke platzieren. Deshalb muss der
    Text an der Position noch übereinstimmen; sonst gilt der Eintrag als
    veraltet und der Cue läuft im Alt-Verhalten (nie falsch, höchstens
    ungeplant). Kur: 'sfx_plan --force'."""
    base = {"description": desc, "placement": sfx_plan.DEFAULT_PLACEMENT,
            "asset": None, "gain": None, "lead_ms": 0}
    entry = plan_cues.get((episode_num, part_idx, ordinal))
    if entry is None:
        return base
    if entry.get("text") != sfx_plan.strip_repeat(desc)[0]:
        if stale is not None:
            stale.append((part_idx, desc, entry.get("text")))
        return base
    if not entry.get("keep"):
        return None

    asset = plan_assets.get(entry.get("asset_key"), {})
    base["asset"] = asset.get("asset")
    base["gain"] = entry.get("gain")
    base["placement"] = entry.get("placement", sfx_plan.DEFAULT_PLACEMENT)
    if base["placement"] == "before":
        duration_ms = int(float(asset.get("duration_s") or 0) * 1000)
        base["lead_ms"] = max(SFX_LEAD_MIN_MS, min(duration_ms, SFX_LEAD_MAX_MS))
    return base


def split_script(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    parts = re.split(r'--- PART \d+ ---', content)
    return [p.strip() for p in parts if p.strip()]


def episode_name_from_file(file_path):
    """Leitet den Episodennamen aus dem Dateinamen ab (figur1.txt → Figur1).
    Muss identisch zu batch.py sein, damit batch.py fertige Episoden erkennt."""
    stem = os.path.splitext(os.path.basename(file_path))[0]
    return stem.capitalize()


def resolve_script_path(input_file, series):
    """Erlaubt sowohl volle Pfade als auch bloße Dateinamen (die in
    scripts/ der Serie gesucht werden)."""
    if os.path.exists(input_file):
        return input_file
    candidate = os.path.join(series.scripts_dir, os.path.basename(input_file))
    if os.path.exists(candidate):
        return candidate
    print(f"FEHLER: Skript nicht gefunden: {input_file}")
    print(f"  (auch nicht als {candidate})")
    sys.exit(1)


def load_section_styles(input_file, data, prefix, parts_per_section):
    """Narration: Section-Styles aus episodes.json anhand der Dateinummer
    (figur1 → Index 0) auf Part-Nummern mappen."""
    match = re.search(rf'{re.escape(prefix)}(\d+)', os.path.basename(input_file), re.IGNORECASE)
    if not match:
        return {}
    ep_idx = int(match.group(1)) - 1
    episodes = data.get("episodes", [])
    if ep_idx < 0 or ep_idx >= len(episodes):
        return {}
    styles = episodes[ep_idx].get("section_styles", [])
    part_styles = {}
    for sec_idx, style in enumerate(styles):
        for k in range(1, parts_per_section + 1):
            part_styles[sec_idx * parts_per_section + k] = style
    return part_styles


def build_narration_jobs(parts, part_styles, default_style, chunk_max_chars):
    """Ein Job = ein TTS-Chunk. Narration: konstante Stimme, Style pro Part."""
    all_jobs = []
    for idx, part_text in enumerate(parts, start=1):
        style = part_styles.get(idx, default_style)
        jobs = []
        for chunk in textproc.chunk_sentences(textproc.split_into_sentences(part_text), chunk_max_chars):
            job = {"text": chunk, "role": NARRATOR_ROLE, "style": style,
                   "speed": None, "line_start": False, "cues": []}
            if not textproc.is_speakable(chunk):
                job["silence_ms"] = PAUSE_ONLY_SILENCE_MS
            jobs.append(job)
        all_jobs.append(jobs)
    return all_jobs


def build_drama_jobs(parts, voices_cfg, chunk_max_chars,
                     plan_cues=None, plan_assets=None, episode_num=None):
    """Drama: pro Skriptzeile Stimme/Style/Speed; SFX-Cues hängen am nächsten
    Job (bzw. am Part-Ende, wenn danach nichts mehr kommt).

    plan_cues/plan_assets: der SFX-Plan (fabrik/cli/sfx_plan.py), gesucht wird
    per POSITION (episode, part, n-ter Cue im Part) statt per Text — derselbe
    Cue-Text kann in einem Part mehrfach vorkommen und dabei unterschiedlich
    platziert sein. Verworfene Cues verschwinden hier komplett."""
    plan_cues = plan_cues or {}
    plan_assets = plan_assets or {}
    all_jobs = []
    dropped = 0
    stale = []
    for idx, part_text in enumerate(parts, start=1):
        items = parse_drama_part(part_text, voices=voices_cfg, part_label=f"PART {idx}")
        jobs = []
        pending_cues = []
        cue_ordinal = 0
        for item in items:
            if item.kind == "sfx":
                cue = resolve_cue(item.description, plan_cues, plan_assets,
                                  episode_num, idx, cue_ordinal, stale)
                cue_ordinal += 1
                if cue is None:
                    dropped += 1
                    continue
                pending_cues.append(cue)
                continue
            if item.kind == "note":
                continue  # reine Autoren-Buchhaltung — nie vertont, nie gecuet
            role_cfg = voices_cfg[item.speaker]
            # NARRATOR ignoriert Skript-Style/Emotion-Tags UND
            # role_cfg.default_style IMMER, auch bei Built-in-Speakern --
            # dramatische/emotionale Anweisungen klingen auf der
            # Erzähler-Rolle hörbar "off"/komisch. Bekommt stattdessen den
            # festen NARRATOR_STYLE (siehe dortiger Kommentar) statt None --
            # None wäre je nach Backend entweder audio.default_style (oft
            # NICHT neutral) oder ein leerer Instruct-String (gar keine
            # Verankerung, hörbares Abdriften über viele Chunks). Voice-
            # Clones ignorieren instruct ohnehin serverseitig, dort ist
            # NARRATOR_STYLE ein No-op.
            style = NARRATOR_STYLE if item.speaker == "NARRATOR" else (item.style or role_cfg.get("default_style"))
            speed = item.speed if item.speed is not None else role_cfg.get("speed")
            chunks = textproc.chunk_sentences(textproc.split_into_sentences(item.text), chunk_max_chars)
            for c_i, chunk in enumerate(chunks):
                job = {"text": chunk, "role": item.speaker, "style": style,
                       "speed": speed, "line_start": c_i == 0,
                       "cues": pending_cues if c_i == 0 else []}
                if not textproc.is_speakable(chunk):
                    job["silence_ms"] = PAUSE_ONLY_SILENCE_MS
                jobs.append(job)
                if c_i == 0:
                    pending_cues = []
        all_jobs.append({"jobs": jobs, "end_cues": pending_cues})
    return all_jobs, dropped, stale


def checkpoint_path(checkpoint_dir, episode_name, part_idx, c_idx):
    part_dir = os.path.join(checkpoint_dir, f"{episode_name}_Part_{part_idx:02d}")
    os.makedirs(part_dir, exist_ok=True)
    return os.path.join(part_dir, f"chunk_{c_idx:03d}.wav")


def clear_checkpoint(checkpoint_dir, episode_name, part_idx):
    part_dir = os.path.join(checkpoint_dir, f"{episode_name}_Part_{part_idx:02d}")
    if os.path.exists(part_dir):
        shutil.rmtree(part_dir)


def cues_json_path(series, episode_name, part_idx):
    return os.path.join(series.cues_dir, f"{episode_name}_Part_{part_idx:02d}.json")


def speakers_json_path(series, episode_name, part_idx):
    return os.path.join(series.cues_dir, f"{episode_name}_Part_{part_idx:02d}_speakers.json")


# Zwei Spannen derselben Rolle mit weniger als dieser Lücke werden zu einer
# zusammengelegt (Chunk-/Zeilenpausen von 250/600 ms verschwinden, die
# 4000-ms-Part-Pause trennt weiterhin) — hält die Timeline kompakt genug
# für Video-Overlays (ffmpeg-enable-Ausdrücke) und Videoeditoren.
SPEAKER_MERGE_GAP_MS = 1500


def merge_speaker_spans(spans):
    """Zusammenlegen nur bei gleicher Rolle UND gleichem Style — der Style
    (die Regieanweisung der Zeile) trägt die Emotion, die das Video als
    Farb-Panel/Emoji visualisiert; ein Wechsel muss eine eigene Spanne bleiben."""
    merged = []
    for span in sorted(spans, key=lambda s: s["start_ms"]):
        if (merged and merged[-1]["role"] == span["role"]
                and merged[-1].get("style") == span.get("style")
                and span["start_ms"] - merged[-1]["end_ms"] <= SPEAKER_MERGE_GAP_MS):
            merged[-1]["end_ms"] = max(merged[-1]["end_ms"], span["end_ms"])
        else:
            merged.append(dict(span))
    return merged


def build_scene_presence(spans, part_offsets):
    """Wer ist WÄHREND jedes PARTs anwesend (nicht nur wer gerade spricht) —
    ein PART ist eine Szene: alle Rollen, die irgendwo innerhalb der
    PART-Grenzen eine Sprecher-Spanne haben, gelten für die GESAMTE Dauer
    dieses Parts als anwesend. Grenzen kommen direkt aus part_offsets (schon
    inklusive Intro-Jingle-Offset) statt aus einer eigenen Zeitmessung — ein
    Part endet exakt dort, wo der nächste beginnt, der letzte Part endet am
    letzten Spannen-Ende. Ermöglicht Video-Overlays wie Lolfi zu zeigen, MIT
    WEM eine Figur gerade spricht, nicht nur DASS sie spricht."""
    if not spans:
        return []
    boundaries = part_offsets + [max(s["end_ms"] for s in spans)]
    scenes = []
    for i in range(len(part_offsets)):
        start, end = boundaries[i], boundaries[i + 1]
        roles = sorted({s["role"] for s in spans if s["start_ms"] < end and s["end_ms"] > start})
        if roles:
            scenes.append({"start_ms": start, "end_ms": end, "roles": roles})
    return scenes


def write_speaker_timeline(series, episode_name, part_offsets, num_parts, output_dir):
    """Kombiniert die pro Part gespeicherten Sprecher-Spannen mit den
    Part-Offsets der fertigen Episode zu einer Timeline (wer spricht wann):
    <Episode>_SPEAKERS.json (maschinenlesbar, z.B. für Video-Overlays in
    Lolfi) + <Episode>_SPEAKERS.txt (lesbar, für manuellen Videoschnitt).
    Enthält zusätzlich "scenes" (wer ist pro PART anwesend, nicht nur wer
    gerade spricht — siehe build_scene_presence) für Overlays, die auch den
    Gesprächspartner zeigen wollen."""
    spans = []
    missing = []
    for idx in range(1, num_parts + 1):
        speakers_file = speakers_json_path(series, episode_name, idx)
        if not os.path.exists(speakers_file):
            missing.append(idx)
            continue
        with open(speakers_file, "r", encoding="utf-8") as f:
            for span in json.load(f):
                spans.append({"start_ms": part_offsets[idx - 1] + span["start_ms"],
                              "end_ms": part_offsets[idx - 1] + span["end_ms"],
                              "role": span["role"], "style": span.get("style", "")})
    if missing:
        print(f"  Hinweis: Keine Sprecher-Daten für Part(s) {missing} gefunden "
              f"(Parts aus einem Lauf vor dieser Funktion?) — Sprecher-Timeline ist unvollständig.")
    if not spans:
        return
    scenes = build_scene_presence(spans, part_offsets)
    spans = merge_speaker_spans(spans)

    json_path = os.path.join(output_dir, f"{episode_name}_SPEAKERS.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"episode": episode_name, "spans": spans, "scenes": scenes}, f, ensure_ascii=False, indent=1)

    txt_path = os.path.join(output_dir, f"{episode_name}_SPEAKERS.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"# Sprecher-Timeline — {episode_name} (Timestamps in der fertigen Episode)\n\n")
        for span in spans:
            f.write(f"{audio.format_timestamp(span['start_ms'])} – "
                    f"{audio.format_timestamp(span['end_ms'])}  {span['role']}\n")
    print(f"Sprecher-Timeline geschrieben: {os.path.basename(json_path)} ({len(spans)} Spannen)")


def get_section_locations(input_file, data, prefix):
    """Section-Locations aus episodes.json anhand der Dateinummer (ep7 ->
    Index 6) auf die Episode gemappt — gleiches Muster wie
    load_section_styles, aber modusunabhängig (locations gibt es sowohl bei
    narration als auch drama). Bei Objekt-Sections (Stage-01-Umbau) steht
    der Ort im Section-Objekt selbst statt im alten Parallel-Array — wird
    hier zu derselben flachen Liste zusammengebaut, damit build_location_timeline()
    unverändert bleibt."""
    match = re.search(rf'{re.escape(prefix)}(\d+)', os.path.basename(input_file), re.IGNORECASE)
    if not match:
        return None
    ep_idx = int(match.group(1)) - 1
    episodes = data.get("episodes", [])
    if ep_idx < 0 or ep_idx >= len(episodes):
        return None
    episode = episodes[ep_idx]
    secs = episode.get("sections") or []
    legacy = episode.get("section_locations")
    if not any(isinstance(s, dict) for s in secs):
        return legacy
    return [sec.section_location(s, i, legacy) for i, s in enumerate(secs)]


def build_location_timeline(section_locations, parts_per_section, part_offsets,
                            episode_duration_ms, section_ambience=None):
    """Ordnet jedem PART (über part_offsets, dieselbe Zeitquelle wie
    build_scene_presence) seinen Section-Index zu (parts_per_section PARTs
    pro Section) und schlägt darüber section_locations[section_idx] nach.
    'null' in section_locations heißt 'Hintergrund bleibt wie zuvor' — der
    zuletzt aktive Ort wird fortgeschrieben, nicht auf 'kein Ort' zurück-
    gesetzt. Konsekutive PARTs mit demselben Ort werden zu einer Zeitspanne
    zusammengelegt, damit die Timeline nicht bei jedem Part-Wechsel unnötig
    einen neuen Abschnitt aufmacht, wenn zwei Sections denselben Ort teilen.

    section_ambience: {section_idx: variant_key} aus dem SFX-Plan — die
    Stimmungs-Variante der Szene (fabrik/cli/sfx_plan.py). Sie wird wie der
    Ort fortgeschrieben und bricht die Zusammenlegung: zwei Sections am
    selben Ort, aber in unterschiedlicher Stimmung, sind zwei Spannen —
    sonst könnte Lolfi mittendrin nicht auf die andere Schleife überblenden.
    Ohne Plan bleibt das Feld weg und alles verhält sich wie bisher."""
    if not section_locations:
        return []
    section_ambience = section_ambience or {}
    boundaries = part_offsets + [episode_duration_ms]
    spans = []
    current_location = None
    current_ambience = None
    for i in range(len(part_offsets)):
        section_idx = i // parts_per_section
        if section_idx < len(section_locations) and section_locations[section_idx]:
            current_location = section_locations[section_idx]
            current_ambience = section_ambience.get(section_idx)
        if current_location is None:
            continue
        start, end = boundaries[i], boundaries[i + 1]
        if (spans and spans[-1]["location"] == current_location
                and spans[-1].get("ambience") == current_ambience
                and spans[-1]["end_ms"] == start):
            spans[-1]["end_ms"] = end
        else:
            span = {"start_ms": start, "end_ms": end, "location": current_location}
            if current_ambience:
                span["ambience"] = current_ambience
            spans.append(span)
    return spans


def write_location_timeline(episode_name, section_locations, parts_per_section,
                            part_offsets, episode_path, output_dir, section_ambience=None):
    """Schreibt <Episode>_LOCATIONS.json: welcher Ort (Key aus episodes.json
    'locations') wann aktiv ist, damit Lolfi beim Video-Rendern automatisch
    den passenden Hintergrund zeigt — und, wenn ein SFX-Plan existiert, welche
    Ambience-Variante ("ambience") dabei laufen soll. Eigene Datei statt
    Erweiterung von _SPEAKERS.json, da Locations modusunabhängig sind —
    _SPEAKERS.json gibt es nur im Drama-Modus."""
    if not section_locations:
        return
    episode_duration_ms = len(AudioSegment.from_file(episode_path))
    spans = build_location_timeline(section_locations, parts_per_section, part_offsets,
                                    episode_duration_ms, section_ambience)
    if not spans:
        return
    json_path = os.path.join(output_dir, f"{episode_name}_LOCATIONS.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"episode": episode_name, "locations": spans}, f, ensure_ascii=False, indent=1)
    moods = len({s["ambience"] for s in spans if s.get("ambience")})
    suffix = f", {moods} Ambience-Variante(n)" if moods else ""
    print(f"Location-Timeline geschrieben: {os.path.basename(json_path)} "
          f"({len(spans)} Abschnitt(e){suffix})")


def write_sfx_cue_sheet(series, episode_name, part_offsets, num_parts, output_path):
    """Kombiniert die pro Part gespeicherten Cue-Offsets mit den Part-Offsets
    der fertigen Episode zu einem DAW-tauglichen Cue-Sheet."""
    entries = []
    missing = []
    for idx in range(1, num_parts + 1):
        cue_file = cues_json_path(series, episode_name, idx)
        if not os.path.exists(cue_file):
            missing.append(idx)
            continue
        with open(cue_file, "r", encoding="utf-8") as f:
            for cue in json.load(f):
                entries.append((part_offsets[idx - 1] + cue["ms"], cue["description"]))
    if missing:
        print(f"  Hinweis: Keine SFX-Cue-Daten für Part(s) {missing} gefunden "
              f"(Parts aus einem Lauf vor dieser Funktion?) — Cue-Sheet ist unvollständig.")
    if not entries:
        return
    entries.sort()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# SFX-Cues — {episode_name} (Timestamps in der fertigen Episode)\n\n")
        for ms, desc in entries:
            f.write(f"{audio.format_timestamp(ms)}  {desc}\n")
    print(f"SFX-Cue-Sheet geschrieben: {os.path.basename(output_path)} ({len(entries)} Cues)")


def write_sfx_cue_json(series, episode_name, part_offsets, num_parts, output_path):
    """Strukturiertes Gegenstück zu write_sfx_cue_sheet() (das Text-Cue-Sheet
    bleibt für Menschen/DAW) — für Lolfis automatisches One-Shot-SFX-
    Triggering (fabrik.cli.sfx_assets generiert dazu passende Sounds,
    Lolfi matched per sfx_asset_hash(description)). Liest dieselben
    pro-Part-Cue-JSONs wie write_sfx_cue_sheet(), bereits inkl. per
    expand_sfx_cue() aufgelöster Wiederholungs-Cues. Schema mirrort
    write_location_timeline()."""
    entries = []
    missing = []
    for idx in range(1, num_parts + 1):
        cue_file = cues_json_path(series, episode_name, idx)
        if not os.path.exists(cue_file):
            missing.append(idx)
            continue
        with open(cue_file, "r", encoding="utf-8") as f:
            for cue in json.load(f):
                entry = {"ms": part_offsets[idx - 1] + cue["ms"], "description": cue["description"]}
                # asset/gain nur, wenn ein SFX-Plan sie gesetzt hat: 'asset' ist
                # der Dateiname, den Lolfi sonst selbst aus dem Cue-Text hashen
                # müsste (Fallback dort bleibt), 'gain' die geplante Lautstärke
                # statt einer pauschalen Konstante.
                if cue.get("asset"):
                    entry["asset"] = cue["asset"]
                if cue.get("gain") is not None:
                    entry["gain"] = cue["gain"]
                entries.append(entry)
    if missing:
        print(f"  Hinweis: Keine SFX-Cue-Daten für Part(s) {missing} gefunden — SFX-Cue-JSON ist unvollständig.")
    if not entries:
        return
    entries.sort(key=lambda e: e["ms"])
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"episode": episode_name, "cues": entries}, f, ensure_ascii=False, indent=1)
    print(f"SFX-Cue-JSON geschrieben: {os.path.basename(output_path)} ({len(entries)} Cues)")


def subs_json_path(series, episode_name, part_idx):
    return os.path.join(series.cues_dir, f"{episode_name}_Part_{part_idx:02d}_subs.json")


def format_srt_timestamp(ms):
    total_seconds, millis = divmod(int(ms), 1000)
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def pretty_role_name(role):
    return role.replace("_", " ").title()


def split_chunk_into_cues(start_ms, end_ms, text):
    """Ein TTS-Chunk (bis ~350 Zeichen) ist zu lang für einen einzelnen
    Untertitel — satzweise aufteilen, Dauer proportional zur Satzlänge
    (die exakte Sprechzeit pro Satz kennt nur das TTS, die Näherung reicht
    fürs Mitlesen)."""
    sentences = [s for s in textproc.split_into_sentences(text) if s.strip()]
    if not sentences:
        return []
    total_len = sum(len(s) for s in sentences)
    duration = end_ms - start_ms
    cues = []
    cursor = start_ms
    for i, sentence in enumerate(sentences):
        if i == len(sentences) - 1:
            cue_end = end_ms
        else:
            cue_end = cursor + int(duration * len(sentence) / total_len)
        cues.append({"start_ms": int(cursor), "end_ms": int(cue_end), "text": sentence.strip()})
        cursor = cue_end
    return cues


def write_srt(cues, path, title_comment=None):
    with open(path, "w", encoding="utf-8") as f:
        for n, cue in enumerate(cues, start=1):
            f.write(f"{n}\n{format_srt_timestamp(cue['start_ms'])} --> "
                    f"{format_srt_timestamp(cue['end_ms'])}\n{cue['text']}\n\n")


def write_episode_subtitles(series, episode_name, part_offsets, num_parts, episode_path, drama):
    """Kombiniert die pro Part gespeicherten Chunk-Texte+Timings zu
    <Episode>_FULL_EPISODE.srt (bei YouTube als Untertitel hochladen) und
    <Episode>..._SUBS.json (Zwischenformat, aus dem batch.py die
    Anthologie-SRT zusammensetzt, UND das Lolfi für szenengenaue
    Sprechblasen-Einblendungen liest — siehe "role" pro Cue unten). Im
    Drama-Modus wird im SRT-Text bei jedem Sprecherwechsel der Name
    vorangestellt; die JSON-Cues bleiben dagegen unpräfixiert und tragen
    stattdessen ein eigenes "role"-Feld, da Lolfi den Namen bereits über
    das Porträt-Label zeigt und keinen doppelten Text in der Sprechblase
    braucht."""
    chunk_records = []
    missing = []
    for idx in range(1, num_parts + 1):
        subs_file = subs_json_path(series, episode_name, idx)
        if not os.path.exists(subs_file):
            missing.append(idx)
            continue
        with open(subs_file, "r", encoding="utf-8") as f:
            for rec in json.load(f):
                chunk_records.append({"start_ms": part_offsets[idx - 1] + rec["start_ms"],
                                      "end_ms": part_offsets[idx - 1] + rec["end_ms"],
                                      "text": rec["text"], "role": rec["role"]})
    if missing:
        print(f"  Hinweis: Keine Untertitel-Daten für Part(s) {missing} — SRT unvollständig.")
    if not chunk_records:
        return

    cues = []
    for rec in chunk_records:
        chunk_cues = split_chunk_into_cues(rec["start_ms"], rec["end_ms"], rec["text"])
        for cue in chunk_cues:
            cue["role"] = rec["role"]
        cues.extend(chunk_cues)

    srt_cues = []
    prev_role = None
    for cue in cues:
        text = cue["text"]
        if drama and cue["role"] != prev_role and cue["role"] != NARRATOR_ROLE:
            text = f"{pretty_role_name(cue['role'])}: {text}"
        prev_role = cue["role"]
        srt_cues.append({"start_ms": cue["start_ms"], "end_ms": cue["end_ms"], "text": text})

    srt_path = os.path.splitext(episode_path)[0] + ".srt"
    write_srt(srt_cues, srt_path)
    with open(os.path.splitext(episode_path)[0] + "_SUBS.json", "w", encoding="utf-8") as f:
        json.dump({"cues": cues}, f, ensure_ascii=False, indent=1)
    print(f"Untertitel geschrieben: {os.path.basename(srt_path)} ({len(cues)} Cues)")


AUDIO_ASSET_EXTS = (".mp3", ".wav", ".m4a", ".flac")


def find_audio_asset(series, stem):
    """Optionales Audio-Asset der Serie: assets/<stem>.mp3|wav|...
    (intro, outro, transition) — None, wenn nicht vorhanden."""
    for ext in AUDIO_ASSET_EXTS:
        candidate = os.path.join(series.assets_dir, f"{stem}{ext}")
        if os.path.exists(candidate):
            return candidate
    return None


def tag_episode_from_meta(episode_path, input_file, data):
    """Sucht die zum Skript gehörende *_META.txt (figur1.txt -> figur1_META.txt)
    und schreibt Titel/Beschreibung als ID3-Tags in die fertige Episoden-MP3.
    Titel bekommt einen 'Serientitel – S{season}E{n}:'-Präfix, wenn die Serie
    'season' gesetzt hat (Mehr-Staffel-Podcast-Kanal, siehe config.py/pipeline.py)."""
    series_title = data.get("series_title", "")
    prefix = data.get("output_prefix", config.DEFAULTS["output_prefix"])
    meta_path = os.path.splitext(input_file)[0] + "_META.txt"
    title, description, _question = audio.parse_meta_file(meta_path)
    if not title:
        print(f"  Hinweis: Keine {os.path.basename(meta_path)} gefunden — "
              f"MP3 bleibt ohne ID3-Titel/Beschreibung.")
        return
    episode_num = audio.extract_episode_number(input_file, prefix)
    title = audio.format_season_title(series_title, data.get("season"), episode_num, title)
    if audio.tag_mp3(episode_path, title=title, album=series_title, comment=description):
        print(f"  ID3-Tags geschrieben (Titel: \"{title}\")")


def run_postprocessing(series, cfg, data, episode_name, input_file, episode_path,
                       part_offsets, section_locations, mode):
    """Untertitel/SFX-Cues/Sprecher-/Location-Timeline + ID3-Tag aus den
    bereits pro Part gespeicherten JSON-Zwischendaten — bewusst idempotent
    (liest/schreibt nur kleine JSON-/Textdateien, keine TTS-Aufrufe) und
    jeder Schritt einzeln try/except-abgesichert.

    Grund: merge_parts_to_episode() hat zu diesem Zeitpunkt die Episoden-MP3
    bereits geschrieben UND die Part-WAVs bereits gelöscht — ein Absturz in
    einem der folgenden Schritte (z.B. eine durch einen früheren Kill mitten
    im Schreiben korrupte Part-JSON-Datei) darf weder die anderen Schritte
    verhindern noch die Episode für immer ohne Metadaten zurücklassen. main()
    ruft diese Funktion deshalb bei JEDEM Lauf erneut auf, auch wenn die MP3
    schon existiert (siehe dortiger Kommentar) — die gespeicherten
    part_offsets (audio.load_part_offsets) machen das möglich, ohne die
    (bereits gelöschten) Part-WAVs zu brauchen."""
    num_parts = len(part_offsets)
    if mode == "drama":
        try:
            cue_sheet_path = os.path.join(series.output_dir, f"{episode_name}_SFX_CUES.txt")
            write_sfx_cue_sheet(series, episode_name, part_offsets, num_parts, cue_sheet_path)
        except Exception as e:
            print(f"  WARNUNG: SFX-Cue-Sheet fehlgeschlagen ({e}) — Lauf erneut starten, um es nachzuholen.")
        try:
            cue_json_path_out = os.path.join(series.output_dir, f"{episode_name}_SFX_CUES.json")
            write_sfx_cue_json(series, episode_name, part_offsets, num_parts, cue_json_path_out)
        except Exception as e:
            print(f"  WARNUNG: SFX-Cue-JSON fehlgeschlagen ({e}) — Lauf erneut starten, um es nachzuholen.")
        try:
            write_speaker_timeline(series, episode_name, part_offsets, num_parts, series.output_dir)
        except Exception as e:
            print(f"  WARNUNG: Sprecher-Timeline fehlgeschlagen ({e}) — Lauf erneut starten, um es nachzuholen.")
    try:
        write_episode_subtitles(series, episode_name, part_offsets, num_parts,
                                episode_path, drama=(mode == "drama"))
    except Exception as e:
        print(f"  WARNUNG: Untertitel fehlgeschlagen ({e}) — Lauf erneut starten, um es nachzuholen.")
    try:
        # Ambience-Varianten dieser Episode aus dem SFX-Plan (falls vorhanden):
        # {section_idx: variant_key} — ohne Plan bleibt es leer und die Timeline
        # sieht aus wie vorher.
        episode_num = audio.extract_episode_number(input_file, cfg["prefix"])
        plan_ambience = sfx_plan.section_ambience_lookup(
            sfx_plan.load_plan(sfx_plan.plan_path(series)))
        section_ambience = {sec_idx: variant
                            for (ep, sec_idx), variant in plan_ambience.items()
                            if ep == episode_num}
        write_location_timeline(episode_name, section_locations, cfg["parts_per_section"],
                                part_offsets, episode_path, series.output_dir,
                                section_ambience)
    except Exception as e:
        print(f"  WARNUNG: Location-Timeline fehlgeschlagen ({e}) — Lauf erneut starten, um es nachzuholen.")
    tag_episode_from_meta(episode_path, input_file, data)


def resolve_drama_voices(backend, voices_cfg, audio_cfg):
    """Löst jede Rolle einmal auf; sammelt alle Fehler statt beim ersten
    abzubrechen (eine Serverliste, eine Fehlermeldung).

    seed je Rolle: 'voices.<ROLLE>.seed', sonst Fallback auf 'audio.seed'
    (episodes.json) — nur RestBackend + geklonte Stimmen (kind == "prompt")
    nutzen ihn tatsächlich (siehe tts_backends.py::RestBackend)."""
    resolved = {}
    problems = []
    for role, vcfg in voices_cfg.items():
        seed = vcfg.get("seed", audio_cfg.get("seed"))
        kind, voice_id, resolved_seed = backend.resolve_voice(vcfg["voice"], seed=seed)
        if kind is None:
            available = f" — verfügbar: {', '.join(voice_id)}" if voice_id else ""
            problems.append(f"[{role}] → Stimme '{vcfg['voice']}' nicht gefunden{available}")
        else:
            resolved[role] = (kind, voice_id, resolved_seed)
            if kind == "kokoro":
                print(f"  HINWEIS: [{role}] nutzt Kokoro-MLX ('{vcfg['voice']}') — "
                      f"Kokoro folgt keinen Stilanweisungen, Style-Zeilen werden ignoriert.")
            elif kind == "prompt":
                print(f"  HINWEIS: [{role}] nutzt eine geklonte Stimme ('{vcfg['voice']}') — "
                      f"Style-Anweisungen (instruct) werden dafür ignoriert.")
                if resolved_seed is not None:
                    print(f"    Seed {resolved_seed} aktiv (Streaming-Endpunkt, gegen Timbre-Drift über Chunks).")
            elif kind == "clone":
                print(f"  HINWEIS: [{role}] nutzt eine geklonte Stimme ('{vcfg['voice']}') — "
                      f"Style-Anweisungen (instruct) werden dafür ignoriert.")
            elif kind == "speaker" and resolved_seed is not None:
                print(f"  HINWEIS: [{role}] nutzt Built-in-Speaker '{vcfg['voice']}' — "
                      f"gesetzter seed wird von dieser API für Built-in-Speaker ignoriert.")
    return resolved, problems


def voices_manifest_path(series):
    return os.path.join(series.output_dir, ".voices_manifest.json")


def build_current_voice_manifest(cfg, audio_cfg):
    """Rollenname -> {voice, speed, seed}, direkt aus episodes.json (kein
    Server-Call nötig) — für den Drift-Check gegen bereits gerenderte Audios.
    Im narration-Modus gibt es nur eine Stimme für die ganze Serie, dafür
    der feste Schlüssel '__narration__'. seed ist Teil des Manifests, weil
    ein nachträglich geänderter seed bei geklonten Stimmen genauso zu
    hörbar unterschiedlichem Timbre zwischen alten und neuen Episoden führen
    würde wie ein geänderter Stimmenname (siehe check_voice_consistency)."""
    if cfg["mode"] == "drama":
        return {
            role: {
                "voice": vcfg["voice"],
                "speed": vcfg.get("speed"),
                "seed": vcfg.get("seed", audio_cfg.get("seed")),
            }
            for role, vcfg in cfg["voices"].items()
        }
    return {"__narration__": {
        "voice": audio_cfg.get("voice", "MyVoice"),
        "speed": None,
        "seed": audio_cfg.get("seed"),
    }}


def check_voice_consistency(series, cfg, audio_cfg):
    """Verhindert, dass eine Rolle über den Verlauf einer Serie hinweg mit
    unterschiedlichen Stimmen vertont wird: Checkpoints/Part-WAVs/fertige
    Episoden-MP3s werden rein nach Dateiname gecacht, nicht nach der
    Stimmen-Konfiguration, die sie erzeugt hat — ändert sich z.B.
    'voices.MARCUS_CHEN.voice' in episodes.json, nachdem schon Episoden mit
    der alten Stimme fertig sind, würde der Rest der Serie sonst
    stillschweigend mit der neuen Stimme weiterlaufen, ohne dass irgendwas
    davon merkt oder warnt. Bricht hart ab statt nur zu warnen, bewusst
    (siehe Absprache) — der Nutzer soll die Abweichung aktiv auflösen
    (episodes.json zurücknehmen oder die betroffenen alten Audios/Checkpoints
    gezielt löschen), nicht dass sie unbemerkt durchrutscht.

    NUR ein Vergleich — schreibt selbst nichts. Läuft bewusst ganz am Anfang
    von main() (fail-fast, bevor Skript/Server/Stimmenauflösung Zeit kosten),
    aber die erstmalige Baseline wird erst von commit_voice_manifest() nach
    erfolgreicher Stimmenauflösung geschrieben (siehe dort) — sonst würde ein
    Lauf, der SOFORT danach an einer nicht auflösbaren Stimme oder einem
    unerreichbaren Server scheitert (kein einziges Byte Audio erzeugt), schon
    eine 'bereits gerendert'-Baseline hinterlassen und jede spätere Korrektur
    von episodes.json fälschlich als Inkonsistenz blockieren."""
    manifest_path = voices_manifest_path(series)
    if not os.path.exists(manifest_path):
        return
    current = build_current_voice_manifest(cfg, audio_cfg)

    with open(manifest_path, "r", encoding="utf-8") as f:
        stored = json.load(f)

    # Migration: Manifeste von vor der seed-Unterstützung haben kein "seed"-Feld.
    # Ohne diesen Normalisierungsschritt würde jede bestehende Serie beim ersten
    # Lauf nach diesem Update fälschlich als Inkonsistenz erkannt (fehlendes
    # Feld != explizit gesetztes "seed": null) und hart abbrechen, obwohl sich
    # an der Stimmen-Konfiguration nichts geändert hat.
    for role_data in stored.values():
        if isinstance(role_data, dict):
            role_data.setdefault("seed", None)

    mismatches = [
        (role, stored[role], current[role])
        for role in current
        if role in stored and stored[role] != current[role]
    ]
    if mismatches:
        print(f"FEHLER: Stimmen-Inkonsistenz in Serie '{series.slug}' erkannt — "
              f"Abbruch, um Vertonung mit gemischten Stimmen zu verhindern:")
        for role, old, new in mismatches:
            label = "Erzähler-Stimme" if role == "__narration__" else f"[{role}]"
            print(f"  - {label}: bisher gerendert mit {old}, episodes.json fordert jetzt {new}")
        print(f"  Bereits gerenderte Audios (Episoden-MP3s, Part-WAVs, Checkpoints) dieser Serie")
        print(f"  wurden mit der ALTEN Stimme erzeugt — würde jetzt weitergemacht, klänge dieselbe")
        print(f"  Rolle je nach Episode unterschiedlich.")
        print(f"  Entweder episodes.json zurücknehmen, oder die betroffene(n) Rolle(n) bewusst neu")
        print(f"  vertonen (alte Episoden-MP3s/Part-WAVs/.checkpoints löschen) und danach")
        print(f"  '{os.path.basename(manifest_path)}' löschen, damit der neue Stand als Basis gilt.")
        sys.exit(1)


def commit_voice_manifest(series, cfg, audio_cfg):
    """Schreibt/aktualisiert die Baseline-Datei — erst NACHDEM die Stimmen
    dieses Laufs erfolgreich beim Backend aufgelöst wurden (siehe Aufrufer in
    main()), damit die Baseline immer tatsächlich rendbare Audio-Konfiguration
    widerspiegelt, nie den Stand eines Laufs, der danach ohnehin scheitert."""
    manifest_path = voices_manifest_path(series)
    current = build_current_voice_manifest(cfg, audio_cfg)

    if not os.path.exists(manifest_path):
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=1)
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        stored = json.load(f)
    for role_data in stored.values():
        if isinstance(role_data, dict):
            role_data.setdefault("seed", None)

    merged = {**stored, **current}  # check_voice_consistency() hat Mismatches bereits ausgeschlossen
    if merged != stored:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=1)


def assemble_part(idx, jobs, segments, part_end_cues, part_path, filename, series, episode_name, mode,
                  pause_lines_ms, pause_chunks_ms):
    """Baut die fertigen Segmente eines Parts zu einer WAV zusammen (Cues
    expandieren, Pausen zwischen Zeilen/Chunks einfügen) und schreibt die
    Part-WAV + Sidecar-JSONs (_subs/_cues/_speakers). Reine Funktion von
    jobs/segments/part_end_cues — liest nichts aus der Generierungs-
    Maschinerie, kann deshalb unabhängig von der Chunk-Generierung laufen."""
    combined = AudioSegment.empty()
    cues = []
    speaker_spans = []
    sub_records = []
    for i, (job, seg) in enumerate(zip(jobs, segments)):
        if i > 0:
            gap = pause_lines_ms if job["line_start"] else pause_chunks_ms
            combined = combined + AudioSegment.silent(duration=gap)
        # placement="before" (SFX-Plan): der Sound bekommt eine eigene
        # Lücke VOR der Zeile, damit die folgende Replik auf ihn
        # reagieren kann, statt ihn zu übersprechen. Alle before-Cues
        # dieses Jobs starten gemeinsam am Anfang dieser Lücke; ihre
        # Länge richtet sich nach dem längsten beteiligten Asset.
        # "under" (und jeder Cue ohne Plan) bleibt beim alten
        # Verhalten: Sound startet exakt mit der Zeile.
        before = [c for c in job["cues"] if c.get("placement") == "before"]
        if before:
            lead_start = len(combined)
            for cue in before:
                cues.extend(expand_sfx_cue(cue, lead_start))
            combined = combined + AudioSegment.silent(
                duration=max(c["lead_ms"] for c in before))
        for cue in job["cues"]:
            if cue.get("placement") != "before":
                cues.extend(expand_sfx_cue(cue, len(combined)))
        span_start = len(combined)
        combined = combined + seg.fade_in(FADE_MS).fade_out(FADE_MS)
        speaker_spans.append({"start_ms": span_start, "end_ms": len(combined),
                              "role": job["role"], "style": job["style"] or ""})
        sub_records.append({"start_ms": span_start, "end_ms": len(combined),
                            "text": job["text"], "role": job["role"]})
    # Cues NACH der letzten Zeile eines Parts: alle feuern am aktuellen
    # Ende. placement="before" braucht auch hier seine Luft — ohne
    # angehängte Stille läge der Sound auf der letzten Millisekunde
    # des Parts und würde vom Übergang geschluckt.
    end_before = [c for c in part_end_cues if c.get("placement") == "before"]
    for cue in part_end_cues:
        cues.extend(expand_sfx_cue(cue, len(combined)))
    if end_before:
        combined = combined + AudioSegment.silent(
            duration=max(c["lead_ms"] for c in end_before))

    combined.export(part_path, format="wav")
    with open(subs_json_path(series, episode_name, idx), "w", encoding="utf-8") as f:
        json.dump(sub_records, f, ensure_ascii=False, indent=1)
    if mode == "drama":
        with open(cues_json_path(series, episode_name, idx), "w", encoding="utf-8") as f:
            json.dump(cues, f, ensure_ascii=False, indent=1)
        with open(speakers_json_path(series, episode_name, idx), "w", encoding="utf-8") as f:
            json.dump(merge_speaker_spans(speaker_spans), f, ensure_ascii=False, indent=1)
    size = os.path.getsize(part_path) // 1024
    print(f"  Gespeichert: {filename} ({size} KB)")
    clear_checkpoint(series.checkpoint_dir, episode_name, idx)


def main():
    parser = argparse.ArgumentParser(description="Skript → gemasterte Episoden-MP3")
    parser.add_argument("input_file", help="Skript-Datei (Pfad oder Dateiname in scripts/ der Serie)")
    parser.add_argument("--name", default=None, help="Name der Episode (überschreibt Auto-Erkennung)")
    parser.add_argument("--api-url", default=None, metavar="URL",
                        help="TTS-Server-URL nur für diesen Lauf überschreiben (statt audio.api_url) — "
                             "batch.py nutzt das, um einen zweiten Worker gegen audio.secondary_api_url "
                             "zu fahren. Der Server muss dieselben Stimmen/Clones anbieten.")
    # Aufgeteilter Render: reine TTS-Vertonung (GPU) und Mastering/Nachbearbeitung
    # (reine CPU/Platte) trennen, damit beim Remote-Rendern nur die GPU-Arbeit auf
    # der teuren Instanz läuft und alles danach lokal auf dem Mac passiert.
    parser.add_argument("--skip-merge", action="store_true",
                        help="NUR die TTS-Parts erzeugen, dann stoppen — KEIN Merge/Mastering/"
                             "Nachbearbeitung. Für Remote-Rendern auf der GPU-Instanz: die Part-WAVs "
                             "+ Sidecar-JSONs bleiben liegen und werden lokal via --merge-only fertig "
                             "verarbeitet.")
    parser.add_argument("--merge-only", action="store_true",
                        help="TTS überspringen; nur Merge + Mastering + Nachbearbeitung aus bereits "
                             "vorhandenen Part-WAVs (KEIN TTS-Server nötig). Gegenstück zu --skip-merge, "
                             "läuft lokal auf dem Mac nach dem Download.")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    if args.skip_merge and args.merge_only:
        print("FEHLER: --skip-merge und --merge-only schließen sich gegenseitig aus.")
        sys.exit(1)

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)
    cfg = config.build_config(data)
    audio_cfg = data.get("audio", {})
    if args.api_url:
        audio_cfg = dict(audio_cfg, api_url=args.api_url)
        print(f"TTS-Server-Override: {args.api_url}")
    series.ensure_dirs()
    check_voice_consistency(series, cfg, audio_cfg)

    input_file = resolve_script_path(args.input_file, series)
    episode_name = args.name if args.name else episode_name_from_file(input_file)
    mode = cfg["mode"]
    section_locations = get_section_locations(input_file, data, cfg["prefix"])

    default_style = audio_cfg.get("default_style",
                                  "Read like an audiobook narrator, calm, steady, and engaging")
    chunk_max_chars = audio_cfg.get("chunk_max_chars", CHUNK_MAX_CHARS)
    pause_chunks_ms = audio_cfg.get("pause_between_chunks_ms", 250)
    pause_lines_ms = audio_cfg.get("pause_between_lines_ms", 600)
    pause_parts_ms = audio_cfg.get("pause_between_parts_ms", 4000)
    target_lufs = audio_cfg.get("target_lufs", -16.0)
    # >1 nur sinnvoll, wenn der TTS-Server tatsächlich mehrere Generierungen
    # gleichzeitig bedienen kann statt sie intern zu serialisieren (siehe
    # audio.chunk_concurrency in fabrik/core/config.py) -- Default 1 erhält
    # das bisherige rein sequenzielle Verhalten.
    chunk_concurrency = max(1, audio_cfg.get("chunk_concurrency", 1))

    print(f"Serie: {series.slug} | Modus: {mode} | Episodenname: {episode_name}")
    episode_path = os.path.join(series.output_dir, f"{episode_name}_FULL_EPISODE.mp3")
    if os.path.exists(episode_path):
        # Bereits fertig — kein laufender TTS-Server nötig. Die Metadaten-
        # Nachbearbeitung (Untertitel/Cues/Timelines/ID3-Tag) wird trotzdem
        # jedes Mal erneut versucht (billig, idempotent) statt hier sofort
        # zurückzukehren — sonst würde ein früherer Absturz NACH dem Merge
        # (der die Part-WAVs schon gelöscht hatte) die Episode für immer ohne
        # Untertitel/Timelines zurücklassen, siehe run_postprocessing().
        size_mb = os.path.getsize(episode_path) / (1024 * 1024)
        print(f"Gesamtepisode existiert bereits: {os.path.basename(episode_path)} ({size_mb:.1f} MB).")
        part_offsets = audio.load_part_offsets(episode_path)
        if part_offsets is None:
            print("  Keine gespeicherten Part-Offsets gefunden (Episode aus einem Lauf vor diesem "
                  "Feature) — nur ID3-Tagging wird nachgeholt.")
            tag_episode_from_meta(episode_path, input_file, data)
        else:
            run_postprocessing(series, cfg, data, episode_name, input_file, episode_path,
                               part_offsets, section_locations, mode)
        return

    if args.merge_only:
        # Nur Mastering + Nachbearbeitung aus bereits vorhandenen Part-WAVs —
        # KEIN TTS-Server, kein Backend-Check (läuft lokal auf dem Mac, nachdem
        # die reine Vertonung remote auf der GPU-Instanz mit --skip-merge lief
        # und die Part-WAVs + Sidecar-JSONs zurückgeholt wurden). Erzeugt
        # daraus die fertige Episoden-MP3 (inkl. Jingle), Untertitel, Timelines
        # und ID3-Tags — exakt derselbe Tail wie ein normaler Lauf, nur ohne
        # vorangehende Generierung. merge_parts_to_episode() löscht die
        # Part-WAVs danach wie gewohnt (Post-Merge-Aufräumen).
        parts = split_script(input_file)
        part_paths = [os.path.join(series.output_dir, f"{episode_name}_Part_{i:02d}.wav")
                      for i in range(1, len(parts) + 1)]
        missing = [os.path.basename(p) for p in part_paths if not os.path.exists(p)]
        if missing:
            print(f"FEHLER: --merge-only, aber {len(missing)} Part-WAV(s) fehlen: "
                  f"{', '.join(missing[:5])}{' …' if len(missing) > 5 else ''}")
            print("  Die remote Vertonung (--skip-merge) ist unvollständig oder noch nicht "
                  "heruntergeladen. Erst alle Parts erzeugen/herunterholen, dann erneut mergen.")
            sys.exit(1)
        print(f"--merge-only: mastere {len(part_paths)} Part(s) lokal → "
              f"{os.path.basename(episode_path)}")
        part_offsets = audio.merge_parts_to_episode(
            part_paths, episode_path, pause_parts_ms, target_lufs,
            intro_path=find_audio_asset(series, "intro"),
            outro_path=find_audio_asset(series, "outro"),
            transition_path=find_audio_asset(series, "transition"),
        )
        run_postprocessing(series, cfg, data, episode_name, input_file, episode_path,
                           part_offsets, section_locations, mode)
        print(f"Fertig (lokal gemastert): {os.path.basename(episode_path)}")
        return

    # --- Skript parsen und Jobs bauen (VOR dem API-Check: Formatfehler sollen
    # sofort auffallen, nicht erst wenn der Server läuft) ---
    parts = split_script(input_file)
    if mode == "drama":
        # SFX-Plan (fabrik.cli.sfx_plan): optional. Fehlt er, bleibt jeder Cue
        # unverändert und landet wie bisher auf dem Start der nächsten Zeile.
        plan = sfx_plan.load_plan(sfx_plan.plan_path(series))
        episode_num = audio.extract_episode_number(input_file, cfg["prefix"])
        try:
            drama_parts, dropped_cues, stale_cues = build_drama_jobs(
                parts, cfg["voices"], chunk_max_chars,
                plan_cues=sfx_plan.cue_lookup(plan),
                plan_assets=sfx_plan.asset_lookup(plan),
                episode_num=episode_num)
        except ScriptFormatError as e:
            print(f"FEHLER im Drama-Skript {os.path.basename(input_file)}:\n  {e}")
            sys.exit(1)
        all_jobs = [p["jobs"] for p in drama_parts]
        end_cues = [p["end_cues"] for p in drama_parts]
        cue_list = [c for jobs in all_jobs for j in jobs for c in j["cues"]]
        cue_list += [c for cues in end_cues for c in cues]
        roles = sorted({j["role"] for jobs in all_jobs for j in jobs})
        print(f"Drama-Skript ok: {len(parts)} Parts, Rollen: {', '.join(roles)}, "
              f"{len(cue_list)} SFX-Cues.")
        if plan:
            before = sum(1 for c in cue_list if c.get("placement") == "before")
            print(f"SFX-Plan aktiv ({len(plan.get('palette', []))} Palette-Assets): "
                  f"{before} Cue(s) mit Lücke vor der Zeile, {len(cue_list) - before} unter "
                  f"der Zeile, {dropped_cues} verworfen.")
            if episode_num is None:
                print("  WARNUNG: Episodennummer nicht aus dem Dateinamen ableitbar — "
                      "der Plan greift für diese Datei nicht (Cues laufen im Alt-Verhalten).")
            if stale_cues:
                print(f"  WARNUNG: {len(stale_cues)} Cue(s) stimmen nicht mehr mit dem Plan "
                      f"überein — das Skript wurde nach dem Planen geändert. Sie laufen im "
                      f"Alt-Verhalten. Kur: 'python3 -m fabrik.cli.sfx_plan --force'.")
                for part_idx, actual, planned in stale_cues[:3]:
                    print(f"    PART {part_idx}: Skript „{actual[:40]}“ ≠ Plan „{(planned or '')[:40]}“")
    else:
        part_styles = load_section_styles(input_file, data, cfg["prefix"], cfg["parts_per_section"])
        if part_styles:
            print(f"Style-Prompts geladen: {len(set(part_styles.values()))} verschiedene Styles für {len(part_styles)} Parts.")
        else:
            print("Kein Style-Mapping gefunden — nutze Standard-Style für alle Parts.")
        all_jobs = build_narration_jobs(parts, part_styles, default_style, chunk_max_chars)
        end_cues = [[] for _ in parts]

    # --- Backend + Stimmen ---
    backend = build_backend(audio_cfg)
    print(f"Prüfe TTS-Backend ({backend.base_url}) ...")
    # Direkt nach einem TTS-Start (webui/tts_control.py::start_tts wartet nur,
    # bis der PORT offen ist) kann der Health-Endpoint noch kurz mit Fehlern
    # antworten, während das Modell selbst noch lädt — ein einzelner Check
    # direkt danach hätte die ganze Episode fälschlich als "Server tot"
    # abgebrochen. Ein paar Sekunden Geduld statt sofortigem Abbruch.
    api_ready = backend.check_api()
    if not api_ready:
        for attempt in range(1, 4):
            print(f"  API antwortet noch nicht (Versuch {attempt}/4) — warte 10s ...")
            time.sleep(10)
            if backend.check_api():
                api_ready = True
                break
    if not api_ready:
        if audio_cfg.get("backend", "rest") == "kokoro":
            print("FEHLER: Kokoro-Modell konnte nicht geladen werden.")
            print("  Tipp: 'pip install mlx-audio' und 'audio.model_path' in episodes.json prüfen.")
        else:
            print("FEHLER: API nicht erreichbar. Ist der Qwen3-TTS Server gestartet?")
            print("  Tipp: Port prüfen und in episodes.json unter 'audio.api_url' eintragen.")
        # Exit != 0: "Episode nicht erzeugt" ist ein echter Fehlschlag — im
        # --skip-merge-Modus gibt es keine fehlende MP3 als Signal, also muss
        # der Exit-Code batch.py das Scheitern melden (sonst Falsch-Erfolg).
        sys.exit(1)

    if mode == "drama":
        resolved_voices, problems = resolve_drama_voices(backend, cfg["voices"], audio_cfg)
        if problems:
            print("FEHLER: Stimmen aus dem voices-Mapping nicht auflösbar:")
            for p in problems:
                print(f"  - {p}")
            print("  Stimmen in episodes.json unter 'voices.<ROLLE>.voice' anpassen.")
            sys.exit(1)
        print(f"API erreichbar. {len(resolved_voices)} Rollen-Stimmen aufgelöst.")
    else:
        voice_name = audio_cfg.get("voice", "MyVoice")
        kind, voice_id, resolved_seed = backend.resolve_voice(voice_name, seed=audio_cfg.get("seed"))
        if kind is None:
            print(f"FEHLER: Stimme '{voice_name}' nicht gefunden.")
            if voice_id:
                print(f"  Details: {', '.join(voice_id)}")
            print("  Stimme in episodes.json unter 'audio.voice' anpassen.")
            sys.exit(1)
        resolved_voices = {NARRATOR_ROLE: (kind, voice_id, resolved_seed)}
        if kind == "prompt":
            print(f"API erreichbar. Geklonte Stimme: '{voice_name}' (prompt_id {voice_id[:8]}…)")
            if part_styles:
                print("  HINWEIS: Diese API-Version unterstützt keine Style-Anweisungen für geklonte")
                print("  Stimmen — die section_styles aus episodes.json werden ignoriert.")
            if resolved_seed is not None:
                print(f"  Seed {resolved_seed} aktiv (Streaming-Endpunkt, gegen Timbre-Drift über Chunks).")
        elif kind == "clone":
            print(f"API erreichbar. Voice-Clone-Backend aktiv (Referenzaudio: {audio_cfg.get('ref_audio')})")
            if part_styles:
                print("  HINWEIS: Voice Clone unterstützt kein 'instruct' — die section_styles")
                print("  aus episodes.json werden ignoriert.")
        elif kind == "kokoro":
            print(f"Kokoro-MLX-Stimme: '{voice_name}' (kein Style/instruct unterstützt)")
            if part_styles:
                print("  HINWEIS: Kokoro folgt keinen Stilanweisungen — die section_styles")
                print("  aus episodes.json werden ignoriert.")
        else:
            print(f"API erreichbar. Built-in-Stimme: '{voice_name}' (Styles aktiv via 'instruct')")

    # Baseline erst JETZT festschreiben — Stimmen sind nachweislich aufgelöst,
    # dieser Lauf wird also tatsächlich mit dieser Konfiguration rendern
    # (siehe commit_voice_manifest()-Docstring).
    commit_voice_manifest(series, cfg, audio_cfg)

    total_chunks = sum(len(jobs) for jobs in all_jobs)
    print(f"{len(parts)} Parts / {total_chunks} Chunks (~{chunk_max_chars} Zeichen je Chunk).\n")

    # --- Render-Schleife (identisch für beide Modi: ein Job = ein Chunk) ---
    os.makedirs(series.checkpoint_dir, exist_ok=True)
    # cues_dir hält neben SFX-/Sprecher-Daten (Drama) auch die
    # Untertitel-Zwischendaten — wird in beiden Modi gebraucht.
    os.makedirs(series.cues_dir, exist_ok=True)

    skipped = 0
    success = 0
    failed = []
    chunks_done = 0
    global_start = time.time()
    # Parts als WAV zwischenspeichern: MP3-kodiert wird nur einmal, beim
    # Export der fertigen Gesamtepisode (kein Generationsverlust). Die volle
    # Liste steht schon vor jeder Generierung fest (reine idx-Ableitung) —
    # Phase B (Zusammenbau) braucht sie unabhängig vom Fortschritt aus Phase A.
    part_paths = [os.path.join(series.output_dir, f"{episode_name}_Part_{idx:02d}.wav")
                  for idx in range(1, len(parts) + 1)]
    # ETA-Basis getrennt von chunks_done: gen_time/gen_count zählen NUR echte
    # generate_chunk()-Aufrufe. Checkpoint-Reads (~0s) dürfen den Schnitt
    # nicht verwässern, sonst ist die ETA nach einem fortgesetzten Lauf mit
    # vielen Checkpoints erst mal deutlich zu optimistisch.
    gen_time = 0.0
    gen_count = 0

    # Batches über Part-Grenzen hinweg bis chunk_concurrency füllen statt nur
    # innerhalb eines Parts (Parts liegen typischerweise deutlich unter
    # chunk_concurrency, siehe cloud/README.md) — deshalb zwei Phasen statt
    # einer Schleife: Phase A generiert ALLE Chunks aller Parts in einen
    # gemeinsamen Pool, Phase B baut danach jeden Part einzeln aus den
    # fertigen Segmenten zusammen (assemble_part, reine Funktion von
    # jobs/segments — unabhängig davon, wann/in welcher Reihenfolge die
    # Chunks generiert wurden).
    already_done_parts = set()
    segments_by_part = {idx: {} for idx in range(1, len(parts) + 1)}
    part_failed = {idx: False for idx in range(1, len(parts) + 1)}
    pending_pool = []
    batching = hasattr(backend, "generate_chunk_batch") and chunk_concurrency > 1

    def commit_result(part_idx, c_idx, job, ckpt, segment, elapsed):
        nonlocal chunks_done, gen_time, gen_count
        chunks_done += 1
        if segment:
            if not job.get("silence_ms"):
                gen_time += elapsed
                gen_count += 1
            segment.export(ckpt, format="wav")
            segments_by_part[part_idx][c_idx] = segment
        else:
            print(f"\n  FEHLER bei Chunk {c_idx}: '{job['text'][:60]}'")
            part_failed[part_idx] = True
        avg = gen_time / gen_count if gen_count > 0 else None
        eta = textproc.format_eta((total_chunks - chunks_done) * avg) if avg is not None else "?"
        label = f"[{job['role']}] " if mode == "drama" else ""
        part_len = len(all_jobs[part_idx - 1])
        msg = f"  Part {part_idx:02d} Chunk {c_idx}/{part_len} {label}| {chunks_done}/{total_chunks} | ETA: {eta}"
        print(msg.ljust(90), end="\r")

    # --- Phase A: Chunk-Generierung ---
    for idx, jobs in enumerate(all_jobs, start=1):
        part_path = part_paths[idx - 1]
        filename = os.path.basename(part_path)

        if os.path.exists(part_path):
            size = os.path.getsize(part_path) // 1024
            print(f"[{idx}/{len(parts)}] Übersprungen: {filename} ({size} KB)")
            chunks_done += len(jobs)
            skipped += 1
            already_done_parts.add(idx)
            continue

        print(f"[{idx}/{len(parts)}] {filename} – {len(jobs)} Chunks"
              + (f" (Batch bis {chunk_concurrency})" if batching
                 else f" (bis zu {chunk_concurrency} gleichzeitig)" if chunk_concurrency > 1 else ""))

        # Checkpoints + reine Interpunktions-Chunks (Stille, nie ans Backend
        # — siehe textproc.is_speakable-Docstring) zuerst synchron erledigen,
        # keine Backend-Last. Rest sammelt sich im teilenweiten pending_pool
        # für Batch/Thread-Pool.
        for c_idx, job in enumerate(jobs, start=1):
            ckpt = checkpoint_path(series.checkpoint_dir, episode_name, idx, c_idx)
            if os.path.exists(ckpt):
                segment = AudioSegment.from_file(ckpt, format="wav")
                segments_by_part[idx][c_idx] = segment
                chunks_done += 1
                avg = gen_time / gen_count if gen_count > 0 else None
                eta = textproc.format_eta((total_chunks - chunks_done) * avg) if avg is not None else "?"
                msg = f"  Part {idx:02d} Chunk {c_idx}/{len(jobs)} | {chunks_done}/{total_chunks} | ETA: {eta} [checkpoint]"
                print(msg.ljust(90), end="\r")
            elif job.get("silence_ms"):
                commit_result(idx, c_idx, job, ckpt, AudioSegment.silent(duration=job["silence_ms"]), 0.0)
            else:
                pending_pool.append((idx, c_idx, job, ckpt))

    # Batching bevorzugt: EIN Forward-Pass für mehrere Chunks statt N
    # sequenzieller Calls, die serverseitig ohnehin denselben CUDA-
    # Default-Stream teilen (siehe cloud/README.md — Threads allein
    # brachten dort NULL Speedup, echtes Batching ~13x). ThreadPool
    # bleibt Fallback für Backends ohne generate_chunk_batch (RestBackend/
    # KokoroBackend auf dem Mac) oder gemischte kind-Batches (z.B.
    # Voice-Clone-Rollen neben Built-in-Speakern).
    batchable, rest = [], []
    for p in pending_pool:
        _part_idx, _c_idx, job, _ckpt = p
        single = [(resolved_voices[job["role"]], job["text"], job["style"], job["speed"])]
        if batching and backend.supports_batch(single):
            batchable.append(p)
        else:
            rest.append(p)

    # Nach Stimm-Art bucketen, NICHT nur nach chunk_concurrency-
    # Fenstergröße schneiden: ein Batch-Call bedient serverseitig EIN
    # Modell (CustomVoice ODER Base). Ein Skript wechselt aber ständig
    # zwischen Rollen (z.B. Built-in-Speaker REID neben Voice-Clone-
    # NARRATOR) — ungebucketes Windowing würde gemischte Kinds in ein
    # Fenster packen und dem falschen Endpoint zuordnen (kind wird nur
    # vom ERSTEN Job im Fenster abgeleitet, siehe generate_chunk_batch).
    # Die Fenster dürfen jetzt Part-Grenzen überschreiten — das ist der
    # eigentliche Zweck des gemeinsamen pending_pool.
    by_kind = {}
    for p in batchable:
        _part_idx, _c_idx, job, _ckpt = p
        by_kind.setdefault(resolved_voices[job["role"]][0], []).append(p)

    for kind, kind_batchable in by_kind.items():
        n_windows = (len(kind_batchable) + chunk_concurrency - 1) // chunk_concurrency
        for win_idx, batch_start in enumerate(range(0, len(kind_batchable), chunk_concurrency), start=1):
            batch = kind_batchable[batch_start: batch_start + chunk_concurrency]
            batch_jobs = [(resolved_voices[job["role"]], job["text"], job["style"], job["speed"])
                          for _part_idx, _c_idx, job, _ckpt in batch]
            # Eigene Zeile VOR dem Call: ein voller Batch braucht am Stück
            # Minuten (Kaltstart der Instanz noch mehr) und der Call selbst
            # gibt bis zum Ende nichts aus — ohne die Zeile sieht der Lauf
            # im WebUI-Log solange wie ein Hänger aus.
            print(f"\n  Batch {win_idx}/{n_windows} ({kind}, {len(batch)} Chunks) ...".ljust(90))
            start = time.time()
            batch_segments, batch_error = backend.generate_chunk_batch(batch_jobs)
            per_item_elapsed = (time.time() - start) / len(batch)
            for (part_idx, c_idx, job, ckpt), segment in zip(batch, batch_segments):
                if segment is None and batch_error:
                    print(f"\n  Batch-Fehler: {batch_error}")
                if segment is not None:
                    # Gleiche Nachbearbeitung wie der Einzel-Pfad
                    # (pipeline.generate_chunk): Trim, Plausibilität,
                    # Loudness — sonst klingen gebatchte Chunks anders als
                    # lokal generierte und ein schlechter Sample würde
                    # ungeprüft gecheckpointet. Verdächtige Segmente werden
                    # einzeln nachgeneriert (voller Retry-Pfad) — selten
                    # genug, dass der sequenzielle Nachschuss egal ist.
                    processed, reason = audio.postprocess_chunk(segment, job["text"], speed=job["speed"])
                    if processed is None:
                        print(f"\n  Batch-Chunk verdächtig ({reason}) – generiere einzeln nach ...")
                        processed = audio.generate_chunk(backend, resolved_voices[job["role"]],
                                                         job["text"], style=job["style"], speed=job["speed"])
                    segment = processed
                commit_result(part_idx, c_idx, job, ckpt, segment, per_item_elapsed)

    if rest:
        def render_one(job):
            """Läuft in einem Pool-Thread — reine I/O-wartende Backend-
            Calls, das GIL wird währenddessen freigegeben. Bringt bei
            diesem Setup KEINEN Durchsatzgewinn (Backend serialisiert
            ohnehin intern, siehe cloud/README.md), ist aber unschädlich
            und der einzige Pfad für Backends ohne Batch-Endpoint."""
            start = time.time()
            segment = audio.generate_chunk(backend, resolved_voices[job["role"]],
                                           job["text"], style=job["style"], speed=job["speed"])
            return segment, time.time() - start

        max_workers = min(chunk_concurrency, len(rest))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_job = {pool.submit(render_one, job): (part_idx, c_idx, job, ckpt)
                             for part_idx, c_idx, job, ckpt in rest}
            # as_completed statt Original-Reihenfolge: Ergebnisse können
            # durcheinander reinkommen, landen aber über (part_idx, c_idx) in
            # segments_by_part -- das Zusammensetzen in Phase B bleibt dadurch
            # unverändert streng in Original-Skriptreihenfolge.
            for future in concurrent.futures.as_completed(future_to_job):
                part_idx, c_idx, job, ckpt = future_to_job[future]
                segment, elapsed = future.result()
                commit_result(part_idx, c_idx, job, ckpt, segment, elapsed)

    print()

    # --- Phase B: Zusammenbau ---
    for idx, jobs in enumerate(all_jobs, start=1):
        if idx in already_done_parts:
            continue
        part_path = part_paths[idx - 1]
        filename = os.path.basename(part_path)
        segments = [segments_by_part[idx].get(c_idx) for c_idx in range(1, len(jobs) + 1)]

        if not part_failed[idx] and segments:
            assemble_part(idx, jobs, segments, end_cues[idx - 1], part_path, filename, series, episode_name,
                          mode, pause_lines_ms, pause_chunks_ms)
            success += 1
        else:
            failed.append(idx)

    total_time = time.time() - global_start
    print(f"\nAlle Parts fertig in {textproc.format_eta(total_time)}!")
    print(f"  Neu generiert: {success} | Übersprungen: {skipped} | Fehlgeschlagen: {len(failed)}")

    if failed:
        print(f"  Fehlgeschlagene Parts: {failed} – Script neu starten zum Fortsetzen.")
        print(f"  Merge zur Gesamtepisode übersprungen (erst wenn alle Parts vorhanden sind).")
        # Exit != 0, damit ein aufrufendes batch.py den Teilausfall zuverlässig
        # erkennt und die Episode in die Retry-Runde nimmt — im Normalmodus
        # signalisiert die fehlende MP3 das Scheitern, im --skip-merge-Modus
        # (keine MP3) MUSS der Exit-Code es tun. Fertige Parts/Checkpoints
        # bleiben liegen, ein Re-Run setzt fort.
        sys.exit(1)

    if args.skip_merge:
        # Reine Vertonung fertig (GPU-Arbeit) — Merge/Mastering/Nachbearbeitung
        # bewusst NICHT hier, sondern lokal via --merge-only nach dem Download.
        # Die Part-WAVs bleiben liegen (merge_parts_to_episode hätte sie sonst
        # gelöscht), damit sie zurückgeholt und lokal verarbeitet werden können.
        print(f"\n--skip-merge: {success} Part(s) erzeugt, {skipped} übersprungen — "
              f"KEIN Merge/Mastering.")
        print(f"  Part-WAVs + Sidecar-JSONs liegen in {series.output_dir}/ bereit für den "
              f"Download + lokales --merge-only.")
        return

    # Optionale Serien-Audio-Assets: intro.mp3 / outro.mp3 / transition.mp3
    # im Serienordner werden automatisch eingesetzt (Jingle am Anfang/Ende,
    # Sting statt purer Stille zwischen den Szenen).
    part_offsets = audio.merge_parts_to_episode(
        part_paths, episode_path, pause_parts_ms, target_lufs,
        intro_path=find_audio_asset(series, "intro"),
        outro_path=find_audio_asset(series, "outro"),
        transition_path=find_audio_asset(series, "transition"),
    )
    run_postprocessing(series, cfg, data, episode_name, input_file, episode_path,
                       part_offsets, section_locations, mode)


if __name__ == "__main__":
    main()
