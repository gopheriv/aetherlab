"""Pluggable render backends for AetherLab.

The repair/critique/narration loop lives in ``manim_runtime.py``. This module
only answers "where does one Manim render run happen?" Local rendering delegates
to the existing implementation; cloud rendering uses a private-or-public GitHub
repository as a Linux Actions render worker and always fails soft so the caller
can fall back to local.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Protocol

from aetherlab.core.models import SceneBundle

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

MANIM_VERSION_PIN = "0.20.1"
CLOUD_WORKFLOW_VERSION = "1"
CLOUD_UNAVAILABLE = "cloud-unavailable"
DEFAULT_GITHUB_WORKFLOW = "render.yml"
DEFAULT_GITHUB_BRANCH = "renders"


class RenderBackend(Protocol):
    name: str

    def available(self) -> tuple[bool, str]:
        """Return whether the backend can be attempted and a human reason."""

    async def render(
        self,
        scene: SceneBundle,
        *,
        quality: str,
        settings: "AppSettings",
        timeout: int,
        progress: Callable[[str], None] | None = None,
    ) -> SceneBundle:
        """Render one compiled SceneBundle to a video or failure SceneBundle."""


class LocalRenderBackend:
    name = "local"

    def available(self) -> tuple[bool, str]:
        from importlib.util import find_spec
        import shutil

        if find_spec("manim") or shutil.which("manim"):
            return True, "Manim is available locally."
        return False, "Manim is not installed locally."

    async def render(
        self,
        scene: SceneBundle,
        *,
        quality: str,
        settings: "AppSettings",
        timeout: int,
        progress: Callable[[str], None] | None = None,
    ) -> SceneBundle:
        if progress:
            progress("Rendering locally")
        from aetherlab.services.manim_runtime import ManimRuntime

        return await asyncio.to_thread(ManimRuntime(settings).render_scene, scene, settings, quality)


class CloudRenderBackend:
    name = "github-actions"

    def __init__(self, settings: "AppSettings", client: "GitHubActionsClient | None" = None) -> None:
        self.settings = settings
        self.client = client

    def available(self) -> tuple[bool, str]:
        if getattr(self.settings, "cloud_provider", "github_actions") != "github_actions":
            return False, "Only github_actions is supported."
        if not getattr(self.settings, "github_repo", ""):
            return False, "GitHub render repo is not configured."
        if not _github_token(self.settings):
            return False, "GitHub token is not configured."
        if not getattr(self.settings, "github_workflow", DEFAULT_GITHUB_WORKFLOW):
            return False, "GitHub workflow is not configured."
        return True, "GitHub Actions render backend is configured."

    async def render(
        self,
        scene: SceneBundle,
        *,
        quality: str,
        settings: "AppSettings",
        timeout: int,
        progress: Callable[[str], None] | None = None,
    ) -> SceneBundle:
        ok, reason = self.available()
        if not ok:
            return _cloud_unavailable(scene, reason)
        if scene.status != "compiled":
            scene.diagnostics.append("Skipping cloud render: scene did not compile.")
            return scene
        blocked = scan_cloud_payload(scene.code)
        if blocked:
            return _cloud_unavailable(scene, blocked)

        from aetherlab.services.manim_runtime import (
            _RUNS_DIR,
            _classify_failure,
            _dump_render_failure,
            _estimate_render_cost,
        )

        fps = render_fps_for(scene.code, quality)
        job_id = cloud_job_id(scene, quality=quality, fps=fps)
        run_dir = _RUNS_DIR / f"cloud_{job_id}_{quality}"
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = CloudRenderManifest(Path(settings.data_dir) / "cloud_renders.json")
        cached = manifest.get(job_id)
        client = self.client or GitHubActionsClient.from_settings(settings)

        def say(message: str) -> None:
            if progress:
                try:
                    progress(message)
                except Exception:  # noqa: BLE001
                    pass

        try:
            say("Checking cloud render cache")
            video = await asyncio.to_thread(self._download_cached, client, manifest, job_id, run_dir, cached)
            if video:
                scene.video_path = str(video)
                scene.status = "rendered"
                scene.failure_kind = ""
                scene.diagnostics.append(f"Cloud render cache hit ({job_id}).")
                return scene

            say("Uploading scene to GitHub")
            scene_path = f"jobs/{job_id}.py"
            await asyncio.to_thread(
                client.ensure_branch,
                getattr(settings, "github_branch", DEFAULT_GITHUB_BRANCH),
            )
            await asyncio.to_thread(
                client.put_file,
                scene_path,
                scene.code,
                branch=getattr(settings, "github_branch", DEFAULT_GITHUB_BRANCH),
                message=f"Add AetherLab render job {job_id}",
            )

            say("Dispatching cloud render")
            run_id = await asyncio.to_thread(
                client.dispatch,
                job_id=job_id,
                quality=quality,
                fps=fps,
                scene_path=scene_path,
                class_name=scene.class_name,
                needs_latex=_needs_latex(scene.code),
                branch=getattr(settings, "github_branch", DEFAULT_GITHUB_BRANCH),
            )

            deadline = time.monotonic() + min(timeout, int(getattr(settings, "cloud_render_timeout", timeout)))
            poll = max(2, int(getattr(settings, "cloud_poll_seconds", 8)))
            run = None
            while time.monotonic() < deadline:
                run = await asyncio.to_thread(
                    client.get_run,
                    run_id,
                    job_id=job_id,
                    branch=getattr(settings, "github_branch", DEFAULT_GITHUB_BRANCH),
                )
                status = (run.get("status") or "").lower()
                conclusion = (run.get("conclusion") or "").lower()
                if status == "completed":
                    if conclusion == "success":
                        break
                    log_text = await asyncio.to_thread(client.download_run_logs, int(run["id"]))
                    stderr = log_text[-8000:] if log_text else f"GitHub Actions concluded {conclusion or 'failure'}."
                    kind = _classify_failure(stderr)
                    dump = _dump_render_failure(settings.data_dir, scene.code, stderr, kind)
                    note = f"Cloud render failed [{kind}]: {stderr[-8000:]}"
                    if dump:
                        note += f"\n(full log: {dump})"
                    scene.diagnostics.append(note)
                    scene.status = "render-error"
                    scene.failure_kind = kind
                    return scene
                say(f"Cloud render {status or 'queued'}")
                await asyncio.sleep(poll)

            if not run or (run.get("status") or "").lower() != "completed":
                _dump_render_failure(settings.data_dir, scene.code, "cloud render exceeded time budget", "timeout")
                scene.diagnostics.append(
                    f"Cloud render timed out ({timeout}s, cost {_estimate_render_cost(scene.code):.1f})."
                )
                scene.status = "render-timeout"
                scene.failure_kind = "timeout"
                return scene

            say("Downloading cloud video")
            artifact = await asyncio.to_thread(client.find_run_artifact, int(run["id"]), f"{job_id}.mp4")
            if not artifact:
                scene.diagnostics.append("Cloud render succeeded but MP4 artifact was not found.")
                scene.status = "render-error"
                scene.failure_kind = "unknown"
                return scene
            video = await asyncio.to_thread(self._download_artifact, client, artifact, run_dir, job_id)
            if not video:
                scene.diagnostics.append("Cloud MP4 artifact failed validation.")
                scene.status = "render-error"
                scene.failure_kind = "ffmpeg"
                return scene
            manifest.put(job_id, {"artifact_id": artifact["id"], "run_id": run["id"]})
            scene.video_path = str(video)
            scene.status = "rendered"
            scene.failure_kind = ""
            scene.diagnostics.append(f"Rendered via GitHub Actions ({job_id}).")
            return scene
        except Exception as exc:  # noqa: BLE001
            log.warning("Cloud render unavailable; falling back to local: %s", _mask(str(exc)))
            return _cloud_unavailable(scene, f"Cloud render unavailable: {_mask(str(exc))}")

    def _download_cached(
        self,
        client: "GitHubActionsClient",
        manifest: "CloudRenderManifest",
        job_id: str,
        run_dir: Path,
        cached: dict | None,
    ) -> Path | None:
        if cached and cached.get("artifact_id"):
            try:
                artifact = client.get_artifact(int(cached["artifact_id"]))
                if artifact and not artifact.get("expired"):
                    return self._download_artifact(client, artifact, run_dir, job_id)
            except Exception:  # noqa: BLE001
                pass
        artifact = client.find_repo_artifact(f"{job_id}.mp4")
        if artifact and not artifact.get("expired"):
            manifest.put(job_id, {"artifact_id": artifact["id"], "run_id": artifact.get("workflow_run", {}).get("id")})
            return self._download_artifact(client, artifact, run_dir, job_id)
        return None

    def _download_artifact(
        self, client: "GitHubActionsClient", artifact: dict, run_dir: Path, job_id: str
    ) -> Path | None:
        data = client.download_artifact_zip(int(artifact["id"]))
        with zipfile.ZipFile(BytesReader(data)) as zf:
            for name in zf.namelist():
                target = Path(name)
                if target.name != f"{job_id}.mp4" or target.is_absolute() or ".." in target.parts:
                    continue
                out = run_dir / target.name
                out.write_bytes(zf.read(name))
                return out if validate_mp4(out) else None
        return None


def select_backend(settings: "AppSettings", code: str = "", quality: str = "l") -> RenderBackend:
    mode = str(getattr(settings, "render_mode", "local") or "local").lower()
    if mode not in {"local", "cloud", "auto"}:
        mode = "local"
    if mode == "local":
        return LocalRenderBackend()
    cloud = CloudRenderBackend(settings)
    if mode == "cloud":
        return cloud
    if mode == "auto":
        from aetherlab.services.manim_runtime import _estimate_render_cost

        threshold = float(getattr(settings, "cloud_render_threshold", 3.0) or 3.0)
        if _estimate_render_cost(code) < threshold:
            return LocalRenderBackend()
        return cloud
    return LocalRenderBackend()


def render_timeout_for(code: str, quality: str, settings: "AppSettings") -> int:
    from aetherlab.services.manim_runtime import _estimate_render_cost

    if str(getattr(settings, "render_mode", "local") or "local").lower() in {"cloud", "auto"}:
        return int(getattr(settings, "cloud_render_timeout", 1800) or 1800)
    base_timeout = {"l": 240, "m": 420, "h": 600, "k": 900}.get(quality, 240)
    return min(int(base_timeout * _estimate_render_cost(code)), 1800)


def render_fps_for(code: str, quality: str) -> int:
    from aetherlab.services.manim_runtime import _RENDER_TIER, _estimate_render_cost

    fps = int(_RENDER_TIER["fps"])
    if _estimate_render_cost(code) >= 3.0 and quality in ("h", "k"):
        fps = 30
    return fps


def cloud_job_id(scene: SceneBundle, *, quality: str, fps: int) -> str:
    payload = "\n".join([
        scene.class_name,
        scene.code,
        quality,
        str(fps),
        f"manim=={MANIM_VERSION_PIN}",
        f"workflow={CLOUD_WORKFLOW_VERSION}",
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def scan_cloud_payload(code: str) -> str | None:
    """Refuse cloud when scene code appears to contain secrets.

    Public render repos are allowed, so this guard focuses on credentials and
    config-file material rather than prompt-derived scene text.
    """
    patterns = (
        r"github_pat_[A-Za-z0-9_]+",
        r"gh[pousr]_[A-Za-z0-9_]{20,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{20,}",
        r"OPENAI_API_KEY",
        r"AETHERLAB_OPENAI",
        r"api[_-]?key\s*=",
        r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
    )
    for pat in patterns:
        if re.search(pat, code, re.IGNORECASE):
            return "Cloud render refused: scene code appears to contain a secret."
    return None


def validate_mp4(path: Path) -> bool:
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return False
    return path.exists() and path.stat().st_size > 128 and b"ftyp" in data[:64]


def _needs_latex(code: str) -> bool:
    return any(token in code for token in ("MathTex", "Tex(", "TexTemplate"))


def _github_token(settings: "AppSettings") -> str:
    return str(getattr(settings, "github_token", "") or "").strip()


def _cloud_unavailable(scene: SceneBundle, reason: str) -> SceneBundle:
    scene.diagnostics.append(_mask(reason))
    scene.status = CLOUD_UNAVAILABLE
    scene.failure_kind = ""
    return scene


def _mask(text: str) -> str:
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "github_pat_***", text)
    text = re.sub(r"gh[pousr]_[A-Za-z0-9_]{8,}", "gh_***", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-***", text)
    return text


@dataclass
class GitHubActionsClient:
    owner: str
    repo: str
    token: str
    workflow: str = DEFAULT_GITHUB_WORKFLOW
    branch: str = DEFAULT_GITHUB_BRANCH
    api_base: str = "https://api.github.com"

    @classmethod
    def from_settings(cls, settings: "AppSettings") -> "GitHubActionsClient":
        repo = str(getattr(settings, "github_repo", "") or "").strip()
        if "/" not in repo:
            raise ValueError("GitHub repo must be in owner/name form.")
        owner, name = repo.split("/", 1)
        return cls(
            owner=owner,
            repo=name,
            token=_github_token(settings),
            workflow=str(getattr(settings, "github_workflow", DEFAULT_GITHUB_WORKFLOW) or DEFAULT_GITHUB_WORKFLOW),
            branch=str(getattr(settings, "github_branch", DEFAULT_GITHUB_BRANCH) or DEFAULT_GITHUB_BRANCH),
        )

    def _request(self, method: str, path: str, payload: dict | None = None, *, raw: bool = False):
        url = self.api_base.rstrip("/") + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("X-GitHub-Api-Version", "2026-03-10")
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            body = resp.read()
            if raw:
                return body
            return json.loads(body.decode("utf-8")) if body else {}

    def ensure_branch(self, branch: str) -> None:
        try:
            self._request("GET", f"/repos/{self.owner}/{self.repo}/git/ref/heads/{urllib.parse.quote(branch, safe='')}")
            return
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        repo_info = self._request("GET", f"/repos/{self.owner}/{self.repo}")
        default = repo_info.get("default_branch", "main")
        ref = self._request("GET", f"/repos/{self.owner}/{self.repo}/git/ref/heads/{urllib.parse.quote(default, safe='')}")
        sha = ref.get("object", {}).get("sha")
        if not sha:
            raise RuntimeError("Could not resolve default branch SHA.")
        self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": sha},
        )

    def put_file(self, path: str, content: str, *, branch: str, message: str) -> None:
        sha = None
        quoted = urllib.parse.quote(path)
        try:
            existing = self._request(
                "GET",
                f"/repos/{self.owner}/{self.repo}/contents/{quoted}?ref={urllib.parse.quote(branch)}",
            )
            sha = existing.get("sha")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        self._request("PUT", f"/repos/{self.owner}/{self.repo}/contents/{quoted}", payload)

    def dispatch(
        self,
        *,
        job_id: str,
        quality: str,
        fps: int,
        scene_path: str,
        class_name: str,
        needs_latex: bool,
        branch: str,
    ) -> int | None:
        result = self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/actions/workflows/{urllib.parse.quote(self.workflow)}/dispatches",
            {
                "ref": branch,
                "inputs": {
                    "job_id": job_id,
                    "quality": quality,
                    "fps": str(fps),
                    "scene_path": scene_path,
                    "class_name": class_name,
                    "needs_latex": "true" if needs_latex else "false",
                },
            },
        )
        return result.get("workflow_run_id") or None

    def get_run(self, run_id: int | None, *, job_id: str, branch: str) -> dict:
        if run_id:
            return self._request("GET", f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}")
        runs = self._request(
            "GET",
            f"/repos/{self.owner}/{self.repo}/actions/runs?event=workflow_dispatch&branch={urllib.parse.quote(branch)}",
        ).get("workflow_runs", [])
        for run in runs:
            text = " ".join(str(run.get(k, "")) for k in ("name", "display_title", "head_branch"))
            if job_id in text:
                return run
        return {"status": "queued"}

    def get_artifact(self, artifact_id: int) -> dict:
        return self._request("GET", f"/repos/{self.owner}/{self.repo}/actions/artifacts/{artifact_id}")

    def find_repo_artifact(self, name: str) -> dict | None:
        artifacts = self._request("GET", f"/repos/{self.owner}/{self.repo}/actions/artifacts?name={urllib.parse.quote(name)}").get("artifacts", [])
        return artifacts[0] if artifacts else None

    def find_run_artifact(self, run_id: int, name: str) -> dict | None:
        artifacts = self._request("GET", f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/artifacts").get("artifacts", [])
        return next((a for a in artifacts if a.get("name") == name), None)

    def download_artifact_zip(self, artifact_id: int) -> bytes:
        return self._request(
            "GET",
            f"/repos/{self.owner}/{self.repo}/actions/artifacts/{artifact_id}/zip",
            raw=True,
        )

    def download_run_logs(self, run_id: int) -> str:
        try:
            data = self._request("GET", f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/logs", raw=True)
            try:
                with zipfile.ZipFile(BytesReader(data)) as zf:
                    parts = []
                    for name in zf.namelist():
                        if not name.endswith("/"):
                            parts.append(zf.read(name).decode("utf-8", errors="replace"))
                    return "\n".join(parts)
            except zipfile.BadZipFile:
                return data.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return ""


class CloudRenderManifest:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, job_id: str) -> dict | None:
        item = self._load().get(job_id)
        return item if isinstance(item, dict) else None

    def put(self, job_id: str, data: dict) -> None:
        payload = self._load()
        payload[job_id] = data
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass


class BytesReader:
    """Tiny file-like adapter so zipfile can read in-memory artifact bytes."""

    def __init__(self, data: bytes) -> None:
        import io

        self._bio = io.BytesIO(data)

    def __getattr__(self, name: str):
        return getattr(self._bio, name)


def request_github_device_code(client_id: str, scope: str = "repo workflow") -> dict:
    data = urllib.parse.urlencode({"client_id": client_id, "scope": scope}).encode("utf-8")
    req = urllib.request.Request("https://github.com/login/device/code", data=data, method="POST")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def poll_github_device_token(client_id: str, device_code: str) -> dict:
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }).encode("utf-8")
    req = urllib.request.Request("https://github.com/login/oauth/access_token", data=data, method="POST")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))
