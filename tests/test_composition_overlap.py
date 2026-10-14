"""Scene composition + runtime overlap detection (layout, allowlist, repair)."""

from __future__ import annotations

from aetherlab.services.scene_components import layout
from aetherlab.services.scene_preflight import (
    PreflightReport,
    overlap_line,
    overlap_score,
    preflight_scene,
    repair_overlap_code,
    repair_overlaps_with_recheck,
    suggest_overlap_repair,
)
from aetherlab.services.scene_validation import check_static_overlaps


# ── layout helpers: regions, measurement, geometry ──────────────────────────

def test_named_regions_are_disjoint_and_inside_the_safe_rect():
    safe = layout.safe_rect()
    rects = {name: layout.region_rect(name) for name in ("title", "diagram", "equation", "readout")}
    for name, (left, right, bottom, top) in rects.items():
        assert safe[0] <= left < right <= safe[1], name
        assert safe[2] <= bottom < top <= safe[3], name
    names = list(rects)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            assert layout.overlap_box(rects[names[i]], rects[names[j]]) is None, (names[i], names[j])


def test_anchor_grid_orders_corners_and_falls_back_safely():
    top_left = layout.anchor_cell_to_point("A1")
    bottom_right = layout.anchor_cell_to_point("F6")
    assert top_left[0] < bottom_right[0] and top_left[1] > bottom_right[1]
    assert layout.anchor_cell_to_point("bogus") == layout.anchor_cell_to_point("C3")


def test_text_budgeting_helpers():
    _, short_h = layout.estimate_text_size("hi", font_size=30)
    wide, tall = layout.estimate_text_size("a much longer label", font_size=60)
    assert tall > short_h and wide > 0.1 and short_h >= 0.05
    lines = layout.wrap_text("one two three four five six", max_chars=9)
    assert len(lines) > 1 and all(len(line) <= 12 for line in lines)
    assert layout.stack_height(3, 0.3, buff=0.1) == 1.1
    assert layout.fits_in_region(0.5, 0.5, "diagram")
    assert not layout.fits_in_region(99.0, 99.0, "readout")


def test_overlap_geometry_and_severity_scale():
    a = (0.0, 2.0, 0.0, 2.0)
    b = (1.0, 3.0, 1.0, 3.0)
    hit = layout.overlap_box(a, b)
    assert hit == (1.0, 2.0, 1.0, 2.0) and layout.box_area(hit) == 1.0
    assert layout.overlap_box(a, (5.0, 6.0, 5.0, 6.0)) is None
    assert layout.overlap_ratio(a, (5.0, 6.0, 5.0, 6.0)) == 0.0
    assert layout.overlap_ratio(a, a) == 1.0
    dx, dy = layout.minimal_separation(a, b)
    moved = (b[0] + dx, b[1] + dx, b[2] + dy, b[3] + dy)
    assert layout.overlap_box(a, moved) is None  # the push actually separates
    assert layout.severity_for(0.5, 0.0) == "high"
    assert layout.severity_for(0.2, 2.0) == "high"
    assert layout.severity_for(0.2, 0.0) == "medium"
    assert layout.severity_for(0.01, 0.0) == "low"
    assert layout.severity_for(0.9, 9.0, transient=True) == "low"


def test_choreography_snippets_stay_layered_and_stable():
    assert "set_z_index(-5)" in layout.snippet_z_layer("axes", "scaffold")
    assert "set_z_index(5)" in layout.snippet_z_layer("tag", "label")
    attached = layout.snippet_attached_label("tag", "peak", "curve", font_size=30)
    assert "next_to(curve" in attached and "font_size=30" in attached and "set_z_index" in attached
    readout = layout.snippet_stable_readout("num", "lbl", "tracker")
    assert readout.index("next_to") < readout.index("add_updater")  # placed, then updated
    assert "set_value" in readout and "always_redraw" not in readout
    lifetime = layout.snippet_beat_lifetime("grp")
    assert "FadeIn(grp" in lifetime and "FadeOut(grp" in lifetime
    chain = layout.snippet_equation_morph_chain(["e1", "e2", "e3"])
    assert chain.count("TransformMatchingTex") == 2
    assert layout.snippet_equation_morph_chain(["only"]) == ""
    assert "camera.frame" in layout.snippet_camera_push("hero")
    assert "FadeOut" in layout.snippet_clear_stage()


