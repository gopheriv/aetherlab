# AetherLab — Render Reliability Fix Prompt + Cloud Rendering Analysis

Two parts:
- **Part A** — a paste-ready prompt for an agent session to fix the manim
  "sync bug" and the render-reliability bugs that stop the pipeline from
  coding and rendering *hard* scenes.
- **Part B** — a deep analysis of using GitHub (and alternatives) as a cloud
  rendering backend.

Both are grounded in the current code (`aetherlab/services/manim_runtime.py`,
`__main__.py`, `scene_generator.py`, `scene_critic.py`).

---

# PART A — Prompt: "Make hard scenes render reliably"

```text
You are a senior Manim Community + Python engineer. AetherLab generates
LLM-written Manim scenes and renders them via a subprocess. The generator is
good; the RENDER PLUMBING is what fails on ambitious ("hard") scenes and blocks
cross-platform / cloud rendering. Fix the reliability layer so the model can
spend its budget on creative, complex scenes instead of fighting the renderer.
Quality and correctness first; assume unlimited time.

READ FIRST
  aetherlab/services/manim_runtime.py  — render_scene / render_scene_with_repair
    / _render_once / _find_manim_command / _scene_name / _find_video /
    _clean_old_renders / _detect_render_tier / detect_latex
  aetherlab/__main__.py                — the `--manim` frozen-bundle relay
  aetherlab/services/scene_generator.py — generate / repair / storyboard
  aetherlab/services/scene_critic.py    — frame sampling (PyAV) + VLM critique
  aetherlab/services/code_safety.py, scene_validation.py — the static gates

════════════════════════════════════════════════════════════════════════
BUG 1 — THE SYNC BUG (frame-cache desync). HIGHEST PRIORITY.
════════════════════════════════════════════════════════════════════════
render_scene runs WITHOUT `--disable_caching` (see the "let Manim cache frames
for speed" note). Manim caches *partial movie files* keyed by an animation
hash and stitches them into the final MP4. On a regenerated or repaired scene
that reuses a scene name / media dir, Manim can splice STALE partial movies —
the rendered video is then out of sync with the current code (old frames, wrong
timing, half-updated animations). This is the "manim sync bug."
Fix, in order of preference:
  1. Render each scene into a UNIQUE per-render media dir (include a content
     hash AND a monotonic/uuid suffix) so no two renders ever share a partial
     cache — eliminates cross-render bleed entirely.
  2. Pass `--disable_caching` for the FINAL/quality render (correctness over
     speed); keep caching only for throwaway draft/critique renders if desired.
  3. Guarantee `_clean_old_renders` wipes `media/videos/<scene>` AND the
     `partial_movie_files` + `Tex`/`text` cache subtrees before every render,
     not just the videos dir.
  4. Make `_find_video` return the file written by THIS render (match on the
     known output path Manim reports, or the file whose mtime is after the
     subprocess start time) — never "newest mp4 in the tree," which can pick a
     neighbor from a previous run.
Add a regression test: render scene A, then render a DIFFERENT scene B that
hashes to a colliding/adjacent name, and assert B's video is B (e.g. differing
duration/first-frame), proving no partial-cache bleed.

════════════════════════════════════════════════════════════════════════
BUG 2 — CROSS-PLATFORM SUBPROCESS (blocks Linux/macOS + all cloud rendering)
════════════════════════════════════════════════════════════════════════
`subprocess.run([...], creationflags=0x08000000 | ...)` is Windows-only.
`creationflags` and the `BELOW_NORMAL_PRIORITY_CLASS` bit are invalid on POSIX.
Gate every Windows-only subprocess arg behind `sys.platform == "win32"`; on
POSIX use `start_new_session=True` + `os.nice()` for the below-normal tier.
Audit ALL subprocess.run calls (render, GIF export in main_window, pdflatex in
services/pdf) for the same Windows-only flags. This single fix is the
prerequisite for Part B (cloud runners are Linux).

════════════════════════════════════════════════════════════════════════
BUG 3 — FROZEN-BUNDLE RENDER (PyInstaller dist produces render-error)
════════════════════════════════════════════════════════════════════════
The `--manim` relay in __main__.py hands argv to `manim.__main__.main`, but the
frozen bundle still renders with status render-error. Diagnose the ACTUAL manim
stderr (it's captured in scene_bundle.diagnostics, 8000-char tail — surface it).
Likely causes to check and fix:
  • Manim data files / plugin entry-points not collected by PyInstaller
    (mapbox_earcut, manimpango, skia/pango fonts, the default .cfg). Extend
    packaging/aetherlab.spec collection and verify `manim render` works from a
    clean dist on a machine without a dev install.
  • ffmpeg: Manim needs an ffmpeg binary. Bundle one (imageio-ffmpeg provides a
    portable binary) and point Manim at it (FFMPEG_BINARY env / config) so the
    dist doesn't depend on a system ffmpeg.
  • LaTeX: detect_latex() already gates MathTex; confirm the frozen path honors
    it and that Text-only scenes render with zero LaTeX installed.
The build gate in packaging/build.py already refuses to package unless the
frozen smoke prints "Scene status: rendered" — keep it; make it pass for real.

════════════════════════════════════════════════════════════════════════
BUG 4 — HARD-SCENE SURVIVAL (don't let ambition cause failure)
════════════════════════════════════════════════════════════════════════
Make complex scenes more likely to reach a good render:
  • Timeouts scale with quality but NOT with scene weight. Estimate cost from
    scene_validation.estimate_duration + updater/mobject counts; give heavy
    scenes a longer ceiling before render-timeout, and prefer a draft-quality
    probe render (480p15) to validate the animation, then a final high-quality
    render only once the draft renders + passes critique.
  • render_scene_with_repair repairs render-error and render-timeout; ensure the
    timeout-repair actually reduces load (fewer always_redraw, lower t_steps)
    rather than gutting the scene — verify with a deliberately-heavy fixture.
  • Add a per-render resource guard: cap frames × resolution so a runaway scene
    (e.g. 60s at 4K from a bad run_time) can't wedge the machine.
  • Surface partial success: if the final render times out, keep the last
    successful draft render instead of returning nothing.

════════════════════════════════════════════════════════════════════════
BUG 5 — OBSERVABILITY (so failures are diagnosable, not silent)
════════════════════════════════════════════════════════════════════════
  • On render-error/timeout, write the failing scene .py + full manim stderr to
    data_dir/logs/renders/<timestamp>/ so any failure is reproducible.
  • Classify failures (LaTeX / hallucinated-API / timeout / ffmpeg / OOM) and
    count them; feed the class into the repair prompt (error_learner already
    has the hooks).

CONSTRAINTS
  • Manim Community + subprocess isolation stay. Don't import manim into the UI
    process. Keep the AST safety gate in front of every render.
  • Every fix ships with a test in test_features.py (offscreen-safe) and a row
    in build_feature_tracker.py; `python test_features.py` must stay green.
  • Verify cross-platform intent by running the render path with the Windows
    flags stubbed out (simulate POSIX) so CI on Linux would pass.

DELIVERABLE ORDER: Bug 1 (sync) → Bug 2 (cross-platform) → Bug 4 (hard scenes)
→ Bug 3 (frozen) → Bug 5 (observability). Bug 2 unblocks Part B.
```

