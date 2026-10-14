"""The catalog adapter must undo fixture patches between parametrized checks."""
from __future__ import annotations

import ast
from pathlib import Path


def test_explicit_story_cases_have_independent_monkeypatch_lifetimes(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "test_features.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_explicit_practice_checks")
    fixture_folder = tmp_path / "tests"
    fixture_folder.mkdir()
    (fixture_folder / "isolated_fixture.py").write_text(
        "import os\n"
        "def test_first(tmp_path, monkeypatch):\n"
        "    monkeypatch.setenv('PHYSLAB_STORY_FIXTURE_ISOLATION', 'patched')\n"
        "def test_second(tmp_path, monkeypatch):\n"
        "    assert os.environ.get('PHYSLAB_STORY_FIXTURE_ISOLATION') is None\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PHYSLAB_STORY_FIXTURE_ISOLATION", raising=False)
    namespace = {"__file__": str(tmp_path / "suite.py"), "Path": Path, "_TMP": tmp_path / "data"}
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(source), "exec"), namespace)
    result = namespace["_explicit_practice_checks"]("isolated_fixture", [
        ("test_first", {"monkeypatch": monkeypatch}),
        ("test_second", {"monkeypatch": monkeypatch}),
    ])
    assert "2 explicit" in result
