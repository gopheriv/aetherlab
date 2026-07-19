"""Locale-independent text output for AetherLab command-line entry points."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import TextIO


def configure_utf8_stdio(streams: Iterable[TextIO] | None = None) -> None:
    """Use UTF-8 with replacement on configurable text streams.

    Interactive Windows consoles already use UTF-8 on modern Python, but a
    redirected stream can still inherit a legacy locale codec. Unsupported
    wrappers (Qt/pytest capture, frozen launchers) are left untouched.
    """
    targets = tuple(streams) if streams is not None else (sys.stdout, sys.stderr)
    for stream in targets:
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            continue
