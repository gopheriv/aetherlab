# AetherLab v2 — Tokens

Evolves the v1 baseline (§3). Dark theme is primary; AA+ contrast throughout. No light theme ships — a future light theme would need a parallel surface ramp and inverted text ramp (noted where relevant).

## Color

### Surfaces
| Token | Hex | Use |
|---|---|---|
| `bg` | `#0A0A0F` | App background |
| `stage` | `#000000` | **New.** True-black video/screening-room letterbox (Manim renders on black) |
| `panel` | `#0D0D14` | Title bar, rail, docks |
| `panel-2` | `#13131A` | Cards, list rows |
| `elev` | `#181822` | **New tint.** Elevated controls, segmented fills, hover targets |
| `hover` | `#1C1C27` | **New tint.** Hover surface |

### Hairlines
| Token | Hex | Use |
|---|---|---|
| `line-0` | `#141A24` | **New.** Faintest dividers (table rows, section rules) |
| `line` | `#1E293B` | Standard hairline |
| `line-2` | `#334155` | Emphasis border / input outline |

### Text
| Token | Hex | Use |
|---|---|---|
| `tx` | `#F8FAFC` | Primary text, inline math emphasis |
| `tx-2` | `#94A3B8` | Body / prose in derivation steps |
| `tx-3` | `#64748B` | Meta, mono telemetry, disabled |

### Accents (roles fixed)
| Token | Hex | Role |
|---|---|---|
| `cyan` | `#22D3EE` | Primary / active / progress filament / plot. *(v1 `#06B6D4` retained as `cyan-deep` for fills & spines)* |
| `emerald` | `#10B981` | Success · **critique “ship” (≥ threshold)** · done nodes |
| `violet` | `#8B5CF6` | **Scene / storyboard / act markers** — the “directing” color |
| `amber` | `#F59E0B` | Warning · **critique “revise”** · repaired diagnostics · incomplete setup |
| `rose` | `#F43F5E` | Error / cancel / failed |

Glows are the accent at low alpha (e.g. cyan filament `box-shadow: 0 0 8–12px var(--cyan)`), never a full glow bloom.

## Radii
| Token | px | Use |
|---|---|---|
| `r-chip` | 6 | Small chips, syntax tags |
| `r-ctrl` | 7–8 | Buttons, inputs, cards (v1 baseline 8 kept) |
| `r-panel` | 10–12 | Cards, dialogs, screen frames |
| `pill` | 999 | Status pills, equation chips |

## Spacing
4 / 6 / 8 / 10 / 12 / 14 / 16 / 20 / 22 / 28 / 40 px scale. Rail = 56px, docks = 250–340px, title bar = 44px, timeline strip = 64px.

## Type scale
UI: **Inter / Segoe UI**. Mono/telemetry: **JetBrains Mono** (stand-in for Cascadia Code — swap in Qt). Math: **KaTeX** (STIX/Cambria-Math look) in the app rendered to pixmaps.

| Token | px / weight | Use |
|---|---|---|
| `display` | 24–26 / 700 | Empty-state headline, cover |
| `h2` | 18 / 600 | Screen titles |
| `title` | 13–15 / 600 | Card / panel titles |
| `body` | 13–14 / 400 | Prose, list text |
| `meta` | 11–12 / 400 | Secondary meta |
| `mono` | 10–12 / 500 | Telemetry, elapsed, counts (JetBrains Mono) |
| `micro` | 9.5–10 / 500 | Uppercase mono labels, tick captions |

## Math type scale (NEW)
| Token | px | Use |
|---|---|---|
| `math-hero` | 40 | Hero equation banner (derivation lead) |
| `math-step` | 22–26 | Display fragments inside steps |
| `math-inline` | 15 | Inline math in body (one shade brighter than prose: `tx` on `tx-2`) |
| `math-chip` | 13 | Equation chips, parameter symbols |
| `math-watermark` | 34–56 @ ≤6% opacity | Ambient background formulas (Maxwell / Schrödinger / Euler–Lagrange) |

Ambient watermark rule: decorative only, ≤6% opacity, never behind reading text, always behind a dot/blueprint grid, never overlapping a control.
