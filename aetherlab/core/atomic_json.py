"""Small building blocks for concurrent JSON persistence.

The app has several lightweight JSON stores that are intentionally simpler
than a database. They still need two guarantees inside one AetherLab process:
read/modify/write transactions for the same path must not overlap, and readers
must never observe a half-written document.  The path lock supplies the first;
same-directory temporary files plus ``os.replace`` supply the second.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}


def path_lock(path: Path) -> threading.RLock:
    """Return the process-wide re-entrant lock for ``path``."""
    # Avoid filesystem-dependent canonicalization here: another thread may be
    # creating the parent at this exact moment, and a before/after ``resolve``
    # result must never split one logical path across two locks on Windows.
    key = os.path.normcase(os.path.abspath(os.fspath(path)))
    with _LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    """Durably stage JSON beside ``path`` and atomically replace the target.

    Callers that perform a read/modify/write transaction must hold
    :func:`path_lock` across the whole transaction.  This function deliberately
    does not acquire it so it is also useful for immutable cache entries.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    staged = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=indent)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, target)
    finally:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            pass
