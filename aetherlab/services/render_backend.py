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
import uuid
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
CLOUD_WORKFLOW_VERSION = "8"  # explicit canvas/FPS transport and artifact validation
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
    output_failure = re.search(r"(?m)^Expected one final MP4 for scene [^;\r\n]+; found \d+\s*$", text)
    if output_failure:
        return output_failure.group().strip()[-limit:]
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
        options: [l, m, h, p, k]
      fps:
        description: Frames per second
        required: true
        default: "30"
        type: string
      width:
        description: Explicit even canvas width (0 uses quality default)
        required: false
        default: "0"
        type: string
      height:
        description: Explicit even canvas height (0 uses quality default)
        required: false
        default: "0"
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
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v5
        with:
          ref: ${{ github.ref_name }}

      - uses: actions/setup-python@v6
        with:
          python-version: "3.14"

      - name: Install system render dependencies
        timeout-minutes: 7
        run: |
          sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 \
            -o Acquire::https::Timeout=30 update
          sudo apt-get install -y --no-install-recommends \
            libcairo2-dev libpango1.0-dev pkg-config
          if [ "${{ inputs.needs_latex }}" = "true" ]; then
            sudo apt-get install -y --no-install-recommends \
              texlive-latex-extra dvisvgm
          fi

      - name: Install pinned Manim
        run: |
          python -m pip install --upgrade pip
          python -m pip install "manim==0.21.0" "imageio-ffmpeg==0.6.0"
          python - <<'PY'
          import importlib.metadata as m
          import os
          from pathlib import Path
          import imageio_ffmpeg

          ffmpeg_dir = Path(os.environ["RUNNER_TEMP"]) / "aetherlab-bin"
          ffmpeg_dir.mkdir(parents=True, exist_ok=True)
          (ffmpeg_dir / "ffmpeg").symlink_to(imageio_ffmpeg.get_ffmpeg_exe())
          with Path(os.environ["GITHUB_PATH"]).open("a", encoding="utf-8") as path_file:
              path_file.write(str(ffmpeg_dir) + "\n")
          print("manim", m.version("manim"))
          print("ffmpeg", imageio_ffmpeg.get_ffmpeg_exe())
          PY

      - name: Render scene
        id: render
        shell: bash
        env:
          SCENE_CLASS: ${{ inputs.class_name }}
          RENDER_JOB_ID: ${{ inputs.job_id }}
          RENDER_WIDTH: ${{ inputs.width }}
          RENDER_HEIGHT: ${{ inputs.height }}
        run: |
          set +e
          mkdir -p out
          size_args=()
          if [ "${RENDER_WIDTH:-0}" != "0" ] || [ "${RENDER_HEIGHT:-0}" != "0" ]; then
            if [[ ! "$RENDER_WIDTH" =~ ^[1-9][0-9]{2,3}$ ]] || [[ ! "$RENDER_HEIGHT" =~ ^[1-9][0-9]{2,3}$ ]]; then
              echo 'Invalid render canvas: supply both even dimensions.' >&2
              exit 2
            fi
            if (( RENDER_WIDTH < 320 || RENDER_WIDTH > 3840 || RENDER_HEIGHT < 240 || RENDER_HEIGHT > 2160 || RENDER_WIDTH % 2 || RENDER_HEIGHT % 2 )); then
              echo 'Invalid render canvas: expected even width 320..3840 and height 240..2160.' >&2
              exit 2
            fi
            size_args=(-r "${RENDER_WIDTH},${RENDER_HEIGHT}")
          fi
          /usr/bin/time -f 'AETHERLAB_RENDER_WALL_SECONDS=%e\nAETHERLAB_PEAK_RSS_KB=%M' \
            -o "${{ inputs.job_id }}.telemetry" python -m manim render \
            -q${{ inputs.quality }} \
            --fps "${{ inputs.fps }}" \
            "${size_args[@]}" \
            --disable_caching \
            --media_dir out \
            "${{ inputs.scene_path }}" \
            "${{ inputs.class_name }}" 2>&1 | tee "${{ inputs.job_id }}.log"
          code=${PIPESTATUS[0]}
          cat "${{ inputs.job_id }}.telemetry" | tee -a "${{ inputs.job_id }}.log"
          if [ "$code" -ne 0 ]; then
            exit "$code"
          fi
          # Select exactly one final output for the requested scene.
          # A larger unrelated video or partial fragment is never a substitute.
          python - <<'PY'
          import os
          import shutil
          import sys
          from pathlib import Path

          scene_class = os.environ["SCENE_CLASS"]
          matches = [
              path for path in Path("out/videos").rglob("*.mp4")
              if path.name == f"{scene_class}.mp4"
              and "partial_movie_files" not in path.parts
          ]
          if len(matches) != 1:
              message = f"Expected one final MP4 for scene {scene_class}; found {len(matches)}"
              print(message, file=sys.stderr)
              with Path(f"{os.environ['RENDER_JOB_ID']}.log").open("a", encoding="utf-8") as output:
                  output.write(message + "\n")
              sys.exit(2)
          shutil.copyfile(matches[0], f"{os.environ['RENDER_JOB_ID']}.mp4")
          PY

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

        # Agent 1: single RenderProfile source of truth (was duplicated
        # fps-reduction policy). Resolved quality/fps propagate to the cloud
        # workflow inputs below; any adaptive fallback is reported.
        profile, _fallback_notice = render_profile_for(scene.code, quality, settings)
        quality = str(getattr(profile, "quality", quality) or quality)
        fps = int(getattr(profile, "fps", 30))
        width, height = int(profile.width), int(profile.height)
        if profile.renderer != "cairo":
            scene.diagnostics.append(
                "Cloud runner uses Cairo; requested OpenGL is unavailable in cloud. "
                "Rendering with Cairo while preserving the requested canvas and FPS."
            )
        if _fallback_notice:
            scene.diagnostics.append(_fallback_notice)
            log.warning("%s", _fallback_notice)
        job_id = cloud_job_id(scene, quality=quality, fps=fps, variant=variant, width=width, height=height)
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
            video = await asyncio.to_thread(self._download_cached, client, manifest, job_id, run_dir, cached, quality,
                                            width=width, height=height, fps=fps)
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
                width=width,
                height=height,
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
            was_rate_limited = False
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
                    remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
                    rate_limited = exc.code == 429 or (
                        exc.code == 403 and str(remaining or "").strip() == "0"
                    )
                    if exc.code not in {408, 425, 429, 500, 502, 503, 504} and not rate_limited:
                        raise
                    log.warning("Transient GitHub run-poll response %s; retrying", exc.code)
                    say("Cloud status check was delayed; retrying")
                    delay = float(poll)
                    if rate_limited:
                        was_rate_limited = True
                        retry_after = exc.headers.get("Retry-After") if exc.headers else None
                        try:
                            delay = max(1.0, float(retry_after)) if retry_after else delay
                        except (TypeError, ValueError):
                            pass
                        ledger.status(job_id, "rate_limited", f"GitHub API rate limit; retrying in {delay:g}s.")
                    await asyncio.sleep(min(delay, max(0.0, deadline - time.monotonic())))
                    continue
                except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as exc:
                    # A status-read timeout does not mean the remote render failed.
                    # GitHub Actions continues independently, so retry within the
                    # existing render deadline rather than returning cloud-unavailable.
                    log.warning("Transient GitHub run-poll error; retrying: %s", _mask(str(exc)))
                    say("Cloud status check was delayed; retrying")
                    await asyncio.sleep(min(poll, max(0.0, deadline - time.monotonic())))
                    continue
                if was_rate_limited:
                    ledger.status(job_id, "in_progress", "GitHub status polling resumed after rate limit.")
                    was_rate_limited = False
                status = (run.get("status") or "").lower()
                conclusion = (run.get("conclusion") or "").lower()
                if status == "completed":
                    if conclusion == "success":
                        run_page = safe_github_run_url(settings, run)
                        if run_page:
                            ledger.urls(job_id, run_url=run_page)
                        ledger.status(job_id, "completed", "GitHub Actions workflow completed successfully.")
                        break
                    run_page = safe_github_run_url(settings, run)
                    if run_page:
                        ledger.urls(job_id, run_url=run_page)
                    log_text = await asyncio.to_thread(client.download_run_logs, int(run["id"]))
                    stderr = (
                        _render_error_excerpt(log_text)
                        if log_text else f"GitHub Actions concluded {conclusion or 'failure'}."
                    )
                    kind = _classify_failure(stderr)
                    if kind == "artifact_missing":
                        scene.diagnostics.append(
                            "Cloud output missing: the requested scene produced no final MP4. "
                            "Check that the scene contains a timed animation or wait, then retry."
                        )
                    elif kind == "artifact_ambiguous":
                        scene.diagnostics.append(
                            "Cloud output ambiguous: multiple final MP4s match the requested scene. "
                            "Check worker output isolation, then retry."
                        )
                    if _note_missing_latex(log_text or ""):
                        scene.diagnostics.append(
                            "The cloud runner had no LaTeX for this scene; later cloud "
                            "renders will install it."
                        )
                    dump = _dump_render_failure(settings.data_dir, scene.code, stderr, kind)
                    note = f"Cloud render failed [{kind}]: {stderr[-8000:]}"
                    if dump:
                        note += f"\n(full log: {dump})"
                    scene.diagnostics.append(_mask(note))
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

            run_page = safe_github_run_url(settings, run)
            if run_page:
                ledger.urls(job_id, run_url=run_page)

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
                scene.failure_kind = "artifact_missing"
                ledger.failure(job_id, "Cloud render succeeded but MP4 artifact was not found.", kind="artifact_missing")
                record_metrics(
                    prepare_seconds=prepare_seconds, upload_seconds=upload_seconds,
                    dispatch_seconds=dispatch_seconds, failure_kind="artifact_missing",
                    total_seconds=time.monotonic() - total_started,
                    **_workflow_elapsed_metrics(run),
                    **runner_metrics,
                )
                return scene
            artifact_page = safe_github_artifact_url(settings, run, artifact)
            if artifact_page:
                ledger.urls(job_id, artifact_url=artifact_page)
            download_started = time.monotonic()
            current_stage = "download_artifact"
            video, reject_reason = await asyncio.to_thread(
                self._download_artifact, client, artifact, run_dir, job_id, quality,
                width=width, height=height, fps=fps,
            )
            ensure_active()
            if not video:
                detail = f"Cloud MP4 artifact failed validation: {reject_reason}."
                scene.diagnostics.append(detail)
                scene.status = "render-error"
                scene.failure_kind = "artifact_invalid"
                ledger.failure(job_id, detail, kind="artifact_invalid")
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
            manifest.put(job_id, {"artifact_id": artifact["id"], "run_id": run["id"],
                                  "width": width, "height": height, "fps": fps})
            scene.video_path = str(video)
            scene.status = "rendered"
            scene.failure_kind = ""
            scene.diagnostics.append(f"Rendered via GitHub Actions ({job_id}).")
            ledger.status(job_id, "artifact_downloaded", "MP4 downloaded and validated")
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
            if isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403}:
                detail = (
                    "GitHub denied access (HTTP " + str(exc.code)
                    + "); check that the token can access the repository, workflow, and Actions runs."
                )
            if cloud_only:
                log.warning("Cloud render unavailable; local fallback skipped: %s", detail)
                detail += " Cloud-only mode is selected, so local fallback was skipped."
            else:
                log.warning("Cloud render unavailable; falling back to local: %s", detail)
            if _is_token_scope_failure(exc, detail):
                ledger.failure(job_id, detail, kind="token_scope", status="action_required")
            else:
                ledger.failure(job_id, detail, kind=current_stage)
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
        quality: str,
        *, width: int = 0, height: int = 0, fps: int = 0,
    ) -> Path | None:
        if cached and cached.get("artifact_id"):
            try:
                artifact = client.get_artifact(int(cached["artifact_id"]))
                if artifact and not artifact.get("expired"):
                    video, _ = self._download_artifact(client, artifact, run_dir, job_id, quality,
                                                      width=width, height=height, fps=fps)
                    return video
            except Exception:  # noqa: BLE001
                pass
        artifact = client.find_repo_artifact(f"{job_id}.mp4")
        if artifact and not artifact.get("expired"):
            manifest.put(job_id, {"artifact_id": artifact["id"], "run_id": artifact.get("workflow_run", {}).get("id")})
            video, _ = self._download_artifact(client, artifact, run_dir, job_id, quality,
                                              width=width, height=height, fps=fps)
            return video
        return None

    def _download_artifact(
        self,
        client: "GitHubActionsClient",
        artifact: dict,
        run_dir: Path,
        job_id: str,
        quality: str,
        *, width: int = 0, height: int = 0, fps: int = 0,
    ) -> tuple[Path | None, str]:
        """Download one MP4 artifact; the reason is "" on success."""
        data = client.download_artifact_zip(int(artifact["id"]))
        with zipfile.ZipFile(BytesReader(data)) as zf:
            for name in zf.namelist():
                target = Path(name)
                if target.name != f"{job_id}.mp4" or target.is_absolute() or ".." in target.parts:
                    continue
                out = run_dir / target.name
                staged = run_dir / f".{job_id}.{uuid.uuid4().hex}.mp4"
                try:
                    staged.write_bytes(zf.read(name))
                    if not validate_mp4(staged):
                        return None, "not an MP4 container (ftyp missing)"
                    ok, reason = self._profile_matches(staged, quality, width=width, height=height, fps=fps)
                    if not ok:
                        return None, reason
                    staged.replace(out)
                    return out, ""
                finally:
                    staged.unlink(missing_ok=True)
        return None, "job MP4 missing from the artifact zip"

    @staticmethod
    def _profile_matches(path: Path, quality: str, *, width: int = 0,
                         height: int = 0, fps: int = 0) -> tuple[bool, str]:
        """Deep media gate: a video stream, a positive duration, and the
        requested canvas/FPS (quality defaults for legacy callers), and a
        decodable frame. It does not certify every frame of the video."""
        facts = probe_mp4(path)
        if facts is None:
            return False, "video validation unavailable: install or repair PyAV (av) and retry"
        if facts["video_streams"] < 1:
            return False, "no video stream in the downloaded MP4"
        if facts["duration_s"] <= 0:
            return False, "downloaded MP4 has no measurable duration"
        if not facts["decoded_frame"]:
            return False, "downloaded MP4 has no decodable video frame"
        expected = (width, height) if width > 0 and height > 0 else CLOUD_QUALITY_DIMS.get(quality)
        actual = (facts["width"], facts["height"])
        if expected is not None and actual != expected:
            return False, (
                f"resolution {actual[0]}x{actual[1]}, expected "
                f"{expected[0]}x{expected[1]} for quality '{quality}'"
            )
        if fps > 0:
            import math
            actual_fps = float(facts.get("fps", 0) or 0)
            if not math.isfinite(actual_fps) or abs(actual_fps - fps) > 0.1:
                return False, f"frame rate {actual_fps:g} fps, expected {fps} fps"
        return True, ""


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
        base = {"l": 420, "m": 540, "h": 720, "p": 810, "k": 900}.get(quality, 420)
        cost = _estimate_render_cost(code)
        adaptive = base + int(max(0.0, min(4.0, cost - 1.0)) * 60)
        return min(configured, adaptive)
    base_timeout = {"l": 240, "m": 420, "h": 600, "p": 750, "k": 900}.get(quality, 240)
    return min(int(base_timeout * _estimate_render_cost(code)), 1800)


