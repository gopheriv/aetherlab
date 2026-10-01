"""Physics parameter normalization shared by solve and output paths."""

from __future__ import annotations

import logging
import math
from dataclasses import replace
from typing import Any

log = logging.getLogger(__name__)


def apply_request_parameters(request: Any, solver: Any) -> Any:
    """Return a solver result with explicit request values applied last.

    Request parameters represent user choices, so they take precedence over
    model-proposed defaults. A copied result keeps cached or caller-owned
    solver objects unchanged while making downstream outputs consistent.

    Fail-soft: an entry with an empty name or a non-finite/non-numeric value
    is skipped with a warning instead of raising into the solve/render path.
    """
    overrides = getattr(request, "parameters", None) or {}
    if not isinstance(overrides, dict) or not overrides:
        return solver

    variables = dict(getattr(solver, "variables", {}) or {})
    applied = False
    for raw_name, raw_value in overrides.items():
        name = str(raw_name).strip()
        value = _finite_float(raw_value)
        if not name or value is None:
            log.warning("Ignoring invalid request parameter %r=%r", raw_name, raw_value)
            continue
        variables[name] = value
        applied = True

    return replace(solver, variables=variables) if applied else solver


def _finite_float(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None
