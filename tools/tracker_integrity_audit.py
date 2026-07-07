"""Integrity checks for AetherLab's canonical feature tracker artifacts."""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRACKER_CSV = ROOT / "AetherLab_Feature_Tracker.csv"
TRACKER_XLSX = ROOT / "AetherLab_Feature_Tracker.xlsx"
RESULTS_JSON = ROOT / "feature_test_results.json"
GENERATOR = ROOT / "build_feature_tracker.py"
FEATURE_TESTS = ROOT / "test_features.py"
ERRORS_FOUND = ROOT / "ERRORS_FOUND.md"

VALID_STATUSES = {"Documented", "PASS", "FAIL", "PARTIAL", "FIXED"}
VALID_TEST_METHODS = {"headless", "static", "gui"}
VALID_RESULTS = {"PASS", "FAIL"}


def _load_generator() -> Any:
    spec = importlib.util.spec_from_file_location("_aetherlab_feature_tracker", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.apply_results()
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
        {headers[i]: "" if value is None else str(value) for i, value in enumerate(row)}
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
    return [dict(zip(module.HEADERS, [str(v) for v in row], strict=True)) for row in module.FEATURES]


def _contiguous(ids: list[str]) -> list[str]:
    nums = sorted(int(fid[1:]) for fid in ids if re.fullmatch(r"F\d+", fid))
    expected = {f"F{n:02d}" if n < 100 else f"F{n}" for n in range(nums[0], nums[-1] + 1)} if nums else set()
    return sorted(expected - set(ids), key=lambda x: int(x[1:]))


def audit(*, allow_pending_result: str | None = None) -> dict[str, Any]:
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
        if row["Test Method"] not in VALID_TEST_METHODS:
            issues.append(f"{fid} invalid test method {row['Test Method']!r}")

    csv_id_set = set(feature_ids)
    result_ids = set(results)
    missing_results = csv_id_set - result_ids
    extra_results = result_ids - csv_id_set
    if allow_pending_result and missing_results == {allow_pending_result} and not extra_results:
        missing_results = set()
    if missing_results or extra_results:
        issues.append(f"Tracker/results ID mismatch: tracker-result={sorted(missing_results)}, result-tracker={sorted(extra_results)}")
    if csv_id_set != test_ids:
        issues.append(f"Tracker/test ID mismatch: tracker-test={sorted(csv_id_set - test_ids)}, test-tracker={sorted(test_ids - csv_id_set)}")
    for fid, result in results.items():
        if result.get("status") not in VALID_RESULTS:
            issues.append(f"{fid} invalid result status {result.get('status')!r}")
        if not str(result.get("note", "")).strip():
            issues.append(f"{fid} missing result note")

    errors_text = ERRORS_FOUND.read_text(encoding="utf-8")
    errors_bug_ids = set(re.findall(r"BUG-\d+", errors_text))
    defect_bug_ids = set()
    defect_ids = set(module.DEFECTS)
    for fid, note in module.DEFECTS.items():
        if fid not in csv_id_set:
            issues.append(f"DEFECTS references unknown feature {fid}")
        if next((r for r in csv_rows if r["ID"] == fid), {}).get("Status") != "FIXED":
            issues.append(f"DEFECTS feature {fid} is not marked FIXED")
        defect_bug_ids.update(re.findall(r"BUG-\d+", note))
    missing_bug_docs = sorted(defect_bug_ids - errors_bug_ids, key=lambda b: int(b.split("-")[1]))
    if missing_bug_docs:
        issues.append(f"DEFECTS bug IDs missing from ERRORS_FOUND.md: {missing_bug_docs}")

    return {
        "ok": not issues,
        "issues": issues,
        "feature_count": len(csv_rows),
        "result_count": len(results),
        "test_count": len(test_ids),
        "defect_count": len(defect_ids),
        "bug_ids_in_defects": sorted(defect_bug_ids, key=lambda b: int(b.split("-")[1])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify tracker generator/CSV/XLSX/results/test parity.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when integrity issues exist.")
    args = parser.parse_args()

    report = audit()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"{report['feature_count']} features, {report['result_count']} results, "
            f"{report['test_count']} tests, {report['defect_count']} defect-linked features"
        )
        for issue in report["issues"]:
            print(f"ISSUE {issue}")
    return 1 if args.check and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
