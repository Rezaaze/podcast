#!/usr/bin/env python3
"""Kuratiert die [SFX: ...]-Cues einer Serie per Claude zu einem Sounddesign-
Plan — der Schritt, der zwischen "Claude schreibt einen Cue ins Skript" und
"ffmpeg legt eine MP3 auf Millisekunde X" bisher fehlte.

Verwendung:
  python3 -m fabrik.cli.sfx_plan                  # aktuelle Serie
  python3 -m fabrik.cli.sfx_plan --series facades
  python3 -m fabrik.cli.sfx_plan --force          # ALLES neu planen (Handkorrekturen weg)
  (--series <slug> wie überall; Standard: data/series/LATEST)

Ohne --force ist der Lauf inkrementell: ein vorhandener Plan wird um die
Episoden ergänzt, die ihm fehlen (neue Skripte, frühere Fehlschläge) —
bereits geplante Episoden und Handkorrekturen bleiben unangetastet.

Zwei Aufgaben, die vorher niemand hatte:

1. PALETTE — die serienweit eindeutigen Cue-Texte werden zu wenigen
   kanonischen Assets geclustert ("a door creaking open, slow" / "the door
   creaks" / "a slow creak of the front door" -> EIN Asset), jedes mit einem
   sauber geschriebenen ElevenLabs-Prompt. Ersetzt das Fuzzy-Wortmengen-
   Matching in fabrik/writing/sfx_library.py als HAUPTpfad (dort bleibt es
   als Notnagel für Serien ohne Plan).

2. CUE-ANNOTATION — pro Cue:
   - keep=false für alles, was gar kein Geräusch ist ("a beat, tension held",
     "Elias exhales, shaky"): wird nie generiert, nie gemischt.
   - placement "before" (Sound feuert in einer eingefügten Lücke VOR der
     nächsten Zeile — Tür knallt, dann die Reaktion) oder "under" (Sound
     läuft unter der Zeile, z.B. Regen, Motor). Vorher landete JEDER Cue auf
     dem ersten Wort der nächsten Zeile.
   - gain — ein Türknall und ein raschelndes Blatt lagen vorher beide auf
     derselben Lautstärke.

Ausgabe: stages/02_scripts/output/SFX_PLAN.json (serienweit, aus den
Skripten abgeleitet, deshalb bei den Skripten). Konsumenten:
  - podcast_maker/batch: Platzierung (Lücke), Drop, gain/asset in die
    <Episode>_SFX_CUES.json
  - sfx_assets: generiert die Palette statt roher Cue-Texte

Von Hand editierbar (Review-Gate im MWP-Sinn) — placement/gain/keep/prompt
anpassen, dann vertonen. Ohne SFX_PLAN.json verhält sich die gesamte
Pipeline exakt wie vorher.

Claude bekommt NICHT die kompletten Skripte, sondern ein durchnummeriertes
Cue-Inventar mit je einer Zeile Kontext davor/danach und antwortet mit
Cue-INDIZES (Muster wie highlight_clips.py) — kompakt genug für eine ganze
Serie in einem Call und strukturell unfähig, Cues zu erfinden.

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
from fabrik.core.textproc import sfx_asset_hash
from fabrik.writing.script_parser import ScriptFormatError, parse_drama_part
from fabrik.writing.script_writer import MAX_RETRIES, RETRY_DELAY

# Wie highlight_clips: das Prompt ist groß (alle Cues der Serie), die Antwort
# klein — die Zeit geht ins Prompt-Processing, nicht in den Output.
TIMEOUT_SECONDS = 600

PLAN_FILENAME = "SFX_PLAN.json"

PLACEMENTS = ("before", "under")
DEFAULT_PLACEMENT = "under"   # = das alte Verhalten (Cue auf dem Zeilenstart)
DEFAULT_GAIN = 0.35           # = Lolfis bisheriges ONESHOT_SFX_VOLUME
MIN_GAIN, MAX_GAIN = 0.05, 1.0
MIN_ASSET_SECONDS, MAX_ASSET_SECONDS = 0.5, 10.0
MAX_KEPT_CUES_PER_PART = 5    # Dichte-Bremse: mehr als das klingt nach Hörspiel-Karaoke
CONTEXT_CHARS = 70            # Kontextzeile vor/nach dem Cue im Prompt

# Ambience: statt EINER Schleife pro Ort für die ganze Serie bekommt jeder Ort
# wenige Stimmungs-Varianten (leerer Mittag vs. Sturmnacht), die die Sections
# unter sich aufteilen. Mehr als das ist Verschwendung — die Varianten müssen
# über Episoden hinweg wiederkehren, sonst klingt kein Ort wie ein Ort.
MAX_AMBIENCE_VARIANTS_PER_LOCATION = 3

# Wiederholungs-Syntax am Cue-Ende ("gunshot x3, 0.4s apart") — hier NUR zum
# Abstreifen fürs Prompt/Asset-Matching. Expandiert wird sie nach wie vor in
# podcast_maker.py::expand_sfx_cue (dort hängt sie an den ms-Offsets).
# Muster identisch zu podcast_maker._SFX_REPEAT_RE.
_REPEAT_RE = re.compile(
    r'(?i)\s*[x×]\s*(\d+)\s*(?:,\s*([\d.]+)\s*s(?:ec(?:onds)?)?\s*apart)?\s*$'
)


def plan_path(series):
    return os.path.join(series.scripts_dir, PLAN_FILENAME)


def strip_repeat(desc):
    """'gunshot x3, 0.4s apart' -> ('gunshot', 3). Der Plan arbeitet auf dem
    bereinigten Text: dieselbe Tür soll dasselbe Asset bekommen, egal ob sie
    einmal oder dreimal knallt."""
    match = _REPEAT_RE.search(desc)
    if not match:
        return desc, 1
    return desc[:match.start()].strip() or desc, max(1, int(match.group(1)))


def load_plan(path):
    """Plan von der Platte; None bei fehlender/kaputter Datei. Konsumenten
    (podcast_maker, sfx_assets) rufen das hier — der Plan ist optional, ein
    unlesbarer Plan darf nie eine Vertonung töten."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("cues"), list):
        return None
    return data


