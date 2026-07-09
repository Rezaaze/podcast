"""Copy-Paste-Block-Assembler für die manuellen Schritte der Pipeline."""

import glob
import os
import re
import sys

from config import LOLFI_DIR, PF_DIR

# create_series.py liegt eine Ebene über webui/ — Import ermöglichen, damit
# build_prompt() nicht dupliziert werden muss (einzige Quelle der Wahrheit).
if PF_DIR not in sys.path:
    sys.path.insert(0, PF_DIR)

import create_series as cs  # noqa: E402

SEPARATOR_RE = re.compile(r"\n-{10,}\n")


def build_series_prompt_block(topic: str, episode_count: int = 3) -> str:
    """Exakt der Prompt, den create_series.py an die claude-CLI schickt —
    fertig zum manuellen Einfügen in Claude, falls create_series.py nicht
    direkt ausgeführt werden soll."""
    return cs.build_prompt(topic, episode_count)


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
    Copy-Paste-Blöcke (Bild-Prompt inkl. Negativ, Kling Loop-Prompt,
    Kling-Negativ, Suno-Musik-Prompt)."""
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
        "kling_loop_prompt": "",
        "kling_negative_prompt": "",
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
        elif "KLING LOOP-PROMPT" in header:
            result["kling_loop_prompt"] = body
        elif "KLING NEGATIV-PROMPT" in header:
            result["kling_negative_prompt"] = body
        elif "SUNO MUSIK-PROMPT" in header:
            result["suno_prompt"] = body

    return result


def read_anthology_meta() -> dict:
    anthology_meta_path = os.path.join(PF_DIR, "ANTHOLOGY_META.txt")
    upload_index_path = os.path.join(PF_DIR, "podcast_output", "UPLOAD_INDEX.md")

    def _read(path):
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    return {
        "anthology_meta": _read(anthology_meta_path),
        "upload_index": _read(upload_index_path),
    }
