# Quality Leap Phase 0 Plan

Date: 2026-07-07

Scope for this pass: Phase 0 research plus Phase 1 foundation only. Phase 2
candidate tournaments stay parked until Phase 1 is green.

## Existing Seams

- Render entry point: `ManimRuntime.render_scene()` writes a scene file and runs Manim with `-q<quality>`; its docstring names `l/m/h/k` quality flags at `aetherlab/services/manim_runtime.py:225` and `aetherlab/services/manim_runtime.py:239`.
- Local render timeout/cost: quality base timeouts live at `aetherlab/services/manim_runtime.py:265`, render cost is computed at `aetherlab/services/manim_runtime.py:266`, and `_estimate_render_cost()` starts at `aetherlab/services/manim_runtime.py:786`.
- Repair and final promotion: `render_scene_with_repair()` starts at `aetherlab/services/manim_runtime.py:340`, renders draft quality first at `aetherlab/services/manim_runtime.py:367`, promotes to requested quality at `aetherlab/services/manim_runtime.py:437`, and keeps a successful draft if final quality fails at `aetherlab/services/manim_runtime.py:456`.
- Backend seam: `_render_once()` starts at `aetherlab/services/manim_runtime.py:548`, calls `select_backend()` at `aetherlab/services/manim_runtime.py:566`, and falls back to local when cloud returns unavailable at `aetherlab/services/manim_runtime.py:589`.
- Critique loop: the perceptual loop starts at `aetherlab/services/manim_runtime.py:459`, imports `critique_video()` at `aetherlab/services/manim_runtime.py:472`, logs verdict/score at `aetherlab/services/manim_runtime.py:489`, and calls `SceneGenerator.revise()` for critique issues at `aetherlab/services/manim_runtime.py:524`.
- Scene generation: `SceneGenerator.storyboard()` starts at `aetherlab/services/scene_generator.py:344` and uses temperature `0.9` at `aetherlab/services/scene_generator.py:377`; `_generate_remote()` starts at `aetherlab/services/scene_generator.py:392`; codegen switches between storyboard-cold temperature `0.15` and fallback cinematic temperature `0.4` at `aetherlab/services/scene_generator.py:439` and `aetherlab/services/scene_generator.py:454`; `repair()` starts at `aetherlab/services/scene_generator.py:495`; `revise()` starts at `aetherlab/services/scene_generator.py:530`.
- Prompt and palette: codegen prompt starts at `aetherlab/services/scene_generator.py:206`; its palette rule is at `aetherlab/services/scene_generator.py:226`; fallback palette loading is at `aetherlab/services/scene_generator.py:655`.
- Critic contract: the rubric starts at `aetherlab/services/scene_critic.py:36`; JSON fields and 0-10 score are specified at `aetherlab/services/scene_critic.py:51`; ship requires score >= 7 at `aetherlab/services/scene_critic.py:56`; `Critique.should_revise` is at `aetherlab/services/scene_critic.py:68`; `critique_video()` degrades to `skipped` without vision credentials at `aetherlab/services/scene_critic.py:187` and `aetherlab/services/scene_critic.py:200`.
- Scene model: `SceneBundle` starts at `aetherlab/core/models.py:121`; it already carries `storyboard` at `aetherlab/core/models.py:131`, `failure_kind` at `aetherlab/core/models.py:135`, and defensive `from_json()` at `aetherlab/core/models.py:145`.
- Session cache: `SessionCache` starts at `aetherlab/core/cache.py:31`; scene JSON rehydrates at `aetherlab/core/cache.py:102`; `store_scene()` writes scene JSON at `aetherlab/core/cache.py:121`.
- Solve cache reuse: `AetherLabPipeline.run()` reads cache at `aetherlab/services/pipeline.py:27`, reuses cached scene at `aetherlab/services/pipeline.py:45`, generates a new scene at `aetherlab/services/pipeline.py:47`, and renders only compiled/missing-video scenes at `aetherlab/services/pipeline.py:52`.
- Lesson chapter cache reuse: `_render_chapter()` cache path starts at `aetherlab/services/lesson_pipeline.py:194`, returns cached chapter scenes at `aetherlab/services/lesson_pipeline.py:203`, renders via `render_scene_with_repair()` at `aetherlab/services/lesson_pipeline.py:216`, and stores rendered chapter scenes at `aetherlab/services/lesson_pipeline.py:222`.
- Cloud backend: `CloudRenderBackend.render()` starts at `aetherlab/services/render_backend.py:104`; `cloud_job_id()` is computed at `aetherlab/services/render_backend.py:131` and defined at `aetherlab/services/render_backend.py:315`; secret scanning starts at `aetherlab/services/render_backend.py:327`; dispatch is at `aetherlab/services/render_backend.py:171`; polling uses exact job id at `aetherlab/services/render_backend.py:188`; artifact lookup/download happens at `aetherlab/services/render_backend.py:220` and `aetherlab/services/render_backend.py:226`.

## Phase Map

- F160, Phase 1: persist `quality_score`, `critique_verdict`, and issue summaries on `SceneBundle`; populate from the existing critic in `render_scene_with_repair()`; add opt-in `AppSettings.min_quality_score`; reject solve and lesson cached scenes below threshold. Default `0.0` preserves current behavior.
- F161, Phase 2: candidate tournament at the scene path using `SceneGenerator.storyboard()`, `_generate_remote()`, existing static gates, `_render_once()` draft renders, and `scene_critic` scoring. Winner collapses back to one `SceneBundle`.
- F162, Phase 3: visual-regression quality gate on top of `tools/visual_regression.py`, including strict mode, regression flags, contact sheets, blank/static detection, and duration/fps reporting.
- F163, Phase 4: exemplar library in `services/scene_exemplars.py`, selected by `detect_domain()` / solver keywords and injected into the codegen prompt within context budget.
- Future Phase 5: Solve regenerate affordance, persisted quality badge surfacing, selectable 4K, and opt-in default quality change.
- Future Phase 6: guarded live GitHub Actions smoke plus offline cloud backend tests around dispatch, polling, artifact validation, secret refusal, cache reuse, and local fallback.
- Future Phase 7: golden-frame assertions and bounded render tuple archive.

## Decisions Needed Before Later Phases

- Phase 2: default candidate count when enabled, max parallel draft renders, and whether tournament drafts may use cloud in `auto` mode or must stay local.
- Phase 2: score tie-break weights: fewer critic issues versus duration-contract closeness.
- Phase 4 follow-up: whether verified user-generated exemplars may enter the library later; the shipped library is project-owned static snippets only.
- Phase 5: whether "High" should become the visible default immediately or only after a saved setting migration.
- Phase 6: which GitHub render repo should be the blessed live-smoke target, and whether public repos are acceptable for CI smoke artifacts.

## Phase 1 Reproduction Target

Before the fix, a stubbed `critique_video()` could return `score=8.4` and
`verdict="ship"`, but `SceneBundle` had no fields to persist it. Separately, a
cached rendered scene with an existing MP4 and low quality score had no way to
be rejected because cache reuse only checked engine/status/video existence.
F160 reproduces both conditions with stubs and verifies the default threshold
still reuses the same cached scene.
