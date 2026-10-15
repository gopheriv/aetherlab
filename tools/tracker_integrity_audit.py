"""Integrity checks for AetherLab's canonical feature tracker artifacts."""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRACKER_CSV = ROOT / "AetherLab_Feature_Tracker.csv"
TRACKER_XLSX = ROOT / "AetherLab_Feature_Tracker.xlsx"
RESULTS_JSON = ROOT / "feature_test_results.json"
GENERATOR = ROOT / "build_feature_tracker.py"
FEATURE_TESTS = ROOT / "test_features.py"
ERRORS_FOUND = ROOT / "ERRORS_FOUND.md"

VALID_STATUSES = {"Documented", "PASS", "FAIL", "PARTIAL", "FIXED", "REGRESSED"}
VALID_TEST_METHODS = {"headless", "static", "gui"}
VALID_PERSONAS = {"P1", "P2", "P3", "P4", "P5"}
VALID_STORY_TEST_METHODS = {"harness", "scripted-ui", "manual", "live-cloud"}
VALID_PHASE_RESULTS = {"PENDING", "PASS", "FAIL", "BLOCKED", "PARTIAL", "DEFERRED"}
VALID_RESULTS = {"PASS", "FAIL"}


def duplicate_literal_mapping_keys(source: str, mapping_name: str) -> list[str]:
    """Detect source collisions before Python silently replaces earlier keys."""
    repeated = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        elif isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == mapping_name for target in targets):
            continue
        if isinstance(value, ast.Dict):
            counts = Counter(key.value for key in value.keys
                             if isinstance(key, ast.Constant) and isinstance(key.value, str))
            repeated.update(key for key, count in counts.items() if count > 1)
    return sorted(repeated)
REQUIRED_STORY_COLUMNS = [
    "Story",
    "Persona",
    "Expected behaviour",
    "Failure-mode expectation",
    "Test method",
    "Phase-2 result",
    "Errors found",
    "Phase-4 result",
]
IMPLEMENTATION_REF_RE = re.compile(
    r"(?<![\w])([A-Za-z0-9_./\\-]+\.(?:py|yml|yaml):(\d+))"
)


def _load_generator() -> Any:
    spec = importlib.util.spec_from_file_location("_aetherlab_feature_tracker", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(ROOT))
        spec.loader.exec_module(module)
        module.apply_results()
    finally:
        sys.path[:] = previous_path
    return module


def _read_csv() -> tuple[list[str], list[dict[str, str]]]:
    with TRACKER_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def _read_xlsx() -> tuple[list[str], list[dict[str, str]]]:
    from openpyxl import load_workbook

    wb = load_workbook(TRACKER_XLSX, read_only=True, data_only=True)
    ws = wb["Features"]
    values = list(ws.iter_rows(values_only=True))
    headers = [str(v or "") for v in values[0]]
    rows = [
        {
            headers[i]: "" if value is None else (
                value.replace(tzinfo=UTC).isoformat(timespec="seconds")
                if isinstance(value, datetime) and headers[i] == "Latest check (UTC)"
                else str(value)
            )
            for i, value in enumerate(row)
        }
        for row in values[1:]
        if any(value is not None for value in row)
    ]
    wb.close()
    return headers, rows


def _test_ids() -> set[str]:
    tree = ast.parse(FEATURE_TESTS.read_text(encoding="utf-8"), filename=str(FEATURE_TESTS))
    ids: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and re.fullmatch(r"t_f\d+", node.name):
            ids.add(node.name[2:].upper())
    return ids


def _expected_rows(module: Any) -> list[dict[str, str]]:
    return [
        dict(zip(module.HEADERS, [str(v) for v in row], strict=True))
        for row in module.FEATURES
    ]


def _contiguous(ids: list[str]) -> list[str]:
    nums = sorted(int(fid[1:]) for fid in ids if re.fullmatch(r"F\d+", fid))
    expected = (
        {f"F{n:02d}" if n < 100 else f"F{n}" for n in range(nums[0], nums[-1] + 1)}
        if nums
        else set()
    )
    return sorted(expected - set(ids), key=lambda x: int(x[1:]))


