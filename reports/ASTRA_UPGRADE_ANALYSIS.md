# AetherLab animation pipeline: implementation review

To: Claude Code, implementing engineer  
Reviewed: 2026-10-02  
Baseline: supplied PR at `13a6b12`; implementation and offline checks are in the current worktree.  
Evidence labels: **measured** = existing owner measurement or test output; **observed** = source inspection/offline test; **hypothesis** = not verified in an actual long AI/cloud run.

## 1. Executive summary

1. Long requests over 45 s now use one global storyboard and resumable, serial AI segments capped at 28 s; this keeps the existing Manim cost/play gates useful per segment.
2. The UI offers 30/60/120/180 s. Beat counts and storyboard output budgets scale with target length; segments assemble only after measured-duration and artifact checks pass.
3. A segment receives its own ordinary compile, render/repair and visual-critique path. The critic can sample beat centers per segment; it still reviews at most six anchors by default.
4. A bounded Newtonian N-body integrator and explicit 2D three-body scene are implemented with refinement/invariant checks; unsupported curated regimes decline inaccurate templates.
5. Kinetic-theory speeds now match the displayed 2D Maxwell/Rayleigh density; lens inputs that require unsupported virtual-image geometry are declined.
6. Offline regressions: 111 passed; feature harness: 221/221 passed. These are software and fixture checks, not proof of a live 60–180 s AI lesson.
7. No live model call or cloud dispatch was made. Do not advertise long-form reliability until the staged VPN/cloud experiments below pass.
8. Keep the measured thinking policy, Cairo and serial local rendering. The agent team remains opt-in pending a paired quality/latency study.

## 2. Current pipeline and changed extension points

| Stage | Current path and evidence |
|---|---|
| Request/orchestration | `ui/widgets.py` exposes 30/60/120/180 s; `ui/main_window.py:1702` puts that value on `ProblemRequest`. Both `services/pipeline.py:57-68` and `ui/workers.py:157-170` route requests over 45 s to the same segmented service. |
| Solve/references | `services/llm.py` solves once; `services/rag.py` and the pipeline prepare references once. The AI code path now passes the complete derivation steps instead of truncating at six (`scene_generator.py`, long-context prompt construction). The solver's own answer is still not a certificate that the requested model is correct. |
| Curated routing | `manim_runtime.py:206-231` retains curated problem/scenario/component priority for ordinary requests. A long request forces the AI path for its segments. `scene_components/__init__.py:113,227` routes explicit supported three-body input; unsupported curated regimes decline their specific visual. |
| Storyboard/code | `scene_generator.py:781-859` requests roughly one meaningful beat per 3.75–5 s, rejects under-filled plans, scales the storyboard token budget up to 32,768, and schedules one global timeline. `segmented_pipeline.py:37-155` verifies full time coverage and partitions only at beat boundaries. Each segment receives a locked local storyboard and shared concept/palette/continuity. |
| Segment lifecycle | `segmented_pipeline.py:248-567` stores a fingerprinted manifest and hashed code/video, resumes valid completed segments, and renders sequentially. Segment generation uses normal static gates and `render_scene_with_repair`; fallback templates and failed segments produce `incomplete`. A successful set is concatenated through `assembly.assemble_lesson`; final measured duration must be within ±1 s at 60 s or ±2 s at 120/180 s. |
| Narration | Long-form narration must have per-beat sync, a silent source track, cues and merged subtitles; excessive boundary overrun (>0.25 s) or speech-rate adjustment (>20%) returns incomplete. Subtitle times are shifted by measured segment duration. There is no whole-clip narration downgrade in the segmented success path. |
| Render/critique | Each segment goes through normal local/cloud rendering and repair. `manim_runtime.py:1697-1719` supplies beat-center sample times. `scene_critic.py:138-202,279-319` extracts requested times where available, otherwise keeps the ordinary six uniform samples. Segments are sequential; cloud parallelism is intentionally deferred. |
| Hard-topic foundation | `services/multibody.py` supports 2–8 point masses in 2D/3D with bounded velocity-Verlet integration and fail-closed collision/range checks. `scene_components/problems/three_body.py` accepts only explicit 2D three-body givens and checks a 10k/20k step comparison plus energy/angular drift before drawing. Lens, quantum, relativity, thermodynamic-cycle, magnetic and unsupported optics routes no longer receive certain misleading curated stand-ins. |

## 3. Bottlenecks and what still breaks

### Long animations

