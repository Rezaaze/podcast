"""Serienübergreifende Wiederverwendung generierter SFX-Assets.

Bevor location_ambience.py/sfx_assets.py einen neuen Sound bei ElevenLabs
anfordern, prüft resolve_or_generate() zuerst die globale Bibliothek unter
data/sfx_library/<category>/ — exakt (gleicher normalisierter Text, auch
aus einer anderen Serie) und, falls kein exakter Treffer existiert UND
allow_fuzzy=True, fuzzy per Wortmengen-Überlappung (kein API-Call, keine
Embeddings — bewusst einfach und stdlib-only, wie der Rest von
fabrik/writing/). Ein Fund wird zusätzlich zum bereits gewünschten Ziel-Pfad
auch unter dem exakten Hash der neuen Beschreibung in die Bibliothek
kopiert, damit derselbe Text beim nächsten Mal ein exakter statt ein fuzzy
Treffer ist (Konvergenz über Zeit).

Stdlib-only — läuft wie image_backends.py/elevenlabs_backend.py ohne
.venv.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import shutil

from fabrik.core.paths import SFX_LIBRARY_DIR
from fabrik.core.textproc import sfx_asset_hash
from fabrik.writing import elevenlabs_backend

# Ab hier gilt ein Fuzzy-Treffer als derselbe Sound. 0.5 war zu leichtgläubig,
# solange die Beschreibungen roher Cue-Text waren: bei "a door creaking open,
# slow" vs. "a door creaking shut" sind nach Stopword-Abzug fast nur noch
# door/creaking übrig — Jaccard 0.5, also Wiederverwendung, obwohl der eine
# Sound auf- und der andere zugeht. Seit fabrik/cli/sfx_plan.py ist Fuzzy nur
# noch der Notnagel (Serien ohne Plan): der Plan clustert vorher selbst und
# schickt lange, konkrete Generierungs-Prompts, bei denen 0.65 erreichbar
# bleibt, ohne Gegenteile zu verschmelzen. Geplante Aufrufe (Palette-Prompts,
# Ambience) übergeben deshalb allow_fuzzy=False — Fuzzy ist NUR für den
# planlosen Alt-Pfad gedacht, in dem es keine Kurationsstufe gibt, die
# Gegensätze vorab trennt.
SFX_REUSE_SIMILARITY_THRESHOLD = 0.65

# Unter so vielen Inhaltswörtern ist Jaccard reines Rauschen ("door slam" vs.
# "door creak" = 0.33, "gunshot" vs. "gunshot echo" = 0.5) — solche Texte
# werden lieber neu generiert als falsch wiederverwendet.
MIN_TOKENS_FOR_FUZZY = 4

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


@contextlib.contextmanager
def _index_lock(category):
    """Sperrt den Index EINER category exklusiv über Prozessgrenzen hinweg
    (fcntl.flock auf einer Lock-Datei neben index.json) — ohne das würde ein
    Read-Modify-Write aus zwei parallelen Läufen (z.B. sfx_assets.py +
    location_ambience.py, oder zwei Serien gleichzeitig über die WebUI) sich
    gegenseitig überschreiben: Prozess B lädt den Index, bevor Prozess A
    seine Änderung zurückschreibt, A's Schreibvorgang geht dann beim
    Überschreiben durch B verloren. Blockierend (kein Timeout) — die
    Sperrzeit pro Aufruf ist ein einzelner JSON-Read+Write, nie ein
    ElevenLabs-Call (der läuft VOR dem Erwerb der Sperre)."""
    os.makedirs(_category_dir(category), exist_ok=True)
    lock_path = os.path.join(_category_dir(category), ".index.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _find_similar(description, index):
    """Bester Fuzzy-Treffer NUR gegen die ursprüngliche description jedes
    Index-Eintrags (nicht gegen dessen aliases) — None wenn nichts über
    SFX_REUSE_SIMILARITY_THRESHOLD liegt oder der Text zu kurz für ein
    belastbares Urteil ist (MIN_TOKENS_FOR_FUZZY).

    BEWUSST nicht gegen aliases verglichen ("Stille-Post"-Fix): würde man
    auch gegen bereits angehängte Aliase matchen, kann ein Eintrag über eine
    Kette grenzwertiger Treffer beliebig weit vom Original wegdriften — Text
    C matcht Alias B (der seinerseits nur knapp gegen das Original A
    matchte), obwohl C gegen A selbst nie über die Schwelle käme. Jeder
    Vergleich bleibt so am unveränderlichen Original verankert; aliases
    dienen weiterhin nur der Konvergenz zu einem exakten Hash-Treffer
    (siehe resolve_or_generate), nicht der Erweiterung des Fuzzy-Suchraums."""
    query = _tokens(description)
    if len(query) < MIN_TOKENS_FOR_FUZZY:
        return None, None
    best_hash, best_score = None, 0.0
    for h, entry in index.items():
        candidate_tokens = _tokens(entry["description"])
        if len(candidate_tokens) < MIN_TOKENS_FOR_FUZZY:
            # Kandidaten unter der Mindestlänge NICHT als Match zulassen: sonst
            # zieht ein alter Zwei-Wort-Eintrag ("door slam") einen neuen,
            # detaillierten Prompt an sich, obwohl über ihn kaum etwas bekannt ist.
            continue
        score = _similarity(query, candidate_tokens)
        if score > best_score:
            best_hash, best_score = h, score
    if best_score >= SFX_REUSE_SIMILARITY_THRESHOLD:
        return best_hash, index[best_hash]
    return None, None


def resolve_or_generate(description, category, out_path, duration_seconds=None,
                        allow_fuzzy=True, post_process=None):
    """category = 'oneshots' | 'ambience'. Schreibt IMMER nach out_path —
    entweder aus der Bibliothek kopiert (exakt oder, wenn allow_fuzzy, fuzzy
    wiederverwendet) oder frisch generiert.

    allow_fuzzy=False für geplante/kuratierte Aufrufe (SFX-Plan-Palette,
    Ambience) — dort gibt es schon eine Kurationsstufe, die Gegensätze
    getrennt hält, ein zusätzlicher Fuzzy-Treffer kann nur noch falsch
    liegen (z.B. eine ruhige Basis-Ambience fälschlich mit einer
    angespannten Stimmungs-Variante verschmelzen) und riskiert eine
    Dauer-Abweichung von der geplanten duration_s, auf der podcast_maker
    Lücken-Timing basiert. Exaktes Hash-Matching bleibt IMMER an (liefert
    per Definition denselben Inhalt, kein Risiko).

    post_process: optionales bytes->bytes (z.B. location_ambience.py's
    Loop-Nahtlos-Behandlung) — läuft NUR bei einer frischen Generierung,
    nicht bei einem Cache-Treffer (der liefert schon verarbeitete Bytes)."""
    with _index_lock(category):
        h = sfx_asset_hash(description)
        lib_path = os.path.join(_category_dir(category), f"{h}.mp3")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if os.path.exists(lib_path):
            shutil.copyfile(lib_path, out_path)
            return

        index = _load_index(category)
        match_hash, match_entry = (_find_similar(description, index)
                                   if allow_fuzzy else (None, None))
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

        elevenlabs_backend.save_sound_effect(description, lib_path, duration_seconds=duration_seconds,
                                             post_process=post_process)
        index[h] = {"description": description, "aliases": []}
        _save_index(category, index)
        shutil.copyfile(lib_path, out_path)
