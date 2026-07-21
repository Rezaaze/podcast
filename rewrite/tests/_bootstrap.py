"""Legt das rewrite/-Wurzelverzeichnis auf den Importpfad, damit ``import factory``
ohne Installation funktioniert (stdlib-only, kein pyproject nötig)."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
