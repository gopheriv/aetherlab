"""Synthetic fixtures validate rejection policy; they never certify app behaviour."""
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from tools import accept_settings_stories as runner
from tools import feature_acceptance as policy


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def matrix(tmp_path, monkeypatch):
    def create(feature):
        root = tmp_path / feature
        folder = root / "tmp/owned"
        folder.mkdir(parents=True)
        report, log, hook, record = (folder / name for name in ("tests.xml", "execution.log", "sitecustomize.py", "evidence.json"))
        source = root / "owned.py"
        source.write_text("Owned fixture only\n", encoding="utf-8")
        suite = ET.Element("testsuite")
        for name, module in runner.CASE_MODULES[feature].items():
            ET.SubElement(suite, "testcase", {"name": name, "classname": module[:-3].replace("/", ".")})
        ET.ElementTree(suite).write(report, encoding="utf-8")
        log.write_text("Synthetic policy fixture; no execution\n", encoding="utf-8")
        hook.write_text(runner.HOOK, encoding="utf-8")
        monkeypatch.setattr(runner, "runtime_fingerprint", lambda: {"owned": "runtime"})
        monkeypatch.setitem(runner.FEATURE_SOURCES, feature, {"owned.py"})
        row = {key: "Owned fixture " + key for key in policy.CONTRACT_COLUMNS}
        row["ID"] = feature
        evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": feature, "status": "PASS", "exit_code": 0,
            "completed_at": "2026-10-15T00:00:00Z", "contract_sha256": policy.contract_hash(row),
            "runtime": {"owned": "runtime"}, "source_sha256": {"owned.py": digest(source)},
            "execution_report": report.relative_to(root).as_posix(), "execution_report_sha256": digest(report),
            "execution_log": log.relative_to(root).as_posix(), "execution_log_sha256": digest(log),
            "headless_hook": hook.relative_to(root).as_posix(), "headless_hook_sha256": digest(hook),
            "isolation": {"qt_imports_forbidden": True, "network_forbidden": True},
            "command": runner._command(feature, report, hook),
            "checks": [{"id": name, "status": "PASS", "covers": sorted(tags)} for name, tags in runner.CASE_REQUIREMENTS[feature].items()]}
        def verify():
            record.write_text(json.dumps(evidence), encoding="utf-8")
            return policy.verify_acceptance(root, row, {"status": "PASS", "phase4_status": "PASS",
                "behaviour_acceptance_evidence": {"path": record.relative_to(root).as_posix(), "sha256": digest(record)}})
        return evidence, report, log, hook, row, source, verify
    return create


@pytest.mark.parametrize("feature", ("F06", "F07", "F08"))
def test_well_formed_settings_policy_fixture_is_accepted(feature, matrix):
    *_, verify = matrix(feature)
    assert verify()[0]


@pytest.mark.parametrize("feature", ("F06", "F07", "F08"))
@pytest.mark.parametrize("damage", ("missing-report", "missing-case", "duplicate-case", "failure", "skip",
    "wrong-module", "runtime", "command", "hook", "log", "isolation", "source", "contract", "coverage", "check-status", "boolean-exit"))
def test_damaged_settings_evidence_cannot_promote_story(feature, damage, matrix):
    evidence, report, log, hook, row, source, verify = matrix(feature)
    tree = ET.parse(report)
    suite = tree.getroot()
    if damage == "missing-case": suite.remove(suite[0])
    elif damage == "duplicate-case": suite[1].set("name", suite[0].attrib["name"])
    elif damage in {"failure", "skip"}: ET.SubElement(suite[0], "failure" if damage == "failure" else "skipped")
    elif damage == "wrong-module": suite[0].set("classname", "unrelated.module")
    elif damage == "runtime": evidence["runtime"] = {"other": "runtime"}
    elif damage == "command": evidence["command"] += ["-k", "one_case"]
    elif damage == "hook":
        hook.write_text(runner.HOOK + "# changed\n", encoding="utf-8")
        evidence["headless_hook_sha256"] = digest(hook)
    elif damage == "log": log.write_text("changed", encoding="utf-8")
    elif damage == "isolation": evidence["isolation"]["network_forbidden"] = False
    elif damage == "source": source.write_text("changed", encoding="utf-8")
    elif damage == "contract": row["Expected behaviour"] = "changed"
    elif damage == "coverage": evidence["checks"][0]["covers"] = []
    elif damage == "check-status": evidence["checks"][0]["status"] = "FAIL"
    elif damage == "boolean-exit": evidence["exit_code"] = False
    tree.write(report, encoding="utf-8")
    evidence["execution_report_sha256"] = digest(report)
    if damage == "missing-report": report.unlink()
    assert not verify()[0]


def test_settings_runner_checks_output_ownership_before_running(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "_current_rows", lambda: pytest.fail("Accessed contracts before output guard"))
    with pytest.raises(ValueError, match="project tmp"):
        runner.run_acceptance(tmp_path / "outside")