def cue_lookup(plan):
    """(episode, part, index_in_part) -> Cue-Eintrag. Der Schlüssel ist
    bewusst die POSITION, nicht der Text: derselbe Cue-Text kann in einem
    Part mehrfach vorkommen und dabei unterschiedlich platziert sein."""
    if not plan:
        return {}
    return {
        (c["episode"], c["part"], c["index_in_part"]): c
        for c in plan.get("cues", [])
        if all(k in c for k in ("episode", "part", "index_in_part"))
    }


def asset_lookup(plan):
    """asset_key -> Palette-Eintrag."""
    if not plan:
        return {}
    return {a["key"]: a for a in plan.get("palette", []) if a.get("key")}


def ambience_variants(plan):
    """Alle geplanten Ambience-Varianten (Quelle für location_ambience)."""
    if not plan:
        return []
    return (plan.get("ambience") or {}).get("variants", [])


def section_ambience_lookup(plan):
    """(episode, section_index) -> Varianten-Key. podcast_maker hängt ihn an
    die Location-Spans, damit Lolfi pro Szene die passende Stimmung lädt."""
    if not plan:
        return {}
    entries = (plan.get("ambience") or {}).get("sections", [])
    return {
        (e["episode"], e["section"]): e["variant"]
        for e in entries
        if "episode" in e and "section" in e and e.get("variant")
    }


def collect_sections(data):
    """Alle Sections mit einem Ort — [{episode, section, location, text}].
    Der Section-Einzeiler aus episodes.json trägt Ort UND dramatische Lage
    ("STUDY — Tobias und Julia sortieren Werners Papiere ...") und ist damit
    genau die Quelle, aus der sich eine Stimmung ableiten lässt. Skripte
    braucht es dafür nicht."""
    out = []
    for ep_num, episode in enumerate(data.get("episodes", []), start=1):
        locs = episode.get("section_locations") or []
        for sec_idx, text in enumerate(episode.get("sections", [])):
            location = locs[sec_idx] if sec_idx < len(locs) else None
            if not location:
                continue  # null = "Ort bleibt wie zuvor" (build_location_timeline)
            out.append({"episode": ep_num, "section": sec_idx,
                        "location": location, "text": text})
    return out


def collect_cues(series, data, prefix):
    """Alle SFX-Cues aller vorhandenen Drama-Skripte, in Skript-Reihenfolge
    durchnummeriert. Jeder Eintrag trägt seine Position (episode/part/
    index_in_part) — das ist der Schlüssel, über den podcast_maker den Cue
    später wiederfindet, ohne sich auf den Text verlassen zu müssen."""
    voices = data.get("voices") or None
    cues = []
    for ep_num in range(1, len(data.get("episodes", [])) + 1):
        script = series.script_file(prefix, ep_num)
        if not os.path.exists(script):
            continue
        with open(script, "r", encoding="utf-8") as f:
            content = f.read()
        parts = [p.strip() for p in re.split(r'--- PART \d+ ---', content) if p.strip()]
        for part_idx, part_text in enumerate(parts, start=1):
            try:
                items = parse_drama_part(part_text, voices=voices,
                                         part_label=f"{os.path.basename(script)} PART {part_idx}")
            except ScriptFormatError as exc:
                print(f"  WARNUNG: {exc} — Part übersprungen.")
                continue
            ordinal = 0
            for i, item in enumerate(items):
                if item.kind != "sfx":
                    continue
                clean, repeats = strip_repeat(item.description)
                cues.append({
                    "id": len(cues),
                    "episode": ep_num,
                    "part": part_idx,
                    "index_in_part": ordinal,
                    "text": clean,
                    "raw_text": item.description,
                    "repeats": repeats,
                    "before_line": _neighbor_text(items, i, -1),
                    "after_line": _neighbor_text(items, i, +1),
                })
                ordinal += 1
    return cues


def _neighbor_text(items, i, step):
    """Nächste Sprecherzeile in Richtung step, gekürzt — der Kontext, aus dem
    Claude erkennt, ob der Sound VOR der Reaktion feuern muss oder unter ihr
    liegt."""
    j = i + step
    while 0 <= j < len(items):
        item = items[j]
        if item.kind == "speech":
            text = " ".join(item.text.split())
            if step < 0 and len(text) > CONTEXT_CHARS:
                text = "…" + text[-CONTEXT_CHARS:]
            elif len(text) > CONTEXT_CHARS:
                text = text[:CONTEXT_CHARS] + "…"
            return f"{item.speaker}: {text}"
        j += step
    return ""


