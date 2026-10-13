"""Real-time interactive parametric canvas with glow trails.

Pure QPainter + numpy. No external dependencies beyond PyQt6.
Renders parametric curves derived from the solver's variables,
with live slider-driven updates and an animated tracer with fading trail.

ARCHITECTURE NOTES
- Sample cache vs pixel mapping: curve SAMPLES (t, x, y arrays) depend only on
  (params, t_range, t_steps) — never on the viewport. Zoom/pan only changes the
  data→pixel affine map, which is re-applied each paint with vectorized numpy
  (no per-point Python loops for curves; see _np_to_qpolygonf).
- Gaps: non-finite and extreme off-screen samples split a curve into separate
  polyline branches, so asymptotes (e.g. 1/t and tan(t)) do not become false
  bridges across the discontinuity.
- Trail lives in DATA space and is mapped at paint time, so it stays glued to
  the curve through zoom/pan.
- Tracer advances by wall-clock time (QElapsedTimer): one sweep takes
  SWEEP_SECONDS regardless of frame rate or timer jitter.
- All colors come from CANVAS_PALETTE, which mirrors the design tokens in
  aetherlab/ui/style.py (blue-graphite surfaces, sky-blue primary accent,
  emerald success, violet tertiary series, amber markers, and muted blue-gray text).
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from aetherlab.ui import icons, style
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt

require_qt()

log = logging.getLogger(__name__)

TRAIL_LENGTH = 24     # number of trail points to keep
SWEEP_SECONDS = 6.0   # wall-clock duration of one full tracer sweep
SNAP_RADIUS_PX = 24.0  # hover snapping distance to a curve sample
ZOOM_ANIM_MS = 120    # smooth-zoom animation duration
FADE_IN_MS = 300      # first-paint fade duration

# Resolve canvas colors from the same theme tokens as the rest of the app.
# Keeping these semantic roles in one place prevents the graph from drifting
# away from the selected Studio Light / custom palette.
CANVAS_PALETTE: dict[str, str] = {
    "bg_top": style.BG_CANVAS_TOP,
    "bg_bottom": style.BG_DEEPEST,
    "grid": style.BORDER_HAIRLINE,
    "grid_zero": style.BORDER_STRONG,
    "axis_text": style.TEXT_LOW,
    "frame": style.BORDER_STRONG,
    "text_high": style.TEXT_HIGH,
    "text_mid": style.TEXT_MID,
    "text_low": style.TEXT_LOW,
    "primary": style.CYAN,
    "secondary": style.EMERALD,
    "tertiary": style.VIOLET,
    "accent": style.AMBER,
    "reference": style.TEXT_LOW,
    "crosshair": style.BORDER_STRONG,
}

# Colors handed out to secondary-role curves, in order.
_SECONDARY_CYCLE = ("secondary", "tertiary", "accent")


@dataclass
class CurveSpec:
    """Describes a single parametric curve to draw on the canvas."""
    name: str
    x_fn: Any
    y_fn: Any
    color: str = CANVAS_PALETTE["primary"]
    width: float = 2.0
    t_range: tuple[float, float] = (-3.0, 3.0)
    t_steps: int = 500
    style: str = "solid"       # solid | dashed
    role: str = "primary"      # primary | secondary | reference
    visible: bool = True       # toggled from the interactive legend


@dataclass
class FillSpec:
    """Translucent region between two curves sharing the primary t grid."""
    upper_fn: Any
    lower_fn: Any
    color: str = CANVAS_PALETTE["primary"]


@dataclass
class MarkedPoint:
    """A labeled marker at parameter value t on the primary curve."""
    t: float
    label: str = ""


@dataclass
class CanvasState:
    """Full state of the live canvas — mutated by slider updates."""
    title: str = ""
    x_label: str = "x"
    y_label: str = "y"
    x_range: tuple[float, float] = (-4.0, 4.0)
    y_range: tuple[float, float] = (-3.0, 3.0)
    params: dict[str, float] = field(default_factory=dict)
    curves: list[CurveSpec] = field(default_factory=list)
    show_phase_portrait: bool = False
    fills: list[FillSpec] = field(default_factory=list)
    marked_points: list[MarkedPoint] = field(default_factory=list)


# ── Pre-built curve factories for common physics domains ──


def _damped_oscillator_curves(params: dict[str, float]) -> list[CurveSpec]:
    def x_fn(t, p):
        return t

    def y_fn(t, p):
        damp = p.get("damping", 0.15)
        stif = p.get("stiffness", 1.0)
        return np.exp(-damp * (t + 3)) * np.sin(stif * t * 2)

    return [CurveSpec(name="x(t)", x_fn=x_fn, y_fn=y_fn,
                      color=CANVAS_PALETTE["primary"], width=2.5)]


def _phase_portrait_curves(params: dict[str, float]) -> list[CurveSpec]:
    def x_fn(t, p):
        damp = p.get("damping", 0.15)
        stif = p.get("stiffness", 1.0)
        return np.exp(-damp * (t + 3)) * np.sin(stif * t * 2)

    def y_fn(t, p):
        damp = p.get("damping", 0.15)
        stif = p.get("stiffness", 1.0)
        dt = 0.01
        t2 = t + dt
        return (
            np.exp(-damp * (t2 + 3)) * np.sin(stif * t2 * 2)
            - np.exp(-damp * (t + 3)) * np.sin(stif * t * 2)
        ) / dt

    return [
        CurveSpec(
            name="phase",
            x_fn=x_fn,
            y_fn=y_fn,
            # Violet per the design: phase-portrait overlay is violet
            # (emerald is reserved for complete/success states).
            color=CANVAS_PALETTE["tertiary"],
            width=1.5,
            t_range=(-3.0, 3.0),
            t_steps=600,
            role="secondary",
        )
    ]


def _pendulum_curves(params: dict[str, float]) -> list[CurveSpec]:
    def x_fn(t, p):
        return t

    def y_fn(t, p):
        g = p.get("gravity", 9.81)
        length = p.get("length", 1.0)
        omega = math.sqrt(g / max(length, 0.01))
        return np.sin(omega * t) * 0.8

    return [CurveSpec(name="θ(t)", x_fn=x_fn, y_fn=y_fn,
                      color=CANVAS_PALETTE["tertiary"], width=2.5)]


def _generic_curves(params: dict[str, float]) -> list[CurveSpec]:
    names = sorted(params.keys())

    def x_fn(t, p):
        freq_a = p.get(names[0], 1.0) if names else 1.0
        return np.sin(freq_a * t * 2)

    def y_fn(t, p):
        freq_b = p.get(names[1], 0.5) if len(names) > 1 else 0.5
        return np.cos(freq_b * t * 3)

    return [CurveSpec(name="parametric", x_fn=x_fn, y_fn=y_fn,
                      color=CANVAS_PALETTE["accent"], width=2.5)]


_DOMAIN_MAP = {
    "damping": _damped_oscillator_curves,
    "stiffness": _damped_oscillator_curves,
    "gravity": _pendulum_curves,
    "length": _pendulum_curves,
}


def _auto_range(samples: np.ndarray, pad_frac: float = 0.08) -> tuple[float, float]:
    """Finite min/max of samples with padding; raises if nothing is finite."""
    finite = samples[np.isfinite(samples)]
    if finite.size == 0:
        raise ValueError("No finite samples to derive an axis range from.")
    lo, hi = float(finite.min()), float(finite.max())
    if lo == hi:
        lo -= 1.0
        hi += 1.0
    pad = (hi - lo) * pad_frac
    return lo - pad, hi + pad


def _phase_overlay_for(
    y_fn, t_range: tuple[float, float], params: dict[str, float]
) -> CurveSpec:
    """Finite-difference phase portrait (y vs dy/dt) for any compiled y_fn."""

    def px_fn(t, p):
        return y_fn(t, p)

    def py_fn(t, p):
        dt = max((t_range[1] - t_range[0]) / 2000.0, 1e-6)
        return (y_fn(t + dt, p) - y_fn(t, p)) / dt

    return CurveSpec(
        name="phase",
        x_fn=px_fn,
        y_fn=py_fn,
        color=CANVAS_PALETTE["tertiary"],
        width=1.5,
        t_range=t_range,
        t_steps=600,
        role="secondary",
    )


def _role_color(role: str, secondary_index: int) -> str:
    """Palette color for a compiled curve, assigned by role."""
    if role == "primary":
        return CANVAS_PALETTE["primary"]
    if role == "reference":
        return CANVAS_PALETTE["reference"]
    key = _SECONDARY_CYCLE[secondary_index % len(_SECONDARY_CYCLE)]
    return CANVAS_PALETTE[key]


def _state_from_plot(
    title: str,
    params: dict[str, float],
    plot: dict,
    phase_portrait: bool,
) -> CanvasState:
    """Build canvas state from a solver plot payload. Raises on any problem."""
    from aetherlab.services.plotting import compile_plot

    compiled = compile_plot(plot, params)

    t = np.linspace(compiled.t_range[0], compiled.t_range[1], 400)

    # Auto-range across every curve (and the fill bounds, if any) so nothing
    # the solver described is born clipped.
    all_xs: list[np.ndarray] = []
    all_ys: list[np.ndarray] = []
    for cc in compiled.curves:
        all_xs.append(np.asarray(cc.x_fn(t, params), dtype=float))
        all_ys.append(np.asarray(cc.y_fn(t, params), dtype=float))
    if compiled.fill is not None:
        upper_fn, lower_fn = compiled.fill
        all_ys.append(np.asarray(upper_fn(t, params), dtype=float))
        all_ys.append(np.asarray(lower_fn(t, params), dtype=float))

    x_range = compiled.x_range or _auto_range(np.concatenate(all_xs))
    y_range = compiled.y_range or _auto_range(np.concatenate(all_ys))

    curves: list[CurveSpec] = []
    secondary_seen = 0
    for cc in compiled.curves:
        color = _role_color(cc.role, secondary_seen)
        if cc.role == "secondary":
            secondary_seen += 1
        curves.append(
            CurveSpec(
                name=cc.name,
                x_fn=cc.x_fn,
                y_fn=cc.y_fn,
                color=color,
                width=2.5 if cc.role == "primary" else 1.5,
                t_range=compiled.t_range,
                t_steps=600,
                style=cc.style,
                role=cc.role,
            )
        )

    primary = next((c for c in curves if c.role == "primary"), curves[0])
    if phase_portrait:
        curves.append(_phase_overlay_for(primary.y_fn, compiled.t_range, params))

    fills: list[FillSpec] = []
    if compiled.fill is not None:
        fills.append(FillSpec(upper_fn=compiled.fill[0], lower_fn=compiled.fill[1],
                              color=primary.color))

    marked = [MarkedPoint(t=pt, label=lbl) for pt, lbl in compiled.points]

    return CanvasState(
        title=title,
        x_label=compiled.x_label,
        y_label=compiled.y_label,
        x_range=x_range,
        y_range=y_range,
        params=dict(params),
        curves=curves,
        show_phase_portrait=phase_portrait,
        fills=fills,
        marked_points=marked,
    )


def _state_from_numeric(
    title: str,
    params: dict[str, float],
    numeric_spec: dict,
    phase_portrait: bool,
) -> CanvasState:
    """Build canvas state from the exact numerically-integrated trajectory.

    Raises if scipy is missing or the spec is invalid so build_canvas_state can
    fall back to the analytic plot payload.
    """
    from aetherlab.services.numeric import solve_numeric

    sol = solve_numeric(numeric_spec, params)
    if not sol.ok or not sol.t:
        raise ValueError(sol.note or "numeric integration unavailable")

    num_t = np.asarray(sol.t, dtype=float)
    num_y = np.asarray(sol.series(), dtype=float)
    if num_t.size < 2 or num_y.size != num_t.size:
        raise ValueError("numeric solution too short to plot")

    def x_fn(t: np.ndarray, p: dict[str, float]) -> np.ndarray:
        return np.asarray(t, dtype=float)

    def y_fn(t: np.ndarray, p: dict[str, float], _t=num_t, _y=num_y) -> np.ndarray:
        return np.interp(np.asarray(t, dtype=float), _t, _y)

    observe = sol.observe or "x"
    curves = [
        CurveSpec(
            name=observe,
            x_fn=x_fn,
            y_fn=y_fn,
            color=CANVAS_PALETTE["primary"],
            width=2.5,
            t_range=(float(num_t[0]), float(num_t[-1])),
            t_steps=min(max(int(num_t.size), 200), 800),
            role="primary",
        )
    ]
    if phase_portrait:
        curves.append(_phase_overlay_for(y_fn, (float(num_t[0]), float(num_t[-1])), params))

    return CanvasState(
        title=title,
        x_label="t",
        y_label=observe,
        x_range=(float(num_t[0]), float(num_t[-1])),
        y_range=_auto_range(num_y),
        params=dict(params),
        curves=curves,
        show_phase_portrait=phase_portrait,
    )


def build_canvas_state(
    title: str,
    params: dict[str, float],
    phase_portrait: bool = False,
    plot: dict | None = None,
    numeric_spec: dict | None = None,
) -> CanvasState:
    """Build the canvas state.

    Prefers the exact numerically-integrated trajectory (services/numeric.py)
    when the solver attached an ODE spec; otherwise the solver's own plot
    payload (compiled safely — see services/plotting.py); any parse/compile
    problem falls back to the legacy name-based curve families so the canvas
    never crashes on bad LLM output.
    """
    if numeric_spec is not None:
        try:
            return _state_from_numeric(title, params, numeric_spec, phase_portrait)
        except Exception as exc:  # noqa: BLE001 — canvas must never crash
            log.warning("Numeric integration rejected (%s); trying analytic plot.", exc)
    if plot is not None:
        try:
            return _state_from_plot(title, params, plot, phase_portrait)
        except Exception as exc:  # noqa: BLE001 — canvas must never crash
            log.warning("Solver plot rejected (%s); using legacy curves.", exc)

    factory = _generic_curves
    for key in params:
        if key in _DOMAIN_MAP:
            factory = _DOMAIN_MAP[key]
            break

    curves = factory(params)
    if phase_portrait:
        curves.extend(_phase_portrait_curves(params))

    return CanvasState(
        title=title,
        params=dict(params),
        curves=curves,
        show_phase_portrait=phase_portrait,
    )


def _np_to_qpolygonf(px: np.ndarray, py: np.ndarray) -> QtGui.QPolygonF:
    """Vectorized numpy → QPolygonF (no per-point Python loop when possible).

    Uses the sip buffer of QPolygonF's contiguous qreal storage (the same
    technique pyqtgraph uses). Falls back to a list build if the buffer API
    is unavailable in the running binding.
    """
    n = int(px.shape[0])
    poly = QtGui.QPolygonF([QtCore.QPointF()] * n)
    try:
        buf = poly.data()
        buf.setsize(2 * n * 8)  # n points × (x, y) × 8-byte doubles
        view = np.frombuffer(buf, dtype=np.float64).reshape((n, 2))
        view[:, 0] = px
        view[:, 1] = py
    except Exception:  # pragma: no cover — binding without .data()
        poly = QtGui.QPolygonF([QtCore.QPointF(float(a), float(b))
                                for a, b in zip(px, py)])
    return poly


def _finite_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous [start, end) runs of True in a boolean mask (length ≥ 2).

    This is what turns NaN gaps into separate polyline branches.
    """
    if mask.size == 0:
        return []
    padded = np.concatenate(([False], mask, [False]))
    diffs = np.diff(padded.astype(np.int8))
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]
    return [(int(s), int(e)) for s, e in zip(starts, ends) if e - s >= 2]


