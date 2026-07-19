"""Adapter: Series-Record + Episode-Script → TTS-Chunk-Jobs (T4.1).

Ersetzt die alte `episodes.json`/`config.py`-Lesart (`podcast_maker.build_drama_jobs`)
durch eine Übersetzung des *neuen* Series-Records (Stage A) + Episode-Scripts (Stage B)
in zustandslose Chunk-Jobs. Reine stdlib-Logik — daher deterministisch unit-getestet;
der eigentliche Audio-Kern (audio_pipeline/tts_backends) bleibt unberührt.

Zwei Regeln aus dem Altsystem sind bewusst erhalten:
- **NARRATOR-Style-Override:** die NARRATOR-Rolle bekommt IMMER den festen
  ``NARRATOR_STYLE`` statt line/default-Style — Emotion klingt auf dem Erzähler „off",
  und „kein Style" ist nicht neutral (Backend-Default). (§ Stage C, narrator-style-override.)
- **Unsprechbare Chunks → Stille:** reine Interpunktions-Chunks („—", „…") liefern kein
  brauchbares TTS-Audio; sie werden als Stille-Job markiert, nicht ans Backend geschickt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from factory.core import textproc

NARRATOR_ROLE = "NARRATOR"
NARRATOR_STYLE = (
    "Read in a calm, neutral, steady narrator voice — "
    "even pacing, no dramatization, no emotional coloring."
)
DEFAULT_CHUNK_MAX_CHARS = 300


@dataclass
class Job:
    text: str
    role: str
    voice: Optional[str]
    style: Optional[str]
    speed: Optional[float]
    seed: Optional[int]
    is_silence: bool = False


def cast_index(record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """role → cast-Eintrag. Genau eine Auflösung der Voice/Style/Speed/Seed pro Rolle."""
    return {m["role"]: m for m in record.get("cast", [])}


def _style_for(role: str, line_style: Optional[str], cfg: Dict[str, Any]) -> Optional[str]:
    if role == NARRATOR_ROLE:
        return NARRATOR_STYLE          # harter Override (§ Stage C)
    return line_style or cfg.get("style")


def build_jobs(
    record: Dict[str, Any],
    episode_script: Dict[str, Any],
    *,
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
) -> List[Job]:
    """Übersetze ein Episode-Script (``{"sections": [{"lines": [...]}]}``) in Chunk-Jobs.

    Jede Zeile wird satzweise gechunkt (CJK-bewusst, wie im Altsystem). Voice/Style/Speed/
    Seed sind pro Chunk explizit gesetzt — die Synthese bleibt zustandslos.
    """
    cast = cast_index(record)
    jobs: List[Job] = []

    for section in episode_script.get("sections", []):
        for line in section.get("lines", []):
            role = line.get("speaker", "")
            cfg = cast.get(role, {})
            sentences = textproc.split_into_sentences(line.get("text", ""))
            for chunk in textproc.chunk_sentences(sentences, chunk_max_chars):
                if not textproc.is_speakable(chunk):
                    jobs.append(Job(text=chunk, role=role, voice=cfg.get("voice"),
                                    style=None, speed=None, seed=None, is_silence=True))
                    continue
                jobs.append(Job(
                    text=chunk,
                    role=role,
                    voice=cfg.get("voice"),
                    style=_style_for(role, line.get("style"), cfg),
                    speed=line.get("speed", cfg.get("speed")),
                    seed=cfg.get("seed"),
                ))
    return jobs