def build_prompt(data, cues, existing_palette, feedback=None):
    series_title = data.get("series_title", "")
    style = data.get("style_guidelines", "")
    locations = data.get("locations") or {}
    loc_block = ""
    if locations:
        loc_lines = "\n".join(
            f"- {key}: {cfg.get('name', key)} — {cfg.get('description', '')}"
            for key, cfg in locations.items()
        )
        loc_block = (
            f"\nThe series plays in these recurring locations (each already has "
            f"its own continuous ambience loop running underneath — do NOT create "
            f"palette assets that duplicate that background atmosphere):\n{loc_lines}\n"
        )

    # Die Palette der bereits geplanten Episoden — der Grund, warum die Serie
    # am Ende nach EINER Welt klingt statt nach zehn Einzelfolgen. Wird als
    # Wiederverwendungs-Pflicht formuliert, nicht als Angebot.
    palette_block = ""
    if existing_palette:
        lines = "\n".join(
            f"- {a['key']}: {a['prompt']} ({a['duration_s']}s)"
            for a in existing_palette
        )
        palette_block = (
            f"\nThese assets already exist from earlier episodes of this series. "
            f"REUSE them wherever the sound honestly fits — a returning sound is what "
            f"makes a series sound like one world. Only invent a new asset if none of "
            f"these matches:\n{lines}\n"
        )

    cue_lines = []
    for c in cues:
        rep = f" (repeats {c['repeats']}x)" if c["repeats"] > 1 else ""
        cue_lines.append(
            f"[{c['id']}] part{c['part']}: \"{c['text']}\"{rep}\n"
            f"      before: {c['before_line'] or '(part start)'}\n"
            f"      after:  {c['after_line'] or '(part end)'}"
        )
    inventory = "\n".join(cue_lines)
    episode_num = cues[0]["episode"]

    prompt = (
        f"You are the sound designer for \"{series_title}\", an audio drama podcast.\n"
        f"Series tone/style: {style}\n"
        f"{loc_block}{palette_block}\n"
        f"The writer put {len(cues)} [SFX: ...] cues into the script of EPISODE "
        f"{episode_num}. Each is listed below with its index, the line spoken BEFORE "
        f"it and the line spoken AFTER it. Your job is to turn this raw list into a "
        f"production plan.\n\n"
        f"{inventory}\n\n"
        f"Do two things:\n\n"
        f"A) Extend the PALETTE of canonical sound assets with whatever THIS episode "
        f"needs and the existing palette does not already cover. Cluster cues that "
        f"mean the same physical sound into ONE asset (\"a door creaking open, slow\", "
        f"\"the door creaks\" and \"a slow creak of the front door\" are one asset). "
        f"Return ONLY the NEW assets in 'palette' (never repeat an existing one). "
        f"Each new asset gets:\n"
        f"   - key: short snake_case id, e.g. door_creak_slow\n"
        f"   - prompt: a concrete, well-written sound-generation prompt (this goes "
        f"straight to a text-to-sound-effect model). Describe the SOURCE, the "
        f"MATERIAL and the SPACE — \"heavy wooden door creaking slowly open in an "
        f"empty stone hallway, close, no music\" beats \"door creak\". No music, no "
        f"speech, no voices in any asset.\n"
        f"   - duration_s: {MIN_ASSET_SECONDS}-{MAX_ASSET_SECONDS} seconds. Keep hits short (0.5-2s); only "
        f"sustained textures (rain, engine, crowd) need more.\n"
        f"   Aim for as FEW new assets as the material honestly allows.\n\n"
        f"B) Annotate EVERY cue index above (this episode's cues only). For each cue:\n"
        f"   - keep: false if it is not actually an audible event. The writer cues "
        f"things that are not sounds — held beats, tension, silence, a character "
        f"breathing or exhaling, emotional states, anything the voice actor already "
        f"conveys. Those get keep=false and no asset. Be strict: a generated "
        f"\"tension\" sound is worse than no sound. Also drop a cue if the same "
        f"sound already fires within a few lines and repeating it adds nothing.\n"
        f"   - Never keep more than {MAX_KEPT_CUES_PER_PART} cues in a single part — if a part has more, "
        f"keep only the ones that genuinely land a dramatic beat and drop the rest.\n"
        f"   - asset_key (only if keep): the palette key this cue plays — either an "
        f"existing one from above or one of your new ones.\n"
        f"   - placement (only if keep):\n"
        f"       \"before\" = a discrete EVENT that must be heard before the next "
        f"line, because the next line reacts to it (a door slams, a glass shatters, "
        f"a phone rings). A short gap of silence will be inserted so the sound has "
        f"air. This is the right choice for most one-shot events.\n"
        f"       \"under\" = a sustained TEXTURE that belongs underneath the "
        f"following speech (rain, an engine, a crowd, a ticking clock). No gap is "
        f"inserted; the sound starts with the line.\n"
        f"   - gain (only if keep): {MIN_GAIN}-{MAX_GAIN}, how loud under the voice. Typical: a "
        f"sharp foreground event 0.4-0.6, a normal event 0.25-0.4, a background "
        f"texture 0.1-0.2. The voice must always stay clearly on top.\n\n"
        f"Answer ONLY with JSON in exactly this shape (one cues entry per index "
        f"above, none missing, none invented; 'palette' holds only the NEW assets "
        f"and may be empty if the existing palette covers everything):\n"
        f'{{"palette": [{{"key": "door_creak_slow", "prompt": "...", "duration_s": 1.5}}], '
        f'"cues": [{{"id": 0, "keep": true, "asset_key": "door_creak_slow", '
        f'"placement": "before", "gain": 0.4}}, '
        f'{{"id": 1, "keep": false, "why": "not an audible event"}}]}}'
    )
    if feedback:
        prompt += (
            f"\n\nYour previous answer was rejected for these reasons — fix ALL of "
            f"them:\n{feedback}"
        )
    return prompt


