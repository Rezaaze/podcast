"""Pfade beider Projekte + feste Kommando-Whitelist für runner.py.

Der Browser sendet nur einen command_id-String + Parameter — nie Pfade,
Interpreter oder Rohbefehle. Diese Datei ist die einzige Quelle dafür, was
überhaupt ausgeführt werden kann.
"""

import os
import sys

WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))
PF_DIR = os.path.dirname(WEBUI_DIR)
LOLFI_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "Lolfi")

# Das Serien-Layout (MWP-Workspace: stages/NN_*/output/) lebt in
# fabrik/core/paths.py — stdlib-only, daher auch aus dem WebUI-venv
# importierbar. Die Relativpfade hier sind die EINZIGE Layout-Kenntnis
# des WebUI; nie wieder Ordnernamen hart verdrahten.
sys.path.insert(0, PF_DIR)
from fabrik.core import paths as pf_paths  # noqa: E402

EPISODES_RELPATH = pf_paths.EPISODES_RELPATH
SCRIPTS_RELPATH = os.path.join(pf_paths.STAGE_SCRIPTS, "output")
OUTPUT_RELPATH = os.path.join(pf_paths.STAGE_AUDIO, "output")
VISUALS_RELPATH = os.path.join(pf_paths.STAGE_VISUALS, "output")
CHARACTERS_RELPATH = os.path.join(VISUALS_RELPATH, "characters")
LOCATIONS_RELPATH = os.path.join(VISUALS_RELPATH, "locations")


def series_root_dir():
    return os.path.join(PF_DIR, "data", "series")


def list_series_slugs() -> list:
    """Alle Serien-Slugs mit vorhandener episodes.json, alphabetisch."""
    root = series_root_dir()
    if not os.path.isdir(root):
        return []
    return sorted(
        d for d in os.listdir(root)
        if os.path.exists(os.path.join(root, d, EPISODES_RELPATH))
    )


def read_latest_slug():
    try:
        with open(os.path.join(series_root_dir(), "LATEST"), "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def write_latest_slug(slug: str):
    root = series_root_dir()
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "LATEST"), "w", encoding="utf-8") as f:
        f.write(slug + "\n")


def series_dir_for(slug):
    """Pfad zu series/<slug>/, NUR wenn slug tatsächlich existiert (Schutz
    gegen Path-Traversal über einen vom Client kommenden Query-Parameter)."""
    if slug and slug in list_series_slugs():
        return os.path.join(series_root_dir(), slug)
    return None


def current_series_dir():
    """series/<slug>/ der aktuellen Serie (series/LATEST bzw. die einzige
    vorhandene Serie) — jede Serie hat dort episodes.json, scripts/ und
    output/. Gibt None zurück, wenn (noch) keine Serie existiert."""
    latest = read_latest_slug()
    d = series_dir_for(latest)
    if d:
        return d
    candidates = list_series_slugs()
    if len(candidates) == 1:
        return os.path.join(series_root_dir(), candidates[0])
    return None


def current_episodes_json():
    d = current_series_dir()
    return os.path.join(d, EPISODES_RELPATH) if d else None


def venv_python(project_dir: str) -> str:
    """.venv/.../python des jeweiligen Projekts, falls vorhanden, sonst der
    Python-Interpreter, mit dem die WebUI selbst läuft."""
    subpath = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    venv_py = os.path.join(project_dir, ".venv", *subpath)
    return venv_py if os.path.exists(venv_py) else sys.executable


