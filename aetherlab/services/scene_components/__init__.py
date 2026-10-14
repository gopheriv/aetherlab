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

from aetherlab.services.scene_components import (
    coupled_oscillators,
    double_pendulum,
    double_slit,
    field_lines,
    fourier_epicycles,
    kinetic_theory,
    lens,
    mirror,
    orbit,
    pendulum,
    phase_portrait,
    quantum,
    standing_wave,
    surface3d,
    trajectory,
)

# Phrasings that make the phase plane (v vs x) the insight frame rather than the
# time series. Kept narrow so a plain oscillator still gets the trajectory curve.
_PHASE_STEMS = (
    "phase portrait", "phase-portrait", "phase plane", "phase-plane",
    "phase space", "phase-space", "phase diagram", "limit cycle", "limit-cycle",
    "state space", "attractor",
)
# Fourier / series framing — deliberately excludes the bare word "harmonic"
# (which belongs to the harmonic *oscillator*) to avoid stealing that domain.
_FOURIER_STEMS = (
    "fourier", "epicycle", "square wave", "square-wave", "sawtooth",
    "partial sum", "series expansion", "harmonic series", "rotating vector",
)
# Quantum framing — distinctive stems only; avoids bare "potential"/"orbital"
# which also read as electrostatics / 3-D geometry.
_QUANTUM_STEMS = (
    "quantum", "wavefunction", "wave function", "wavepacket", "wave packet",
    "schrodinger", "schrödinger", "probability density", "potential well",
    "quantum harmonic", "quantum tunnel", "tunneling", "tunnelling",
)
# Optics / interference framing.
_INTERFERENCE_STEMS = (
    "double slit", "double-slit", "two-slit", "two slit", "young's", "youngs",
    "interference", "diffraction", "interference fringes",
)
# The named two-slit apparatus. It is more specific than "quantum", so a
# quantum-framed double-slit prompt still gets the fringe stage.
_SLIT_EXPERIMENT_STEMS = (
    "double slit", "double-slit", "two-slit", "two slit", "young's", "youngs",
)
# Thermodynamics / statistical-mechanics framing.
_THERMO_STEMS = (
    "kinetic theory", "ideal gas", "maxwell-boltzmann", "maxwell boltzmann",
    "thermodynamic", "statistical mechanic", "gas particles", "brownian",
    "pressure of a gas", "molecular motion",
)
# Chaotic double pendulum — checked before the single pendulum so it wins.
# Coupled pendulums are NOT a double pendulum: they are a linear two-mode
# system that trades energy back and forth (see _COUPLED_PENDULUM_STEMS).
_DOUBLE_PENDULUM_STEMS = (
    "double pendulum", "double-pendulum", "chaotic pendulum", "chaos pendulum",
)
# Two pendulums joined by a spring: the coupled-oscillator staging, checked
# before the single pendulum (whose detector also fires on "pendulum").
_COUPLED_PENDULUM_STEMS = (
    "coupled pendul", "sympathetic pendul", "pendulums connected",
    "pendulums joined", "spring-coupled pendul", "pendulums coupled",
)
# Geometric optics — thin lens / refraction / image formation. "mirror" is
# excluded here so a curved-mirror prompt reaches the mirror component instead.
_LENS_STEMS = (
    "lens", "focal length", "thin lens", "thin-lens", "converging lens",
    "convex lens", "image formation", "ray diagram",
)
# Curved-mirror optics (reflective image formation). No bare "mirror": a
# summary saying "mirror image" or "mirror symmetry" is not an optics problem.
_MIRROR_STEMS = (
    "concave mirror", "convex mirror", "curved mirror", "spherical mirror",
    "parabolic mirror", "mirror equation", "reflecting telescope",
    "mirror formula", "focal length of a mirror", "image in a mirror",
)
# Coupled oscillators — two masses exchanging energy (distinct from the single
# standing-wave normal mode; distinctive stems so it doesn't collide). Generic
# phrases such as "two masses" also describe Atwood machines and collisions,
# so only coupling language routes here.
_COUPLED_STEMS = (
    "coupled oscillator", "coupled oscillators", "coupled spring", "two coupled",
    "coupled mass", "coupled pendula", "spring-coupled", "masses coupled by",
)
# Atomic/quantum "orbital" — distinct from a planetary orbit; keeps the Kepler
# component from stealing "hydrogen orbital" via the "orbit" substring.
_ATOMIC_STEMS = (
    "orbital", "atomic", "hydrogen", "electron cloud", "wavefunction", "quantum",
)
# Explicit N-body prompts must never fall through to the visually similar but
# physically different two-body Kepler component.
_THREE_BODY_STEMS = ("three body", "three-body", "3 body", "3-body")
_HARMONIC_QUANTUM_STEMS = (
    "quantum harmonic oscillator", "harmonic quantum oscillator",
    "coherent state in a harmonic", "harmonic coherent state",
)
_KINETIC_GAS_STEMS = ("kinetic theory", "gas particles", "molecular motion")
_UNSUPPORTED_THERMO_STEMS = (
    "heat engine", "carnot", "entropy", "thermodynamic cycle", "p-v diagram",
    "pv diagram", "heat and work", "internal energy change", "first law of thermodynamics",
)
_UNSUPPORTED_OPTICS_STEMS = (
    "diverging lens", "diverging-lens", "concave lens", "virtual image",
    "convex mirror",
    "total internal reflection", "critical angle", "diffraction grating",
    "single slit", "single-slit", "magnetic field", "charged particle",
)
# Standing wave / normal mode on a string.
_STANDING_WAVE_STEMS = (
    "standing wave", "standing-wave", "normal mode", "vibrating string",
    "node and antinode", "antinode", "harmonics on a string", "eigenmode",
    "resonant mode",
)