**Before segmentation**, an exactly estimated 60 s monolithic cloud scene fails admission: the existing render-cost score is already about 4.0 before updater/heavy-object overhead, above the 3.5 gate. The supplied measurements remain relevant: one AI blackbody run took about 7 min 42 s and scored about 4/10; a 34 s cloud render took about 3.5 min round trip and peaked near 770 MB RSS. The agent-team blackbody run was recorded at 21 min, 20.7 s output and 2/10. These are individual measurements, not distributions (`ERRORS_FOUND.md`, recent sections dated 2026-09-30/10-01).

The new route avoids one giant scene but makes more separate model/render attempts. At the default 30 fps, 60/120/180 s still mean 1,800/3,600/5,400 output frames. **Hypothesis:** serial segment wall time will grow roughly with segment count plus repeated worker setup, while peak render RSS should be bounded only if scene geometry/updaters do not accumulate. Neither claim has a long-run measurement. A 28 s segment may still exceed the existing 3.5 cost gate for dense geometry or heavy updaters; the service reports incomplete rather than removing detail.

The storyboard budget now scales: targets request 12–16, 24–32 and 36–48 beats at 60, 120 and 180 s. The output-token budget scales with that beat maximum, capped at 32,768. This addresses the prior fixed 6–8-beat prompt and truncated global JSON, but does not guarantee model completeness, detailed equations, or finished scene code. Codegen remains one complete scene per segment under the existing ceiling. **Hypothesis:** the 180 s global storyboard can still be truncated or lose objective ordering; preserve finish reason and usage and test with the configured MiniMax endpoint.

Partitioning is exact only at authored beat boundaries. Offline fixtures show a 120 s board of 24 five-second beats becomes five segments; a 180 s board of 36 such beats becomes eight, because six whole beats exceed the 28 s cap. Real boards will create a different number. A pathological >28 s single beat is not split; it reaches ordinary admission and can fail. The global timeline validates ordered coverage, but timeline markers remain generated-code comments, not proof that on-screen changes occurred in that time.

Narration guards are stricter than the legacy whole-scene path, but they only validate the metadata and segment outcomes available today. No 60/120/180 s speech track was generated. The 0.25 s overrun and 20% speech-rate gates need normal-speed human review; accurate timestamps can still accompany rushed or unintelligible audio.

Critic sampling is now segment-local and event-aware, which reduces the 180 s blind interval from about 36 s to beat-scale gaps. The current default still sees at most six frames per segment and selects centers from the timeline; short transients, exact transition boundaries and unsampled beats can be missed. The reviewer sees declared physics expectations but cannot infer a hidden numeric error from appearance. The critic remains advisory/fail-soft.

### Hard animations

| Topic | Implemented state | Remaining failure modes |
|---|---|---|
| Multi-body | Bounded point-mass solver and explicit, numerically checked 2D three-body scene. Tests cover a circular two-body invariant fixture, step refinement, invalid inputs, collisions, step cap and explicit route. | No collision resolution, constraints, adaptive close-encounter stepping, or AI-callable object library. The scene is not a general n-body lesson; supports exactly three specified 2D masses/positions/velocities and a requested time. Chaotic endpoint refinement can reject a useful trajectory. |
| Fields | Existing dipole component remains narrow; magnetic/charged-particle topics no longer get the electrostatic depiction. | General multipole, magnetic field, particle trajectories and 3D geometry remain unsupported. Declining a curated component allows AI codegen to continue; it does not itself prove the generated explanation correct. |
| 3D | Existing scalar `Surface` examples remain available. Hydrogen/orbital prompts no longer receive the signed-heightfield pseudo-orbital. | No new verified `ThreeDScene` camera/object framework, robust projection/layout checks, or field isosurface library. Generic prompt allowance is not demonstrated capability. |
| Relativity | Existing muon-survival problem remains the narrow supported case; broad spacetime/Lorentz requests decline generic curated shortcuts. | No reusable Lorentz event/interval calculator or verified multi-frame scene. |
| Quantum | Harmonic/coherent-state and named double-slit cases remain distinct; unsupported tunneling/barrier/orbital visualizations are declined as curated components. | No normalized general wavefunction evolution or barrier transmission helper. AI fallback can still attempt unsupported topics unless a global capability policy is added. |
| Thermodynamics | Kinetic-theory microstate velocities are independent Gaussian components; its plotted 2D Maxwell speed density is Rayleigh and temperature-scaled. | No cycle/engine/entropy/P–V work and first-law component. Current offline feature check verifies deterministic construction/routing; it does not provide a Monte Carlo goodness-of-fit or rendered-distribution proof. |
| Optics | Converging-lens builder declines known virtual-image or out-of-supported-range givens; unsupported optics phrases decline misleading ray-diagram routes. | No diverging lens, virtual image, TIR, grating or single-slit implementation. Lens drawing still uses a restricted display scale and is not an AI-callable ray helper. |
| Plots/layout | Existing source lints and preflight continue. | There is no general proof that `axes.plot` stays in viewport or that transformed bounding boxes do not overlap. `scene_validation.py` textual placement heuristics cannot establish geometry. Require declared plot bounds plus runtime projected geometry for strong guarantees. |

