"""Copy-Paste-Block-Assembler für die manuellen Schritte der Pipeline."""

import glob
import os
import re
import sys

from config import LOLFI_DIR, PF_DIR

# Das fabrik-Package liegt eine Ebene über webui/ — Import ermöglichen, damit
# build_prompt() nicht dupliziert werden muss (einzige Quelle der Wahrheit).
if PF_DIR not in sys.path:
    sys.path.insert(0, PF_DIR)

from fabrik.cli import create_series as cs  # noqa: E402

SEPARATOR_RE = re.compile(r"\n-{10,}\n")


def build_series_prompt_block(topic: str, episode_count: int = 3,
                              template: str = "narration",
                              minutes: float = cs.DEFAULT_MINUTES) -> str:
    """Exakt der Prompt, den create_series.py an die claude-CLI schickt —
    fertig zum manuellen Einfügen in Claude, falls create_series.py nicht
    direkt ausgeführt werden soll."""
    return cs.build_prompt(cs.load_creator_prompt(template), topic, episode_count, minutes)


def _split_prompt_sections(text: str) -> list[tuple[str, str]]:
    """Zerlegt eine Lolfi prompts/*.txt-Datei anhand der 70-Bindestrich-
    Trennlinien in (header, body)-Paare. Format (stabil, siehe generate_prompts.py):
    ...\\nHEADER\\n----...----\\nBODY\\n\\nHEADER2\\n----...----\\nBODY2\\n..."""
    parts = SEPARATOR_RE.split(text)
    n_sep = len(parts) - 1
    if n_sep <= 0:
        return []

    headers = [None] * n_sep
    bodies = [None] * n_sep

    headers[0] = parts[0].strip().split("\n\n")[-1].strip()
    for k in range(1, n_sep):
        paras = parts[k].strip("\n").split("\n\n")
        if len(paras) > 1:
            bodies[k - 1] = "\n\n".join(paras[:-1]).strip()
            headers[k] = paras[-1].strip()
        else:
            bodies[k - 1] = paras[0].strip()
            headers[k] = ""
    bodies[n_sep - 1] = parts[n_sep].strip()

    return list(zip(headers, bodies))


def parse_latest_prompt_set() -> dict:
    """Findet die neueste prompts/*.txt in Lolfi und extrahiert die
    Copy-Paste-Blöcke (Bild-Prompt inkl. Negativ, Suno-Musik-Prompt).
    Ältere Prompt-Dateien können noch KLING-Abschnitte enthalten — die
    werden schlicht ignoriert."""
    prompt_files = sorted(
        glob.glob(os.path.join(LOLFI_DIR, "prompts", "*.txt")),
        key=os.path.getmtime, reverse=True,
    )
    if not prompt_files:
        return {"source_file": None}

    latest = prompt_files[0]
    with open(latest, "r", encoding="utf-8") as f:
        text = f.read()

    result = {
        "source_file": os.path.basename(latest),
        "scene_summary": "",
        "image_prompt": "",
        "image_negative_prompt": "",
        "suno_prompt": "",
    }

    for header, body in _split_prompt_sections(text):
        if "SZENEN-KONZEPT" in header:
            result["scene_summary"] = body
        elif "BILD-PROMPT" in header:
            m = re.search(r"^Negativ:\s*(.+)$", body, re.MULTILINE)
            if m:
                result["image_negative_prompt"] = m.group(1).strip()
                result["image_prompt"] = body[:m.start()].strip()
            else:
                result["image_prompt"] = body
        elif "SUNO MUSIK-PROMPT" in header:
            result["suno_prompt"] = body

    return result


CHARACTER_BLOCK_RE = re.compile(r"===\s*([A-Z0-9_]+)\s*===")


def read_character_prompts(series_slug=None) -> dict:
    """Liest series/<slug>/characters/PROMPTS.txt (character_prompts.py) und
    zerlegt sie in einen Copy-Paste-Block pro Rolle. Meldet zusätzlich, für
    welche Rollen bereits ein Bild im characters/-Ordner liegt."""
    from config import current_series_dir, series_dir_for, CHARACTERS_RELPATH
    series_dir = series_dir_for(series_slug) or current_series_dir()
    if not series_dir:
        return {"prompts_ready": False, "characters": []}
    characters_dir = os.path.join(series_dir, CHARACTERS_RELPATH)
    prompts_path = os.path.join(characters_dir, "PROMPTS.txt")

    existing_images = {}
    if os.path.isdir(characters_dir):
        for fname in os.listdir(characters_dir):
            stem, ext = os.path.splitext(fname)
            if ext.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                existing_images[stem.upper()] = fname

    if not os.path.exists(prompts_path):
        return {"prompts_ready": False, "characters": []}

    with open(prompts_path, "r", encoding="utf-8") as f:
        text = f.read()

    characters = []
    chunks = CHARACTER_BLOCK_RE.split(text)
    for i in range(1, len(chunks), 2):
        role = chunks[i].strip()
        prompt = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
        characters.append({
            "role": role,
            "prompt": prompt,
            "image": existing_images.get(role.upper()),
            "target_filename": f"{role}.png",
        })

    return {"prompts_ready": True, "characters": characters}


def read_location_prompts(series_slug=None) -> dict:
    """Liest series/<slug>/locations/PROMPTS.txt (location_prompts.py) und
    zerlegt sie in einen Copy-Paste-Block pro Ort. Meldet zusätzlich, für
    welche Orte bereits ein Bild im locations/-Ordner liegt."""
    from config import current_series_dir, series_dir_for, LOCATIONS_RELPATH
    series_dir = series_dir_for(series_slug) or current_series_dir()
    if not series_dir:
        return {"prompts_ready": False, "locations": []}
    locations_dir = os.path.join(series_dir, LOCATIONS_RELPATH)
    prompts_path = os.path.join(locations_dir, "PROMPTS.txt")

    existing_images = {}
    if os.path.isdir(locations_dir):
        for fname in os.listdir(locations_dir):
            stem, ext = os.path.splitext(fname)
            if ext.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                existing_images[stem.upper()] = fname

    if not os.path.exists(prompts_path):
        return {"prompts_ready": False, "locations": []}

    with open(prompts_path, "r", encoding="utf-8") as f:
        text = f.read()

    locations = []
    chunks = CHARACTER_BLOCK_RE.split(text)
    for i in range(1, len(chunks), 2):
        key = chunks[i].strip()
        prompt = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
        locations.append({
            "key": key,
            "prompt": prompt,
            "image": existing_images.get(key.upper()),
            "target_filename": f"{key}.png",
        })

    return {"prompts_ready": True, "locations": locations}


def read_anthology_meta() -> dict:
    from config import current_series_dir, SCRIPTS_RELPATH, OUTPUT_RELPATH
    series_dir = current_series_dir()
    anthology_meta_path = os.path.join(series_dir, SCRIPTS_RELPATH, "ANTHOLOGY_META.txt") if series_dir else ""
    upload_index_path = os.path.join(series_dir, OUTPUT_RELPATH, "UPLOAD_INDEX.md") if series_dir else ""

    def _read(path):
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    return {
        "anthology_meta": _read(anthology_meta_path),
        "upload_index": _read(upload_index_path),
    }
