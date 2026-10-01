"""Topic-specific scenarios: each topic tells its story its own way.

A curated component animates one topic's physics exactly. A scenario is a
creative staging of the same physics, with a device chosen for that topic:
a race, a stopwatch, a meeting of two waves, a build-up. The explanation lives
inside the animation rather than in a template shared by every topic.

Human review asked for this. A uniform teaching scaffold applied to every topic
(v3) scored below lighter cards around varied animations (v2), because "it uses
different approaches and different ideas for each topic".

Every scenario reuses its component's ``params()`` and numeric solve, so the
physics is the same as the component's; only the staging differs. Each module
exposes ``build(class_name, solver) -> str | None`` and ``explain(solver)``.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

log = logging.getLogger(__name__)

# curated component name -> scenario module that restages it
SCENARIOS: dict[str, str] = {
    "pendulum": "pendulum_race",
    "orbit": "kepler_stopwatch",
    "standing_wave": "wave_meeting",
    "fourier_epicycles": "fourier_buildup",
    "field_lines": "field_arrows",
    "double_slit": "photon_buildup",
    "coupled_oscillators": "energy_buckets",
}


def _module(name: str) -> Any:
    return importlib.import_module(f"aetherlab.services.scene_components.scenarios.{name}")


def compose_scenario(component: str, class_name: str, solver: Any) -> tuple[str, str] | None:
    """Return (scenario name, scene source) for a component, or None (fail-soft)."""
    name = SCENARIOS.get(component)
    if name is None:
        return None
    try:
        code = _module(name).build(class_name, solver)
    except Exception as exc:  # noqa: BLE001 — the plain component is the fallback
        log.info("Scenario %s unavailable (%s); using the component.", name, exc)
        return None
    return (name, code) if code else None


def explain(name: str, solver: Any) -> dict[str, Any] | None:
    """Explanation for a scenario, or None when ``name`` is not a scenario."""
    if name not in SCENARIOS.values():
        return None
    return _module(name).explain(solver)