def test_fallback_layout_fixes_dim_and_reveal_without_removing_physics():
    code = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        title = Text('t')\n        summary = Text('s')\n"
        "        rows = VGroup(Text('a'), Text('b'))\n"
        "        self.add(title, summary, rows)\n"
        "        axes = Axes()\n"
        "        self.play(Create(axes), run_time=1.0)\n"
        "        self.play(axes.animate.shift(UP), run_time=1.0)\n"
    )
    fixed, fixes = layout.apply_fallback_layout_fixes(code)
    assert fixes and "FadeOut(rows)" in fixed
    assert 'axes = Axes(axis_config={"stroke_opacity": 0.35})' in fixed
    assert "axes.animate.shift(UP)" in fixed  # physics preserved
    compile(fixed, "<test-layout-fix>", "exec")
    with_args = "from manim import *\nclass S(Scene):\n    def construct(self):\n        a = Axes(x_range=[-1, 1])\n"
    fixed_args, fixes_args = layout.apply_fallback_layout_fixes(with_args)
    assert 'Axes(x_range=[-1, 1], axis_config={"stroke_opacity": 0.35})' in fixed_args
    assert fixes_args and fixed_args != with_args
    compile(fixed_args, "<test-layout-fix>", "exec")
    broken, fixes = layout.apply_fallback_layout_fixes("def broken(:\n")
    assert broken == "def broken(:\n" and fixes == []


# ── static crowding advice (advisory only, never a blocker) ─────────────────

_TEXT_PILE = (
    "from manim import *\nclass S(Scene):\n    def construct(self):\n"
    "        a = Text('one')\n        b = Text('two')\n        c = Text('three')\n"
    "        self.play(FadeIn(a), FadeIn(b), FadeIn(c))\n"
)

_POSITIONED = (
    "from manim import *\nclass S(Scene):\n    def construct(self):\n"
    "        a = Text('one').move_to(UP)\n"
    "        b = Text('two').next_to(a, DOWN)\n"
    "        c = Text('three').next_to(b, DOWN)\n"
    "        self.play(FadeIn(a), FadeIn(b), FadeIn(c))\n"
)


def test_static_text_pile_is_advisory_not_blocking():
    warnings = check_static_overlaps(_TEXT_PILE)
    assert warnings and all(w.startswith("[HYGIENE:CROWDING]") for w in warnings)
    assert not any("[HYGIENE:OVERLAP]" in w for w in warnings)
    assert check_static_overlaps(_POSITIONED) == []


def test_static_edge_pile_flags_only_shared_edges():
    shared = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        a = Text('title').to_edge(UP)\n"
        "        b = Text('legend').to_edge(UP)\n"
        "        self.add(a, b)\n"
    )
    split = shared.replace("Text('legend').to_edge(UP)", "Text('legend').to_edge(DOWN)")
    assert any(w.startswith("[HYGIENE:CROWDING]") for w in check_static_overlaps(shared))
    assert check_static_overlaps(split) == []


# ── overlap report API (Agent2 contract) ─────────────────────────────────────

def _finding(**overrides):
    item = {
        "a": "Text#0", "b": "Text#1", "label_a": "Alpha", "label_b": "Beta",
        "time_s": 1.0, "duration_s": 1.5, "bounds_a": [-1, 1, -1, 1],
        "bounds_b": [-1, 1, -1, 1], "overlap": [-1, 1, -1, 1],
        "overlap_ratio": 0.9, "transient": False, "severity": "high",
        "repair": "move Text#1 by (0.00, +2.15)",
    }
    item.update(overrides)
    return item


def test_overlap_score_lines_and_repair_suggestion():
    assert overlap_score([_finding(severity="high"), _finding(severity="medium"),
                          _finding(severity="low")]) == 4.2
    assert overlap_score([]) == 0.0
    line = overlap_line(_finding())
    assert line.startswith("[PREFLIGHT:OVERLAP]") and "Alpha" in line and "move Text#1" in line
    assert overlap_line(_finding(transient=True, severity="low")).startswith("[PREFLIGHT:OVERLAP]")
    assert "move Text#1" in suggest_overlap_repair(_finding())
    assert "sequence them" in suggest_overlap_repair(_finding(repair=""))


def test_preflight_report_keeps_compat_fields_with_overlaps():
    report = PreflightReport(ran=True, ok=True, duration_s=3.0, overlaps=[_finding()])
    assert report.overlap_lines() and report.overlap_lines()[0].startswith("[PREFLIGHT:OVERLAP]")
    assert report.overlap_score == 3.0
    assert report.off_frame == [] and report.events == [] and report.error == ""


# ── deterministic bounded repair ─────────────────────────────────────────────

