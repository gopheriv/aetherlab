"""Cloud failure is diagnosable without local Manim (Stage C, step 6).

Safe mocks only: fake repo/token, in-process fake client, tmp data dir.
No network, no local Manim launch, user cloud settings untouched.
"""

from __future__ import annotations

import asyncio
import urllib.error
from dataclasses import replace
from pathlib import Path


def _settings(tmp_path: Path, mode: str):
    from aetherlab.core.settings import load_settings

    return replace(
        load_settings(),
        data_dir=tmp_path / "data",
        openai_api_key="test",
        render_mode=mode,
        github_repo="fake-owner/fake-repo",
        github_token="fake-token-for-mock",
    )


def _bundle():
    from aetherlab.core.models import SceneBundle

    code = (
        "from manim import *\n\n"
        "class FakeProbe(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Text('probe'))\n"
    )
    return SceneBundle(class_name="FakeProbe", code=code,
                       engine="manim", status="compiled")


class _FailingGitHubClient:
    """Passes provision/upload, then fails dispatch like a revoked token."""

    def get_artifact(self, artifact_id: int):
        return None

    def find_repo_artifact(self, name: str):
        return None

    def default_branch(self) -> str:
        return "main"

    def ensure_workflow(self, workflow: str, branch: str) -> bool:
        return False

    def ensure_branch(self, branch: str) -> None:
        return None

    def put_file(self, path: str, content: str, **kwargs) -> None:
        return None

    def dispatch(self, **kwargs) -> int:
        raise urllib.error.HTTPError(
            "https://api.github.com/fake/dispatch", 403, "Forbidden", None, None)


def test_cloud_dispatch_denied_is_diagnosed_without_local_manim(tmp_path: Path, monkeypatch) -> None:
    from aetherlab.services import manim_runtime, render_backend

    def _no_local_manim(*args, **kwargs):
        raise AssertionError("local Manim must not run for a cloud dispatch failure")

    monkeypatch.setattr(manim_runtime.ManimRuntime, "render_scene", _no_local_manim)
    settings = _settings(tmp_path, "cloud")
    backend = render_backend.CloudRenderBackend(settings, client=_FailingGitHubClient())
    result = asyncio.run(backend.render(
        _bundle(), quality="m", settings=settings, timeout=60))

    assert result.status == render_backend.CLOUD_UNAVAILABLE
    assert result.video_path == ""
    text = "\n".join(result.diagnostics)
    assert "GitHub denied access (HTTP 403)" in text
    assert "local fallback was skipped" in text
    assert "fake-token-for-mock" not in text


def _render_once(monkeypatch, tmp_path: Path, mode: str, local_renders: bool):
    from aetherlab.services import render_backend
    from aetherlab.services.manim_runtime import ManimRuntime

    calls: list[str] = []

    class _Cloud:
        name = "github-actions"

        async def render(self, scene, **kwargs):
            calls.append("cloud")
            return replace(scene, status=render_backend.CLOUD_UNAVAILABLE,
                           diagnostics=["Cloud render unavailable: down"])

    class _Local:
        name = "local"

        async def render(self, scene, **kwargs):
            calls.append("local")
            if not local_renders:
                raise AssertionError("local Manim must not run in cloud-only mode")
            return replace(scene, status="rendered", video_path="local.mp4")

    monkeypatch.setattr(render_backend, "select_backend", lambda *a, **k: _Cloud())
    monkeypatch.setattr(render_backend, "LocalRenderBackend", _Local)
    settings = _settings(tmp_path, mode)
    result = asyncio.run(ManimRuntime(settings)._render_once(_bundle(), settings, "m"))
    return result, calls


def test_cloud_only_mode_never_falls_back_to_local(tmp_path: Path, monkeypatch) -> None:
    from aetherlab.services import render_backend

    result, calls = _render_once(monkeypatch, tmp_path, "cloud", local_renders=False)
    assert result.status == render_backend.CLOUD_UNAVAILABLE
    assert calls == ["cloud"]


