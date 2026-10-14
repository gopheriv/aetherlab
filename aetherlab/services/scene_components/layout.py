"""Reusable scene-composition helpers: regions, spacing, lifetimes, choreography.

Generated and curated scenes used to crowd the frame: titles, axes, equations,
and live readouts were each placed "somewhere sensible" in isolation, so the
combination overlapped into mud. This module is the single source of truth for
*where things go* so every component and prompt agrees:

- safe margins + named frame regions (title / diagram / equation / readout),
- measured text bounds, wrapping, spacing, and attached labels,
- predictable placement incl. the 6x6 anchor grid used by storyboards,
- z-order layering constants,
- object lifetimes between beats (enter / hold / exit),
- stable updater / always_redraw placement (position INSIDE the callback),
- reusable choreography snippets (highlight pulse, equation morph chain,
  camera push) so variety comes from composition, not from new physics.

Leaf module: stdlib only. Generated scene code must stay self-contained
(``manim`` + ``numpy`` imports only), so components bake these values and
snippets into their templates as literals — they never import this module at
render time.
"""

from __future__ import annotations

# ── frame geometry ───────────────────────────────────────────────────────────
# Manim's default 16:9 frame is 14.22 x 8.0 scene units. Agent1 owns
# core/render_profile.py; consume it when present, else fall back to these
# canonical dimensions (never a competing config).

_DEFAULT_HALF_W = 7.11
_DEFAULT_HALF_H = 4.0

SAFE_MARGIN = 0.45        # min distance of any mobject edge from the frame edge
MIN_LABEL_HEIGHT = 0.22   # never shrink an individual label below this height
MIN_FONT_SIZE = 30        # Text(font_size=...) floor for readability
MAX_FOCAL = 3             # max focal elements visible at once
MAX_TRACES = 2            # max data traces visible at once

# Z-order layers: scaffolding recedes, physics is brightest, labels float above.
Z_BACKGROUND = -10
Z_SCAFFOLD = -5    # axes, grids, ghosts
Z_PHYSICS = 0      # the hero curves / apparatus
Z_TRAIL = 1        # comet tails, traced paths
Z_LABEL = 5        # attached labels, readouts
Z_CAPTION = 8      # captions, hero annotations
Z_OVERLAY = 10     # boxes, circumscribe flashes


def frame_half_extents() -> tuple[float, float]:
    """(half_width, half_height) from Agent1's RenderProfile when available."""
    try:
        from aetherlab.core.render_profile import get_effective_profile  # type: ignore

        profile = get_effective_profile()
        width = float(getattr(profile, "width", 1280) or 1280)
        height = float(getattr(profile, "height", 720) or 720)
        if width > 0 and height > 0:
            # Manim fixes frame_height=8.0; width follows the canvas aspect.
            half_h = _DEFAULT_HALF_H
            half_w = round(half_h * width / height, 3)
            if half_w > 0:
                return half_w, half_h
    except Exception:  # noqa: BLE001 — profile is optional; canonical fallback
        pass
    return _DEFAULT_HALF_W, _DEFAULT_HALF_H


def safe_rect() -> tuple[float, float, float, float]:
    """(left, right, bottom, top) inside the safe margin."""
    half_w, half_h = frame_half_extents()
    return (
        -half_w + SAFE_MARGIN, half_w - SAFE_MARGIN,
        -half_h + SAFE_MARGIN, half_h - SAFE_MARGIN,
    )


# ── named regions (fractions of the safe rect; y grows upward) ──────────────
# Title strip on top, diagram owning the middle, equation + readout sharing the
# bottom band. Regions are disjoint by construction so content placed in
# distinct regions cannot overlap.

REGIONS: dict[str, tuple[float, float, float, float]] = {
    # name: (x0_frac, x1_frac, y0_frac, y1_frac) within the safe rect
    "title": (0.05, 0.95, 0.82, 1.00),
    "diagram": (0.02, 0.98, 0.18, 0.82),
    "equation": (0.05, 0.62, 0.00, 0.18),
    "readout": (0.65, 0.98, 0.00, 0.18),
    "caption": (0.10, 0.90, 0.00, 0.12),
    "full": (0.00, 1.00, 0.00, 1.00),
}


