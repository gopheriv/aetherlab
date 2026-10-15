"""Saved profile -> actual backend request/media gate; all clients are owned fakes."""
from __future__ import annotations

import asyncio
import io
import subprocess
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from aetherlab.core.render_profile import RenderProfile, adapt_profile_for_cost, get_effective_profile


@pytest.fixture(autouse=True)
def owned_environment(tmp_path, monkeypatch):
    import os
    for name in tuple(os.environ):
        if name.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "MANIM_", "GPT_", "CHAT_", "LLM_", "DASHSCOPE_")) or name == "RENDER_TIER":
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "0")


def test_saved_cinematic_keeps_nonadaptive_default(tmp_path):
    from aetherlab.core.settings import load_settings, save_app_config
    save_app_config({"render_preset": "cinematic"})
    settings = load_settings()
    profile = get_effective_profile(settings)
    assert profile.preset == "cinematic" and profile.fps == 60
    assert not profile.adaptive
    effective, notice = adapt_profile_for_cost(profile, 4.0)
    assert effective.fps == 60 and notice is None


def test_environment_preset_switch_inherits_its_policy(monkeypatch):
    from aetherlab.core.settings import load_settings
    settings = load_settings()
    monkeypatch.setenv("AETHERLAB_RENDER_PRESET", "cinematic")
    assert not get_effective_profile(settings).adaptive


@pytest.mark.parametrize("enabled", [False, True])
def test_saved_explicit_adaptive_override_survives(enabled):
    from aetherlab.core.settings import load_settings, save_app_config
    save_app_config({"render_preset": "cinematic", "adaptive_quality": enabled})
    assert get_effective_profile(load_settings()).adaptive is enabled


def test_invalid_adaptive_override_does_not_enable_cinematic_fallback(monkeypatch):
    from aetherlab.core.settings import load_settings, save_app_config
    save_app_config({"render_preset": "cinematic", "adaptive_quality": False})
    monkeypatch.setenv("AETHERLAB_ADAPTIVE_QUALITY", "occasionally")
    assert not get_effective_profile(load_settings()).adaptive


def test_adaptive_notice_reports_the_actual_original_fps():
    profile = RenderProfile(width=1920, height=1080, fps=48, quality="h", adaptive=True)
    effective, notice = adapt_profile_for_cost(profile, 4.0)
    assert effective.fps == 30
    assert "48→30" in notice and "60→30" not in notice
    assert "48→30" in effective.source


def test_normalized_odd_resolution_can_encode_yuv420p(tmp_path):
    import imageio_ffmpeg
    from aetherlab.core.proc import subprocess_kwargs
    profile = RenderProfile(width=321, height=241, fps=30).validated()
    output = tmp_path / "owned-profile.mp4"
    result = subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=0.1",
        "-vf", profile.canvas_filter(), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
    ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, **subprocess_kwargs())
    assert result.returncode == 0, result.stderr
    assert profile.width % 2 == profile.height % 2 == 0
    assert output.is_file() and output.stat().st_size > 128


class OwnedGitHub:
    def __init__(self, cached=False):
        self.inputs = []
        self.cached = cached
        self.job_id = ""
    def default_branch(self): return "main"
    def ensure_workflow(self, **kwargs): return False
    def ensure_branch(self, branch): return None
    def put_file(self, *args, **kwargs): return None
    def find_repo_artifact(self, name):
        self.job_id = name.removesuffix(".mp4")
        return {"id": 7} if self.cached else None
    def get_artifact(self, artifact_id): return {"id": artifact_id}
    def dispatch(self, **kwargs):
        self.inputs.append(kwargs)
        self.job_id = kwargs["job_id"]
        return 1
    def get_run(self, *args, **kwargs): return {"id": 1, "status": "completed", "conclusion": "success"}
    def download_run_logs(self, *args): return "owned runner log"
    def find_run_artifact(self, *args): return {"id": 7}
    def download_artifact_zip(self, *args):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr(self.job_id + ".mp4", b"\x00\x00\x00\x20ftypmp42" + b"x" * 256)
        return data.getvalue()


def _cloud_settings(tmp_path, **overrides):
    from aetherlab.core.settings import load_settings
    return replace(load_settings(), data_dir=tmp_path / "data", render_mode="cloud",
        github_repo="owned/profile-test", github_token="owned-fake-token",
        render_width=960, render_height=540, render_fps=24, **overrides)