def render_profile_for(
    code: str, quality: str, settings: object | None = None
) -> tuple[object, str | None]:
    """Resolve (RenderProfile, fallback_notice) — single source of truth.

    Agent 1: replaces the duplicated fps-reduction policy that used to live
    here AND in manim_runtime. Adaptive fallback is reported, never silent.
    """
    from aetherlab.core.render_profile import adapt_profile_for_cost, get_effective_profile
    from aetherlab.services.manim_runtime import _estimate_render_cost

    profile = get_effective_profile(settings, quality=quality)
    return adapt_profile_for_cost(profile, _estimate_render_cost(code))


def render_fps_for(code: str, quality: str, settings: object | None = None) -> int:
    """Legacy fps helper — delegates to RenderProfile (kept for importers)."""
    profile, notice = render_profile_for(code, quality, settings)
    if notice:
        log.warning("%s", notice)
    return int(getattr(profile, "fps", 30))


def cloud_job_id(scene: SceneBundle, *, quality: str, fps: int, variant: str = "",
                 width: int = 0, height: int = 0) -> str:
    """Content-addressed cloud job id (also the cloud cache key).

    ``variant`` salts the id so concurrent tournament candidates with
    byte-identical code never collide on the same ``jobs/<id>.py`` scene file
    or steal each other's ``<id>.mp4`` artifact (the BUG-15 race under
    concurrency). Canvas dimensions and workflow version distinguish profiles
    and prevent reusing an artifact from an older output contract.
    """
    dimensions = (width, height) if width > 0 and height > 0 else CLOUD_QUALITY_DIMS.get(quality, (1280, 720))
    parts = [
        scene.class_name,
        scene.code,
        quality,
        str(fps),
        f"canvas={dimensions[0]}x{dimensions[1]}",
        f"manim=={MANIM_VERSION_PIN}",
        f"workflow={CLOUD_WORKFLOW_VERSION}",
    ]
    if variant:
        parts.append(f"variant={variant}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:24]


def cloud_job_id_for_profile(scene: SceneBundle, quality: str, settings: object,
                             variant: str = "") -> str:
    """Use the same resolved canvas/FPS for lookup, dispatch and ledger IDs."""
    profile, _ = render_profile_for(scene.code, quality, settings)
    return cloud_job_id(scene, quality=profile.quality, fps=profile.fps,
                        width=profile.width, height=profile.height, variant=variant)


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
        with path.open("rb") as video:
            size = os.fstat(video.fileno()).st_size
            header = video.read(64)
    except OSError:
        return False
    return size > 128 and b"ftyp" in header


# Pinned-Manim (0.21.0) output dimensions per quality flag. A cloud MP4 that
# comes back at the wrong profile is rejected instead of silently shipping.
# Agent 1: single source of truth lives in render_profile.QUALITY_DIMS.
try:
    from aetherlab.core.render_profile import QUALITY_DIMS as CLOUD_QUALITY_DIMS
except Exception:  # pragma: no cover — import fallback, never silent wrong dims
    CLOUD_QUALITY_DIMS = {
        "l": (854, 480),
        "m": (1280, 720),
        "h": (1920, 1080),
        "p": (2560, 1440),
        "k": (3840, 2160),
    }


def probe_mp4(path: Path) -> dict[str, float | int] | None:
    """Video-stream facts for a downloaded MP4.

    None when PyAV cannot load; callers must not certify the video in that case.
    Invalid files report zero facts. Sampling one decoded frame verifies actual
    video data without reading every frame of a long lesson into memory.
    """
    try:
        import av
    except Exception:  # noqa: BLE001 — missing/broken decoder is diagnosed by caller
        return None
    try:
        with av.open(str(path)) as container:
            video = container.streams.video
            if not video:
                return {"video_streams": 0, "duration_s": 0.0, "width": 0, "height": 0, "decoded_frame": 0}
            stream = video[0]
            try:
                frame_rate = float(getattr(stream, "average_rate", None) or 0)
            except (TypeError, ValueError, OverflowError):
                frame_rate = 0.0
            duration = 0.0
            if stream.duration and stream.time_base:
                duration = float(stream.duration * stream.time_base)
            elif container.duration:
                duration = container.duration / 1_000_000.0
            return {
                "video_streams": len(video),
                "duration_s": duration,
                "width": int(stream.width or 0),
                "height": int(stream.height or 0),
                "fps": frame_rate,
                "decoded_frame": int(next(container.decode(video=0), None) is not None),
            }
    except Exception:  # noqa: BLE001 — undecodable file reads as no facts
        return {"video_streams": 0, "duration_s": 0.0, "width": 0, "height": 0, "decoded_frame": 0}


# Manim objects that typeset with LaTeX internally. A render that uses one
# without LaTeX installed dies with FileNotFoundError: 'latex' (live
# 2026-10-02: a DecimalNumber readout failed three cloud renders in a row).
_LATEX_CONSTRUCTORS = re.compile(
    r"\b(?:MathTex|Tex|SingleStringMathTex|TexTemplate|DecimalNumber|Integer|Variable"
    r"|Matrix|IntegerMatrix|DecimalMatrix|MobjectMatrix|MathTable|DecimalTable"
    r"|IntegerTable|BarChart|BraceLabel|BraceText|Title|BulletedList)\s*\("
)
_LATEX_HELPERS = re.compile(
    r"\b(?:include_numbers|numbers_to_include|add_coordinates|get_axis_labels"
    r"|get_x_axis_label|get_y_axis_label|get_axis_label|get_graph_label|get_tex"
    r"|decimal_number_config)\b|\.get_text\("
)
# Set once a cloud render fails for lack of LaTeX; later renders in this
# process (render repairs, other segments) then always install it.
_latex_missing_seen = False


def _needs_latex(code: str) -> bool:
    if _latex_missing_seen:
        return True
    return bool(_LATEX_CONSTRUCTORS.search(code) or _LATEX_HELPERS.search(code))


def _note_missing_latex(log_text: str) -> bool:
    """Remember a render that failed because the runner had no LaTeX."""
    global _latex_missing_seen
    if re.search(r"No such file or directory: '(?:latex|dvisvgm)'", log_text or ""):
        _latex_missing_seen = True
        return True
    return False


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
    from aetherlab.services.render_ledger import scrub

    # Keep the render diagnostic's historical short-token protection too;
    # fixture credentials and truncated provider errors can be shorter than
    # the ledger's conservative high-confidence patterns.
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "<redacted>", str(text))
    text = re.sub(r"gh[pousr]_[A-Za-z0-9_]{8,}", "<redacted>", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "<redacted>", text)
    return scrub(text)


