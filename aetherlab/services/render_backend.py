"""Pluggable render backends for AetherLab.

The repair/critique/narration loop lives in ``manim_runtime.py``. This module
only answers "where does one Manim render run happen?" Local rendering delegates
to the existing implementation; cloud rendering uses a private-or-public GitHub
repository as a Linux Actions render worker and respects explicit Cloud-only
mode when a remote request fails.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Protocol

from aetherlab.core.atomic_json import atomic_write_json, path_lock
from aetherlab.core.models import SceneBundle

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

MANIM_VERSION_PIN = "0.21.0"
CLOUD_WORKFLOW_VERSION = "3"  # bumped for structured render telemetry
CLOUD_UNAVAILABLE = "cloud-unavailable"
DEFAULT_GITHUB_WORKFLOW = "render.yml"
DEFAULT_GITHUB_BRANCH = "renders"


def _workflow_elapsed_metrics(run: dict) -> dict[str, float]:
    """Extract queue and worker time from GitHub's public run timestamps."""
    def parse(key: str) -> datetime | None:
        value = run.get(key)
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    created, started, updated = parse("created_at"), parse("run_started_at"), parse("updated_at")
    metrics: dict[str, float] = {}
    if created and started:
        metrics["queue_seconds"] = max(0.0, (started - created).total_seconds())
    if started and updated:
        metrics["worker_seconds"] = max(0.0, (updated - started).total_seconds())
    return metrics


# "render<TAB>Render scene<TAB>2026-10-01T07:14:11Z " - job/step columns and
# the timestamp GitHub prefixes to every log line.
_GH_TIMESTAMP_RE = re.compile(r"(?m)^(?:[^\t\n]*\t){0,2}\d{4}-\d\d-\d\dT[\d:.]+Z ?")


def _render_error_excerpt(log_text: str, limit: int = 8000) -> str:
    """The part of a GitHub Actions log that explains a failed render.

    The job log ends with GitHub's post-job cleanup (git config, artifact
    upload), so its tail hid the traceback from repair and the agent team's
    Reviewer (live 2026-10-01: an AttributeError arrived as git noise). Prefer
    the last Python traceback, then the last exception line, then the tail.
    """
    text = _GH_TIMESTAMP_RE.sub("", str(log_text or ""))
    start = text.rfind("Traceback (most recent call last)")
    if start < 0:
        match = None
        for match in re.finditer(r"(?m)^.*\b\w+(?:Error|Exception)\b:.*$", text):
            pass
        if match is None:
            return text[-limit:]
        start = max(0, text.rfind("\n", 0, max(0, match.start() - 2500)))
    end = text.find("##[error]", start)
    excerpt = text[start:end if end > start else None].strip()
    return excerpt[-limit:]


def _parse_runner_metrics(log_text: str) -> dict[str, float | str]:
    """Read numeric/version markers despite GitHub's per-line log prefixes."""
    metrics: dict[str, float | str] = {}
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(log_text or ""))
    for key, field in (
        ("AETHERLAB_RENDER_WALL_SECONDS", "render_wall_seconds"),
        ("AETHERLAB_PEAK_RSS_KB", "peak_rss_mb"),
    ):
        matches = re.findall(
            rf"\b{re.escape(key)}=([0-9]+(?:\.[0-9]+)?)\b", text
        )
        if matches:
            value = float(matches[-1])
            metrics[field] = value / 1024.0 if field == "peak_rss_mb" else value
    versions = re.findall(r"\bmanim\s+([0-9]+\.[0-9]+\.[0-9]+)\b", text)
    if versions:
        metrics["manim_version"] = versions[-1]
    return metrics

