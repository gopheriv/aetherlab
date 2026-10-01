# AetherLab Upgrade Research

**Research snapshot:** 23 September 2026  
**Scope:** current repository, HANDOFF_BRIEF.md, MANIM_UPGRADE_NOTES.md, MANIM_PIPELINE_QUALITY_ANALYSIS.md, the AI physics explainer innovation research folder, and its summary in reports/AI physics explainer innovation.md. External claims below are checked against primary papers or official documentation where available.

## Recommendation

Build AetherLab around a verifiable chain from a physics model to the lesson a student sees: the same equations, parameters, units, citations, timeline, animation, narration, quiz answers, and interactive model should agree. The project already has much of the creative and rendering machinery. The highest-value work now is to make correctness and quality easier to inspect, evaluate, and reproduce.

## What is already in the project

Several items in the older innovation report are no longer open work:

- **Structured animation timing:** ProblemRequest carries a target duration; scene generation has timed visual windows and pacing/layout constraints.
- **Scene quality review:** scene_critic.py scores legibility, composition, palette, structure, and physics substance. It asks for locations on a 6×6 frame grid and accepts numeric physics expectations where those are observable.
- **Candidate selection and memory:** manim_runtime.py can render and score candidates concurrently, escalate the candidate budget when a draft is weak, record losing-scene pitfalls, retain exemplar candidates for review, and log candidate/HQ scores. This is already a quality flywheel foundation; the next step is to measure its results against people and deterministic checks.
- **Render safety and API checks:** generated scenes pass code-safety and Manim-name/argument checks before rendering. The cloud job ledger stores lifecycle and candidate details with credential scrubbing.
- **Learning interactions:** Learn lessons already include symbol pretraining, prediction and retrieval questions, fact-checking, quizzes, and local per-question course progress.
- **Physics checks:** verify.py reintegrates supported numeric models and checks properties such as finite/bounded trajectories, energy behavior, and the small-angle pendulum period. The result screen explicitly says the written derivation is not automatically verified.
- **Cloud rendering:** explicit Cloud mode was changed to avoid starting a local render after a cloud failure. A direct cloud radiation render was visually reviewed; an offscreen smoke now exercises the normal Run button, Cloud backend, and artifact validation/download path; its GitHub client is stubbed and it replays a real Cloud MP4, so it verifies the app route without claiming a second live GitHub UI run.

These facts change the roadmap: do not spend the next cycle rebuilding a planner, adding another generic visual critic, or adding basic prediction questions. Improve how the existing pieces exchange evidence and how AetherLab proves that a release is better.

## Prioritized upgrade plan

### 0. Preserve settings isolation and make the normal workflow measurable

**Implemented:** `test_features.py` redirects feature data to a throwaway directory. A full run with a sentinel in the real settings file preserved the sentinel and restored the original settings, tracker, and result bytes. Keep this isolation if the harness is refactored.

An offscreen app smoke now clicks the normal Run action, records Cloud as the selected backend, and exercises artifact validation/download with a stubbed GitHub client and a real rendered Cloud MP4. The explicit Cloud-failure case displays an error and launches no local Manim process. This verifies the app route; it is not a live desktop session or a new live GitHub dispatch.

**Success measures:** a sentinel settings file outside the test data directory survives a local and CI run; the UI smoke records a completed cloud job and downloaded MP4; explicit Cloud failure produces a visible error and zero local Manim child processes.

`docs/CLOUD_RENDERING.md` now documents that explicit Cloud mode reports failure without starting a local render.

### 1. Verify derivations and show the evidence

**Implemented:** structured derivation records carry equation forms, named variables, values, units, assumptions, and source provenance. SymPy checks supported algebraic transformations and substitutions; Pint checks dimensional consistency. Unsupported claims remain `not_checked`. These tools can catch algebra and unit mismatches, but they cannot decide whether the chosen physical model or its assumptions are appropriate.

The outcome appears beside derivation steps and in lesson/video evidence. The scene critic receives only facts the numeric solver can establish, and the UI distinguishes numeric-model verification from written-derivation verification. A reviewed benchmark is still needed to estimate false verified labels.

**Success measures:** each displayed claim has provenance and a check status; injected algebra/unit errors are caught in supported domains; unsupported domains remain explicitly unverified; the rate of false “verified” labels is zero in a reviewed benchmark.

