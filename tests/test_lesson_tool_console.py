"""Lesson tooling must emit Kazakh diagnostics from legacy Windows pipes."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


def test_every_printing_lesson_tool_bootstraps_utf8_without_running_its_job(tmp_path):
    root = Path(__file__).resolve().parents[1]
    folder = root / "tools/lesson_pipeline"
    paths = []
    for path in sorted(folder.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "print" for node in ast.walk(tree)):
            paths.append(path)
    assert paths
    script = """
import ast, pathlib, sys
path = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(path.parent))
sys.path.insert(0, str(path.parents[2]))
tree = ast.parse(path.read_text(encoding='utf-8'))
index = next(i for i, node in enumerate(tree.body)
             if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
             and isinstance(node.value.func, ast.Name)
             and node.value.func.id == 'configure_utf8_stdio')
prefix = ast.Module(body=tree.body[:index + 1], type_ignores=[])
exec(compile(prefix, str(path), 'exec'), {'__package__': sys.argv[2] or None})
print('Үдеу → θ м/с²')
"""
    for path in paths:
        for package in ("", "tools.lesson_pipeline"):
            completed = subprocess.run(
                [sys.executable, "-c", script, str(path), package], cwd=tmp_path,
                env={**os.environ, "PYTHONIOENCODING": "cp1251:strict"},
                capture_output=True, timeout=20, check=False,
            )
            assert completed.returncode == 0, (path.name, package, completed.stderr)
            assert completed.stdout.decode("utf-8").strip() == "Үдеу → θ м/с²"
