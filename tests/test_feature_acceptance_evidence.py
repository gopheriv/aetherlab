"""Policy tests; synthetic evidence here never becomes production acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from tools.feature_acceptance import (
    CONTRACT_COLUMNS, DEFAULT_PATH_CASES, DEFAULT_PATH_SOURCES,
    contract_hash, requirements_for_mode, verify_acceptance,
    WATCHDOG_CASE_REQUIREMENTS, WATCHDOG_SOURCES,
)


def _evidence(root, row):
    sources = {}
    for name in DEFAULT_PATH_SOURCES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("unit fixture source", encoding="utf-8")
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "schema": "physlab.story_acceptance.v1", "feature_id": "F11", "status": "PASS",
        "exit_code": 0, "completed_at": "2026-10-14T09:00:00+00:00",
        "contract_sha256": contract_hash(row), "source_sha256": sources,
        "checks": [{"id": case, "status": "PASS", "covers": sorted(requirements_for_mode(case.rsplit("-", 1)[0]))}
                   for case in sorted(DEFAULT_PATH_CASES)],
    }
    return payload


def _write(root, payload):
    path = root / "evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {"status": "PASS", "phase4_status": "PASS", "behaviour_acceptance_evidence": {
        "path": "evidence.json", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }}


@pytest.fixture
def row():
    return {key: "F11" if key == "ID" else "Unit contract " + key for key in CONTRACT_COLUMNS}


def test_complete_current_matrix_is_accepted(tmp_path, row):
    result = _write(tmp_path, _evidence(tmp_path, row))
    assert verify_acceptance(tmp_path, row, result)[0]


def test_legacy_catalog_row_without_phase4_field_can_use_current_pass(tmp_path, row):
    result = _write(tmp_path, _evidence(tmp_path, row))
    result.pop("phase4_status")
    assert verify_acceptance(tmp_path, row, result)[0]


def test_explicit_null_phase_is_not_a_legacy_absent_field(tmp_path, row):
    result = _write(tmp_path, _evidence(tmp_path, row))
    result["phase4_status"] = None
    assert not verify_acceptance(tmp_path, row, result)[0]


@pytest.mark.parametrize("damage", (
    "wrong_feature", "wrong_contract", "failure", "nonzero_exit", "boolean_exit", "unfinished",
    "missing_case", "duplicate_case", "failed_case", "missing_condition", "missing_sources",
    "stale_source", "changed_evidence", "outside_path", "list_root", "unreadable",
))
def test_incomplete_stale_or_unrelated_evidence_never_passes(damage, tmp_path, row):
    payload = _evidence(tmp_path, row)
    if damage == "wrong_feature": payload["feature_id"] = "F12"
    elif damage == "wrong_contract": payload["contract_sha256"] = "old"
    elif damage == "failure": payload["status"] = "FAIL"
    elif damage == "nonzero_exit": payload["exit_code"] = 1
    elif damage == "boolean_exit": payload["exit_code"] = False
    elif damage == "unfinished": payload["completed_at"] = ""
    elif damage == "missing_case": payload["checks"].pop()
    elif damage == "duplicate_case": payload["checks"][-1] = payload["checks"][0]
    elif damage == "failed_case": payload["checks"][0]["status"] = "FAIL"
    elif damage == "missing_condition": payload["checks"][0]["covers"] = []
    elif damage == "missing_sources": payload["source_sha256"] = {}
    elif damage == "list_root": payload = []
    result = _write(tmp_path, payload)
    if damage == "stale_source": (tmp_path / "aetherlab/core/settings.py").write_text("changed", encoding="utf-8")
    elif damage == "changed_evidence": (tmp_path / "evidence.json").write_text("{}", encoding="utf-8")
    elif damage == "outside_path": result["behaviour_acceptance_evidence"]["path"] = "../elsewhere.json"
    elif damage == "unreadable": (tmp_path / "evidence.json").unlink()
    assert not verify_acceptance(tmp_path, row, result)[0]


@pytest.mark.parametrize("phase", ("PENDING", "PARTIAL", "BLOCKED", "DEFERRED", "FAIL"))
def test_valid_evidence_cannot_promote_an_unfinished_retest(phase, tmp_path, row):
    result = _write(tmp_path, _evidence(tmp_path, row))
    result["phase4_status"] = phase
    assert not verify_acceptance(tmp_path, row, result)[0]


def test_actual_catalog_failure_cannot_be_overridden_by_acceptance(tmp_path, row):
    result = _write(tmp_path, _evidence(tmp_path, row))
    result["status"] = "FAIL"
    assert not verify_acceptance(tmp_path, row, result)[0]


def test_a_story_without_a_reviewed_matrix_is_not_promoted(tmp_path, row):
    row = {**row, "ID": "F16"}
    result = _write(tmp_path, _evidence(tmp_path, row))
    assert not verify_acceptance(tmp_path, row, result)[0]


def test_generator_uses_acceptance_and_invalidates_it_after_source_change(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "build_feature_tracker.py"
    spec = importlib.util.spec_from_file_location("_acceptance_tracker_case", source)
    tracker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tracker)
    tracker.apply_results({})
    current = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F11")))
    result = _write(tmp_path, _evidence(tmp_path, current))
    result["note"] = "Controlled schema integration fixture"
    monkeypatch.setattr(tracker, "ROOT", tmp_path)
    tracker.apply_results({"F11": result})
    accepted = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F11")))
    assert accepted["Behaviour status"] == "PASS" and accepted["Remaining verification"] == "None"
    (tmp_path / "aetherlab/core/settings.py").write_text("new source", encoding="utf-8")
    tracker.apply_results({"F11": result})
    stale = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F11")))
    assert stale["Behaviour status"] == "PARTIAL" and "stale" in stale["Remaining verification"]


def _watchdog_evidence(root, row):
    payload = _evidence(root, row)
    payload["feature_id"] = "F04"
    payload["checks"] = [{"id": case, "status": "PASS", "covers": sorted(requirements)}
                         for case, requirements in WATCHDOG_CASE_REQUIREMENTS.items()]
    sources = {}
    for name in WATCHDOG_SOURCES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("policy fixture, not an executed application result", encoding="utf-8")
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload["source_sha256"] = sources
    return payload


def test_watchdog_complete_matrix_is_accepted(tmp_path, row):
    row = {**row, "ID": "F04"}
    result = _write(tmp_path, _watchdog_evidence(tmp_path, row))
    assert verify_acceptance(tmp_path, row, result)[0]


@pytest.mark.parametrize("damage", ("missing_case", "failed_case", "missing_condition", "missing_sources",
                                   "changed_watchdog", "changed_batch", "changed_runner", "defaults_matrix"))
def test_watchdog_requires_its_own_complete_current_matrix(damage, tmp_path, row):
    row = {**row, "ID": "F04"}
    payload = _watchdog_evidence(tmp_path, row)
    if damage == "missing_case": payload["checks"].pop()
    elif damage == "failed_case": payload["checks"][0]["status"] = "FAIL"
    elif damage == "missing_condition": payload["checks"][0]["covers"] = []
    elif damage == "missing_sources": payload["source_sha256"].pop("start.bat")
    elif damage == "defaults_matrix": payload["checks"] = _evidence(tmp_path, row)["checks"]
    result = _write(tmp_path, payload)
    changed = {"changed_watchdog": "aetherlab_watchdog.py", "changed_batch": "start.bat",
               "changed_runner": "test_features.py"}.get(damage)
    if changed: (tmp_path / changed).write_text("new source", encoding="utf-8")
    assert not verify_acceptance(tmp_path, row, result)[0]


def _startup_evidence(root, row):
    from tools.accept_startup_stories import CASE_REQUIREMENTS, FEATURE_SOURCES

    feature = row["ID"]
    sources = {}
    for name in FEATURE_SOURCES[feature]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic policy fixture, not runtime evidence", encoding="utf-8")
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"schema":"physlab.story_acceptance.v1","feature_id":feature,"status":"PASS",
            "exit_code":0,"completed_at":"2026-10-14T11:00:00+00:00","contract_sha256":contract_hash(row),
            "source_sha256":sources,"checks":[{"id":case,"status":"PASS","covers":sorted(coverage)}
                for case,coverage in CASE_REQUIREMENTS[feature].items()]}


@pytest.mark.parametrize("feature", ("F03","F05","F09"))
def test_reviewed_startup_matrix_is_accepted(feature, tmp_path, row):
    row = {**row,"ID":feature}
    assert verify_acceptance(tmp_path,row,_write(tmp_path,_startup_evidence(tmp_path,row)))[0]


@pytest.mark.parametrize("feature", ("F03","F05","F09"))
@pytest.mark.parametrize("damage", ("missing_case","failed_case","missing_condition","missing_source",
                                   "changed_implementation","changed_runner","wrong_feature"))
def test_startup_acceptance_cannot_hide_missing_or_stale_work(feature, damage, tmp_path, row):
    row = {**row,"ID":feature}
    payload = _startup_evidence(tmp_path,row)
    if damage=="missing_case": payload["checks"].pop()
    elif damage=="failed_case": payload["checks"][0]["status"]="FAIL"
    elif damage=="missing_condition": payload["checks"][0]["covers"]=[]
    elif damage=="missing_source": payload["source_sha256"].pop("tools/accept_startup_stories.py")
    elif damage=="wrong_feature": payload["feature_id"]="F12"
    result = _write(tmp_path,payload)
    if damage=="changed_runner": (tmp_path/"tools/accept_startup_stories.py").write_text("new runner",encoding="utf-8")
    elif damage=="changed_implementation":
        path="aetherlab/core/settings.py" if feature=="F09" else "aetherlab/__main__.py"
        (tmp_path/path).write_text("new implementation",encoding="utf-8")
    assert not verify_acceptance(tmp_path,row,result)[0]


def _command_bar_evidence(root, row):
    """Synthetic policy inputs only; never exported as executed acceptance."""
    import xml.etree.ElementTree as ET
    from tools.accept_command_bar_stories import CASE_REQUIREMENTS, FEATURE_SOURCES

    feature = row["ID"]
    sources = {}
    for name in FEATURE_SOURCES[feature]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic UI policy fixture, not an application execution", encoding="utf-8")
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    suite = ET.Element("testsuite")
    for name in CASE_REQUIREMENTS[feature]:
        ET.SubElement(suite, "testcase", name=name)
    report = root / "synthetic-report.xml"
    report.write_bytes(ET.tostring(suite))
    return {"schema": "physlab.story_acceptance.v1", "feature_id": feature, "status": "PASS",
        "exit_code": 0, "completed_at": "2026-10-14T17:00:00+00:00", "contract_sha256": contract_hash(row),
        "source_sha256": sources, "qt_platform": "windows", "execution_report": report.name,
        "execution_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        "checks": [{"id": name, "status": "PASS", "covers": sorted(covers)}
                   for name, covers in CASE_REQUIREMENTS[feature].items()]}


@pytest.mark.parametrize("feature", ("F12", "F13", "F14", "F15", "F17", "F19", "F20", "F84"))
def test_reviewed_native_ui_evidence_schema_is_accepted(feature, tmp_path, row):
    row = {**row, "ID": feature}
    assert verify_acceptance(tmp_path, row, _write(tmp_path, _command_bar_evidence(tmp_path, row)))[0]


@pytest.mark.parametrize("feature", ("F12", "F13", "F14", "F15", "F17", "F19", "F20", "F84"))
@pytest.mark.parametrize("damage", ("offscreen", "missing_report", "changed_report", "report_missing_case",
                                    "report_failed_case", "stale_ui_source", "missing_condition"))
def test_native_ui_evidence_rejects_incomplete_or_stale_execution(feature, damage, tmp_path, row):
    import xml.etree.ElementTree as ET

    row = {**row, "ID": feature}
    payload = _command_bar_evidence(tmp_path, row)
    report = tmp_path / payload["execution_report"]
    if damage == "offscreen": payload["qt_platform"] = "offscreen"
    elif damage == "missing_report": report.unlink()
    elif damage == "changed_report": report.write_bytes(b"changed")
    elif damage in {"report_missing_case", "report_failed_case"}:
        tree = ET.parse(report)
        if damage == "report_missing_case": tree.getroot().remove(tree.getroot()[0])
        else: ET.SubElement(tree.getroot()[0], "failure")
        tree.write(report, encoding="utf-8")
        payload["execution_report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
    elif damage == "stale_ui_source":
        (tmp_path / "aetherlab/ui/main_window.py").write_text("changed UI", encoding="utf-8")
    elif damage == "missing_condition": payload["checks"][0]["covers"] = []
    assert not verify_acceptance(tmp_path, row, _write(tmp_path, payload))[0]
