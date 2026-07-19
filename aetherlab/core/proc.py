"""Cross-platform subprocess helpers.

Every external process AetherLab spawns (Manim render, pdflatex, ffmpeg,
ffprobe) was previously launched with a hardcoded Windows creation flag. That
flag is meaningless — and, depending on the Python/OS build, outright invalid —
on POSIX, so the whole render path failed on Linux/macOS. Cloud/CI render
runners are Linux, so portability here is a hard prerequisite for cloud
rendering, not a nicety.

This module returns the correct ``subprocess`` keyword arguments per platform:

* Windows — ``creationflags`` with CREATE_NO_WINDOW (hide the console window)
  and, optionally, BELOW_NORMAL_PRIORITY_CLASS so a heavy render keeps the UI
  responsive.
* POSIX — ``start_new_session=True`` so the child gets its own process group
  (clean signal isolation; a timeout kill takes the whole render subtree with
  it). Below-normal priority is intentionally left to the OS on POSIX:
  ``preexec_fn``-based reniceing is unsafe in the multithreaded Qt process, and
  CI runners don't need it.

Pure stdlib, no project imports — safe to import from anywhere.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any

# Windows process-creation flags (winbase.h).
CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

IS_WINDOWS = sys.platform == "win32"


class ProcessCancelledError(RuntimeError):
    """Raised after a cancellable subprocess and its descendants are stopped."""


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Best-effort hard stop of a process and every descendant it started."""
    if process.poll() is not None:
        return
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass


def run_process_tree(
    args: Sequence[str],
    *,
    timeout: float,
    cancel_check: Callable[[], bool] | None = None,
    poll_interval: float = 0.1,
    **popen_kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a command and kill its whole tree on timeout or cancellation.

    This mirrors the subset of ``subprocess.run`` used by the renderer while
    retaining control of ``Popen`` long enough to terminate Manim's FFmpeg and
    LaTeX descendants. POSIX callers are placed in a new session; Windows uses
    ``taskkill /T`` before falling back to killing the immediate process.
    """
    capture_output = bool(popen_kwargs.pop("capture_output", False))
    check = bool(popen_kwargs.pop("check", False))
    if capture_output:
        if "stdout" in popen_kwargs or "stderr" in popen_kwargs:
            raise ValueError("stdout/stderr may not be used with capture_output")
        popen_kwargs["stdout"] = subprocess.PIPE
        popen_kwargs["stderr"] = subprocess.PIPE
    if not IS_WINDOWS:
        popen_kwargs.setdefault("start_new_session", True)

    process = subprocess.Popen(list(args), **popen_kwargs)
    started = time.monotonic()
    stdout = stderr = None
    try:
        while True:
            if cancel_check is not None and cancel_check():
                _terminate_process_tree(process)
                stdout, stderr = process.communicate()
                raise ProcessCancelledError("Subprocess cancelled")
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                _terminate_process_tree(process)
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(
                    list(args), timeout, output=stdout, stderr=stderr
                )
            wait_for = min(remaining, poll_interval) if cancel_check else remaining
            try:
                stdout, stderr = process.communicate(timeout=wait_for)
                break
            except subprocess.TimeoutExpired:
                if cancel_check is not None:
                    continue
                _terminate_process_tree(process)
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(
                    list(args), timeout, output=stdout, stderr=stderr
                )
    except BaseException:
        if process.poll() is None:
            _terminate_process_tree(process)
            process.communicate()
        raise

    result = subprocess.CompletedProcess(list(args), process.returncode, stdout, stderr)
    if check:
        result.check_returncode()
    return result


def subprocess_kwargs(*, no_window: bool = True, below_normal: bool = False) -> dict:
    """Platform-correct kwargs for ``subprocess.run`` / ``subprocess.Popen``.

    Args:
        no_window: hide the console window (Windows only; no-op on POSIX).
        below_normal: request below-normal scheduling priority (Windows only).

    Returns a dict to splat into the subprocess call. On POSIX this is always
    ``{"start_new_session": True}``; the Windows-only flags never leak across.
    """
    if IS_WINDOWS:
        flags = 0
        if no_window:
            flags |= CREATE_NO_WINDOW
        if below_normal:
            flags |= BELOW_NORMAL_PRIORITY_CLASS
        return {"creationflags": flags} if flags else {}
    return {"start_new_session": True}
