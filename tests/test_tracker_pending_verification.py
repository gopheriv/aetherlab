"""Historical passing checks cannot certify changed code awaiting a retest."""
import importlib.util
from pathlib import Path

import pytest


def _tracker():
    source = Path(__file__).resolve().parents[1] / "build_feature_tracker.py"
    spec = importlib.util.spec_from_file_location("_pending_tracker_case", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("phase", ("BLOCKED", "PENDING", "PARTIAL", "DEFERRED"))
@pytest.mark.parametrize("with_reason", (False, True))
def test_old_pass_with_explicit_pending_retest_is_not_marked_fixed(phase, with_reason):
    tracker = _tracker()
    result = {"status": "PASS", "note": "Historical check", "phase4_status": phase}
    if with_reason:
        result["pending_validation"] = {"reason": "UI retest unavailable", "scope": "Core checked; UI pending"}
    tracker.apply_results({"F167": result})
    row = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F167")))
    assert row["Status"] == "PARTIAL"
    assert row["Phase-4 result"] == phase
    if with_reason:
        assert "Core checked; UI pending" in row["Verification scope"]


def test_actual_failure_wins_over_a_pending_retest_marker():
    tracker = _tracker()
    tracker.apply_results({"F167": {"status": "FAIL", "note": "Actual failed check",
        "phase4_status": "BLOCKED", "pending_validation": {"reason": "UI pending"}}})
    row = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F167")))
    assert row["Status"] == "REGRESSED" and row["Phase-4 result"] == "FAIL"


def test_successful_retest_supersedes_the_preserved_pending_marker():
    tracker = _tracker()
    tracker.apply_results({"F167": {"status": "PASS", "note": "Completed current retest",
        "phase4_status": "PASS", "pending_validation": {"reason": "Historical pending note"}}})
    row = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F167")))
    assert row["Status"] == "FIXED" and row["Phase-4 result"] == "PASS"