def _scene():
    from aetherlab.core.models import SceneBundle
    return SceneBundle("OwnedProfileScene", "from manim import *\nclass OwnedProfileScene(Scene):\n    def construct(self):\n        self.wait(0.1)\n", "manim-community", "compiled")


def _facts(width=960, height=540, fps=24):
    return {"video_streams": 1, "duration_s": 1.0, "width": width, "height": height, "fps": fps, "decoded_frame": 1}


def test_cloud_custom_profile_reaches_dispatch_and_media_validation(tmp_path, monkeypatch):
    from aetherlab.services import render_backend as backend
    settings = _cloud_settings(tmp_path)
    client = OwnedGitHub()
    monkeypatch.setattr(backend, "probe_mp4", lambda _path: _facts())
    result = asyncio.run(backend.CloudRenderBackend(settings, client).render(
        _scene(), quality="m", settings=settings, timeout=10))
    assert result.status == "rendered", result.diagnostics
    assert client.inputs[0]["width"] == 960 and client.inputs[0]["height"] == 540
    assert client.inputs[0]["fps"] == 24


def test_cloud_custom_dimensions_get_distinct_cache_id(tmp_path, monkeypatch):
    from aetherlab.services import render_backend as backend
    ids = []
    for width, height in ((960, 540), (1024, 576)):
        settings = replace(_cloud_settings(tmp_path), render_width=width, render_height=height)
        client = OwnedGitHub()
        monkeypatch.setattr(backend, "probe_mp4", lambda _path, w=width, h=height: _facts(w, h))
        asyncio.run(backend.CloudRenderBackend(settings, client).render(
            _scene(), quality="m", settings=settings, timeout=10))
        ids.append(client.inputs[0]["job_id"])
    assert ids[0] != ids[1], "Different requested canvases must never reuse the same cloud artifact"


def test_cloud_refuses_wrong_fps_in_download(tmp_path, monkeypatch):
    from aetherlab.services import render_backend as backend
    settings = replace(_cloud_settings(tmp_path), render_width=1280, render_height=720)
    client = OwnedGitHub()
    monkeypatch.setattr(backend, "probe_mp4", lambda _path: _facts(1280, 720, 30))
    result = asyncio.run(backend.CloudRenderBackend(settings, client).render(
        _scene(), quality="m", settings=settings, timeout=10))
    assert result.status == "render-error" and result.failure_kind == "artifact_invalid"
    assert "fps" in " ".join(result.diagnostics).lower()


def test_cloud_rejects_cached_wrong_fps_and_dispatches_again(tmp_path, monkeypatch):
    from aetherlab.services import render_backend as backend
    settings = replace(_cloud_settings(tmp_path), render_width=1280, render_height=720)
    client = OwnedGitHub(cached=True)
    monkeypatch.setattr(backend, "probe_mp4", lambda _path: _facts(1280, 720, 24 if client.inputs else 30))
    result = asyncio.run(backend.CloudRenderBackend(settings, client).render(
        _scene(), quality="m", settings=settings, timeout=10))
    assert result.status == "rendered" and len(client.inputs) == 1


def test_cloud_reports_cairo_when_opengl_is_not_available(tmp_path, monkeypatch):
    from aetherlab.services import render_backend as backend
    settings = replace(_cloud_settings(tmp_path), render_renderer="opengl", render_width=1280, render_height=720)
    client = OwnedGitHub()
    monkeypatch.setattr(backend, "probe_mp4", lambda _path: _facts(1280, 720, 24))
    result = asyncio.run(backend.CloudRenderBackend(settings, client).render(
        _scene(), quality="m", settings=settings, timeout=10))
    assert result.status == "rendered"
    assert any("Cairo" in text and "OpenGL" in text for text in result.diagnostics)


def test_invalid_download_does_not_replace_a_prior_video(tmp_path, monkeypatch):
    from aetherlab.services import render_backend as backend
    client = OwnedGitHub()
    client.job_id = "owned-job"
    output = tmp_path / "owned-job.mp4"
    output.write_bytes(b"prior good owned video")
    monkeypatch.setattr(backend, "probe_mp4", lambda _path: _facts(854, 480, 30))
    video, reason = backend.CloudRenderBackend(_cloud_settings(tmp_path), client)._download_artifact(
        client, {"id": 7}, tmp_path, client.job_id, "m")
    assert video is None and reason
    assert output.read_bytes() == b"prior good owned video"
    assert list(tmp_path.glob(".*.mp4")) == []


