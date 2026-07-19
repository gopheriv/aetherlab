# AetherLab — Design Brief v2 (for Claude Design)

Paste this whole file to Claude Design. It is self-contained. It **evolves** the
existing v1 design system (see §3) — do not start from zero. Deliver updated
high-fidelity mockups (§8), an updated component sheet (§7), and refreshed
tokens/guidelines in the same structure as the current `design/` package
(tokens/ · guidelines/ · components/ · ui_kits/aetherlab-desktop/) so the output
can drop in as a replacement.

---

## 1. Product in one line
AetherLab turns a natural-language physics/math prompt into an analytical
derivation → textbook references (RAG over real university physics books) → a
**storyboarded, LLM-directed Manim Community animation** (MP4, self-healing
render pipeline, optional vision-model critique) → a live interactive
parametric canvas driven by parameter sliders.

## 2. The redesign direction in three words
**Modern. Technical. Mathematical.**

1. **Modern & tech** — push the current "dark lab" toward a precision-instrument
   feel: HUD/oscilloscope cues, fine dot-grid and blueprint textures, hairline
   rules, glassy elevated panels, mono-spaced telemetry, restrained glow. Think
   "mission control for physics", not "gamer RGB". Everything still flat-ish and
   Qt-buildable (§9).
2. **Formulas are the brand.** Typeset mathematics must be a first-class visual
   element everywhere — not body text pretending to be math (see §5).
3. **Manim Community is part of the identity.** The videos are rendered with
   Manim CE; the design should proudly and tastefully acknowledge it (see §6).

## 3. What exists today (baseline you are evolving)
The v1 system you produced is implemented and shipping:
- Persistent left icon rail (Solve / Refs / Scene / Params / History) driving
  ONE workspace; 44px TitleBar; pipeline timeline strip (Solve → RAG → Scene →
  Render nodes with pulse/elapsed/cancel); bottom CommandBar (Examples ·
  prompt · quality · Run/Cancel); Toast feedback; EmptyState with setup CTAs;
  RunningView with blueprint loading overlay; Library manager (file list with
  Indexed/Pending chips, "Get starter library" OpenStax download dialog,
  incremental Re-index with progress strip); Settings dialog (Provider /
  Rendering / Paths); History list; Simulation panel with Canvas/Video/Code
  pill tabs, video transport (frame-step, seek, speed), error banner.
- Current tokens (keep as the base, evolve tints/shades, keep AA+ contrast):
  bg `#0A0A0F` · panels `#0D0D14`/`#13131A` · hairlines `#1E293B`/`#334155` ·
  cyan `#06B6D4` · emerald `#10B981` · violet `#8B5CF6` · amber `#F59E0B` ·
  rose `#F43F5E` · text `#F8FAFC`/`#94A3B8`/`#64748B`.
  Type: Segoe UI/Inter + Cascadia Code mono. Radius 8. Lucide 1.75px icons.

## 4. New capabilities since v1 that the design must now cover
These exist in the product and have **no designed surface yet**:
1. **Storyboard** — before coding a scene, the LLM produces a directed
   treatment: concept, staging, palette, THREE ACTS with durations and beats,
   a hero-frame description, an idle loop, and a per-act narration script.
   Design a **Storyboard strip/panel**: act timeline (ESTABLISH → EVOLVE →
   REVEAL) with durations, expandable beats, the hero frame called out, the
   narration lines displayed script-style. It should read like a film slate /
   shot list.
2. **Visual critique** — an optional vision model watches the rendered video
   and returns ship/revise + a 0–10 score + issues. Design a **Critique badge**
   on the video view (score, verdict, expandable issues list) and a "revised
   ×N" pill when revisions were applied.
3. **Self-heal telemetry** — renders can undergo repair rounds (crash or
   timeout) before succeeding. Design a subtle **"repaired ×N"** affordance and
   a diagnostics drawer (mono log style) instead of dumping text in the code
   view.
4. **Starter library** — 8 OpenStax books (University Physics 1–3, Astronomy,
   Calculus 1–3, College Physics) + user PDFs; the RAG index holds ~28k chunks.
   The Library screen should feel like a **research bookshelf**: book-spine or
   card visual per source, chunk counts, license note (CC BY), index freshness.

## 5. FORMULAS AS A DESIGN ELEMENT (the headline requirement)
Typeset math must permeate the design — display-quality, not ASCII:

1. **Hero equation banner.** The derivation view leads with the problem's
   governing equation, typeset large (think chalkboard-hero): e.g.
   `m·ẍ + c·ẋ + k·x = 0` or `∇×E = −∂B/∂t`. Serif math (STIX/Cambria-Math
   look), italic variables, proper minus signs, centered, with a faint cyan
   underline glow. Design normal + long-equation (scrollable/shrink) states.
2. **Inline math in derivation steps.** Each numbered step mixes prose with
   typeset fragments; show how inline math sits in body text (baseline
   alignment, slightly brighter than prose).
3. **Equation chips.** Small pill-shaped typeset equations used as keyword
   chips (e.g. `ω₀ = √(k/m)` as a chip beside "resonance").