# The Actions workflow the cloud backend dispatches. It MUST exist in the user's
# render repo — GitHub only lets the REST API dispatch a workflow that is present
# on the repository's default branch, and the dispatched ``ref`` runs that
# branch's copy of the file — so the app installs this on BOTH the default branch
# and the render branch (see ``provision_render_repo``). Bundled as a string so
# it works identically from a source checkout and a frozen build. Keep in sync
# with .github/workflows/render.yml (CLOUD_WORKFLOW_VERSION gates the job hash).
RENDER_WORKFLOW_YAML = r"""name: AetherLab Cloud Render
run-name: AetherLab render ${{ inputs.job_id }}

on:
  workflow_dispatch:
    inputs:
      job_id:
        description: Stable render job id
        required: true
        type: string
      quality:
        description: Manim quality flag
        required: true
        default: l
        type: choice
        options: [l, m, h, k]
      fps:
        description: Frames per second
        required: true
        default: "30"
        type: string
      scene_path:
        description: Path to committed scene file
        required: true
        type: string
      class_name:
        description: Manim scene class
        required: true
        default: AetherLabScene
        type: string
      needs_latex:
        description: Install a minimal TeX stack
        required: true
        default: "false"
        type: choice
        options: ["false", "true"]

permissions:
  contents: read
  actions: read

jobs:
  render:
    runs-on: ubuntu-24.04
    timeout-minutes: 360
    steps:
      - uses: actions/checkout@v5
        with:
          ref: ${{ github.ref_name }}

      - uses: actions/setup-python@v6
        with:
          python-version: "3.14"

      - name: Install system render dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \
            ffmpeg libcairo2-dev libpango1.0-dev pkg-config
          if [ "${{ inputs.needs_latex }}" = "true" ]; then
            sudo apt-get install -y --no-install-recommends \
              texlive-latex-base texlive-latex-extra texlive-fonts-recommended dvisvgm
          fi

      - name: Install pinned Manim
        run: |
          python -m pip install --upgrade pip
          python -m pip install "manim==0.21.0"
          python - <<'PY'
          import importlib.metadata as m
          print("manim", m.version("manim"))
          PY

      - name: Render scene
        id: render
        shell: bash
        run: |
          set +e
          mkdir -p out
          /usr/bin/time -f 'AETHERLAB_RENDER_WALL_SECONDS=%e\nAETHERLAB_PEAK_RSS_KB=%M' \
            -o "${{ inputs.job_id }}.telemetry" python -m manim render \
            -q${{ inputs.quality }} \
            --fps "${{ inputs.fps }}" \
            --disable_caching \
            --media_dir out \
            "${{ inputs.scene_path }}" \
            "${{ inputs.class_name }}" 2>&1 | tee "${{ inputs.job_id }}.log"
          code=${PIPESTATUS[0]}
          cat "${{ inputs.job_id }}.telemetry" | tee -a "${{ inputs.job_id }}.log"
          if [ "$code" -ne 0 ]; then
            exit "$code"
          fi
          mp4="$(find out -type f -name '*.mp4' -print0 | xargs -0 ls -S | head -n 1)"
          if [ -z "$mp4" ]; then
            echo "No MP4 produced" | tee -a "${{ inputs.job_id }}.log"
            exit 2
          fi
          cp "$mp4" "${{ inputs.job_id }}.mp4"

      - name: Upload rendered MP4
        if: success()
        uses: actions/upload-artifact@v6
        with:
          name: ${{ inputs.job_id }}.mp4
          path: ${{ inputs.job_id }}.mp4
          retention-days: 14

      - name: Upload render log
        if: always()
        uses: actions/upload-artifact@v6
        with:
          name: ${{ inputs.job_id }}.log
          path: ${{ inputs.job_id }}.log
          if-no-files-found: ignore
          retention-days: 14
"""


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
        variant: str = "",
        cancel_check: Callable[[], bool] | None = None,
        cache_lineage: str | None = None,
        partial_animation_range: tuple[int, int] | None = None,
    ) -> SceneBundle:
        """Render one compiled SceneBundle to a video or failure SceneBundle.

        ``variant`` isolates concurrent tournament candidates (see cloud_job_id).
        """