_PILED_CODE = (
    "from manim import *\nclass S(Scene):\n    def construct(self):\n"
    '        a = Text("A").move_to(ORIGIN)\n'
    '        b = Text("B").move_to(ORIGIN)\n'
    '        c = Text("C").move_to(ORIGIN)\n'
    "        self.play(FadeIn(a), FadeIn(b), FadeIn(c))\n"
)


def test_repair_overlap_code_nudges_piles_with_staggered_shifts():
    fixed, changed = repair_overlap_code(_PILED_CODE, [_finding()])
    assert changed
    assert fixed.count(".shift(DOWN *") == 2  # later occurrences only, staggered
    assert ".shift(DOWN * 1.0)" in fixed and ".shift(DOWN * 2.0)" in fixed
    compile(fixed, "<test-overlap-repair>", "exec")


def test_repair_overlap_code_leaves_clean_code_untouched():
    assert repair_overlap_code(_POSITIONED, [_finding()]) == (_POSITIONED, False)
    assert repair_overlap_code(_PILED_CODE, []) == (_PILED_CODE, False)
    assert repair_overlap_code("def broken(:\n", [_finding()]) == ("def broken(:\n", False)


def test_repair_with_recheck_keeps_only_improvements(monkeypatch):
    import aetherlab.services.scene_preflight as preflight_mod

    calls = []

    def fake_preflight(code, class_name, *args, **kwargs):
        calls.append(code)
        if len(calls) == 1:
            return PreflightReport(ran=True, ok=True, overlaps=[_finding(severity="high")])
        return PreflightReport(ran=True, ok=True, overlaps=[])

    monkeypatch.setattr(preflight_mod, "preflight_scene", fake_preflight)
    best_code, best_report, improved = repair_overlaps_with_recheck(_PILED_CODE, "S")
    assert improved and best_code != _PILED_CODE and best_report.overlap_score == 0.0

    def fake_stuck(code, class_name, *args, **kwargs):
        return PreflightReport(ran=True, ok=True, overlaps=[_finding(severity="high")])

    monkeypatch.setattr(preflight_mod, "preflight_scene", fake_stuck)
    best_code, _report, improved = repair_overlaps_with_recheck(_PILED_CODE, "S")
    assert not improved and best_code == _PILED_CODE


# ── storyboard arc + critic variety (owned companions) ──────────────────────

def test_beat_arc_tags_kinds_and_warns_on_flat_arcs():
    from aetherlab.services.scene_specification import beat_arc_warnings, ensure_beat_arc

    board = {"timeline": [
        {"act": "Hook", "detail": "drop the ball"},
        {"act": "Evolve", "detail": "it swings", "kind": "motion"},
        {"act": "Mystery", "detail": "something", "kind": "nonsense"},
    ]}
    ensure_beat_arc(board)
    kinds = [beat["kind"] for beat in board["timeline"]]
    assert kinds[1] == "motion" and kinds[2] == "demo"  # kept valid, replaced unknown
    assert all(isinstance(kind, str) and kind for kind in kinds)
    flat = {"timeline": [{"act": "Hook", "detail": "x", "kind": "demo"}] * 4}
    warnings = beat_arc_warnings(flat)
    assert any(w.startswith("[ARC:MOTION]") for w in warnings)
    assert any(w.startswith("[ARC:VARIETY]") for w in warnings)


def test_static_critic_proxy_rewards_motion_and_explanation():
    from aetherlab.services.scene_critic import CRITIC_AXES, static_quality_estimate

    lively = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        t = ValueTracker(0.0)\n"
        "        d = Dot().move_to(LEFT * 3)\n"
        "        d.add_updater(lambda m: m.set_x(t.get_value()))\n"
        "        e1 = Text('v = 3').move_to(UP * 2)\n"
        "        e2 = Text('v = 5').move_to(UP * 2)\n"
        "        self.play(FadeIn(d), FadeIn(e1), run_time=3.0)\n"
        "        self.play(t.animate.set_value(3.0), run_time=3.0)\n"
        "        self.play(TransformMatchingTex(e1, e2), run_time=3.0)\n"
        "        self.play(FadeOut(d), FadeOut(e2), run_time=1.0)\n"
    )
    flat = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        a = Text('one')\n        b = Text('two')\n        c = Text('three')\n"
        "        self.play(FadeIn(a), FadeIn(b), FadeIn(c), run_time=1.0)\n"
    )
    lively_est, flat_est = static_quality_estimate(lively), static_quality_estimate(flat)
    for est in (lively_est, flat_est):
        assert est.verdict == "skipped" and est.breakdown_source == "static"
        assert set(est.breakdown) == set(CRITIC_AXES)
    assert lively_est.score > flat_est.score


