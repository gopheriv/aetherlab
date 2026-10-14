"""Catalog fixtures need compact fresh paths, including nested invocations."""
import ast
import asyncio
import inspect
from pathlib import Path

import pytest


def _adapter(tmp_path, name):
    source = Path(__file__).resolve().parents[1] / "test_features.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {"__file__": str(tmp_path / "suite.py"), "Path": Path,
                 "_TMP": tmp_path / "data", "inspect": inspect, "asyncio": asyncio}
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(source), "exec"), namespace)
    return namespace[name]


@pytest.mark.parametrize("adapter_name", ("_story_checks", "_explicit_practice_checks"))
def test_catalog_fixture_paths_do_not_embed_long_test_names(adapter_name, tmp_path):
    folder = tmp_path / "tests"
    folder.mkdir()
    module_name = "fixture_" + "m" * 80
    function_name = "test_" + "f" * 100
    root = tmp_path / "data"
    (folder / f"{module_name}.py").write_text(
        "from pathlib import Path\n"
        f"def {function_name}(tmp_path):\n"
        f"    assert len(str(tmp_path.relative_to(Path({str(root)!r})))) <= 45\n"
        "    (tmp_path / 'written.txt').write_text('isolated', encoding='utf-8')\n",
        encoding="utf-8",
    )
    adapter = _adapter(tmp_path, adapter_name)
    if adapter_name == "_story_checks":
        adapter(module_name, (function_name,))
    else:
        adapter(module_name, [(function_name, {})])
    assert len(list(root.rglob("written.txt"))) == 1


def test_plain_story_invocations_do_not_reuse_previous_state(tmp_path):
    folder = tmp_path / "tests"
    folder.mkdir()
    (folder / "fresh_fixture.py").write_text(
        "def test_fresh(tmp_path):\n"
        "    assert not (tmp_path / 'prior.txt').exists()\n"
        "    (tmp_path / 'prior.txt').write_text('one invocation', encoding='utf-8')\n",
        encoding="utf-8",
    )
    adapter = _adapter(tmp_path, "_story_checks")
    adapter("fresh_fixture", ("test_fresh",))
    adapter("fresh_fixture", ("test_fresh",))
    assert len(list((tmp_path / "data").rglob("prior.txt"))) == 2
