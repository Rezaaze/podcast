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
import json
import os
import re
import shutil
import sys
import time

from pydub import AudioSegment

from fabrik.audio import pipeline as audio
from fabrik.audio.tts_backends import build_backend
from fabrik.core import config, paths, textproc
from fabrik.writing.script_parser import ScriptFormatError, parse_drama_part

FADE_MS = 15
NARRATOR_ROLE = "__narrator__"

# Fallbacks — werden in main() aus episodes.json überschrieben
CHUNK_MAX_CHARS = 350


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
            jobs.append({"text": chunk, "role": NARRATOR_ROLE, "style": style,
                         "speed": None, "line_start": False, "cues": []})
        all_jobs.append(jobs)
    return all_jobs


def build_drama_jobs(parts, voices_cfg, chunk_max_chars):
    """Drama: pro Skriptzeile Stimme/Style/Speed; SFX-Cues hängen am nächsten
    Job (bzw. am Part-Ende, wenn danach nichts mehr kommt)."""
    all_jobs = []
    for idx, part_text in enumerate(parts, start=1):
        items = parse_drama_part(part_text, voices=voices_cfg, part_label=f"PART {idx}")
        jobs = []
        pending_cues = []
        for item in items:
            if item.kind == "sfx":
                pending_cues.append(item.description)
                continue
            if item.kind == "note":
                continue  # reine Autoren-Buchhaltung — nie vertont, nie gecuet
            role_cfg = voices_cfg[item.speaker]
            style = item.style or role_cfg.get("default_style")
            speed = item.speed if item.speed is not None else role_cfg.get("speed")
            chunks = textproc.chunk_sentences(textproc.split_into_sentences(item.text), chunk_max_chars)
            for c_i, chunk in enumerate(chunks):
                jobs.append({"text": chunk, "role": item.speaker, "style": style,
                             "speed": speed, "line_start": c_i == 0,
                             "cues": pending_cues if c_i == 0 else []})
                if c_i == 0:
                    pending_cues = []
        all_jobs.append({"jobs": jobs, "end_cues": pending_cues})
    return all_jobs


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
    narration als auch drama)."""
    match = re.search(rf'{re.escape(prefix)}(\d+)', os.path.basename(input_file), re.IGNORECASE)
    if not match:
        return None
    ep_idx = int(match.group(1)) - 1
    episodes = data.get("episodes", [])
    if ep_idx < 0 or ep_idx >= len(episodes):
        return None
    return episodes[ep_idx].get("section_locations")


def build_location_timeline(section_locations, parts_per_section, part_offsets, episode_duration_ms):
    """Ordnet jedem PART (über part_offsets, dieselbe Zeitquelle wie
    build_scene_presence) seinen Section-Index zu (parts_per_section PARTs
    pro Section) und schlägt darüber section_locations[section_idx] nach.
    'null' in section_locations heißt 'Hintergrund bleibt wie zuvor' — der
    zuletzt aktive Ort wird fortgeschrieben, nicht auf 'kein Ort' zurück-
    gesetzt. Konsekutive PARTs mit demselben Ort werden zu einer Zeitspanne
    zusammengelegt, damit die Timeline nicht bei jedem Part-Wechsel unnötig
    einen neuen Abschnitt aufmacht, wenn zwei Sections denselben Ort teilen."""
    if not section_locations:
        return []
    boundaries = part_offsets + [episode_duration_ms]
    spans = []
    current_location = None
    for i in range(len(part_offsets)):
        section_idx = i // parts_per_section
        if section_idx < len(section_locations) and section_locations[section_idx]:
            current_location = section_locations[section_idx]
        if current_location is None:
            continue
        start, end = boundaries[i], boundaries[i + 1]
        if spans and spans[-1]["location"] == current_location and spans[-1]["end_ms"] == start:
            spans[-1]["end_ms"] = end
        else:
            spans.append({"start_ms": start, "end_ms": end, "location": current_location})
    return spans


def write_location_timeline(episode_name, section_locations, parts_per_section,
                            part_offsets, episode_path, output_dir):
    """Schreibt <Episode>_LOCATIONS.json: welcher Ort (Key aus episodes.json
    'locations') wann aktiv ist, damit Lolfi beim Video-Rendern automatisch
    den passenden Hintergrund zeigt. Eigene Datei statt Erweiterung von
    _SPEAKERS.json, da Locations modusunabhängig sind — _SPEAKERS.json gibt
    es nur im Drama-Modus."""
    if not section_locations:
        return
    episode_duration_ms = len(AudioSegment.from_file(episode_path))
    spans = build_location_timeline(section_locations, parts_per_section, part_offsets, episode_duration_ms)
    if not spans:
        return
    json_path = os.path.join(output_dir, f"{episode_name}_LOCATIONS.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"episode": episode_name, "locations": spans}, f, ensure_ascii=False, indent=1)
    print(f"Location-Timeline geschrieben: {os.path.basename(json_path)} ({len(spans)} Abschnitt(e))")


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
    """Optionales Audio-Asset der Serie: series/<slug>/<stem>.mp3|wav|...
    (intro, outro, transition) — None, wenn nicht vorhanden."""
    for ext in AUDIO_ASSET_EXTS:
        candidate = os.path.join(series.root, f"{stem}{ext}")
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
    title, description = audio.parse_meta_file(meta_path)
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
            write_speaker_timeline(series, episode_name, part_offsets, num_parts, series.output_dir)
        except Exception as e:
            print(f"  WARNUNG: Sprecher-Timeline fehlgeschlagen ({e}) — Lauf erneut starten, um es nachzuholen.")
    try:
        write_episode_subtitles(series, episode_name, part_offsets, num_parts,
                                episode_path, drama=(mode == "drama"))
    except Exception as e:
        print(f"  WARNUNG: Untertitel fehlgeschlagen ({e}) — Lauf erneut starten, um es nachzuholen.")
    try:
        write_location_timeline(episode_name, section_locations, cfg["parts_per_section"],
                                part_offsets, episode_path, series.output_dir)
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


def main():
    parser = argparse.ArgumentParser(description="Skript → gemasterte Episoden-MP3")
    parser.add_argument("input_file", help="Skript-Datei (Pfad oder Dateiname in scripts/ der Serie)")
    parser.add_argument("--name", default=None, help="Name der Episode (überschreibt Auto-Erkennung)")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)
    cfg = config.build_config(data)
    audio_cfg = data.get("audio", {})
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

    # --- Skript parsen und Jobs bauen (VOR dem API-Check: Formatfehler sollen
    # sofort auffallen, nicht erst wenn der Server läuft) ---
    parts = split_script(input_file)
    if mode == "drama":
        try:
            drama_parts = build_drama_jobs(parts, cfg["voices"], chunk_max_chars)
        except ScriptFormatError as e:
            print(f"FEHLER im Drama-Skript {os.path.basename(input_file)}:\n  {e}")
            sys.exit(1)
        all_jobs = [p["jobs"] for p in drama_parts]
        end_cues = [p["end_cues"] for p in drama_parts]
        num_cues = sum(len(j["cues"]) for jobs in all_jobs for j in jobs) + sum(len(c) for c in end_cues)
        roles = sorted({j["role"] for jobs in all_jobs for j in jobs})
        print(f"Drama-Skript ok: {len(parts)} Parts, Rollen: {', '.join(roles)}, {num_cues} SFX-Cues.")
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
        return

    if mode == "drama":
        resolved_voices, problems = resolve_drama_voices(backend, cfg["voices"], audio_cfg)
        if problems:
            print("FEHLER: Stimmen aus dem voices-Mapping nicht auflösbar:")
            for p in problems:
                print(f"  - {p}")
            print("  Stimmen in episodes.json unter 'voices.<ROLLE>.voice' anpassen.")
            return
        print(f"API erreichbar. {len(resolved_voices)} Rollen-Stimmen aufgelöst.")
    else:
        voice_name = audio_cfg.get("voice", "MyVoice")
        kind, voice_id, resolved_seed = backend.resolve_voice(voice_name, seed=audio_cfg.get("seed"))
        if kind is None:
            print(f"FEHLER: Stimme '{voice_name}' nicht gefunden.")
            if voice_id:
                print(f"  Details: {', '.join(voice_id)}")
            print("  Stimme in episodes.json unter 'audio.voice' anpassen.")
            return
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
    part_paths = []
    # ETA-Basis getrennt von chunks_done: gen_time/gen_count zählen NUR echte
    # generate_chunk()-Aufrufe. Checkpoint-Reads (~0s) dürfen den Schnitt
    # nicht verwässern, sonst ist die ETA nach einem fortgesetzten Lauf mit
    # vielen Checkpoints erst mal deutlich zu optimistisch.
    gen_time = 0.0
    gen_count = 0

    for idx, jobs in enumerate(all_jobs, start=1):
        filename = f"{episode_name}_Part_{idx:02d}.wav"
        # Parts als WAV zwischenspeichern: MP3-kodiert wird nur einmal,
        # beim Export der fertigen Gesamtepisode (kein Generationsverlust).
        part_path = os.path.join(series.output_dir, filename)
        part_paths.append(part_path)

        if os.path.exists(part_path):
            size = os.path.getsize(part_path) // 1024
            print(f"[{idx}/{len(parts)}] Übersprungen: {filename} ({size} KB)")
            chunks_done += len(jobs)
            skipped += 1
            continue

        print(f"[{idx}/{len(parts)}] {filename} – {len(jobs)} Chunks")

        segments = []
        part_failed = False

        for c_idx, job in enumerate(jobs, start=1):
            ckpt = checkpoint_path(series.checkpoint_dir, episode_name, idx, c_idx)

            if os.path.exists(ckpt):
                segment = AudioSegment.from_file(ckpt, format="wav")
                chunks_done += 1
                avg = gen_time / gen_count if gen_count > 0 else None
                eta = textproc.format_eta((total_chunks - chunks_done) * avg) if avg is not None else "?"
                msg = f"  Chunk {c_idx}/{len(jobs)} | {chunks_done}/{total_chunks} | ETA: {eta} [checkpoint]"
                print(msg.ljust(90), end="\r")
                segments.append(segment)
                continue

            # ETA für den GERADE STARTENDEN Chunk beruht auf dem Schnitt der
            # bisher abgeschlossenen echten Generierungen — chunks_done wird
            # erst NACH generate_chunk() erhöht.
            avg = gen_time / gen_count if gen_count > 0 else None
            eta = textproc.format_eta((total_chunks - chunks_done) * avg) if avg is not None else "?"
            label = f"[{job['role']}] " if mode == "drama" else ""
            msg = f"  Chunk {c_idx}/{len(jobs)} {label}| {chunks_done + 1}/{total_chunks} | ETA: {eta}"
            print(msg.ljust(90), end="\r")

            chunk_start = time.time()
            segment = audio.generate_chunk(backend, resolved_voices[job["role"]],
                                           job["text"], style=job["style"], speed=job["speed"])

            chunks_done += 1
            if segment:
                gen_time += time.time() - chunk_start
                gen_count += 1
                segment.export(ckpt, format="wav")
                segments.append(segment)
            else:
                print(f"\n  FEHLER bei Chunk {c_idx}: '{job['text'][:60]}'")
                part_failed = True
                break

        print()

        if not part_failed and segments:
            # Zusammensetzen + Cue-Offsets protokollieren: Zeilenwechsel
            # (Sprecherwechsel) bekommen eine längere Pause als Chunk-Grenzen.
            combined = AudioSegment.empty()
            cues = []
            speaker_spans = []
            sub_records = []
            for i, (job, seg) in enumerate(zip(jobs, segments)):
                if i > 0:
                    gap = pause_lines_ms if job["line_start"] else pause_chunks_ms
                    combined = combined + AudioSegment.silent(duration=gap)
                for desc in job["cues"]:
                    cues.append({"ms": len(combined), "description": desc})
                span_start = len(combined)
                combined = combined + seg.fade_in(FADE_MS).fade_out(FADE_MS)
                speaker_spans.append({"start_ms": span_start, "end_ms": len(combined),
                                      "role": job["role"], "style": job["style"] or ""})
                sub_records.append({"start_ms": span_start, "end_ms": len(combined),
                                    "text": job["text"], "role": job["role"]})
            for desc in end_cues[idx - 1]:
                cues.append({"ms": len(combined), "description": desc})

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
            success += 1
        else:
            failed.append(idx)

    total_time = time.time() - global_start
    print(f"\nAlle Parts fertig in {textproc.format_eta(total_time)}!")
    print(f"  Neu generiert: {success} | Übersprungen: {skipped} | Fehlgeschlagen: {len(failed)}")

    if failed:
        print(f"  Fehlgeschlagene Parts: {failed} – Script neu starten zum Fortsetzen.")
        print(f"  Merge zur Gesamtepisode übersprungen (erst wenn alle Parts vorhanden sind).")
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
