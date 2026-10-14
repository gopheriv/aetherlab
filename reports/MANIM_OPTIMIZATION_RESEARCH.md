# Manim optimization and ManimML: research for AetherLab

*Claude Code, 2026-10-02. Published sources plus experiments run on this machine (Manim 0.21.0, Python 3.14).*

## Summary

1. **Static gates and a vision critic are not enough. Execute the scene without rendering and check its
   geometry.** The SGA paper (2026) does exactly this: <5 s per scene versus 30–90 s for render plus VLM
   critique. It reports that VLM critics barely see geometric errors (ρ = 0.24). AetherLab's new preflight
   (commit 24623ba) already covers crashes, out-of-frame objects and exact duration. The next step is
   SGA's **overlap and legibility checks with exact fix vectors**.
2. **Long videos come from per-section generation, not one big call.** TheoremExplainAgent reaches
   5–10 min videos with planner + per-scene coding (a single-call approach failed past 20 s). Code2Video
   cut generation time **86.6 → 15.4 min (5.6×)** by generating and debugging sections **in parallel**.
   Astra's new segmented pipeline is serial, so parallel sections are the main speed lever left.
3. **Do not adopt ManimML. Copy its design.** It is stale (last release 0.0.24, April 2023) and its basic
   forward-pass animation **fails on Manim 0.21** (verified below). Its real lesson is the pattern:
   a short declarative description that expands into a full, verified animation. AetherLab's curated
   components are this pattern. Expose them to the AI coder as building blocks.
4. **Manim's own speed knobs are mostly used up for drafts.** Cairo (2.2× faster in 0.21) is the
   renderer; the WebGPU renderer PR was closed unmerged; parallel encoding gave ~2–4 % at 480p here.
   The remaining wins are fewer renders (preflight, keep-best revisions) and parallelism (sections,
   cloud jobs), not raw Manim speed.

## Findings

### Manim Community 0.21.0 (released 2026-08-10; AetherLab already runs it)

| Change | What it means here |
|---|---|
| Cairo path construction vectorised, fewer pixel copies: **2.2× on animation-heavy scenes** | Already in effect. No action needed. |
| NumPy cache keys hashed by content: **94–98 % less hashing CPU** | Helps only where caching is on (repair lineage); AetherLab mostly runs `--disable_caching`. |
| `--max-inflight-encoders N` / `--encoder-queue-size M` (default 1 / 8): −56 % on an encoding-heavy benchmark, 8–11 % on real renders | **Measured here: no meaningful gain at 480p** (see experiments). Consider 2 only for `-qh` final renders, after measuring. |
| `Typst` / `MathTypst` mobjects: math without a TeX install (`pip install "manim[typst]"`) | Would remove the slowest, most fragile step (LaTeX). **Blocked today:** the `typst` package has no wheel for Python 3.14 (verified below). Revisit when one ships. |
| `--seed` (0.20), `--dry_run`, `--save_sections` | AetherLab uses `--seed` and now `--dry_run` (preflight). `--save_sections` could give per-section clips from one process. |