SymPy documents symbolic substitution, simplification, and equation solving; Pint provides quantities and dimensionality checks. [SymPy symbolic operations](https://docs.sympy.org/latest/tutorials/intro-tutorial/basic_operations.html), [SymPy equation solving](https://docs.sympy.org/latest/guides/solving/index.html), [Pint units and dimensionality](https://pint.readthedocs.io/en/latest/getting/tutorial.html).

### 2. Turn the quality flywheel into a release gate

Keep the existing 6×6 critic and candidate tournament. An eight-scene review pack now spans several physics areas, and deterministic checks cover literal off-frame placement, likely overlaps, text size, timed marker coverage/runtime, duration, and numeric samples in the curated trajectory component. A human/critic comparison utility is ready, but the human ratings and critic scores have not been supplied. A VLM score should help rank scenes, not certify physics.

The repository has prompt-quality and visual-regression tools, and CI uploads visual-regression results. Chosen regressions remain non-blocking until thresholds are calibrated on the reviewed set. The render ledger records backend, timing, retries, renderer, quality, and cache metrics so quality gains can be weighed against waiting time and compute.

**Success measures:** a stable benchmark with human-reviewed labels; lower overlap/overflow and first-pass repair rates over time; measured agreement between draft and final-quality scores; no release regression in the reviewed scene set.

Recent code-centric video work also separates planning, coding, and visual criticism, and uses spatial anchors to make layout feedback concrete. TheoremExplainAgent reports that planning supports detailed long-form explanations while layout remains a recurring issue; Code2Video describes planner/coder/critic stages and visual-anchor feedback. These results support the project's direction, but they do not establish that any particular AetherLab score predicts student learning. [TheoremExplainAgent, ACL 2025](https://aclanthology.org/2025.acl-long.332/), [Code2Video, arXiv preprint](https://arxiv.org/abs/2510.01174).

### 3. Align narration to the existing visual beat schedule

**Implemented:** generated narration is split into segments tied to storyboard beat windows, with subtitles, target objects/equations, and a fixed overall duration. The Planck sample measured zero beat-boundary overrun and no speech-rate adjustment. The remaining check is a normal-speed human listening review for clarity and naturalness.

Study Manim Voiceover's bookmark and tracker-duration patterns before adding it as a dependency; the timing interface can be adopted without taking on a new runtime dependency. [Manim Voiceover quickstart](https://voiceover.manim.community/en/stable/quickstart.html).

**Success measures:** measured audio/beat boundary drift, subtitle-to-speech alignment, no fast or unnatural rate changes, and a complete final beat. Review sample videos at normal playback speed, not only by inspecting still frames.

### 4. Upgrade Manim as one local/cloud change

Manim Community 0.21.0 was released on 10 August 2026. Its official notes report a 2.2× Cairo speedup for animation-heavy scenes, optional Typst text/math rendering without a TeX installation, and bounded parallel encoding of partial movie files. AetherLab now pins 0.21.0 through its `render` extra, CI, cloud worker, and bundled workflow; the app environment was upgraded and focused compatibility checks passed.

**Implemented:** local/Cloud golden parity and a curated-component, typography, and repaired-math parity smoke now run against the pinned version. The tested Cairo path remains the default; OpenGL remains opt-in after visual regressions in the tested components. MathTypst was not made the default.

**Success measures:** local and cloud render the same golden scenes; no change in verifier results or text legibility; tracked wall-clock improvement; cloud worker and app report the same Manim version.

Source: [Manim Community 0.21.0 release notes](https://docs.manim.community/en/stable/changelog/0.21.0-changelog.html), [Typst and MathTypst guide](https://docs.manim.community/en/stable/guides/using_text.html).

### 5. Add a local spaced-review loop

**Implemented:** local due dates and a configurable review schedule are available for missed or low-confidence questions; confidence and review events are recorded. The effectiveness measures below remain open until learners complete delayed recall and transfer checks.

Retrieval practice has meta-analytic support, including field studies in psychology classrooms, but the exact schedule and transfer to multi-step physics problem solving should be measured rather than assumed. A controlled physics-tutoring study also found that platform-enforced sequencing and detailed solution scaffolds mattered; its result came from one course and should not be generalized into an efficacy promise. [Practice-testing meta-analysis](https://journals.sagepub.com/doi/10.3102/0034654316689306), [Harvard physics-tutoring RCT](https://www.nature.com/articles/s41598-025-97652-6).

**Success measures:** return rate to due questions, delayed accuracy after one and seven days, and performance on transfer questions. Do not market learning-effect claims until a controlled evaluation supports them.

### 6. Longer-term architecture: one validated scene specification

**Implemented:** `aetherlab.scene_spec.v1` carries equations and units, assumptions, solver parameters, evidence provenance, timed beats, narration, scene metadata, and assessment data across generation, rendering, canvas, analysis, and portable lesson export. Future clients can build on this backend-neutral contract.

**Implemented (parameters):** explicit request parameters are now authoritative at every boundary through one shared helper, `aetherlab/services/parameters.py::apply_request_parameters`. It is applied to the remote solver result, the offline fallback, the scene generator's prompt/spec inputs, and `build_scene_spec`. A regression follows one override (`mass=2.5` against a model-proposed `1.0`) from a remote solver response through the scene spec, canvas projection, numeric re-solve, research figure/LaTeX, and direct scene generation. Invalid entries (empty name, non-numeric, NaN/inf, bool) are skipped with a warning rather than raised, which keeps the path fail-soft. **Still open:** equation edits are not yet propagated the same way. A changed equation still needs a fresh solve.

## Recommended order

1. **Complete:** preserve test isolation, correct the Cloud-rendering docs, and exercise the UI-to-Cloud route and explicit-failure behavior.
2. **Partly complete:** step-level physics/provenance records and deterministic scene checks are implemented; paired human scene ratings and critic scores are still needed to calibrate the benchmark.
3. **Implemented:** narration and subtitles follow timed visual beats; normal-speed listening review is pending.
4. **Complete:** Manim 0.21.0 is pinned consistently and local/Cloud parity checks are recorded.
5. **Implemented; evaluation pending:** local delayed review is available; measure one- and seven-day recall and transfer before asserting learning efficacy.

The key strategic conclusion in the internal innovation report remains sound: AetherLab can distinguish itself through physics that users can inspect and cross-check, rather than by adding another general-purpose chat or unconstrained video generator. The research supports the architecture and the learning mechanisms above; it does not yet prove AetherLab improves physics learning outcomes. Measure those outcomes before making that claim.

## Implementation status - 25 September 2026

### Delivered and verified

- **M1/M4, real AI scene and richer timing:** The Planck radiation scene was generated by AI, passed safety, layout, play-budget, and duration gates without fallback, and rendered through GitHub Actions. Visual review moved the “UV catastrophe” tag into clear plot space. A later timing repair added readable holds to align all six beats, and the current review-pack master is 30.0 seconds / 900 frames. The saved Cloud mode was not changed.
- **M2, settings isolation:** Ran the full feature harness with a sentinel in the real settings file. The sentinel survived, and the original settings, tracker, and result bytes were restored exactly. The corrected run passed **215/215** features. F107 now asserts that MiniMax's provider default is preserved unless a per-call thinking override is explicitly supplied.
- **M3, render mode:** The user's Cloud preference remains saved; explicit Cloud failure does not start a local render.
- **Physics evidence and learning loop:** Derivation records preserve provenance and algebra/unit check states; unsupported claims remain `not_checked`. Local due dates and rescheduling for missed or low-confidence questions are implemented.
- **Sync and animation pacing:** Timed beat windows, narration cues, duration gates, 6-8 beat Cloud guidance, and the 16-call animation budget are implemented. Voiceover scheduling rejects overlapping or out-of-window beat audio and incomplete audio artifacts.
- **M5, Manim 0.21.0 parity:** Local and Cloud rendered the same deterministic 4-second Cairo scene at 30 fps and 120 frames. Both videos are 854x480 and 4.0 seconds. Sampled-frame mean absolute pixel error averaged 1.8335; 98.6-99.3% of pixels had per-channel differences at most 16. The Cloud MP4 metadata and local package both identify Manim 0.21.0. Evidence: `.analysis/manim-golden/comparison.json` and `comparison.png`.
- **UI-to-Cloud route:** Clicked `MainWindow.command_bar.run_button` in an offscreen app. The success case exercised the real `CloudRenderBackend` flow and artifact validation/download using a stubbed GitHub client and a real previously rendered Cloud MP4. The explicit Cloud-unavailable case displayed the error banner. Both recorded zero local Manim renders. Evidence: `.analysis/ui-cloud-smoke/result.json`. This verifies the app route; it is not a live desktop session or a second live GitHub dispatch.
- **M7, tracker artifacts:** Regenerated the canonical CSV/XLSX from the current generator. Strict integrity passed with **215 features, 215 stories, 215 results, 215 tests, and zero audit issues**; both file formats match the generator.
- **Cloud resilience and telemetry:** Transient GitHub run-status read errors retry within the existing deadline. The ledger records backend, timing, retries, renderer, quality, and cache metrics. Explicit Cloud failures stay visible without local Manim.
- **OpenGL candidate evaluation:** Compared `field_lines`, `kinetic_theory`, and `fourier_epicycles` locally at 854x480 and 30 fps. OpenGL failed on field lines because a Cairo `VMobject` was added to an OpenGL `VGroup`. Kinetic theory rendered in 17.3s with OpenGL versus 17.6s with Cairo, but the OpenGL output omitted the box and plot axes. Fourier epicycles took 56.5s with OpenGL versus 49.7s with Cairo and omitted most moving geometry. The contact sheets and run logs are in `.analysis/opengl-ab-20260925-011248/`; the repeatable runner is `tools/renderer_ab_benchmark.py`. These results close the benchmark and support keeping OpenGL opt-in and Cairo as the default/Cloud renderer.

### Follow-up delivered - 25 September 2026

- **Planck timing was aligned to its actual animation runtime.** The corrected scene previously had a 30-second storyboard but accumulated only 28.9 seconds of literal `self.play`/`self.wait` time, with later beat boundaries drifting by as much as 1.1 seconds. Added a conservative static timing gate that compares cumulative action durations between required beat comments and the storyboard; it counts any prelude before the first marker and declines to guess when dynamic timing or control flow makes the schedule ambiguous. The smoke validator and bounded repair prompt now use this gate. The six-beat scene received 1.1 seconds of readable holds and rendered through Cloud as a 30.0-second, 900-frame, 854x480 MP4 at 30 fps (199.425 seconds wall time). The resulting contact sheet was inspected. Evidence: `.analysis/ai-radiation-smoke/cloud-final-timed-scene.py`, `.analysis/ai-radiation-smoke/result.json`, and `.analysis/ai-radiation-smoke/timed-cloud-contact-sheet.png`. The configured render mode remains `cloud`.
- **M5 golden coverage now includes the curated component and text paths.** Added reproducible runner `tools/manim_parity_smoke.py`: it renders a 9.2-second `field_lines` component scene with generated `Text` typography and an intentionally text-mode `Tex` expression that must be repaired to `MathTex` before rendering. Local and Cloud outputs both measured 9.2 seconds, 276 frames, 30 fps, 854x480, and Manim 0.21.0. Across five sampled frames, mean absolute pixel error was 0.3945 and the lowest share of channels within 16 intensity levels was 98.854%; the comparison gate passed its recorded thresholds. Local wall time was 23.667s; Cloud call wall time was 153.168s, of which the Actions renderer took 3.74s and peaked at 304.406 MB. The contact sheet was inspected. Evidence: `.analysis/manim-parity-20260925/comparison.json`, `comparison.png`, and `cloud/runner-metrics.json`. The run exposed that GitHub's prefixed log lines defeated the old telemetry regex; `_parse_runner_metrics` now finds version/time/memory markers inside those lines, and a Cloud-backend regression asserts the values reach the ledger.
- **Beat-level narration was measured against that exact Cloud master.** A seven-cue narration and SRT were synthesized at +8% in `.analysis/timed-narration-cloud-20260925/`. Audio and video are both 30.0 seconds; all seven cues stay within their beat windows, maximum boundary overrun is 0, and no rate adjustment was needed. The final cue ends at 28.236 seconds within the 26-30 second final beat. The normal-speed human listening review remains pending. Narration stays disabled in the saved app settings. The automatic visual critic did not return a usable score for this Cloud render (Qwen returned HTTP 400; MiniMax returned an unparsable response), so no quality score is claimed.
- **The versioned scene specification is now wired into generation and outputs.** `aetherlab.scene_spec.v1` carries request parameters, solver equations/units/assumptions, evidence provenance, verification status, timed visual/narration beats, scene metadata, and assessment data. The generation prompt consumes the validated spec when available; pipeline and Qt workers attach and refresh it before and after rendering; timed narration, analysis evidence, and the interactive canvas project from it; portable lesson bundles include validated path-scrubbed JSON evidence files. Focused tests open an exported lesson zip and confirm the evidence JSON contains no machine-local paths, and exercise both scene-ready/render-ready UI callbacks while preserving a live parameter value.
- **Derivation checks now report numeric substitution separately from symbolic equivalence.** Supported records are evaluated at supplied solver values; a sampled match cannot override a failed symbolic transformation. Unsupported ODE syntax and missing units remain `not_checked`, while injected dimensional contradictions remain `failed`. The expanded regression verifies each result and carries the substitution status into scene-spec evidence and the expanded derivation details.
- **The deterministic visual review now checks explicit text size.** `scene_hygiene_warnings` emits an advisory for literal Manim font sizes below 20; computed sizes remain unjudged, and this heuristic is not a release gate. The other static checks continue to cover literal off-frame placement, likely shared-position overlap, timed marker coverage/runtime, and requested duration bounds.
- **Numeric trajectory agreement now has a deterministic scene-generation check.** The curated ODE trajectory scene serializes the solver's sampled coordinates to five decimal places, draws a piecewise-linear path through those exact samples, and advances its tracer uniformly in time instead of by path distance. A regression compares the generated coordinates with `solve_numeric` and checks the path and timing code. This establishes agreement at the serialized control points; it does not score arbitrary AI-authored curves or replace rendered-video/human review.
- **Human/critic calibration has a repeatable analysis command.** `tools/human_review_analysis.py` validates the eight-case pack, verifies the MP4s exist, summarizes human axis ratings, and calculates descriptive Spearman agreement when corresponding critic scores are supplied. It explicitly never declares a blocking gate calibrated. Current snapshot: 8 videos present, 0/8 complete human rating sets, 0 critic scores, so the report correctly remains `incomplete` at `.analysis/human-review-pack/analysis.json`. Re-run after entering ratings and supplying critic scores with `--critic-scores`.
- **Spaced review now captures learner confidence and exposes a configurable schedule.** Quiz cards let learners self-rate confidence before selecting an answer; low-confidence correct answers return at the first configured interval without advancing the mastery streak. The schedule is editable in Settings, persisted with the app config, and accepts up to eight intervals from 1 to 365 days. Review events and delayed recall timing are available from the local progress store for a later study. The test harness clears `AETHERLAB_REVIEW_INTERVALS_DAYS` so a machine-level override cannot leak into feature results.
- **Verification in this continuation:** all 24 tests in `tests/test_upgrade_missions.py` pass, including GUI confidence capture, symbolic-plus-numeric derivation checks, unsupported-unit-expression handling, numeric trajectory sample/time-order checks, the tiny-text heuristic, human/critic analysis, and saved-setting/environment precedence; the Settings dialog also round-trips a custom schedule. The added parity tool passes Ruff and the local/Cloud metadata, version, and sampled-frame thresholds; the radiation validation-only smoke passes; package/tool compilation and `git diff --check` pass. The full feature harness was not rerun in this continuation; its prior 215/215 run and settings sentinel evidence remain documented above.
- **Request parameters now reach every output (continuation after the session interruption, 25 September 2026):** `apply_request_parameters` makes explicit request values authoritative in the solver, scene generator, and scene spec. It skips invalid entries instead of raising. Its regressions pass (`test_request_parameter_flows_…`, `test_invalid_request_parameters_are_skipped_not_raised`).
- **Full gate re-run (25 September 2026):** The previous continuation had not re-run the full harness. Its first run reported **201/215**. There was one real regression, BUG-63 (F167): the confidence-selector change re-indented `answer_recorded.emit` inside the button loop, so each quiz answer was recorded once per choice. This would have corrupted the spaced-review event log. It is fixed and logged in `ERRORS_FOUND.md`. The other 13 failures were stale checks. Ten trajectory tests looked for the pre-rewrite `set_points_smoothly`/`MoveAlongPath` markers. F107 still expected the raw "Locked storyboard" block, which a validated scene spec now supersedes while carrying the same creative plan. F133 flagged two new tools that lacked the UTF-8 subprocess/stdio policy. F164 flagged the uncatalogued review-interval and confidence surfaces, now described under F167. After those fixes the harness passed **215/215** in a clean provider environment. The tracker integrity and feature-surface audits (80/80) pass, 63 pytest tests pass, and the real settings file was byte-identical before and after (render mode still `cloud`).
- **Human review acted on (25-26 September 2026):** The owner rated all eight v1 review videos 8/10 overall (from 8 sampled frames each, not per-axis), noting "missing more details and explanation". Inspecting the pack found two problems. First, BUG-64: the double-slit case had rendered a quantum wavepacket instead of fringes, because quantum keywords were checked before a named two-slit apparatus. Second, every curated video was 7-12 s with only a title. F216 now gives every 2-D curated component an intro card (concept, governing equation, what to watch) and a closing card (equation, 2-4 key numbers, takeaway) and sizes holds to the request duration. The numbers come from each component's own `params()` or numeric solve. For example, the pendulum's 57-degree first swing measures 2.10 s against the 2.01 s small-angle formula, matching the exact undamped value of 2.14 s once damping is accounted for. A refactor to share `params()` left all 300 sampled component outputs byte-identical. Rendered frames exposed subscript glyphs that drew as blank boxes; they were replaced, and the remaining glyph set is locked by `t_f216`. All seven curated cases re-rendered through Cloud at 29.1-30.0 s (116-155 s wall each). One transient GitHub read timeout was retried successfully. Evidence: `.analysis/human-review-pack-v2/` (review.json, contact_sheet.png, and `before_after_proof.mp4`, a 209 s side-by-side of v1 against v2). Gate: 216/216 features, both tracker audits, 63 pytest tests; saved settings byte-identical. v2 ratings are pending.
- **v3 explanation layer (26 September 2026):** v2 was rated 9/10. v3 applies the four highest-evidence techniques from `reports/PHYSICS_VISUALIZATION_INSPIRATION.md` to all 14 curated components:
  - a prediction card with a countdown;
  - timed captions during the animation, each with a highlight ring and pointer on the named object; captions can pin to a beat of the component's schedule, for example the orbit's closest approach;
  - the common misconception crossed out beside what actually happens;
  - the animation kept as a thumbnail beside the explanation.

  Four bugs were caught before the owner saw them, each found by looking at rendered frames rather than trusting the static gates:
  - pointers referenced objects before the animation created them (a render-time NameError);
  - the caption band let the title show through, and the highlight ring trailed moving objects by a frame;
  - two captions were out of sync with their moment (the lens and orbit captions);
  - animated `ValueTracker`s stretched the stage, so the Kepler thumbnail shrank to a sliver.

  All seven curated cases re-rendered through Cloud at 30.0-32.5 s. Evidence: `.analysis/human-review-pack-v3/` (review.json, contact_sheet.png, and `v2_vs_v3_proof.mp4`, a 214 s side-by-side). Gate: 216/216 features, both tracker audits, 63 pytest tests; saved settings byte-identical. v3 ratings are pending.
- **v4 creative scenarios (26 September 2026):** The owner rated v3 below v2: "v2 is better cause it uses different approaches and different ideas for each topic. it should be really creative." v2 and v3 had the same animations, and v3 wrapped every topic in one identical scaffold. The lesson: research-backed techniques are ingredients, not a template. v4 (F217) restages seven topics with a device chosen per topic (`aetherlab/services/scene_components/scenarios/`), reusing each component's `params()` and numeric solve. The v3 devices become opt-in, and the cards return to v2 style. The seven scenarios:
  - the pendulum race (1 kg and 3 kg in lockstep; double length √2 slower; 60° vs 10° release);
  - Kepler's stopwatch (distance-per-tick bars vary 3.0×, area-per-tick bars equal within 0.1%);
  - two waves meet;
  - a square wave one circle at a time (overshoot 13.7% → 9.1%);
  - follow the arrows (equal-length force arrows, lines grown along them, a live probe);
  - photon by photon (bands build from single hits and vanish when a slit is covered);
  - energy buckets (93% of the energy transfers at t = 4.5 s).

  F217 checks each claim numerically and checks the fallback to the plain component. Visual review of the Cloud frames fixed five text-layout issues before handoff. All seven were rendered through Cloud at 30.0-33.1 s. Evidence: `.analysis/human-review-pack-v4/` (review.json, contact_sheet.png, `v2_vs_v4_proof.mp4`). Gate: 217/217, both audits, 63 pytest tests; settings byte-identical. v4 ratings are pending.
- **v5 problem-solving videos (26-27 September 2026):** The owner rated v4 "really good" and set a new goal: animation that solves a concrete physics problem in about a minute, keeping the creativity, with quality first. F218 (`aetherlab/services/scene_components/problems/`) builds self-contained videos from the solver's givens. Each follows the Minnesota solving arc with subgoal labels, which worked-example research links to better transfer. Each uses its own device, and each ends by proving the answer with the simulation:
  - the kicked ball: two shadows; the flight lands on a flag at 32.5 m after 2.36 s; 30° and 60° land on the same spot;
  - a grandfather clock on the Moon: two clocks driven by simulated pendulums; one swing takes 2.46 s; a 16.4 cm pendulum keeps Earth time;
  - one lap of the ISS: Newton's cannon, then a time-lapse lap timed at 92.8 min; the one-day orbit is 35,786 km up.

  Every build checks the simulation against the analytic answer before emitting the scene. Without givens, the topic's v4 scenario still plays. All three rendered through Cloud at 1920×1080 in 60-66 s. Reviewing the Cloud frames showed the Cloud font runs wider than the local one and clipped three labels; every problem video now caps its text lines to the frame. Evidence: `.analysis/problem-pack-v5/` (videos and `problem_videos_v5.mp4`). Gate: 218/218, both audits, 63 pytest tests; settings byte-identical.
- **v6 harder problem videos (F221, 28 September 2026):** The owner asked for more creativity, harder topics, and "don't lose details while optimizing". Four new problem videos (80–110 s) keep the full working on screen as typeset MathTex. Cloud installs TeX automatically, and each equation falls back to plain text when LaTeX is missing. Every number is computed from the solver's givens and verified before the scene is emitted. Each has its own device:
  - **muons:** two stories, one ending. The everyday guess (33 half-lives) wipes out 400 muons in the first kilometres. In Earth's story the muon's clock runs 10× slow; in the muon's zoomed view the air is 1.5 km thick. Random lifetimes and an ODE check the 10.1% survival.
  - **quantum dot:** size decides colour. Whole half-waves build the n²E₁ ladder, and the 3→2 photon lands at 659 nm on a spectrum. A 1200-point Schrödinger solve reproduces the ladder, and squeezing the box shifts the light to green and blue.
  - **chaos:** twin double pendulums 10⁻⁶ rad apart. A live log-scale gap graph gives a Lyapunov exponent of 1.0 s⁻¹. The predicted split is 13.2 s and the measured one 12.8 s; each 1000× better start buys only +7.9 s and then +5.2 s.
  - **coupled pendulums:** in-step and opposite normal modes added into beats. T = π/(ω₂ − ω₁) = 10.3 s, and the full nonlinear simulation gives 10.2 s.

  Low-resolution frame reviews caught these before Cloud rendering:
  - a muon group whose updater never ran;
  - clipped labels;
  - a squeeze that only narrowed the box instead of spreading the rungs;
  - overlapping panels;
  - text too small to read.

  Evidence: `.analysis/problem-pack-v6/`.
- **Provider failover (F219, 27 September 2026):** Every model call goes through `llm_client.make_client`. The client tries the primary provider first, then an optional backup (`AETHERLAB_FALLBACK_*` or `fallback_*` in the app config). On the way it recomputes temperature and thinking flags for the backup, and it streams where a gateway needs streaming. Kimi K3 was trialled as primary and then turned off at the owner's request (28 September). MiniMax-M3 is again the only provider, and the backup slot is empty.
- **LaTeX study documents (F220, 28 September 2026):** The owner asked for "latex well-explained pdf files for a topic" and, for a problem, "write theories and solve [it] into pdf". `aetherlab/services/study_document.py` sorts each request into one of two kinds:
  - A **topic** becomes a study guide: overview, 4–6 sections that build intuition and then derive step by step, key results, a worked example, common mistakes and a summary.
  - A **problem** becomes a worked solution: the problem, a given/find table, the theory needed, a plan, numbered steps (symbolic first, then numbers), a boxed final answer, sense checks, common mistakes, and AetherLab's own independent simulation check.

  The model writes structured JSON; the app does the typesetting (tcolorbox, booktabs, amsmath). Parsing repairs single-backslash LaTeX. If pdflatex fails, compilation heals itself: it locates the failing block from the log, or by bisection when the log points elsewhere, and swaps only that block for a plain-text version. Without a model, the document is built from the solver. The same path serves the app's PDF export and `python -m aetherlab --pdf "<prompt>"`.

  A review of the first live MiniMax-M3 PDFs found six defects, all fixed:
  - multi-line equations collapsed onto one overflowing line;
  - headings were numbered twice;
  - variables were left as plain text (`a\_y`, `R_max`);
  - ✓ printed as "?";
  - a tooling FAIL line appeared among the checks;
  - a `\-` in math overprinted "6–7".

  A second round of live runs found and fixed more:
  - MiniMax dropped connections often (5 of 6 solver calls in one probe). Authoring now retries a dropped connection twice with backoff, but never retries a timeout. When the solver itself falls back, the simulation check and figure are left out rather than faked.
  - A `\n` between list items was misread as a LaTeX command and printed literally. Multi-item strings are now split into bullets.
  - Bare `\checkmark` and `v_0^2` in prose printed as text.
  - Loose web matches ("Taekwondo" and "Knuckleball" for a football problem) were cited. A Wikipedia reference now stays only if its title words appear in the document.

  `--pdf` also saves the model's `content.json` beside the PDF, so a document can be re-typeset without another model call.

  One limit remains: the model's prose is not fact-checked. The Planck guide's worked example compares 3.54×10⁷ W/m² to "half the solar constant", which is about 1361 W/m². The arithmetic is right; the comparison is wrong. Numbers in problem documents are cross-checked by the independent simulation; claims in prose are not.

  Evidence: `.analysis/pdf-v1/` (before) and `.analysis/pdf-v2/` (after; `iterations/` holds the intermediate runs and an offline-fallback example).
- **Still open:** M6's MiniMax thinking A/B remains inconclusive; eight human scene ratings are still blank in `.analysis/human-review-pack/review.json`; the narrated Planck sample still needs normal-speed listening; and spaced-review learning efficacy requires one- and seven-day recall plus transfer measurements. No ratings or efficacy results were invented.

### Evidence still requiring human input or more samples

- **M6 MiniMax thinking A/B remains inconclusive.** In the 24 September rerun, the thinking-disabled arm produced a non-fallback AI scene (7,902 characters, 14 `self.play` calls), repaired its duration estimate from 19.5 to 27.6 seconds, and rendered a 31.0-second Cloud video. Its recovered MP4 received 3/10 from a two-endpoint MiniMax-M3 probe; the critic flagged the blank opening and a sparse final frame with the Rayleigh-Jeans curve clipped, which manual inspection confirmed. This two-frame score cannot assess transitions or pacing. The thinking-enabled arm took 954.968 seconds, produced truncated output across bounded attempts, and fell back without rendering, so it has no video to score. Separate one- and two-frame probes on another Planck clip returned 7/10, but the one-frame critic made a false physics claim about the inverse-fourth-power curve and the two-frame critic sampled a deliberately blank opening. A four-frame request returned HTTP 500; a six-frame request returned HTTP 200 with empty content. These probes are not calibrated evidence, and the two arms lack comparable accepted output and scores. Production leaves MiniMax thinking at the provider default. Reports: `.analysis/minimax-thinking-ab-20260924-182245/report.json`, `.analysis/minimax-thinking-off-vision-20260924/report.json`, `.analysis/minimax-vision-one-frame-20260924/report.json`, and `.analysis/minimax-vision-two-frame-20260924/report.json`.
- **Human quality calibration still needs paired real scene reviews and critic scores** for legibility, physics, pacing, and teaching value. No human labels were fabricated. The ready-to-review pack contains eight Cloud-rendered MP4s, a contact sheet, and blank rating fields in `.analysis/human-review-pack/review.json`; the current analysis records 0/8 completed ratings and 0 critic scores. Fill the ratings and supply comparable critic scores before deciding whether any quality threshold can become a release gate.
- **Learning efficacy is unmeasured.** The local spaced-review loop is implemented; delayed one- and seven-day recall and transfer outcomes still need a study before making learning-effect claims.