def test_actual_api_payload_contains_the_requested_canvas(monkeypatch):
    from aetherlab.services.render_backend import GitHubActionsClient
    client = GitHubActionsClient(owner="owned", repo="profile", token="owned-fake")
    captured = []
    def request(method, path, payload):
        captured.append(payload)
        return {"workflow_run_id": 3}
    monkeypatch.setattr(client, "_request", request)
    assert client.dispatch(job_id="owned", quality="m", fps=24, width=960, height=540,
        scene_path="jobs/owned.py", class_name="OwnedProfileScene", needs_latex=False, branch="renders") == 3
    assert captured[0]["inputs"]["width"] == "960"
    assert captured[0]["inputs"]["height"] == "540"


def test_profile_lookup_and_backend_dispatch_have_the_same_identity(tmp_path, monkeypatch):
    from aetherlab.services import render_backend as backend
    settings = _cloud_settings(tmp_path)
    client = OwnedGitHub()
    monkeypatch.setattr(backend, "probe_mp4", lambda _path: _facts())
    scene = _scene()
    expected = backend.cloud_job_id_for_profile(scene, "m", settings)
    result = asyncio.run(backend.CloudRenderBackend(settings, client).render(
        scene, quality="m", settings=settings, timeout=10))
    assert result.status == "rendered"
    assert client.inputs[0]["job_id"] == expected


def test_real_saved_profile_reaches_manim_command_and_decoded_video(tmp_path):
    import imageio_ffmpeg
    from aetherlab.core.proc import subprocess_kwargs
    from aetherlab.core.settings import load_settings, save_app_config
    from aetherlab.services.manim_runtime import _manim_render_command
    from aetherlab.services.render_backend import CloudRenderBackend, probe_mp4

    save_app_config({"render_preset": "cinematic", "render_width": 960,
                     "render_height": 540, "render_fps": 24})
    profile = get_effective_profile(load_settings())
    assert not profile.adaptive
    command = _manim_render_command(["python", "-m", "manim"], quality=profile.quality,
        fps=profile.fps, width=profile.width, height=profile.height, renderer=profile.renderer,
        seed=1, media_dir=tmp_path, scene_file=tmp_path / "owned.py", class_name="OwnedProfileScene")
    assert command[command.index("-r") + 1] == "960,540"
    assert command[command.index("--fps") + 1] == "24"
    output = tmp_path / "owned-custom-profile.mp4"
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=0.25", "-vf", profile.canvas_filter(),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, **subprocess_kwargs())
    assert result.returncode == 0, result.stderr
    facts = probe_mp4(output)
    assert (facts["width"], facts["height"], facts["fps"]) == (960, 540, 24)
    ok, reason = CloudRenderBackend._profile_matches(output, "h", width=960, height=540, fps=24)
    assert ok, reason
    assert not CloudRenderBackend._profile_matches(output, "h", width=960, height=540, fps=30)[0]


@pytest.mark.parametrize("width,height,valid", [
    ("960", "540", True), ("0", "0", True), ("321", "240", False),
    ("960", "0", False), ("99999", "540", False), ("960;echo bad", "540", False),
])
def test_actual_worker_canvas_preamble_validates_and_builds_resolution(width, height, valid, tmp_path):
    import os
    import shutil
    import textwrap
    from aetherlab.core.proc import subprocess_kwargs
    from aetherlab.services.render_backend import RENDER_WORKFLOW_YAML

    git = shutil.which("git")
    bash = Path(git).parent.parent / "bin/bash.exe" if os.name == "nt" and git else Path(shutil.which("bash") or "missing-bash")
    if not bash.is_file():
        pytest.skip("Bash unavailable; actual worker command preamble remains unverified")
    code = RENDER_WORKFLOW_YAML.split("          set +e\n", 1)[1].split("          /usr/bin/time", 1)[0]
    script = tmp_path / "owned-worker-preamble.sh"
    script.write_text(textwrap.dedent(code) + '\nprintf "%s\\n" "${size_args[@]}"\n', encoding="utf-8")
    result = subprocess.run([str(bash), script.as_posix()], cwd=tmp_path,
        env={**os.environ, "RENDER_WIDTH": width, "RENDER_HEIGHT": height},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, **subprocess_kwargs())
    assert result.returncode == (0 if valid else 2), result.stdout + result.stderr
    if valid and width != "0":
        assert result.stdout.splitlines() == ["-r", width + "," + height]
    elif not valid:
        assert "Invalid render canvas" in result.stderr
