"""Scaffolding des MWP-Workspace einer Serie (stdlib-only).

Stanzt beim Anlegen einer Serie die Kontext-Dateien aus
templates/_workspace/ in den Serien-Ordner (CLAUDE.md = Layer 0,
CONTEXT.md = Layer 1, stages/NN_*/CONTEXT.md = Layer-2-Verträge) und
kopiert die Prompt-Dateien des Templates nach references/ — Stage 02
liest das Skript-Prompt der SERIE, nicht mehr das globale Master-Template
(Reproduzierbarkeit: Master-Änderungen erreichen nur neue Serien).

Idempotent: vorhandene Dateien werden nie überschrieben — Hand-Edits an
Verträgen oder am Serien-Prompt überleben jeden Re-Run.
"""

import os
import shutil
import datetime

from . import paths

WORKSPACE_TEMPLATES_DIR = os.path.join(paths.TEMPLATES_DIR, "_workspace")

# Vorlagendatei -> Zielpfad relativ zum Serien-Root
_STAGE_CONTEXT_MAP = {
    "stage_01_CONTEXT.md": paths.STAGE_CONCEPT,
    "stage_02_CONTEXT.md": paths.STAGE_SCRIPTS,
    "stage_03_CONTEXT.md": paths.STAGE_AUDIO,
    "stage_04_CONTEXT.md": paths.STAGE_VISUALS,
}

# Aus templates/<name>/ nach references/ kopierte Dateien
_REFERENCE_FILES = ("PROMPT_TEMPLATE.md", "EPISODES_CREATOR_PROMPT.md")


def _render(template_path, dest_path, replacements):
    if os.path.exists(dest_path):
        return False
    with open(template_path, "r", encoding="utf-8") as f:
        text = f.read()
    for key, value in replacements.items():
        text = text.replace(key, str(value))
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def scaffold_workspace(series, data, template_name):
    """Legt den kompletten Workspace-Baum + Kontext-Dateien an.

    `data` ist die (bereits validierte) episodes.json-Struktur — nur für
    die Platzhalter-Befüllung; geschrieben wird sie vom Aufrufer.
    """
    series.ensure_dirs()

    replacements = {
        "{{SERIES_TITLE}}": data.get("series_title", series.slug),
        "{{SLUG}}": series.slug,
        "{{TEMPLATE}}": template_name,
        "{{MODE}}": data.get("mode", "narration"),
        "{{EPISODES_TOTAL}}": len(data.get("episodes", [])),
        "{{CREATED}}": datetime.date.today().isoformat(),
    }

    written = []
    for src_name, dest in (("CLAUDE.md", "CLAUDE.md"), ("CONTEXT.md", "CONTEXT.md")):
        if _render(os.path.join(WORKSPACE_TEMPLATES_DIR, src_name),
                   os.path.join(series.root, dest), replacements):
            written.append(dest)

    for src_name, stage in _STAGE_CONTEXT_MAP.items():
        dest = os.path.join(stage, "CONTEXT.md")
        if _render(os.path.join(WORKSPACE_TEMPLATES_DIR, src_name),
                   os.path.join(series.root, dest), replacements):
            written.append(dest)

    template_src = paths.template_dir(template_name)
    for name in _REFERENCE_FILES:
        src = os.path.join(template_src, name)
        dest = os.path.join(series.references_dir, name)
        if os.path.exists(src) and not os.path.exists(dest):
            shutil.copyfile(src, dest)
            written.append(os.path.join("references", name))

    return written
