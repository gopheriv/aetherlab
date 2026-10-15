"""Catalog fixtures must remain independent and fit nested Windows paths."""
import ast
import asyncio
import inspect
from pathlib import Path

import pytest


def _adapter(tmp_path, name):
    source = Path(__file__).resolve().parents[1] / "test_features.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = {"__file__": str(tmp_path / "suite.py"), "Path": Path, "_TMP": tmp_path / "data",
             "inspect": inspect, "asyncio": asyncio}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), "exec"), scope)
    return scope[name]


@pytest.mark.parametrize("name", ("_story_checks", "_explicit_practice_checks", "_practice_display_checks"))
def test_fixture_paths_do_not_include_long_test_names(name, tmp_path):
    folder = tmp_path / "tests"
    folder.mkdir()
    module = "test_practice_explanation_display" if name == "_practice_display_checks" else "fixture_" + "m" * 60
    function = "test_" + "f" * 90
    (folder / f"{module}.py").write_text(
        "from pathlib import Path\n" + f"def {function}({'language, ' if name == '_practice_display_checks' else ''}tmp_path):\n" +
        f"    assert len(str(tmp_path.relative_to(Path({str(tmp_path / 'data')!r})))) <= 45\n" +
        "    (tmp_path / 'owned.txt').write_text('ok', encoding='utf-8')\n", encoding="utf-8")
    adapter = _adapter(tmp_path, name)
    if name == "_story_checks": adapter(module, (function,))
    elif name == "_explicit_practice_checks": adapter(module, [(function, {})])
    else: adapter((function,))
    assert len(list((tmp_path / "data").rglob("owned.txt"))) == (3 if name == "_practice_display_checks" else 1)


@pytest.mark.parametrize("name", ("_story_checks", "_explicit_practice_checks", "_practice_display_checks"))
def test_repeated_story_calls_never_reuse_state(name, tmp_path):
    folder = tmp_path / "tests"
    folder.mkdir()
    module = "test_practice_explanation_display" if name == "_practice_display_checks" else "fresh"
    parameters = "language, tmp_path" if name == "_practice_display_checks" else "tmp_path"
    (folder / f"{module}.py").write_text(
        f"def test_owned({parameters}):\n    path=tmp_path/'owned.txt'\n    assert not path.exists()\n    path.write_text('new', encoding='utf-8')\n", encoding="utf-8")
    adapter = _adapter(tmp_path, name)
    for _ in range(2):
        if name == "_story_checks": adapter(module, ("test_owned",))
        elif name == "_explicit_practice_checks": adapter(module, [("test_owned", {})])
        else: adapter(("test_owned",))
    assert len(list((tmp_path / "data").rglob("owned.txt"))) == (6 if name == "_practice_display_checks" else 2)
