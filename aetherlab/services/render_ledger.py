"""Render-farm job ledger — an observable, secret-scrubbed record of renders.

The Quality Flywheel's cloud backend can provision, dispatch, poll, download,
score N tournament candidates, and fall back to local — but until now none of
that was *visible*. This module records a stable, JSON-persisted ledger of render
jobs (and the per-candidate tournament that produced each winner) so a user or
maintainer can see what queued, what ran, what failed, which artifact was
downloaded, and why a local fallback happened.

Design constraints, mirroring the other flywheel leaves (error_learner,
scene_exemplars):
- **Standard library only**, no project imports — a safe, isolated, testable leaf.
- **Fail-soft**: no method raises into the render pipeline.
- **No secrets**: every free-text field (status detail, failure log tail,
  fallback reason) is scrubbed of tokens/keys before it is persisted.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from aetherlab.core.atomic_json import atomic_write_json, path_lock

log = logging.getLogger(__name__)

# The lifecycle states a render job (or a candidate) can move through. Kept as a
# documented set the UI can render and tests can assert against.
STATUSES: frozenset[str] = frozenset({
    "queued",
    "in_progress",
    "completed",
    "failed",
    "cancelled",
    "action_required",
    "rate_limited",
    "artifact_downloaded",
    "fallback_local",
    "rendered",
})

_MAX_JOBS = 50
_LOG_TAIL_CHARS = 4000

# Secret shapes to redact from any persisted free text. Deliberately broad — a
# ledger is meant to be shown and shared, so err toward over-redaction.
_SECRET_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----[\s\S]*?-----END[^-]*-----"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\b\s*[=:]\s*[^\s'\"]+"),
)

_REDACTED = "<redacted>"


def scrub(text: str) -> str:
    """Redact anything that looks like a credential from free text."""
    out = str(text or "")
    for pattern in _SECRET_RES:
        out = pattern.sub(_REDACTED, out)
    return out


_SAFE_GITHUB_PATH = re.compile(
    r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+(?:/artifacts/\d+)?$"
)


def safe_github_url(value: object) -> str:
    """Return only a credential-free GitHub Actions run/artifact page URL."""
    candidate = str(value or "")
    try:
        parsed = urlsplit(candidate)
        if (
            parsed.scheme == "https"
            and parsed.netloc.lower() == "github.com"
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and _SAFE_GITHUB_PATH.fullmatch(parsed.path)
        ):
            return f"https://github.com{parsed.path}"
    except (TypeError, ValueError):
        pass
    return ""


@dataclass
class LedgerEvent:
    status: str
    at: str
    detail: str = ""


@dataclass
class JobRecord:
    job_id: str
    scene_class: str = ""
    quality: str = ""
    fps: int = 0
    backend: str = ""
    provider: str = ""
    status: str = "queued"
    timeline: list[dict] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)  # {index, score, verdict, breakdown?}
    winner_index: int | None = None
    # Tournament economics + the draft->HQ pair the ledger report mines (F181):
    # the winner is SELECTED on its cheap 480p draft score (stored in candidates),
    # then re-critiqued at HQ in the repair loop — winner_hq_score is that final
    # score, so the report can measure whether the cheap proxy predicts reality.
    difficulty: float = 0.0
    budget: int = 0
    winner_hq_score: float = 0.0
    winner_hq_verdict: str = ""
    log_tail: str = ""
    fallback_reason: str = ""
    run_url: str = ""
    artifact_url: str = ""
    final_path: str = ""
    created_at: str = ""
    updated_at: str = ""
    metrics: dict[str, float | int | str | bool] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalise_record(row: dict) -> dict:
    """Make a persisted row safe for mutations and dashboard/report readers."""
    def clean(value):
        if isinstance(value, str):
            return scrub(value)
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, dict):
            return {scrub(str(key)): clean(item) for key, item in value.items()}
        return value

    job_id = scrub(str(row.get("job_id", "")))
    defaults = asdict(JobRecord(job_id=job_id, created_at=str(row.get("created_at", ""))))
    record = clean({**defaults, **row, "job_id": job_id})
    if not isinstance(record.get("status"), str) or record.get("status") not in STATUSES:
        record["status"] = "failed"
    record["timeline"] = [
        event for event in record.get("timeline", []) if isinstance(event, dict)
    ] if isinstance(record.get("timeline"), list) else []
    record["candidates"] = [
        candidate for candidate in record.get("candidates", []) if isinstance(candidate, dict)
    ] if isinstance(record.get("candidates"), list) else []
    record["metrics"] = dict(record.get("metrics", {})) if isinstance(record.get("metrics"), dict) else {}
    record["run_url"] = safe_github_url(record.get("run_url"))
    record["artifact_url"] = safe_github_url(record.get("artifact_url"))
    winner = record.get("winner_index")
    try:
        record["winner_index"] = int(winner) if winner is not None else None
    except (TypeError, ValueError):
        record["winner_index"] = None
    return record


class RenderJobLedger:
    """JSON-backed, fail-soft, secret-scrubbed ledger of render jobs."""

    def __init__(self, path: Path | None = None, *, max_jobs: int = _MAX_JOBS) -> None:
        self.path = Path(path) if path else None
        self.max_jobs = max_jobs

    # -- persistence (never raises) -------------------------------------------
    def _load(self) -> list[dict]:
        if not self.path or not self.path.exists():
            return []
        with path_lock(self.path):
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return [
                    _normalise_record(row) for row in data if isinstance(row, dict)
                ] if isinstance(data, list) else []
            except Exception as exc:  # noqa: BLE001 — corruption must not break renders
                log.debug("render ledger unreadable, starting fresh: %s", exc)
                return []

    def _save(self, jobs: list[dict]) -> None:
        if not self.path:
            return
        with path_lock(self.path):
            try:
                atomic_write_json(self.path, jobs[: self.max_jobs])
            except Exception as exc:  # noqa: BLE001 — persistence is best-effort
                log.debug("could not persist render ledger: %s", exc)

    def _mutate(self, job_id: str, apply) -> None:
        """Load, find-or-create the job, apply a mutation, and persist. Fail-soft."""
        if not job_id:
            return
        job_id = scrub(str(job_id))
        try:
            if not self.path:
                return
            with path_lock(self.path):
                jobs = self._load()
                record = next((j for j in jobs if j.get("job_id") == job_id), None)
                if record is None:
                    record = asdict(JobRecord(job_id=job_id, created_at=_now()))
                    jobs.insert(0, record)
                apply(record)
                record["updated_at"] = _now()
                self._save(jobs)
        except Exception as exc:  # noqa: BLE001 — observability must never break a render
            log.debug("render ledger update failed: %s", exc)

    # -- public API -----------------------------------------------------------
    def start(self, *, job_id: str, scene_class: str = "", quality: str = "",
              fps: int = 0, backend: str = "", provider: str = "") -> None:
        def _apply(r: dict) -> None:
            r.update({
                "scene_class": scrub(str(scene_class)), "quality": scrub(str(quality)),
                "fps": int(fps or 0), "backend": scrub(str(backend)),
                "provider": scrub(str(provider)), "status": "queued",
            })
            # Job ids are content-addressed, so a local and a cloud render of
            # the same scene share a row. Each attempt starts with clean
            # metrics instead of inheriting the previous backend's fields.
            r["metrics"] = {}
            r["timeline"].append(asdict(LedgerEvent("queued", _now())))
        self._mutate(job_id, _apply)

    def status(self, job_id: str, status: str, detail: str = "") -> None:
        status = str(status)
        status = status if status in STATUSES else "failed"
        def _apply(r: dict) -> None:
            r["status"] = status
            r["timeline"].append(asdict(LedgerEvent(status, _now(), scrub(detail))))
        self._mutate(job_id, _apply)

    def candidates(self, job_id: str, entries: list[dict]) -> None:
        def _apply(r: dict) -> None:
            r["candidates"] = [
                {
                    "index": int(e.get("index", i)),
                    "score": round(float(e.get("score", 0.0) or 0.0), 3),
                    "verdict": scrub(str(e.get("verdict", ""))),
                    "breakdown": {str(k): float(v) for k, v in (e.get("breakdown") or {}).items()},
                }
                for i, e in enumerate(entries or [])
            ]
        self._mutate(job_id, _apply)

    def winner(self, job_id: str, index: int) -> None:
        self._mutate(job_id, lambda r: r.update({"winner_index": int(index)}))

    def tournament(self, job_id: str, *, difficulty: float = 0.0, budget: int = 0) -> None:
        """Record the difficulty/budget that governed a tournament's fan-out."""
        def _apply(r: dict) -> None:
            r["difficulty"] = round(float(difficulty or 0.0), 3)
            r["budget"] = int(budget or 0)
        self._mutate(job_id, _apply)

    def metrics(self, job_id: str, values: dict) -> None:
        """Merge safe, structured render timing and quality measurements."""
        allowed = {
            "backend", "cache_hit", "prepare_seconds", "upload_seconds",
            "dispatch_seconds", "queue_seconds", "worker_seconds",
            "download_seconds", "total_seconds", "retry_count",
            "render_wall_seconds", "peak_rss_mb", "quality_score",
            "failure_kind", "manim_version", "local_manim_version",
            "manim_renderer", "repair_cache", "cache_hits",
            "failure_stage",
            "critic_model", "narration_max_boundary_overrun_s",
            "narration_max_rate_adjustment_pct", "narration_timeline_scale",
        }

        def _apply(r: dict) -> None:
            metrics = r.setdefault("metrics", {})
            if not isinstance(metrics, dict):
                metrics = {}
                r["metrics"] = metrics
            for key, value in (values or {}).items():
                if key not in allowed:
                    continue
                if isinstance(value, bool):
                    metrics[key] = value
                elif isinstance(value, (int, float)):
                    number = float(value)
                    if number == number and abs(number) != float("inf"):
                        metrics[key] = round(number, 3)
                elif isinstance(value, str):
                    metrics[key] = scrub(value)[:160]

        self._mutate(job_id, _apply)

    def hq_result(self, job_id: str, *, score: float, verdict: str = "") -> None:
        """Record the winner's FINAL HQ critic score/verdict — the other half of
        the draft->HQ pair (the draft half is candidates[winner_index].score)."""
        def _apply(r: dict) -> None:
            r["winner_hq_score"] = round(float(score or 0.0), 3)
            r["winner_hq_verdict"] = scrub(str(verdict or ""))
        self._mutate(job_id, _apply)

    def failure(self, job_id: str, log_tail: str, *, kind: str = "", status: str = "failed") -> None:
        status = str(status)
        status = status if status in {"failed", "action_required"} else "failed"
        def _apply(r: dict) -> None:
            r["status"] = status
            r["log_tail"] = scrub(log_tail)[-_LOG_TAIL_CHARS:]
            r["timeline"].append(asdict(LedgerEvent(status, _now(), scrub(kind))))
        self._mutate(job_id, _apply)

    def fallback(self, job_id: str, reason: str, final_path: str = "") -> None:
        def _apply(r: dict) -> None:
            r["status"] = "fallback_local"
            r["fallback_reason"] = scrub(reason)
            if final_path:
                r["final_path"] = scrub(str(final_path))
            r["timeline"].append(asdict(LedgerEvent("fallback_local", _now(), scrub(reason))))
        self._mutate(job_id, _apply)

    def finish(self, job_id: str, status: str = "rendered", final_path: str = "") -> None:
        status = str(status)
        status = status if status in STATUSES else "failed"
        def _apply(r: dict) -> None:
            r["status"] = status
            if final_path:
                r["final_path"] = scrub(str(final_path))
            r["timeline"].append(asdict(LedgerEvent(status, _now())))
        self._mutate(job_id, _apply)

    def urls(self, job_id: str, *, run_url: str = "", artifact_url: str = "") -> None:
        def _apply(r: dict) -> None:
            if run_url:
                r["run_url"] = safe_github_url(run_url)
            if artifact_url:
                r["artifact_url"] = safe_github_url(artifact_url)
        self._mutate(job_id, _apply)

    def list(self, limit: int = 20) -> list[dict]:
        return self._load()[: max(0, limit)]

    def get(self, job_id: str) -> dict | None:
        return next((j for j in self._load() if j.get("job_id") == job_id), None)
