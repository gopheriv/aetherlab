"""Shared motion helpers for curated Manim scene components (Agent 1).

Why this module exists: several curated builders bake numerically-integrated
solutions into self-contained Manim scenes (``manim`` + ``numpy`` only). The
generated code cannot import :mod:`aetherlab` — it must stay runnable in an
isolated Manim worker — so the reference implementations live here and the
templates inline the few lines they need. Keep every helper below pure
(stdlib, optional ``numpy``) so builders can also use them at codegen time.

Diagnosed jitter / abrupt-transition causes (Oct 2026 pass):

- **Stepwise index rounding** (orbit): ``planet_pt`` used
  ``int(round(tracker))`` to pick a baked sample, so the planet sat still and
  then jumped once per sample (~4 samples/s at 240 points / 6.5 s) instead of
  gliding. Fix: lerp between the two bracketing samples (continuous path).
- **Unclamped tracker reads** (double pendulum): ``ValueTracker.get_value()``
  can transiently overshoot ``[0, N-1]`` on the animate ramp; ``floor`` without
  a clamp then indexes out of range or snaps. Fix: clamp before indexing.
- **Pop-in additions** (trajectory tracer): ``self.add(tracer)`` makes the dot
  appear in one frame. Fix: ``FadeIn`` it so the eye tracks the handoff.
- **Eased physics time**: physics trackers (pendulum ``t_tracker``, orbit
  ``idx``) must animate with ``rate_func=linear`` so baked sample index maps
  to elapsed time; easing belongs on entrances/exits (titles, axes, cards),
  never on the data-driven sweep itself.
- **Numeric readout flicker**: readouts must derive from the same tracker as
  the figure (single source of truth) and round to fixed decimals so the last
  digit does not churn every frame.
"""

from __future__ import annotations

import math


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp ``value`` into ``[lo, hi]`` (tracker-overshoot guard)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(lo)
    if not math.isfinite(v):
        return float(lo)
    return max(float(lo), min(float(hi), v))


def smoothstep(alpha: float) -> float:
    """Perlin smoothstep easing for entrances/exits (NOT physics sweeps)."""
    try:
        a = max(0.0, min(1.0, float(alpha)))
    except (TypeError, ValueError):
        return 0.0
    return a * a * (3.0 - 2.0 * a)


def ease_in_out(alpha: float) -> float:
    """Cosine ease-in-out for camera moves and card transitions."""
    try:
        a = max(0.0, min(1.0, float(alpha)))
    except (TypeError, ValueError):
        return 0.0
    return 0.5 - 0.5 * math.cos(math.pi * a)


def lerp(a: float, b: float, fraction: float) -> float:
    """Frame-rate-independent linear blend between two bracketing samples."""
    try:
        f = max(0.0, min(1.0, float(fraction)))
        return float(a) * (1.0 - f) + float(b) * f
    except (TypeError, ValueError):
        return float(a)


def sample_bracket(position: float, count: int) -> tuple[int, int, float]:
    """Return ``(lo, hi, fraction)`` for continuous sampling of ``count`` points.

    ``position`` is a float sample index (e.g. ``tracker * (count - 1)``).
    Always safe to index ``[lo]`` and ``[hi]`` when ``count >= 1``.
    """
    if count <= 1:
        return 0, 0, 0.0
    p = clamp(position, 0.0, float(count - 1))
    lo = int(math.floor(p))
    lo = max(0, min(count - 1, lo))
    hi = min(lo + 1, count - 1)
    return lo, hi, p - lo


def format_readout(value: float, digits: int = 2) -> str:
    """Stable fixed-decimal readout text (no per-frame digit churn)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    if not math.isfinite(v):
        v = 0.0
    digits = max(0, min(6, int(digits)))
    text = f"{v:.{digits}f}"
    # Avoid "-0.00" flicker when the value crosses zero.
    if text.startswith("-") and float(text) == 0.0:
        text = text[1:]
    return text


def camera_static_hold() -> dict:
    """Purposeful-camera default: curated scenes hold a static frame.

    Rationale: the physics figure is the subject; unmotivated pans/zooms read
    as jitter on rewatch and fight the exhibit-style fixed staging. Builders
    that need a move should key it to a beat boundary with :func:`ease_in_out`.
    """
    return {"mode": "static", "ease": "ease_in_out"}
