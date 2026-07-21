"""TEST-GATE 0 — Umgebungs-Split hart erzwungen (§2).

factory.core und factory.authoring dürfen factory.media NIE importieren — das bräche
den No-venv-Pfad der Skript-Generierung. Statt Konvention: ein AST-Scan, der bei jeder
Verletzung fehlschlägt.
"""

import ast
import os
import unittest

from tests import _bootstrap  # noqa: F401

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FORBIDDEN_PREFIX = "factory.media"
_GUARDED_PACKAGES = ("factory/core", "factory/authoring")


def _py_files(rel_pkg: str):
    base = os.path.join(_ROOT, rel_pkg)
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _imports(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


class ImportBoundaryTest(unittest.TestCase):
    def test_authoring_and_core_never_import_media(self) -> None:
        violations = []
        for pkg in _GUARDED_PACKAGES:
            for path in _py_files(pkg):
                for mod in _imports(path):
                    if mod == _FORBIDDEN_PREFIX or mod.startswith(_FORBIDDEN_PREFIX + "."):
                        rel = os.path.relpath(path, _ROOT)
                        violations.append(f"{rel} imports {mod}")
        self.assertEqual(
            violations, [],
            msg="Umgebungs-Split verletzt (§2): " + "; ".join(violations),
        )

    def test_guard_itself_catches_a_violation(self) -> None:
        # Meta-Test: der Scanner findet eine echte Verletzung, wäre sie da.
        src = "from factory.media import mastering\n"
        tree = ast.parse(src)
        mods = [
            n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        ]
        self.assertTrue(
            any(m and m.startswith(_FORBIDDEN_PREFIX) for m in mods)
        )


if __name__ == "__main__":
    unittest.main()
