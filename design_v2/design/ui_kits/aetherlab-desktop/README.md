# aetherlab-desktop — UI kit (v2)

Drop-in replacement for the v1 `design/` package. Evolves, does not replace, the v1 token baseline.

## Contents
- `../../tokens/tokens.md` — colors, radii, spacing, type + **math type scale**
- `../../guidelines/guidelines.md` — visual direction, formulas-as-brand, Manim identity, constraints
- `../../components/components.md` — full component sheet + per-component Qt mapping
- `../../../AetherLab v2.dc.html` — annotated hi-fi mockups (all 9 screens + component sheet), interactive canvas

## Screens (§8)
1. Empty / first-run — ambient math texture + setup CTAs
2. Pipeline running — timeline mid-flight + storyboard filling in + loading overlay
3. Result · Derivation — hero equation banner + typeset steps + chips + references
4. Result · Video — screening room + act markers + critique badge + Manim CE + storyboard dock + param rail
5. Result · Canvas — plot chrome (toolbar, readout chips, legend, export) + param rail
6. Result · Code — artifact editor + diagnostics drawer
7. Library — research bookshelf + starter-download dialog
8. Settings — provider / rendering / **vision·critique (new)** / paths
9. History — runs w/ status, refs, critique score, re-run

## How the mockup renders math
The `.dc.html` uses KaTeX to typeset math **production-accurate** for review. In the shipping Qt app, replace KaTeX with pre-rendered LaTeX/mathtext pixmaps (§5.6) — the visual target is identical.

## Fonts
- UI: Inter / Segoe UI
- Mono: JetBrains Mono (swap for Cascadia Code in Qt)
- Math: KaTeX fonts (STIX/Cambria-Math look)

## Out of scope (§11)
No backend changes; no new features beyond surfacing §4; no light theme; Manim video content itself unchanged.
