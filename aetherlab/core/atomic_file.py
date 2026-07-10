"""Atomic, cancellable helpers for user-facing file exports."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from aetherlab.core.proc import ProcessCancelledError

_COPY_CHUNK = 1024 * 1024


def unique_staging_path(destination: Path) -> Path:
    """Reserve a same-directory temporary name that keeps the final suffix."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=f".tmp{destination.suffix}",
        dir=destination.parent,
    )
    os.close(fd)
    stage = Path(raw_path)
    stage.unlink(missing_ok=True)
    return stage


def atomic_copy_file(
    source: Path,
    destination: Path,
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> Path:
    """Copy to a sibling staging file, then atomically replace destination."""
    source = Path(source)
    destination = Path(destination)
    if source.resolve() == destination.resolve():
        return destination
    stage = unique_staging_path(destination)
    try:
        with source.open("rb") as src, stage.open("wb") as dst:
            while True:
                if cancel_check is not None and cancel_check():
                    raise ProcessCancelledError("File export cancelled")
                chunk = src.read(_COPY_CHUNK)
                if not chunk:
                    break
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        shutil.copystat(source, stage)
        os.replace(stage, destination)
    except BaseException:
        stage.unlink(missing_ok=True)
        raise
    return destination