def validate_plan(parsed, cues, existing_keys=()):
    """Fehlerliste (leer = gültig). Die Texte gehen wörtlich als Feedback in
    den Retry — daher konkret formulieren (Muster: highlight_clips).

    existing_keys: Palette-Keys der bereits geplanten Episoden — ein Cue darf
    auf sie zeigen, ohne dass dieser Call sie erneut liefert."""
    errors = []
    palette = parsed.get("palette")
    annotations = parsed.get("cues")

    if palette is None:
        palette = []          # leere Palette ist legal: die alte deckt alles ab
    if not isinstance(palette, list):
        errors.append("'palette' must be a list (may be empty).")
        palette = []
    if not isinstance(annotations, list) or not annotations:
        return errors + ["'cues' must be a non-empty list, one entry per cue index."]

    keys = set(existing_keys)
    for n, asset in enumerate(palette):
        if not isinstance(asset, dict):
            errors.append(f"Palette entry {n}: must be an object.")
            continue
        key = asset.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_]+", key or ""):
            errors.append(f"Palette entry {n}: 'key' must be snake_case (a-z, 0-9, _).")
            continue
        if key in existing_keys:
            errors.append(f"Palette key '{key}' already exists from an earlier episode — "
                          f"do not return it again, just reference it in asset_key.")
        elif key in keys:
            errors.append(f"Palette key '{key}' appears twice.")
        keys.add(key)
        if not isinstance(asset.get("prompt"), str) or not asset["prompt"].strip():
            errors.append(f"Palette '{key}': 'prompt' must be a non-empty string.")
        dur = asset.get("duration_s")
        if not isinstance(dur, (int, float)) or not (MIN_ASSET_SECONDS <= dur <= MAX_ASSET_SECONDS):
            errors.append(f"Palette '{key}': 'duration_s' must be a number "
                          f"{MIN_ASSET_SECONDS}-{MAX_ASSET_SECONDS}.")

    # Die ids sind serienweit vergeben, dieser Call sieht nur die einer Episode
    # — also gegen die Menge der gezeigten ids prüfen, nicht gegen 0..len-1.
    by_id = {c["id"]: c for c in cues}
    id_range = f"{cues[0]['id']}-{cues[-1]['id']}"

    seen = {}
    for entry in annotations:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), int):
            errors.append("Every cues entry needs an integer 'id' from the list above.")
            continue
        cid = entry["id"]
        if cid not in by_id:
            errors.append(f"Cue id {cid} was not in this episode's list (valid: {id_range}).")
            continue
        if cid in seen:
            errors.append(f"Cue id {cid} appears twice.")
            continue
        seen[cid] = entry

        if not entry.get("keep"):
            continue
        key = entry.get("asset_key")
        if key not in keys:
            errors.append(f"Cue {cid}: asset_key '{key}' is not in the palette.")
        if entry.get("placement") not in PLACEMENTS:
            errors.append(f"Cue {cid}: 'placement' must be one of {list(PLACEMENTS)}.")
        gain = entry.get("gain")
        if not isinstance(gain, (int, float)) or not (MIN_GAIN <= gain <= MAX_GAIN):
            errors.append(f"Cue {cid}: 'gain' must be a number {MIN_GAIN}-{MAX_GAIN}.")

    missing = [c["id"] for c in cues if c["id"] not in seen]
    if missing:
        shown = ", ".join(str(m) for m in missing[:20])
        more = f" (and {len(missing) - 20} more)" if len(missing) > 20 else ""
        errors.append(f"Missing cues entries for these ids: {shown}{more}. "
                      f"Every one of the {len(cues)} cue indices needs an entry.")

    # Dichte pro Part — die Regel, die das Prompt ansagt, wird hier auch geprüft.
    # Zählt tatsächliche Sound-EVENTS, nicht Cue-IDs: ein Cue mit "gunshot x8"
    # (repeats=8, siehe collect_cues) löst beim Vertonen 8 einzelne Trigger
    # aus (podcast_maker.py::expand_sfx_cue) — eine Bremse, die nur Cue-Zeilen
    # zählt, ließe "5 Cues à x8" (=40 Events) klaglos durch, obwohl genau das
    # die "Hörspiel-Karaoke"-Dichte ist, die MAX_KEPT_CUES_PER_PART verhindern
    # soll.
    per_part = {}
    for cid, entry in seen.items():
        if entry.get("keep"):
            per_part.setdefault(by_id[cid]["part"], []).append(cid)
    for part, kept in sorted(per_part.items()):
        event_count = sum(by_id[cid].get("repeats", 1) for cid in kept)
        if event_count > MAX_KEPT_CUES_PER_PART:
            errors.append(
                f"Part {part} keeps {len(kept)} cue(s) but {event_count} Sound-Event(s) "
                f"nach Wiederholungen (ids {', '.join(str(c) for c in kept)}) — max "
                f"{MAX_KEPT_CUES_PER_PART} Events. Drop the weakest ones (keep=false) or "
                f"reduce a cue's 'xN' repeat count."
            )
    return errors


def build_ambience_prompt(data, sections, locations, feedback=None, existing_variants=None):
    series_title = data.get("series_title", "")
    style = data.get("style_guidelines", "")

    loc_lines = "\n".join(
        f"- {key}: {cfg.get('name', key)} — {cfg.get('description', '')}"
        for key, cfg in locations.items()
        if key in {s["location"] for s in sections}
    )
    sec_lines = "\n".join(
        f"[{s['episode']}.{s['section']}] {s['location']}: {s['text']}"
        for s in sections
    )

    # Beim inkrementellen Nachplanen (neue Episoden nach dem ersten Ambience-
    # Lauf) sieht Claude die schon existierenden Varianten und wird auf
    # Wiederverwendung verpflichtet — exakt dasselbe Muster wie base_palette
    # bei den Cues (generate_plan). Ohne das würde jeder neue Batch pro Ort
    # wieder bei 0 anfangen und den MAX_AMBIENCE_VARIANTS_PER_LOCATION-Deckel
    # der bereits existierenden Varianten ignorieren.
    existing_block = ""
    if existing_variants:
        existing_lines = "\n".join(
            f"- {v['key']} ({v.get('location')}): {v.get('mood', '')}"
            for v in existing_variants
        )
        existing_block = (
            f"\nThese variants already exist from earlier planning — REUSE them by "
            f"key wherever a new scene's mood matches one, do not redefine them, and "
            f"count them against the per-location max below:\n{existing_lines}\n"
        )

    prompt = (
        f"You are the sound designer for \"{series_title}\", an audio drama podcast.\n"
        f"Series tone/style: {style}\n\n"
        f"Every scene runs a continuous AMBIENCE bed underneath the dialogue — a "
        f"looping background atmosphere for the place the scene happens in. Until "
        f"now each location had exactly ONE loop for the entire series, which meant "
        f"a quiet breakfast and a screaming midnight confrontation in the same room "
        f"sounded identical. Your job is to fix that.\n\n"
        f"The locations:\n{loc_lines}\n"
        f"{existing_block}\n"
        f"Every scene to plan now, as [episode.section] LOCATION: what happens:\n"
        f"{sec_lines}\n\n"
        f"Do two things:\n\n"
        f"A) For each location, define ambience VARIANTS — the distinct moods "
        f"this room actually takes on across the scenes above (e.g. an empty hotel "
        f"lobby at midday vs. the same lobby at night in a storm), up to "
        f"{MAX_AMBIENCE_VARIANTS_PER_LOCATION} TOTAL per location INCLUDING the "
        f"already-existing ones listed above. Do not invent moods the scenes do not "
        f"call for: if an existing variant already fits, reuse it instead of adding "
        f"a new one. Each NEW variant gets:\n"
        f"   - key: LOCATION__mood, e.g. LOBBY__storm_night (the location key, two "
        f"underscores, a short snake_case mood)\n"
        f"   - location: the location key it belongs to\n"
        f"   - mood: one short phrase, for humans\n"
        f"   - prompt: a concrete sound-generation prompt for a SEAMLESS, CONTINUOUS "
        f"background loop. Describe the space and its steady textures (room tone, "
        f"weather behind glass, distant traffic, a refrigerator hum). It must contain "
        f"NO music, NO voices, and NO discrete events (no doors, no footsteps, no "
        f"thunderclaps) — a one-off bang inside a loop repeats every few seconds and "
        f"instantly gives the loop away. What differs between two variants of the "
        f"same room is weather, time of day, distance, density and pressure — not a "
        f"new set of objects. Only list NEW variants here, not the already-existing "
        f"ones you're reusing.\n\n"
        f"B) Assign exactly one variant (new OR existing) to EVERY scene listed "
        f"above, by its [episode.section] index. The variant's location must match "
        f"the scene's location. Reuse variants across episodes — a returning mood "
        f"is what makes a room feel like the same room.\n\n"
        f"Answer ONLY with JSON in exactly this shape:\n"
        f'{{"variants": [{{"key": "LOBBY__storm_night", "location": "LOBBY", '
        f'"mood": "night, storm outside", "prompt": "..."}}], '
        f'"sections": [{{"episode": 1, "section": 0, "variant": "LOBBY__storm_night"}}]}}'
    )
    if feedback:
        prompt += (
            f"\n\nYour previous answer was rejected for these reasons — fix ALL of "
            f"them:\n{feedback}"
        )
    return prompt


