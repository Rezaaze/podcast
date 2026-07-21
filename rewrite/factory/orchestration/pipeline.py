"""Benannte, resumbare Stufen (T7.1, §8) — die Verdrahtung zur Pipeline.

Jede Stufe nimmt „welche Serie" (einen Workspace) und resumt aus ihren Outputs; eine
fertige Stufe ist ein No-op (Idempotenz). Stufengrenzen sind physisch: jede schreibt in
ihren ``stages/<n>/output/``. Der Status kommt aus dem State-Record (§10.3), nicht aus
Datei-Existenz.

Modell/Backend/Merge werden injiziert — so läuft die ganze Pipeline im E2E-Test mit Fakes,
ohne LLM/TTS/ffmpeg.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from factory.core.checkpoint import CheckpointStore
from factory.core.model import Model
from factory.core.queue import WorkQueue
from factory.core.state import StateStore, Status
from factory.core.validator import validate_series
from factory.core.workspace import Workspace
from factory.authoring.conceive import ConceiveConfig, conceive
from factory.authoring.script_writer import write_series
from factory.media.voicing import MergeFn, RenderBackend, voice_series
from factory.orchestration.locks import DeviceLock, no_lock
from factory.orchestration.status import series_status, stage_unit

STAGES = ["01_concept", "02_scripts", "03_audio", "04_visuals"]


def _write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _read_json(path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def series_record_path(ws: Workspace) -> str:
    return os.path.join(ws.stage_output("01_concept"), "series.json")


def scripts_path(ws: Workspace) -> str:
    return os.path.join(ws.stage_output("02_scripts"), "scripts.json")


@dataclass
class PipelineContext:
    workspace: Workspace
    model: Model
    state: StateStore
    checkpoints: CheckpointStore
    queue: Optional[WorkQueue] = None
    backend: Optional[RenderBackend] = None
    merge_fn: Optional[MergeFn] = None
    device_lock: Optional[DeviceLock] = None


def run_concept(ctx: PipelineContext, cfg: ConceiveConfig) -> Dict[str, Any]:
    """Stage A. Resumbar: fertige Stufe liefert das persistierte Record ohne Regenerierung."""
    if ctx.state.is_done(stage_unit("01_concept")):
        record = _read_json(series_record_path(ctx.workspace))
        if record is not None:
            return record
    record = conceive(cfg, ctx.model, ctx.checkpoints, ctx.queue)
    report = validate_series(record)
    if not report.is_valid:
        raise ValueError(f"conceived record invalid: {report}")
    _write_json(series_record_path(ctx.workspace), record)
    ctx.state.mark(stage_unit("01_concept"), Status.COMPLETE, produced=series_record_path(ctx.workspace))
    return record


def run_scripts(ctx: PipelineContext, record: Dict[str, Any]) -> Dict[str, Any]:
    """Stage B. Sections sind intern resumbar (State-Record); die Stufe ist idempotent."""
    result = write_series(record, ctx.model, ctx.state, ctx.checkpoints)
    payload = {"episodes": result.episodes, "reviews": result.reviews,
               "phrase_reports": result.phrase_reports}
    _write_json(scripts_path(ctx.workspace), payload)
    ctx.state.mark(stage_unit("02_scripts"), Status.COMPLETE, produced=scripts_path(ctx.workspace))
    return payload


def run_audio(
    ctx: PipelineContext,
    record: Dict[str, Any],
    scripts: Dict[str, Any],
    *,
    committed_manifest: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Stage C. Läuft unter dem exklusiven Device-Lock (geteilter TTS-Prozess, §8)."""
    if ctx.backend is None or ctx.merge_fn is None:
        raise ValueError("audio stage needs a backend and a merge_fn")
    episode_scripts = [{"sections": ep["sections"]} for ep in scripts["episodes"]]
    lock = ctx.device_lock.acquire() if ctx.device_lock is not None else no_lock()
    with lock:
        results = voice_series(
            record, episode_scripts, ctx.backend, ctx.state, ctx.checkpoints,
            ctx.merge_fn, committed_manifest=committed_manifest, queue=ctx.queue,
        )
    ctx.state.mark(stage_unit("03_audio"), Status.COMPLETE)
    return results


def run_pipeline(ctx: PipelineContext, cfg: ConceiveConfig, *, with_audio: bool = True) -> Dict[str, Any]:
    """A → B → (C). Jede Stufe resumt; ein zweiter Lauf ist idempotent."""
    record = run_concept(ctx, cfg)
    scripts = run_scripts(ctx, record)
    audio = None
    if with_audio:
        audio = run_audio(ctx, record, scripts)
    return {"record": record, "scripts": scripts, "audio": audio}


def status(ctx: PipelineContext, record: Dict[str, Any]):
    return series_status(record, ctx.state, STAGES)
