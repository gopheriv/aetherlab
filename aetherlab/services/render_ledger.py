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


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class RenderJobLedger:
    """JSON-backed, fail-soft, secret-scrubbed ledger of render jobs."""

    def __init__(self, path: Path | None = None, *, max_jobs: int = _MAX_JOBS) -> None:
        self.path = Path(path) if path else None
        self.max_jobs = max_jobs

    # -- persistence (never raises) -------------------------------------------
    def _load(self) -> list[dict]:
        if not self.path or not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception as exc:  # noqa: BLE001 — corruption must not break renders
            log.debug("render ledger unreadable, starting fresh: %s", exc)
            return []

    def _save(self, jobs: list[dict]) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(jobs[: self.max_jobs], indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 — persistence is best-effort
            log.debug("could not persist render ledger: %s", exc)

    def _mutate(self, job_id: str, apply) -> None:
        """Load, find-or-create the job, apply a mutation, and persist. Fail-soft."""
        if not job_id:
            return
        try:
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
                "scene_class": str(scene_class), "quality": str(quality), "fps": int(fps or 0),
                "backend": str(backend), "provider": str(provider), "status": "queued",
            })
            r["timeline"].append(asdict(LedgerEvent("queued", _now())))
        self._mutate(job_id, _apply)

    def status(self, job_id: str, status: str, detail: str = "") -> None:
        def _apply(r: dict) -> None:
            r["status"] = str(status)
            r["timeline"].append(asdict(LedgerEvent(str(status), _now(), scrub(detail))))
        self._mutate(job_id, _apply)

    def candidates(self, job_id: str, entries: list[dict]) -> None:
        def _apply(r: dict) -> None:
            r["candidates"] = [
                {
                    "index": int(e.get("index", i)),
                    "score": round(float(e.get("score", 0.0) or 0.0), 3),
                    "verdict": str(e.get("verdict", "")),
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

    def hq_result(self, job_id: str, *, score: float, verdict: str = "") -> None:
        """Record the winner's FINAL HQ critic score/verdict — the other half of
        the draft->HQ pair (the draft half is candidates[winner_index].score)."""
        def _apply(r: dict) -> None:
            r["winner_hq_score"] = round(float(score or 0.0), 3)
            r["winner_hq_verdict"] = str(verdict or "")
        self._mutate(job_id, _apply)

    def failure(self, job_id: str, log_tail: str, *, kind: str = "") -> None:
        def _apply(r: dict) -> None:
            r["status"] = "failed"
            r["log_tail"] = scrub(log_tail)[-_LOG_TAIL_CHARS:]
            r["timeline"].append(asdict(LedgerEvent("failed", _now(), scrub(kind))))
        self._mutate(job_id, _apply)

    def fallback(self, job_id: str, reason: str, final_path: str = "") -> None:
        def _apply(r: dict) -> None:
            r["status"] = "fallback_local"
            r["fallback_reason"] = scrub(reason)
            if final_path:
                r["final_path"] = str(final_path)
            r["timeline"].append(asdict(LedgerEvent("fallback_local", _now(), scrub(reason))))
        self._mutate(job_id, _apply)

    def finish(self, job_id: str, status: str = "rendered", final_path: str = "") -> None:
        def _apply(r: dict) -> None:
            r["status"] = str(status)
            if final_path:
                r["final_path"] = str(final_path)
            r["timeline"].append(asdict(LedgerEvent(str(status), _now())))
        self._mutate(job_id, _apply)

    def urls(self, job_id: str, *, run_url: str = "", artifact_url: str = "") -> None:
        def _apply(r: dict) -> None:
            if run_url:
                r["run_url"] = scrub(run_url)
            if artifact_url:
                r["artifact_url"] = scrub(artifact_url)
        self._mutate(job_id, _apply)

    def list(self, limit: int = 20) -> list[dict]:
        return self._load()[: max(0, limit)]

    def get(self, job_id: str) -> dict | None:
        return next((j for j in self._load() if j.get("job_id") == job_id), None)
