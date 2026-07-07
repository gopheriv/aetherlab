# AetherLab — Phase 2 Error Log

Testing method: `test_features.py` exercises all 159 catalogued features
(headless logic, offscreen-Qt widget construction, and source assertions).
**Automated result: 159/159 pass at the behavioural/happy-path level.**

Green happy-path tests do not prove the absence of defects, so this log records
the logistical/UX errors found by close code review of paths the happy-path
tests don't reach. Each is fixed in Phase 3 and re-verified in Phase 4.

| # | Severity | Feature | File | Defect |
|---|----------|---------|------|--------|
| BUG-1 | Logistical | F17 Pipeline stepper | `ui/widgets.py:316,449` | `PipelineStepper` defines `reset()` **twice**. The second (`set_stage(-1)`) shadows the first and never clears `_started`/`_elapsed`, so **stale per-stage elapsed times leak across runs**. `MainWindow.start_pipeline` calls `reset()` expecting a clean slate. |
| BUG-2 | Logistical | F70 Parameter sync | `ui/widgets.py:906-919` | `ParameterDock.update_variable` expands range with `setRange(0, span)` and tests `if value > span`, contradicting `set_variables` which uses `[-span, span]`. A large **negative** value pushed from the canvas is clamped and the spinbox loses its negative range — inconsistent with the negative-value support elsewhere. |
| BUG-3 | UX / consistency | F36/F38 References | `services/rag.py:140`, `ui/widgets.py:1213` | Filesystem RAG sets `score` = raw keyword **count** (unbounded: 1, 5, 12…). ChromaDB sets `score` = `1/(1+dist)` in `[0,1]`. The reference card renders `{score:.2f}` and colours the pill with 0-1 thresholds (`≥0.8` emerald / `≥0.5` amber). So filesystem hits always show emerald and a misleading number like `12.00`. The two backends are visually incomparable. |
| BUG-4 | UX / consistency | F10 Settings dialog | `ui/main_window.py:611-648`, `core/settings.py:68-76` | The Settings dialog shows a **Data path** field, but `_open_settings` never passes `data_dir` to `save_app_config`, and `load_settings` reads `data_dir` only from env/default (never app-config). So editing Data path silently does not persist across restarts — unlike Library path, which does. Misleading field. |
| BUG-5 | Dead config | F06 Settings | `core/settings.py:28` | `llm_context_window` (default `250_000`) is defined but **referenced nowhere** in the codebase. It is inert configuration that implies an effect it doesn't have. (This is the very value the user opened the session asking to change from 1M to 250k.) |

## Second review pass (uncommitted lesson/produced-video work)

Found by close review of the changed-but-uncommitted surface (assembly, lesson
pipeline, cards) that the happy-path tests only smoke-check. Both fixed and
re-verified; full suite stays green.

| # | Severity | Feature | File | Defect |
|---|----------|---------|------|--------|
| BUG-6 | Rendering | F148 Produced lesson (crossfades) | `services/assembly.py:343` | `_xfade_chain` tracks `cum` so that `offset_k = cum - k*d` should equal the documented `sum(durs[0..k-1]) - k*d`. But it updated `cum += durs[k] - d`, **double-subtracting the overlap** — so from the 2nd crossfade on, each `offset` drifts earlier by an accumulating `d`, over-clipping mid-lesson segments (a ~10-segment lesson with `d≈0.5s` lands its final crossfade ~4s early). ffmpeg still runs (offsets stay monotonic), so the smoke test F148 passes while the produced lesson silently loses time. Fixed to `cum += durs[k]`; offsets now match the reference formula exactly. |
| BUG-7 | Logistical | F146/F147 Chapter aspects | `services/lesson_pipeline.py:314` | `_chapter_aspect` decided the "setup" (first-chapter) composition via `renderable[0].id == ch.id`. LLM-planned lessons routinely omit chapter ids (`LessonChapter.from_json` defaults `id=""`), so `"" == ""` tagged **every** id-less chapter as `setup`, collapsing the setup→evolution→math→recap arc for AI lessons (keyless lessons have hardcoded ids and were unaffected — why F147 passed). Fixed to compare by object identity (`renderable[0] is ch`), robust regardless of ids. |
| BUG-8 | Logistical / UX | F145 Lesson view (seek + subtitles) | `ui/widgets.py:3624`, `services/lesson_pipeline.py`, `services/assembly.py` | The produced lesson prepends a 3s intro card and inserts a 2.2s card before every chapter, then crossfades all segments — but the chapter-outline **seek offsets** and the **.srt** cue times were both computed as a plain running sum of raw chapter-clip durations from t=0. So clicking "Chapter 2" seeked into the *middle of Chapter 1* in the real video, and the error compounded (~9s off by chapter 3); subtitles drifted the same way. A regression from the produced-lesson work (before it, `assemble_lesson` did a plain concat and the naive offsets lined up). Additionally the UI indexed durations by *plan*-chapter index, mis-aligning whenever a lesson had a non-rendered `interactive` chapter. Fixed: `assemble_lesson(..., return_offsets=True)` reports each chapter clip's true start (shared `_segment_starts` with the xfade graph); `LessonBundle.chapter_offsets` carries them (cache-safe); the outline seeks and `build_srt(segments, starts)` use them; the UI walks rendered chapters with a separate index and falls back to a running sum for old caches. |
| BUG-9 | Logistical / UX | F143/F145 Partial lesson alignment | `services/lesson_pipeline.py:142,222`, `core/models.py`, `ui/widgets.py:3631` | If a middle renderable chapter failed, `run()` compacted successful `SceneBundle`s into `rendered`, then `_narrate_chapters()` zipped that compact list against the full renderable chapter list. A surviving later clip (e.g. Chapter 3) was narrated, titled, subtitled, and outlined as the failed earlier chapter (Chapter 2). Fixed by carrying `rendered_chapter_indexes` (plan indexes) alongside `chapter_scenes`/`chapter_offsets`, narrating from `(plan_index, chapter, scene)` tuples, and teaching `LessonView` to map offsets by plan index. Old caches keep the legacy fallback. |

