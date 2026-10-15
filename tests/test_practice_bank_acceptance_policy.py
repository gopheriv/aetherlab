"""Synthetic verifier fixtures test rejection policy, not production acceptance."""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

import pytest

from tools import accept_practice_bank as runner
from tools import feature_acceptance as policy


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def fixture_evidence(tmp_path, monkeypatch):
    def create(feature):
        root = tmp_path / feature
        folder = root / "tmp/owned"
        folder.mkdir(parents=True)
        report, log, hook, record = (folder / name for name in ("tests.xml", "execution.log", "sitecustomize.py", "evidence.json"))
        (root / "owned.py").write_text("owned fixture source\n", encoding="utf-8")
        report_root = ET.Element("testsuites")
        suite = ET.SubElement(report_root, "testsuite")
        classname = runner.MODULES[feature][:-3].replace("/", ".")
        for name in runner.CASE_REQUIREMENTS[feature]:
            ET.SubElement(suite, "testcase", {"name": name, "classname": classname})
        ET.ElementTree(report_root).write(report, encoding="utf-8")
        log.write_text("Owned schema fixture, no real tests executed\n", encoding="utf-8")
        hook.write_text(runner.HOOK, encoding="utf-8")
        monkeypatch.setattr(runner, "runtime_fingerprint", lambda: {"owned": "runtime"})
        monkeypatch.setitem(runner.FEATURE_SOURCES, feature, {"owned.py"})
        row = {key: "owned fixture" for key in policy.CONTRACT_COLUMNS}
        row["ID"] = feature
        evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": feature, "status": "PASS", "exit_code": 0,
            "completed_at": "2026-10-15T00:00:00Z", "contract_sha256": policy.contract_hash(row),
            "runtime": {"owned": "runtime"}, "source_sha256": {"owned.py": digest(root / "owned.py")},
            "execution_report": report.relative_to(root).as_posix(), "execution_report_sha256": digest(report),
            "execution_log": log.relative_to(root).as_posix(), "execution_log_sha256": digest(log),
            "headless_hook": hook.relative_to(root).as_posix(), "headless_hook_sha256": digest(hook),
            "isolation": {"qt_imports_forbidden": True, "network_forbidden": True},
            "command": [sys.executable, "-c", runner.LAUNCHER, str(hook), runner.MODULES[feature], "-q", "-p", "no:cacheprovider",
                        f"--basetemp={folder / 'cases'}", f"--junitxml={report}"],
            "checks": [{"id": name, "status": "PASS", "covers": sorted(tags)} for name, tags in runner.CASE_REQUIREMENTS[feature].items()]}

        def verify():
            record.write_text(json.dumps(evidence), encoding="utf-8")
            result = {"status": "PASS", "phase4_status": "PASS", "behaviour_acceptance_evidence": {
                "path": record.relative_to(root).as_posix(), "sha256": digest(record)}}
            return policy.verify_acceptance(root, row, result)

        return root, row, evidence, report, log, hook, verify
    return create


@pytest.mark.parametrize("feature", ("F232", "F254"))
def test_well_formed_policy_fixture_is_accepted(feature, fixture_evidence):
    *_, verify = fixture_evidence(feature)
    assert verify()[0]


@pytest.mark.parametrize("feature", ("F232", "F254"))
@pytest.mark.parametrize("damage", ("missing-case", "duplicate-case", "failed-case", "skipped-case", "wrong-module",
    "runtime", "command", "hook", "log", "isolation", "source", "contract", "coverage", "check-status", "boolean-exit"))
def test_damaged_or_unrelated_evidence_is_rejected(feature, damage, fixture_evidence):
    root, row, evidence, report, log, hook, verify = fixture_evidence(feature)
    tree = ET.parse(report)
    suite = tree.getroot().find("testsuite")
    if damage == "missing-case":
        suite.remove(suite[0])
    elif damage == "duplicate-case":
        suite[1].set("name", suite[0].attrib["name"])
    elif damage == "failed-case":
        ET.SubElement(suite[0], "failure")
    elif damage == "skipped-case":
        ET.SubElement(suite[0], "skipped")
    elif damage == "wrong-module":
        suite[0].set("classname", "unrelated.module")
    elif damage == "runtime":
        evidence["runtime"] = {"owned": "other runtime"}
    elif damage == "command":
        evidence["command"] += ["-k", "one_case_only"]
    elif damage == "hook":
        hook.write_text(runner.HOOK + "# changed\n", encoding="utf-8")
        evidence["headless_hook_sha256"] = digest(hook)
    elif damage == "log":
        log.write_text("changed", encoding="utf-8")
    elif damage == "isolation":
        evidence["isolation"]["network_forbidden"] = False
    elif damage == "source":
        (root / "owned.py").write_text("changed source", encoding="utf-8")
    elif damage == "contract":
        row["Expected behaviour"] = "different contract"
    elif damage == "coverage":
        evidence["checks"][0]["covers"] = []
    elif damage == "check-status":
        evidence["checks"][0]["status"] = "FAIL"
    else:
        evidence["exit_code"] = True
    tree.write(report, encoding="utf-8")
    evidence["execution_report_sha256"] = digest(report)
    assert not verify()[0]


def test_runner_rejects_output_outside_owned_tmp_before_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "runtime_fingerprint", lambda: pytest.fail("Runtime inspected before ownership guard"))
    with pytest.raises(ValueError, match="project tmp"):
        runner.run_acceptance(tmp_path / "outside.json", {"ID": "F232"})
