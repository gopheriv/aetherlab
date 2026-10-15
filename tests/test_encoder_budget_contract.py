"""Local encoder command contract, no process/network or performance claims."""
from aetherlab.services.manim_runtime import _manim_render_command


def test_encoder_budget_handles_absent_invalid_and_integer_boundaries(tmp_path, monkeypatch):
    cases = [(None, "4"), ("", "4"), ("bogus", "4"), ("2.5", "4"),
             ("-2", "1"), ("0", "1"), ("1", "1"), (" 2 ", "2"), ("8", "8"), ("99", "8")]
    for value, expected in cases:
        with monkeypatch.context() as owned:
            if value is None:
                owned.delenv("AETHERLAB_MAX_INFLIGHT_ENCODERS", raising=False)
            else:
                owned.setenv("AETHERLAB_MAX_INFLIGHT_ENCODERS", value)
            command = _manim_render_command(["python", "-m", "manim"], quality="h", fps=60, seed=1,
                media_dir=tmp_path / "media", scene_file=tmp_path / "scene.py", class_name="Owned")
            assert command.count("--max-inflight-encoders") == 1
            assert command[command.index("--max-inflight-encoders") + 1] == expected


def test_encoder_budget_preserves_requested_profile_and_render_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHERLAB_MAX_INFLIGHT_ENCODERS", "2")
    command = _manim_render_command(["python", "-m", "manim"], quality="p", fps=48, seed=7,
        media_dir=tmp_path / "media", scene_file=tmp_path / "scene.py", class_name="Owned",
        width=960, height=540)
    assert "-qp" in command
    assert command[command.index("--fps") + 1] == "48"
    assert command[command.index("-r") + 1] == "960,540"
    assert command[command.index("--media_dir") + 1] == str(tmp_path / "media")
    assert command[-2:] == [str(tmp_path / "scene.py"), "Owned"]
    assert "--disable_caching" in command