# Global bound on concurrent LOCAL Manim renders (F178). Lessons render chapters
# concurrently and each chapter's tournament renders candidates concurrently, so
# without a shared cap the nesting multiplies (e.g. 2 chapters x 2 candidates) into
# many simultaneous CPU-bound subprocesses that thrash the machine and can push a
# render past its timeout. Threading (not asyncio) so the bound holds across the
# app's many separate event loops. Cloud renders are I/O-bound and NOT bounded here.
def _default_local_render_limit() -> int:
    return max(1, min(4, (os.cpu_count() or 4) // 2 or 1))


LOCAL_RENDER_LIMIT: int = max(
    1, int(os.getenv("AETHERLAB_LOCAL_RENDER_LIMIT") or _default_local_render_limit())
)
_LOCAL_RENDER_SEM = threading.Semaphore(LOCAL_RENDER_LIMIT)

# GitHub's Contents API creates one commit per write and documents concurrent
# mutations as conflicting. Tournament candidates use separate files but share
# a branch, so serialize by repository+branch inside this process; bounded 409
# retries below also cover a second AetherLab process writing at the same time.
_BRANCH_WRITE_LOCKS_GUARD = threading.Lock()
_BRANCH_WRITE_LOCKS: dict[tuple[str, str, str], threading.RLock] = {}


def _branch_write_lock(owner: str, repo: str, branch: str) -> threading.RLock:
    key = (owner.lower(), repo.lower(), branch)
    with _BRANCH_WRITE_LOCKS_GUARD:
        return _BRANCH_WRITE_LOCKS.setdefault(key, threading.RLock())


class LocalRenderBackend:
    name = "local"

    def available(self) -> tuple[bool, str]:
        import shutil
        from importlib.util import find_spec

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
        variant: str = "",  # accepted for interface parity; local renders are already isolated per-process
        cancel_check: Callable[[], bool] | None = None,
        cache_lineage: str | None = None,
        partial_animation_range: tuple[int, int] | None = None,
    ) -> SceneBundle:
        if progress:
            progress("Rendering locally")
        from aetherlab.services.manim_runtime import ManimRuntime

        def _bounded_render() -> SceneBundle:
            # Acquired inside the worker thread so the global cap holds across
            # concurrent lesson chapters and tournament candidates.
            from aetherlab.core.proc import ProcessCancelledError

            while not _LOCAL_RENDER_SEM.acquire(timeout=0.1):
                if cancel_check is not None and cancel_check():
                    raise ProcessCancelledError("Render cancelled while queued")
            try:
                cancel_kwargs = (
                    {"cancel_check": cancel_check} if cancel_check is not None else {}
                )
                return ManimRuntime(settings).render_scene(
                    scene, settings, quality,
                    cache_lineage=cache_lineage,
                    partial_animation_range=partial_animation_range,
                    **cancel_kwargs,
                )
            finally:
                _LOCAL_RENDER_SEM.release()

        return await asyncio.to_thread(_bounded_render)


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
        variant: str = "",
        cancel_check: Callable[[], bool] | None = None,
        cache_lineage: str | None = None,
        partial_animation_range: tuple[int, int] | None = None,
    ) -> SceneBundle:
        from aetherlab.core.proc import ProcessCancelledError

        def ensure_active() -> None:
            if cancel_check is not None and cancel_check():
                raise ProcessCancelledError("Cloud render cancelled")

        ensure_active()
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
        job_id = cloud_job_id(scene, quality=quality, fps=fps, variant=variant)
        run_dir = _RUNS_DIR / f"cloud_{job_id}_{quality}"
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = CloudRenderManifest(Path(settings.data_dir) / "cloud_renders.json")
        cached = manifest.get(job_id)
        client = self.client or GitHubActionsClient.from_settings(settings)

        # Render-farm ledger: observe this cloud job so the dashboard can show
        # what queued, ran, failed, downloaded, or fell back. Fail-soft.
        from aetherlab.services.render_ledger import RenderJobLedger

        ledger = RenderJobLedger(Path(settings.data_dir) / "render_ledger.json")
        ledger.start(job_id=job_id, scene_class=scene.class_name, quality=quality,
                     fps=fps, backend=self.name, provider="github_actions")
        total_started = time.monotonic()
        current_stage = "cache_check"

        def record_metrics(**values) -> None:
            values.setdefault("backend", "github_actions")
            ledger.metrics(job_id, values)

        def say(message: str) -> None:
            if progress:
                try:
                    progress(message)
                except Exception:  # noqa: BLE001
                    pass

        run_id = None
        try:
            say("Checking cloud render cache")
            video = await asyncio.to_thread(self._download_cached, client, manifest, job_id, run_dir, cached)
            ensure_active()
            if video:
                scene.video_path = str(video)
                scene.status = "rendered"
                scene.failure_kind = ""
                scene.diagnostics.append(f"Cloud render cache hit ({job_id}).")
                ledger.status(job_id, "rendered", "cloud cache hit")
                ledger.finish(job_id, "rendered", str(video))
                record_metrics(cache_hit=True, total_seconds=time.monotonic() - total_started)
                return scene

            say("Preparing render repo")
            current_stage = "prepare"
            prepare_started = time.monotonic()
            # Install the dispatchable workflow (on the default + render branch)
            # BEFORE the first dispatch — otherwise dispatch 404s and cloud looks
            # "unavailable" even on a correctly configured repo/token.
            await asyncio.to_thread(
                provision_render_repo,
                client,
                branch=getattr(settings, "github_branch", DEFAULT_GITHUB_BRANCH),
                workflow=getattr(settings, "github_workflow", DEFAULT_GITHUB_WORKFLOW) or DEFAULT_GITHUB_WORKFLOW,
            )
            ensure_active()
            prepare_seconds = time.monotonic() - prepare_started

            say("Uploading scene to GitHub")
            current_stage = "upload"
            upload_started = time.monotonic()
            scene_path = f"jobs/{job_id}.py"
            await asyncio.to_thread(
                client.put_file,
                scene_path,
                scene.code,
                branch=getattr(settings, "github_branch", DEFAULT_GITHUB_BRANCH),
                message=f"Add AetherLab render job {job_id}",
            )
            ensure_active()
            upload_seconds = time.monotonic() - upload_started

            say("Dispatching cloud render")
            current_stage = "dispatch"
            dispatch_started = time.monotonic()
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
            dispatch_seconds = time.monotonic() - dispatch_started
            ledger.status(job_id, "in_progress", "dispatched to GitHub Actions")

            effective_timeout = max(
                0,
                min(timeout, int(getattr(settings, "cloud_render_timeout", timeout) or timeout)),
            )
            deadline = time.monotonic() + effective_timeout
            poll = max(2, int(getattr(settings, "cloud_poll_seconds", 8)))
            run = None
            current_stage = "poll"
            while time.monotonic() < deadline:
                ensure_active()
                try:
                    run = await asyncio.to_thread(
                        client.get_run,
                        run_id,
                        job_id=job_id,
                        branch=getattr(settings, "github_branch", DEFAULT_GITHUB_BRANCH),
                    )
                except urllib.error.HTTPError as exc:
                    # Authentication, permission, and missing-run errors will not
                    # heal by polling again. Retry only GitHub's transient statuses.
                    if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                        raise
                    log.warning("Transient GitHub run-poll response %s; retrying", exc.code)
                    say("Cloud status check was delayed; retrying")
                    await asyncio.sleep(min(poll, max(0.0, deadline - time.monotonic())))
                    continue
                except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as exc:
                    # A status-read timeout does not mean the remote render failed.
                    # GitHub Actions continues independently, so retry within the
                    # existing render deadline rather than returning cloud-unavailable.
                    log.warning("Transient GitHub run-poll error; retrying: %s", _mask(str(exc)))
                    say("Cloud status check was delayed; retrying")
                    await asyncio.sleep(min(poll, max(0.0, deadline - time.monotonic())))
                    continue
                status = (run.get("status") or "").lower()
                conclusion = (run.get("conclusion") or "").lower()
                if status == "completed":
                    if conclusion == "success":
                        break
                    log_text = await asyncio.to_thread(client.download_run_logs, int(run["id"]))
                    stderr = (
                        _render_error_excerpt(log_text)
                        if log_text else f"GitHub Actions concluded {conclusion or 'failure'}."
                    )
                    kind = _classify_failure(stderr)
                    dump = _dump_render_failure(settings.data_dir, scene.code, stderr, kind)
                    note = f"Cloud render failed [{kind}]: {stderr[-8000:]}"
                    if dump:
                        note += f"\n(full log: {dump})"
                    scene.diagnostics.append(note)
                    scene.status = "render-error"
                    scene.failure_kind = kind
                    ledger.failure(job_id, stderr, kind=kind)
                    record_metrics(
                        prepare_seconds=prepare_seconds, upload_seconds=upload_seconds,
                        dispatch_seconds=dispatch_seconds, failure_kind=kind,
                        total_seconds=time.monotonic() - total_started,
                        **_workflow_elapsed_metrics(run),
                        **_parse_runner_metrics(log_text),
                    )
                    return scene
                say(f"Cloud render {status or 'queued'}")
                sleep_deadline = time.monotonic() + poll
                while time.monotonic() < sleep_deadline:
                    ensure_active()
                    await asyncio.sleep(
                        min(0.25, max(0.0, sleep_deadline - time.monotonic()))
                    )

            if not run or (run.get("status") or "").lower() != "completed":
                cancel_id = (run or {}).get("id") or run_id
                if cancel_id:
                    try:
                        await asyncio.to_thread(client.cancel_run, int(cancel_id))
                    except Exception as exc:  # noqa: BLE001 — fallback must still proceed
                        log.info("Could not cancel timed-out cloud run %s: %s", cancel_id, exc)
                reason = (
                    f"Cloud render timed out after {effective_timeout}s "
                    f"(cost {_estimate_render_cost(scene.code):.1f}); cancelled the cloud attempt."
                )
                if str(getattr(settings, "render_mode", "local") or "local").lower() == "cloud":
                    reason += " Cloud-only mode is selected, so local fallback was skipped."
                    say("Cloud render timed out; cloud-only mode selected, local fallback skipped")
                else:
                    reason += " Falling back to local."
                    say("Cloud render timed out; falling back to local")
                _dump_render_failure(settings.data_dir, scene.code, reason, "timeout")
                ledger.failure(job_id, reason, kind="timeout")
                record_metrics(
                    prepare_seconds=prepare_seconds, upload_seconds=upload_seconds,
                    dispatch_seconds=dispatch_seconds, failure_kind="timeout",
                    total_seconds=time.monotonic() - total_started,
                    **_workflow_elapsed_metrics(run or {}),
                )
                log.warning(reason)
                return _cloud_unavailable(scene, reason)

            say("Downloading cloud video")
            current_stage = "download_logs"
            ensure_active()
            runner_logs = await asyncio.to_thread(client.download_run_logs, int(run["id"]))
            runner_metrics = _parse_runner_metrics(runner_logs)
            current_stage = "find_artifact"
            artifact = await asyncio.to_thread(client.find_run_artifact, int(run["id"]), f"{job_id}.mp4")
            if not artifact:
                scene.diagnostics.append("Cloud render succeeded but MP4 artifact was not found.")
                scene.status = "render-error"
                scene.failure_kind = "unknown"
                record_metrics(
                    prepare_seconds=prepare_seconds, upload_seconds=upload_seconds,
                    dispatch_seconds=dispatch_seconds, failure_kind="artifact_missing",
                    total_seconds=time.monotonic() - total_started,
                    **_workflow_elapsed_metrics(run),
                    **runner_metrics,
                )
                return scene
            download_started = time.monotonic()
            current_stage = "download_artifact"
            video = await asyncio.to_thread(self._download_artifact, client, artifact, run_dir, job_id)
            ensure_active()
            if not video:
                scene.diagnostics.append("Cloud MP4 artifact failed validation.")
                scene.status = "render-error"
                scene.failure_kind = "ffmpeg"
                record_metrics(
                    prepare_seconds=prepare_seconds, upload_seconds=upload_seconds,
                    dispatch_seconds=dispatch_seconds,
                    download_seconds=time.monotonic() - download_started,
                    failure_kind="artifact_invalid",
                    total_seconds=time.monotonic() - total_started,
                    **_workflow_elapsed_metrics(run),
                    **runner_metrics,
                )
                return scene
            manifest.put(job_id, {"artifact_id": artifact["id"], "run_id": run["id"]})
            scene.video_path = str(video)
            scene.status = "rendered"
            scene.failure_kind = ""
            scene.diagnostics.append(f"Rendered via GitHub Actions ({job_id}).")
            ledger.status(job_id, "artifact_downloaded", "MP4 downloaded")
            ledger.finish(job_id, "rendered", str(video))
            record_metrics(
                cache_hit=False, prepare_seconds=prepare_seconds,
                upload_seconds=upload_seconds, dispatch_seconds=dispatch_seconds,
                download_seconds=time.monotonic() - download_started,
                total_seconds=time.monotonic() - total_started,
                **_workflow_elapsed_metrics(run),
                **runner_metrics,
            )
            return scene
        except ProcessCancelledError:
            if run_id:
                try:
                    await asyncio.to_thread(client.cancel_run, int(run_id))
                except Exception as exc:  # noqa: BLE001
                    log.info("Could not cancel abandoned cloud run %s: %s", run_id, exc)
            ledger.status(job_id, "cancelled", "cancelled by user")
            raise
        except Exception as exc:  # noqa: BLE001
            cloud_only = (
                str(getattr(settings, "render_mode", "local") or "local").lower()
                == "cloud"
            )
            detail = _mask(str(exc))
            if cloud_only:
                log.warning("Cloud render unavailable; local fallback skipped: %s", detail)
                detail += " Cloud-only mode is selected, so local fallback was skipped."
            else:
                log.warning("Cloud render unavailable; falling back to local: %s", detail)
            ledger.status(job_id, "failed", detail)
            record_metrics(
                failure_kind=scene.failure_kind or "unavailable",
                failure_stage=current_stage,
                total_seconds=time.monotonic() - total_started,
            )
            return _cloud_unavailable(scene, f"Cloud render unavailable: {detail}")

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


