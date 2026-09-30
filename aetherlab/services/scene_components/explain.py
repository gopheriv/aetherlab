"""Explanation layer for curated scenes: what the viewer is seeing and why.

Human review shaped this layer over four rounds:

* v1 (8/10, "missing more details and explanation"): bare 7-12 s animations.
* v2 (9/10): an intro card (concept, equation, what to watch) and a closing card
  (key numbers, takeaway) around each animation.
* v3 (rated below v2): the same prediction card, captions, crossed-out
  misconception and thumbnail wrapped around *every* topic. The owner preferred
  v2 "cause it uses different approaches and different ideas for each topic".
* v4: the storytelling moves into topic-specific scenarios
  (scene_components/scenarios/), and this layer returns to v2's light cards.

The v3 devices remain available as optional ingredients: an explanation may
supply ``predict``/``answer``, ``misconception``, ``captions`` and
``outro="beside"`` (thumbnail), and each is rendered only when present. Nothing
is applied uniformly.

Every number comes from the scene's own ``params()`` (and, where measured, from
the same numeric solve the animation uses), so the text can never disagree with
the picture. The layer is LaTeX-free (``Text`` only) to keep the curated path's
no-TeX guarantee, and fail-soft: any problem returns the scene unchanged.
"""

from __future__ import annotations

import ast
import logging
import math
import textwrap
from typing import Any, Callable

log = logging.getLogger(__name__)

_WRAP = 54            # characters per line on full-width cards
_WRAP_SIDE = 44       # characters per line in the column beside the thumbnail
_WRAP_CAPTION = 64    # one caption line in the top band
_MAX_WIDTH = 12.4     # frame is ~14.2 units wide
_MAX_HEIGHT = 7.0     # frame is 8 units tall
_MIN_CAPTION_S = 1.8  # shortest readable caption window


def explanation_for(component: str, solver: Any) -> dict[str, Any] | None:
    """Return the explanation for a composed component, or None if unavailable."""
    from aetherlab.services.scene_components import scenarios

    builder = _BUILDERS.get(component)
    if builder is None and component in scenarios.SCENARIOS.values():
        def builder(s: Any) -> dict[str, Any] | None:
            return scenarios.explain(component, s)
    if builder is None:
        return None
    try:
        exp = builder(solver)
    except Exception as exc:  # noqa: BLE001 — explanation is additive, never fatal
        log.info("No explanation for %s (%s)", component, exc)
        return None
    if not exp or not exp.get("heading") or not exp.get("facts"):
        return None
    return exp


def add_explanation(code: str, exp: dict[str, Any] | None, duration_target_s: float = 30.0) -> str:
    """Wrap a composed ``Scene``'s construct() with the explanation beats.

    Returns ``code`` unchanged when there is no explanation, the scene is not a
    plain 2-D ``Scene`` (3-D scenes would need fixed-in-frame text), or the
    source cannot be parsed.
    """
    if not exp:
        return code
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    construct = _construct_of_plain_scene(tree)
    if construct is None or not construct.body:
        return code

    from aetherlab.services.scene_validation import estimate_duration

    facts = [str(f) for f in exp.get("facts", [])][:4]
    component_s = max(0.0, estimate_duration(code).total_seconds)
    captions = _caption_windows(exp, construct, component_s)
    caption_hold = _caption_hold(captions, component_s)
    component_s += caption_hold
    beside = exp.get("outro") == "beside"
    has_predict = bool(exp.get("predict") and exp.get("answer"))
    misconception = exp.get("misconception") if beside else None
    has_beat_a = beside and (has_predict or bool(misconception))

    # Fixed animation time per beat, then bounded holds absorb the remainder so
    # the whole video lands near the requested duration.
    if beside:
        outro_fixed = (
            1.0 + 0.6                                   # shrink to thumbnail, equation
            + ((0.8 + 0.5 + (1.2 + 0.8 if misconception else 0.0)) if has_beat_a else 0.0)
            + 0.8 + 1.1 * len(facts) + 1.0              # beat B
        )
    else:
        outro_fixed = 0.8 + 1.2 + 1.4 * len(facts) + 1.2   # clear, heading, facts, takeaway
    fixed = 1.0 + 0.5 + ((0.8 + 0.5) if has_predict else 0.0) + outro_fixed
    holds = {"intro": 1.8, "predict": 2.5 if has_predict else 0.0,
             "beat_a": 1.8 if has_beat_a else 0.0, "beat_b": 1.8}
    caps = {"intro": 3.0, "predict": 3.5, "beat_a": 3.5, "beat_b": 6.0}
    target = float(duration_target_s) if duration_target_s and duration_target_s > 0 else 30.0
    spare = target - (component_s + fixed + sum(holds.values()))
    for key in ("beat_b", "beat_a", "predict", "intro"):
        if spare <= 0 or not holds[key]:
            continue
        add = min(spare, caps[key] - holds[key])
        holds[key] += add
        spare -= add

    intro = _intro_source(exp, holds["intro"])
    if has_predict:
        intro += _predict_source(exp, holds["predict"])
    intro += _caption_setup_source(captions)
    if beside:
        outro = _outro_source(exp, facts, captions, holds["beat_a"], holds["beat_b"], caption_hold)
    else:
        outro = _card_outro_source(exp, facts, captions, holds["beat_b"], caption_hold)

    lines = code.split("\n")
    first = construct.body[0].lineno - 1          # 0-based index of first statement
    last = construct.end_lineno                     # insert after this 1-based line
    out = lines[:first] + intro + lines[first:last] + outro + lines[last:]
    new_code = "\n".join(out)
    try:
        compile(new_code, "<aetherlab-explained-scene>", "exec")
    except SyntaxError as exc:  # pragma: no cover - defensive
        log.warning("Explanation layer produced invalid code (%s); using the plain scene.", exc)
        return code
    return new_code


