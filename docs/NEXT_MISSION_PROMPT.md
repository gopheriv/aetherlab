# AetherLab Next Mission Prompt

Copy this into a fresh Codex session when you want the next agent to continue
from the current branch without rediscovering the project.

## Project Snapshot

You are working on **AetherLab** at `C:\Users\sunak\Projects\aetherlab`, a
PySide6 desktop physics workbench. A prompt can run:

- **Solve**: derivation -> RAG citations -> storyboarded Manim scene ->
  self-healing MP4 render -> live parametric canvas.
- **Learn**: multi-chapter narrated lesson video with title cards, crossfades,
  subtitles, quizzes, and chapter seeking.

Rendering runs locally through Manim Community or remotely through the
provisioned GitHub Actions cloud-render backend.

Current branch: `codex/stabilize-current-branch`

Recent baseline:

- Feature harness: `python test_features.py` -> 165/165 passed.
- Tracker build: `python build_feature_tracker.py` regenerated CSV/XLSX.
- Tracker audit: `python tools\tracker_integrity_audit.py --check` passed.
- Surface audit: `python tools\feature_surface_audit.py --check` passed.
- Pytest: `python -m pytest -q` -> 37 passed.
- Compile: `python -m compileall -q aetherlab test_features.py build_feature_tracker.py tools` passed.
- Diff hygiene: `git diff --check` passed.
- Strict visual regression: 7/7 cases, 0 render failures, 0 quality failures,
  0 warnings, 0 regressions.

Last documented defect: **BUG-23** in `ERRORS_FOUND.md`.

## Ground Rules

1. A green suite is not enough. For each touched path, read the code
   end-to-end and reason about adversarial inputs before trusting tests.
2. For every defect fix, update the canonical workflow:
   - add or update a `DEFECTS["Fxx"]` entry in `build_feature_tracker.py`;
   - add a row in `ERRORS_FOUND.md`;
   - add a regression assertion in `test_features.py`;
   - run `python test_features.py`;
   - run `python build_feature_tracker.py`.
3. For render work, also run:
   `python tools\visual_regression.py --out visual_regression\runs\<name> --compare visual_regression\baseline\current --strict`
4. Do not commit `.env`, keys, `.analysis/`, temp renders, Chroma data, or raw
   visual-regression run videos. See `docs/STABILIZATION_PLAN.md`.
5. Keep commits small and grouped by concern.

## Key Files

- Pipeline: `aetherlab/services/pipeline.py`, `manim_runtime.py`,
  `scene_generator.py`, `scene_validation.py`, `scene_critic.py`,
  `scene_templates.py`, `scene_exemplars.py`, `code_safety.py`
- Lessons: `lesson_planner.py`, `lesson_pipeline.py`, `assembly.py`,
  `cards.py`, `voiceover.py`, `fact_check.py`
- Cloud: `render_backend.py`, `.github/workflows/render.yml`,
  `docs/CLOUD_RENDERING.md`, `docs/MANIM_BOT_SETTINGS_COMPAT.md`
- UI: `aetherlab/ui/main_window.py`, `widgets.py`, `live_canvas.py`,
  `workers.py`, `theme.py`, `style.py`
- Core: `core/settings.py`, `models.py`, `cache.py`, `proc.py`, `events.py`
- Tracker: `test_features.py`, `build_feature_tracker.py`,
  `tools/tracker_integrity_audit.py`, `AetherLab_Feature_Tracker.*`

## High-Leverage Mission Backlog

### Mission 1: Share/Export Bundle

Build one-click export for completed lessons: MP4, SRT, study guide, scene code,
metadata JSON, and a portable HTML player packed into a ZIP. This turns
AetherLab output into something a teacher or student can actually hand off.

Done means:

- deterministic bundle layout;
- no secrets in metadata;
- HTML opens locally and plays the lesson MP4 with subtitles;
- user-facing UI action from `LessonView` or `MainWindow`;
- tracker row and regression test.

### Mission 2: Course Mode

Chain lessons into a lightweight course plan with saved quiz performance and
recommended next topics. This is product value, not only rendering hygiene.

Done means:

- persistent course/session model;
- quiz results stored per lesson;
- next-lesson recommendation based on missed concepts;
- small UI surface in the lesson page.

### Mission 3: Render Farm Dashboard

Expose cloud-render jobs as a real dashboard: queued, running, failed, complete,
artifact downloaded, fallback-to-local state, and log tail.

Done means:

- backend job status model;
- UI list with actionable failed-job diagnostics;
- rate-limit and timeout messages are human-readable;
- stubs cover success, failure, cancellation, and fallback.

### Mission 4: Prompt Quality Lab

Add an in-repo prompt evaluation harness for 6 canonical physics prompts. It
records generated storyboard metadata, render metrics, visual critic score, and
contact sheet paths in a compact report.

Done means:

- no raw videos committed;
- repeatable command under `tools/`;
- baseline score table in docs;
- at least two prompt/exemplar improvements measured against the report.

### Mission 5: UI Modularization

Split the large `aetherlab/ui/widgets.py` into cohesive modules without
behavior change: command bar, reference cards, scene player, lesson view,
analysis panel, parameter dock, and shared primitives.

Done means:

- imports remain stable or compatibility re-exports are provided;
- feature harness, pytest, compileall, and manual smoke pass;
- no visual redesign churn mixed into the refactor.

## Audit Targets That Still Deserve Attention

- Timing math in `assembly.py`, `voiceover.py`, and lesson chapter offset
  mapping.
- Optional-id comparisons in any model or LLM-produced object.
- Cache reads in `core/cache.py`, `pipeline.py`, and `lesson_pipeline.py`.
- Subprocess cancellation, timeout, and non-UTF8 output paths.
- Code-safety bypasses through dynamic string construction or Manim file APIs.
- Settings precedence between env vars, app config, and legacy `.env` aliases.

## Definition Of Done

- The relevant hand-audit note is written in docs or the final response.
- Tests and tracker artifacts are regenerated.
- Strict visual regression is run for render-affecting work.
- Commits are logical and the final status identifies any remaining untracked
  or intentionally ignored files.