def compose_scene_code(
    class_name: str, solver: Any, plan: Any = None, duration_target_s: float = 30.0,
    *, problem_prompt: str = "",
) -> str | None:
    """Compose a curated scene (or its creative scenario), then add explanation cards.

    The explanation layer (scene_components/explain.py) is fail-soft: without
    an explanation, or on any error, the plain component scene is returned.
    """
    # A concrete problem with its givens (for example a kick speed and angle)
    # gets a problem video that solves it; it is self-contained, so no cards.
    try:
        from aetherlab.services.scene_components.problems import compose_problem

        solved = compose_problem(class_name, solver, prompt_context=problem_prompt)
    except Exception:  # noqa: BLE001 — problem videos are additive, never fatal
        solved = None
    if solved is not None:
        return solved[1]
    composed = _compose_component(class_name, solver, plan, problem_prompt=problem_prompt)
    if composed is None:
        return None
    name, code = composed
    # A topic-specific scenario restages the same physics creatively; the plain
    # component stays the fallback when a scenario cannot build.
    try:
        from aetherlab.services.scene_components.scenarios import compose_scenario

        staged = compose_scenario(name, class_name, solver)
    except Exception:  # noqa: BLE001 — scenarios are additive, never fatal
        staged = None
    if staged is not None:
        name, code = staged
    try:
        from aetherlab.services.scene_components.explain import (
            add_explanation,
            explanation_for,
        )

        return add_explanation(code, explanation_for(name, solver), duration_target_s)
    except Exception:  # noqa: BLE001 — explanation is additive, never fatal
        return code


def compose_component_code(class_name: str, solver: Any, plan: Any = None) -> str | None:
    """The plain curated component for a problem: no scenario, no explanation cards.

    This is the fallback layer beneath the scenarios; tests of a component's own
    content and routing use it directly.
    """
    composed = _compose_component(class_name, solver, plan)
    return composed[1] if composed else None