def region_rect(name: str) -> tuple[float, float, float, float]:
    """Absolute (left, right, bottom, top) bounds of a named region."""
    left, right, bottom, top = safe_rect()
    x0, x1, y0, y1 = REGIONS.get(name, REGIONS["full"])
    width, height = right - left, top - bottom
    return (
        round(left + x0 * width, 3), round(left + x1 * width, 3),
        round(bottom + y0 * height, 3), round(bottom + y0 * height + (y1 - y0) * height, 3),
    )


def region_center(name: str) -> tuple[float, float]:
    """Center point of a named region."""
    left, right, bottom, top = region_rect(name)
    return round((left + right) / 2.0, 3), round((bottom + top) / 2.0, 3)


def anchor_cell_to_point(cell: str) -> tuple[float, float]:
    """Center of a storyboard 6x6 anchor cell (A1-F6, cols L->R, rows T->B)."""
    cell = (cell or "").strip().upper()
    if len(cell) != 2 or cell[0] not in "ABCDEF" or cell[1] not in "123456":
        cell = "C3"
    col, row = ord(cell[0]) - ord("A"), int(cell[1]) - 1
    left, right, bottom, top = safe_rect()
    width, height = right - left, top - bottom
    return (
        round(left + (col + 0.5) * width / 6.0, 3),
        round(top - (row + 0.5) * height / 6.0, 3),
    )


# ── text measurement / wrapping / spacing ────────────────────────────────────

def estimate_text_size(text: str, font_size: float = 30.0, scale: float = 1.0) -> tuple[float, float]:
    """Rough (width, height) in scene units for a Text object.

    Calibrated for Manim's default font at 16:9: cap height ~ font_size/96 * 0.5
    units, average glyph advance ~0.52 * height. Good enough for layout
    budgeting (generous callers add 20%); exact bounds come from the preflight.
    """
    height = max(0.05, float(font_size) / 96.0 * 0.5 * float(scale))
    width = max(0.1, len(text) * height * 0.52)
    return round(width, 3), round(height, 3)


def wrap_text(text: str, max_chars: int = 44) -> list[str]:
    """Greedy word wrap for on-screen labels (short lines stay readable)."""
    words, lines, current = str(text).split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def stack_height(count: int, row_height: float, buff: float = 0.12) -> float:
    """Vertical extent of count rows arranged with buff spacing."""
    if count <= 0:
        return 0.0
    return round(count * row_height + (count - 1) * buff, 3)


def fits_in_region(width: float, height: float, region: str) -> bool:
    """True when a (w, h) box fits inside the named region."""
    left, right, bottom, top = region_rect(region)
    return width <= (right - left) and height <= (top - bottom)


# ── overlap geometry (shared vocabulary for preflight + repair) ──────────────

def overlap_box(a: tuple[float, float, float, float],
                b: tuple[float, float, float, float]) -> tuple[float, float, float, float] | None:
    """Intersection of two (left, right, bottom, top) boxes, or None."""
    left = max(a[0], b[0])
    right = min(a[1], b[1])
    bottom = max(a[2], b[2])
    top = min(a[3], b[3])
    if right - left <= 1e-9 or top - bottom <= 1e-9:
        return None
    return (left, right, bottom, top)


def box_area(box: tuple[float, float, float, float]) -> float:
    """Area of a (left, right, bottom, top) box."""
    return max(0.0, box[1] - box[0]) * max(0.0, box[3] - box[2])


def overlap_ratio(a: tuple[float, float, float, float],
                  b: tuple[float, float, float, float]) -> float:
    """Intersection area over the smaller box area (0 = disjoint, 1 = covered)."""
    hit = overlap_box(a, b)
    if hit is None:
        return 0.0
    smaller = min(box_area(a), box_area(b))
    if smaller <= 1e-12:
        return 0.0
    return round(box_area(hit) / smaller, 4)


def minimal_separation(a: tuple[float, float, float, float],
                       b: tuple[float, float, float, float]) -> tuple[float, float]:
    """Smallest (dx, dy) push that separates box b from box a."""
    hit = overlap_box(a, b)
    if hit is None:
        return (0.0, 0.0)
    push_x = (hit[1] - hit[0]) + 0.15
    push_y = (hit[3] - hit[2]) + 0.15
    center_ax, center_bx = (a[0] + a[1]) / 2.0, (b[0] + b[1]) / 2.0
    center_ay, center_by = (a[2] + a[3]) / 2.0, (b[2] + b[3]) / 2.0
    if push_x <= push_y:
        return (round(push_x if center_bx >= center_ax else -push_x, 3), 0.0)
    return (0.0, round(push_y if center_by >= center_ay else -push_y, 3))