4. **Ambient math texture.** Empty states and the loading overlay may use
   large, ultra-low-contrast (≤6% opacity) formula watermarks (Maxwell,
   Schrödinger, Euler–Lagrange) as background art — decorative, never
   legibility-harming. Provide the exact formulas and placement rules.
5. **Live parameter math.** The parameter rail shows each variable with its
   symbol typeset (γ, ω, ℓ) next to the mono numeric value — design the row
   with symbol · slider · value · reset.
6. **Implementation note (for your Qt-mapping section):** equations will be
   pre-rendered to pixmaps via LaTeX (MiKTeX is present) or Matplotlib
   mathtext — so any typeset-math visual is buildable; treat equations as
   images with a known baseline, not as selectable rich text.

## 6. MANIM COMMUNITY IDENTITY
1. **Attribution done proudly:** a "Rendered with Manim Community" badge on
   the video view (small banner logo lockup or text badge — Manim CE logo is
   available in their repo; if unusable, design a text-only badge) and a line
   in Settings/About. Follow the vibe of 3blue1brown-style math animation
   culture without copying assets.
2. **The video frame is a stage.** Treat the video player as a "screening
   room": true-black letterboxed frame (Manim renders on black), thin cyan
   progress filament, act markers on the seek bar sourced from the storyboard
   (ESTABLISH/EVOLVE/REVEAL tick marks), hero-frame bookmark you can jump to.
3. **Scene code view as artifact.** The generated Manim code is a deliverable
   users export — design the code view like a polished editor pane: line
   numbers, Manim-aware syntax accent colors (class names cyan, self.play
   emerald, strings amber), a header row with engine/status/duration-estimate
   chips, Copy + Export actions.
4. **Storyboard ↔ video linkage.** Clicking an act in the storyboard strip
   seeks the video to that act's start (design the interaction affordance).

## 7. Component sheet to deliver (default/hover/active/disabled, dark)
Everything from v1 (rail item, timeline node, command bar, parameter row,
reference card, video controls, derivation block, toast, settings fields) PLUS:
- Hero equation banner (normal, long-equation, loading-shimmer states)
- Inline-math derivation step (collapsed preview + expanded)
- Equation chip
- Storyboard act card + act timeline strip (pending/active/complete while
  rendering; static when done)
- Narration script line (act label + spoken line, script formatting)
- Critique badge (ship ≥7 emerald / revise amber / skipped muted) + issues
  popover
- "Repaired ×N" pill + diagnostics drawer (mono log rows with severity dots)
- Library book card (title, size, chunks indexed, license, freshness dot)
- Video seek bar with act markers + hero-frame bookmark
- "Rendered with Manim Community" badge (two sizes)

## 8. Screens to mock (deliverables)
1. Empty/first-run — with ambient math texture + setup CTAs (key, library).
2. Pipeline running — timeline mid-flight **plus the storyboard strip filling
   in as acts are planned**, loading overlay behind.
3. Result · Derivation — hero equation banner, typeset steps, equation chips,
   references beside.
4. Result · Video — screening-room player, act markers, critique badge,
   Manim CE attribution, storyboard strip docked below, parameter rail.
5. Result · Canvas — live canvas with legend/hover/zoom chrome (canvas itself
   is custom-painted; design its chrome: toolbar, readout chips, export
   button).
6. Result · Code — the artifact editor pane.
7. Library — bookshelf with starter-library download flow (book picker,
   progress, indexing).
8. Settings — now including Vision model (critique) field + existing
   provider/render/paths.
9. History — runs with status, refs count, critique score, re-run.

## 9. Hard constraints (unchanged from v1 — they are real)
- Buildable in **PyQt6/QSS + QPainter**: no web fonts assumed, no CSS
  grid/flex-only effects, no blur-heavy glassmorphism (subtle translucency ok).
  Equations = pre-rendered pixmaps (§5.6). Name the Qt widget mapping for
  every new component.
- 1280×720 → 4K reflow; keyboard-first (Ctrl+Enter run, Ctrl+1..5 rail,
  Ctrl+Shift+C code, Escape cancel) with visible focus states.
- Keep the token baseline (§3) — evolve, don't replace; AA+ contrast; dark
  theme primary.
- Motion: purposeful only (stage transitions, storyboard fill-in, tracer,
  critique badge arrival). Nothing loops forever except the live canvas
  tracer and the loading overlay.

## 10. Output format requested
- 2–4 sentence rationale for the evolved visual direction.
- Annotated mockups for §8, component sheet for §7.
- Updated token tables (colors incl. any new tints, spacing, radii, type
  scale **plus a new "math type" scale**: hero equation, inline math, chip
  math sizes).
- The Qt mapping note per component.
- Deliver in the existing `design/` package structure (tokens/, guidelines/,
  components/, ui_kits/aetherlab-desktop/) so it can replace the v1 folder.

## 11. Out of scope
No backend changes; no new features beyond surfacing what §4 lists; no light
theme (note tokens that would need one later); don't redesign the Manim video
content itself — only the app around it.
