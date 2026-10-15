"""The real tracker CLI also works from a foreign working directory."""
import ast
import json
import subprocess
import sys
from pathlib import Path


def test_tracker_json_cli_imports_project_modules_from_foreign_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / "tools/tracker_integrity_audit.py"), "--json"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["feature_count"] >= 250 and isinstance(report["unfinished_behaviour_ids"], list)


def test_complete_behaviour_gate_refuses_unfinished_stories(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / "tools/tracker_integrity_audit.py"), "--complete-behaviours", "--json"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    report = json.loads(result.stdout)
    if report["unfinished_behaviour_ids"]:
        assert result.returncode == 1 and not report["ok"]
        assert any("Complete user-story acceptance" in issue for issue in report["issues"])


def test_watchdog_reference_points_to_its_actual_main():
    import build_feature_tracker as tracker

    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "aetherlab_watchdog.py").read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    refs = tracker._source_line_refs("aetherlab_watchdog.py / start.bat", "`aetherlab_watchdog.main()` logs uptime")
    assert refs.split(" / ")[0] == f"aetherlab_watchdog.py:{main.lineno}"


def test_integrity_refuses_duplicate_issue_definitions(tmp_path, monkeypatch):
    from tools import tracker_integrity_audit as audit_module

    original = audit_module.ERRORS_FOUND.read_text(encoding="utf-8")
    row = next(line for line in original.splitlines() if line.startswith("| BUG-1 |"))
    owned = tmp_path / "duplicate-issues.md"
    owned.write_text(original + "\n" + row + "\n", encoding="utf-8")
    monkeypatch.setattr(audit_module, "ERRORS_FOUND", owned)
    report = audit_module.audit(include_run_status=False)
    assert any("Duplicate BUG definitions" in issue and "BUG-1" in issue for issue in report["issues"])


def test_error_feature_mapping_has_no_duplicate_literal_keys():
    from collections import Counter

    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "build_feature_tracker.py").read_text(encoding="utf-8"))
    definition = next(node for node in tree.body if isinstance(node, ast.AnnAssign)
                      and isinstance(node.target, ast.Name) and node.target.id == "ERROR_FEATURE_LINKS")
    counts = Counter(key.value for key in definition.value.keys if isinstance(key, ast.Constant))
    assert {key: value for key, value in counts.items() if value > 1} == {}


def test_literal_collision_detector_handles_annotated_and_plain_mappings():
    from tools.tracker_integrity_audit import duplicate_literal_mapping_keys

    for target in ("ERROR_FEATURE_LINKS", "ERROR_FEATURE_LINKS: dict"):
        text = target + " = {'BUG-7': ('F01','one'), 'BUG-7': ('F02','two')}"
        assert duplicate_literal_mapping_keys(text, "ERROR_FEATURE_LINKS") == ["BUG-7"]
        assert duplicate_literal_mapping_keys(text, "OTHER_MAPPING") == []
        assert duplicate_literal_mapping_keys(target + " = {'BUG-7': 1, 'BUG-8': 2}", "ERROR_FEATURE_LINKS") == []
