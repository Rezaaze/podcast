"""Whitelisted 'Ordner öffnen' — nie ein Roh-Pfad vom Client."""

import os
import subprocess

from config import LOLFI_DIR, PF_DIR, current_series_dir, OUTPUT_RELPATH, CHARACTERS_RELPATH, LOCATIONS_RELPATH, SCRIPTS_RELPATH

ALLOWED_FOLDERS = {
    "pf_root": PF_DIR,
    # pf_output wird in open_folder() dynamisch auf output/ der aktuellen
    # Serie aufgelöst (series/LATEST) — der statische Eintrag ist der
    # Fallback, falls noch keine Serie existiert.
    "pf_output": os.path.join(PF_DIR, "data", "series"),
    # pf_characters/pf_locations werden wie pf_output dynamisch auf die
    # aktuelle Serie aufgelöst.
    "pf_characters": os.path.join(PF_DIR, "data", "series"),
    "pf_locations": os.path.join(PF_DIR, "data", "series"),
    "pf_scripts": os.path.join(PF_DIR, "data", "series"),
    "pf_series_root": os.path.join(PF_DIR, "data", "series"),
    "pf_archive": os.path.join(PF_DIR, "data", "archive"),
    "lolfi_root": LOLFI_DIR,
    # Standbild-Loops (Auto-Pfad von generate_prompts.py) landen in
    # baseline_normal/ — baseline/ (Pingpong, für animierte Clips) bleibt
    # nutzbar, hat aber keinen eigenen WebUI-Button mehr.
    "lolfi_video_baseline": os.path.join(LOLFI_DIR, "video", "baseline_normal"),
    "lolfi_video_output": os.path.join(LOLFI_DIR, "video", "output"),
    "lolfi_music": os.path.join(LOLFI_DIR, "music"),
    "lolfi_prompts": os.path.join(LOLFI_DIR, "prompts"),
    "lolfi_sfx_baseline": os.path.join(LOLFI_DIR, "sfx", "baseline"),
    "lolfi_sfx_variations": os.path.join(LOLFI_DIR, "sfx", "variations"),
    "lolfi_video_overlays": os.path.join(LOLFI_DIR, "video", "overlays"),
}


def open_folder(key: str) -> bool:
    if key not in ALLOWED_FOLDERS:
        return False
    path = ALLOWED_FOLDERS[key]
    if key in ("pf_output", "pf_characters", "pf_locations", "pf_scripts", "pf_series_root"):
        series_dir = current_series_dir()
        if series_dir:
            subdir = {"pf_output": OUTPUT_RELPATH, "pf_characters": CHARACTERS_RELPATH,
                      "pf_locations": LOCATIONS_RELPATH, "pf_scripts": SCRIPTS_RELPATH,
                      "pf_series_root": ""}[key]
            path = os.path.join(series_dir, subdir)
    os.makedirs(path, exist_ok=True)
    subprocess.run(["open", path], check=False)
    return True
