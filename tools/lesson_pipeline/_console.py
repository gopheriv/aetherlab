"""Reuse the app's UTF-8 console policy for direct and module script runs."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from aetherlab.core.console import configure_utf8_stdio  # noqa: E402

__all__ = ["configure_utf8_stdio"]
