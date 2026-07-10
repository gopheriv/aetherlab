# AetherLab Test Layout

`test_features.py` is the canonical feature tracker loop. It owns the numbered
F01-F165 behavior checks, writes `feature_test_results.json`, and feeds
`build_feature_tracker.py` for the CSV/XLSX tracker artifacts.

`python -m pytest -q` runs the focused regression suite. The legacy batch module
lives in `tests/test_batch.py` so pytest collection is conventional and the
repository root stays reserved for project entry points and generated trackers.

`tools/visual_regression.py` is the render quality suite. It renders canonical
prompt cases, samples videos into lightweight reports/contact sheets, and can
compare runs against `visual_regression/baseline/current`.