Sources: [0.21.0 changelog](https://docs.manim.community/en/latest/changelog/0.21.0-changelog.html),
[releases](https://github.com/ManimCommunity/manim/releases),
[0.19.0 changelog](https://docs.manim.community/en/stable/changelog/0.19.0-changelog.html) (PyAV replaced
the ffmpeg subprocess, a separate frame-writer thread), 0.19.1 (cheaper `always_redraw` via fewer copies in `become`).

**Renderer outlook.** The WebGPU renderer PR (#4968) was **closed unmerged on 2026-09-12**; maintainers
want a unified renderer protocol first ([PR](https://github.com/ManimCommunity/manim/pull/4968)). The
OpenGL renderer has known compatibility and performance gaps
([#1957](https://github.com/ManimCommunity/manim/issues/1957)). Stay on Cairo.

**Profiling.** The official guidance is cProfile + SnakeViz on a scene run inside
`tempconfig({"disable_caching": True})`; the docs call Manim "very unoptimized" without naming hotspots
([performance docs](https://docs.manim.community/en/stable/contributing/performance.html)). Profile real
AetherLab scenes before optimising scene-level code.

### ManimML

- What it is: a library by Alec Helbling and Duen Horng Chau (Georgia Tech) for animating ML
  architectures ([paper](https://arxiv.org/pdf/2306.17108),
  [README](https://github.com/helblazer811/ManimML/blob/main/Readme.md)). You declare
  `NeuralNetwork([FeedForwardLayer(3), Convolutional2DLayer(...), ...])`, and
  `make_forward_pass_animation()` composes the animation from pre-built per-layer pieces.
- Status: **0.0.24, April 2023, one maintainer, "documentation is lacking"**
  ([PyPI](https://pypi.org/project/manim-ml/)). No declared dependency pins.
- **Verified here:** installed in isolation against Manim 0.21, its minimal 3-layer forward pass fails
  with `ValueError: Trying to play AnimationGroup(Group) without animations`. It would need a port.
- **Lesson for AetherLab:** a domain-specific layer of verified components lets a user (or an LLM) write
  a few lines and get a long, correct animation. This attacks AetherLab's main failure mode directly:
  TheoremExplainAgent's top failure was **Manim API hallucination**. Every line of low-level Manim the
  model does not have to write is a line it cannot hallucinate.

### Research on LLM-generated Manim videos

| Work | Method | Key numbers |
|---|---|---|
| **TheoremExplainAgent** (ACL 2025) — [paper](https://arxiv.org/html/2502.19400v1) | Planner → per-scene coding agent, ≤5 fix attempts, scenes concatenated | Videos up to 10 min; o3-mini 93.8 % success; ~1,100–2,200 s and $0.10–2.42 per video. **Generic RAG over Manim docs lowered success (93.8 → 82.1 %).** Top failure: API hallucination; most videos had layout issues. |
| **Code2Video** (Oct 2025) — [paper](https://arxiv.org/html/2510.01174) | Planner (outline → storyboard + shared asset store) → **parallel per-section** coder with **ScopeRefine** repair (line ±1 → block → whole section) → VLM critic with a **6×6 anchor grid** | Parallel sections 86.6 → 15.4 min; ScopeRefine 2.8× fewer tokens; ablations: no planner −41.5, no shared assets −30.0, no anchor grid −26.8, no critic −21.3 (TeachQuiz). |
| **SGA** (Jul 2026) — [paper](https://arxiv.org/html/2607.18116v1) | Runs `construct()` with each statement wrapped in try/except, extracts bounding boxes, checks **overlap** (AABB, >30 % high / >10 % medium), **out-of-frame**, **legibility**, **label collisions**; returns a minimum separation vector and ±5 lines of code per conflict | +16.1 % visual quality; <5 s per scene vs 30–90 s render + VLM critique; +7 % pipeline time; VLM aesthetics correlates weakly with geometric correctness (ρ = 0.24). |

### Plugins

- **manim-voiceover / manim-narration**: bookmarks trigger an animation at a specific spoken word, with
  word-level alignment ([voiceover quickstart](https://voiceover.manim.community/en/stable/quickstart.html),
  [manim-narration](https://github.com/maejam/manim-narration)). AetherLab already times narration per
  beat; word-level bookmarks would tighten sync for long videos. Not tested here.
- **manim-physics**: rigid bodies via pymunk, electromagnetism (`Charge`, `ElectricField`, …), waves
  ([plugin page](https://www.manim.community/plugin/manim-physics/),
  [docs](https://manim-physics.readthedocs.io/en/latest/)). The original author may not maintain it.
  **Not tested here**; check compatibility the same way ManimML was checked before relying on it.

## Experiments on this machine

| Experiment | Result |
|---|---|
| Preflight (dry run, 2 fps) on real AetherLab scenes | Crashes caught in **4–11 s** (hex colour, `wait(0)`); off-frame curve (y = 5.96) and a formula at y = 55 found; exact duration (3.75 s for a lagged-group scene). Warm 15 s, cold 35–50 s (LaTeX-bound). |
| LaTeX cost | **1.74 s per formula** cold (10 physics formulas: 17.4 s). Shared per-code TeX cache removes the repeat in the render. |
| ManimML 0.0.24 on Manim 0.21 | **Fails** on a minimal forward pass (see above). |
| `typst` for `MathTypst` on Python 3.14 | **`No matching distribution found`**; not usable yet. |
| `--max-inflight-encoders` 1 vs 2, blackbody scene, 480p, warm cache | 20.1 / 20.4 s vs 19.2 / 19.9 s: **~2–4 %, within noise**. Encoding is not the bottleneck at draft quality. |

## Recommendations, ranked

| # | Upgrade | Why | Effort |
|---|---|---|---|
| 1 | **Extend the preflight into an SGA-style verifier**: pairwise overlap with severity, minimum readable text height, and a fix vector ("move `label` 0.8 down"). Map each object to its source line (record the line at creation inside the runner) so repair gets ±5 lines of context. | Largest measured quality gain per second spent (SGA +16 %); AetherLab's critic only sees 6 frames, and live critiques flagged overlaps every run. | M |
| 2 | **Parallelise segments in Astra's segmented pipeline**: generate segment code concurrently (cap 2 MiniMax calls, since two long requests at once have dropped connections) and render segments as parallel cloud jobs. | Code2Video's 5.6×; long videos are otherwise serial-minute sums. | M |
| 3 | **Give the AI coder AetherLab's verified components as callable building blocks** (the ManimML lesson): `PlanckCurve(T, axes)`, `Pendulum(...)`, problem templates, the `eq()` helper. Document their signatures in the codegen prompt; preflight validates usage. | Removes the main failure mode (API hallucination) and makes long scenes shorter to write. | M–L |
| 4 | **ScopeRefine repair**: try a line-level fix (±1 line) for single-line errors (NameError, bad kwarg, wrong colour type) before the current function-scope repair. | 2.8× fewer repair tokens in Code2Video; most AetherLab crashes this week were one-liners. | S |
| 5 | **Keep retrieval narrow**: keep the current error-scoped signature lookup; do not add a generic Manim-docs RAG. | TheoremExplainAgent measured generic RAG *hurting* (−11.7 points). | — |
| 6 | **Typst math when a Python 3.14 wheel exists** (or in the cloud runner if pinned to 3.12): fall back to `MathTex` when Typst is missing. | Removes the LaTeX step: ~35 s of a cold preflight, fragile TeX errors, the TeX install on cloud runners. | S–M, later |
| 7 | **Word-level narration bookmarks** (manim-voiceover style) for long videos. | Beat-level timing drifts over minutes; word alignment keeps pointers on the spoken term. | M |

**Do not do now:** switch renderers (OpenGL gaps; WebGPU not merged); depend on ManimML (broken on 0.21);
raise `max_inflight_encoders` for drafts (no measured gain).