def audit(
    *, allow_pending_result: str | set[str] | None = None, include_run_status: bool = True,
    require_complete_behaviours: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    module = _load_generator()
    expected = _expected_rows(module)
    csv_headers, csv_rows = _read_csv()
    xlsx_headers, xlsx_rows = _read_xlsx()
    results = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    test_ids = _test_ids()
    feature_ids = [row["ID"] for row in csv_rows]

    if csv_headers != module.HEADERS:
        issues.append(f"CSV headers differ from generator: {csv_headers!r}")
    if xlsx_headers != module.HEADERS:
        issues.append(f"XLSX headers differ from generator: {xlsx_headers!r}")
    missing_story_columns = [col for col in REQUIRED_STORY_COLUMNS if col not in csv_headers]
    if missing_story_columns:
        issues.append(f"CSV missing story columns: {missing_story_columns}")
    xlsx_missing_story_columns = [col for col in REQUIRED_STORY_COLUMNS if col not in xlsx_headers]
    if xlsx_missing_story_columns:
        issues.append(f"XLSX missing story columns: {xlsx_missing_story_columns}")
    if csv_rows != expected:
        issues.append("CSV rows differ from build_feature_tracker.py after apply_results().")
    if xlsx_rows != expected:
        issues.append("XLSX rows differ from build_feature_tracker.py after apply_results().")

    duplicate_ids = sorted({fid for fid in feature_ids if feature_ids.count(fid) > 1})
    if duplicate_ids:
        issues.append(f"Duplicate feature IDs: {duplicate_ids}")
    missing_ids = _contiguous(feature_ids)
    if missing_ids:
        issues.append(f"Missing contiguous feature IDs: {missing_ids}")

    for row in csv_rows:
        fid = row["ID"]
        if not row["User Story"].strip():
            issues.append(f"{fid} missing User Story")
        if not row["Expected Behavior"].strip():
            issues.append(f"{fid} missing Expected Behavior")
        if row["Status"] not in VALID_STATUSES:
            issues.append(f"{fid} invalid status {row['Status']!r}")
        if row["Feature test method"] not in VALID_TEST_METHODS:
            issues.append(f"{fid} invalid feature test method {row['Feature test method']!r}")
        for col in REQUIRED_STORY_COLUMNS:
            if not row.get(col, "").strip():
                issues.append(f"{fid} missing {col}")
        expected_behavior = row.get("Expected behaviour", "")
        references = IMPLEMENTATION_REF_RE.findall(expected_behavior)
        if not references:
            issues.append(f"{fid} missing a concrete Python/YAML implementation reference")
        else:
            has_implementation_source = False
            for reference, line_text in references:
                relative_path = reference.rsplit(":", 1)[0].replace("\\", "/")
                source_path = ROOT / relative_path
                line_number = int(line_text)
                if source_path.suffix in {".py", ".yml", ".yaml"}:
                    has_implementation_source = True
                if not source_path.is_file():
                    issues.append(f"{fid} implementation reference points to missing file {relative_path}")
                    continue
                try:
                    source_lines = source_path.read_text(encoding="utf-8").splitlines()
                except (OSError, UnicodeError) as exc:
                    issues.append(f"{fid} cannot read implementation reference {reference}: {exc}")
                    continue
                if not 1 <= line_number <= len(source_lines):
                    issues.append(
                        f"{fid} implementation reference is out of range: {reference} "
                        f"(file has {len(source_lines)} lines)"
                    )
                elif not source_lines[line_number - 1].strip():
                    issues.append(f"{fid} implementation reference points to a blank line: {reference}")
            if not has_implementation_source:
                issues.append(f"{fid} implementation reference does not point to source code/config")
        if row.get("Story") and not row["Story"].startswith(f"US-{fid}:"):
            issues.append(f"{fid} story id does not match feature id")
        if row.get("Persona") and row["Persona"] not in VALID_PERSONAS:
            issues.append(f"{fid} invalid persona {row['Persona']!r}")
        if row.get("Test method") and row["Test method"] not in VALID_STORY_TEST_METHODS:
            issues.append(f"{fid} invalid story test method {row['Test method']!r}")
        if row.get("Phase-2 result") and row["Phase-2 result"] not in VALID_PHASE_RESULTS:
            issues.append(f"{fid} invalid Phase-2 result {row['Phase-2 result']!r}")
        if row.get("Phase-4 result") and row["Phase-4 result"] not in VALID_PHASE_RESULTS:
            issues.append(f"{fid} invalid Phase-4 result {row['Phase-4 result']!r}")

    csv_id_set = set(feature_ids)
    result_ids = set(results)
    missing_results = csv_id_set - result_ids
    extra_results = result_ids - csv_id_set
    allowed_pending = (
        {allow_pending_result}
        if isinstance(allow_pending_result, str)
        else set(allow_pending_result or ())
    )
    if missing_results <= allowed_pending and not extra_results:
        missing_results = set()
    if missing_results or extra_results:
        issues.append(
            "Tracker/results ID mismatch: "
            f"tracker-result={sorted(missing_results)}, "
            f"result-tracker={sorted(extra_results)}"
        )
    if csv_id_set != test_ids:
        issues.append(
            "Tracker/test ID mismatch: "
            f"tracker-test={sorted(csv_id_set - test_ids)}, "
            f"test-tracker={sorted(test_ids - csv_id_set)}"
        )
    for fid, result in results.items():
        if result.get("status") not in VALID_RESULTS:
            issues.append(f"{fid} invalid result status {result.get('status')!r}")
        if not str(result.get("note", "")).strip():
            issues.append(f"{fid} missing result note")

    # BUG-60: the audit used to certify a tracker regenerated from *failing*
    # results — rebuilding simply absorbed the failures into the spreadsheet and
    # every downstream gate went green. A run with failures is never certifiable,
    # however the statuses happen to be stamped.
    # `include_run_status` exists only so t_f165 — which runs *inside* the
    # harness and therefore reads the PREVIOUS run's results — can assert
    # artifact consistency without asserting on a stale run status. Without it a
    # single failing run would fail t_f165 forever: its own recorded failure
    # would keep the audit red on every subsequent run. The CLI `--check` gate
    # (the CI path) always includes it, and t_f215 asserts that it rejects.
    harness_failures = sorted(
        (fid for fid, result in results.items() if result.get("status") == "FAIL"),
        key=lambda fid: int(fid[1:]) if re.fullmatch(r"F\d+", fid) else 0,
    )
    if include_run_status and harness_failures:
        issues.append(
            "Feature harness failures recorded in feature_test_results.json: "
            f"{harness_failures}"
        )

    errors_text = ERRORS_FOUND.read_text(encoding="utf-8")
    issue_definitions = re.findall(r"^\|\s*(BUG-\d+)\s*\|", errors_text, re.M)
    duplicate_issues = sorted(key for key, count in Counter(issue_definitions).items() if count > 1)
    if duplicate_issues:
        issues.append(f"Duplicate BUG definitions in ERRORS_FOUND.md: {duplicate_issues}")
    duplicate_links = duplicate_literal_mapping_keys(GENERATOR.read_text(encoding="utf-8"), "ERROR_FEATURE_LINKS")
    if duplicate_links:
        issues.append(f"Duplicate literal keys in ERROR_FEATURE_LINKS: {duplicate_links}")
    errors_bug_ids = set(issue_definitions)
    tracker_bug_ids = {
        bug_id
        for row in csv_rows
        for bug_id in re.findall(r"BUG-\d+", row.get("Errors found", ""))
    }
    for row in csv_rows:
        if row.get("Phase-2 result") in {"FAIL", "PARTIAL"}:
            linked_bugs = set(re.findall(r"BUG-\d+", row.get("Errors found", "")))
            if not linked_bugs:
                issues.append(
                    f"{row['ID']} Phase-2 result is {row['Phase-2 result']} without a linked BUG entry"
                )
            undocumented = sorted(linked_bugs - errors_bug_ids, key=lambda b: int(b.split("-")[1]))
            if undocumented:
                issues.append(f"{row['ID']} references bugs missing from ERRORS_FOUND.md: {undocumented}")
    defect_bug_ids = set()
    defect_ids = set(module.DEFECTS)
    for fid, note in module.DEFECTS.items():
        if fid not in csv_id_set:
            issues.append(f"DEFECTS references unknown feature {fid}")
        defect_status = next((r for r in csv_rows if r["ID"] == fid), {}).get("Status")
        recorded = results.get(fid, {}).get("status")
        expected_status = {"PASS": "FIXED", "FAIL": "REGRESSED"}.get(recorded, "PARTIAL")
        if defect_status != expected_status:
            issues.append(f"DEFECTS feature {fid} is {defect_status}, expected {expected_status} for recorded result {recorded}")
        if include_run_status and defect_status == "REGRESSED":
            issues.append(
                f"DEFECTS feature {fid} REGRESSED: a previously-fixed defect is failing again"
            )
        defect_bug_ids.update(re.findall(r"BUG-\d+", note))
    missing_bug_docs = sorted(defect_bug_ids - errors_bug_ids, key=lambda b: int(b.split("-")[1]))
    if missing_bug_docs:
        issues.append(f"DEFECTS bug IDs missing from ERRORS_FOUND.md: {missing_bug_docs}")
    non_feature_bug_ids = set(module.NON_FEATURE_DEFECTS)
    unknown_non_feature_bug_ids = sorted(
        non_feature_bug_ids - errors_bug_ids,
        key=lambda b: int(b.split("-")[1]),
    )
    if unknown_non_feature_bug_ids:
        issues.append(
            f"NON_FEATURE_DEFECTS references missing error rows: {unknown_non_feature_bug_ids}"
        )
    unlinked_logged_bugs = sorted(
        errors_bug_ids - tracker_bug_ids - non_feature_bug_ids,
        key=lambda b: int(b.split("-")[1]),
    )
    if unlinked_logged_bugs:
        issues.append(
            f"Logged BUG rows are not linked to a feature story: {unlinked_logged_bugs}"
        )

    unfinished_behaviours = [row["ID"] for row in expected if row.get("Behaviour status") != "PASS"]
    if require_complete_behaviours and unfinished_behaviours:
        issues.append(f"Complete user-story acceptance remains open for {len(unfinished_behaviours)} stories; first: {unfinished_behaviours[:12]}")

    return {
        "ok": not issues,
        "issues": issues,
        "feature_count": len(csv_rows),
        "story_count": sum(1 for row in csv_rows if row.get("Story", "").strip()),
        "result_count": len(results),
        "test_count": len(test_ids),
        "defect_count": len(defect_ids),
        "bug_ids_in_defects": sorted(defect_bug_ids, key=lambda b: int(b.split("-")[1])),
        "logged_bug_count": len(errors_bug_ids),
        "linked_bug_count": len(errors_bug_ids & tracker_bug_ids),
        "unlinked_logged_bug_ids": unlinked_logged_bugs,
        "accepted_behaviour_count": len(expected) - len(unfinished_behaviours),
        "unfinished_behaviour_ids": unfinished_behaviours,
    }


def main() -> int:
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Verify tracker generator/CSV/XLSX/results/test parity."
    )
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--complete-behaviours", action="store_true",
                        help="Require complete, current evidence for every user story as well as tracker integrity.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when integrity issues exist.",
    )
    args = parser.parse_args()

    report = audit(require_complete_behaviours=args.complete_behaviours)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"{report['feature_count']} features, {report['result_count']} results, "
            f"{report['test_count']} tests, {report['defect_count']} defect-linked features"
        )
        for issue in report["issues"]:
            print(f"ISSUE {issue}")
    return 1 if (args.check or args.complete_behaviours) and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