Numerical integration verifies a chosen model, not that the student’s intended model was chosen. The three-body component’s “consistent input units” assumption is not unit conversion. High-stakes conceptual regimes must stay explicitly unsupported until their own physical fixtures and independent references pass.

### Speed and stability

The implementation intentionally renders serially; parallel cloud segment fan-out is not safe to infer from the existing tournament fan-out. The local workstation has about 8 GB RAM and previous background renders were killed, so keep one local render at a time. Cloud response time can be dominated by queue/setup/upload rather than frame rendering; separately log enqueue, worker setup, render and download. The 3.5 min supplied short cloud measurement and 153 s setup/transport record in `MANIM_UPGRADE_NOTES.md` are not 120 s estimates.

The segmented manifest reuses completed outputs by fingerprint and artifact hashes. It does not yet expose dependency-specific invalidation (for example, a voice-only edit preserving every visual segment) or prove cache correctness under app restart, disk failure and profile changes. No cloud/local benchmark, concurrency experiment or 60–180 s local render was run.

## 4. Ranked upgrade plan for Claude Code

Effort: S = localized, M = coordinated modules, L = cross-pipeline. Acceptance values are release gates, not claims already achieved.

### 1. Establish the 60-second live gate — implemented offline; **L**, medium/high risk

**Current code:** use `segmented_pipeline.py` for requests >45 s, one global plan, beat-boundary partitions, serial render/repair/critic, resumable manifest and strict assembled duration. UI exposes the target. Do not revert to one monolithic scene to reduce setup time.

**Creativity/correctness:** AI directs one scenario and carries its palette, apparatus and entry/exit beat across segments; exact solver givens/full derivation stay shared. Missing or template-substituted segments remain incomplete.

**Acceptance:** run 20 cloud-backed AI cases (five topics × four seeds, at least half narrated): 20/20 complete at 60 s ±1 s; all authored objectives mapped to a beat; no silent fallback; no critical scientific error in blind review; audio/visual anchors ≤0.25 s and no human-rated unintelligible cue. Current fake-render tests do not meet this gate.

### 2. Scale objective and narration budgets — partial; **M**, medium risk

**Current code:** duration-scaled beat minimum/maximum, model-output allowance scaled up to 32,768, complete solver derivation supplied, segment-level narration fail-closed checks. Keep solver thinking ON and codegen/critic/reviewer thinking OFF.

**Next:** record provider token usage, finish reason, truncation, cue text/audio timing and every fallback reason. Validate required equations/units/derivation IDs against a plan checklist before codegen and after assembly. Do not assume a larger output budget creates correct detail.

**Acceptance:** in 60/120/180 s generations, zero truncated/under-filled global plans pass as complete; 100% checklist equations and derivation steps survive to recap or spoken cues; ten narrated jobs per duration have no missed cue, >0.25 s boundary overrun or unapproved >20% rate shift.

### 3. Extend critique to actual events and geometry — partial; **M**, medium risk

**Current code:** the normal segment revision loop can receive up to six storyboard beat-center frames per segment. No extra model call was added and no criterion was falsely promoted to numeric verification.

**Next:** sample equation appearance, extrema/turning points, collisions, segment joins and final recap, preserving exact extracted timestamps. Add runtime checks for declared plot ranges, finite samples and transformed bounding boxes. Record coverage by beat ID; if a critical event cannot be sampled, mark the review incomplete.

**Creativity/correctness:** the critic may suggest composition improvements; numeric contracts and objective coverage block correctness claims. Retain a prior scored scene if a new critique is skipped or worse.

**Acceptance:** all critical beat/event IDs sampled or covered by deterministic tests; ≥90% of seeded clipped-curve/overlap/missing-step/transient defects caught on a 30-case corpus with ≤10% false positives; missing critique never upgrades a result to “reviewed.”

### 4. Grow capability-gated verified components — partial; **L**, high scientific risk

**Current code:** N-body helper and one explicit three-body scene; narrow topic declines; corrected 2D gas speed law; lens refuses unsupported image regime. The components are still full-scene templates rather than reusable composable objects.

**Next:** extract a versioned, audited helper interface for physics data and drawing primitives. Each helper declares model, assumptions, units, supported domain, invariants, display mapping, size/cost bound and independent fixtures. Keep creative direction free: AI chooses scenario, camera, staging, comparison and sequence while measurements resolve only through checked helpers. Do not widen arbitrary import/filesystem access in `code_safety.py`.

