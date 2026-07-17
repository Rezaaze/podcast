"""Section-Zugriffs-Helfer — vereinheitlicht die Alt-Form (sections = Liste
von Titel-Strings, Ort/Wortbudget in separaten section_locations/
section_words-Parallel-Arrays) und die neue Objekt-Form (sections = Liste
von {title, what, who, thread, location, words}, seit dem Stage-01-Umbau,
siehe docs/konzept-stage-umbau.md) für alle Lesestellen. stdlib-only
(fabrik/core-Regel — darf NIE aus fabrik/audio/ importieren).

Alt-Serien bleiben dadurch unverändert lesbar: jede Funktion hier fällt bei
einer String-Section exakt auf das alte Verhalten zurück."""


def section_text(section) -> str:
    """Der erzählte Szeneninhalt, der dem Skript-Schreiber als Auftrag für
    GENAU diese Section vorgelegt wird: bei Alt-String-Sections der String
    selbst (er WAR die einzige Vorgabe), bei Objekt-Sections das Pflichtfeld
    'what'. Fällt auf 'title' zurück, falls 'what' fehlt — sollte durch
    config.validate_data() nie vorkommen, aber eine Lesestelle soll bei einer
    ungültigen Handkorrektur nicht crashen, nur schlechter schreiben."""
    if isinstance(section, str):
        return section
    if isinstance(section, dict):
        return section.get("what") or section.get("title") or ""
    return str(section)


def section_title(section) -> str:
    """Kurzes Szenen-Label für Übersichten/Fortschrittsausgaben (episoden-
    weite Sections-Liste, Meta-/Thumbnail-Prompts) — bei Alt-String-Sections
    identisch mit section_text(), bei Objekt-Sections das 'title'-Feld."""
    if isinstance(section, str):
        return section
    if isinstance(section, dict):
        return section.get("title") or section_text(section)
    return str(section)


def section_location(section, idx: int, legacy_locations=None):
    """Location-Key einer Section: bei Objekt-Sections das 'location'-Feld
    direkt, sonst (Alt-Form) der idx-te Eintrag aus episode['section_locations']
    ('null' an beiden Stellen bedeutet gleichermaßen 'kein Ortswechsel')."""
    if isinstance(section, dict):
        return section.get("location")
    if legacy_locations and idx < len(legacy_locations):
        return legacy_locations[idx]
    return None


def section_words_override(section, idx: int, legacy_words=None):
    """Wortbudget-Override einer Section ({min, max, target} oder None): bei
    Objekt-Sections das 'words'-Feld (nur wenn es ein Objekt ist — ein 'null'
    oder eine rohe Zahl bedeutet 'kein Override'), sonst (Alt-Form) der idx-te
    Eintrag aus episode['section_words']."""
    if isinstance(section, dict):
        w = section.get("words")
        return w if isinstance(w, dict) else None
    if legacy_words and idx < len(legacy_words):
        return legacy_words[idx]
    return None
