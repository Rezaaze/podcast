"""Serien-übergreifende Figuren-Historie (figure_history.json im Projekt-Root):
verhindert, dass dieselbe Figur in immer neuen Podcasts wieder auftaucht."""

import json
import os
from datetime import datetime

from .paths import FIGURE_HISTORY_FILE


def load_figure_history() -> list:
    if not os.path.exists(FIGURE_HISTORY_FILE):
        return []
    try:
        with open(FIGURE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_figure_history(history: list):
    with open(FIGURE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


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
    history = load_figure_history()
    if any(h["figure"] == figure and h["series_title"] == series_title for h in history):
        return
    history.append({
        "figure": figure,
        "series_title": series_title,
        "created": datetime.now().isoformat(timespec="seconds"),
    })
    save_figure_history(history)