def _drawable_sample_mask(
    px: np.ndarray, py: np.ndarray, plot_rect: QtCore.QRectF
) -> np.ndarray:
    """Reject non-finite points and extreme pixel spikes outside the viewport.

    QPainter clips the final polyline, but a finite value close to an
    asymptote can still be millions of pixels away. Connecting samples on
    either side would draw a false chord through the visible plot. A
    one-viewport overscan preserves segments that enter or leave the frame
    while turning those spikes into gaps for ``_finite_runs`` to split.
    """
    finite = np.isfinite(px) & np.isfinite(py)
    x_pad = max(float(plot_rect.width()), 1.0)
    y_pad = max(float(plot_rect.height()), 1.0)
    return (
        finite
        & (px >= plot_rect.left() - x_pad)
        & (px <= plot_rect.right() + x_pad)
        & (py >= plot_rect.top() - y_pad)
        & (py <= plot_rect.bottom() + y_pad)
    )


class LiveCanvas(QtWidgets.QWidget):
    """Real-time parametric curve renderer with glow trails and animated tracer.

    Performance: caches curve samples in data space (viewport-independent),
    maps to pixels each paint with vectorized numpy, caches fonts, and never
    loops per-point in Python for curve geometry.
    """

    png_exported = QtCore.pyqtSignal(str)

    # Cached fonts — zero allocation per paint event
    _TITLE_FONT = QtGui.QFont("Segoe UI", 12, QtGui.QFont.Weight.Bold)
    _LABEL_FONT = QtGui.QFont("Segoe UI", 9)
    _GRID_FONT = QtGui.QFont("Cascadia Code", 8)
    _TRACER_FONT = QtGui.QFont("Cascadia Code", 9)
    _LEGEND_FONT = QtGui.QFont("Segoe UI", 9)
    _CHIP_FONT = QtGui.QFont("Cascadia Code", 8)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(260, 180)
        self.setMouseTracking(True)
        self._state: CanvasState | None = None
        self._tracer_t = 0.0
        # Trail points are stored in DATA space; mapped to pixels at paint
        # time so zoom/pan never smears the comet trail.
        self._trail: deque[tuple[float, float]] = deque(maxlen=TRAIL_LENGTH)
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.setInterval(33)
        self._sweep_clock = QtCore.QElapsedTimer()
        self._margin = {"left": 60, "right": 20, "top": 44, "bottom": 44}

        # Sample cache: curve index -> (t, xs, ys); viewport-independent.
        self._sample_key: tuple | None = None
        self._samples: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        self._fill_samples: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        # Pixel cache rebuilt each paint; consumed by hover snapping.
        self._pixel_cache: list[tuple[int, np.ndarray, np.ndarray, np.ndarray]] = []

        # Zoom/pan state (#11)
        self._zoom_factor = 1.0
        self._pan_offset = QtCore.QPointF(0.0, 0.0)
        self._dragging = False
        self._drag_start = QtCore.QPoint()
        self._hover_pos: QtCore.QPointF | None = None
        self._hover_coords: tuple[float, float] | None = None
        # (curve_index, t, x, y, px, py) when the cursor snapped to a sample
        self._hover_snap: tuple[int, float, float, float, float, float] | None = None

        # Smooth zoom (target-based; ~120ms animation, cursor-anchored)
        self.smooth_zoom_enabled = True
        self._zoom_target = 1.0
        self._zoom_anchor = QtCore.QPointF(0.0, 0.0)
        self._zoom_anim = QtCore.QVariantAnimation(self)
        self._zoom_anim.setDuration(ZOOM_ANIM_MS)
        self._zoom_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._zoom_anim.valueChanged.connect(self._on_zoom_anim)

        # Time scrubbing (right-drag / Shift+drag)
        self._scrubbing = False

        # First-paint fade-in
        self._fade_alpha = 1.0
        self._fade_anim = QtCore.QVariantAnimation(self)
        self._fade_anim.setDuration(FADE_IN_MS)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.valueChanged.connect(self._on_fade_anim)

        # Interactive legend hit boxes: (rect, curve_index), widget coords.
        self._legend_hits: list[tuple[QtCore.QRectF, int]] = []

        # Hover-revealed PNG export button (ghost style per the design system)
        self._export_btn = QtWidgets.QToolButton(self)
        self._export_btn.setObjectName("CanvasExportButton")
        self._export_btn.setIcon(icons.icon("camera", 15, CANVAS_PALETTE["text_mid"]))
        self._export_btn.setToolTip("Export canvas as PNG (2×)")
        self._export_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._export_btn.setFixedSize(30, 30)
        self._export_btn.clicked.connect(self.save_png)
        self._export_btn.hide()

    # ── public API ──

    def set_state(self, state: CanvasState) -> None:
        had_curves = bool(self._state and self._state.curves)
        self._state = state
        self._invalidate_samples()
        self._tracer_t = state.curves[0].t_range[0] if state.curves else 0.0
        self._trail.clear()
        # Reset zoom/pan on new state
        self._zoom_factor = 1.0
        self._zoom_target = 1.0
        self._pan_offset = QtCore.QPointF(0.0, 0.0)
        self._sweep_clock.invalidate()
        if not self._anim_timer.isActive():
            self._anim_timer.start()
        # Fade the very first curve in instead of popping (#18) — but never
        # flicker on subsequent updates (slider drags rebuild state often).
        if state.curves and not had_curves:
            self._fade_alpha = 0.0
            self._fade_anim.stop()
            self._fade_anim.start()
        self.update()

    def update_params(self, params: dict[str, float]) -> None:
        if self._state:
            self._state.params.update(params)
            self._invalidate_samples()
            self._trail.clear()
            self.update()

    def stop(self) -> None:
        self._anim_timer.stop()

    def reset_view(self) -> None:
        """Reset zoom and pan to defaults."""
        self._zoom_anim.stop()
        self._zoom_factor = 1.0
        self._zoom_target = 1.0
        self._pan_offset = QtCore.QPointF(0.0, 0.0)
        self.update()

    def toggle_curve_visibility(self, index: int) -> None:
        """Show/hide a curve (interactive legend, #16)."""
        if self._state and 0 <= index < len(self._state.curves):
            curve = self._state.curves[index]
            curve.visible = not curve.visible
            self.update()

    def save_png(self, path: str | None = None) -> str | None:
        """Export the current canvas at 2× resolution to a PNG (#15).

        Returns the written path, or None if the user cancelled the dialog.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export canvas as PNG", "canvas.png", "PNG Images (*.png)"
            )
            if not path:
                return None
        pixmap = QtGui.QPixmap(self.size() * 2)
        pixmap.setDevicePixelRatio(2.0)
        pixmap.fill(QtGui.QColor(CANVAS_PALETTE["bg_bottom"]))
        was_visible = self._export_btn.isVisible()
        self._export_btn.hide()  # keep chrome out of the export
        try:
            self.render(pixmap)
        finally:
            if was_visible:
                self._export_btn.show()
        pixmap.save(path, "PNG")
        self.png_exported.emit(path)
        return path

    # ── zoom / pan / view helpers ──

    def _plot_rect(self) -> QtCore.QRectF:
        rect = self.rect()
        m = self._margin
        return QtCore.QRectF(
            m["left"], m["top"],
            max(rect.width() - m["left"] - m["right"], 1),
            max(rect.height() - m["top"] - m["bottom"], 1),
        )

    def _effective_ranges(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Return (x_range, y_range) adjusted for zoom and pan."""
        if not self._state:
            return (-4.0, 4.0), (-3.0, 3.0)
        x_min, x_max = self._state.x_range
        y_min, y_max = self._state.y_range
        x_center = (x_min + x_max) / 2 + self._pan_offset.x()
        y_center = (y_min + y_max) / 2 + self._pan_offset.y()
        x_half = (x_max - x_min) / 2 / self._zoom_factor
        y_half = (y_max - y_min) / 2 / self._zoom_factor
        return (x_center - x_half, x_center + x_half), (y_center - y_half, y_center + y_half)

    def _pixel_to_data(self, px: float, py: float, plot_rect: QtCore.QRectF) -> tuple[float, float]:
        """Convert pixel coordinates to data coordinates using effective ranges."""
        x_range, y_range = self._effective_ranges()
        x_min, x_max = x_range
        y_min, y_max = y_range
        x = x_min + (px - plot_rect.left()) / plot_rect.width() * (x_max - x_min)
        y = y_max - (py - plot_rect.top()) / plot_rect.height() * (y_max - y_min)
        return x, y

    def _apply_zoom(self, new_zoom: float, anchor_px: QtCore.QPointF) -> None:
        """Set the zoom so the data point under anchor_px stays put (#1)."""
        new_zoom = max(0.1, min(new_zoom, 50.0))
        plot_rect = self._plot_rect()
        before = self._pixel_to_data(anchor_px.x(), anchor_px.y(), plot_rect)
        self._zoom_factor = new_zoom
        after = self._pixel_to_data(anchor_px.x(), anchor_px.y(), plot_rect)
        self._pan_offset += QtCore.QPointF(before[0] - after[0], before[1] - after[1])
        self.update()

    def _on_zoom_anim(self, value: object) -> None:
        try:
            self._apply_zoom(float(value), self._zoom_anchor)
        except (TypeError, ValueError):
            pass

    def _on_fade_anim(self, value: object) -> None:
        try:
            self._fade_alpha = float(value)
        except (TypeError, ValueError):
            self._fade_alpha = 1.0
        self.update()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return
        step = 1.15 if delta > 0 else 1 / 1.15
        self._zoom_target = max(0.1, min(self._zoom_target * step, 50.0))
        self._zoom_anchor = QtCore.QPointF(event.position())
        if self.smooth_zoom_enabled:
            # Animate from the CURRENT zoom toward the target (#12); repeated
            # wheel notches retarget mid-flight without jumps.
            self._zoom_anim.stop()
            self._zoom_anim.setStartValue(float(self._zoom_factor))
            self._zoom_anim.setEndValue(float(self._zoom_target))
            self._zoom_anim.start()
        else:
            self._apply_zoom(self._zoom_target, self._zoom_anchor)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        # Double-click = reset view (#14), alongside Ctrl+0.
        self.reset_view()
        super().mouseDoubleClickEvent(event)

    # ── mouse: pan, scrub, legend, hover ──

    def _legend_hit(self, pos: QtCore.QPointF) -> int | None:
        for rect, index in self._legend_hits:
            if rect.contains(pos):
                return index
        return None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        pos = QtCore.QPointF(event.position())
        shift = bool(event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier)
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            hit = self._legend_hit(pos)
            if hit is not None:
                self.toggle_curve_visibility(hit)
                return
            if shift:
                self._begin_scrub(pos)
                return
            self._dragging = True
            self._drag_start = event.pos()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            self._begin_scrub(pos)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        if self._scrubbing and event.button() in (
            QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.LeftButton
        ):
            self._scrubbing = False
            self._sweep_clock.invalidate()  # resume cleanly from scrubbed t
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            self.update()

    def _begin_scrub(self, pos: QtCore.QPointF) -> None:
        if not (self._state and self._state.curves):
            return
        self._scrubbing = True
        self._trail.clear()
        self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        self._scrub_to(pos)

    def _scrub_to(self, pos: QtCore.QPointF) -> None:
        """Map cursor x within the plot to tracer t on the primary curve (#13)."""
        curve = self._primary_curve()
        if curve is None:
            return
        plot_rect = self._plot_rect()
        frac = (pos.x() - plot_rect.left()) / max(plot_rect.width(), 1.0)
        frac = min(max(frac, 0.0), 1.0)
        t0, t1 = curve.t_range
        self._tracer_t = t0 + frac * (t1 - t0)
        self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        pos = QtCore.QPointF(event.position())

        if self._scrubbing:
            self._scrub_to(pos)
            return

        if self._dragging and self._state:
            dx = event.pos().x() - self._drag_start.x()
            dy = event.pos().y() - self._drag_start.y()
            self._drag_start = event.pos()
            x_range, y_range = self._effective_ranges()
            plot_rect = self._plot_rect()
            data_dx = -dx / plot_rect.width() * (x_range[1] - x_range[0])
            data_dy = dy / plot_rect.height() * (y_range[1] - y_range[0])
            self._pan_offset += QtCore.QPointF(data_dx, data_dy)
            self.update()

        # Hover: legend hand cursor, snapping, raw coords fallback (#4)
        self._hover_pos = pos
        if not self._dragging:
            over_legend = self._legend_hit(pos) is not None
            self.setCursor(
                QtCore.Qt.CursorShape.PointingHandCursor
                if over_legend
                else QtCore.Qt.CursorShape.ArrowCursor
            )
        self._update_hover(pos)
        self.update()

    def _update_hover(self, pos: QtCore.QPointF) -> None:
        self._hover_snap = None
        self._hover_coords = None
        if not (self._state and self._state.curves):
            return
        plot_rect = self._plot_rect()
        if not plot_rect.contains(pos):
            return
        # Nearest-sample snapping across visible, non-reference curves.
        best: tuple[float, int, int] | None = None  # (dist2, curve_idx, sample_idx)
        mx, my = pos.x(), pos.y()
        for idx, px, py, _t in self._pixel_cache:
            if px.size == 0:
                continue
            d2 = (px - mx) ** 2 + (py - my) ** 2
            j = int(np.nanargmin(d2))
            dj = float(d2[j])
            if math.isfinite(dj) and (best is None or dj < best[0]):
                best = (dj, idx, j)
        if best is not None and best[0] <= SNAP_RADIUS_PX ** 2:
            _, idx, j = best
            for cidx, px, py, t_arr in self._pixel_cache:
                if cidx == idx:
                    xs, ys = self._samples[idx][1], self._samples[idx][2]
                    self._hover_snap = (
                        idx, float(t_arr[j]), float(xs[j]), float(ys[j]),
                        float(px[j]), float(py[j]),
                    )
                    return
        self._hover_coords = self._pixel_to_data(pos.x(), pos.y(), plot_rect)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._hover_pos = None
        self._hover_coords = None
        self._hover_snap = None
        self._export_btn.hide()
        self.update()
        super().leaveEvent(event)

    def enterEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._export_btn.show()
        super().enterEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        self._export_btn.move(self.width() - self._export_btn.width() - 8, 8)
        super().resizeEvent(event)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        # Only animate while visible — avoids burning CPU on a hidden tab.
        self._sweep_clock.invalidate()
        if self._state and self._state.curves and not self._anim_timer.isActive():
            self._anim_timer.start()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        self._anim_timer.stop()

    # ── animation ──

    def _primary_curve(self) -> CurveSpec | None:
        """The curve the tracer rides: first visible non-reference curve."""
        if not (self._state and self._state.curves):
            return None
        for curve in self._state.curves:
            if curve.visible and curve.role != "reference":
                return curve
        for curve in self._state.curves:
            if curve.visible:
                return curve
        return None

    def _tick(self) -> None:
        if not self._state or not self._state.curves:
            return
        curve = self._primary_curve()
        if curve is None:
            return

        # Wall-clock advance (#3): one sweep takes SWEEP_SECONDS regardless of
        # timer jitter. The first tick after a pause only starts the clock.
        if self._scrubbing:
            return
        if not self._sweep_clock.isValid():
            self._sweep_clock.start()
            return
        dt = self._sweep_clock.restart() / 1000.0
        dt = min(dt, 0.25)  # clamp catch-up after stalls

        t_min, t_max = curve.t_range
        self._tracer_t += (t_max - t_min) * dt / SWEEP_SECONDS
        if self._tracer_t > t_max:
            self._tracer_t = t_min
            self._trail.clear()

        # Append tracer position to the trail in DATA space (#2).
        try:
            t_arr = np.array([self._tracer_t])
            x = float(curve.x_fn(t_arr, self._state.params)[0])
            y = float(curve.y_fn(t_arr, self._state.params)[0])
            if np.isfinite(x) and np.isfinite(y):
                self._trail.append((x, y))
        except Exception:
            pass

        self.update()

    # ── sample cache (#6) ──

    def _invalidate_samples(self) -> None:
        self._sample_key = None
        self._samples.clear()
        self._fill_samples.clear()

    def _build_sample_key(self, state: CanvasState) -> tuple:
        # Viewport (x/y ranges, zoom, pan) is deliberately EXCLUDED: samples
        # are functions of t and params only.
        return (
            tuple(sorted(state.params.items())),
            tuple((c.name, c.t_range, c.t_steps) for c in state.curves),
            len(state.fills),
        )

    def _ensure_samples(self, state: CanvasState) -> None:
        key = self._build_sample_key(state)
        if key == self._sample_key:
            return
        self._samples.clear()
        self._fill_samples.clear()
        for idx, curve in enumerate(state.curves):
            t = np.linspace(curve.t_range[0], curve.t_range[1], curve.t_steps)
            try:
                xs = np.asarray(curve.x_fn(t, state.params), dtype=float)
                ys = np.asarray(curve.y_fn(t, state.params), dtype=float)
            except Exception:
                xs = np.full_like(t, np.nan)
                ys = np.full_like(t, np.nan)
            self._samples[idx] = (t, xs, ys)
        if state.fills and state.curves:
            primary = state.curves[0]
            t = np.linspace(primary.t_range[0], primary.t_range[1], primary.t_steps)
            for fill in state.fills:
                try:
                    upper = np.asarray(fill.upper_fn(t, state.params), dtype=float)
                    lower = np.asarray(fill.lower_fn(t, state.params), dtype=float)
                except Exception:
                    upper = np.full_like(t, np.nan)
                    lower = np.full_like(t, np.nan)
                self._fill_samples.append((t, upper, lower))
        self._sample_key = key

    def _map_arrays(
        self, xs: np.ndarray, ys: np.ndarray, plot_rect: QtCore.QRectF
    ) -> tuple[np.ndarray, np.ndarray]:
        """Vectorized data→pixel mapping under the current zoom/pan."""
        (x_min, x_max), (y_min, y_max) = self._effective_ranges()
        x_span = x_max - x_min
        y_span = y_max - y_min
        if abs(x_span) < 1e-12:
            px = np.full_like(xs, plot_rect.left() + plot_rect.width() / 2)
        else:
            px = plot_rect.left() + (xs - x_min) * (plot_rect.width() / x_span)
        if abs(y_span) < 1e-12:
            py = np.full_like(ys, plot_rect.top() + plot_rect.height() / 2)
        else:
            py = plot_rect.bottom() - (ys - y_min) * (plot_rect.height() / y_span)
        return px, py

    def _map_to_plot(
        self, x: float, y: float, plot_rect: QtCore.QRectF, state: CanvasState
    ) -> QtCore.QPointF:
        x_min, x_max = state.x_range
        y_min, y_max = state.y_range
        x_span = x_max - x_min
        y_span = y_max - y_min
        # Guard against division by zero on extreme zoom
        if abs(x_span) < 1e-12:
            px = plot_rect.left() + plot_rect.width() / 2
        else:
            px = plot_rect.left() + (x - x_min) / x_span * plot_rect.width()
        if abs(y_span) < 1e-12:
            py = plot_rect.top() + plot_rect.height() / 2
        else:
            py = plot_rect.bottom() - (y - y_min) / y_span * plot_rect.height()
        return QtCore.QPointF(px, py)

    # ── painting ──

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Background (QRadialGradient needs QPointF, not QPoint, in PyQt6)
        bg_gradient = QtGui.QRadialGradient(
            QtCore.QPointF(rect.center()), max(rect.width(), rect.height()) * 0.7
        )
        bg_gradient.setColorAt(0, QtGui.QColor(CANVAS_PALETTE["bg_top"]))
        bg_gradient.setColorAt(1, QtGui.QColor(CANVAS_PALETTE["bg_bottom"]))
        painter.fillRect(rect, bg_gradient)

        if not self._state or not self._state.curves:
            # Empty state with onboarding hint (#12)
            painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_low"]))
            painter.setFont(QtGui.QFont("Segoe UI", 14))
            painter.drawText(
                rect.adjusted(0, -40, 0, 0),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "No curve data",
            )
            painter.setPen(QtGui.QColor(CANVAS_PALETTE["axis_text"]))
            painter.setFont(QtGui.QFont("Segoe UI", 11))
            painter.drawText(
                rect.adjusted(0, 20, 0, 0),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "Enter a physics problem below and press Run to get started.",
            )
            return

        state = self._state
        plot_rect = self._plot_rect()
        eff_x, eff_y = self._effective_ranges()
        # Lightweight state view for text/grid helpers that take ranges.
        paint_state = CanvasState(
            title=state.title, x_label=state.x_label, y_label=state.y_label,
            x_range=eff_x, y_range=eff_y, params=state.params,
            curves=state.curves, show_phase_portrait=state.show_phase_portrait,
        )

        # Title
        painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_high"]))
        painter.setFont(self._TITLE_FONT)
        painter.drawText(
            QtCore.QRectF(self._margin["left"], 6, plot_rect.width(), self._margin["top"] - 6),
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
            state.title,
        )

        # Grid + axes
        self._draw_grid(painter, plot_rect, paint_state)
        self._draw_axes(painter, plot_rect, paint_state)

        # Samples (viewport-independent) + per-paint pixel mapping
        self._ensure_samples(state)
        self._pixel_cache = []
        pixel_arrays: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for idx, curve in enumerate(state.curves):
            t_arr, xs, ys = self._samples.get(
                idx, (np.array([]), np.array([]), np.array([]))
            )
            px, py = self._map_arrays(xs, ys, plot_rect)
            mask = _drawable_sample_mask(px, py, plot_rect)
            pixel_arrays[idx] = (px, py, mask)
            if curve.visible and curve.role != "reference":
                finite_px = np.where(mask, px, np.nan)
                finite_py = np.where(mask, py, np.nan)
                self._pixel_cache.append((idx, finite_px, finite_py, t_arr))

        painter.save()
        painter.setClipRect(plot_rect)
        painter.setOpacity(self._fade_alpha)

        # Region shading first (behind everything) (#9)
        self._draw_fills(painter, plot_rect)

        # Curves — NaN gaps become separate branches (#6)
        for idx, curve in enumerate(state.curves):
            if not curve.visible:
                continue
            px, py, mask = pixel_arrays[idx]
            self._draw_curve(painter, curve, px, py, mask)

        # Marked points (#10)
        self._draw_marked_points(painter, plot_rect, state)

        # Trail (data space → pixels at paint time, #2)
        self._draw_trail(painter, plot_rect)

        # Tracer rides the primary curve
        primary = self._primary_curve()
        if primary is not None:
            self._draw_tracer(painter, plot_rect, state, primary)

        painter.restore()
        painter.setOpacity(1.0)

        # t-progress bar along the bottom axis (#13)
        self._draw_progress_bar(painter, plot_rect)

        # Legend (interactive, always shown for named curves) (#16)
        self._draw_legend(painter, plot_rect, state)

        # Param chip + zoom indicator (#17)
        self._draw_param_chip(painter, plot_rect, state)

        # Hover: snapped sample or raw coords (#4)
        self._draw_hover(painter, plot_rect, state)

    def _draw_fills(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        if not (self._state and self._state.fills and self._fill_samples):
            return
        for fill, (t, upper, lower) in zip(self._state.fills, self._fill_samples):
            upper_px, upper_py = self._map_arrays(t, upper, plot_rect)
            lower_px, lower_py = self._map_arrays(t, lower, plot_rect)
            mask = _drawable_sample_mask(upper_px, upper_py, plot_rect)
            mask &= _drawable_sample_mask(lower_px, lower_py, plot_rect)
            for start, end in _finite_runs(mask):
                poly_x = np.concatenate(
                    [upper_px[start:end], lower_px[start:end][::-1]]
                )
                poly_y = np.concatenate(
                    [upper_py[start:end], lower_py[start:end][::-1]]
                )
                polygon = _np_to_qpolygonf(poly_x, poly_y)
                top = QtGui.QColor(fill.color)
                top.setAlphaF(0.12)
                bottom = QtGui.QColor(fill.color)
                bottom.setAlphaF(0.03)
                gradient = QtGui.QLinearGradient(
                    QtCore.QPointF(0, plot_rect.top()),
                    QtCore.QPointF(0, plot_rect.bottom()),
                )
                gradient.setColorAt(0.0, top)
                gradient.setColorAt(1.0, bottom)
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(QtGui.QBrush(gradient))
                painter.drawPolygon(polygon)

    def _draw_curve(
        self,
        painter: QtGui.QPainter,
        curve: CurveSpec,
        px: np.ndarray,
        py: np.ndarray,
        mask: np.ndarray,
    ) -> None:
        runs = _finite_runs(mask)
        if not runs:
            return

        is_reference = curve.role == "reference"
        color = QtGui.QColor(curve.color)

        main_pen = QtGui.QPen(color, curve.width if not is_reference else max(curve.width, 1.0))
        main_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        main_pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        if curve.style == "dashed" or is_reference:
            main_pen.setStyle(QtCore.Qt.PenStyle.CustomDashLine)
            main_pen.setDashPattern([5.0, 4.0])

        glow_pen = None
        if not is_reference:
            glow_color = QtGui.QColor(curve.color)
            glow_color.setAlphaF(0.15)
            glow_pen = QtGui.QPen(glow_color, curve.width * 4)
            glow_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            glow_pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)

        for start, end in runs:
            polygon = _np_to_qpolygonf(px[start:end], py[start:end])
            if glow_pen is not None:
                painter.setPen(glow_pen)
                painter.drawPolyline(polygon)
            painter.setPen(main_pen)
            painter.drawPolyline(polygon)

    def _draw_marked_points(
        self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF, state: CanvasState
    ) -> None:
        if not state.marked_points:
            return
        primary = self._primary_curve()
        if primary is None:
            return
        accent = QtGui.QColor(CANVAS_PALETTE["accent"])
        painter.setFont(self._GRID_FONT)
        eff_state = CanvasState(x_range=self._effective_ranges()[0],
                                y_range=self._effective_ranges()[1])
        for mp in state.marked_points:
            try:
                t_arr = np.array([mp.t])
                x = float(primary.x_fn(t_arr, state.params)[0])
                y = float(primary.y_fn(t_arr, state.params)[0])
            except Exception:
                continue
            if not (np.isfinite(x) and np.isfinite(y)):
                continue
            pt = self._map_to_plot(x, y, plot_rect, eff_state)
            painter.setPen(QtGui.QPen(accent, 1.6))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawEllipse(pt, 6, 6)
            painter.setBrush(accent)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawEllipse(pt, 2, 2)
            if mp.label:
                painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_mid"]))
                painter.drawText(
                    QtCore.QRectF(pt.x() + 9, pt.y() - 16, 160, 14),
                    QtCore.Qt.AlignmentFlag.AlignLeft,
                    mp.label,
                )

    def _draw_trail(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        if not (self._state and self._state.curves):
            return
        n = len(self._trail)
        if n == 0:
            return
        primary = self._primary_curve()
        if primary is None:
            return
        eff_state = CanvasState(x_range=self._effective_ranges()[0],
                                y_range=self._effective_ranges()[1])
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        for i, (x, y) in enumerate(self._trail):
            alpha = (i + 1) / n
            color = QtGui.QColor(primary.color)
            color.setAlphaF(alpha * 0.4)
            painter.setBrush(color)
            pt = self._map_to_plot(x, y, plot_rect, eff_state)
            painter.drawEllipse(pt, 2 + alpha * 3, 2 + alpha * 3)

    def _draw_tracer(
        self,
        painter: QtGui.QPainter,
        plot_rect: QtCore.QRectF,
        state: CanvasState,
        curve: CurveSpec,
    ) -> None:
        try:
            t = np.array([self._tracer_t])
            x = float(curve.x_fn(t, state.params)[0])
            y = float(curve.y_fn(t, state.params)[0])
        except Exception:
            return

        if not (np.isfinite(x) and np.isfinite(y)):
            return

        eff_state = CanvasState(x_range=self._effective_ranges()[0],
                                y_range=self._effective_ranges()[1])
        pt = self._map_to_plot(x, y, plot_rect, eff_state)

        # Outer glow — simple filled ellipse, no gradient
        glow_color = QtGui.QColor(curve.color)
        glow_color.setAlpha(48)
        painter.setBrush(glow_color)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(pt, 12, 12)

        # Inner ring
        painter.setPen(QtGui.QPen(QtGui.QColor(curve.color), 1.5))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawEllipse(pt, 10, 10)

        # Core dot
        painter.setBrush(QtGui.QColor(curve.color))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(pt, 5, 5)

        # Coordinate label
        painter.setFont(self._TRACER_FONT)
        painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_mid"]))
        painter.drawText(
            QtCore.QRectF(pt.x() + 14, pt.y() - 18, 140, 16),
            QtCore.Qt.AlignmentFlag.AlignLeft,
            f"({x:.2f}, {y:.2f})",
        )

    def _draw_progress_bar(self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF) -> None:
        primary = self._primary_curve()
        if primary is None:
            return
        t0, t1 = primary.t_range
        span = t1 - t0
        if span <= 0:
            return
        frac = min(max((self._tracer_t - t0) / span, 0.0), 1.0)
        bar_y = plot_rect.bottom() - 3
        track = QtGui.QColor(CANVAS_PALETTE["grid"])
        track.setAlphaF(0.6)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRect(QtCore.QRectF(plot_rect.left(), bar_y, plot_rect.width(), 2))
        fill = QtGui.QColor(CANVAS_PALETTE["primary"])
        fill.setAlphaF(0.85 if self._scrubbing else 0.35)
        painter.setBrush(fill)
        painter.drawRect(QtCore.QRectF(plot_rect.left(), bar_y, plot_rect.width() * frac, 2))

    def _draw_grid(
        self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF, state: CanvasState
    ) -> None:
        painter.setFont(self._GRID_FONT)
        x_min, x_max = state.x_range
        y_min, y_max = state.y_range

        x_step = _nice_step(x_max - x_min, 8)
        x = math.ceil(x_min / x_step) * x_step
        while x <= x_max:
            pt = self._map_to_plot(x, 0, plot_rect, state)
            is_zero = abs(x) < x_step * 0.01
            color = CANVAS_PALETTE["grid_zero"] if is_zero else CANVAS_PALETTE["grid"]
            painter.setPen(QtGui.QColor(color))
            painter.drawLine(
                QtCore.QPointF(pt.x(), plot_rect.top()),
                QtCore.QPointF(pt.x(), plot_rect.bottom()),
            )
            painter.setPen(QtGui.QColor(CANVAS_PALETTE["axis_text"]))
            painter.drawText(
                QtCore.QRectF(pt.x() - 22, plot_rect.bottom() + 2, 44, 16),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "0" if is_zero else f"{x:g}",
            )
            x += x_step

        y_step = _nice_step(y_max - y_min, 6)
        y = math.ceil(y_min / y_step) * y_step
        while y <= y_max:
            pt = self._map_to_plot(0, y, plot_rect, state)
            is_zero = abs(y) < y_step * 0.01
            color = CANVAS_PALETTE["grid_zero"] if is_zero else CANVAS_PALETTE["grid"]
            painter.setPen(QtGui.QColor(color))
            painter.drawLine(
                QtCore.QPointF(plot_rect.left(), pt.y()),
                QtCore.QPointF(plot_rect.right(), pt.y()),
            )
            painter.setPen(QtGui.QColor(CANVAS_PALETTE["axis_text"]))
            painter.drawText(
                QtCore.QRectF(plot_rect.left() - 52, pt.y() - 8, 48, 16),
                QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
                "0" if is_zero else f"{y:g}",
            )
            y += y_step

    def _draw_axes(
        self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF, state: CanvasState
    ) -> None:
        painter.setPen(QtGui.QColor(CANVAS_PALETTE["frame"]))
        painter.drawRect(plot_rect)

        painter.setFont(self._LABEL_FONT)
        painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_low"]))
        painter.drawText(
            QtCore.QRectF(plot_rect.left(), plot_rect.bottom() + 4, plot_rect.width(), 20),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            state.x_label,
        )
        painter.save()
        painter.translate(14, plot_rect.center().y())
        painter.rotate(-90)
        painter.drawText(
            QtCore.QRectF(-plot_rect.height() / 2, -10, plot_rect.height(), 20),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            state.y_label,
        )
        painter.restore()

    def _draw_legend(
        self,
        painter: QtGui.QPainter,
        plot_rect: QtCore.QRectF,
        state: CanvasState,
    ) -> None:
        self._legend_hits = []
        named = [(i, c) for i, c in enumerate(state.curves) if c.name]
        if not named:
            return
        painter.setFont(self._LEGEND_FONT)
        x = plot_rect.right() - 12
        y = plot_rect.top() + 26  # below the param chip row
        for index, curve in named:
            entry_rect = QtCore.QRectF(x - 96, y - 4, 96, 17)
            self._legend_hits.append((entry_rect, index))
            if curve.visible:
                swatch = QtGui.QColor(curve.color)
                text_color = QtGui.QColor(curve.color)
                painter.setBrush(swatch)
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.drawRoundedRect(int(x - 88), int(y - 2), 10, 10, 2, 2)
            else:
                # Muted, hollow swatch when hidden (#16)
                muted = QtGui.QColor(CANVAS_PALETTE["text_low"])
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.setPen(QtGui.QPen(muted, 1))
                painter.drawRoundedRect(int(x - 88), int(y - 2), 10, 10, 2, 2)
                text_color = muted
            painter.setPen(text_color)
            # Snapped-curve highlight (#4)
            if self._hover_snap is not None and self._hover_snap[0] == index:
                painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_high"]))
            painter.drawText(
                QtCore.QRectF(x - 76, y - 2, 76, 14),
                QtCore.Qt.AlignmentFlag.AlignRight,
                curve.name,
            )
            y += 18

    def _draw_param_chip(
        self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF, state: CanvasState
    ) -> None:
        parts = [f"{k}={v:g}" for k, v in sorted(state.params.items())]
        if abs(self._zoom_factor - 1.0) > 0.01:
            parts.append(f"· {self._zoom_factor:.1f}x")
        if not parts:
            return
        text = "  ".join(parts)
        painter.setFont(self._CHIP_FONT)
        painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_low"]))
        painter.drawText(
            QtCore.QRectF(plot_rect.left(), plot_rect.top() + 4, plot_rect.width() - 12, 14),
            QtCore.Qt.AlignmentFlag.AlignRight,
            text,
        )

    def _draw_hover(
        self, painter: QtGui.QPainter, plot_rect: QtCore.QRectF, state: CanvasState
    ) -> None:
        if self._hover_pos is None or not plot_rect.contains(self._hover_pos):
            return

        if self._hover_snap is not None:
            idx, t, x, y, px, py = self._hover_snap
            color = QtGui.QColor(state.curves[idx].color)
            # Crosshair locked to the snapped sample
            cross_pen = QtGui.QPen(QtGui.QColor(CANVAS_PALETTE["crosshair"]), 1,
                                   QtCore.Qt.PenStyle.DotLine)
            painter.setPen(cross_pen)
            painter.drawLine(QtCore.QPointF(px, plot_rect.top()),
                             QtCore.QPointF(px, plot_rect.bottom()))
            painter.drawLine(QtCore.QPointF(plot_rect.left(), py),
                             QtCore.QPointF(plot_rect.right(), py))
            # Snap marker
            painter.setPen(QtGui.QPen(color, 1.5))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QtCore.QPointF(px, py), 7, 7)
            # (t, x, y) readout
            painter.setFont(self._TRACER_FONT)
            label = f"t={t:.3f}  ({x:.3f}, {y:.3f})"
            lx = min(px + 14, plot_rect.right() - 190)
            ly = max(py - 22, plot_rect.top() + 16)
            painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_mid"]))
            painter.drawText(QtCore.QRectF(lx, ly, 200, 16),
                             QtCore.Qt.AlignmentFlag.AlignLeft, label)
            return

        if self._hover_coords is None:
            return
        hx, hy = self._hover_coords
        cross_pen = QtGui.QPen(QtGui.QColor(CANVAS_PALETTE["crosshair"]), 1,
                               QtCore.Qt.PenStyle.DotLine)
        painter.setPen(cross_pen)
        painter.drawLine(QtCore.QPointF(self._hover_pos.x(), plot_rect.top()),
                         QtCore.QPointF(self._hover_pos.x(), plot_rect.bottom()))
        painter.drawLine(QtCore.QPointF(plot_rect.left(), self._hover_pos.y()),
                         QtCore.QPointF(plot_rect.right(), self._hover_pos.y()))
        painter.setFont(self._TRACER_FONT)
        label = f"({hx:.3f}, {hy:.3f})"
        lx = min(self._hover_pos.x() + 14, plot_rect.right() - 100)
        ly = max(self._hover_pos.y() - 22, plot_rect.top() + 16)
        painter.setPen(QtGui.QColor(CANVAS_PALETTE["text_mid"]))
        painter.drawText(QtCore.QRectF(lx, ly, 120, 16),
                         QtCore.Qt.AlignmentFlag.AlignLeft, label)


def _nice_step(range_val: float, target_divisions: int) -> float:
    """Compute a 'nice' grid step size."""
    if abs(range_val) < 1e-12:
        return 1.0  # degenerate range — return safe default
    raw = range_val / target_divisions
    if abs(raw) < 1e-12:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(abs(raw)))
    normalized = raw / magnitude
    if normalized < 1.5:
        nice = 1.0
    elif normalized < 3.5:
        nice = 2.0
    elif normalized < 7.5:
        nice = 5.0
    else:
        nice = 10.0
    return nice * magnitude
