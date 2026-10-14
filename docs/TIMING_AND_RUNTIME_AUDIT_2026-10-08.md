# Timing and Runtime Audit — 2026-10-08

Scope: the six follow-up areas listed in `docs/NEXT_MISSION_PROMPT.md`:
lesson timing, optional identifiers, cache reads, subprocess cancellation and
diagnostics, generated-scene safety, and settings precedence.

## Findings fixed

- **BUG-105 / F148 — produced-lesson timing.** Crossfade duration had a 0.2 s
  floor, which could exceed an unusually short normalized chapter. The FFmpeg
  graph rounded fades and offsets to hundredths while chapter-seek offsets used
  full precision. Fades are now limited to 40% of the shortest segment and the
  filter graph keeps six decimal places. `t_f148` checks the short-segment bound
  and the exact values passed to FFmpeg.
- **BUG-106 / F150 — cancellation after rendering.** Learn cancellation was not
  passed into narration muxing or lesson assembly. The callback now flows into
  those stages, FFmpeg uses `run_process_tree` to stop descendants on cancel or
  timeout, output is written to a same-directory staging file and atomically
  installed only on success, and `LessonPipeline.run` returns a `cancelled`
  bundle. An interrupted rerun keeps any prior good output. `t_f150` covers
  cancellation during narration and assembly, plus output preservation.
- **BUG-107 / F103 — NumPy pickle output.** The allowed NumPy API includes
  `ndarray.dump(path)`, an arbitrary-path pickle writer absent from the earlier
  sink list. The code-safety gate now rejects its `dump` attribute; `t_f103`
  contains a regression probe.

## Audited paths with no additional defect found

- Chapter layout compares the first renderable chapter by object identity, and
  the pipeline carries plan indexes through partial-render results. No
  `LessonChapter.id` equality is used to associate optional/empty ids in those
  paths.
- The SQLite session cache validates decoded JSON object shapes and treats
  malformed cached model payloads as misses. Lesson-plan and chapter cache
  reads validate payload types; rendered chapter reuse additionally requires
  a playable video. Cache write transactions use the shared path lock and
  atomic JSON helper where applicable.
- Manim subprocesses use the shared process-tree runner. Assembly and narration
  FFmpeg paths now use that same tree-aware timeout/cancellation mechanism.
  Captured error text is decoded with replacement semantics rather than the
  machine's active code page.
- Settings document and implement environment → app config → legacy/Qwen
  fallback precedence for provider configuration. The Qwen settings file stays
  opt-in; secrets are represented in the UI by source/status rather than their
  values. Existing `t_f10` and `t_f153` cover the precedence and migration
  decisions reviewed here.

## Validation

- Feature harness: **223/223 passed**; tracker artifacts rebuilt afterward.
- Tracker integrity: **223 features / 223 results / 223 tests** aligned, with
  55 defect-linked features.
- Surface audit: **89/89** surfaces covered.
- Pytest: **217 passed, 1 third-party ChromaDB deprecation warning**.
- Compile: `python -m compileall -q aetherlab test_features.py
  build_feature_tracker.py tools` passed.
- Targeted rerun: F103, F148, and F150 passed, including real lesson assembly,
  lesson cancellation, and prior-output preservation.
- Strict visual regression rendered **7/7 cases** with zero render failures,
  but the first strict gate failed: all cases exceeded the blank-span quality
  limit, and comparison against the saved baseline reported 14 metric
  regressions. The solve-scene rendering paths were not changed in that audit.
  The initial report remains at
  `visual_regression/runs/mission-audit-2026-10-08/summary.md` for comparison.

## Visual-regression follow-up (BUG-108 / F224)

The failure came from comparing unlike revisions: the saved July 19 baseline
contains 6–35 s clips, while the current storyboarded scenes and lesson run
25–161 s and add explanatory cards. Blank/static *ratios* cannot be compared
reliably when clip length changes several-fold. Contact sheets for all seven
current cases were inspected; the added diagrams, worked visual summaries,
chapter cards, and motion are present. The reported blank spans were all under
one second and aligned with fade transitions.

The strict audit now treats fades up to 1.0 s as normal, still fails on a
longer blank span or more than 10% blank frames, and only compares normalized
blank/static ratios when the clip lengths are within 25%. A duration collapse
remains a regression regardless, and the report labels ratio comparisons it
skips because durations changed.

Validation after the fix:

- Feature harness: **224/224 passed**.
- Tracker build and integrity: **224 features / 224 results / 224 tests**;
  defect links resolved.
- Surface audit: **89/89** surfaces covered.
- Strict visual regression: **7/7 rendered, 0 render failures, 0 quality
  failures, 0 warnings, 0 regressions** at
  `visual_regression/runs/mission-fade-aware-2026-10-08/summary.md`.