# Pro Kommando entweder "script" (Datei relativ zu cwd) oder "module"
# (python -m <module>, für die fabrik.cli-Entry-Points — cwd muss dann
# PF_DIR sein, damit das fabrik-Package auf sys.path liegt).
#
# args_schema beschreibt erlaubte Parameter pro Kommando:
#   ("positional", name)              -> wird als einzelnes Argv-Element angehängt
#   ("flag", name, cli_flag)          -> optional, wird als "<cli_flag> <value>" angehängt wenn value gesetzt
#   ("boolflag", name, cli_flag)      -> optional, wird als "<cli_flag>" angehängt wenn value truthy
COMMANDS = {
    "pf_create_series": {
        "label": "Serie erstellen",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "module": "fabrik.cli.create_series",
        "args_schema": [
            ("positional_required", "topic"),
            ("flag", "episodes", "--episodes"),
            ("flag", "template", "--template"),
            ("flag", "minutes", "--minutes"),
            ("flag", "locations", "--locations"),
        ],
        "kind": "line",
    },
    "pf_import_story": {
        "label": "Aus vorhandenem Text importieren",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "module": "fabrik.cli.import_story",
        "args_schema": [
            ("positional_required", "source"),
            ("positional_required", "series_title"),
            ("flag", "template", "--template"),
            ("boolflag", "no_summary", "--no-summary"),
        ],
        "kind": "line",
    },
    "pf_generate_episode": {
        "label": "Episode generieren",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "module": "fabrik.cli.generate_episode",
        "args_schema": [
            ("positional_required", "episode"),
            ("boolflag", "force", "--force"),
            ("boolflag", "fix", "--fix"),
            ("flag", "jobs", "--jobs"),
            ("flag", "series", "--series"),
        ],
        "kind": "line",
    },
    "pf_generate_episode_all": {
        "label": "Alle Episoden generieren (+ vertonen + Anthologie)",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "module": "fabrik.cli.generate_episode",
        "fixed_args": ["all"],
        "args_schema": [
            ("boolflag", "force", "--force"),
            ("boolflag", "fix", "--fix"),
            ("flag", "jobs", "--jobs"),
            ("flag", "series", "--series"),
        ],
        "kind": "line",
        "poll_checkpoints": True,
    },
    "pf_generate_episode_check": {
        "label": "episodes.json validieren",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "module": "fabrik.cli.generate_episode",
        "fixed_args": ["check"],
        "args_schema": [
            ("flag", "series", "--series"),
        ],
        "kind": "line",
    },
    "pf_podcast_maker": {
        "label": "Episode vertonen",
        "cwd": PF_DIR,
        "interpreter": lambda: venv_python(PF_DIR),
        "module": "fabrik.cli.podcast_maker",
        "args_schema": [
            ("positional_required", "input_file"),
            ("flag", "name", "--name"),
            ("flag", "series", "--series"),
        ],
        "kind": "progress_cr",
        "poll_checkpoints": True,
    },
    # Cloud-Vertonung: wrappt cloud/render_remote.sh (Upload, Remote-batch.py
    # gegen 127.0.0.1, Download der Ergebnisse). Bewusst NICHT in
    # AUTO_TTS_COMMANDS -- die TTS läuft auf der vast.ai-Instanz, das lokale
    # Pinokio/Qwen3 bleibt aus. "only" rendert eine einzelne Skript-Datei
    # (podcast_maker statt batch), "stop_after" pausiert die Instanz danach.
    "pf_render_remote": {
        "label": "Cloud-Vertonung (vast.ai, render_remote.sh)",
        "cwd": PF_DIR,
        "interpreter": lambda: "/bin/bash",
        "interpreter_args": [],
        "script": os.path.join("cloud", "render_remote.sh"),
        "args_schema": [
            ("positional_required", "series"),
            ("flag", "only", "--only"),
            ("boolflag", "stop_after", "--stop-after"),
        ],
        "kind": "line",
    },
    # Vertont ALLE fehlenden Episoden einer Serie PARALLEL auf mehreren
    # vast.ai-Instanzen (wellenweise zu je "max_parallel"): wrappt
    # cloud/render_remote_parallel.sh. Bewusst NICHT in AUTO_TTS_COMMANDS
    # (kein lokales TTS nötig). "episodes" optional -- ohne das erkennt das
    # Script selbst, welche Episoden noch keine <Prefix>_FULL_EPISODE.mp3
    # haben.
    "pf_render_remote_parallel": {
        "label": "Cloud-Vertonung parallel (mehrere Instanzen, render_remote_parallel.sh)",
        "cwd": PF_DIR,
        "interpreter": lambda: "/bin/bash",
        "interpreter_args": [],
        "script": os.path.join("cloud", "render_remote_parallel.sh"),
        "args_schema": [
            ("positional_required", "series"),
            ("flag", "max_parallel", "--max"),
            ("flag", "episodes", "--episodes"),
        ],
        "kind": "line",
    },
    "pf_batch": {
        "label": "Alle vertonen + Anthologie mergen",
        "cwd": PF_DIR,
        "interpreter": lambda: venv_python(PF_DIR),
        "module": "fabrik.cli.batch",
        "fixed_args": [],
        "args_schema": [
            ("flag", "series", "--series"),
        ],
        "kind": "line",
        "poll_checkpoints": True,
    },
    "lolfi_generate_scene": {
        "label": "Neue Szene generieren",
        "cwd": LOLFI_DIR,
        "interpreter": lambda: sys.executable,
        "script": "generate_scene.py",
        "fixed_args": [],
        "args_schema": [],
        "kind": "line",
    },
    "lolfi_generate_prompts": {
        "label": "Prompts aus Szene generieren",
        "cwd": LOLFI_DIR,
        "interpreter": lambda: sys.executable,
        "script": "generate_prompts.py",
        "fixed_args": ["--scene-file", "szene.txt"],
        "args_schema": [
            ("flag", "style", "--style"),
        ],
        "kind": "line",
    },
    "pf_character_prompts": {
        "label": "Charakter-Porträt-Prompts generieren",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "module": "fabrik.cli.character_prompts",
        "args_schema": [
            ("boolflag", "force", "--force"),
            ("flag", "series", "--series"),
        ],
        "kind": "line",
    },
    "pf_location_prompts": {
        "label": "Location-Bild-Prompts generieren",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "module": "fabrik.cli.location_prompts",
        "args_schema": [
            ("boolflag", "force", "--force"),
            ("flag", "series", "--series"),
        ],
        "kind": "line",
    },
    "pf_cover_art": {
        "label": "Cover-Bild generieren",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "module": "fabrik.cli.cover_art",
        "args_schema": [
            ("boolflag", "force", "--force"),
            ("flag", "series", "--series"),
        ],
        "kind": "line",
    },
    "pf_tts_start": {
        "label": "TTS starten (Pinokio/Qwen3)",
        "kind": "pyfunc",
        "pyfunc": "tts_control.start_tts",
        "args_schema": [],
    },
    "pf_tts_stop": {
        "label": "TTS stoppen (Pinokio/Qwen3)",
        "kind": "pyfunc",
        "pyfunc": "tts_control.stop_tts",
        "args_schema": [],
    },
    "lolfi_render": {
        "label": "Video rendern (lofi_system.py)",
        "cwd": LOLFI_DIR,
        "interpreter": lambda: venv_python(LOLFI_DIR),
        "script": "lofi_system.py",
        "fixed_args": [],
        "args_schema": [
            ("flag", "episode", "--episode"),
        ],
        "kind": "cr_steps",
    },
    "lolfi_render_all": {
        "label": "Alle Episoden einzeln rendern (lofi_system.py --all)",
        "cwd": LOLFI_DIR,
        "interpreter": lambda: venv_python(LOLFI_DIR),
        "script": "lofi_system.py",
        "fixed_args": ["--all"],
        "args_schema": [],
        "kind": "cr_steps",
    },
}

# Diese Kommandos brauchen die lokale Qwen3-TTS-API. runner.py startet dafür
# automatisch Pinokio + die TTS-App, bevor der Subprocess läuft, und stoppt
# sie danach wieder (Ressourcen sparen — läuft nicht dauerhaft im Hintergrund).
AUTO_TTS_COMMANDS = {
    "pf_podcast_maker",
    "pf_batch",
    # "all" generiert Skripte UND ruft batch.py am Ende intern selbst als
    # eigenen Subprozess auf (siehe generate_episode.py) — das läuft an
    # unserer Job-Steuerung vorbei, daher muss TTS schon vor diesem
    # Kommando bereitstehen, nicht erst bei "pf_batch" selbst.
    "pf_generate_episode_all",
}