def _compose_component(
    class_name: str,
    solver: Any,
    plan: Any = None,
    *,
    problem_prompt: str = "",
) -> tuple[str, str] | None:
    """Return (component name, Manim scene source) from the curated components.

    Priority (most specific physical staging first):
      1. the chaotic double pendulum (checked before the single pendulum),
      2. a real swinging pendulum when the problem *is* a pendulum,
      3. a Kepler orbit (equal-area law) when the problem is gravitational,
      4. electric field lines when the problem is electrostatic,
      5. a quantum wavepacket in a well when the prompt is quantum (unless it
         names the double-slit experiment),
      6. a double-slit interference stage when the prompt is about interference,
      7. a concave-mirror ray diagram when the prompt is about curved mirrors,
      8. a thin-lens ray diagram when the prompt is about lenses/refraction,
      9. two coupled oscillators when the prompt is about a coupled/two-mass system,
      10. a standing wave when the prompt is about normal modes on a string,
      11. a kinetic-theory gas when the prompt is thermodynamic,
      12. a Fourier-series epicycle build when the prompt asks for one,
      13. a phase-space portrait when the prompt asks for one (2-state ODE),
      14. the exact 2-D time-series trajectory for any other integrable ODE,
      15. a 3-D surface of the problem's field for inherently-3-D problems.
    Returns None when no curated component fits — the caller then falls back to
    LLM generation or the static template.
    """
    topic_text = " ".join([
        problem_prompt,
        getattr(solver, "summary", "") or "",
        " ".join(getattr(solver, "keywords", []) or []),
    ]).lower().replace("-", " ")
    def has(*terms: str) -> bool:
        return any(term.replace("-", " ") in topic_text for term in terms)
    if any(stem.replace("-", " ") in topic_text for stem in _THREE_BODY_STEMS):
        # A verified specific route owns this topic. If it declines the supplied
        # data or numerical convergence, do not silently show a two-body orbit.
        return None
    if (
        has(*_QUANTUM_STEMS)
        and not has(*_SLIT_EXPERIMENT_STEMS)
        and not has(*_HARMONIC_QUANTUM_STEMS)
    ):
        # The existing Gaussian scene is only a coherent state in a harmonic
        # well. It is not a barrier-scattering, spin, atomic-orbital, or generic
        # Schrödinger solution.
        return None
    if has("hydrogen", "atomic orbital", "p orbital", "s orbital", "electron cloud"):
        return None
    if has("relativity", "relativistic", "lorentz transform", "spacetime") and not has("muon"):
        return None
    if has(*_UNSUPPORTED_THERMO_STEMS):
        return None
    if has(*_THERMO_STEMS) and not has(*_KINETIC_GAS_STEMS):
        return None
    if has("magnetic field", "charged particle", "magnet", "lorentz force"):
        return None
    if has(*_UNSUPPORTED_OPTICS_STEMS):
        return None
    if has("electric field", "electrostatic", "dipole"):
        charge_values = getattr(solver, "variables", {}) or {}
        custom_charge = any(
            str(key).lower().replace("_", "") in {"q1", "q2", "charge1", "charge2"}
            for key in charge_values
        )
        if not has("dipole") or custom_charge:
            return None
    # 1. The chaotic double pendulum — must precede the single pendulum, whose
    #    domain detector also matches the word "pendulum".
    if _mentions(solver, _DOUBLE_PENDULUM_STEMS):
        code = double_pendulum.build(class_name, solver)
        if code is not None:
            return "double_pendulum", code

    # 1b. Spring-coupled pendulums trade energy like coupled oscillators; stage
    #     them that way rather than as one pendulum (or a chaotic double one).
    if _mentions(solver, _COUPLED_PENDULUM_STEMS):
        code = coupled_oscillators.build(class_name, solver)
        if code is not None:
            return "coupled_oscillators", code

    # 2. Pendulum problems get a real rod + bob driven by the nonlinear solution
    #    rather than an abstract theta(t) line.
    if _is_pendulum(solver):
        code = pendulum.build(class_name, solver)
        if code is not None:
            return "pendulum", code

    # 3. Orbits / gravitation: a real Kepler orbit with the equal-area law.
    #    Guard against the "orbital" false friend — an atomic/quantum orbital is
    #    not a planetary orbit (it falls through to the 3-D field surface).
    if _is_orbit(solver) and not _mentions(solver, _ATOMIC_STEMS):
        code = orbit.build(class_name, solver)
        if code is not None:
            return "orbit", code

    # 4. Electrostatics is not a time-ODE, so nothing else fires — stage the
    #    field lines of the charge configuration.
    if _is_em_field(solver):
        code = field_lines.build(class_name, solver)
        if code is not None:
            return "field_lines", code

    # 5. Quantum mechanics: a probability density sloshing in a potential well.
    #    A named double-slit experiment is the more specific staging even when
    #    it is framed quantum-mechanically, so it skips to step 6.
    if _mentions(solver, _QUANTUM_STEMS) and not _mentions(solver, _SLIT_EXPERIMENT_STEMS):
        code = quantum.build(class_name, solver)
        if code is not None:
            return "quantum", code

    # 6. Interference / diffraction: Young's two-source experiment.
    if _mentions(solver, _SLIT_EXPERIMENT_STEMS):
        code = double_slit.build(class_name, solver)
        if code is not None:
            return "double_slit", code

    # 7. Reflective optics: concave-mirror image formation. Checked before the
    #    lens because both share generic optics terms ("image formation", "ray
    #    diagram") — the explicit "mirror" is the more specific signal.
    if _is_mirror_optics(solver):
        code = mirror.build(class_name, solver)
        if code is not None:
            return "mirror", code

    # 8. Geometric optics: thin-lens image formation by ray tracing.
    if _mentions(solver, _LENS_STEMS):
        code = lens.build(class_name, solver)
        if code is not None:
            return "lens", code

    # 9. Coupled oscillators — checked before the single standing wave, since a
    #    coupled system's "normal modes" would otherwise match that first.
    if _mentions(solver, _COUPLED_STEMS):
        code = coupled_oscillators.build(class_name, solver)
        if code is not None:
            return "coupled_oscillators", code

    # 10. Standing wave / normal mode on a string.
    if _mentions(solver, _STANDING_WAVE_STEMS):
        code = standing_wave.build(class_name, solver)
        if code is not None:
            return "standing_wave", code

    # 11. Thermodynamics / kinetic theory: a gas of bouncing particles.
    if _mentions(solver, _THERMO_STEMS):
        code = kinetic_theory.build(class_name, solver)
        if code is not None:
            return "kinetic_theory", code

    # 12. Fourier / series problems get the rotating-vector epicycle build.
    if _wants_fourier(solver):
        code = fourier_epicycles.build(class_name, solver)
        if code is not None:
            return "fourier_epicycles", code

    # 13. Phase-space framing (only when the prompt/summary explicitly asks) —
    #     the v-vs-x spiral is the insight, not the time series.
    if _wants_phase_portrait(solver):
        code = phase_portrait.build(class_name, solver)
        if code is not None:
            return "phase_portrait", code

    # 14. Exact 2-D time-series trajectory whenever the solver attached an ODE.
    code = trajectory.build(class_name, solver)
    if code is not None:
        return "trajectory", code

    # 15. Inherently-3-D problems get a real ThreeDScene scaffold.
    if plan is not None and getattr(plan, "needs_3d", False):
        code = surface3d.build(class_name, solver)
        if code is not None:
            return "surface3d", code

    return None


