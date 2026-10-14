"""Problem videos: animation that solves one concrete physics problem.

A scenario explains a topic. A problem video solves a specific problem, using
the numbers the solver extracted, in about a minute, and ends by proving the
answer: the simulation runs with those numbers and hits the computed result.

The solving arc follows the Minnesota strategy (focus, describe, plan, execute,
evaluate), marked with short subgoal labels, which research links to better
transfer to new problems. The visual device is different for every problem
(two shadows, two clocks, Newton's cannon) because a template shared by every
topic was rated lower than varied, topic-specific staging.

Each module exposes ``matches(solver) -> bool`` and ``build(class_name, solver)``.
A problem video is self-contained, so it gets no intro/closing cards.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

log = logging.getLogger(__name__)

PROBLEMS: tuple[str, ...] = (
    "three_body", "muon_paradox", "quantum_dot", "chaos_horizon",
    "coupled_swing", "projectile_landing", "moon_clock", "orbit_period",
)


def _module(name: str) -> Any:
    return importlib.import_module(f"aetherlab.services.scene_components.problems.{name}")


def compose_problem(
    class_name: str, solver: Any, *, prompt_context: str = "",
) -> tuple[str, str] | None:
    """Return (problem name, scene source) when a problem video fits, else None."""
    for name in PROBLEMS:
        try:
            module = _module(name)
            if name == "three_body":
                matched = module.matches(solver, prompt_context=prompt_context)
            else:
                matched = module.matches(solver)
            if not matched:
                continue
            code = module.build(class_name, solver)
        except Exception as exc:  # noqa: BLE001 — fall through to scenarios/components
            log.info("Problem video %s unavailable (%s).", name, exc)
            continue
        if code:
            return name, code
    return None


def check_lines(solver: Any, *, prompt_context: str = "") -> list[str]:
    """Independent simulation results for every problem type this request matches."""
    lines: list[str] = []
    for name in PROBLEMS:
        try:
            module = _module(name)
            if name == "three_body":
                matched = module.matches(solver, prompt_context=prompt_context)
            else:
                matched = module.matches(solver)
            if matched:
                lines += module.check_lines(solver)
        except Exception as exc:  # noqa: BLE001 — checks are advisory
            log.info("No independent check from %s (%s).", name, exc)
    return lines