# ── timing ─────────────────────────────────────────────────────────────────


def _construct_of_plain_scene(tree: ast.AST) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
        if bases != {"Scene"}:
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "construct":
                return item
    return None


def _schedule(construct: ast.FunctionDef) -> list[tuple[float, float]]:
    """(start, end) of each top-level self.play/self.wait, from literal durations."""
    spans: list[tuple[float, float]] = []
    t = 0.0
    for stmt in construct.body:
        call = stmt.value if isinstance(stmt, ast.Expr) else None
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "self"):
            continue
        duration = 1.0
        if call.func.attr == "play":
            for kw in call.keywords:
                if kw.arg == "run_time" and isinstance(kw.value, ast.Constant):
                    duration = float(kw.value.value)
        elif call.func.attr == "wait":
            if call.args and isinstance(call.args[0], ast.Constant):
                duration = float(call.args[0].value)
        else:
            continue
        spans.append((t, t + duration))
        t += duration
    return spans


def _assigned_names(construct: ast.FunctionDef) -> set[str]:
    names = set()
    for node in ast.walk(construct):
        if isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _caption_windows(
    exp: dict[str, Any], construct: ast.FunctionDef, component_s: float,
) -> list[tuple[str, str | None, float, float]]:
    """Place each caption in time, relative to the start of the component.

    A caption may pin itself to the component's schedule with a third element
    ``(play_index, f0, f1)``: it shows from ``f0`` to ``f1`` play-lengths after
    that play starts (``f1`` may run past the play). That keeps a caption such
    as "close to the star, it whips around fast" on the moment it describes.
    Unpinned captions share the component's key motion equally. Anchors are
    only kept when the component really assigns that name, so a content typo
    can never produce a NameError at render time.
    """
    raw = [c for c in exp.get("captions", []) if c and c[0]]
    spans = _schedule(construct)
    if not raw or not spans:
        return []
    total = max(component_s, spans[-1][1])
    names = _assigned_names(construct)
    pinned: dict[int, tuple[float, float]] = {}
    for i, caption in enumerate(raw):
        if len(caption) > 2 and caption[2] and 0 <= int(caption[2][0]) < len(spans):
            idx, f0, f1 = caption[2]
            a0, b0 = spans[int(idx)]
            pinned[i] = (a0 + f0 * (b0 - a0), a0 + f1 * (b0 - a0))
    free = [i for i in range(len(raw)) if i not in pinned]
    if free:
        start, end = max(spans, key=lambda s: s[1] - s[0])
        if exp.get("caption_window") == "all" or end - start < 4.0:
            start, end = min(1.0, 0.1 * total), total - 0.2
        else:
            start, end = start + 0.2, max(end, total - 0.2)
        count = max(1, min(len(free), int((end - start) // _MIN_CAPTION_S)))
        width = (end - start) / count
        for slot, i in enumerate(free[:count]):
            a = start + slot * width + 0.1
            pinned[i] = (a, a + width - 0.2)
    out = []
    previous_end = -1.0
    for i in sorted(pinned):
        a, b = pinned[i]
        a = max(a, previous_end + 0.15)   # one caption at a time in the band
        if b - a < 1.0:
            continue
        previous_end = b
        anchor = raw[i][1]
        out.append((str(raw[i][0]), anchor if anchor in names else None, round(a, 2), round(b, 2)))
    return out


def _caption_hold(captions: list[tuple[str, str | None, float, float]], component_s: float) -> float:
    """Extra seconds the finished diagram stays up so late captions can be read."""
    if not captions:
        return 0.0
    return round(min(4.0, max(0.0, captions[-1][3] + 0.3 - component_s)), 2)


# ── source generation ──────────────────────────────────────────────────────


def _wrap(text: str, width: int = _WRAP) -> str:
    return "\n".join(textwrap.wrap(" ".join(str(text).split()), width)) or " "


def _fit(name: str, width: float = _MAX_WIDTH, height: float = _MAX_HEIGHT) -> list[str]:
    return [
        f"        if {name}.width > {width}:",
        f"            {name}.scale_to_fit_width({width})",
        f"        if {name}.height > {height}:",
        f"            {name}.scale_to_fit_height({height})",
    ]


def _intro_source(exp: dict[str, Any], wait_s: float) -> list[str]:
    return [
        "        # AetherLab explanation layer: concept, governing equation, what to watch.",
        f"        _intro_head = Text({_wrap(exp['heading'])!r}, font_size=40, weight=BOLD, color=YELLOW)",
        f"        _intro_eq = Text({_wrap(exp.get('equation', ''))!r}, font_size=30, color=WHITE)",
        f"        _intro_watch = Text({_wrap('Watch: ' + exp.get('watch', ''))!r}, font_size=26, color=GREY_B)",
        "        _intro = VGroup(_intro_head, _intro_eq, _intro_watch).arrange(DOWN, buff=0.5)",
        *_fit("_intro"),
        "        self.play(FadeIn(_intro, shift=0.2 * UP), run_time=1.0)",
        f"        self.wait({round(wait_s, 2)})",
        "        self.play(FadeOut(_intro), run_time=0.5)",
        "",
    ]


def _predict_source(exp: dict[str, Any], countdown_s: float) -> list[str]:
    return [
        "        # AetherLab explanation layer: predict before the reveal.",
        "        _pq_head = Text('Predict first', font_size=34, weight=BOLD, color=YELLOW)",
        f"        _pq_text = Text({_wrap(exp['predict'], 50)!r}, font_size=30, color=WHITE)",
        "        _pq_hint = Text('Decide before you watch.', font_size=24, color=GREY_B)",
        "        _pq_bar = Line(3 * LEFT, 3 * RIGHT, color=YELLOW, stroke_width=6)",
        "        _pq_card = VGroup(_pq_head, _pq_text, _pq_hint, _pq_bar).arrange(DOWN, buff=0.45)",
        *_fit("_pq_card"),
        "        self.play(FadeIn(_pq_card, shift=0.2 * UP), run_time=0.8)",
        "        self.play(_pq_bar.animate.scale(0.01, about_edge=LEFT),"
        f" run_time={round(countdown_s, 2)}, rate_func=linear)",
        "        self.play(FadeOut(_pq_card), run_time=0.5)",
        "",
    ]


def _caption_setup_source(captions: list[tuple[str, str | None, float, float]]) -> list[str]:
    if not captions:
        return []
    band_a, band_b = captions[0][2], captions[-1][3]
    lines = [
        "        # AetherLab explanation layer: timed captions during the animation, with a",
        "        # highlight ring and pointer on the object each caption describes.",
        "        _clock = ValueTracker(0.0)",
        "        _clock.add_updater(lambda m, dt: m.increment_value(dt))",
        "        self.add(_clock)",
        "",
        "        def _cap_alpha(t, a, b):",
        "            return max(0.0, min(1.0, (t - a) / 0.35, (b - t) / 0.35))",
        "",
        "        def _cap_pointer(cap, target, alpha):",
        "            end = target.get_center()",
        "            ring = Circle(radius=0.32, color=YELLOW_A, stroke_width=3).move_to(end)",
        "            ring.set_stroke(opacity=alpha)",
        "            start = cap.get_bottom() + 0.12 * DOWN",
        "            if np.linalg.norm(end - start) < 0.9:",
        "                return VGroup(ring).set_z_index(19)",
        "            line = DashedLine(start, end, buff=0.36, color=YELLOW_A, stroke_width=2)",
        "            line.set_stroke(opacity=0.8 * alpha)",
        "            return VGroup(line, ring).set_z_index(19)",
        "",
        "        def _cap_point_update(m, cap, target_fn, a, b):",
        "            # The target is looked up lazily: it is only created by the",
        "            # animation below, after this setup code has run.",
        "            alpha = _cap_alpha(_clock.get_value(), a, b)",
        "            if alpha <= 0:",
        "                m.set_stroke(opacity=0)",
        "                return",
        "            try:",
        "                target = target_fn()",
        "            except NameError:",
        "                return",
        "            # Refresh the target first; otherwise the ring trails a moving",
        "            # object by one frame (this updater can run before the target's).",
        "            target.update(0)",
        "            m.become(_cap_pointer(cap, target, alpha))",
        "",
        "        _cap_band = Rectangle(width=14.6, height=1.0, stroke_width=0, fill_color=BLACK,"
        " fill_opacity=0.0).to_edge(UP, buff=0).set_z_index(20)",
        "        _cap_band.add_updater(lambda m: m.set_fill(BLACK,"
        f" opacity=_cap_alpha(_clock.get_value(), {band_a}, {band_b})))",
        "        self.add(_cap_band)",
        "        _cap_mobs = []",
    ]
    for i, (text, anchor, a, b) in enumerate(captions):
        lines += [
            f"        _cap_{i} = Text({_wrap(text, _WRAP_CAPTION)!r}, font_size=28, color=YELLOW_A)"
            ".move_to(_cap_band).set_z_index(21).set_opacity(0.0)",
            *[ln.replace("        ", "        ", 1) for ln in _fit(f"_cap_{i}", 13.4, 0.9)],
            f"        _cap_{i}.add_updater(lambda m: m.set_opacity(_cap_alpha(_clock.get_value(), {a}, {b})))",
            f"        _cap_mobs.append(_cap_{i})",
        ]
        if anchor:
            lines += [
                f"        _ptr_{i} = VGroup().set_z_index(19)",
                f"        _ptr_{i}.add_updater(lambda m: _cap_point_update(m, _cap_{i}, lambda: {anchor},"
                f" {a}, {b}))",
                f"        _cap_mobs.append(_ptr_{i})",
            ]
    lines += ["        self.add(*_cap_mobs)", ""]
    return lines


def _card_outro_source(
    exp: dict[str, Any],
    facts: list[str],
    captions: list[tuple[str, str | None, float, float]],
    hold_s: float,
    caption_hold: float = 0.0,
) -> list[str]:
    """v2's closing card: clear the stage, then equation, key numbers, takeaway."""
    fact_texts = ", ".join(
        f"Text({_wrap(fact, 70)!r}, font_size=25, color=GREY_A)" for fact in facts
    )
    lines = [""]
    if caption_hold > 0:
        lines += [f"        self.wait({caption_hold})"]
    if captions:
        lines.append("        self.remove(_clock, _cap_band, *_cap_mobs)")
    lines += [
        "        # AetherLab explanation layer: clear the stage, then explain what it showed.",
        "        for _m in self.mobjects:",
        "            _m.clear_updaters()",
        "        if self.mobjects:",
        "            self.play(FadeOut(*self.mobjects), run_time=0.8)",
        "        _head = Text('What the animation shows', font_size=34, weight=BOLD, color=YELLOW)",
        f"        _eq = Text({_wrap(exp.get('equation', ''), 70)!r}, font_size=28, color=WHITE)",
        f"        _facts = VGroup({fact_texts}).arrange(DOWN, aligned_edge=LEFT, buff=0.3)",
        f"        _key = Text({_wrap(exp.get('takeaway', ''), 70)!r}, font_size=27, color=TEAL_A)",
        "        _key_box = SurroundingRectangle(_key, color=TEAL, buff=0.22, corner_radius=0.12)",
        "        _card = VGroup(_head, _eq, _facts, VGroup(_key, _key_box)).arrange(DOWN, buff=0.42)",
        *_fit("_card"),
        "        self.play(FadeIn(_head, shift=0.2 * DOWN), FadeIn(_eq), run_time=1.2)",
        "        self.play(LaggedStart(*[FadeIn(_f, shift=0.2 * RIGHT) for _f in _facts],"
        f" lag_ratio=0.85), run_time={round(1.4 * len(facts), 2)})",
        "        self.play(FadeIn(_key), Create(_key_box), run_time=1.2)",
        f"        self.wait({round(hold_s, 2)})",
    ]
    return lines


def _outro_source(
    exp: dict[str, Any],
    facts: list[str],
    captions: list[tuple[str, str | None, float, float]],
    hold_a: float,
    hold_b: float,
    caption_hold: float = 0.0,
) -> list[str]:
    lines = [""]
    if caption_hold > 0:
        lines += [
            "        # AetherLab explanation layer: hold the finished diagram for the last captions.",
            f"        self.wait({caption_hold})",
        ]
    lines.append("        # AetherLab explanation layer: keep the animation as a thumbnail and explain beside it.")
    if captions:
        lines.append("        self.remove(_clock, _cap_band, *_cap_mobs)")
    lines += [
        "        for _m in self.mobjects:",
        "            _m.clear_updaters()",
        "        # play() adds animated ValueTrackers to the scene; each is a point at x = its",
        "        # value, which would stretch the stage's bounding box and shrink the thumbnail.",
        "        self.remove(*[_m for _m in self.mobjects if isinstance(_m, ValueTracker)])",
        "        _stage = Group(*self.mobjects)",
        "        if len(_stage) and _stage.width > 0.1:",
        "            _s = min(4.8 / _stage.width, 3.3 / max(_stage.height, 0.1), 1.0)",
        "            self.play(_stage.animate.scale(_s).to_corner(UL, buff=0.45), run_time=1.0)",
        "        _thumb_box = SurroundingRectangle(_stage, color=GREY_B, buff=0.12, stroke_width=1.5,"
        " corner_radius=0.08)",
        f"        _eq = Text({_wrap(exp.get('equation', ''), 34)!r}, font_size=24, color=WHITE)",
        "        _eq_w = max(_thumb_box.width, 3.2)",
        "        if _eq.width > _eq_w:",
        "            _eq.scale_to_fit_width(_eq_w)",
        "        _eq.next_to(_thumb_box, DOWN, buff=0.35).align_to(_thumb_box, LEFT)",
        "        self.play(Create(_thumb_box), FadeIn(_eq), run_time=0.6)",
        "        _left = VGroup(_thumb_box, _eq)",
        "        _side_w = max(4.0, 6.9 - _left.get_right()[0] - 0.55)",
        "",
    ]
    misconception = exp.get("misconception")
    if exp.get("predict") and exp.get("answer") or misconception:
        parts = []
        lines.append("        # Beat A: the prediction's answer, then the misconception confronted.")
        if exp.get("predict") and exp.get("answer"):
            lines += [
                "        _pa_head = Text('The answer', font_size=30, weight=BOLD, color=YELLOW)",
                f"        _pa_text = Text({_wrap(exp['answer'], _WRAP_SIDE)!r}, font_size=24, color=WHITE)",
            ]
            parts += ["_pa_head", "_pa_text"]
        if misconception:
            common, actual = misconception
            lines += [
                "        _mis_head = Text('Common idea', font_size=24, weight=BOLD, color=RED_B)",
                f"        _mis_wrong = Text({_wrap(common, _WRAP_SIDE)!r}, font_size=24, color=RED_A)",
                "        _mis_fix_head = Text('What actually happens', font_size=24, weight=BOLD, color=GREEN_B)",
                f"        _mis_fix = Text({_wrap(actual, _WRAP_SIDE)!r}, font_size=24, color=GREEN_A)",
            ]
            parts += ["_mis_head", "_mis_wrong", "_mis_fix_head", "_mis_fix"]
        lines += [
            f"        _beat_a = VGroup({', '.join(parts)}).arrange(DOWN, aligned_edge=LEFT, buff=0.25)",
            "        if _beat_a.width > _side_w:",
            "            _beat_a.scale_to_fit_width(_side_w)",
            "        if _beat_a.height > 6.6:",
            "            _beat_a.scale_to_fit_height(6.6)",
            "        _beat_a.next_to(_left, RIGHT, buff=0.55).align_to(_thumb_box, UP)",
        ]
        if misconception:
            lines += [
                "        _first = VGroup(" + ", ".join(parts[:-2]) + ")",
                "        self.play(FadeIn(_first, shift=0.2 * LEFT), run_time=0.8)",
                "        self.wait(1.2)",
                "        _cross = Cross(_mis_wrong, stroke_color=RED, stroke_width=4)",
                "        self.play(Create(_cross), FadeIn(_mis_fix_head), FadeIn(_mis_fix), run_time=0.8)",
                f"        self.wait({round(hold_a, 2)})",
                "        self.play(FadeOut(_beat_a), FadeOut(_cross), run_time=0.5)",
            ]
        else:
            lines += [
                "        self.play(FadeIn(_beat_a, shift=0.2 * LEFT), run_time=0.8)",
                f"        self.wait({round(hold_a, 2)})",
                "        self.play(FadeOut(_beat_a), run_time=0.5)",
            ]
        lines.append("")

    fact_texts = ", ".join(
        f"Text({_wrap(fact, _WRAP_SIDE)!r}, font_size=23, color=GREY_A)" for fact in facts
    )
    lines += [
        "        # Beat B: the key numbers and the takeaway, beside the thumbnail.",
        "        _head = Text('What the animation shows', font_size=30, weight=BOLD, color=YELLOW)",
        f"        _facts = VGroup({fact_texts}).arrange(DOWN, aligned_edge=LEFT, buff=0.26)",
        f"        _key = Text({_wrap(exp.get('takeaway', ''), _WRAP_SIDE)!r}, font_size=24, color=TEAL_A)",
        "        _key_box = SurroundingRectangle(_key, color=TEAL, buff=0.2, corner_radius=0.12)",
        "        _beat_b = VGroup(_head, _facts, VGroup(_key, _key_box)).arrange("
        "DOWN, aligned_edge=LEFT, buff=0.34)",
        "        if _beat_b.width > _side_w:",
        "            _beat_b.scale_to_fit_width(_side_w)",
        "        if _beat_b.height > 6.6:",
        "            _beat_b.scale_to_fit_height(6.6)",
        "        _beat_b.next_to(_left, RIGHT, buff=0.55).align_to(_thumb_box, UP)",
        "        self.play(FadeIn(_head, shift=0.2 * DOWN), run_time=0.8)",
        "        self.play(LaggedStart(*[FadeIn(_f, shift=0.2 * RIGHT) for _f in _facts],"
        f" lag_ratio=0.85), run_time={round(1.1 * len(facts), 2)})",
        "        self.play(FadeIn(_key), Create(_key_box), run_time=1.0)",
        f"        self.wait({round(hold_b, 2)})",
    ]
    return lines


# ── per-component physics content ──────────────────────────────────────────


def _pendulum(solver: Any) -> dict[str, Any]:
    from aetherlab.services.numeric import solve_numeric
    from aetherlab.services.scene_components import pendulum

    p = pendulum.params(solver)
    g, length, theta0 = p["gravity"], p["length"], p["theta0"]
    t_small = 2.0 * math.pi * math.sqrt(length / g)
    facts = [
        f"Released from {math.degrees(abs(theta0)):.0f} degrees, with L = {length:.2f} m and g = {g:.2f} m/s²",
        f"Small-angle formula: T = 2π·√(L/g) = {t_small:.2f} s",
    ]
    sol = solve_numeric(
        pendulum.numeric_spec(theta0),
        {"gravity": g, "length": length, "damping": p["damping"]},
        max_points=2000,
    )
    ts, ths = (list(sol.t), list(sol.series("theta"))) if sol.ok else ([], [])
    # The first swing is the one released at theta0; later swings are smaller
    # because damping bleeds energy, so averaging them would understate it.
    measured = _first_period(ts, ths)
    if measured is not None:
        facts.append(f"First swing measured from this simulation: {measured:.2f} s")
        slower = measured > t_small * 1.02
    else:
        slower = abs(theta0) > 0.35
    if ths and p["damping"] > 0:
        tail = ths[-max(2, len(ths) // 6):]
        end_deg = math.degrees(max(abs(v) for v in tail))
        if end_deg < 0.9 * math.degrees(abs(theta0)):
            facts.append(
                f"Friction shrinks the swing to about {end_deg:.0f} degrees by t = {ts[-1]:.0f} s"
            )
    takeaway = (
        "The period depends on L and g, not on the mass. "
        + ("Wide swings take longer than the small-angle formula predicts."
           if slower else "At small angles the simple formula is accurate.")
    )
    return {
        "heading": "The pendulum and its period",
        "equation": "θ'' = -(g/L)·sin θ - 2γ·θ'",
        "watch": "the bob swings on the left while its angle θ(t) is drawn on the right.",
        "facts": facts,
        "takeaway": takeaway,
    }


def _first_period(ts: list[float], ys: list[float]) -> float | None:
    """Period of the first full swing: time from the 1st to the 3rd zero crossing."""
    crossings = []
    for i in range(1, len(ys)):
        if (ys[i - 1] < 0.0) != (ys[i] < 0.0) and ys[i] != ys[i - 1]:
            frac = -ys[i - 1] / (ys[i] - ys[i - 1])
            crossings.append(ts[i - 1] + frac * (ts[i] - ts[i - 1]))
            if len(crossings) == 3:
                return crossings[2] - crossings[0]
    return None


def _orbit(solver: Any) -> dict[str, Any]:
    from aetherlab.services.scene_components import orbit

    e = orbit.params(solver)["eccentricity"]
    ratio = (1.0 + e) / (1.0 - e)
    return {
        "heading": "Kepler's second law: equal areas in equal times",
        "equation": "dA/dt = L / (2m) = constant",
        "watch": "the line from the star to the planet, and the two shaded sectors.",
        "facts": [
            f"Orbit eccentricity e = {e:.2f}",
            f"Farthest point is (1+e)/(1-e) = {ratio:.1f}× farther than the closest",
            f"So the planet moves {ratio:.1f}× faster at its closest point",
        ],
        "takeaway": (
            "Angular momentum is conserved, so the planet speeds up near the star "
            "and slows down far from it. Equal time, equal area."
        ),
        "answer": (
            f"At the closest point, where it moves {ratio:.1f}× faster than at the "
            "farthest point."
        ),
    }


def _standing_wave(solver: Any) -> dict[str, Any]:
    from aetherlab.services.scene_components import standing_wave

    n = standing_wave.params(solver)["mode"]
    return {
        "heading": f"Standing wave: normal mode n = {n}",
        "equation": "y(x,t) = 2A·sin(nπx/L)·cos(ωt)",
        "watch": "the nodes stay still while the string breathes between the dashed envelopes.",
        "facts": [
            f"Mode n = {n}: {n + 1} nodes (including the fixed ends) and {n} antinodes",
            f"Wavelength λ = 2L/n = {2.0 / n:.2f}·L",
            f"Frequency f = n·f₁ = {n}·f₁",
        ],
        "takeaway": (
            "Two equal waves travelling in opposite directions add up to a standing "
            "wave. Only whole numbers of half-wavelengths fit: L = n·λ/2."
        ),
    }


def _coupled(solver: Any) -> dict[str, Any]:
    from aetherlab.services.scene_components import coupled_oscillators

    p = coupled_oscillators.params(solver)
    w1 = math.sqrt(p["stiffness"] / p["mass"])
    w2 = math.sqrt(3.0 * p["stiffness"] / p["mass"])
    transfer = math.pi / (w2 - w1)
    return {
        "heading": "Two coupled oscillators exchange energy",
        "equation": "m·x₁'' = -2k·x₁ + k·x₂,   m·x₂'' = k·x₁ - 2k·x₂",
        "watch": "only the left mass starts moving; its motion drains into the right mass and back.",
        "facts": [
            f"In-phase mode: ω₁ = √(k/m) = {w1:.2f} rad/s",
            f"Opposite-phase mode: ω₂ = √(3k/m) = {w2:.2f} rad/s",
            f"Energy moves fully to the second mass after π/(ω₂-ω₁) = {transfer:.1f} s",
        ],
        "takeaway": (
            "Starting one mass excites both normal modes at once. "
            "Their beating passes the energy back and forth."
        ),
        "answer": (
            f"Yes. After about {transfer:.1f} s the right mass has taken nearly all "
            "of the energy, and then it flows back."
        ),
    }


def _double_slit(solver: Any) -> dict[str, Any]:
    return {
        "heading": "Double-slit interference",
        "equation": "I(θ) ∝ cos²(π·d·sin θ / λ)",
        "watch": "waves spread from both slits and build the bright and dark bands on the screen.",
        "facts": [
            "Bright bands where the path difference d·sin θ = m·λ",
            "Dark bands where it is (m + ½)·λ: crest meets trough",
            "Band spacing Δy = λL/d: closer slits or longer λ spread the bands",
        ],
        "takeaway": (
            "Waves from the two slits add where crests meet and cancel where crest meets "
            "trough. The band pattern is the signature of wave behaviour."
        ),
    }


def _field_lines(solver: Any) -> dict[str, Any]:
    return {
        "heading": "Electric field of a dipole",
        "equation": "E = Σ k·q / r²   (vector sum over both charges)",
        "watch": "a marker traces one field line from + to -.",
        "facts": [
            "Field lines start on the positive charge and end on the negative",
            "Lines never cross: the field has one direction at every point",
            "Lines crowd together where the field is strongest, near the charges",
        ],
        "takeaway": "A dipole's field is the vector sum of two point-charge fields.",
    }


def _fourier(solver: Any) -> dict[str, Any]:
    from aetherlab.services.scene_components import fourier_epicycles

    harmonics = fourier_epicycles.params(solver)["harmonics"]
    return {
        "heading": "Building a square wave from sine waves",
        "equation": "f(x) = (4/π)·Σ sin(n·x)/n,   n = 1, 3, 5, ...",
        "watch": "each rotating circle is one harmonic; the tip of the chain draws the wave.",
        "facts": [
            f"{len(harmonics)} odd harmonics are used: n = {', '.join(str(h) for h in harmonics)}",
            "Circle n has radius 4/(π·n): higher harmonics add finer detail",
            "Near the jumps the sum overshoots by about 9% (the Gibbs phenomenon)",
        ],
        "takeaway": (
            "Enough rotating circles can draw any repeating shape. "
            "A square wave needs only the odd harmonics."
        ),
    }


def _quantum(solver: Any) -> dict[str, Any]:
    return {
        "heading": "A quantum wavepacket in a harmonic well",
        "equation": "iħ·∂ψ/∂t = -(ħ²/2m)·∂²ψ/∂x² + ½·m·ω²·x²·ψ",
        "watch": "the shaded packet |ψ|² slides back and forth inside the parabola.",
        "facts": [
            "|ψ(x,t)|² is the probability density of finding the particle at x",
            "The packet oscillates at the classical frequency ω = √(k/m)",
            "Energy levels are evenly spaced: E = (n + ½)·ħω",
        ],
        "takeaway": (
            "In a harmonic well a coherent wavepacket moves like a classical particle "
            "and keeps its shape."
        ),
    }


def _kinetic(solver: Any) -> dict[str, Any]:
    from aetherlab.services.scene_components import kinetic_theory

    p = kinetic_theory.params(solver)
    facts = [
        f"{p['particles']} particles bounce elastically off the walls",
        "Temperature sets the typical speed: rms speed = √(3kT/m)",
        "Pressure is the push of countless wall collisions",
    ]
    if p.get("temperature"):
        facts[1] = (
            f"At T = {p['temperature']:.0f} K particles move "
            f"√(T/300 K) = {math.sqrt(p['temperature'] / 300.0):.2f}× as fast as at 300 K"
        )
    return {
        "heading": "Kinetic theory of an ideal gas",
        "equation": "P·V = N·k·T   (k: Boltzmann constant)",
        "watch": "the particles in the box, and the speed distribution curve beside them.",
        "facts": facts,
        "takeaway": (
            "Temperature is the average kinetic energy of the molecules. "
            "Pressure is their collisions with the walls."
        ),
    }


def _image_facts(p: dict[str, float]) -> tuple[list[str], str]:
    m = -p["di"] / p["do"]
    size = "enlarged" if abs(m) > 1.02 else "reduced" if abs(m) < 0.98 else "same size"
    kind = "real and inverted" if m < 0 else "virtual and upright"
    facts = [
        f"Focal length f = {p['f']:.2f}, object distance u = {p['do']:.2f}  →  image distance v = {p['di']:.2f}",
        f"Magnification m = -v/u = {m:.2f}",
        f"The image is {kind}, {size}",
    ]
    return facts, kind


def _lens(solver: Any) -> dict[str, Any]:
    from aetherlab.services.scene_components import lens

    facts, _ = _image_facts(lens.params(solver))
    return {
        "heading": "Image formation by a converging lens",
        "equation": "1/f = 1/u + 1/v",
        "watch": "the principal rays bend at the lens and meet again where the image forms.",
        "facts": facts,
        "takeaway": "Two principal rays are enough to find the image, and the lens equation agrees.",
    }


def _mirror(solver: Any) -> dict[str, Any]:
    from aetherlab.services.scene_components import mirror

    facts, _ = _image_facts(mirror.params(solver))
    return {
        "heading": "Image formation by a concave mirror",
        "equation": "1/f = 1/u + 1/v,   f = R/2",
        "watch": "rays reflect off the mirror and cross where the image forms.",
        "facts": facts,
        "takeaway": (
            "An object beyond the centre of curvature gives a real, inverted, "
            "smaller image. The mirror equation predicts where."
        ),
    }


def _double_pendulum(solver: Any) -> dict[str, Any]:
    from aetherlab.services.numeric import solve_numeric
    from aetherlab.services.scene_components import double_pendulum

    p = double_pendulum.params(solver)
    values = {"g": p["g"], "m1": p["m1"], "m2": p["m2"], "L1": p["L1"], "L2": p["L2"]}
    base_spec = double_pendulum.numeric_spec()
    start = base_spec["initial"]
    base = solve_numeric(base_spec, values, max_points=600)
    nudged = solve_numeric(
        double_pendulum.numeric_spec([start[0] + 1e-3, *start[1:]]), values, max_points=600
    )
    facts = [
        f"Released from θ₁ = {math.degrees(start[0]):.0f}° and θ₂ = {math.degrees(start[1]):.0f}°",
        "No friction: total energy is conserved, yet the motion never repeats",
    ]
    split = None
    if base.ok and nudged.ok:
        split = next(
            (t for t, a, b in zip(base.t, base.series("th1"), nudged.series("th1"))
             if abs(a - b) > 0.5),
            None,
        )
        if split is not None:
            facts.append(
                f"A 0.001 rad change in the start separates the paths by t ≈ {split:.1f} s"
            )
    return {
        "heading": "The double pendulum: deterministic chaos",
        "equation": "Two coupled nonlinear equations for θ₁ and θ₂",
        "watch": "the lower arm whips unpredictably while the upper one swings.",
        "facts": facts,
        "takeaway": (
            "Exact equations, unpredictable outcome: tiny differences in the start "
            "grow until the future cannot be forecast. That is chaos."
        ),
        "answer": (
            f"Only for about {split:.1f} s. A 0.001 rad difference then grows until "
            "the two motions have nothing in common."
            if split is not None else
            "They stay close during this short run, but the tiny difference keeps growing."
        ),
    }


def _ode_summary(solver: Any) -> tuple[list[str], dict[str, Any]] | None:
    spec = getattr(solver, "numeric_spec", None)
    if not isinstance(spec, dict):
        return None
    state = [str(s) for s in spec.get("state", [])]
    rhs = [str(r) for r in spec.get("rhs", [])]
    if not state or len(state) != len(rhs):
        return None
    lines = [f"{s}' = {r}" for s, r in zip(state, rhs)][:3]
    return lines, spec


def _param_fact(solver: Any) -> str | None:
    variables = dict(getattr(solver, "variables", {}) or {})
    shown = [f"{k} = {float(v):g}" for k, v in list(variables.items())[:4]
             if isinstance(v, (int, float)) and math.isfinite(float(v))]
    return "Parameters: " + ",  ".join(shown) if shown else None


def _trajectory(solver: Any) -> dict[str, Any] | None:
    from aetherlab.services.numeric import solve_numeric

    summary = _ode_summary(solver)
    if summary is None:
        return None
    lines, spec = summary
    sol = solve_numeric(spec, getattr(solver, "variables", {}), max_points=400)
    if not sol.ok:
        return None
    ys = list(sol.series())
    name = sol.observe or "x"
    facts = [
        f"{name} starts at {ys[0]:.3g} and ends at {ys[-1]:.3g} after t = {sol.t[-1]:.3g}",
        f"Largest |{name}| reached: {max(abs(v) for v in ys):.3g}",
    ]
    param = _param_fact(solver)
    if param:
        facts.append(param)
    quarter = max(1, len(ys) // 4)
    early = max(abs(v) for v in ys[:quarter])
    late = max(abs(v) for v in ys[-quarter:])
    if early > 1e-12 and late < 0.6 * early:
        answer = f"It settles down: the size of {name} shrinks from {early:.3g} to {late:.3g}."
    elif early > 1e-12 and late > 1.6 * early:
        answer = f"It grows: the size of {name} rises from {early:.3g} to {late:.3g}."
    else:
        answer = f"It keeps going at about the same size (from {early:.3g} to {late:.3g})."
    return {
        "answer": answer,
        "heading": "Numerical solution of the model",
        "equation": "   ".join(lines),
        "watch": f"the tracer draws {name}(t) as time advances left to right.",
        "facts": facts,
        "takeaway": (
            "Every point on the curve comes from integrating the equations above "
            "numerically, not from a sketch."
        ),
    }


def _phase_portrait(solver: Any) -> dict[str, Any] | None:
    from aetherlab.services.numeric import solve_numeric

    summary = _ode_summary(solver)
    if summary is None:
        return None
    lines, spec = summary
    state = [str(s) for s in spec.get("state", [])]
    if len(state) != 2:
        return None
    sol = solve_numeric(spec, getattr(solver, "variables", {}), max_points=400)
    if not sol.ok:
        return None
    xs, vs = list(sol.series(state[0])), list(sol.series(state[1]))
    r0 = math.hypot(xs[0], vs[0])
    r1 = math.hypot(xs[-1], vs[-1])
    if r0 > 1e-9 and r1 < 0.7 * r0:
        verdict = "It spirals inward toward rest: the system is losing energy."
    elif r0 > 1e-9 and r1 > 1.4 * r0:
        verdict = "It spirals outward: the system is gaining energy (unstable)."
    else:
        verdict = "It closes into a loop: the energy stays (nearly) constant."
    facts = [
        f"Each point is one state ({state[0]}, {state[1]}) of the system",
        f"Distance from the origin goes from {r0:.3g} to {r1:.3g}",
    ]
    param = _param_fact(solver)
    if param:
        facts.append(param)
    return {
        "heading": "The motion as a path in phase space",
        "equation": "   ".join(lines),
        "watch": f"the dot traces {state[1]} against {state[0]} as the state evolves.",
        "facts": facts,
        "takeaway": verdict,
        "answer": verdict,
    }


_BUILDERS: dict[str, Callable[[Any], dict[str, Any] | None]] = {
    "pendulum": _pendulum,
    "orbit": _orbit,
    "standing_wave": _standing_wave,
    "coupled_oscillators": _coupled,
    "double_slit": _double_slit,
    "field_lines": _field_lines,
    "fourier_epicycles": _fourier,
    "quantum": _quantum,
    "kinetic_theory": _kinetic,
    "lens": _lens,
    "mirror": _mirror,
    "double_pendulum": _double_pendulum,
    "trajectory": _trajectory,
    "phase_portrait": _phase_portrait,
}
