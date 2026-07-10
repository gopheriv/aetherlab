# Quality Leap Phase 2 Summary

Date: 2026-07-07

Scope at the time of this pass: opt-in scene candidate tournament only.
Status update: the later exemplar-library work has since landed as F163.

## Built

- Added `AppSettings.scene_candidates` (default `1`) and
  `scene_candidate_concurrency` (default `2`).
- Added seeded storyboard variation support in `SceneGenerator.storyboard()`.
- Added `SceneGenerator.generate_from_storyboard()` so the tournament can
  implement locked storyboards using the existing cold codegen prompt.
- Added `SceneCandidate` and `ManimRuntime.generate_render_tournament()`.
- Wired tournament usage into:
  - headless `AetherLabPipeline.run()`
  - Qt `PipelineWorker`
  - lesson chapter rendering
- Preserved the existing path when `scene_candidates <= 1`, no API key, no
  vision model, or any tournament error.

## Selection Rule

Candidates are ranked by:

1. Higher visual-critic score
2. Fewer critic issues
3. Closer to the 15-22 second duration contract
4. Earlier candidate index as a stable final tie-break

Drafts render at low quality through the existing backend seam, so Local,
Cloud, and Auto continue to route through the same `_render_once()` behavior.
Only the selected winner is re-rendered through the existing
`render_scene_with_repair()` final-quality path.

## Verified Output

Focused F161 run:

```text
[PASS] F161: candidate tournament selects highest score, drops failed candidates, N=1 delegates (F161)
```

The full-suite output is recorded in `feature_test_results.json` after running
`python test_features.py`.

## Fail-Soft Behavior

- `scene_candidates=1`: delegates to `generate_scene_async()` plus
  `render_scene_with_repair()`.
- Missing API key or `vision_model`: tournament disabled.
- No candidate passes static gates, render, or scoring: logs and falls back to
  the single-scene path.
- A failed candidate is dropped, not fatal.

## Deferred

- Real live model tournament run. F161 uses stubs by design so CI and local
  development stay offline-safe.