def severity_for(ratio: float, duration_s: float, *, transient: bool = False) -> str:
    """low/medium/high from overlap area ratio + persistence (shared scale)."""
    if transient:
        return "low"
    if ratio >= 0.35 or (ratio >= 0.15 and duration_s >= 1.5):
        return "high"
    if ratio >= 0.12 or duration_s >= 1.0:
        return "medium"
    return "low"


# ── codegen snippets (baked into templates as literals) ──────────────────────
# Generated scenes may only import manim + numpy, so these return source
# chunks — never runtime imports.

def snippet_z_layer(var: str, layer: str = "physics") -> str:
    """Pin a mobject to a composition layer (scaffolding stays behind)."""
    value = {
        "background": Z_BACKGROUND, "scaffold": Z_SCAFFOLD, "physics": Z_PHYSICS,
        "trail": Z_TRAIL, "label": Z_LABEL, "caption": Z_CAPTION, "overlay": Z_OVERLAY,
    }.get(layer, Z_PHYSICS)
    return f"{var}.set_z_index({value})"


def snippet_attached_label(label_var: str, text: str, target_var: str,
                           direction: str = "UP", buff: float = 0.15,
                           font_size: int = 30) -> str:
    """A short label attached to its referent (moves with the layout)."""
    return (
        f"{label_var} = Text({text!r}, font_size={font_size})\n"
        f"{label_var}.next_to({target_var}, {direction}, buff={buff})\n"
        f"{snippet_z_layer(label_var, 'label')}"
    )


def snippet_safe_fit(group_var: str) -> str:
    """Guard a composed group to the safe width, centered."""
    half_w, _ = frame_half_extents()
    width = round(2 * half_w - 2 * SAFE_MARGIN, 2)
    return (
        f"{group_var}.scale_to_fit_width(min({group_var}.width, {width}))\n"
        f"{group_var}.move_to(ORIGIN)"
    )


def snippet_beat_lifetime(group_var: str, enter_s: float = 0.6,
                          hold_s: float = 1.2, exit_s: float = 0.4) -> str:
    """Enter / hold / exit for one beat's focal group (progressive reveal).

    Callers play the entrance, wait the hold, then fade the group so the next
    unrelated beat starts clean — completed content never lingers into the
    next idea.
    """
    return (
        f"self.play(FadeIn({group_var}, shift=UP * 0.2), run_time={enter_s})\n"
        f"self.wait({hold_s})\n"
        f"self.play(FadeOut({group_var}, shift=DOWN * 0.2), run_time={exit_s})"
    )


def snippet_stable_readout(number_var: str, label_var: str, tracker_var: str,
                           direction: str = "RIGHT", buff: float = 0.2) -> str:
    """A live number positioned INSIDE its updater (never jumps to center).

    Uses a placed DecimalNumber + set_value updater (no per-frame rebuild, no
    LaTeX storm, no center jump like naive always_redraw).
    """
    return (
        f"{number_var} = DecimalNumber({tracker_var}.get_value(), num_decimal_places=2)\n"
        f"{number_var}.next_to({label_var}, {direction}, buff={buff})\n"
        f"{snippet_z_layer(number_var, 'label')}\n"
        f"{number_var}.add_updater(lambda m: m.set_value({tracker_var}.get_value()))"
    )


# ── reusable choreography (creativity through composition, not new physics) ──

def snippet_highlight_pulse(target_var: str, color: str = "YELLOW",
                            run_time: float = 0.8) -> str:
    """Coordinated highlight: flash + circumscribe the focal object."""
    return (
        f"self.play(Flash({target_var}, color={color}), "
        f"Circumscribe({target_var}, color={color}), run_time={run_time})"
    )


def snippet_equation_morph_chain(vars: list[str], run_time: float = 1.0) -> str:
    """Morph an equation through its forms so the algebra feels alive.

    ``vars`` names pre-built MathTex/Text objects in morph order; consecutive
    pairs become each other instead of fading out/in.
    """
    if len(vars) < 2:
        return ""
    lines = []
    step = round(run_time / (len(vars) - 1), 2)
    for before, after in zip(vars, vars[1:]):
        lines.append(
            f"self.play(TransformMatchingTex({before}, {after}), run_time={step})"
        )
    return "\n".join(lines)


