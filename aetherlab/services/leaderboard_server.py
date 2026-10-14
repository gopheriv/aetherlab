"""Small self-hosted HTTP API for cross-device UNT mock-score rankings.

Run only behind an HTTPS reverse proxy on a public network. The service uses
only Python's standard library so it can also run in a school LAN without
installing the desktop application's UI or scientific dependencies.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from aetherlab.core.console import configure_utf8_stdio

_STUDENT_ID = re.compile(r"^[a-f0-9]{64}$")
_MAX_BODY_BYTES = 64_000
_MAX_SCORES = 500


class LeaderboardValidationError(ValueError):
    """Invalid leaderboard request data."""


class LeaderboardRepository:
    def __init__(self, database_path: Path, secret: str) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("AETHERLAB_LEADERBOARD_SECRET must be at least 32 bytes.")
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._secret = secret.encode("utf-8")
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS students (
                    school_key TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (school_key, student_id)
                );
                CREATE TABLE IF NOT EXISTS mock_scores (
                    school_key TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    score INTEGER NOT NULL CHECK(score >= 0 AND score <= 50),
                    PRIMARY KEY (school_key, student_id, completed_at),
                    FOREIGN KEY (school_key, student_id)
                        REFERENCES students(school_key, student_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS mock_scores_school_idx
                    ON mock_scores(school_key, completed_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _connection(self):
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def _school_key(self, school_id: str) -> str:
        canonical = " ".join(str(school_id or "").strip().casefold().split())
        if not canonical or len(canonical) > 40:
            raise LeaderboardValidationError("Enter a valid school ID.")
        return hmac.new(self._secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _clean_text(value: Any, field: str, limit: int, *, required: bool = False) -> str:
        result = " ".join(str(value or "").strip().split())
        if (required and not result) or len(result) > limit:
            raise LeaderboardValidationError(f"Invalid {field}.")
        return result

    @staticmethod
    def _clean_scores(value: Any) -> list[tuple[str, int]]:
        if not isinstance(value, list) or len(value) > _MAX_SCORES:
            raise LeaderboardValidationError("Invalid mock exam history.")
        cleaned: list[tuple[str, int]] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, dict):
                raise LeaderboardValidationError("Invalid mock exam history.")
            completed_at = str(item.get("completed_at", ""))
            try:
                stamp = dt.datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            except (TypeError, ValueError) as exc:
                raise LeaderboardValidationError("Invalid mock exam date.") from exc
            if stamp.tzinfo is None or len(completed_at) > 40:
                raise LeaderboardValidationError("Invalid mock exam date.")
            raw_score = item.get("score")
            if isinstance(raw_score, bool):
                raise LeaderboardValidationError("Mock scores must be between 0 and 50.")
            try:
                score = int(raw_score)
            except (TypeError, ValueError) as exc:
                raise LeaderboardValidationError("Mock scores must be between 0 and 50.") from exc
            if score < 0 or score > 50:
                raise LeaderboardValidationError("Mock scores must be between 0 and 50.")
            if completed_at not in seen:
                cleaned.append((completed_at, score))
                seen.add(completed_at)
        return cleaned

    def submit(self, payload: Any) -> dict:
        if not isinstance(payload, dict):
            raise LeaderboardValidationError("Invalid request.")
        school_key = self._school_key(payload.get("school_id", ""))
        student_id = str(payload.get("student_id", ""))
        if not _STUDENT_ID.fullmatch(student_id):
            raise LeaderboardValidationError("Invalid student profile.")
        name = self._clean_text(payload.get("name"), "student name", 80, required=True)
        class_name = self._clean_text(payload.get("class_name"), "class", 24)
        scores = self._clean_scores(payload.get("scores", []))
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self._connection() as db:
            db.execute(
                """INSERT INTO students(school_key, student_id, name, class_name, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(school_key, student_id) DO UPDATE SET
                   name=excluded.name, class_name=excluded.class_name, updated_at=excluded.updated_at""",
                (school_key, student_id, name, class_name, now),
            )
            db.executemany(
                """INSERT INTO mock_scores(school_key, student_id, completed_at, score)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(school_key, student_id, completed_at)
                   DO UPDATE SET score=excluded.score""",
                [(school_key, student_id, completed_at, score) for completed_at, score in scores],
            )
            return self._leaderboard(db, school_key, student_id)

    @staticmethod
    def _leaderboard(
        db: sqlite3.Connection,
        school_key: str,
        current_student_id: str,
    ) -> dict:
        students = db.execute(
            "SELECT student_id, name, class_name FROM students WHERE school_key = ?",
            (school_key,),
        ).fetchall()
        entries = []
        for student in students:
            score_rows = db.execute(
                """SELECT score, completed_at FROM mock_scores
                   WHERE school_key = ? AND student_id = ? ORDER BY completed_at DESC""",
                (school_key, student["student_id"]),
            ).fetchall()
            scores = [
                {"score": int(row["score"]), "completed_at": str(row["completed_at"])}
                for row in score_rows
            ]
            best = max((score["score"] for score in scores), default=None)
            latest = scores[0]["score"] if scores else None
            entries.append({
                "student_id": student["student_id"],
                "name": student["name"],
                "class_name": student["class_name"],
                "best_score": best,
                "latest_score": latest,
                "mock_count": len(scores),
                "scores": scores,
            })
        entries.sort(key=lambda entry: entry["name"].casefold())
        entries.sort(
            key=lambda entry: (
                entry["best_score"] is not None,
                entry["best_score"] if entry["best_score"] is not None else -1,
                entry["latest_score"] if entry["latest_score"] is not None else -1,
            ),
            reverse=True,
        )
        previous_score = None
        previous_rank = None
        for index, entry in enumerate(entries, 1):
            score = entry["best_score"]
            if score is None:
                rank = None
            elif score == previous_score:
                rank = previous_rank
            else:
                rank = index
                previous_score, previous_rank = score, rank
            entry["rank"] = rank
            entry["is_current_user"] = entry["student_id"] == current_student_id
        return {"entries": entries}


class LeaderboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "PhysLabLeaderboard/1.0"
    sys_version = ""

    def log_message(self, _format: str, *_args: Any) -> None:
        # Request bodies and group identifiers contain student information.
        return

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "Not found."})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/v1/leaderboard/sync":
            self._send(404, {"error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > _MAX_BODY_BYTES:
                raise LeaderboardValidationError("Request size is invalid.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = self.server.repository.submit(payload)  # type: ignore[attr-defined]
        except LeaderboardValidationError as exc:
            self._send(400, {"error": str(exc)})
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._send(400, {"error": "Invalid JSON request."})
            return
        except Exception:  # noqa: BLE001 — keep server internals out of responses
            self._send(500, {"error": "Leaderboard service error."})
            return
        self._send(200, result)


class LeaderboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], repository: LeaderboardRepository) -> None:
        super().__init__(address, LeaderboardRequestHandler)
        self.repository = repository


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Run the PhysLab school leaderboard API.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: localhost).")
    parser.add_argument("--port", type=int, default=8765, help="Listen port (default: 8765).")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.getenv("AETHERLAB_LEADERBOARD_DB", "leaderboard.sqlite3")),
        help="SQLite database path.",
    )
    args = parser.parse_args(argv)
    secret = os.getenv("AETHERLAB_LEADERBOARD_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        parser.error("set AETHERLAB_LEADERBOARD_SECRET to a random value of at least 32 bytes")
    repository = LeaderboardRepository(args.db, secret)
    server = LeaderboardHTTPServer((args.host, args.port), repository)
    print(f"PhysLab leaderboard listening on {args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