**Acceptance:** 50 routing fixtures with zero wrong-apparatus curated hits; helper numeric fixtures pass convergence/analytic limits; five hard-topic benchmarks in Stage 3 achieve zero critical physics errors. Unsupported model remains visibly “unverified/incomplete,” even if AI can draw something plausible.

### 5. Unify admission and geometry checks across repairs — **M**, medium risk

**Current gap:** the segmented path inherits ordinary per-scene cost/play gates, but the estimator can mark loops/helper calls exact incorrectly; post-revision resource/cost checks are not consistently centralized. See `scene_validation.py` duration estimator and `manim_runtime.py:2639` `_blocking_scene_issues`.

**Next:** make uncertain control flow `exact=False`; share a single pre-dispatch resource decision across initial code, render repair, critic revision and agent output. Enforce at every stage and bound nested attempts by a parent job budget. Add axis range/clip contracts and post-transform geometry sampling; do not claim arbitrary Python is statically proven safe.

**Acceptance:** 20-case duration-helper corpus has zero false exact estimates; every dispatch path blocks the same over-budget fixture; repaired/revised code cannot bypass the segment budget; all declared curves finite and inside their declared viewports at endpoints/extrema.

### 6. Measure worker cost before enabling cloud parallelism — **M**, medium risk

**Current code:** segments render serially and cache by request/solver/RAG/profile fingerprint plus artifact hashes. This bounds concurrent segment memory but repeats setup and time.

**Next:** add stage timings/RSS, unique attempt directories for critic/narration/assembly, dependency-aware cache invalidation, parent cancellation/deadline and stable cross-backend physical seeds. Benchmark worker dependency caching/batching. Only then try two cloud segments in flight; retain one local render.

**Acceptance:** cancellation stops/marks incomplete within 5 s of polling opportunity; two identical-stem attempts cannot share extracted frames/audio; restart after segment 2 reuses verified segment hashes; changing voice does not regenerate physics/code; two-job cloud fan-out cuts paired median wall time ≥25% with no higher failure rate or lower blind quality.

### 7. Keep the agent team experimental — **S/M**, high benefit uncertainty

Recorded evidence is one poor 21-minute run. The new ordinary path fixes some routing and asset issues but does not change the team's sequential lead/tool design or prove its gates match current admission rules. Continue only as a separately measured feature.

**Acceptance to expand:** ten paired hard-topic jobs, blinded human review, same render/model budgets: ≥1 point median quality gain, no additional critical physics failures, and ≤25% median latency overhead. Otherwise retain opt-in research only.

## 5. Staged roadmap and experiments

### Stage 1: 60 s reliably

**Software present:** request selector, scaled global storyboard, segment manifest/resume, strict assembly duration, segment-level repair/review and narration checks. **Not complete:** no live 60 s AI/cloud scene is known to pass.

Run five topics × four generations: (1) blackbody spectrum heating, (2) angled projectile with full range derivation, (3) damped oscillator with energy loss, (4) converging lens with object inside focus (must decline this builder or use a correct virtual-image path), and (5) ideal-gas heat/work cycle (must not masquerade as kinetic theory). Half narrated. Include seeds and a distinct creative treatment per topic; compare to a matched 30 s baseline. Record route, tokens/finish reason, objectives, model calls, segment setup/render times, RSS, measured duration, repair count, artifact hashes, voice sync and blind human score.

Fault-inject second-segment render failure, one skipped critic, cancellation, malformed media and assembly retry. Expect explicit incomplete status, correct resume, no template substitution, no concurrent local fallback storm. Exit at 20/20 duration-complete and no critical physics failures; separately report quality and time distributions.

### Stage 2: 120–180 s

First run the same five topics at 120 and 180 s twice each, once narrated, once silent (20 cases). Include full worked derivation plus a parameter comparison. Restart after two segments; edit a label, change a physical value, change only voice; corrupt one segment hash; interrupt assembly. Prove exact cache invalidation and that no stale physical content reassembles.

Measure one cloud segment at a time before evaluating two concurrent renders. Record queue/setup/runner/download separately and peak RSS of client, renderer and ffmpeg. Compare 28 s segments to longer segments only after recalibrating admission; maintain actual output duration ±2 s. Latency goals are hypotheses: 120 s cloud render P95 ≤10 min and end-to-end P95 ≤15 min; 180 s ≤15/20 min. Never trade away derivation detail to hit these.

### Stage 3: hard-topic library