def _is_token_scope_failure(exc: Exception, detail: str) -> bool:
    if isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403}:
        remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
        if not (exc.code == 403 and str(remaining or "").strip() == "0"):
            return True
    text = f"{type(exc).__name__}: {detail}".lower()
    return any(marker in text for marker in (
        "lacks the 'workflow' scope", "insufficient scope", "resource not accessible",
        "workflow scope", "token scope", "permission to", "not authorized",
    ))


def safe_github_run_url(settings: "AppSettings", run: dict) -> str:
    """Return a validated human-facing URL for a GitHub Actions run."""
    from aetherlab.services.render_ledger import safe_github_url

    repo = str(getattr(settings, "github_repo", "") or "").strip()
    run_id = run.get("id")
    candidate = str(run.get("html_url", "") or "")
    if not candidate and repo and str(run_id or "").isdigit():
        candidate = f"https://github.com/{repo}/actions/runs/{run_id}"
    return safe_github_url(candidate)


def safe_github_artifact_url(settings: "AppSettings", run: dict, artifact: dict) -> str:
    """Build a safe artifact page link; never persist GitHub's signed ZIP URL."""
    from aetherlab.services.render_ledger import safe_github_url

    repo = str(getattr(settings, "github_repo", "") or "").strip()
    run_id, artifact_id = run.get("id"), artifact.get("id")
    if not repo or not str(run_id or "").isdigit() or not str(artifact_id or "").isdigit():
        return ""
    return safe_github_url(
        f"https://github.com/{repo}/actions/runs/{run_id}/artifacts/{artifact_id}"
    )


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
        width: int = 0,
        height: int = 0,
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
                    "width": str(width),
                    "height": str(height),
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
