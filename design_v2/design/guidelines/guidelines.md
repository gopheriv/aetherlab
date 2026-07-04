# AetherLab v2 — Guidelines

## Visual direction — Modern · Technical · Mathematical
Push the v1 dark lab toward a **precision instrument / mission-control** feel:
- Hairline rules over heavy borders; fine dot-grid (`radial-gradient` dots, 26–32px) and blueprint grid (crossed 40px lines at ~6% cyan) as texture.
- Mono-spaced telemetry (elapsed, counts, fps, coordinates) in JetBrains Mono — numbers are always mono.
- Restrained cyan glow: a thin filament + a soft shadow, never bloom. No saturated multi-hue “RGB”.
- Flat-ish, translucency only (`rgba` panels at 60–80%), **no blur-heavy glass** — Qt/QPainter buildable.
- Motion is purposeful only: stage transitions, storyboard fill-in, the canvas tracer, the loading tracer, critique-badge arrival. Only the canvas tracer and loading overlay loop forever.

## Formulas are the brand (§5)
1. **Hero equation banner** leads the derivation view — governing equation at `math-hero` (40px), centered, faint cyan underline glow. Long equations shrink then horizontally scroll.
2. **Inline math** in steps sits on the baseline of prose, rendered one shade brighter (`tx`) than the surrounding body (`tx-2`).
3. **Equation chips** — pill-shaped typeset fragments used as keyword chips (cyan for results, violet for scene concepts, neutral otherwise).
4. **Ambient math texture** — large ≤6% watermarks on empty/loading surfaces only.
5. **Live parameter math** — each parameter row is `symbol · slider · value · reset`, symbol typeset (ζ, ω₀, x₀), value mono.
6. **Implementation** — equations are pre-rendered to pixmaps (LaTeX via MiKTeX, or Matplotlib mathtext). Treat every typeset element as an image with a known baseline, not selectable rich text.

## Manim Community identity (§6)
- **Attribution, proudly:** a “Rendered with Manim Community” badge in the screening-room frame corner (two sizes), plus an About line in Settings. Original text/mark lockup (a cyan aperture glyph) — no copied assets.
- **The player is a screening room:** true-black letterbox, thin cyan progress filament, violet act ticks sourced from the storyboard (ESTABLISH / EVOLVE / REVEAL), an amber hero-frame bookmark you can jump to.
- **Code view is an artifact:** editor pane with line numbers, Manim-aware syntax accents, engine/status/duration chips, Copy + Export.
- **Storyboard ↔ video linkage:** clicking an act in the docked strip seeks the video to that act’s start.

## New surfaces (§4)
- **Storyboard** — act timeline that fills in during planning (complete → active shimmer → pending dashed); narration shown script-style; hero frame called out.
- **Visual critique** — badge with verdict + 0–10 score (emerald ship ≥ threshold / amber revise / muted skipped) and an expandable issues list; “revised ×N” pill when revisions applied.
- **Self-heal** — subtle “repaired ×N” pill + a mono diagnostics drawer with severity dots, instead of dumping logs into the code view.
- **Starter library** — research bookshelf: coloured spine + title + size + chunk count + freshness dot; starter-download dialog with book picker + progress.

## Layout & interaction constraints (§9)
- One workspace driven by the persistent left icon rail (Solve / Refs / Scene / Params / History).
- 1280×720 → 4K reflow. Docks are fixed-width, content flexes.
- Keyboard-first: Ctrl+Enter run · Ctrl+1..5 rail · Ctrl+Shift+C code · Esc cancel. Every interactive element has a visible focus ring (cyan 1.5px outline).
- AA+ contrast on all text/background pairs; accent-on-dark checked for chips and pills.