---

# PART B — Cloud rendering via GitHub: deep analysis

**Short answer: yes, GitHub Actions can render Manim in the cloud, and it's a
genuinely clever zero-infrastructure option — but it's a background/offload
tool, not a real-time renderer, and it has real auth, security, and quota
caveats. Prerequisite: Bug 2 above (the renderer must run on Linux).**

## B.1 Why it works
- GitHub Actions gives free Linux VMs (ubuntu-latest: 4 vCPU, 16 GB RAM,
  ~14 GB disk). Manim is CPU-only (cairo/OpenGL software raster) — **no GPU
  needed**, so a CI runner is a fine renderer.
- Manim ships an official image (`manimcommunity/manim`) with LaTeX + ffmpeg
  preinstalled; a job can `container: manimcommunity/manim` and render in
  seconds of setup instead of apt-installing TeX Live.
- Artifacts (the MP4) upload cheaply (videos are 1–30 MB; 500 MB/90-day free
  storage on private repos is plenty).

## B.2 The four architectures (ranked for a student tool)

**1. `workflow_dispatch` render-on-demand (recommended).**
A `.github/workflows/render.yml` takes inputs (scene code or a gist/artifact
ref + quality) → renders in `manimcommunity/manim` → uploads the MP4 artifact.
The desktop app triggers it via the REST API (`POST /actions/workflows/
render.yml/dispatches`), polls the run, downloads the artifact zip, extracts the
MP4.
  + No servers, no cost for public repos (unlimited minutes), simple.
  − ~30–90 s overhead (queue + VM boot + checkout) before a single frame; not
    interactive. Best framed as "Render this hard scene at 4K in the cloud"
    while the user keeps working locally.