# ── real dry runs (Manim child process; no LaTeX, seconds each) ─────────────

_CROWDED = '''from manim import *
class S(Scene):
    def construct(self):
        a = Text("Alpha")
        b = Text("Beta")
        c = Text("Gamma")
        self.play(FadeIn(a), FadeIn(b), FadeIn(c), run_time=1.0)
        self.wait(1.5)
'''


def test_preflight_detects_crowded_text_pile_with_diagnostics():
    report = preflight_scene(_CROWDED, "S")
    assert report.ran and report.ok, report.error or report.note
    assert report.overlaps, "three Texts at ORIGIN must be flagged"
    for item in report.overlaps:
        assert item["severity"] in {"high", "medium"}
        assert not item["transient"]
        for key in ("a", "b", "time_s", "duration_s", "overlap", "overlap_ratio",
                    "severity", "repair"):
            assert key in item and item[key] not in ("", None), key
        assert item["repair"].strip()
    lines = report.overlap_lines()
    assert lines and all(line.startswith("[PREFLIGHT:OVERLAP]") for line in lines)
    assert report.overlap_score > 0


_INTENTIONAL = '''from manim import *
class S(Scene):
    def construct(self):
        title = Text("Orbit demo").to_edge(UP)
        box = SurroundingRectangle(title, buff=0.15)
        axes = Axes(x_range=[-3, 3], y_range=[-2, 2]).scale(0.5).move_to(LEFT * 2.5)
        curve = axes.plot(lambda x: x ** 2 / 8.0)
        axes_label = Text("x vs y", font_size=20).next_to(axes, DOWN, buff=0.3)
        dot = Dot().move_to(RIGHT * 2 + DOWN * 2)
        tag = Text("p", font_size=20).next_to(dot, UP, buff=0.15)
        tag.add_updater(lambda m: m.next_to(dot, UP, buff=0.15))
        trail = TracedPath(dot.get_center, stroke_width=2.0)
        sq1 = Square().move_to(RIGHT * 4.5 + UP)
        sq1._aetherlab_allow_overlap = True
        sq2 = Square().move_to(RIGHT * 4.5 + UP)
        sq2._aetherlab_allow_overlap = True
        self.play(FadeIn(title), FadeIn(box), Create(axes), Create(curve),
                  FadeIn(axes_label), FadeIn(dot), FadeIn(tag),
                  FadeIn(sq1), FadeIn(sq2), run_time=1.0)
        self.add(trail)
        self.play(dot.animate.shift(RIGHT), run_time=1.0)
        self.wait(0.5)
'''


def test_preflight_allows_intentional_relations_without_false_positives():
    report = preflight_scene(_INTENTIONAL, "S")
    assert report.ran and report.ok, report.error or report.note
    serious = [item for item in report.overlaps if item.get("severity") in {"high", "medium"}]
    assert serious == [], [overlap_line(item) for item in serious]
    assert not [item for item in report.overlaps if not item.get("transient")]


_SWAP = '''from manim import *
class S(Scene):
    def construct(self):
        a = Dot().move_to(LEFT * 4)
        b = Dot().move_to(RIGHT * 4)
        self.play(FadeIn(a), FadeIn(b), run_time=0.5)
        self.play(a.animate.move_to(RIGHT * 4), b.animate.move_to(LEFT * 4), run_time=2.0)
        self.wait(0.5)
'''


def test_preflight_detects_transient_crossing_during_motion():
    report = preflight_scene(_SWAP, "S")
    assert report.ran and report.ok, report.error or report.note
    transient = [item for item in report.overlaps if item.get("transient")]
    assert transient, "dots swapping sides must register a motion crossing"
    assert all(item["severity"] == "low" for item in transient)


_READOUT = '''from manim import *
class S(Scene):
    def construct(self):
        label = Text("energy", font_size=28).move_to(LEFT * 4 + DOWN * 2.5)
        tracker = ValueTracker(0.0)
        number = DecimalNumber(0.0, num_decimal_places=1).next_to(label, RIGHT, buff=0.2)
        number.add_updater(lambda m: m.set_value(tracker.get_value()))
        self.play(FadeIn(label), FadeIn(number), run_time=0.5)
        self.play(tracker.animate.set_value(5.0), run_time=2.0)
        self.wait(0.5)
'''


def test_preflight_updater_readout_stays_placed_without_overlap():
    report = preflight_scene(_READOUT, "S")
    assert report.ran and report.ok, report.error or report.note
    assert report.off_frame == []
    serious = [item for item in report.overlaps if item.get("severity") in {"high", "medium"}]
    assert serious == [], [overlap_line(item) for item in serious]
