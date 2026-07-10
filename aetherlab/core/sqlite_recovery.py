"""Conservative recovery helpers for AetherLab's disposable SQLite stores."""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


def is_sqlite_corruption(exc: sqlite3.DatabaseError) -> bool:
    """True only for SQLite corruption/not-a-database failures."""
    code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(code, int) and (code & 0xFF) in {
        getattr(sqlite3, "SQLITE_CORRUPT", 11),
        getattr(sqlite3, "SQLITE_NOTADB", 26),
    }:
        return True
    message = str(exc).lower()
    return "malformed" in message or "not a database" in message


def quarantine_sqlite(path: Path) -> Path:
    """Move a corrupt DB and available WAL/SHM sidecars to unique names."""
    source = Path(path)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    quarantined = source.with_name(f"{source.name}.corrupt-{stamp}")
    source.replace(quarantined)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{source}{suffix}")
        if not sidecar.exists():
            continue
        try:
            sidecar.replace(Path(f"{quarantined}{suffix}"))
        except OSError as exc:
            log.warning("Could not preserve corrupt SQLite sidecar %s: %s", sidecar, exc)
    return quarantined
