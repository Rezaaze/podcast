"""Read-only Status-Dashboard-Funktionen. Kein Caching — jeder Aufruf liest
die aktuellen Dateien frisch von Disk."""

import glob
import json
import os
import re

from config import LOLFI_DIR, PF_DIR, current_series_dir, series_dir_for


def _read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _read_text(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _state(running: bool, ready: bool, partial: bool = False) -> str:
    if running:
        return "running"
    if ready:
        return "ready"
    if partial:
        return "partial"
    return "missing"


def pf_status(jobs=None, series_slug=None) -> dict:
    """series_slug: explizite Serie (z.B. aus der WebUI-Auswahl) — fällt bei
    None/ungültigem Slug auf series/LATEST bzw. die einzige vorhandene Serie
    zurück. series_dir_for() validiert den Slug gegen die echte Ordnerliste,
    ein Query-Parameter vom Client kann also nie außerhalb von series/ lesen."""
    series_dir = series_dir_for(series_slug) or current_series_dir()
    scripts_dir = os.path.join(series_dir, "scripts") if series_dir else PF_DIR
    episodes_json = (_read_json(os.path.join(series_dir, "episodes.json")) if series_dir else None) or {}
    prefix = episodes_json.get("output_prefix", "figur")
    episodes = episodes_json.get("episodes", [])
    output_dir = os.path.join(series_dir, "output") if series_dir else os.path.join(PF_DIR, "data", "series")
    checkpoints_dir = os.path.join(output_dir, ".checkpoints")

    running_commands = jobs.snapshot() if jobs else {}
    # Vertonung läuft auch während batch.py / "all" (die rufen podcast_maker
    # intern auf) — nicht nur beim direkten Einzelaufruf.
    podcast_maker_running = any(
        running_commands.get(cid, {}).get("state") == "running"
        for cid in ("pf_podcast_maker", "pf_batch", "pf_generate_episode_all")
    )

    episode_rows = []
    for i, ep in enumerate(episodes, start=1):
        script_file = os.path.join(scripts_dir, f"{prefix}{i}.txt")
        meta_file = os.path.join(scripts_dir, f"{prefix}{i}_META.txt")
        name = f"{prefix}{i}".capitalize()
        mp3_file = os.path.join(output_dir, f"{name}_FULL_EPISODE.mp3")

        script_ready = os.path.exists(script_file) and os.path.getsize(script_file) > 0
        meta_ready = os.path.exists(meta_file)
        audio_ready = os.path.exists(mp3_file)

        checkpoint_glob = glob.glob(os.path.join(checkpoints_dir, f"{name}_Part_*"))
        audio_in_progress = podcast_maker_running and bool(checkpoint_glob) and not audio_ready

        episode_rows.append({
            "index": i,
            "figure": ep.get("figure", ""),
            "script_file": f"{prefix}{i}.txt",
            "script_state": _state(False, script_ready and meta_ready, script_ready),
            "audio_state": _state(audio_in_progress, audio_ready),
        })

    anthology_file = os.path.join(output_dir, "ANTHOLOGY_COMPLETE.mp3")
    archive_dir = os.path.join(PF_DIR, "data", "archive")
    archive_count = len(os.listdir(archive_dir)) if os.path.isdir(archive_dir) else 0

    # Charakter-Porträts (nur Drama-Serien): wie viele Rollen haben schon ein
    # Bild in characters/? Treibt den Video-Vorbereitungs-Schritt der WebUI.
    roles = [r for r in episodes_json.get("voices", {}) if r != "NARRATOR"]
    characters_dir = os.path.join(series_dir, "characters") if series_dir else None
    image_stems = set()
    if characters_dir and os.path.isdir(characters_dir):
        image_stems = {
            os.path.splitext(f)[0].upper() for f in os.listdir(characters_dir)
            if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp")
        }
    characters = {
        "roles": len(roles),
        "images": sum(1 for r in roles if r.upper() in image_stems),
        "prompts_ready": bool(characters_dir) and os.path.exists(os.path.join(characters_dir, "PROMPTS.txt")),
    }

    # Szenen-Orte (nur Serien mit "locations" in episodes.json, z.B. soap_opera):
    # wie viele Orte haben schon ein Hintergrundbild in locations/?
    location_keys = list(episodes_json.get("locations", {}))
    locations_dir = os.path.join(series_dir, "locations") if series_dir else None
    location_image_stems = set()
    if locations_dir and os.path.isdir(locations_dir):
        location_image_stems = {
            os.path.splitext(f)[0].upper() for f in os.listdir(locations_dir)
            if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp")
        }
    locations = {
        "keys": len(location_keys),
        "images": sum(1 for k in location_keys if k.upper() in location_image_stems),
        "prompts_ready": bool(locations_dir) and os.path.exists(os.path.join(locations_dir, "PROMPTS.txt")),
    }

    # Cover-Bild: ein einziges Bild pro Serie, kein Rollen-/Orte-Zähler nötig.
    cover_exists = bool(series_dir) and os.path.exists(os.path.join(series_dir, "cover.png"))

    return {
        "series_slug": os.path.basename(series_dir) if series_dir else None,
        "series_title": episodes_json.get("series_title"),
        "language": episodes_json.get("language"),
        "mode": episodes_json.get("mode", "narration"),
        "template": episodes_json.get("template", "narration"),
        "episode_count": len(episodes),
        "episodes": episode_rows,
        "anthology_state": _state(
            running_commands.get("pf_batch", {}).get("state") == "running",
            os.path.exists(anthology_file),
        ),
        "characters": characters,
        "locations": locations,
        "cover_exists": cover_exists,
        "anthology_meta_exists": os.path.exists(os.path.join(scripts_dir, "ANTHOLOGY_META.txt")),
        "upload_index_exists": os.path.exists(os.path.join(output_dir, "UPLOAD_INDEX.md")),
        "archive_count": archive_count,
        "running_jobs": running_commands,
    }


# Muss mit lofi_system.py::AUDIO_EXTS / PODCAST_EXCLUDE_PATTERNS übereinstimmen
# (keine gemeinsame Imports zwischen den beiden Projekten, siehe CLAUDE.md).
_PODCAST_AUDIO_EXTS = (".mp3", ".wav", ".flac", ".aac", ".m4a")
_PODCAST_EXCLUDE_PATTERNS = ("_meta_",)


def _list_podcast_episode_files() -> list:
    """Alle einzeln wählbaren Episoden-Audiodateien (inkl. einer evtl.
    vorhandenen Anthologie) aus dem Output-Ordner der aktiven Serie sowie dem
    lokalen Lolfi-Ordner podcast/ — gleiche Reihenfolge/Filter wie
    lofi_system.py::PODCAST_DIRS, aber nur zum Auflisten fürs Dropdown, ohne
    Dauer-Probing (das übernimmt lofi_system.py selbst beim Rendern)."""
    pf_series_dir = current_series_dir()
    dirs = [
        os.path.join(LOLFI_DIR, "podcast"),
        os.path.join(pf_series_dir, "output") if pf_series_dir else None,
    ]
    files = []
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if os.path.splitext(fname)[1].lower() not in _PODCAST_AUDIO_EXTS:
                continue
            if any(p in fname.lower() for p in _PODCAST_EXCLUDE_PATTERNS):
                continue
            files.append(fname)
    return files


def lolfi_status(jobs=None) -> dict:
    scene_history = _read_json(os.path.join(LOLFI_DIR, "scene_history.json")) or []
    scene_text = _read_text(os.path.join(LOLFI_DIR, "szene.txt")) or ""
    scene_title_match = re.search(r"^Titel:\s*(.+)$", scene_text, re.MULTILINE)

    prompt_files = sorted(
        glob.glob(os.path.join(LOLFI_DIR, "prompts", "*.txt")),
        key=os.path.getmtime, reverse=True,
    )
    latest_prompt_file = prompt_files[0] if prompt_files else None
    latest_pattern_file = None
    if latest_prompt_file:
        candidate = latest_prompt_file[:-4] + "_pattern.json"
        if os.path.exists(candidate):
            latest_pattern_file = candidate

    def _nonempty_dir(*parts):
        d = os.path.join(LOLFI_DIR, *parts)
        if not os.path.isdir(d):
            return False
        return any(not f.startswith(".") for f in os.listdir(d))

    renders = sorted(
        glob.glob(os.path.join(LOLFI_DIR, "video", "output", "*")),
        key=os.path.getmtime, reverse=True,
    )
    render_rows = [
        {
            "name": os.path.basename(r),
            "size_mb": round(os.path.getsize(r) / (1024 * 1024), 1),
            "mtime": os.path.getmtime(r),
        }
        for r in renders if os.path.isfile(r)
    ]

    running_commands = jobs.snapshot() if jobs else {}

    pf_series_dir = current_series_dir()
    pf_output_dir = os.path.join(pf_series_dir, "output") if pf_series_dir else None
    local_podcast_dir = os.path.join(LOLFI_DIR, "podcast")
    podcast_sources = {
        "local (podcast/)": len([f for f in os.listdir(local_podcast_dir) if f.lower().endswith((".mp3", ".wav"))])
            if os.path.isdir(local_podcast_dir) else 0,
        "Podcast-Fabrik (series/.../output/)": len([f for f in os.listdir(pf_output_dir) if f.lower().endswith((".mp3", ".wav"))])
            if pf_output_dir and os.path.isdir(pf_output_dir) else 0,
    }

    return {
        "scene_count": len(scene_history),
        "current_scene_title": scene_title_match.group(1).strip() if scene_title_match else None,
        "current_scene_text": scene_text,
        "latest_prompt_file": os.path.basename(latest_prompt_file) if latest_prompt_file else None,
        "latest_prompt_state": _state(
            running_commands.get("lolfi_generate_prompts", {}).get("state") == "running",
            bool(latest_prompt_file),
        ),
        "latest_pattern_ready": bool(latest_pattern_file),
        # lofi_system.py akzeptiert den Loop-Clip aus baseline/ (Pingpong)
        # ODER baseline_normal/ (nur vorwärts, Standbild-Auto-Pfad).
        "video_baseline_ready": _nonempty_dir("video", "baseline") or _nonempty_dir("video", "baseline_normal"),
        "music_ready": _nonempty_dir("music"),
        "sfx_baseline_ready": _nonempty_dir("sfx", "baseline"),
        "sfx_variations_ready": _nonempty_dir("sfx", "variations"),
        "renders": render_rows,
        "podcast_sources": podcast_sources,
        "podcast_episode_files": _list_podcast_episode_files(),
        "render_state": _state(
            running_commands.get("lolfi_render", {}).get("state") == "running",
            bool(render_rows),
        ),
        "running_jobs": running_commands,
    }