**2. `repository_dispatch` (event-driven).**
App POSTs a custom event with the scene payload; same render job. Equivalent to
#1 with a cleaner payload channel; use if you outgrow dispatch inputs' 65 k
limit (large scenes → put code in a gist/artifact and pass the ref).

**3. Matrix / batch rendering.**
One workflow renders N scenes (or one scene at l/m/h/4k) in parallel matrix
jobs. Great for "render my whole worksheet overnight" or pre-baking the example
gallery. This is the strongest, least-caveated use: **CI that pre-renders a
gallery of example problems on every push**, committed/released as assets — the
app ships with beautiful videos, zero student compute.

**4. Self-hosted runner (a lab PC/GPU box registered to the repo).**
"GitHub-orchestrated" but your hardware. Removes minute limits and lets you add
a GPU/many cores. Best if a school has a spare machine; it's really a private
render server wearing a GitHub coat.

## B.3 The hard caveats (the "couldn't we?" gotchas)
- **Auth friction.** Triggering Actions needs a token with `actions:write`.
  You CANNOT ship a shared write token in a student app (anyone could burn your
  minutes or push to the repo). Options: (a) each student uses their OWN fork +
  their OWN fine-grained PAT (real setup friction); (b) a tiny broker service
  holds the token and the app calls the broker (now you have a server — defeats
  "zero infra"); (c) public repo + a GitHub App with least-privilege
  installation tokens (best, but nontrivial).
- **Running LLM-written Python on CI = code execution.** A malicious/hallucinated
  scene could read secrets (the repo token!) or exfiltrate. Mitigate: run the
  code_safety AST gate BEFORE dispatch AND inside the job; render in the
  container with `permissions: {contents: read}` and NO secrets in the render
  job; never expose the trigger token to the render step.
- **Quotas.** Private repos: 2000 free min/month (Free tier) — a class sharing
  one repo will exhaust that fast at high quality. Public repos: unlimited
  Actions minutes → for an OSS project this is the killer feature.
- **Latency & concurrency.** Cold start + queue; free tier caps concurrent jobs
  (~20). Fine for background/batch, wrong for "instant preview."
- **Not persistent compute.** Each run is ephemeral; no warm renderer, no state.

## B.4 Alternatives worth knowing (if GitHub's caveats bite)
- **Modal / Replicate / RunPod** — serverless functions; sub-second cold-ish
  starts, pay-per-second, optional GPU, a proper Python SDK. The right answer if
  cloud rendering becomes a core, real-time feature rather than an offload.
- **A small FastAPI render service** (manim in Docker + a job queue) on a cheap
  VM — full control, predictable cost, warm workers; more infra to run.
- **Google Cloud Run / AWS Batch / Fargate** — container renderers that scale to
  zero; production-grade, more setup than GitHub, cheaper than always-on.

## B.5 Recommendation
- **Now, free, high-value:** use Actions as a **matrix batch renderer in CI** to
  pre-render the example/gallery scenes (architecture #3) — pure win, no auth
  friction, ships great videos with the app. If the repo is public, minutes are
  unlimited.
- **Opt-in "Render in cloud" button (later):** architecture #1 with the user's
  own fine-grained PAT, gated behind the AST safety check, for heavy/4K renders
  they don't want to run on a laptop. Document it as background, not instant.
- **If it becomes core:** graduate to Modal/a render service (B.4) — GitHub
  Actions is the clever bootstrap, not the long-term real-time backend.
- **Non-negotiable prerequisite either way:** Part A Bug 2 (make the renderer
  cross-platform) — today the Windows-only `creationflags` would fail on every
  Linux runner before Manim even starts.
```
