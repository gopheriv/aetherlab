"""Regression tests for the shared Manim render-profile (Agent 1).

Covers: preset defaults, precedence (arg > env > settings > preset),
explicit --fps/--resolution (never Manim's silent 15 fps at -ql), loud
adaptive fallbacks (never silent; cinematic never downgrades), invalid-input
clamping, cache identity keys, and assembly-canvas preservation.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from aetherlab.core.render_profile import (
    PRESETS,
    RenderProfile,
    adapt_profile_for_cost,
    describe_fallback,
    get_effective_profile,
    profile_for_quality,
    tier_compat,
)

_PROFILE_ENV_VARS = (
    "AETHERLAB_RENDER_PRESET",
    "AETHERLAB_RENDER_TIER",
    "RENDER_TIER",
    "AETHERLAB_MANIM_RENDERER",
    "AETHERLAB_MANIM_FPS",
    "MANIM_FPS",
    "AETHERLAB_RENDER_WIDTH",
    "AETHERLAB_RENDER_HEIGHT",
    "AETHERLAB_MANIM_QUALITY",
    "MANIM_QUALITY",
    "AETHERLAB_ADAPTIVE_QUALITY",
    "AETHERLAB_RENDER_ADAPTIVE",
    "AETHERLAB_LOCAL_RENDER_LIMIT",
)


@pytest.fixture(autouse=True)
def _clean_profile_env(monkeypatch):
    for name in _PROFILE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


# ── presets ────────────────────────────────────────────────────────────────


def test_presets_cover_preview_standard_cinematic():
    assert set(PRESETS) == {"preview", "standard", "cinematic", "unt", "unt_vertical"}
    assert (PRESETS["preview"].width, PRESETS["preview"].height,
            PRESETS["preview"].fps, PRESETS["preview"].quality) == (854, 480, 30, "l")
    assert (PRESETS["standard"].width, PRESETS["standard"].height,
            PRESETS["standard"].fps, PRESETS["standard"].quality) == (1280, 720, 30, "m")
    assert (PRESETS["cinematic"].width, PRESETS["cinematic"].height,
            PRESETS["cinematic"].fps, PRESETS["cinematic"].quality) == (1920, 1080, 60, "h")
    assert (PRESETS["unt"].width, PRESETS["unt"].height,
            PRESETS["unt"].fps, PRESETS["unt"].quality) == (1920, 1080, 30, "h")
    assert (PRESETS["unt_vertical"].width, PRESETS["unt_vertical"].height,
            PRESETS["unt_vertical"].fps, PRESETS["unt_vertical"].quality) == (1080, 1920, 30, "h")


def test_cinematic_is_non_adaptive_by_default():
    assert PRESETS["cinematic"].adaptive is False
    assert PRESETS["preview"].adaptive is True
    assert PRESETS["standard"].adaptive is True


def test_unt_presets_are_non_adaptive_by_default():
    assert PRESETS["unt"].adaptive is False
    assert PRESETS["unt_vertical"].adaptive is False


def test_default_profile_is_standard_without_settings():
    profile = get_effective_profile(None)
    assert (profile.preset, profile.width, profile.height, profile.fps,
            profile.quality, profile.renderer) == ("standard", 1280, 720, 30, "m", "cairo")


def test_missing_new_settings_fields_fall_back_gracefully():
    profile = get_effective_profile(object())  # old saved settings, no render_* attrs
    assert profile.preset == "standard"
    assert profile.fps == 30


# ── precedence: explicit arg > env > settings > preset ──────────────────────


def test_explicit_quality_arg_wins_over_env_and_settings(monkeypatch):
    monkeypatch.setenv("AETHERLAB_MANIM_QUALITY", "l")
    settings = SimpleNamespace(render_quality="m")
    assert get_effective_profile(settings, quality="h").quality == "h"


def test_env_preset_wins_over_settings():
    settings = SimpleNamespace(render_preset="preview")
    os.environ["AETHERLAB_RENDER_PRESET"] = "cinematic"
    try:
        profile = get_effective_profile(settings)
    finally:
        del os.environ["AETHERLAB_RENDER_PRESET"]
    assert profile.preset == "cinematic"
    assert (profile.width, profile.height, profile.fps) == (1920, 1080, 60)


def test_legacy_tier_names_map_onto_presets(monkeypatch):
    assert get_effective_profile(None, preset="").preset == "standard"
    monkeypatch.setenv("AETHERLAB_RENDER_TIER", "cloud_cinematic")
    assert get_effective_profile(None).preset == "cinematic"
    monkeypatch.setenv("AETHERLAB_RENDER_TIER", "draft")
    assert get_effective_profile(None).preset == "preview"


def test_settings_preset_used_when_no_env():
    profile = get_effective_profile(SimpleNamespace(render_preset="cinematic"))
    assert profile.preset == "cinematic"


def test_env_fps_overrides_settings_and_preset(monkeypatch):
    monkeypatch.setenv("AETHERLAB_MANIM_FPS", "24")
    profile = get_effective_profile(SimpleNamespace(render_fps=60), preset="cinematic")
    assert profile.fps == 24


def test_settings_fps_overrides_preset():
    profile = get_effective_profile(SimpleNamespace(render_fps=50), preset="standard")
    assert profile.fps == 50


def test_env_resolution_overrides_settings(monkeypatch):
    monkeypatch.setenv("AETHERLAB_RENDER_WIDTH", "1920")
    monkeypatch.setenv("AETHERLAB_RENDER_HEIGHT", "1080")
    profile = get_effective_profile(SimpleNamespace(render_width=640, render_height=360))
    assert (profile.width, profile.height) == (1920, 1080)


def test_env_renderer_overrides_settings(monkeypatch):
    monkeypatch.setenv("AETHERLAB_MANIM_RENDERER", "opengl")
    profile = get_effective_profile(SimpleNamespace(render_renderer="cairo"))
    assert profile.renderer == "opengl"


# ── explicit fps/resolution: never Manim's silent defaults ──────────────────


def test_manim_args_always_carry_explicit_fps():
    for preset in ("preview", "standard", "cinematic", "unt", "unt_vertical"):
        args = get_effective_profile(None, preset=preset).manim_args()
        assert "--fps" in args
        assert args[args.index("--fps") + 1] == str(PRESETS[preset].fps)
    # Low quality must NOT inherit Manim's silent 15 fps default.
    assert get_effective_profile(None, preset="preview").manim_args() == ["-ql", "--fps", "30"]
    assert get_effective_profile(None, preset="unt").manim_args() == ["-qh", "--fps", "30"]
    assert get_effective_profile(None, preset="unt_vertical").manim_args() == ["-qh", "--fps", "30"]


def test_low_quality_resolution_is_480p_not_manim_default():
    profile = get_effective_profile(None, preset="preview")
    assert (profile.width, profile.height) == (854, 480)


# ── adaptive fallback: loud, never silent; cinematic never downgrades ───────


def test_adaptive_heavy_hires_scene_downgrades_fps_with_notice():
    profile = RenderProfile(width=1920, height=1080, fps=60, quality="h",
                            preset="standard", adaptive=True)
    effective, notice = adapt_profile_for_cost(profile, 3.5)
    assert effective.fps == 30
    assert notice is not None and "fps 60→30" in notice
    assert notice.startswith("Render fallback:")


def test_non_adaptive_cinematic_never_downgrades():
    effective, notice = adapt_profile_for_cost(PRESETS["cinematic"], 9.9)
    assert effective.fps == 60
    assert notice is None


def test_cheap_or_lowres_scenes_keep_fps():
    profile = RenderProfile(width=1280, height=720, fps=60, quality="m",
                            preset="standard", adaptive=True)
    effective, notice = adapt_profile_for_cost(profile, 5.0)
    assert (effective.fps, notice) == (60, None)
    hires, notice = adapt_profile_for_cost(
        RenderProfile(width=1920, height=1080, fps=60, quality="h",
                      preset="standard", adaptive=True), 1.0)
    assert (hires.fps, notice) == (60, None)


def test_describe_fallback_is_human_readable():
    assert describe_fallback("expensive scene").startswith("Render fallback: expensive scene")


# ── validation: clamp, never raise ──────────────────────────────────────────


def test_validated_clamps_instead_of_raising():
    profile = RenderProfile(width=99999, height=-5, fps=1000,
                            renderer="bogus", preset="bogus", quality="bogus").validated()
    assert (profile.width, profile.height, profile.fps) == (3840, 240, 120)
    assert (profile.renderer, profile.preset, profile.quality) == ("cairo", "standard", "m")


def test_unknown_env_values_fall_back_loudly_without_raising(monkeypatch):
    monkeypatch.setenv("AETHERLAB_RENDER_PRESET", "ultra-mega")
    monkeypatch.setenv("AETHERLAB_MANIM_RENDERER", "vulkan")
    profile = get_effective_profile(None)
    assert (profile.preset, profile.renderer) == ("standard", "cairo")


# ── identity / compat API ───────────────────────────────────────────────────


def test_identity_key_stable_and_preset_sensitive():
    assert PRESETS["standard"].identity_key() == PRESETS["standard"].identity_key()
    assert len(PRESETS["standard"].identity_key()) == 16
    keys = {name: PRESETS[name].identity_key() for name in PRESETS}
    assert len(set(keys.values())) == 5


def test_identity_key_ignores_machine_only_limits():
    from aetherlab.core.render_profile import ResourceLimits

    base = PRESETS["standard"]
    tuned = RenderProfile(
        width=base.width, height=base.height, fps=base.fps, renderer=base.renderer,
        preset=base.preset, adaptive=base.adaptive, quality=base.quality,
        resource_limits=ResourceLimits(max_local_renders=8, below_normal_priority=True,
                                       render_timeout_scale=2.0),
    )
    assert tuned.identity_key() == base.identity_key()


def test_tier_compat_shape():
    assert tier_compat(PRESETS["cinematic"]) == {"name": "cinematic", "fps": 60, "below_normal": False}


def test_runtime_tier_refreshes_and_preserves_legacy_constrained_limits(monkeypatch):
    from aetherlab.services.manim_runtime import get_render_tier

    for name in _PROFILE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    initial = get_render_tier()
    assert (initial["name"], initial["fps"]) == ("standard", 30)
    monkeypatch.setenv("RENDER_TIER", "constrained")
    monkeypatch.setenv("MANIM_FPS", "24")
    constrained = get_render_tier()
    assert constrained == {"name": "standard", "fps": 24, "below_normal": True}
    # A preset overrides the legacy look; constrained scheduling stays intact.
    monkeypatch.setenv("AETHERLAB_RENDER_PRESET", "cinematic")
    monkeypatch.delenv("MANIM_FPS")
    assert get_render_tier() == {"name": "cinematic", "fps": 60, "below_normal": True}
    monkeypatch.setenv("AETHERLAB_MANIM_FPS", "48")
    assert get_render_tier()["fps"] == 48
    # Calls resolve fresh dictionaries without changing previously returned data.
    assert (initial["name"], initial["fps"]) == ("standard", 30)
    assert constrained == {"name": "standard", "fps": 24, "below_normal": True}


def test_runtime_hardware_changes_priority_without_raising_quality(monkeypatch):
    import psutil

    from aetherlab.services.manim_runtime import get_render_tier

    for name in _PROFILE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(total=8 * 1024**3))
    assert get_render_tier() == {"name": "standard", "fps": 30, "below_normal": True}
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(total=32 * 1024**3))
    assert get_render_tier() == {"name": "standard", "fps": 30, "below_normal": False}


def test_profile_for_quality_pins_flag():
    assert profile_for_quality("h").quality == "h"
    assert profile_for_quality("l", SimpleNamespace(render_preset="cinematic")).quality == "l"


def test_canvas_filter_normalizes_to_profile():
    filt = PRESETS["cinematic"].canvas_filter()
    assert "scale=1920:1080" in filt and "fps=60" in filt and "format=yuv420p" in filt


# ── UNT presets ─────────────────────────────────────────────────────────────


def test_unt_preset_resolves_1080p30():
    profile = get_effective_profile(None, preset="unt")
    assert (profile.preset, profile.width, profile.height, profile.fps,
            profile.quality, profile.renderer) == ("unt", 1920, 1080, 30, "h", "cairo")
    assert profile.adaptive is False


def test_unt_vertical_bypasses_quality_dims():
    # Manim -q flags are landscape-only; portrait must keep 1080x1920
    # instead of QUALITY_DIMS["h"] (1920x1080).
    profile = get_effective_profile(None, preset="unt_vertical")
    assert (profile.width, profile.height, profile.fps) == (1080, 1920, 30)
    assert "preset:unt_vertical" in profile.source
    assert profile.manim_args() == ["-qh", "--fps", "30"]


def test_env_preset_unt_and_ent_mapping(monkeypatch):
    monkeypatch.setenv("AETHERLAB_RENDER_PRESET", "unt")
    assert get_effective_profile(None).preset == "unt"
    monkeypatch.setenv("AETHERLAB_RENDER_PRESET", "unt_vertical")
    profile = get_effective_profile(None)
    assert (profile.preset, profile.width, profile.height) == ("unt_vertical", 1080, 1920)
    monkeypatch.setenv("AETHERLAB_RENDER_PRESET", "ent")
    assert get_effective_profile(None).preset == "unt"


def test_settings_preset_unt_used_when_no_env():
    profile = get_effective_profile(SimpleNamespace(render_preset="unt"))
    assert (profile.preset, profile.width, profile.height, profile.fps) == ("unt", 1920, 1080, 30)
    vertical = get_effective_profile(SimpleNamespace(render_preset="unt_vertical"))
    assert (vertical.width, vertical.height) == (1080, 1920)


def test_unt_presets_never_downgrade():
    effective, notice = adapt_profile_for_cost(PRESETS["unt"], 9.9)
    assert (effective.fps, notice) == (30, None)
    effective, notice = adapt_profile_for_cost(PRESETS["unt_vertical"], 9.9)
    assert (effective.fps, notice) == (30, None)


def test_canvas_filter_unt_vertical():
    filt = PRESETS["unt_vertical"].canvas_filter()
    assert "scale=1080:1920" in filt and "fps=30" in filt


# ── assembly: explicit quality must survive ─────────────────────────────────


def test_assembly_canvas_keeps_explicit_profile_without_chapters():
    from aetherlab.services.assembly import _resolve_canvas

    canvas = _resolve_canvas([], profile=PRESETS["cinematic"])
    assert (canvas.width, canvas.height, canvas.fps) == (1920, 1080, 60)


def test_assembly_canvas_falls_back_loudly_on_invalid_profile():
    from aetherlab.services.assembly import _resolve_canvas

    canvas = _resolve_canvas([], profile=None, settings=object(), quality="bogus")
    assert (canvas.width, canvas.height, canvas.fps) == (1280, 720, 30)
