"""Serienübergreifende Wiederverwendung generierter Charakter-Porträts.

Bevor character_prompts.py ein Porträt-Bild bei OpenAI anfordert, prüft
find_match() zuerst die globale Bibliothek unter data/character_library/ —
exakt (gleiche normalisierte Rollenbeschreibung aus voices.<ROLLE>.
description, auch aus einer anderen Serie) und, falls kein exakter Treffer
existiert, fuzzy per Wortmengen-Überlappung (identisches Muster zu
fabrik/writing/sfx_library.py für Sounds — siehe dort für die Begründung
des Verfahrens).

Matching läuft bewusst auf der KURZEN Rollenbeschreibung
(voices.<ROLLE>.description, z.B. "gruff veteran homicide detective, early
50s"), NICHT auf dem langen generierten Bild-Prompt aus PROMPTS.txt — der
variiert stilistisch zu stark zwischen Claude-Läufen für brauchbares
Fuzzy-Matching, während die Rollenbeschreibung stabil den Charaktertyp
trifft.

Emotionsvarianten sind Teil desselben Bibliothekseintrags (Datei
<hash>__<emotion>.png neben dem Neutral-Porträt <hash>.png) — ein Treffer
liefert deshalb potenziell schon einen Teil der gebrauchten Emotionen mit.
Fehlt eine gebrauchte Emotion, generiert character_prompts.py nur sie neu
(per Bild-Edit auf dem wiederverwendeten Neutral-Bild, für optische
Konsistenz) und speist sie über register() in denselben Bibliothekseintrag
zurück — die Bibliothek konvergiert so über Zeit, wie bei sfx_library.py.

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

CHARACTER_LIBRARY_DIR = os.path.join(DATA_DIR, "character_library")
_INDEX_PATH = os.path.join(CHARACTER_LIBRARY_DIR, "index.json")
_LOCK_PATH = os.path.join(CHARACTER_LIBRARY_DIR, ".index.lock")

# HÖHER als sfx_library.py (0.65), nicht niedriger — Rollenbeschreibungen
# sind kurz (oft nur 4-8 Inhaltswörter nach Stopword-Abzug), und bei kurzen
# Texten kippt schon EIN abweichendes Wort den Jaccard-Score stark (4 von 5
# Wörtern gleich = 0.6 knapp über einer 0.6-Schwelle, selbst wenn das eine
# abweichende Wort die Bedeutung umkehrt, z.B. "cheerful" vs. "grieving").
# Kurze Texte brauchen also einen STRENGEREN, nicht laxeren Schwellenwert
# als lange — die vorherige Begründung hier war invertiert.
SIMILARITY_THRESHOLD = 0.8

# Unter so vielen Inhaltswörtern ist Jaccard reines Rauschen (siehe
# sfx_library.py-Begründung) — solche Beschreibungen werden lieber neu
# generiert als falsch wiederverwendet.
MIN_TOKENS_FOR_FUZZY = 3

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "with", "and", "or", "to",
    "is", "are", "very", "who", "his", "her", "their", "she", "he", "who's",
    "into", "from", "as", "by", "for",
}
_WORD_RE = re.compile(r"[a-z0-9']+")


def character_hash(description: str) -> str:
    """Deterministischer Bibliotheks-Schlüssel aus der Rollenbeschreibung —
    normalisiert (strip+lower) wie sfx_asset_hash(), damit Rand-Whitespace
    oder Groß-/Kleinschreibung keinen neuen Eintrag erzeugen."""
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
    """Atomarer Write (Temp-Datei + os.replace) — ein Reader außerhalb der
    Sperre (find_match() nimmt bewusst keine Sperre, läuft sehr häufig) sieht
    dadurch nie eine angerissene Schreiboperation, sondern immer entweder den
    alten oder den neuen vollständigen Stand."""
    os.makedirs(CHARACTER_LIBRARY_DIR, exist_ok=True)
    tmp_path = _INDEX_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    os.replace(tmp_path, _INDEX_PATH)


@contextlib.contextmanager
def _index_lock():
    """Sperrt den Index exklusiv über Prozessgrenzen hinweg (fcntl.flock) —
    verhindert, dass zwei parallele character_prompts.py-Läufe (verschiedene
    Serien, oder über die WebUI angestoßen) sich beim Read-Modify-Write
    gegenseitig überschreiben. Siehe sfx_library.py::_index_lock für die
    volle Begründung (identisches Muster)."""
    os.makedirs(CHARACTER_LIBRARY_DIR, exist_ok=True)
    fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def portrait_path(h: str, emotion: str | None = None) -> str:
    fname = f"{h}.png" if emotion is None else f"{h}__{emotion}.png"
    return os.path.join(CHARACTER_LIBRARY_DIR, fname)


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
    zuerst, sonst fuzzy) — nur wenn dessen Neutral-Porträt tatsächlich auf
    der Platte liegt. (None, None), wenn nichts brauchbares existiert."""
    if not description:
        return None, None
    index = _load_index()
    h = character_hash(description)
    if h in index and os.path.exists(portrait_path(h)):
        return h, index[h]
    match_hash, match_entry = _find_similar(description, index)
    if match_hash and os.path.exists(portrait_path(match_hash)):
        return match_hash, match_entry
    return None, None


def copy_from_library(h: str, emotion: str | None, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    shutil.copyfile(portrait_path(h, emotion), out_path)


def register(h: str, description: str, image_bytes: bytes, emotion: str | None = None):
    """Speichert image_bytes unter (h, emotion) in der Bibliothek und trägt
    die Rollenbeschreibung in den Index ein. Legt einen neuen Eintrag an,
    falls h noch unbekannt ist, sonst wird ein bestehender ergänzt — neue
    Emotion, oder description als Alias, falls sie vom Eintrag abweicht
    (z.B. beim Nachgenerieren einer fehlenden Emotion für einen per
    Fuzzy-Match wiederverwendeten Charakter aus einer anderen Serie)."""
    os.makedirs(CHARACTER_LIBRARY_DIR, exist_ok=True)
    with open(portrait_path(h, emotion), "wb") as f:
        f.write(image_bytes)

    with _index_lock():
        index = _load_index()
        entry = index.setdefault(h, {"description": description, "aliases": [], "emotions": []})
        if emotion and emotion not in entry["emotions"]:
            entry["emotions"].append(emotion)
        if description != entry["description"] and description not in entry["aliases"]:
            entry["aliases"].append(description)
        _save_index(index)