Start with the implemented 2D three-body case as the helper-quality pattern, then add exactly these five independently reviewed tests:

| Topic / distinctive scenario | Numeric and visual acceptance |
|---|---|
| Three-body mission-control encounter | Unequal masses, declared units and collision exclusion. Energy/angular drift ≤0.1% on reference interval and half-step endpoint difference ≤1% initial extent. All three identities/state labels persist at joins. Do not require chaotic trajectories to agree indefinitely. |
| Charged probe in field-mapping chamber | Pure-B control conserves speed/energy ≤0.1%; analytic radius/period ≤0.5%; Coulomb superposition within 0.1% outside stated singularity radii. Clearly distinguish field lines from particle paths. |
| Muon spacetime relay, two inertial frames | Event transform and interval invariance relative error ≤1e-8 on scaled fixtures; proper/coordinate times and frame labels remain distinct across joins. |
| Wavepacket and finite quantum barrier | Norm error ≤1e-3; scattering control R+T within 1e-3; explicit potential/boundaries; label density, amplitude and phase correctly. |
| Gas engine viewed through refracting window | Test separately: cycle work/first-law closure ≤0.5% declared energy scale; Carnot control ≤0.1% relative; Snell residual ≤1e-6 and TIR threshold within 0.1°. No invented coupling between the two topics. |

At each stage render 60 s and 180 s with three creative variants per topic. Require zero generic fallback presented as verified, all numeric fixtures pass, and ≥7/10 median blind human quality per topic. Report unsupported capability explicitly.

## 6. Risks, unresolved defects and owner questions

1. **Live status:** no long AI scene has been rendered locally/cloud in this implementation pass, and no long narration has been synthesized. The 221 feature checks and fake-media segment tests establish contracts only. Maintain that distinction in UI and release notes.
2. **Critic keep-best:** source review found a final revision path where `skipped` critique may allow an unscored trial to survive instead of restoring the prior scored best (`manim_runtime.py`, visual revision loop near lines 1830–1860). Add an explicit regression.
3. **Post-repair admission:** generated-cost/play guards are not one common check after every repair/revision. A changed candidate must not escape the initial scene budget.
4. **Artifact races:** critic frame and narration scratch paths include video stems in shared temp/output directories. New segments are serial, but independent app jobs can still collide. Use unique attempt IDs before any parallel fan-out.
5. **Cloud reproducibility/privacy:** existing cloud action does not carry the local Manim seed consistently. Uploaded source lands in the public `gopheriv/manim-render-worker` git history; artifact retention does not erase commits. Do not add raw reference excerpts, private prompt payloads or avoidable solver response text to public manifests.
6. **Local capacity:** renderer concurrency follows CPU-derived limits, not this machine’s 8 GB RAM. Keep local work serialized until memory is measured under long scenes.
7. **Three-body limits:** no collision response or adaptive integrator; the visual supports explicit 2D data and uses a fixed-duration showcase. Step-halving agreement can be misleading for chaotic long horizons; reject rather than imply universal validity.
8. **Routing fallback:** “decline curated builder” currently means AI codegen may still attempt the topic. The app needs a global capability declaration/status before calling an arbitrary AI scene verified.
9. **Graphics:** no static proof for plot clipping or bounding-box overlap. Six critic anchors per segment remain sparse. Add deterministic checks before raising critic frame/call count.
10. **Feature tracker artifacts:** `feature_test_results.json` and the tracker CSV/XLSX were regenerated after the full pass. Any later test change requires rerunning the harness and `build_feature_tracker.py` in that order.

Open owner decisions: Is selected target runtime strict including narration (implementation currently gates final assembled media strictly)? What latency/cost budget is acceptable at 720p30? May prompt-derived code use a private worker repository? Who will perform blind physics/audio review? Which unsupported family should be implemented after three-body: field trajectories, relativity, optics, quantum or thermodynamics? Until those answers and live gates exist, ship long output as an explicit preview capability, not as established correctness or reliability.

## 7. Offline verification performed

- `python -m pytest -q tests/test_segmented_pipeline.py tests/test_multibody.py tests/test_bugcheck_regressions.py tests/test_scene_preflight.py tests/test_upgrade_missions.py`: **111 passed**.
- `python test_features.py` with isolated temp data, offscreen Qt and provider keys removed: **221/221 passed**. Includes one ordinary local smoke render; no live LLM or cloud work.
- `python build_feature_tracker.py`: completed; subsequent F165 tracker-integrity probe passed (221 features/stories/results/tests aligned).
- `python -m compileall` over changed service/UI/test modules and `git diff --check`: completed clean before final report update.
- No setting file was edited, no live model request/cloud render was dispatched, and no commit was made.
