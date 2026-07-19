"""SQLite session cache for prompt, RAG, and scene artifacts."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aetherlab.core.atomic_json import path_lock
from aetherlab.core.models import (
    ProblemRequest,
    RagResult,
    SceneBundle,
    SolverResult,
    utc_now_iso,
)
from aetherlab.core.sqlite_recovery import is_sqlite_corruption, quarantine_sqlite

log = logging.getLogger(__name__)


class _CacheCorruption(sqlite3.DatabaseError):
    pass


@dataclass
class CachedSession:
    key: str
    prompt: str
    parameters_json: dict[str, Any]
    solver: SolverResult | None
    rag: RagResult | None
    scene: SceneBundle | None


class SessionCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def make_key(self, request: ProblemRequest) -> str:
        payload = json.dumps(request.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with path_lock(self.path):
            try:
                self._create_schema(check_integrity=True)
            except sqlite3.DatabaseError as exc:
                if not isinstance(exc, _CacheCorruption) and not is_sqlite_corruption(exc):
                    raise
                quarantined = quarantine_sqlite(self.path)
                log.warning("Session cache was corrupt; rebuilt it after preserving %s", quarantined)
                self._create_schema(check_integrity=False)

    def _create_schema(self, *, check_integrity: bool) -> None:
        with self._transaction() as connection:
            if check_integrity:
                row = connection.execute("PRAGMA quick_check(1)").fetchone()
                if not row or str(row[0]).lower() != "ok":
                    raise _CacheCorruption(str(row[0]) if row else "quick_check returned no result")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    key TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    solver_json TEXT,
                    rag_json TEXT,
                    scene_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def ensure_request(self, request: ProblemRequest) -> str:
        key = self.make_key(request)
        now = utc_now_iso()
        payload = request.canonical_payload()
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    key, prompt, parameters_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    prompt = excluded.prompt,
                    parameters_json = excluded.parameters_json,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    request.normalized_prompt(),
                    json.dumps(payload["parameters"], sort_keys=True),
                    now,
                    now,
                ),
            )
        return key

    def get(self, key: str) -> CachedSession | None:
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None

        solver = self._decode_cached(row["solver_json"], SolverResult.from_json)
        rag = self._decode_cached(row["rag_json"], RagResult.from_json)
        scene = self._decode_cached(row["scene_json"], SceneBundle.from_json)
        parameters = self._decode_object(row["parameters_json"]) or {}

        return CachedSession(
            key=row["key"],
            prompt=row["prompt"],
            parameters_json=parameters,
            solver=solver,
            rag=rag,
            scene=scene,
        )

    @staticmethod
    def _decode_object(raw: str | None) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @classmethod
    def _decode_cached(cls, raw: str | None, factory):
        payload = cls._decode_object(raw)
        if payload is None:
            return None
        try:
            return factory(payload, cached=True)
        except (TypeError, ValueError, KeyError):
            return None

    def store_solver(self, key: str, solver: SolverResult) -> None:
        self._store_json(key, "solver_json", solver.to_json())

    def store_rag(self, key: str, rag: RagResult) -> None:
        self._store_json(key, "rag_json", rag.to_json())

    def store_scene(self, key: str, scene: SceneBundle) -> None:
        self._store_json(key, "scene_json", scene.to_json())

    def clear_artifacts(self, key: str, artifacts: tuple[str, ...] = ("solver", "rag", "scene")) -> None:
        """Clear cached pipeline artifacts for one request key.

        This keeps the request row/history while forcing selected stages to be
        recomputed on the next pipeline run. Used by visual regression refreshes
        after deterministic template changes.
        """
        columns = {
            "solver": "solver_json",
            "rag": "rag_json",
            "scene": "scene_json",
        }
        selected = [columns[name] for name in artifacts if name in columns]
        if not selected:
            return
        assignments = ", ".join(f"{column} = NULL" for column in selected)
        with self._transaction() as connection:
            connection.execute(
                f"UPDATE sessions SET {assignments}, updated_at = ? WHERE key = ?",
                (utc_now_iso(), key),
            )

    def _store_json(self, key: str, column: str, payload: dict[str, Any]) -> None:
        if column not in {"solver_json", "rag_json", "scene_json"}:
            raise ValueError(f"Unsupported cache column: {column}")
        with self._transaction() as connection:
            connection.execute(
                f"UPDATE sessions SET {column} = ?, updated_at = ? WHERE key = ?",
                (json.dumps(payload, sort_keys=True), utc_now_iso(), key),
            )
