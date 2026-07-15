"""Read-only Status-Dashboard-Funktionen. Kein Caching — jeder Aufruf liest
die aktuellen Dateien frisch von Disk."""

import glob
import json
import os

from config import (PF_DIR, current_series_dir, series_dir_for,
                    EPISODES_RELPATH, SCRIPTS_RELPATH, OUTPUT_RELPATH,
                    CHARACTERS_RELPATH, LOCATIONS_RELPATH, THUMBNAILS_RELPATH, VISUALS_RELPATH)


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
    scripts_dir = os.path.join(series_dir, SCRIPTS_RELPATH) if series_dir else PF_DIR
    episodes_json = (_read_json(os.path.join(series_dir, EPISODES_RELPATH)) if series_dir else None) or {}
    prefix = episodes_json.get("output_prefix", "figur")
    episodes = episodes_json.get("episodes", [])
    output_dir = os.path.join(series_dir, OUTPUT_RELPATH) if series_dir else os.path.join(PF_DIR, "data", "series")
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

    # Endgültig gescheiterte Vertonungen (batch.py schreibt/löscht den Marker
    # nach den Retry-Runden) — treibt eine rote Alarm-Karte in der WebUI.
    failed_marker = _read_json(os.path.join(output_dir, "FAILED_EPISODES.json")) or {}
    failed_episodes = failed_marker.get("failed", [])

    anthology_file = os.path.join(output_dir, "ANTHOLOGY_COMPLETE.mp3")
    archive_dir = os.path.join(PF_DIR, "data", "archive")
    archive_count = len(os.listdir(archive_dir)) if os.path.isdir(archive_dir) else 0

    # Charakter-Porträts (nur Drama-Serien): wie viele Rollen haben schon ein
    # Bild in characters/? Treibt den Video-Vorbereitungs-Schritt der WebUI.
    roles = [r for r in episodes_json.get("voices", {}) if r != "NARRATOR"]
    characters_dir = os.path.join(series_dir, CHARACTERS_RELPATH) if series_dir else None
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
    locations_dir = os.path.join(series_dir, LOCATIONS_RELPATH) if series_dir else None
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
    cover_exists = bool(series_dir) and os.path.exists(os.path.join(series_dir, VISUALS_RELPATH, "cover.png"))

    # Teaser-Highlights (fabrik.cli.highlight_clips): wie viele der vertonten
    # Episoden haben schon ein <Name>_FULL_EPISODE_HIGHLIGHTS.json? Muster
    # wie characters/locations oben — reiner Existenz-Check.
    highlights_audio = highlights_ready = 0
    for i in range(1, len(episodes) + 1):
        name = f"{prefix}{i}".capitalize()
        if os.path.exists(os.path.join(output_dir, f"{name}_FULL_EPISODE.mp3")):
            highlights_audio += 1
            if os.path.exists(os.path.join(output_dir, f"{name}_FULL_EPISODE_HIGHLIGHTS.json")):
                highlights_ready += 1
    highlights = {"audio_ready": highlights_audio, "with_highlights": highlights_ready}

    # Episoden-Thumbnails (fabrik.cli.episode_thumbnails / automatisch am Ende
    # jeder Episoden-Generierung): wie viele Episoden haben schon BEIDE
    # Größen (<prefix>N_wide.png + <prefix>N_square.png)?
    thumbnails_dir = os.path.join(series_dir, THUMBNAILS_RELPATH) if series_dir else None
    thumbnails_ready = 0
    if thumbnails_dir and os.path.isdir(thumbnails_dir):
        for i in range(1, len(episodes) + 1):
            if (os.path.exists(os.path.join(thumbnails_dir, f"{prefix}{i}_wide.png"))
                    and os.path.exists(os.path.join(thumbnails_dir, f"{prefix}{i}_square.png"))):
                thumbnails_ready += 1
    thumbnails = {"ready": thumbnails_ready, "total": len(episodes)}

    return {
        "series_slug": os.path.basename(series_dir) if series_dir else None,
        "series_title": episodes_json.get("series_title"),
        "language": episodes_json.get("language"),
        "mode": episodes_json.get("mode", "narration"),
        "template": episodes_json.get("template", "narration"),
        "episode_count": len(episodes),
        "episodes": episode_rows,
        "failed_episodes": failed_episodes,
        "anthology_state": _state(
            running_commands.get("pf_batch", {}).get("state") == "running",
            os.path.exists(anthology_file),
        ),
        "characters": characters,
        "locations": locations,
        "highlights": highlights,
        "thumbnails": thumbnails,
        "cover_exists": cover_exists,
        "anthology_meta_exists": os.path.exists(os.path.join(scripts_dir, "ANTHOLOGY_META.txt")),
        "upload_index_exists": os.path.exists(os.path.join(output_dir, "UPLOAD_INDEX.md")),
        "archive_count": archive_count,
        "running_jobs": running_commands,
    }