def validate_ambience(parsed, sections, locations, existing_variants=None):
    """Fehlerliste (leer = gültig) — Texte gehen wörtlich in den Retry.

    existing_variants: beim inkrementellen Nachplanen die schon vorhandenen
    Varianten — zählen gegen MAX_AMBIENCE_VARIANTS_PER_LOCATION mit, dürfen
    aber als 'variant' in sections referenziert werden, ohne in DIESER
    Antwort erneut in 'variants' aufzutauchen."""
    errors = []
    existing_variants = existing_variants or []
    existing_by_key = {v["key"]: v for v in existing_variants}
    variants = parsed.get("variants")
    assignments = parsed.get("sections")

    if variants is None:
        variants = []  # inkrementell: alle Szenen können auf bestehende Varianten fallen
    if not isinstance(variants, list):
        return ["'variants' must be a list (may be empty if only reusing existing variants)."]
    if not isinstance(assignments, list) or not assignments:
        errors.append("'sections' must be a non-empty list, one entry per scene.")
        assignments = []

    by_key = dict(existing_by_key)
    per_location = {}
    for key, var in existing_by_key.items():
        per_location.setdefault(var["location"], []).append(key)
    for n, var in enumerate(variants):
        if not isinstance(var, dict):
            errors.append(f"Variant {n}: must be an object.")
            continue
        key, loc = var.get("key"), var.get("location")
        if loc not in locations:
            errors.append(f"Variant {n}: 'location' must be one of {sorted(locations)}.")
            continue
        # Format hart erzwingen: der Key ist auch der DATEINAME
        # (sfx/ambience/<key>.mp3) — ein Key, der exakt dem Orts-Key gleicht,
        # würde die Basis-Fallback-Schleife des Orts überschreiben.
        if (not isinstance(key, str) or not key.startswith(f"{loc}__")
                or not re.fullmatch(r"[a-z0-9_]+", key[len(loc) + 2:])):
            errors.append(f"Variant {n}: 'key' must be '{loc}__<mood>' with a "
                          f"snake_case mood (a-z, 0-9, _), e.g. {loc}__storm_night — "
                          f"never the bare location key.")
            continue
        if key in existing_by_key:
            errors.append(f"Variant key '{key}' already exists from earlier planning — "
                          f"do not return it again, just reference it in 'sections'.")
            continue
        if key in by_key:
            errors.append(f"Variant key '{key}' appears twice.")
            continue
        if not isinstance(var.get("prompt"), str) or not var["prompt"].strip():
            errors.append(f"Variant '{key}': 'prompt' must be a non-empty string.")
        by_key[key] = var
        per_location.setdefault(loc, []).append(key)

    for loc, keys in sorted(per_location.items()):
        if len(keys) > MAX_AMBIENCE_VARIANTS_PER_LOCATION:
            errors.append(
                f"Location {loc} has {len(keys)} variants total, existing+new "
                f"({', '.join(keys)}) — max {MAX_AMBIENCE_VARIANTS_PER_LOCATION}. "
                f"Reuse an existing variant instead of adding a new one, or merge "
                f"moods that are not genuinely different."
            )

    wanted = {(s["episode"], s["section"]): s["location"] for s in sections}
    seen = set()
    for entry in assignments:
        if not isinstance(entry, dict):
            errors.append("Every sections entry must be an object.")
            continue
        pos = (entry.get("episode"), entry.get("section"))
        if pos not in wanted:
            errors.append(f"Scene {pos[0]}.{pos[1]} is not in the scene list.")
            continue
        if pos in seen:
            errors.append(f"Scene {pos[0]}.{pos[1]} is assigned twice.")
            continue
        seen.add(pos)
        var = by_key.get(entry.get("variant"))
        if var is None:
            errors.append(f"Scene {pos[0]}.{pos[1]}: variant '{entry.get('variant')}' "
                          f"is not in 'variants'.")
        elif var["location"] != wanted[pos]:
            errors.append(
                f"Scene {pos[0]}.{pos[1]} plays in {wanted[pos]}, but variant "
                f"'{var['key']}' belongs to {var['location']}."
            )

    missing = [f"{e}.{s}" for (e, s) in wanted if (e, s) not in seen]
    if missing:
        shown = ", ".join(missing[:20])
        more = f" (and {len(missing) - 20} more)" if len(missing) > 20 else ""
        errors.append(f"Missing sections entries for these scenes: {shown}{more}.")
    return errors