def provision_render_repo(
    client: "GitHubActionsClient",
    *,
    branch: str = DEFAULT_GITHUB_BRANCH,
    workflow: str = DEFAULT_GITHUB_WORKFLOW,
) -> str:
    """Make a render repo dispatch-ready (idempotent).

    GitHub only lets the REST API dispatch a workflow that exists on the repo's
    DEFAULT branch, and the dispatched ``ref`` runs that branch's copy of the
    file — so install the bundled workflow on BOTH the default branch and the
    render branch. Without this, dispatch 404s ("workflow not found") on every
    otherwise-correctly-configured repo — the real reason cloud render reported
    "unavailable". Returns a short human status.
    """
    try:
        workflow = _workflow_name(workflow)
        default = client.default_branch()
        wrote = client.ensure_workflow(workflow=workflow, branch=default)
        client.ensure_branch(branch)
        if branch != default:
            wrote = client.ensure_workflow(workflow=workflow, branch=branch) or wrote
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise RuntimeError(
                "GitHub token lacks the 'workflow' scope required to install the "
                "render workflow. Use the in-app 'Get token' device login, or a "
                "token with 'repo' + 'workflow' scope."
            ) from exc
        raise
    return "Render workflow installed." if wrote else "Render workflow already present."


def render_timeout_for(code: str, quality: str, settings: "AppSettings") -> int:
    from aetherlab.services.manim_runtime import _estimate_render_cost

    if str(getattr(settings, "render_mode", "local") or "local").lower() in {"cloud", "auto"}:
        configured = max(60, min(1800, int(getattr(settings, "cloud_render_timeout", 600) or 600)))
        base = {"l": 420, "m": 540, "h": 720, "k": 900}.get(quality, 420)
        cost = _estimate_render_cost(code)
        adaptive = base + int(max(0.0, min(4.0, cost - 1.0)) * 60)
        return min(configured, adaptive)
    base_timeout = {"l": 240, "m": 420, "h": 600, "k": 900}.get(quality, 240)
    return min(int(base_timeout * _estimate_render_cost(code)), 1800)


