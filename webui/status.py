"""Read-only Status-Dashboard-Funktionen. Kein Caching — jeder Aufruf liest
die aktuellen Dateien frisch von Disk."""

import glob
import json
import os

from config import (PF_DIR, current_series_dir, series_dir_for,
                    EPISODES_RELPATH, SCRIPTS_RELPATH, OUTPUT_RELPATH,
                    CHARACTERS_RELPATH, LOCATIONS_RELPATH, THUMBNAILS_RELPATH, VISUALS_RELPATH,
                    SFX_PLAN_RELPATH, SFX_ONESHOTS_RELPATH)

from fabrik.core.textproc import sfx_asset_hash


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


def any_command_running(running_commands: dict, *command_ids: str) -> bool:
    """jobs.snapshot() ist seit dem per-Serie-Lock nach runner.py::_lock_key()
    geschlüsselt (nicht mehr 1:1 nach command_id — AUTO_TTS_COMMANDS teilen
    sich sogar einen einzigen Schlüssel) — command_id steht aber weiterhin
    als Feld in jedem Eintrag, hier drüber suchen statt per Dict-Lookup."""
    return any(
        job.get("command_id") in command_ids and job.get("state") == "running"
        for job in running_commands.values()
    )


def _load_sfx_coverage(series_dir):
    """Liest SFX_PLAN.json (falls vorhanden) und liefert
    (needed_keys_by_episode, asset_hash_by_key, unplanned_episodes) — die
    Zutaten, um pro Episode zu sehen, wie viele ihrer geplanten SFX-Assets
    schon als Datei in sfx/oneshots/ liegen. asset_hash_by_key spiegelt
    fabrik/cli/sfx_assets.py::jobs_from_plan()'s Hash-Herleitung (Plan-Feld
    'asset', sonst sfx_asset_hash(prompt)) — MUSS identisch bleiben, sonst
    zeigt das Cockpit eine Datei als fehlend an, die podcast_maker/Lolfi
    unter einem anderen Namen längst gefunden hätten."""
    plan = _read_json(os.path.join(series_dir, SFX_PLAN_RELPATH)) if series_dir else None
    if not plan:
        return None
    asset_hash_by_key = {}
    for asset in plan.get("palette", []):
        key = asset.get("key")
        prompt = (asset.get("prompt") or "").strip()
        if key and prompt:
            asset_hash_by_key[key] = asset.get("asset") or sfx_asset_hash(prompt)
    needed_keys_by_episode = {}
    for cue in plan.get("cues", []):
        if not cue.get("keep") or not cue.get("asset_key"):
            continue
        ep = cue.get("episode")
        if ep is None:
            continue
        needed_keys_by_episode.setdefault(ep, set()).add(cue["asset_key"])
    unplanned = set(plan.get("unplanned_episodes") or [])
    return needed_keys_by_episode, asset_hash_by_key, unplanned


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
    podcast_maker_running = any_command_running(
        running_commands, "pf_podcast_maker", "pf_batch", "pf_generate_episode_all")

    thumbnails_dir = os.path.join(series_dir, THUMBNAILS_RELPATH) if series_dir else None
    sfx_coverage = _load_sfx_coverage(series_dir) if series_dir else None
    is_drama = episodes_json.get("mode") == "drama"

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

        # Thumbnail: braucht BEIDE Größen (16:9 + 1:1, siehe episode_thumbnails.py).
        thumb_ready = bool(thumbnails_dir) and (
            os.path.exists(os.path.join(thumbnails_dir, f"{prefix}{i}_wide.png"))
            and os.path.exists(os.path.join(thumbnails_dir, f"{prefix}{i}_square.png")))

        # Highlights: nur sinnvoll, sobald die Episode vertont ist (highlight_clips.py
        # braucht die _SUBS.json-Timing-Cues, die erst beim Vertonen entstehen).
        highlights_ready = audio_ready and os.path.exists(
            os.path.join(output_dir, f"{name}_FULL_EPISODE_HIGHLIGHTS.json"))

        # SFX-Abdeckung: nur für Drama-Serien sinnvoll (narration hat keine Cues).
        # "none" = kein Plan ODER der Plan deckt diese Episode (noch) nicht ab
        # (unplanned_episodes) ODER keine Cues behalten — kein Fehlzustand,
        # nur "hier gibt's nichts zu prüfen".
        sfx_state = None
        if is_drama:
            if not sfx_coverage:
                sfx_state = "none"
            else:
                needed_by_ep, asset_hash_by_key, unplanned = sfx_coverage
                if i in unplanned:
                    sfx_state = "none"
                else:
                    needed_keys = needed_by_ep.get(i, set())
                    needed_hashes = {asset_hash_by_key[k] for k in needed_keys if k in asset_hash_by_key}
                    if not needed_hashes:
                        sfx_state = "none"
                    else:
                        have = sum(
                            1 for h in needed_hashes
                            if os.path.exists(os.path.join(series_dir, SFX_ONESHOTS_RELPATH, f"{h}.mp3")))
                        sfx_state = _state(False, have >= len(needed_hashes), have > 0)

        episode_rows.append({
            "index": i,
            "figure": ep.get("figure", ""),
            "script_file": f"{prefix}{i}.txt",
            "script_state": _state(False, script_ready and meta_ready, script_ready),
            "audio_state": _state(audio_in_progress, audio_ready),
            "thumbnail_state": _state(False, thumb_ready),
            "highlights_state": "none" if not audio_ready else _state(False, highlights_ready),
            "sfx_state": sfx_state,
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

    # Teaser-Highlights / Episoden-Thumbnails: Aggregate abgeleitet aus den
    # bereits pro Episode berechneten States oben (episode_rows) — EINE
    # Quelle der Wahrheit statt zweier eigener Verzeichnis-Scans, die exakt
    # dieselben Dateien nochmal prüften.
    highlights = {
        "audio_ready": sum(1 for e in episode_rows if e["audio_state"] == "ready"),
        "with_highlights": sum(1 for e in episode_rows if e["highlights_state"] == "ready"),
    }
    thumbnails = {
        "ready": sum(1 for e in episode_rows if e["thumbnail_state"] == "ready"),
        "total": len(episodes),
    }
    sfx_summary = None
    if is_drama:
        covered = [e for e in episode_rows if e["sfx_state"] not in (None, "none")]
        sfx_summary = {
            "plan_exists": sfx_coverage is not None,
            "episodes_ready": sum(1 for e in covered if e["sfx_state"] == "ready"),
            "episodes_with_cues": len(covered),
        }

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
            any_command_running(running_commands, "pf_batch"),
            os.path.exists(anthology_file),
        ),
        "characters": characters,
        "locations": locations,
        "highlights": highlights,
        "thumbnails": thumbnails,
        "sfx": sfx_summary,
        "cover_exists": cover_exists,
        "anthology_meta_exists": os.path.exists(os.path.join(scripts_dir, "ANTHOLOGY_META.txt")),
        "upload_index_exists": os.path.exists(os.path.join(output_dir, "UPLOAD_INDEX.md")),
        "archive_count": archive_count,
        "running_jobs": running_commands,
    }
