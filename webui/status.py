"""Read-only Status-Dashboard-Funktionen. Kein Caching — jeder Aufruf liest
die aktuellen Dateien frisch von Disk."""

import glob
import json
import os
import re

from config import LOLFI_DIR, PF_DIR


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


def pf_status(jobs=None) -> dict:
    episodes_json = _read_json(os.path.join(PF_DIR, "episodes.json")) or {}
    prefix = episodes_json.get("output_prefix", "figur")
    episodes = episodes_json.get("episodes", [])
    output_dir = os.path.join(PF_DIR, "podcast_output")
    checkpoints_dir = os.path.join(output_dir, ".checkpoints")

    running_commands = jobs.snapshot() if jobs else {}
    podcast_maker_running = running_commands.get("pf_podcast_maker", {}).get("state") == "running"

    episode_rows = []
    for i, ep in enumerate(episodes, start=1):
        script_file = os.path.join(PF_DIR, f"{prefix}{i}.txt")
        meta_file = os.path.join(PF_DIR, f"{prefix}{i}_META.txt")
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
    archive_dir = os.path.join(PF_DIR, "archive")
    archive_count = len(os.listdir(archive_dir)) if os.path.isdir(archive_dir) else 0

    return {
        "series_title": episodes_json.get("series_title"),
        "language": episodes_json.get("language"),
        "episode_count": len(episodes),
        "episodes": episode_rows,
        "anthology_state": _state(
            running_commands.get("pf_batch", {}).get("state") == "running",
            os.path.exists(anthology_file),
        ),
        "anthology_meta_exists": os.path.exists(os.path.join(PF_DIR, "ANTHOLOGY_META.txt")),
        "upload_index_exists": os.path.exists(os.path.join(output_dir, "UPLOAD_INDEX.md")),
        "archive_count": archive_count,
        "running_jobs": running_commands,
    }


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

    pf_output_dir = os.path.join(PF_DIR, "podcast_output")
    local_podcast_dir = os.path.join(LOLFI_DIR, "podcast")
    podcast_sources = {
        "local (podcast/)": len([f for f in os.listdir(local_podcast_dir) if f.lower().endswith((".mp3", ".wav"))])
            if os.path.isdir(local_podcast_dir) else 0,
        "Podcast-Fabrik (podcast_output/)": len([f for f in os.listdir(pf_output_dir) if f.lower().endswith((".mp3", ".wav"))])
            if os.path.isdir(pf_output_dir) else 0,
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
        "video_baseline_ready": _nonempty_dir("video", "baseline"),
        "music_ready": _nonempty_dir("music"),
        "sfx_baseline_ready": _nonempty_dir("sfx", "baseline"),
        "sfx_variations_ready": _nonempty_dir("sfx", "variations"),
        "renders": render_rows,
        "podcast_sources": podcast_sources,
        "render_state": _state(
            running_commands.get("lolfi_render", {}).get("state") == "running",
            bool(render_rows),
        ),
        "running_jobs": running_commands,
    }
