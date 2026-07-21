"""Vertonungs-Orchestrator (T4.4/T4.7) — die Brücke zwischen neuem Kern und Altsystem-Audio.

Verdrahtet den bewährten Audio-Kern (audio_pipeline/tts_backends) mit den Rewrite-
Primitiven: State-Record-Resume (§10.3), eine Work-Queue (§10.7), stabile Merge-
Reihenfolge, Voice-Manifest-Guard (§9 Falle #5).

Backend UND Merge werden **injiziert** — so ist die Orchestrierung (Resume, Reihenfolge,
Guard) ohne pydub/ffmpeg deterministisch testbar; in Produktion reicht man den echten
TTS-Backend und ``audio_pipeline.merge_parts_to_episode`` hinein.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Protocol

from factory.core.checkpoint import CheckpointStore
from factory.core.queue import WorkQueue
from factory.core.state import StateStore, Status
from factory.media.jobs import Job, build_jobs
from factory.media.voice_manifest import check_voice_consistency


class RenderBackend(Protocol):
    """Rendert einen Chunk-Job zu einer Audiodatei und liefert deren Pfad zurück."""

    def render(self, job: Job, episode_index: int, chunk_index: int) -> str: ...


# merge_fn(ordered_chunk_paths, episode_index) -> {"episode_path", "part_offsets"}
MergeFn = Callable[[List[str], int], Dict[str, Any]]


def voice_episode(
    record: Dict[str, Any],
    episode_index: int,
    jobs: List[Job],
    backend: RenderBackend,
    state: StateStore,
    checkpoints: CheckpointStore,
    merge_fn: MergeFn,
    *,
    queue: Optional[WorkQueue] = None,
) -> Dict[str, Any]:
    """Rendere alle Chunks (resumbar, parallel) und merge sie in STABILER Reihenfolge.

    Resume kommt aus dem State-Record (§10.3), nicht aus Datei-Existenz: ein Chunk mit
    Status COMPLETE wird übersprungen und sein Pfad aus dem Checkpoint gelesen.
    """
    queue = queue or WorkQueue()

    def render_one(idx: int) -> str:
        unit_id = f"ep{episode_index}/chunk{idx}"
        if state.is_done(unit_id):
            cached = checkpoints.get(unit_id)
            if cached is not None:
                return cached["path"]      # Resume aus State+Checkpoint
        path = backend.render(jobs[idx], episode_index, idx)
        checkpoints.put(unit_id, {"path": path})
        state.mark(unit_id, Status.COMPLETE, produced=path)
        return path

    # queue.map liefert in Eingabereihenfolge → Merge-Reihenfolge ist stabil,
    # egal welcher Worker zuerst fertig wird.
    paths = queue.map(render_one, list(range(len(jobs))))
    return merge_fn(paths, episode_index)


def voice_series(
    record: Dict[str, Any],
    episode_scripts: List[Dict[str, Any]],
    backend: RenderBackend,
    state: StateStore,
    checkpoints: CheckpointStore,
    merge_fn: MergeFn,
    *,
    committed_manifest: Optional[Dict[str, Dict[str, Any]]] = None,
    queue: Optional[WorkQueue] = None,
    chunk_max_chars: int = 300,
) -> List[Dict[str, Any]]:
    """Vertone alle Episoden. Voice-Guard läuft VOR jedem Dateizugriff (Hard-Stop bei Drift).

    Episoden werden in Index-Reihenfolge gemerged (stabile Anthologie-Reihenfolge, § Stage C).
    """
    # HARD-STOP vor jedem Dateizugriff, wenn sich Voice/Speed/Seed geändert haben (§9 #5).
    check_voice_consistency(record, committed_manifest)

    results: List[Dict[str, Any]] = []
    for ei, script in enumerate(episode_scripts):
        jobs = build_jobs(record, script, chunk_max_chars=chunk_max_chars)
        results.append(
            voice_episode(record, ei, jobs, backend, state, checkpoints, merge_fn, queue=queue)
        )
    return results
