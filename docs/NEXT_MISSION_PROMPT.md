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

Current branch: `fix/bugcheck-2026-09-30`

Recent baseline (2026-10-08):

- Feature harness: `python test_features.py` -> 224/224 passed.
- Tracker build: `python build_feature_tracker.py` regenerated CSV/XLSX.
- Tracker audit: `python tools\tracker_integrity_audit.py --check` -> 224 features/results/tests aligned.
- Surface audit: `python tools\feature_surface_audit.py --check` -> 89/89 surfaces covered.
- Pytest: `python -m pytest -q --basetemp .analysis\pytest-full-mission` -> 205 passed, 1 warning.
- Compile: `python -m compileall -q aetherlab test_features.py build_feature_tracker.py tools` passed.
- Strict visual regression: 7/7 passed in the 2026-10-08 runtime audit; the current F180 reporting changes do not alter rendered output.
- Current mission check: the 2026-10-09 keyed F180 attempt was invalid/incomplete (see `.analysis/prompt-quality-lab/ab-cloud-20261008/diagnostic.md`). Follow-up fixes now send tournament candidates through the shared static/runtime repair path, canonicalize equal-count beat markers, retry malformed storyboard/planner output, and bound/minimize cloud TeX dependency installation. Rerun the full keyed A/B to validate those fixes; no valid lift is established yet.

Last documented defects: **BUG-109** (provider A/B measurement validity) in `ERRORS_FOUND.md`.

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

### Completed: Share/Export Bundle

Completed as F166. Lessons can export a portable ZIP containing MP4, SRT/VTT,
study guide, metadata, chapter source files, README, and a static HTML player.

Key files:

- `aetherlab/services/share_export.py`
- `docs/LESSON_SHARE_EXPORT.md`
- `LessonView` / `MainWindow` export-bundle wiring

### Completed: Course Mode Lite

Completed as F167. Multiple-choice quiz answers persist to
`data_dir/course_progress.json`; the lesson page shows a score and recommended
next topic based on missed objectives.

Key files:

- `aetherlab/services/course_mode.py`
- `docs/COURSE_MODE.md`
- `_QuestionCard` / `LessonView` / `MainWindow` quiz-progress wiring

### Completed: Prompt Quality Lab

Completed as F168. `tools/prompt_quality_lab.py` runs canonical scene/lesson
prompts, reuses visual-regression metrics/contact sheets, records storyboard
and critic metadata, writes JSON/Markdown/CSV reports under ignored `.analysis`
runs, and compares against prior reports.

Key files:

- `tools/prompt_quality_lab.py`
- `docs/PROMPT_QUALITY_LAB.md`
- `test_features.py` F168

Validation run:

```powershell
python tools\prompt_quality_lab.py --out .analysis\prompt-quality-lab\canonical-smoke
```

Result: 6 prompts, 0 failures, mean score 5.32.

### Completed: Render Farm Dashboard (F175/F176, BUG-102)

Make cloud rendering observable inside AetherLab. Today the cloud backend can
provision, dispatch, poll, download, and fall back, but users cannot see a
stable job ledger: what queued, what ran, what failed, which artifact was
downloaded, and why local fallback happened.

The render-farm dashboard now records and displays:

- job id, source scene/class, quality, fps, backend, and provider;
- status timeline: queued, in_progress, completed, failed, cancelled,
  action_required, rate_limited/retry, artifact_downloaded, rendered, and
  fallback_local;
- canonical GitHub Actions run/artifact page links; signed URLs and query
  strings are rejected;
- sanitized log tail for failures;
- rate-limit or token-scope messages;
- local fallback reason and final local render path.

Completion evidence:

- backend job-status event model with JSON persistence under the data dir;
- UI page or panel reachable from the existing cloud/backend surfaces;
- no secrets in persisted events or diagnostics;
- stub coverage for success, artifact download, failure log tail, cancellation,
  token-scope failure, rate-limit retry, and Auto local fallback;
- docs explaining how to debug cloud renders from the dashboard.

The follow-up audit closed missing lifecycle/link/metadata details that the
initial F175/F176 implementation did not expose. Hand audit and regression
coverage are recorded under BUG-102 in `ERRORS_FOUND.md`; cloud dashboard
debugging steps are documented in `docs/CLOUD_RENDERING.md`.

### Completed: UI Modularization

Split the large `aetherlab/ui/widgets.py` into cohesive modules without
behavior change: command bar, reference cards, scene player, lesson view,
analysis panel, parameter dock, and shared primitives.

The implementations now live in `aetherlab/ui/{command_bar,navigation,
parameter_dock,analysis_panel,reference_panel,simulation_panel,
library_panel,lesson_view,shared_widgets}.py`. `widgets.py` remains a
backward-compatible facade, including the existing private names used by
tests and integrations. The extracted declarations were compared as Python
ASTs with the pre-refactor source; their bodies are unchanged. See
[`docs/UI_MODULARIZATION.md`](UI_MODULARIZATION.md) for the hand audit and
validation record.

Completion checks:

- imports remain stable or compatibility re-exports are provided;
- feature harness, pytest, compileall, and manual smoke pass;
- no visual redesign churn mixed into the refactor.

## Completed Audit (2026-10-08)

The listed timing, optional-id, cache, subprocess, code-safety, and settings
precedence paths were hand-audited and recorded in
`docs/TIMING_AND_RUNTIME_AUDIT_2026-10-08.md`. The audit fixed produced-lesson
timing drift, cancellation after rendering, a NumPy `ndarray.dump` safety
bypass, and strict visual-regression false positives for short fades and
duration-incomparable baselines (BUG-105–BUG-108). Tracker, surface, feature,
and strict visual checks passed after regeneration.

## Definition Of Done

- The relevant hand-audit note is written in docs or the final response.
- Tests and tracker artifacts are regenerated.
- Strict visual regression is run for render-affecting work.
- Commits are logical and the final status identifies any remaining untracked
  or intentionally ignored files.
