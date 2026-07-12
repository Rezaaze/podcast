"""Podcast-Fabrik — gemeinsame Pipeline-Logik.

Vier Teilpakete, getrennt nach Laufzeitumgebung und Zweck:

  core     kein venv nötig: paths (Serien-Auflösung series/<slug>/),
           config (episodes.json laden + validieren), textproc
           (Satz-Splitting EN + CJK, Chunking, Längeneinheiten),
           history (Serien-übergreifende Figuren-Historie)
  writing  braucht nur die claude-CLI: script_writer (Skript-Generierung),
           script_parser (Drama-Format [SPRECHER|style], [SFX: ...])
  audio    braucht .venv (pydub, numpy, pyloudnorm, requests) + ffmpeg:
           pipeline (TTS-Chunks, Mastering, Merge, ID3-Tagging),
           tts_backends (Qwen3-TTS-Anbindung REST/MLX + Gradio/CUDA)
  cli      die Entry-Points, aufzurufen als python3 -m fabrik.cli.<name>:
           create_series, import_story, generate_episode, podcast_maker,
           batch, character_prompts

Wichtig: dieses __init__ (und core/writing) darf nie audio importieren —
generate_episode/create_series laufen bewusst ohne .venv.
"""
