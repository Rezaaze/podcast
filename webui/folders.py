"""Whitelisted 'Ordner öffnen' — nie ein Roh-Pfad vom Client."""

import os
import subprocess

from config import LOLFI_DIR, PF_DIR

ALLOWED_FOLDERS = {
    "pf_root": PF_DIR,
    "pf_output": os.path.join(PF_DIR, "podcast_output"),
    "pf_archive": os.path.join(PF_DIR, "archive"),
    "lolfi_root": LOLFI_DIR,
    "lolfi_video_baseline": os.path.join(LOLFI_DIR, "video", "baseline"),
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
    os.makedirs(path, exist_ok=True)
    subprocess.run(["open", path], check=False)
    return True
