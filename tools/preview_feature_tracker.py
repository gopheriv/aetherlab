"""Build a review copy of the feature tracker without replacing canonical files."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

from aetherlab.core.console import configure_utf8_stdio

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "build_feature_tracker.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("_aetherlab_tracker_preview", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load tracker generator: {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_xlsx(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        values = list(workbook["Features"].iter_rows(values_only=True))
    finally:
        workbook.close()
    headers = [str(value or "") for value in values[0]]
    rows = [
        {headers[index]: "" if value is None else str(value) for index, value in enumerate(row)}
        for row in values[1:]
        if any(value is not None for value in row)
    ]
    return headers, rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="New or empty output directory (defaults to a timestamped .analysis folder).",
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (
        ROOT / ".analysis" / f"tracker-review-{datetime.now(UTC):%Y%m%d-%H%M%S}"
    )
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        parser.error(f"Refusing to overwrite non-empty review directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = _load_generator()
    generator.CSV_PATH = output_dir / "AetherLab_Feature_Tracker.csv"
    generator.XLSX_PATH = output_dir / "AetherLab_Feature_Tracker.xlsx"
    generator.apply_results()
    generator.write_csv()
    generator.write_xlsx()

    expected = [
        dict(zip(generator.HEADERS, (str(value) for value in row), strict=True))
        for row in generator.FEATURES
    ]
    with generator.CSV_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        csv_headers = list(reader.fieldnames or [])
        csv_rows = list(reader)
    xlsx_headers, xlsx_rows = _read_xlsx(generator.XLSX_PATH)
    parity = (
        csv_headers == generator.HEADERS
        and xlsx_headers == generator.HEADERS
        and csv_rows == expected
        and xlsx_rows == expected
    )
    report = {
        "review_copy": True,
        "canonical_files_replaced": False,
        "feature_count": len(expected),
        "csv_xlsx_generator_parity": parity,
        "csv_path": str(generator.CSV_PATH),
        "xlsx_path": str(generator.XLSX_PATH),
    }
    (output_dir / "preview_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if parity else 1


if __name__ == "__main__":
    configure_utf8_stdio()
    raise SystemExit(main())
