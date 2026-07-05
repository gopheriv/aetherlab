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

import sys

# Windows process-creation flags (winbase.h).
CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

IS_WINDOWS = sys.platform == "win32"


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