def render_fps_for(code: str, quality: str) -> int:
    from aetherlab.services.manim_runtime import _RENDER_TIER, _estimate_render_cost

    fps = int(_RENDER_TIER["fps"])
    if _estimate_render_cost(code) >= 3.0 and quality in ("h", "k"):
        fps = 30
    return fps


def cloud_job_id(scene: SceneBundle, *, quality: str, fps: int, variant: str = "") -> str:
    """Content-addressed cloud job id (also the cloud cache key).

    ``variant`` salts the id so concurrent tournament candidates with
    byte-identical code never collide on the same ``jobs/<id>.py`` scene file
    or steal each other's ``<id>.mp4`` artifact (the BUG-15 race under
    concurrency). An empty variant leaves the hash byte-identical to the legacy
    id, so the single-scene path keeps hitting its existing cloud cache.
    """
    parts = [
        scene.class_name,
        scene.code,
        quality,
        str(fps),
        f"manim=={MANIM_VERSION_PIN}",
        f"workflow={CLOUD_WORKFLOW_VERSION}",
    ]
    if variant:
        parts.append(f"variant={variant}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:24]


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
    token = str(getattr(settings, "github_token", "") or "").strip()
    if token:
        return token
    return _github_cli_token()


@lru_cache(maxsize=1)
def _github_cli_token() -> str:
    """Return the active GitHub CLI token, if the user already ran gh auth login."""
    exe = shutil.which("gh")
    if not exe:
        return ""
    try:
        from aetherlab.core.proc import subprocess_kwargs

        result = subprocess.run(
            [exe, "auth", "token"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            **subprocess_kwargs(),
        )
    except Exception:  # noqa: BLE001
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


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


def _workflow_name(value: str | None) -> str:
    name = Path(str(value or DEFAULT_GITHUB_WORKFLOW).strip()).name
    return name or DEFAULT_GITHUB_WORKFLOW


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
            workflow=_workflow_name(getattr(settings, "github_workflow", DEFAULT_GITHUB_WORKFLOW)),
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
        with _branch_write_lock(self.owner, self.repo, branch):
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
            try:
                self._request(
                    "POST",
                    f"/repos/{self.owner}/{self.repo}/git/refs",
                    {"ref": f"refs/heads/{branch}", "sha": sha},
                )
            except urllib.error.HTTPError as exc:
                if exc.code != 422:
                    raise
                # Another process may have created it after our initial GET.
                self._request(
                    "GET",
                    f"/repos/{self.owner}/{self.repo}/git/ref/heads/{urllib.parse.quote(branch, safe='')}",
                )

    def put_file(self, path: str, content: str, *, branch: str, message: str) -> None:
        quoted = urllib.parse.quote(path)
        lock = _branch_write_lock(self.owner, self.repo, branch)
        for attempt in range(3):
            try:
                with lock:
                    sha = None
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
                return
            except urllib.error.HTTPError as exc:
                if exc.code != 409 or attempt == 2:
                    raise
                time.sleep(0.2 * (2 ** attempt))

    def cancel_run(self, run_id: int) -> None:
        """Best-effort cancellation for a run that exceeded AetherLab's budget."""
        try:
            self._request(
                "POST",
                f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/cancel",
            )
        except urllib.error.HTTPError as exc:
            if exc.code not in {409, 422}:
                raise

    def default_branch(self) -> str:
        return str(self._request("GET", f"/repos/{self.owner}/{self.repo}").get("default_branch", "main"))

    def file_content(self, path: str, *, branch: str) -> str | None:
        """Return the decoded text of a repo file, or None if it does not exist."""
        quoted = urllib.parse.quote(path)
        try:
            info = self._request(
                "GET",
                f"/repos/{self.owner}/{self.repo}/contents/{quoted}?ref={urllib.parse.quote(branch)}",
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        raw = info.get("content", "")
        try:
            return base64.b64decode(raw).decode("utf-8") if raw else ""
        except Exception:  # noqa: BLE001
            return ""

    def ensure_workflow(self, *, workflow: str = DEFAULT_GITHUB_WORKFLOW, branch: str) -> bool:
        """Install/update ``.github/workflows/<workflow>`` on ``branch`` if its
        content differs from the bundled workflow. Returns True if it wrote."""
        workflow = _workflow_name(workflow)
        path = f".github/workflows/{workflow}"
        current = self.file_content(path, branch=branch)
        if current is not None and current.strip() == RENDER_WORKFLOW_YAML.strip():
            return False
        self.put_file(
            path, RENDER_WORKFLOW_YAML, branch=branch,
            message="AetherLab: install cloud render workflow",
        )
        return True

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
        return self._download_redirecting_raw(
            f"/repos/{self.owner}/{self.repo}/actions/artifacts/{artifact_id}/zip"
        )

    def download_run_logs(self, run_id: int) -> str:
        try:
            data = self._download_redirecting_raw(
                f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/logs"
            )
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

    def _download_redirecting_raw(self, path: str) -> bytes:
        """Download endpoints that return a short-lived signed storage URL.

        GitHub artifact/log APIs respond with 302. The redirected URL points at
        object storage and must be fetched without the GitHub Bearer token.
        """
        url = self.api_base.rstrip("/") + path
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("X-GitHub-Api-Version", "2026-03-10")

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=30) as resp:  # noqa: S310
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in {301, 302, 303, 307, 308}:
                raise
            location = exc.headers.get("Location")
            if not location:
                raise
        signed = urllib.request.Request(location, method="GET")
        with urllib.request.urlopen(signed, timeout=120) as resp:  # noqa: S310
            return resp.read()


class CloudRenderManifest:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict:
        with path_lock(self.path):
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            except (OSError, json.JSONDecodeError):
                return {}
        return payload if isinstance(payload, dict) else {}

    def get(self, job_id: str) -> dict | None:
        item = self._load().get(job_id)
        return item if isinstance(item, dict) else None

    def put(self, job_id: str, data: dict) -> None:
        with path_lock(self.path):
            payload = self._load()
            payload[job_id] = data
            try:
                atomic_write_json(self.path, payload)
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
