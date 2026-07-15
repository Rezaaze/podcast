"""Serienübergreifende Wiederverwendung generierter Szenen-Orts-Hintergründe.

Analog zu character_library.py (Charaktere) und sfx_library.py (Sounds):
bevor location_prompts.py ein Hintergrundbild bei OpenAI anfordert, prüft
find_match() zuerst die globale Bibliothek unter data/location_library/ —
exakt (gleiche normalisierte Ortsbeschreibung, auch aus einer anderen Serie)
und, falls kein exakter Treffer existiert, fuzzy per Wortmengen-Überlappung
(identisches Verfahren wie dort — siehe sfx_library.py für die Begründung).

Matching läuft auf locations.<KEY>.description (episodes.json). Anders als
bei Charakteren gibt es hier keine Varianten (keine Emotionen) — ein Ort
hat genau EIN Bild, entsprechend einfacher als character_library.py.

Stdlib-only.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil

from fabrik.core.paths import DATA_DIR

LOCATION_LIBRARY_DIR = os.path.join(DATA_DIR, "location_library")
_INDEX_PATH = os.path.join(LOCATION_LIBRARY_DIR, "index.json")
_LOCK_PATH = os.path.join(LOCATION_LIBRARY_DIR, ".index.lock")

# HÖHER als sfx_library.py (0.65), nicht niedriger — Ortsbeschreibungen sind
# kurz, und bei kurzen Texten kippt schon EIN abweichendes Wort den Jaccard-
# Score stark, selbst wenn das Wort die Bedeutung umkehrt (siehe
# character_library.py-Begründung, identisches Argument hier).
SIMILARITY_THRESHOLD = 0.8
MIN_TOKENS_FOR_FUZZY = 3

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "with", "and", "or", "to",
    "is", "are", "very", "its", "it's", "into", "from", "as", "by", "for",
}
_WORD_RE = re.compile(r"[a-z0-9']+")


def location_hash(description: str) -> str:
    """Deterministischer Bibliotheks-Schlüssel aus der Ortsbeschreibung —
    normalisiert (strip+lower) wie sfx_asset_hash()/character_hash()."""
    return hashlib.sha1(description.strip().lower().encode("utf-8")).hexdigest()[:16]


def _tokens(text):
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def _similarity(a_tokens, b_tokens):
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return overlap / union if union else 0.0


def _load_index():
    if not os.path.exists(_INDEX_PATH):
        return {}
    try:
        with open(_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_index(index):
    """Atomarer Write (Temp-Datei + os.replace) — siehe
    character_library.py::_save_index für die Begründung."""
    os.makedirs(LOCATION_LIBRARY_DIR, exist_ok=True)
    tmp_path = _INDEX_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    os.replace(tmp_path, _INDEX_PATH)


@contextlib.contextmanager
def _index_lock():
    """Sperrt den Index exklusiv über Prozessgrenzen hinweg — siehe
    sfx_library.py::_index_lock für die volle Begründung (identisches
    Muster)."""
    os.makedirs(LOCATION_LIBRARY_DIR, exist_ok=True)
    fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def image_path(h: str) -> str:
    return os.path.join(LOCATION_LIBRARY_DIR, f"{h}.png")


def _find_similar(description, index):
    """Bester Fuzzy-Treffer NUR gegen die ursprüngliche description jedes
    Index-Eintrags (nicht gegen dessen aliases) — verhindert Drift über eine
    Kette grenzwertiger Treffer hinweg (siehe sfx_library.py::_find_similar
    für die volle "Stille-Post"-Begründung, identisches Muster hier)."""
    query = _tokens(description)
    if len(query) < MIN_TOKENS_FOR_FUZZY:
        return None, None
    best_hash, best_score = None, 0.0
    for h, entry in index.items():
        candidate_tokens = _tokens(entry["description"])
        if len(candidate_tokens) < MIN_TOKENS_FOR_FUZZY:
            continue
        score = _similarity(query, candidate_tokens)
        if score > best_score:
            best_hash, best_score = h, score
    if best_score >= SIMILARITY_THRESHOLD:
        return best_hash, index[best_hash]
    return None, None


def find_match(description: str):
    """description -> (hash, entry) des besten Bibliothekstreffers (exakt
    zuerst, sonst fuzzy) — nur wenn das Bild tatsächlich auf der Platte
    liegt. (None, None), wenn nichts brauchbares existiert."""
    if not description:
        return None, None
    index = _load_index()
    h = location_hash(description)
    if h in index and os.path.exists(image_path(h)):
        return h, index[h]
    match_hash, match_entry = _find_similar(description, index)
    if match_hash and os.path.exists(image_path(match_hash)):
        return match_hash, match_entry
    return None, None


def copy_from_library(h: str, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    shutil.copyfile(image_path(h), out_path)


def register(description: str, image_bytes: bytes):
    """Speichert ein frisch generiertes Hintergrundbild in der Bibliothek
    und trägt die Ortsbeschreibung in den Index ein."""
    h = location_hash(description)
    os.makedirs(LOCATION_LIBRARY_DIR, exist_ok=True)
    with open(image_path(h), "wb") as f:
        f.write(image_bytes)

    with _index_lock():
        index = _load_index()
        entry = index.setdefault(h, {"description": description, "aliases": []})
        if description != entry["description"] and description not in entry["aliases"]:
            entry["aliases"].append(description)
        _save_index(index)
