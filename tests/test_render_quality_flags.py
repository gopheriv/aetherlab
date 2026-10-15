"""Tests for the R1 (1440p60 quality flag) and R2 (parallel encoders) upgrades."""
from types import SimpleNamespace

from aetherlab.core.render_profile import (
    QUALITY_DIMS,
    VALID_QUALITY_FLAGS,
    adapt_profile_for_cost,
    get_effective_profile,
)
from aetherlab.services.render_backend import CLOUD_QUALITY_DIMS


def test_p_flag_resolves_to_1440p60():
    assert "p" in VALID_QUALITY_FLAGS
    assert QUALITY_DIMS["p"] == (2560, 1440)
    assert CLOUD_QUALITY_DIMS["p"] == (2560, 1440)
    profile = get_effective_profile(SimpleNamespace(), quality="p")
    assert profile.quality == "p"
    assert (profile.width, profile.height) == (2560, 1440)
    # fps follows the preset (standard → 30), resolution follows the flag.
    assert profile.fps == 30
    assert profile.manim_args() == ["-qp", "--fps", "30"]


def test_p_flag_accepted_from_settings_and_env(monkeypatch):
    profile = get_effective_profile(SimpleNamespace(render_quality="p"))
    assert profile.quality == "p"
    monkeypatch.setenv("AETHERLAB_MANIM_QUALITY", "p")
    profile = get_effective_profile(SimpleNamespace(render_quality="m"))
    assert profile.quality == "p"


def test_p_flag_gets_adaptive_fps_policy():
    from dataclasses import replace

    profile = get_effective_profile(SimpleNamespace(), quality="p")
    assert profile.adaptive  # explicit quality keeps the preset default (adaptive)
    sixty = replace(profile, fps=60)
    downgraded, notice = adapt_profile_for_cost(sixty, 3.5)
    assert downgraded.fps == 30
    assert notice and "fps" in notice


def test_command_passes_inflight_encoders_default_4(tmp_path, monkeypatch):
    from aetherlab.services.manim_runtime import _manim_render_command

    monkeypatch.delenv("AETHERLAB_MAX_INFLIGHT_ENCODERS", raising=False)
    command = _manim_render_command(
        ["python", "-m", "manim"], quality="h", fps=60, seed=1,
        media_dir=tmp_path, scene_file=tmp_path / "s.py", class_name="S",
    )
    assert command[command.index("--max-inflight-encoders") + 1] == "4"


def test_command_inflight_encoders_env_override_and_clamp(tmp_path, monkeypatch):
    from aetherlab.services.manim_runtime import _manim_render_command

    def flag():
        command = _manim_render_command(
            ["python", "-m", "manim"], quality="h", fps=60, seed=1,
            media_dir=tmp_path, scene_file=tmp_path / "s.py", class_name="S",
        )
        return command[command.index("--max-inflight-encoders") + 1]

    monkeypatch.setenv("AETHERLAB_MAX_INFLIGHT_ENCODERS", "1")
    assert flag() == "1"
    monkeypatch.setenv("AETHERLAB_MAX_INFLIGHT_ENCODERS", "99")
    assert flag() == "8"
    monkeypatch.setenv("AETHERLAB_MAX_INFLIGHT_ENCODERS", "bogus")
    assert flag() == "4"
