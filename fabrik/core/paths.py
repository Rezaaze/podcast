"""Serien-Auflösung: jede Serie lebt in einem eigenen Ordner data/series/<slug>/.

Auflösungsreihenfolge ohne explizites --series:
  1. data/series/LATEST (Textdatei mit dem Slug — wird von create_series gepflegt)
  2. genau eine vorhandene Serie → diese
  3. sonst: Abbruch mit Liste der verfügbaren Serien
"""

from __future__ import annotations  # das venv ist Python 3.9 — PEP-604-Annotationen (X | None)

import os
import re
import sys

# fabrik/core/paths.py -> fabrik/core -> fabrik -> Projekt-Root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")           # alles, was die Pipeline erzeugt
SERIES_ROOT = os.path.join(DATA_DIR, "series")
VOICES_DIR = os.path.join(DATA_DIR, "voices")       # Referenzaufnahmen für Voice-Clones
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
FIGURE_HISTORY_FILE = os.path.join(DATA_DIR, "figure_history.json")
LATEST_FILE = os.path.join(SERIES_ROOT, "LATEST")


class Series:
    """Alle Pfade einer Serie an einem Ort."""

    def __init__(self, slug: str):
        self.slug = slug
        self.root = os.path.join(SERIES_ROOT, slug)
        self.episodes_file = os.path.join(self.root, "episodes.json")
        self.scripts_dir = os.path.join(self.root, "scripts")
        self.output_dir = os.path.join(self.root, "output")
        self.checkpoint_dir = os.path.join(self.output_dir, ".checkpoints")
        self.cues_dir = os.path.join(self.output_dir, ".cues")
        self.anthology_meta_file = os.path.join(self.scripts_dir, "ANTHOLOGY_META.txt")

    def ensure_dirs(self):
        os.makedirs(self.scripts_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        return self

    def script_file(self, prefix: str, episode_num: int) -> str:
        return os.path.join(self.scripts_dir, f"{prefix}{episode_num}.txt")

    def meta_file(self, prefix: str, episode_num: int) -> str:
        return os.path.join(self.scripts_dir, f"{prefix}{episode_num}_META.txt")

    def review_file(self, prefix: str, episode_num: int) -> str:
        return os.path.join(self.scripts_dir, f"{prefix}{episode_num}_REVIEW.txt")

    def beats_file(self, prefix: str, episode_num: int) -> str:
        return os.path.join(self.scripts_dir, f"{prefix}{episode_num}_BEATS.txt")

    def beats_review_file(self, prefix: str, episode_num: int) -> str:
        return os.path.join(self.scripts_dir, f"{prefix}{episode_num}_BEATS_REVIEW.txt")


def slugify(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()[:50] or "serie"


def list_series() -> list[str]:
    if not os.path.isdir(SERIES_ROOT):
        return []
    return sorted(
        d for d in os.listdir(SERIES_ROOT)
        if os.path.exists(os.path.join(SERIES_ROOT, d, "episodes.json"))
    )


def read_latest() -> str | None:
    try:
        with open(LATEST_FILE, "r", encoding="utf-8") as f:
            slug = f.read().strip()
        return slug or None
    except FileNotFoundError:
        return None


def write_latest(slug: str):
    os.makedirs(SERIES_ROOT, exist_ok=True)
    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        f.write(slug + "\n")


def find_series(slug: str | None = None) -> Series | None:
    """Wie resolve_series(), aber ohne Abbruch — für WebUI/Status-Anzeigen."""
    available = list_series()
    if slug:
        return Series(slug) if slug in available else None
    latest = read_latest()
    if latest and latest in available:
        return Series(latest)
    if len(available) == 1:
        return Series(available[0])
    return None


def resolve_series(slug: str | None = None) -> Series:
    """Löst die Ziel-Serie auf oder bricht mit verständlicher Meldung ab."""
    available = list_series()
    if slug:
        if slug in available:
            return Series(slug)
        print(f"FEHLER: Serie '{slug}' nicht gefunden unter {SERIES_ROOT}/")
        if available:
            print(f"  Verfügbar: {', '.join(available)}")
        sys.exit(1)

    series = find_series()
    if series:
        return series

    if not available:
        print(f"FEHLER: Keine Serie gefunden unter {SERIES_ROOT}/")
        print("  Neue Serie anlegen: python3 -m fabrik.cli.create_series \"Thema\"")
    else:
        print("FEHLER: Mehrere Serien vorhanden — bitte mit --series wählen:")
        for s in available:
            print(f"  --series {s}")
    sys.exit(1)


def add_series_arg(parser):
    parser.add_argument("--series", default=None, metavar="SLUG",
                        help="Serie unter data/series/<slug>/ (Standard: data/series/LATEST "
                             "bzw. die einzige vorhandene Serie)")


def template_dir(name: str) -> str:
    return os.path.join(TEMPLATES_DIR, name)