def generate_ambience(data, sections, locations, model, effort=None, existing_variants=None):
    """Ein Claude-Call für die zu planenden Sections (beim inkrementellen
    Nachplanen nur die NEUEN, nicht die ganze Serie erneut) mit Validierungs-
    Retry. None = gescheitert; dann bleibt die Ambience beim Alt-Verhalten
    (eine Schleife pro Ort).

    existing_variants: schon geplante Varianten aus einem früheren Lauf —
    Claude wird auf Wiederverwendung verpflichtet (gleiches Muster wie
    base_palette bei generate_plan)."""
    feedback = None
    for attempt in range(1, MAX_RETRIES + 1):
        prompt = build_ambience_prompt(data, sections, locations, feedback,
                                       existing_variants=existing_variants)
        output = call_claude(prompt, model, "Ambience-Plan", effort=effort)
        if output is None:
            print(f"  Versuch {attempt}/{MAX_RETRIES}: keine Ausgabe.")
        else:
            parsed = parse_json_response(output)
            if parsed is None:
                feedback = "Answer was not parseable JSON. Return ONLY the JSON object."
                print(f"  Versuch {attempt}/{MAX_RETRIES}: kein parsebares JSON.")
            else:
                errors = validate_ambience(parsed, sections, locations,
                                           existing_variants=existing_variants)
                if not errors:
                    return parsed
                feedback = "\n".join(f"- {e}" for e in errors)
                print(f"  Versuch {attempt}/{MAX_RETRIES}: {len(errors)} Validierungsfehler:")
                for e in errors[:8]:
                    print(f"    - {e}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
    return None


def call_claude(prompt, model, label, effort=None):
    """Wie highlight_clips.call_claude — Timeout/API-Fehler sind retryable
    (None), nur 'claude not found'/401 brechen ab."""
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


def generate_episode_plan(data, cues, existing_palette, model, label, effort=None):
    """Ein Claude-Call pro Episode mit Validierungs-Retry (Fehler wörtlich
    zurückgefüttert). None, wenn alle Versuche scheitern."""
    existing_keys = {a["key"] for a in existing_palette}
    feedback = None
    for attempt in range(1, MAX_RETRIES + 1):
        prompt = build_prompt(data, cues, existing_palette, feedback)
        output = call_claude(prompt, model, label, effort=effort)
        if output is None:
            print(f"  Versuch {attempt}/{MAX_RETRIES}: keine Ausgabe.")
        else:
            parsed = parse_json_response(output)
            if parsed is None:
                feedback = "Answer was not parseable JSON. Return ONLY the JSON object."
                print(f"  Versuch {attempt}/{MAX_RETRIES}: kein parsebares JSON.")
            else:
                errors = validate_plan(parsed, cues, existing_keys)
                if not errors:
                    return parsed
                feedback = "\n".join(f"- {e}" for e in errors)
                print(f"  Versuch {attempt}/{MAX_RETRIES}: {len(errors)} Validierungsfehler:")
                for e in errors[:8]:
                    print(f"    - {e}")
                if len(errors) > 8:
                    print(f"    … und {len(errors) - 8} weitere")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
    return None


def generate_plan(data, cues, model, base_palette=None, effort=None):
    """Episode für Episode planen, Palette wächst dabei mit (Episode N sieht
    die Assets aus 1..N-1 und wird auf Wiederverwendung verpflichtet) — der
    Grund, warum ein Türknall in Episode 7 derselbe ist wie in Episode 1.

    Seriell, nicht parallel: genau diese Kontinuität hängt an der Reihenfolge
    (gleiches Muster wie der Beats-Vorlauf in generate_episode.py).

    base_palette: beim inkrementellen Nachplanen die Palette des vorhandenen
    Plans — die neuen Episoden werden auf ihre Wiederverwendung verpflichtet,
    genau wie Episode N auf die Assets aus 1..N-1.

    Rückgabe: (palette, annotations_by_id, failed_episodes). Eine gescheiterte
    Episode kostet nur ihre eigenen Cues — die fallen ohne Plan-Eintrag auf das
    alte Verhalten zurück, statt die ganze Serie zu blockieren."""
    by_episode = {}
    for cue in cues:
        by_episode.setdefault(cue["episode"], []).append(cue)

    palette = list(base_palette or [])
    annotations = {}
    failed = []
    for ep_num in sorted(by_episode):
        ep_cues = by_episode[ep_num]
        print(f"\nEpisode {ep_num}: {len(ep_cues)} Cue(s), Palette bisher: "
              f"{len(palette)} Asset(s) ...")
        parsed = generate_episode_plan(data, ep_cues, palette, model,
                                       f"SFX-Plan Ep{ep_num}", effort=effort)
        if parsed is None:
            print(f"  FEHLER: Episode {ep_num} — kein gültiger Plan nach {MAX_RETRIES} "
                  f"Versuchen (ihre Cues laufen im Alt-Verhalten).")
            failed.append(ep_num)
            continue
        new_assets = parsed.get("palette") or []
        palette.extend(new_assets)
        for entry in parsed["cues"]:
            annotations[entry["id"]] = entry
        kept = sum(1 for e in parsed["cues"] if e.get("keep"))
        print(f"  {kept} behalten, {len(ep_cues) - kept} verworfen, "
              f"{len(new_assets)} neue(s) Asset(s)")
    return palette, annotations, failed


def build_ambience_block(parsed, sections):
    """Ambience-Teil des Plans. Anders als die One-Shot-Palette tragen
    Varianten KEIN 'asset'-Hash-Feld: location_ambience legt die Datei direkt
    unter dem VARIANTEN-KEY ab (sfx/ambience/<key>.mp3), weil Lolfi sie über
    den Key aus der Location-Timeline sucht, nicht über einen Hash."""
    variants = []
    used = {}
    for var in parsed["variants"]:
        variants.append({
            "key": var["key"],
            "location": var["location"],
            "mood": (var.get("mood") or "").strip(),
            "prompt": var["prompt"].strip(),
        })
    entries = []
    for entry in parsed["sections"]:
        entries.append({"episode": entry["episode"], "section": entry["section"],
                        "variant": entry["variant"]})
        used[entry["variant"]] = used.get(entry["variant"], 0) + 1
    # Varianten ohne eine einzige Szene fliegen raus — sonst generiert
    # location_ambience Loops, die nie laufen.
    variants = [v for v in variants if used.get(v["key"])]
    for var in variants:
        var["scenes"] = used[var["key"]]
    return {"variants": variants, "sections": entries}


def write_plan(out_file, series, cues, raw_palette, annotations, failed, ambience=None):
    """Schreibt das editierbare Artefakt. 'asset' ist der Dateiname-Hash des
    GENERIERUNGS-PROMPTS (nicht des Cue-Texts) — derselbe Hash, unter dem
    sfx_assets/sfx_library die Datei ablegt, und den podcast_maker in die
    <Episode>_SFX_CUES.json durchreicht, damit Lolfi ihn nicht mehr selbst
    aus dem Cue-Text berechnen muss (eine nachträgliche Skript-Korrektur
    bricht damit den Sound nicht mehr still)."""
    palette = []
    for asset in raw_palette:
        palette.append({
            "key": asset["key"],
            "prompt": asset["prompt"].strip(),
            "duration_s": round(float(asset["duration_s"]), 1),
            # Bestands-Einträge (inkrementeller Lauf) behalten ihren
            # gespeicherten Hash — das dokumentierte Verhalten "asset wird
            # beim Prompt-Edit NICHT automatisch neu berechnet" gilt auch hier.
            "asset": asset.get("asset") or sfx_asset_hash(asset["prompt"].strip()),
        })
    used = {}

    entries = []
    for cue in cues:
        ann = annotations.get(cue["id"])
        if ann is None:
            continue  # Episode gescheitert: kein Eintrag = Alt-Verhalten
        entry = {
            "id": cue["id"],
            "episode": cue["episode"],
            "part": cue["part"],
            "index_in_part": cue["index_in_part"],
            "text": cue["text"],
            "keep": bool(ann.get("keep")),
        }
        if entry["keep"]:
            entry["asset_key"] = ann["asset_key"]
            entry["placement"] = ann["placement"]
            entry["gain"] = round(float(ann["gain"]), 2)
            used[ann["asset_key"]] = used.get(ann["asset_key"], 0) + 1
        else:
            entry["why"] = (ann.get("why") or "").strip()
        entries.append(entry)

    # Palette-Assets, die kein Cue mehr spielt (alle seine Cues gedroppt),
    # fliegen raus — sonst generiert sfx_assets Sounds, die nie klingen.
    palette = [a for a in palette if used.get(a["key"])]
    for asset in palette:
        asset["cues"] = used[asset["key"]]

    payload = {
        "series": series.slug,
        "hinweis": (
            "Von Hand editierbar (Review-Gate): keep/placement/gain/prompt anpassen, "
            "dann vertonen. placement 'before' = Sound feuert in einer eingefügten "
            "Lücke VOR der nächsten Zeile, 'under' = Sound startet mit der Zeile. "
            "'asset' ist der Dateiname (<asset>.mp3) — wird beim Ändern von 'prompt' "
            "NICHT automatisch neu berechnet, dann sfx_plan --force laufen lassen. "
            "Konsumenten: podcast_maker/batch (Platzierung), sfx_assets (Generierung)."
        ),
        "palette": palette,
        "cues": entries,
    }
    if ambience:
        payload["ambience"] = ambience
    if failed:
        payload["unplanned_episodes"] = failed  # Cues dieser Episoden laufen im Alt-Verhalten
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return payload


def print_summary(payload):
    kept = [c for c in payload["cues"] if c["keep"]]
    dropped = [c for c in payload["cues"] if not c["keep"]]
    before = sum(1 for c in kept if c["placement"] == "before")
    print(f"\nPalette: {len(payload['palette'])} Assets")
    for asset in payload["palette"]:
        print(f"  {asset['key']:<28} {asset['cues']:>2}x  {asset['duration_s']}s  "
              f"„{asset['prompt'][:60]}…“")
    print(f"\nCues: {len(kept)} behalten ({before} vor der Zeile, "
          f"{len(kept) - before} unter der Zeile), {len(dropped)} verworfen")
    for cue in dropped[:10]:
        print(f"  ✗ ep{cue['episode']} part{cue['part']}: „{cue['text'][:50]}“"
              f"{' — ' + cue['why'] if cue.get('why') else ''}")
    if len(dropped) > 10:
        print(f"  … und {len(dropped) - 10} weitere verworfen")

    amb = payload.get("ambience")
    if amb:
        per_loc = {}
        for var in amb["variants"]:
            per_loc.setdefault(var["location"], []).append(var)
        print(f"\nAmbience: {len(amb['variants'])} Variante(n) für {len(per_loc)} Ort(e), "
              f"{len(amb['sections'])} Szene(n) zugewiesen")
        for loc, variants in sorted(per_loc.items()):
            print(f"  {loc}:")
            for var in variants:
                print(f"    {var['key']:<30} {var['scenes']:>2} Szene(n)  „{var['mood']}“")


def main():
    parser = argparse.ArgumentParser(
        description="SFX-Cues einer Serie per Claude zu Palette + Platzierungsplan kuratieren")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene SFX_PLAN.json komplett neu generieren (statt "
                             "fehlende Episoden inkrementell nachzuplanen); "
                             "Handkorrekturen gehen dabei verloren")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)

    if data.get("mode") != "drama":
        print(f"Serie '{series.slug}' läuft im Modus '{data.get('mode')}' — SFX-Cues gibt es "
              f"nur im Drama-Modus. Nichts zu tun.")
        return

    out_file = plan_path(series)
    existing = None
    if os.path.exists(out_file) and not args.force:
        existing = load_plan(out_file)
        if existing is None:
            print(f"Vorhandene {PLAN_FILENAME} ist nicht lesbar — wird neu generiert.")

    prefix = data.get("output_prefix", config.DEFAULTS["output_prefix"])
    cues = collect_cues(series, data, prefix)
    if not cues:
        print(f"Serie '{series.slug}': keine [SFX: ...]-Cues in den vorhandenen Skripten "
              f"({series.scripts_dir}) — erst Skripte generieren, dann planen.")
        return

    all_episodes = sorted({c["episode"] for c in cues})
    # light_model: JSON-Extraktion von SFX-Cue-Objekten aus fertigem Skript,
    # keine kreative Skript-Arbeit — braucht nicht das teure Schreibmodell.
    model = data.get("generation", {}).get("light_model", config.DEFAULTS["light_model"])
    effort = data.get("generation", {}).get("effort", config.DEFAULTS["effort"])

    # INKREMENTELL: ein vorhandener Plan wird nicht weggeworfen, sondern um
    # die Episoden ergänzt, die ihm fehlen — neue Skripte, die nach dem
    # Planen dazukamen, und frühere Fehlschläge (unplanned_episodes). Die
    # Einträge der bereits geplanten Episoden werden 1:1 übernommen,
    # HANDKORREKTUREN BLEIBEN also erhalten; nur --force plant alles neu.
    annotations = {}
    base_palette = []
    ambience = None
    if existing is not None:
        retry = set(existing.get("unplanned_episodes") or [])
        have = {c["episode"] for c in existing.get("cues", [])} - retry
        todo = [ep for ep in all_episodes if ep not in have]
        if not todo:
            print(f"SFX-Plan bereits vollständig: {out_file}")
            print("  (--force zum Neu-Generieren; Handkorrekturen gehen dabei verloren)")
            print_summary(existing)
            return
        base_palette = [a for a in existing.get("palette", [])
                        if a.get("key") and a.get("prompt")]
        # Übernahme per POSITION + Text-Abgleich — derselbe Stale-Guard wie in
        # podcast_maker.resolve_cue: ein nach dem Planen geändertes Skript
        # macht den Eintrag ungültig, der Cue fällt aufs Alt-Verhalten zurück.
        old_by_pos = {(c["episode"], c["part"], c["index_in_part"]): c
                      for c in existing.get("cues", [])}
        for cue in cues:
            if cue["episode"] in todo:
                continue
            old = old_by_pos.get((cue["episode"], cue["part"], cue["index_in_part"]))
            if old is not None and old.get("text") == cue["text"]:
                annotations[cue["id"]] = old
        ambience = existing.get("ambience")
        cues_to_plan = [c for c in cues if c["episode"] in todo]
        print(f"Serie: {series.slug} — SFX-Plan vorhanden, plane inkrementell nach: "
              f"Episode(n) {', '.join(str(e) for e in todo)} "
              f"({len(cues_to_plan)} Cue(s); geplante Episoden bleiben unangetastet), "
              f"Modell: {model} ...")
    else:
        cues_to_plan = cues
        print(f"Serie: {series.slug} — {len(cues)} SFX-Cues aus {len(all_episodes)} "
              f"Episode(n), Modell: {model} (ein Call pro Episode, Palette wächst mit) ...")

    palette, new_annotations, _ = generate_plan(data, cues_to_plan, model, base_palette, effort=effort)
    annotations.update(new_annotations)
    if not annotations:
        print(f"\nFEHLER: keine einzige Episode planbar — später erneut starten "
              f"(vorhandener Plan bleibt unangetastet).")
        sys.exit(1)

    # Ungeplant = Episoden mit Cues, aber ohne einen einzigen Plan-Eintrag —
    # deckt neue Fehlschläge UND übernommene Lücken ab (selbstheilend: der
    # nächste Lauf ohne --force versucht genau diese Episoden erneut).
    by_id = {c["id"]: c for c in cues}
    planned_eps = {by_id[i]["episode"] for i in annotations if i in by_id}
    failed = sorted(set(all_episodes) - planned_eps)

    # Ambience: eigener Call, unabhängig von den Cues (Quelle sind die
    # section_locations aus episodes.json, nicht die Skripte). INKREMENTELL
    # wie der Cue-Plan: deckt der vorhandene Plan schon alle Sections ab
    # (episode.section-Positionen), bleibt er unangetastet — wächst die
    # Serie aber (neue Episoden/Sections in episodes.json seit dem letzten
    # Ambience-Lauf), werden NUR die fehlenden neu geplant, Claude sieht die
    # existierenden Varianten und wird auf Wiederverwendung verpflichtet.
    # Serien ohne locations — also alle außer soap_opera — überspringen ihn
    # stillschweigend und behalten die eine Schleife pro Ort bzw. gar keine.
    locations = data.get("locations") or {}
    all_sections = collect_sections(data) if locations else []
    existing_ambience = ambience or {}
    covered_positions = {(e["episode"], e["section"]) for e in existing_ambience.get("sections", [])}
    todo_sections = [s for s in all_sections if (s["episode"], s["section"]) not in covered_positions]
    if todo_sections:
        existing_variants = existing_ambience.get("variants", [])
        if existing_variants:
            print(f"\nAmbience: Plan vorhanden ({len(existing_variants)} Variante(n)), "
                  f"plane {len(todo_sections)} neue Szene(n) nach (z.B. neue Episoden) ...")
        else:
            print(f"\nAmbience: {len(todo_sections)} Szene(n) in "
                  f"{len({s['location'] for s in todo_sections})} Ort(en) — "
                  f"Stimmungs-Varianten planen ...")
        parsed_amb = generate_ambience(data, todo_sections, locations, model, effort=effort,
                                       existing_variants=existing_variants)
        if parsed_amb is None:
            print(f"  FEHLER: Ambience-Plan gescheitert — die betroffenen Szenen bleiben "
                  f"beim Alt-Verhalten (eine Schleife pro Ort). Der Cue-Plan ist davon "
                  f"unberührt; ein erneuter Lauf (ohne --force) versucht sie wieder.")
        else:
            new_block = build_ambience_block(parsed_amb, todo_sections)
            merged_sections = existing_ambience.get("sections", []) + new_block["sections"]
            merged_variants_by_key = {v["key"]: v for v in existing_variants}
            for var in new_block["variants"]:
                merged_variants_by_key[var["key"]] = var
            used = {}
            for entry in merged_sections:
                used[entry["variant"]] = used.get(entry["variant"], 0) + 1
            final_variants = [v for v in merged_variants_by_key.values() if used.get(v["key"])]
            for var in final_variants:
                var["scenes"] = used[var["key"]]
            ambience = {"variants": final_variants, "sections": merged_sections}

    payload = write_plan(out_file, series, cues, palette, annotations, failed, ambience)
    print(f"\nGespeichert: {out_file}")
    print_summary(payload)
    if failed:
        print(f"\nWARNUNG: Episode(n) {', '.join(str(f) for f in failed)} ungeplant — "
              f"ihre Cues laufen im Alt-Verhalten. Ein erneuter 'sfx_plan'-Lauf (ohne "
              f"--force) versucht genau diese Episoden noch einmal; geplante Episoden "
              f"und Handkorrekturen bleiben dabei unangetastet.")
    print(f"\nNächste Schritte: vertonen (podcast_maker/batch — liest den Plan für die "
          f"Platzierung), dann 'python3 -m fabrik.cli.sfx_assets' (generiert die Palette).")


if __name__ == "__main__":
    main()
