"""Routine catalog checks must not silently launch desktop test windows."""
from __future__ import annotations

import ast
import os
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _catalog_entry():
    # Execute the actual function without importing the catalog's environment
    # setup, which intentionally changes provider/settings paths for its suite.
    source = ast.parse((ROOT / "test_features.py").read_text(encoding="utf-8"))
    node = next(item for item in source.body
                if isinstance(item, ast.FunctionDef) and item.name == "_complete_command_bar_acceptance")
    scope = {"os": os, "_behaviour_evidence": {}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "test_features.py", "exec"), scope)
    return scope[node.name]


@pytest.mark.skipif(os.name != "nt", reason="Windows-only native acceptance entry")
def test_explicit_opt_in_keeps_the_native_entry_available(monkeypatch):
    import tools.accept_command_bar_stories as runner
    monkeypatch.setenv("PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE", "1")
    monkeypatch.setitem(sys.modules, "build_feature_tracker", SimpleNamespace(
        HEADERS=("ID",), FEATURES=[("F13",)]))
    observed = []
    def controlled_acceptance(rows):
        observed.append(rows)
        return {"F13": {"path": "owned-unit-fixture"}}
    monkeypatch.setattr(runner, "run_acceptance", controlled_acceptance)
    entry = _catalog_entry()
    assert entry("F13") == runner.DETAILS["F13"]
    assert observed == [{"F13": {"ID": "F13"}}]
    assert entry.__globals__["_behaviour_evidence"] == {"F13": {"path": "owned-unit-fixture"}}


@pytest.mark.parametrize("value", [None, "0", "true"])
def test_catalog_leaves_visible_acceptance_pending_without_explicit_opt_in(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE", raising=False)
    else:
        monkeypatch.setenv("PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE", value)
    note = _catalog_entry()("F13")
    assert "pending" in note.lower() or "not requested" in note.lower()


@pytest.mark.parametrize("value", [None, "0", "true"])
def test_direct_native_runner_refuses_before_sources_or_processes(monkeypatch, value):
    import tools.accept_command_bar_stories as runner
    if value is None:
        monkeypatch.delenv("PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE", raising=False)
    else:
        monkeypatch.setenv("PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE", value)
    def forbidden():
        pytest.fail("Native runner reached source capture without explicit opt-in")
    monkeypatch.setattr(runner, "_snapshot", forbidden)
    with pytest.raises(RuntimeError, match="PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE=1"):
        runner.run_acceptance({})
