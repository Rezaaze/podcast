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


def venv_python(project_dir: str) -> str:
    """.venv/.../python des jeweiligen Projekts, falls vorhanden, sonst der
    Python-Interpreter, mit dem die WebUI selbst läuft."""
    subpath = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    venv_py = os.path.join(project_dir, ".venv", *subpath)
    return venv_py if os.path.exists(venv_py) else sys.executable


# args_schema beschreibt erlaubte Parameter pro Kommando:
#   ("positional", name)              -> wird als einzelnes Argv-Element angehängt
#   ("flag", name, cli_flag)          -> optional, wird als "<cli_flag> <value>" angehängt wenn value gesetzt
#   ("boolflag", name, cli_flag)      -> optional, wird als "<cli_flag>" angehängt wenn value truthy
COMMANDS = {
    "pf_create_series": {
        "label": "Serie erstellen",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "script": "create_series.py",
        "args_schema": [
            ("positional_required", "topic"),
            ("flag", "episodes", "--episodes"),
        ],
        "kind": "line",
    },
    "pf_generate_episode": {
        "label": "Episode generieren",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "script": "generate_episode.py",
        "args_schema": [
            ("positional_required", "episode"),
            ("boolflag", "force", "--force"),
            ("flag", "jobs", "--jobs"),
        ],
        "kind": "line",
    },
    "pf_generate_episode_all": {
        "label": "Alle Episoden generieren (+ vertonen + Anthologie)",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "script": "generate_episode.py",
        "fixed_args": ["all"],
        "args_schema": [
            ("boolflag", "force", "--force"),
            ("flag", "jobs", "--jobs"),
        ],
        "kind": "line",
    },
    "pf_generate_episode_check": {
        "label": "episodes.json validieren",
        "cwd": PF_DIR,
        "interpreter": lambda: sys.executable,
        "script": "generate_episode.py",
        "fixed_args": ["check"],
        "args_schema": [],
        "kind": "line",
    },
    "pf_podcast_maker": {
        "label": "Episode vertonen",
        "cwd": PF_DIR,
        "interpreter": lambda: venv_python(PF_DIR),
        "script": "podcast_maker.py",
        "args_schema": [
            ("positional_required", "input_file"),
            ("flag", "name", "--name"),
        ],
        "kind": "progress_cr",
    },
    "pf_batch": {
        "label": "Alle vertonen + Anthologie mergen",
        "cwd": PF_DIR,
        "interpreter": lambda: venv_python(PF_DIR),
        "script": "batch.py",
        "fixed_args": [],
        "args_schema": [],
        "kind": "line",
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