def test_auto_mode_falls_back_to_local_after_cloud_failure(tmp_path: Path, monkeypatch) -> None:
    result, calls = _render_once(monkeypatch, tmp_path, "auto", local_renders=True)
    assert result.status == "rendered"
    assert calls == ["cloud", "local"]


def test_worker_output_failure_overrides_dependency_banners():
    from aetherlab.services.manim_runtime import _classify_failure

    for count, expected in ((0, "artifact_missing"), (2, "artifact_ambiguous")):
        log = "ffmpeg installed successfully\n" + f"Expected one final MP4 for scene RequestedScene; found {count}\n" + "cleanup codec paths\n" * 100
        assert _classify_failure(log) == expected


def test_worker_output_excerpt_keeps_the_actual_failure():
    from aetherlab.services.render_backend import _render_error_excerpt

    log = "ffmpeg installed successfully\nExpected one final MP4 for scene RequestedScene; found 0\n##[error]Process completed with exit code 2.\n" + "git cleanup\n" * 1000
    excerpt = _render_error_excerpt(log)
    assert "Expected one final MP4" in excerpt
    assert "ffmpeg installed" not in excerpt
    assert "git cleanup" not in excerpt


class _CompletedClient(_FailingGitHubClient):
    conclusion = "failure"
    artifact = None

    def dispatch(self, **kwargs):
        return 123

    def get_run(self, *args, **kwargs):
        return {"id": 123, "status": "completed", "conclusion": self.conclusion}

    def download_run_logs(self, run_id):
        return "ffmpeg installed successfully\nExpected one final MP4 for scene FakeProbe; found 0\n##[error]Process completed with exit code 2.\n" + "git cleanup\n" * 1000

    def find_run_artifact(self, run_id, name):
        return self.artifact


def test_failed_worker_reports_missing_output_without_local_fallback(tmp_path, monkeypatch):
    from aetherlab.services import manim_runtime, render_backend

    monkeypatch.setattr(manim_runtime, "_RUNS_DIR", tmp_path / "runs")
    settings = _settings(tmp_path, "cloud")
    result = asyncio.run(render_backend.CloudRenderBackend(settings, _CompletedClient()).render(
        _bundle(), quality="m", settings=settings, timeout=60))
    assert result.status == "render-error" and not result.video_path
    assert result.failure_kind == "artifact_missing"
    assert any("timed animation" in note for note in result.diagnostics)


def test_successful_workflow_without_artifact_has_missing_output_kind(tmp_path, monkeypatch):
    from aetherlab.services import manim_runtime, render_backend

    monkeypatch.setattr(manim_runtime, "_RUNS_DIR", tmp_path / "runs")
    client = _CompletedClient()
    client.conclusion = "success"
    settings = _settings(tmp_path, "cloud")
    result = asyncio.run(render_backend.CloudRenderBackend(settings, client).render(
        _bundle(), quality="m", settings=settings, timeout=60))
    assert result.status == "render-error" and not result.video_path
    assert result.failure_kind == "artifact_missing"


def test_invalid_artifact_has_validation_kind_not_encoder_kind(tmp_path, monkeypatch):
    from aetherlab.services import manim_runtime, render_backend

    monkeypatch.setattr(manim_runtime, "_RUNS_DIR", tmp_path / "runs")
    client = _CompletedClient()
    client.conclusion, client.artifact = "success", {"id": 321}
    settings = _settings(tmp_path, "cloud")
    backend = render_backend.CloudRenderBackend(settings, client)
    monkeypatch.setattr(backend, "_download_artifact", lambda *args, **kwargs: (None, "video has no decodable frame"))
    result = asyncio.run(backend.render(_bundle(), quality="m", settings=settings, timeout=60))
    assert result.status == "render-error" and not result.video_path
    assert result.failure_kind == "artifact_invalid"
    assert any("no decodable frame" in note for note in result.diagnostics)
