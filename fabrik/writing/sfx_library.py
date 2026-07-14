"""Serienübergreifende Wiederverwendung generierter SFX-Assets.

Bevor location_ambience.py/sfx_assets.py einen neuen Sound bei ElevenLabs
anfordern, prüft resolve_or_generate() zuerst die globale Bibliothek unter
data/sfx_library/<category>/ — exakt (gleicher normalisierter Text, auch
aus einer anderen Serie) und, falls kein exakter Treffer existiert, fuzzy
per Wortmengen-Überlappung (kein API-Call, keine Embeddings — bewusst
einfach und stdlib-only, wie der Rest von fabrik/writing/). Ein Fund wird
zusätzlich zum bereits gewünschten Ziel-Pfad auch unter dem exakten Hash
der neuen Beschreibung in die Bibliothek kopiert, damit derselbe Text beim
nächsten Mal ein exakter statt ein fuzzy Treffer ist (Konvergenz über
Zeit).

Stdlib-only — läuft wie image_backends.py/elevenlabs_backend.py ohne
.venv.
"""

from __future__ import annotations

import json
import os
import re
import shutil

from fabrik.core.paths import SFX_LIBRARY_DIR
from fabrik.core.textproc import sfx_asset_hash
from fabrik.writing import elevenlabs_backend

SFX_REUSE_SIMILARITY_THRESHOLD = 0.5

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "with", "and", "or", "to",
    "is", "are", "very", "some", "one", "single", "faint", "distant",
    "nearby", "loud", "soft", "quiet", "sound", "sounds", "noise",
}
_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text):
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def _similarity(a_tokens, b_tokens):
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return overlap / union if union else 0.0


def _category_dir(category):
    return os.path.join(SFX_LIBRARY_DIR, category)


def _index_path(category):
    return os.path.join(_category_dir(category), "index.json")


def _load_index(category):
    path = _index_path(category)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_index(category, index):
    with open(_index_path(category), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)


def _find_similar(description, index):
    """Bester Fuzzy-Treffer über Description + Aliases jedes Index-Eintrags,
    None wenn nichts über SFX_REUSE_SIMILARITY_THRESHOLD liegt."""
    query = _tokens(description)
    best_hash, best_score = None, 0.0
    for h, entry in index.items():
        candidates = [entry["description"], *entry.get("aliases", [])]
        score = max(_similarity(query, _tokens(c)) for c in candidates)
        if score > best_score:
            best_hash, best_score = h, score
    if best_score >= SFX_REUSE_SIMILARITY_THRESHOLD:
        return best_hash, index[best_hash]
    return None, None


def resolve_or_generate(description, category, out_path, duration_seconds=None):
    """category = 'oneshots' | 'ambience'. Schreibt IMMER nach out_path —
    entweder aus der Bibliothek kopiert (exakt oder fuzzy wiederverwendet)
    oder frisch generiert."""
    os.makedirs(_category_dir(category), exist_ok=True)
    h = sfx_asset_hash(description)
    lib_path = os.path.join(_category_dir(category), f"{h}.mp3")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if os.path.exists(lib_path):
        shutil.copyfile(lib_path, out_path)
        return

    index = _load_index(category)
    match_hash, match_entry = _find_similar(description, index)
    if match_entry is not None:
        match_lib_path = os.path.join(_category_dir(category), f"{match_hash}.mp3")
        if os.path.exists(match_lib_path):
            print(f"  ♻️  SFX wiederverwendet: '{description}' ~ '{match_entry['description']}'")
            shutil.copyfile(match_lib_path, out_path)
            shutil.copyfile(match_lib_path, lib_path)
            match_entry.setdefault("aliases", [])
            if description not in match_entry["aliases"] and description != match_entry["description"]:
                match_entry["aliases"].append(description)
            _save_index(category, index)
            return

    elevenlabs_backend.save_sound_effect(description, lib_path, duration_seconds=duration_seconds)
    index[h] = {"description": description, "aliases": []}
    _save_index(category, index)
    shutil.copyfile(lib_path, out_path)