def snippet_camera_push(focus_var: str, scale: float = 0.6,
                        run_time: float = 1.2) -> str:
    """Purposeful camera push toward the hero object (MovingCameraScene)."""
    return (
        f"self.play(self.camera.frame.animate.scale({scale}).move_to({focus_var}), "
        f"run_time={run_time})"
    )


def snippet_clear_stage(except_vars: list[str] | None = None,
                        run_time: float = 0.5) -> str:
    """Fade completed content between acts (one focal idea per beat)."""
    if except_vars:
        keep = ", ".join(except_vars)
        return (
            f"self.play(*[FadeOut(m) for m in self.mobjects "
            f"if m not in ({keep},)], run_time={run_time})"
        )
    return f"self.play(FadeOut(*self.mobjects), run_time={run_time})"


# ── deterministic fallback de-crowding ───────────────────────────────────────
# The deterministic templates (services/scene_templates.py) predate regions;
# this post-processor applies only safe, verifiable fixes to their source:
# layering (z_index), dim scaffolding, and attached readout labels. It never
# removes physics or shrinks text below the readable floor.

def apply_fallback_layout_fixes(code: str) -> tuple[str, list[str]]:
    """Apply conservative layout fixes to deterministic template code.

    Returns (new_code, fixes). Fixes are narrow, additive, and verified:
    1. progressive reveal for top-style headers — the static derivation-step
       rows fade out as the domain animation starts (title + summary stay),
       so completed intro content never crowds the physics;
    2. dim bare single-line Axes/NumberPlane scaffolding via axis_config
       stroke_opacity so the physics stays brightest.
    The result is compile-checked; on any doubt the code returns unchanged
    with no fixes recorded. Never removes physics or shrinks readable text.
    """
    import ast

    fixes: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, fixes
    lines = code.splitlines(keepends=True)

    def _single_line(node: ast.AST) -> bool:
        return (getattr(node, "end_lineno", node.lineno) == node.lineno
                and 0 <= node.lineno - 1 < len(lines))

    # 1) Progressive reveal: top-style header only (self.add(title, summary,
    # rows)), fading the rows just before the first self.play beat.
    if "self.add(title, summary, rows)" in code:
        first_play = next(
            (node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "play" and isinstance(node.func.value, ast.Name)
             and node.func.value.id == "self"),
            None,
        )
        if first_play is not None and "FadeOut(rows)" not in code:
            indent = " " * 8
            insert_at = first_play.lineno - 1
            snippet = (
                f"{indent}# layout: clear completed intro steps; title+summary stay.\n"
                f"{indent}self.play(FadeOut(rows), run_time=0.5)\n"
            )
            candidate = "".join(lines[:insert_at] + [snippet] + lines[insert_at:])
            try:
                compile(candidate, "<aetherlab-layout-fix>", "exec")
            except SyntaxError:
                pass
            else:
                lines = candidate.splitlines(keepends=True)
                fixes.append("progressive reveal: FadeOut(rows) before first play")
                try:
                    tree = ast.parse(candidate)
                except SyntaxError:
                    return code, []

    # 2) Dim bare single-line Axes/NumberPlane scaffolding.
    dimmed: list[tuple[int, int, bool]] = []  # (line index, insert column, needs comma)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id not in {"Axes", "NumberPlane"}:
            continue
        if any(kw.arg == "axis_config" for kw in node.keywords):
            continue
        if not _single_line(node):
            continue
        end_col = getattr(node, "end_col_offset", 0)
        if end_col and lines[node.lineno - 1][max(0, end_col - 1):end_col] == ")":
            # A bare Axes() takes no leading comma; Axes(...) does.
            dimmed.append((node.lineno - 1, end_col - 1, bool(node.args or node.keywords)))
    new_lines = list(lines)
    for line_index, col, needs_comma in sorted(dimmed, reverse=True):
        line = new_lines[line_index]
        insert = (", " if needs_comma else "") + 'axis_config={"stroke_opacity": 0.35}'
        new_lines[line_index] = line[:col] + insert + line[col:]
    if dimmed:
        candidate = "".join(new_lines)
        try:
            compile(candidate, "<aetherlab-layout-fix>", "exec")
        except SyntaxError:
            # Keep fix 1's verified result; only the dimming is dropped.
            return "".join(lines), fixes
        fixes.append(f"dimmed {len(dimmed)} scaffold axes (stroke_opacity 0.35)")
        return candidate, fixes
    return "".join(lines), fixes