def _is_pendulum(solver: Any) -> bool:
    """True when the solver's domain is a pendulum (keyword or gravity+length)."""
    try:
        from aetherlab.services.scene_templates import detect_domain

        keywords = list(getattr(solver, "keywords", []) or [])
        variables = dict(getattr(solver, "variables", {}) or {})
        return detect_domain(keywords, variables) == "pendulum"
    except Exception:  # noqa: BLE001 — selection must never crash composition
        return False


def _is_orbit(solver: Any) -> bool:
    """True when the solver's domain is an orbit / Kepler / gravitation problem."""
    try:
        from aetherlab.services.scene_templates import detect_domain

        keywords = list(getattr(solver, "keywords", []) or [])
        variables = dict(getattr(solver, "variables", {}) or {})
        return detect_domain(keywords, variables) == "orbit"
    except Exception:  # noqa: BLE001 — selection must never crash composition
        return False


def _is_em_field(solver: Any) -> bool:
    """True when the solver's domain is electrostatics (charges/fields)."""
    try:
        from aetherlab.services.scene_templates import detect_domain

        keywords = list(getattr(solver, "keywords", []) or [])
        variables = dict(getattr(solver, "variables", {}) or {})
        return detect_domain(keywords, variables) == "em_field"
    except Exception:  # noqa: BLE001 — selection must never crash composition
        return False


_MIRROR_OPTICS_CUES = (
    "focal", "ray", "reflect", "curvature", "object distance", "image distance",
    "magnification", "real image", "virtual image",
)


def _is_mirror_optics(solver: Any) -> bool:
    """A curved-mirror optics problem: a named mirror type, or "mirror" plus optics cues."""
    if _mentions(solver, _MIRROR_STEMS):
        return True
    return _mentions(solver, ("mirror",)) and _mentions(solver, _MIRROR_OPTICS_CUES)


def _wants_fourier(solver: Any) -> bool:
    return _mentions(solver, _FOURIER_STEMS)


def _wants_phase_portrait(solver: Any) -> bool:
    return _mentions(solver, _PHASE_STEMS)


def _mentions(solver: Any, stems: tuple[str, ...]) -> bool:
    text = " ".join([
        " ".join(getattr(solver, "keywords", []) or []),
        getattr(solver, "summary", "") or "",
    ]).lower()
    return any(stem in text for stem in stems)