## Third review pass (pytest + static hygiene)

Found by running the legacy `test_batch.py` both directly and under pytest, then
checking source-level Pyflakes diagnostics. Fixed and re-verified with pytest,
compileall, source lint, and the full 159-feature harness.

| # | Severity | Feature | File | Defect |
|---|----------|---------|------|--------|
| BUG-10 | Export correctness | F86 PDF export | `services/pdf.py:44-63` | `compile_latex_to_pdf` returned `pdf_path` whenever the file existed, without checking whether the current `pdflatex` invocation succeeded. If a stale PDF existed beside the `.tex` file, a failed compile could be reported as success and the UI/export path could surface old output. Fixed by deleting the stale target before compile and requiring `subprocess.run(...).returncode == 0` plus fresh PDF existence before returning the path. |
| BUG-11 | Logistical / UX | F15/F84 Pipeline cancel | `ui/main_window.py:1034` | `_cancel_pipeline` cancelled the worker and reset stepper state but did not explicitly clear the scene panel loading stack. If cancellation happened while scene loading UI was visible, the user could be left with a stale loading surface after cancellation. Fixed by calling `SimulationPanel.hide_loading()` during cancellation; the legacy batch check now verifies it. |
| BUG-12 | Test harness reliability | Legacy smoke tests | `test_batch.py` | The old standalone batch script used a helper named `test(...)`, which pytest collected as a test needing non-existent fixtures. A few assertions also encoded pre-v2 UI assumptions: solver cache storage was expected at request creation time, diagnostics were expected in the code editor, and a bullet literal was mojibaked. Fixed by renaming the helper to `run_check(...)`, aligning assertions with the current diagnostics drawer/cache contract, and comparing the bullet by Unicode codepoint. |

## Fourth review pass (deep edge-case audit)

Found by targeted review of security, retrieval freshness, and cloud-render
race paths that normal happy-path tests do not naturally exercise. Fixed and
covered by regression assertions in `test_features.py`.

| # | Severity | Feature | File | Defect |
|---|----------|---------|------|--------|
| BUG-13 | Security / sandbox escape | F103 Scene code safety gate | `services/code_safety.py` | The safety gate blocked direct `open`, `eval`, and direct dunder attributes, but accepted string-based escape helpers such as `getattr(__builtins__, 'open')`, `getattr(type, '__subclasses__')`, and `().__getattribute__('__class__')`. Generated Manim code runs in a real Python subprocess, so this was an arbitrary file/host access bypass if an LLM produced adversarial code. Fixed by banning dynamic runtime-introspection helpers, `__builtins__`, `type`, more dunder attributes, and string-literal references to banned runtime handles. |
| BUG-14 | Retrieval correctness / stale data | F43 Library ingestion | `services/ingestion.py` | Incremental Chroma ingestion upserted changed files but never deleted old chunks for the same source path. If a file shrank or a PDF extraction changed, orphan chunks remained in the vector store and could keep appearing in RAG results forever, contradicting the current library contents. Fixed by deleting chunks with matching `path` metadata before re-upserting a changed file. |
| BUG-15 | Cloud render race / wrong artifact | F154 Cloud render | `services/render_backend.py` | GitHub `workflow_dispatch` usually returns no run id, so AetherLab polls branch runs by `job_id`. If no matching run had appeared yet, `get_run` returned the newest run on the branch (`runs[0]`). Under concurrent or recent renders this could attach to another job, download the wrong artifact, or report the wrong failure. Fixed so unmatched polls return queued until a run whose name/title contains this exact `job_id` appears. |

## Notes on non-issues considered and dismissed
- `SimulationPanel.show_loading` is defined but unused — the shell drives the
  running state via `RunningView`; `hide_loading` is still used. Harmless dead
  method, not fixed.
- `llm.awaitable_pause()` is effectively a no-op; harmless, left as-is.
- No infinite-loop risk in the param↔canvas signal path: `blockSignals`
  guards the mirror updates.
