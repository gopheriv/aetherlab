"""SQLite session cache for prompt, RAG, and scene artifacts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aetherlab.core.models import (
    ProblemRequest,
    RagResult,
    SceneBundle,
    SolverResult,
    utc_now_iso,
)


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

    def _initialize(self) -> None:
        with self._connect() as connection:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None

        solver = None
        if row["solver_json"]:
            solver = SolverResult.from_json(json.loads(row["solver_json"]), cached=True)

        rag = None
        if row["rag_json"]:
            rag = RagResult.from_json(json.loads(row["rag_json"]), cached=True)

        scene = None
        if row["scene_json"]:
            scene = SceneBundle.from_json(json.loads(row["scene_json"]), cached=True)

        return CachedSession(
            key=row["key"],
            prompt=row["prompt"],
            parameters_json=json.loads(row["parameters_json"]),
            solver=solver,
            rag=rag,
            scene=scene,
        )

    def store_solver(self, key: str, solver: SolverResult) -> None:
        self._store_json(key, "solver_json", solver.to_json())

    def store_rag(self, key: str, rag: RagResult) -> None:
        self._store_json(key, "rag_json", rag.to_json())

    def store_scene(self, key: str, scene: SceneBundle) -> None:
        self._store_json(key, "scene_json", scene.to_json())

    def _store_json(self, key: str, column: str, payload: dict[str, Any]) -> None:
        if column not in {"solver_json", "rag_json", "scene_json"}:
            raise ValueError(f"Unsupported cache column: {column}")
        with self._connect() as connection:
            connection.execute(
                f"UPDATE sessions SET {column} = ?, updated_at = ? WHERE key = ?",
                (json.dumps(payload, sort_keys=True), utc_now_iso(), key),
            )
