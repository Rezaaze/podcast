"""Serien-übergreifende Figuren-Historie (figure_history.json im Projekt-Root):
verhindert, dass dieselbe Figur in immer neuen Podcasts wieder auftaucht."""

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime

from .paths import FIGURE_HISTORY_FILE

_LOCK_FILE = FIGURE_HISTORY_FILE + ".lock"


@contextmanager
def _locked():
    """Exklusiver Cross-Prozess-Lock um den Read-Modify-Write-Zyklus von
    record_figure(). generate_episode.py --jobs N startet parallele
    Subprozesse, die alle gegen dieselbe figure_history.json schreiben —
    ohne Lock überschreibt der zweite Write kommentarlos, was der erste
    gerade hinzugefügt hat."""
    with open(_LOCK_FILE, "a") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)


def load_figure_history() -> list:
    if not os.path.exists(FIGURE_HISTORY_FILE):
        return []
    try:
        with open(FIGURE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_figure_history(history: list):
    # temp + os.replace: ein harter Kill mitten im Write darf die komplette
    # serienübergreifende Historie nicht zerstören — load_figure_history()
    # fällt bei kaputtem JSON stillschweigend auf [] zurück, der Verlust
    # bliebe unbemerkt.
    tmp = FIGURE_HISTORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FIGURE_HISTORY_FILE)


def warn_on_repeated_figures(data: dict):
    """Warnt (blockiert nicht — könnte ein bewusstes Crossover sein), wenn eine
    Figur der aktuellen Serie bereits in einer ANDEREN Serie vorkam."""
    history = load_figure_history()
    series_title = data.get("series_title", "")
    used_elsewhere = {
        h["figure"]: h["series_title"]
        for h in history
        if h["series_title"] != series_title
    }
    for ep in data.get("episodes", []):
        figure = ep.get("figure")
        if figure in used_elsewhere:
            print(f"⚠️  WARNUNG: Figur '{figure}' kam bereits in der Serie "
                  f"\"{used_elsewhere[figure]}\" vor — figure_history.json prüfen.")


def record_figure(figure: str, series_title: str):
    """Einmal pro Figur+Serie, kein Duplikat bei erneutem Lauf derselben Episode."""
    with _locked():
        history = load_figure_history()
        if any(h["figure"] == figure and h["series_title"] == series_title for h in history):
            return
        history.append({
            "figure": figure,
            "series_title": series_title,
            "created": datetime.now().isoformat(timespec="seconds"),
        })
        save_figure_history(history)
