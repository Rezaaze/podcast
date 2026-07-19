"""Workspace = Pipeline (§2, §3.2). Ordner-Layout *ist* die Pipeline.

    series/<slug>/
      series.json                 identity + Routing (schema_version, layout_version)
      references/                 pro-Serie editierbare Contract-Kopien
      stages/
        01_concept/output/        series-record (single source of truth)
        02_scripts/output/        Skripte, Reviews, Phrase-Report
        03_audio/output/          gemasterte Audio, Timelines, Subtitles, Index
        04_visuals/output/        Character/Location/Cover + Prompts
      assets/                     optionale Stings

Ein Pointer (``series/LATEST``) markiert die „aktuelle" Serie. Eine neue Serie
**reserviert ihren Slug atomar** — der leere Ordner IST die Reservierung, per
``os.mkdir`` (schlägt fehl, wenn er existiert), sodass zwei parallele Creator nie auf
demselben Namen kollidieren (§3.2).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

# Version des Ordner-Layouts selbst (§7.1): eine Layout-Änderung (umbenannte Stage, neuer
# output-Contract) ist eine Migration im selben Sinn wie eine Schema-Änderung.
LAYOUT_VERSION = 1

STAGES = ("01_concept", "02_scripts", "03_audio", "04_visuals")
_POINTER = "LATEST"


class SlugCollision(Exception):
    """Der Slug ist bereits reserviert — parallele Creator kollidieren nicht still."""


@dataclass
class Workspace:
    root: str          # das series/-Wurzelverzeichnis
    slug: str

    @property
    def path(self) -> str:
        return os.path.join(self.root, self.slug)

    def stage_output(self, stage: str) -> str:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; known: {STAGES}")
        return os.path.join(self.path, "stages", stage, "output")

    def series_json(self) -> str:
        return os.path.join(self.path, "series.json")


def _scaffold(ws: Workspace) -> None:
    os.makedirs(os.path.join(ws.path, "references"), exist_ok=True)
    for stage in STAGES:
        os.makedirs(os.path.join(ws.path, "stages", stage, "output"), exist_ok=True)
    os.makedirs(os.path.join(ws.path, "assets"), exist_ok=True)
    meta = {"slug": ws.slug, "layout_version": LAYOUT_VERSION}
    with open(ws.series_json(), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)


def reserve_series(root: str, slug: str) -> Workspace:
    """Reserviere einen Slug atomar und scaffolde den Workspace.

    Der leere Ordner ist die Reservierung: ``os.mkdir`` ist atomar und schlägt fehl,
    wenn er existiert — das ist der Kollisionsschutz (§3.2). Erst danach werden die
    Unterordner angelegt.
    """
    os.makedirs(root, exist_ok=True)
    target = os.path.join(root, slug)
    try:
        os.mkdir(target)   # ATOMARE Reservierung — nicht makedirs(exist_ok=True)!
    except FileExistsError as exc:
        raise SlugCollision(f"slug {slug!r} already reserved") from exc
    ws = Workspace(root=root, slug=slug)
    _scaffold(ws)
    return ws


def open_series(root: str, slug: str) -> Workspace:
    """Öffne einen existierenden Workspace (kein Scaffolding)."""
    ws = Workspace(root=root, slug=slug)
    if not os.path.isdir(ws.path):
        raise FileNotFoundError(f"no series workspace at {ws.path}")
    return ws


def set_latest(root: str, slug: str) -> None:
    """Setze den Pointer auf die aktuelle Serie (atomar)."""
    tmp = os.path.join(root, _POINTER + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(slug)
    os.replace(tmp, os.path.join(root, _POINTER))


def get_latest(root: str) -> Optional[str]:
    path = os.path.join(root, _POINTER)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().strip() or None


def list_series(root: str) -> List[str]:
    if not os.path.isdir(root):
        return []
    return sorted(
        name for name in os.listdir(root)
        if os.path.isdir(os.path.join(root, name))
    )
