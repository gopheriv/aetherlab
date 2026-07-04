"""WP5: cross-run error learning — signatures, curated hints, persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from aetherlab.services.error_learner import (
    ErrorLearner,
    error_signature,
    known_pitfall_hints,
    preventive_pitfalls_block,
)


def test_signature_is_stable_across_lines_and_paths() -> None:
    a = '  File "/tmp/scene_abc.py", line 12, in construct\nNameError: name \'wobble\' is not defined'
    b = '  File "C:\\x\\scene_xyz.py", line 88, in construct\nNameError: name \'wobble\' is not defined'
    assert error_signature(a) == error_signature(b)
    assert "NameError" in error_signature(a)


def test_signature_normalizes_numbers() -> None:
    sig = error_signature("ValueError: expected 3 dimensions, got 7")
    assert "<n>" in sig
    assert error_signature("ValueError: expected 5 dimensions, got 9") == sig


def test_latex_content_error_signature() -> None:
    assert error_signature("! Undefined control sequence.\nLaTeX Error: x") == (
        "latexerror: undefined control sequence"
    )


def test_known_pitfalls_map_to_fixes() -> None:
    assert any("plot" in h for h in known_pitfall_hints(
        "AttributeError: 'Axes' object has no attribute 'get_graph'"
    ))
    assert any("Create" in h for h in known_pitfall_hints(
        "NameError: name 'ShowCreation' is not defined"
    ))
    assert any("Text" in h for h in known_pitfall_hints(
        "NameError: name 'TextMobject' is not defined"
    ))
    assert known_pitfall_hints("NameError: name 'x' is not defined") == []


def test_preventive_block_is_actionable() -> None:
    block = preventive_pitfalls_block()
    assert "plot" in block
    assert "Create" in block


def test_learner_persists_across_instances(tmp_path) -> None:
    path = tmp_path / "errmem.json"
    stderr = "NameError: name 'q' is not defined"
    first = ErrorLearner(path)
    assert first.seen_count(stderr) == 0
    first.record(stderr)

    reloaded = ErrorLearner(path)
    assert reloaded.seen_count(stderr) == 1
    reloaded.record(stderr)
    assert ErrorLearner(path).seen_count(stderr) == 2


def test_hints_include_recurrence_warning_after_first_record(tmp_path) -> None:
    path = tmp_path / "errmem.json"
    learner = ErrorLearner(path)
    stderr = "AttributeError: 'Axes' object has no attribute 'get_graph'"
    assert not any("before" in h for h in learner.hints_for(stderr))
    learner.record(stderr)
    hints = learner.hints_for(stderr)
    assert any("before" in h for h in hints)  # recurrence warning
    assert any("plot" in h for h in hints)  # curated fix still present


def test_corrupt_store_does_not_crash(tmp_path) -> None:
    path = tmp_path / "errmem.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    learner = ErrorLearner(path)  # must not raise
    assert learner.seen_count("anything") == 0


def test_no_path_is_in_memory_only(tmp_path) -> None:
    learner = ErrorLearner(None)
    learner.record("NameError: name 'z' is not defined")
    assert learner.seen_count("NameError: name 'z' is not defined") == 1


def test_old_entries_are_pruned_on_load(tmp_path) -> None:
    path = tmp_path / "errmem.json"
    old = (datetime.now(UTC) - timedelta(days=90)).isoformat(timespec="seconds")
    fresh = datetime.now(UTC).isoformat(timespec="seconds")
    path.write_text(
        json.dumps({
            "old: stale error": {"count": 5, "last_seen": old},
            "new: recent error": {"count": 1, "last_seen": fresh},
        }),
        encoding="utf-8",
    )
    learner = ErrorLearner(path)
    assert learner._store.get("old: stale error") is None
    assert learner._store.get("new: recent error") is not None
