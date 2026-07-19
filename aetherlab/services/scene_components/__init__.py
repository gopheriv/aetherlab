"""Curated, tested Manim scene components.

Instead of asking the LLM to write a whole Manim scene from scratch (which
passes `compile()` but often explodes at render time on invented kwargs), the
generator composes scenes from a small library of hand-verified, parameterized
templates driven by the numeric ground truth. Each component returns a complete,
self-contained scene as source (import manim + numpy only) or None when it does
not apply.

`compose_scene_code` is the entry point: it picks the best component for a given
solver result + plan, or returns None so the caller can fall back to the LLM /
static path.
"""

from __future__ import annotations

from typing import Any

from aetherlab.services.scene_components import surface3d, trajectory


def compose_scene_code(class_name: str, solver: Any, plan: Any = None) -> str | None:
    """Return complete Manim scene source composed from curated components.

    Priority: an exact numeric trajectory (dynamics) beats a 3-D scaffold beats
    nothing. Returns None when no curated component fits — the caller then falls
    back to LLM generation or the static template.
    """
    # Exact 2-D trajectory whenever the solver attached an integrable ODE.
    code = trajectory.build(class_name, solver)
    if code is not None:
        return code

    # Inherently-3-D problems get a real ThreeDScene scaffold.
    if plan is not None and getattr(plan, "needs_3d", False):
        code = surface3d.build(class_name, solver)
        if code is not None:
            return code

    return None
