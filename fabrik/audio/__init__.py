"""Vertonung — braucht .venv (pydub, numpy, pyloudnorm, requests) + ffmpeg.

Bewusst KEINE Re-Exports hier: core/writing dürfen fabrik.audio nie
importieren, damit generate_episode/create_series ohne .venv laufen.
"""
