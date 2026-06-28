"""Composable PyQt6 widgets for the redesigned dashboard shell."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from aetherlab.core.models import RagResult, SceneBundle, SolverResult
from aetherlab.ui.live_canvas import LiveCanvas, build_canvas_state
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt

require_qt()


# ────────────────────────────────────────────────────────────────────────────
# Blueprint Loading Overlay
# ────────────────────────────────────────────────────────────────────────────


class BlueprintLoadingOverlay(QtWidgets.QWidget):
    """Animated loading overlay with concentric rings and tracer dots."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BlueprintOverlay")
        self._angle = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)
        self.setMinimumSize(300, 200)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start(33)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        self._timer.stop()

    def _tick(self) -> None:
        self._angle += 2.5
        if self._angle >= 360.0:
            self._angle -= 360.0
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor("#0A0A0F"))

        cx, cy = rect.width() // 2, rect.height() // 2

        # Subtle grid
        grid_pen = QtGui.QPen(QtGui.QColor("#13131A"), 1)
        painter.setPen(grid_pen)
        for x in range(0, rect.width(), 48):
            painter.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), 48):
            painter.drawLine(0, y, rect.width(), y)

        # Crosshair axes
        accent_pen = QtGui.QPen(QtGui.QColor("#164E63"), 1)
        accent_pen.setStyle(QtCore.Qt.PenStyle.DotLine)
        painter.setPen(accent_pen)
        painter.drawLine(cx, 0, cx, rect.height())
        painter.drawLine(0, cy, rect.width(), cy)

        # Concentric rings
        for i, radius in enumerate([40, 80, 120, 160, 200]):
            opacity = max(0.08, 0.25 - i * 0.04)
            color = QtGui.QColor("#06B6D4")
            color.setAlphaF(opacity)
            painter.setPen(QtGui.QPen(color, 1))
            painter.drawEllipse(QtCore.QPoint(cx, cy), radius, radius)

        # Primary rotating arc
        arc_pen = QtGui.QPen(QtGui.QColor("#06B6D4"), 3)
        arc_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(cx - 35, cy - 35, 70, 70, int(self._angle * 16), 100 * 16)

        # Counter-rotating secondary arc
        arc_pen2 = QtGui.QPen(QtGui.QColor("#10B981"), 2)
        arc_pen2.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen2)
        painter.drawArc(cx - 55, cy - 55, 110, 110, int(-self._angle * 16), 80 * 16)

        # Orbiting dots
        for radius, speed, color_hex, dot_r in [
            (80, 1.0, "#06B6D4", 4),
            (120, -0.7, "#10B981", 3),
            (160, 0.5, "#8B5CF6", 3),
        ]:
            angle_rad = math.radians(self._angle * speed)
            ox = cx + radius * math.cos(angle_rad)
            oy = cy + radius * math.sin(angle_rad)
            painter.setBrush(QtGui.QColor(color_hex))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawEllipse(QtCore.QPoint(int(ox), int(oy)), dot_r, dot_r)

        # Center dot with glow
        glow = QtGui.QRadialGradient(float(cx), float(cy), 16)
        glow.setColorAt(0, QtGui.QColor("#06B6D440"))
        glow.setColorAt(1, QtGui.QColor("#00000000"))
        painter.fillRect(cx - 16, cy - 16, 32, 32, glow)
        painter.setBrush(QtGui.QColor("#06B6D4"))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(QtCore.QPoint(cx, cy), 5, 5)


# ────────────────────────────────────────────────────────────────────────────
# Sidebar Navigation
# ────────────────────────────────────────────────────────────────────────────


class SidebarNav(QtWidgets.QWidget):
    """Vertical sidebar navigation with icon+label buttons."""

    item_selected = QtCore.pyqtSignal(int)

    _ITEMS = [
        ("\U0001f4d0", "Solve", "Analytical derivation"),
        ("\U0001f4da", "Refs", "Textbook references"),
        ("\U0001f3ac", "Scene", "Visual sandbox"),
        ("\u2699\ufe0f", "Params", "Parameter control"),
        ("\U0001f4dc", "History", "Past pipeline runs"),
    ]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(160)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        # Logo
        logo = QtWidgets.QLabel("AetherLab")
        logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            "color: #06B6D4; font-size: 16pt; font-weight: 800; "
            "letter-spacing: -0.5px; padding: 12px 0 16px 0;"
        )
        layout.addWidget(logo)

        # Separator
        sep = QtWidgets.QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1E293B;")
        layout.addWidget(sep)

        layout.addSpacing(8)

        # Nav buttons
        self._buttons: list[QtWidgets.QPushButton] = []
        for idx, (icon, label, _tooltip) in enumerate(self._ITEMS):
            btn = QtWidgets.QPushButton(f"  {icon}  {label}")
            btn.setObjectName("SidebarItem")
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(_tooltip)
            btn.clicked.connect(lambda checked, i=idx: self._on_click(i))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Select first by default
        if self._buttons:
            self._buttons[0].setChecked(True)

    def _on_click(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
        self.item_selected.emit(index)

    def select(self, index: int) -> None:
        self._on_click(index)


# ────────────────────────────────────────────────────────────────────────────
# Pipeline Stepper
# ────────────────────────────────────────────────────────────────────────────


class PipelineStepper(QtWidgets.QWidget):
    """Horizontal 4-stage pipeline progress indicator."""

    STAGES = ["Solve", "RAG", "Scene", "Render"]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PipelineStepper")
        self.setFixedHeight(64)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(0)

        self._stage_labels: list[QtWidgets.QLabel] = []
        self._stage_dots: list[QtWidgets.QLabel] = []

        for i, name in enumerate(self.STAGES):
            # Dot + label column
            col = QtWidgets.QWidget()
            col_layout = QtWidgets.QVBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(4)
            col_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            dot = QtWidgets.QLabel("\u25cf")
            dot.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            dot.setObjectName("StepPending")
            dot.setStyleSheet("font-size: 16px;")
            self._stage_dots.append(dot)

            label = QtWidgets.QLabel(name)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setObjectName("StepPending")
            label.setStyleSheet("font-size: 11px; font-weight: 600;")
            self._stage_labels.append(label)

            col_layout.addWidget(dot)
            col_layout.addWidget(label)

            layout.addWidget(col, 1)

            # Connector line (except last)
            if i < len(self.STAGES) - 1:
                connector = QtWidgets.QFrame()
                connector.setFixedHeight(2)
                connector.setStyleSheet("background-color: #1E293B; border-radius: 1px;")
                layout.addWidget(connector, 2)

        self._current_stage = -1

    def set_stage(self, stage: int, status: str = "active") -> None:
        """Update pipeline stage. status: 'active', 'complete', 'error'."""
        self._current_stage = stage
        for i in range(len(self.STAGES)):
            if i < stage:
                self._stage_dots[i].setObjectName("StepComplete")
                self._stage_labels[i].setObjectName("StepComplete")
            elif i == stage:
                obj_name = "StepError" if status == "error" else "StepActive"
                self._stage_dots[i].setObjectName(obj_name)
                self._stage_labels[i].setObjectName(obj_name)
            else:
                self._stage_dots[i].setObjectName("StepPending")
                self._stage_labels[i].setObjectName("StepPending")

            # Force style refresh
            self._stage_dots[i].style().unpolish(self._stage_dots[i])
            self._stage_dots[i].style().polish(self._stage_dots[i])
            self._stage_labels[i].style().unpolish(self._stage_labels[i])
            self._stage_labels[i].style().polish(self._stage_labels[i])

    def reset(self) -> None:
        self.set_stage(-1)


# ────────────────────────────────────────────────────────────────────────────
# History Panel
# ────────────────────────────────────────────────────────────────────────────


class HistoryPanel(QtWidgets.QWidget):
    """Chronological list of past pipeline runs, clickable to re-run."""

    prompt_selected = QtCore.pyqtSignal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("\U0001f4dc Pipeline History")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("HistoryList")
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list, 1)

        # Bottom bar with clear button
        bottom = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self._count_label = QtWidgets.QLabel("0 entries")
        self._count_label.setStyleSheet("color: #64748B; font-size: 11px;")
        bottom_layout.addWidget(self._count_label)
        bottom_layout.addStretch()

        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.setFixedWidth(80)
        clear_btn.setStyleSheet(
            "background: transparent; border: 1px solid #334155; "
            "border-radius: 6px; color: #64748B; padding: 4px 12px; font-size: 11px;"
        )
        clear_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear)
        bottom_layout.addWidget(clear_btn)
        layout.addWidget(bottom)

        self._entries: list[str] = []

    def add_entry(self, prompt: str, cache_key: str, scene_status: str, num_refs: int) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        status_icon = "\u2705" if scene_status in ("rendered", "compiled") else "\u26a0\ufe0f"
        text = f"{status_icon}  {ts}  [{cache_key}]  {prompt[:80]}"
        item = QtWidgets.QListWidgetItem(text)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, prompt)
        item.setToolTip(prompt)
        self._list.insertItem(0, item)
        self._entries.insert(0, prompt)
        self._count_label.setText(f"{self._list.count()} entries")

    def _on_double_click(self, item: QtWidgets.QListWidgetItem) -> None:
        prompt = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if prompt:
            self.prompt_selected.emit(str(prompt))

    def _clear(self) -> None:
        self._list.clear()
        self._entries.clear()
        self._count_label.setText("0 entries")


# ────────────────────────────────────────────────────────────────────────────
# Example Prompts
# ────────────────────────────────────────────────────────────────────────────

EXAMPLE_PROMPTS = [
    "Derive the damped harmonic oscillator and visualize phase space.",
    "Solve the simple pendulum for large angles using energy methods.",
    "Show the Kepler orbit for an inverse-square central force.",
    "Derive the heat equation on a rod with fixed boundary conditions.",
    "Prove that e is irrational using a contradiction argument.",
    "Solve the two-body problem and plot the relative trajectory.",
    "Derive the Euler-Lagrange equations for a double pendulum.",
    "Show the Fourier series convergence for a square wave.",
    "Solve the RLC circuit ODE and plot current vs time.",
    "Derive the Navier-Stokes equations for incompressible flow.",
]


# ────────────────────────────────────────────────────────────────────────────
# Command Bar
# ────────────────────────────────────────────────────────────────────────────


class CommandBar(QtWidgets.QWidget):
    """Single-line command input with example prompts, quality selector, and run button."""

    submitted = QtCore.pyqtSignal(str)

    _QUALITIES = {"480p": "l", "720p": "m", "1080p": "h"}

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # Example prompts dropdown
        self._examples = QtWidgets.QComboBox()
        self._examples.setObjectName("ExamplesCombo")
        self._examples.addItem("\U0001f4cb Examples\u2026")
        for p in EXAMPLE_PROMPTS:
            label = p[:48] + "\u2026" if len(p) > 48 else p
            self._examples.addItem(label)
        self._examples.setFixedWidth(180)
        self._examples.setStyleSheet(
            "QComboBox#ExamplesCombo {"
            "  background-color: #13131A; border: 1px solid #334155;"
            "  border-radius: 8px; color: #94A3B8; padding: 8px 12px;"
            "  font-size: 12px;"
            "}"
            "QComboBox#ExamplesCombo:hover { border-color: #06B6D4; color: #CBD5E1; }"
            "QComboBox#ExamplesCombo::drop-down { border: none; }"
            "QComboBox#ExamplesCombo QAbstractItemView {"
            "  background-color: #13131A; border: 1px solid #334155;"
            "  color: #CBD5E1; selection-background-color: #164E63;"
            "}"
        )
        self._examples.activated.connect(self._on_example_selected)
        layout.addWidget(self._examples)

        # Input field
        self.input = QtWidgets.QLineEdit()
        self.input.setObjectName("CommandBar")
        self.input.setPlaceholderText(
            "\u2318  Enter a physics problem, derivation, or simulation request\u2026"
        )
        self.input.returnPressed.connect(self._submit)
        layout.addWidget(self.input, 1)

        # Render quality selector
        self._quality = QtWidgets.QComboBox()
        self._quality.setObjectName("QualityCombo")
        self._quality.addItems(list(self._QUALITIES.keys()))
        self._quality.setCurrentIndex(0)
        self._quality.setFixedWidth(72)
        self._quality.setToolTip("Render quality")
        self._quality.setStyleSheet(
            "QComboBox#QualityCombo {"
            "  background-color: #13131A; border: 1px solid #334155;"
            "  border-radius: 8px; color: #94A3B8; padding: 8px 8px;"
            "  font-size: 12px; font-weight: 600;"
            "}"
            "QComboBox#QualityCombo:hover { border-color: #06B6D4; color: #CBD5E1; }"
            "QComboBox#QualityCombo::drop-down { border: none; }"
            "QComboBox#QualityCombo QAbstractItemView {"
            "  background-color: #13131A; border: 1px solid #334155;"
            "  color: #CBD5E1; selection-background-color: #164E63;"
            "}"
        )
        layout.addWidget(self._quality)

        # Run button
        self.run_button = QtWidgets.QPushButton("\u25b6  Run")
        self.run_button.setObjectName("RunButton")
        self.run_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.run_button.clicked.connect(self._submit)
        layout.addWidget(self.run_button)

    def get_render_quality(self) -> str:
        """Return the Manim quality flag (l/m/h) for the selected quality."""
        label = self._quality.currentText()
        return self._QUALITIES.get(label, "l")

    def set_busy(self, busy: bool) -> None:
        self.run_button.setDisabled(busy)
        self.run_button.setText("\u23f3  Running\u2026" if busy else "\u25b6  Run")
        self.input.setDisabled(busy)

    def _on_example_selected(self, index: int) -> None:
        if index > 0:
            self.input.setText(EXAMPLE_PROMPTS[index - 1])
            self.input.setFocus()
        self._examples.blockSignals(True)
        self._examples.setCurrentIndex(0)
        self._examples.blockSignals(False)

    def _submit(self) -> None:
        prompt = self.input.text().strip()
        if prompt and self.run_button.isEnabled():
            self.submitted.emit(prompt)
            self.input.clear()


# ────────────────────────────────────────────────────────────────────────────
# Parameter Dock
# ────────────────────────────────────────────────────────────────────────────


class ParameterDock(QtWidgets.QWidget):
    """Collapsible horizontal strip of parameter sliders with live values."""

    parameter_changed = QtCore.pyqtSignal(str, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._sliders: dict[str, tuple[QtWidgets.QSlider, QtWidgets.QLabel]] = {}
        self._spans: dict[str, float] = {}
        self._collapsed = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(4)

        # Header with collapse toggle
        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._toggle_btn = QtWidgets.QPushButton("\u25bc  Parameters")
        self._toggle_btn.setStyleSheet(
            "background: transparent; border: none; color: #64748B; "
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
            "letter-spacing: 1px; padding: 4px 0;"
        )
        self._toggle_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self._toggle_btn)
        header_layout.addStretch()
        layout.addWidget(header)

        # Sliders container
        self._container = QtWidgets.QWidget()
        self._container_layout = QtWidgets.QFormLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(8)
        layout.addWidget(self._container)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._container.setVisible(not self._collapsed)
        self._toggle_btn.setText(
            "\u25b6  Parameters" if self._collapsed else "\u25bc  Parameters"
        )

    def expand(self) -> None:
        """Ensure the parameter strip is expanded (used by sidebar nav)."""
        if self._collapsed:
            self._toggle()

    _SLIDER_TICKS = 1000

    def _span_for(self, value: float) -> float:
        """Slider spans 0..span where span scales to the variable's magnitude,
        so large values (e.g. gravity 9.81) remain reachable and the initial
        handle sits at the midpoint."""
        return max(abs(float(value)) * 2.0, 1.0)

    def set_variables(self, variables: dict[str, float]) -> None:
        self._clear()
        for name, value in sorted(variables.items()):
            value = float(value)
            span = self._span_for(value)
            self._spans[name] = span
            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(0, self._SLIDER_TICKS)
            slider.setValue(self._value_to_tick(value, span))
            slider.valueChanged.connect(
                lambda raw, key=name: self._on_change(key, raw / self._SLIDER_TICKS * self._spans[key])
            )

            value_label = QtWidgets.QLabel(f"{value:g}")
            value_label.setMinimumWidth(48)
            value_label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            value_label.setStyleSheet(
                "color: #06B6D4; font-family: 'Cascadia Code', monospace; "
                "font-size: 12px; font-weight: 600;"
            )

            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            row_layout.addWidget(slider, 1)
            row_layout.addWidget(value_label)

            self._sliders[name] = (slider, value_label)
            self._container_layout.addRow(name, row_widget)

    def _value_to_tick(self, value: float, span: float) -> int:
        if span <= 0:
            return 0
        return max(0, min(self._SLIDER_TICKS, int(value / span * self._SLIDER_TICKS)))

    def update_variable(self, name: str, value: float) -> None:
        if name in self._sliders:
            slider, label = self._sliders[name]
            span = self._spans.get(name, self._span_for(value))
            # Grow the span if an external update exceeds the current range.
            if value > span:
                span = self._span_for(value)
                self._spans[name] = span
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(value, span))
            slider.blockSignals(False)
            label.setText(f"{value:g}")

    def _on_change(self, name: str, value: float) -> None:
        if name in self._sliders:
            _, label = self._sliders[name]
            label.setText(f"{value:g}")
        self.parameter_changed.emit(name, value)

    def _clear(self) -> None:
        while self._container_layout.rowCount():
            self._container_layout.removeRow(0)
        self._sliders.clear()
        self._spans.clear()


# ────────────────────────────────────────────────────────────────────────────
# Analysis Panel
# ────────────────────────────────────────────────────────────────────────────


class AnalysisPanel(QtWidgets.QWidget):
    token_selected = QtCore.pyqtSignal(str, float)

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("\U0001f4d0 Analytical Core")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Summary card
        self._summary_frame = QtWidgets.QFrame()
        self._summary_frame.setObjectName("CardFrame")
        summary_layout = QtWidgets.QVBoxLayout(self._summary_frame)
        summary_layout.setContentsMargins(14, 10, 14, 10)
        summary_layout.setSpacing(6)
        summary_label = QtWidgets.QLabel("Derivation")
        summary_label.setObjectName("SectionTitle")
        summary_layout.addWidget(summary_label)
        self.summary = QtWidgets.QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMinimumHeight(60)
        summary_layout.addWidget(self.summary)

        # Steps card
        self._steps_frame = QtWidgets.QFrame()
        self._steps_frame.setObjectName("CardFrame")
        steps_layout = QtWidgets.QVBoxLayout(self._steps_frame)
        steps_layout.setContentsMargins(14, 10, 14, 10)
        steps_layout.setSpacing(6)
        steps_label = QtWidgets.QLabel("Steps")
        steps_label.setObjectName("SectionTitle")
        steps_layout.addWidget(steps_label)
        self.steps = QtWidgets.QListWidget()
        self.steps.setMinimumHeight(100)
        steps_layout.addWidget(self.steps)

        layout.addWidget(self._summary_frame, 2)
        layout.addWidget(self._steps_frame, 3)

    def set_solver_result(self, solver: SolverResult) -> None:
        cache_note = " [cache]" if solver.cached else ""
        self.summary.setPlainText(f"{solver.summary}{cache_note}")
        self.steps.clear()
        for index, step in enumerate(solver.derivation_steps, start=1):
            self.steps.addItem(f"{index}. {step}")

    def update_variable(self, name: str, value: float) -> None:
        pass  # Parameters now live in ParameterDock


# ────────────────────────────────────────────────────────────────────────────
# Reference Panel
# ────────────────────────────────────────────────────────────────────────────


class ReferencePanel(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("\U0001f4da Textbook Viewport")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self._ref_frame = QtWidgets.QFrame()
        self._ref_frame.setObjectName("CardFrame")
        ref_layout = QtWidgets.QVBoxLayout(self._ref_frame)
        ref_layout.setContentsMargins(14, 10, 14, 10)
        ref_layout.setSpacing(6)
        self.references = QtWidgets.QPlainTextEdit()
        self.references.setReadOnly(True)
        ref_layout.addWidget(self.references)

        layout.addWidget(self._ref_frame, 1)

    def set_rag_result(self, rag: RagResult) -> None:
        if not rag.hits:
            self.references.setPlainText(
                f"No local references found via {rag.backend}. "
                "Add PDFs or text files to the library directory."
            )
            return
        lines: list[str] = [f"Backend: {rag.backend}", ""]
        for hit in rag.hits:
            page = f", page {hit.page_number}" if hit.page_number else ""
            lines.append(f"{hit.source_name}{page} | score {hit.score:g}")
            lines.append(hit.excerpt)
            lines.append("")
        self.references.setPlainText("\n".join(lines).strip())


# ────────────────────────────────────────────────────────────────────────────
# Simulation Panel (Visual Sandbox)
# ────────────────────────────────────────────────────────────────────────────


class SimulationPanel(QtWidgets.QWidget):
    parameter_changed = QtCore.pyqtSignal(str, float)
    phase_toggled = QtCore.pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Error banner (hidden by default) ──
        self._error_banner = QtWidgets.QFrame()
        self._error_banner.setObjectName("ErrorBanner")
        self._error_banner.setStyleSheet(
            "QFrame#ErrorBanner {"
            "  background-color: #1C0A0A; border-bottom: 2px solid #F43F5E;"
            "  padding: 0;"
            "}"
        )
        err_layout = QtWidgets.QHBoxLayout(self._error_banner)
        err_layout.setContentsMargins(16, 8, 16, 8)
        err_layout.setSpacing(12)

        self._error_icon = QtWidgets.QLabel("\u26a0\ufe0f")
        self._error_icon.setStyleSheet("font-size: 14px; color: #F43F5E;")
        err_layout.addWidget(self._error_icon)

        self._error_text = QtWidgets.QLabel("")
        self._error_text.setStyleSheet("color: #FDA4AF; font-size: 12px;")
        self._error_text.setWordWrap(True)
        err_layout.addWidget(self._error_text, 1)

        self._error_detail_btn = QtWidgets.QPushButton("Details")
        self._error_detail_btn.setFixedWidth(72)
        self._error_detail_btn.setStyleSheet(
            "background: transparent; border: 1px solid #F43F5E; border-radius: 6px;"
            " color: #FDA4AF; font-size: 11px; padding: 4px 8px;"
        )
        self._error_detail_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._error_detail_btn.clicked.connect(self._show_error_details)
        err_layout.addWidget(self._error_detail_btn)

        dismiss_btn = QtWidgets.QPushButton("\u2715")
        dismiss_btn.setFixedWidth(28)
        dismiss_btn.setStyleSheet(
            "background: transparent; border: none; color: #64748B; font-size: 14px;"
        )
        dismiss_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        dismiss_btn.clicked.connect(self._error_banner.hide)
        err_layout.addWidget(dismiss_btn)

        self._error_banner.hide()
        self._error_traceback = ""
        layout.addWidget(self._error_banner)

        # Top bar with pill tabs for view switching + phase portrait toggle
        top_bar = QtWidgets.QWidget()
        top_bar.setFixedHeight(48)
        top_bar.setStyleSheet("background-color: #0D0D14; border-bottom: 1px solid #1E293B;")
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 6, 16, 6)
        top_layout.setSpacing(8)

        self.status = QtWidgets.QLabel("Waiting for pipeline\u2026")
        self.status.setObjectName("StatusIdle")
        self.status.setStyleSheet("font-size: 12px;")
        top_layout.addWidget(self.status, 1)

        # Phase portrait toggle checkbox
        self._phase_check = QtWidgets.QCheckBox("Phase")
        self._phase_check.setStyleSheet(
            "QCheckBox { color: #94A3B8; font-size: 11px; font-weight: 600; spacing: 6px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px;"
            "  border: 1px solid #334155; background: #13131A; }"
            "QCheckBox::indicator:checked { background: #06B6D4; border-color: #06B6D4; }"
        )
        self._phase_check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._phase_check.setToolTip("Toggle phase portrait overlay")
        self._phase_check.toggled.connect(self.phase_toggled.emit)
        top_layout.addWidget(self._phase_check)

        # View pill tabs
        self._pill_group = QtWidgets.QButtonGroup(self)
        self._pill_group.setExclusive(True)
        for i, label in enumerate(["Canvas", "Video", "Code"]):
            pill = QtWidgets.QPushButton(label)
            pill.setObjectName("PillTab")
            pill.setCheckable(True)
            pill.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self._pill_group.addButton(pill, i)
            pill.clicked.connect(lambda checked, idx=i: self._switch_view(idx))
            top_layout.addWidget(pill)

        layout.addWidget(top_bar)

        # Stacked widget: loading + live canvas + video + code
        self._stack = QtWidgets.QStackedWidget()

        # Index 0: loading overlay
        self._loading = BlueprintLoadingOverlay()

        # Index 1: live interactive canvas
        self._live_canvas = LiveCanvas()

        # Index 2: video player
        self._video_frame = self._build_video_player()

        # Index 3: code viewer
        self._code_frame = QtWidgets.QFrame()
        self._code_frame.setObjectName("CardFrame")
        code_layout = QtWidgets.QVBoxLayout(self._code_frame)
        code_layout.setContentsMargins(14, 10, 14, 10)
        self.code = QtWidgets.QPlainTextEdit()
        self.code.setReadOnly(True)
        code_layout.addWidget(self.code)

        self._stack.addWidget(self._loading)
        self._stack.addWidget(self._live_canvas)
        self._stack.addWidget(self._video_frame)
        self._stack.addWidget(self._code_frame)
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, 1)

        self._solver: SolverResult | None = None

        # Set first pill checked
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)

    def _switch_view(self, index: int) -> None:
        # Map pill index to stack index: 0->Canvas(1), 1->Video(2), 2->Code(3)
        stack_map = {0: 1, 1: 2, 2: 3}
        target = stack_map.get(index, 1)
        if self._stack.count() > target:
            self._stack.setCurrentIndex(target)

    def _build_video_player(self) -> QtWidgets.QWidget:
        from PyQt6.QtMultimedia import QMediaPlayer
        from PyQt6.QtMultimediaWidgets import QVideoWidget

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(12, 8, 12, 8)
        container_layout.setSpacing(8)

        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumSize(400, 225)
        self._video_widget.setStyleSheet(
            "background-color: #0A0A0F; border-radius: 8px;"
        )
        container_layout.addWidget(self._video_widget, 1)

        # Controls
        controls = QtWidgets.QWidget()
        controls.setMaximumHeight(44)
        controls_layout = QtWidgets.QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.setSpacing(8)

        self._play_btn = QtWidgets.QPushButton("\u25b6")
        self._play_btn.setFixedWidth(36)
        self._play_btn.setObjectName("VideoControlBtn")

        self._pause_btn = QtWidgets.QPushButton("\u23f8")
        self._pause_btn.setFixedWidth(36)
        self._pause_btn.setObjectName("VideoControlBtn")

        self._stop_btn = QtWidgets.QPushButton("\u23f9")
        self._stop_btn.setFixedWidth(36)
        self._stop_btn.setObjectName("VideoControlBtn")

        self._seek_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setToolTip("Seek")
        self._seek_slider.setObjectName("VideoSeekSlider")
        self._seeking = False

        self._time_label = QtWidgets.QLabel("0:00 / 0:00")
        self._time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._time_label.setObjectName("VideoTimeLabel")
        self._time_label.setMinimumWidth(100)

        self._speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._speed_slider.setRange(25, 200)
        self._speed_slider.setValue(100)
        self._speed_slider.setToolTip("Playback speed")
        self._speed_slider.setFixedWidth(80)
        speed_label = QtWidgets.QLabel("1.0x")
        speed_label.setStyleSheet(
            "color: #64748B; font-size: 11px; font-weight: 600;"
        )

        controls_layout.addWidget(self._play_btn)
        controls_layout.addWidget(self._pause_btn)
        controls_layout.addWidget(self._stop_btn)
        controls_layout.addWidget(self._seek_slider, 1)
        controls_layout.addWidget(self._time_label)
        controls_layout.addWidget(self._speed_slider)
        controls_layout.addWidget(speed_label)

        container_layout.addWidget(controls)

        self._player = QMediaPlayer()
        self._player.setVideoOutput(self._video_widget)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.positionChanged.connect(self._on_position_changed)

        # Seek slider: track drags, seek on release, ignore feedback while dragging.
        self._seek_slider.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self._seek_slider.sliderReleased.connect(self._on_seek_released)

        self._play_btn.clicked.connect(self._player.play)
        self._pause_btn.clicked.connect(self._player.pause)
        self._stop_btn.clicked.connect(self._player.stop)
        self._speed_slider.valueChanged.connect(
            lambda v: (
                self._player.setPlaybackRate(v / 100.0),
                speed_label.setText(f"{v / 100:.1f}x"),
            )
        )

        return container

    def _on_duration_changed(self, duration: int) -> None:
        self._seek_slider.setRange(0, max(duration, 0))
        total = duration // 1000
        self._time_label.setText(f"0:00 / {total // 60}:{total % 60:02d}")

    def _on_position_changed(self, position: int) -> None:
        if not self._seeking:
            self._seek_slider.blockSignals(True)
            self._seek_slider.setValue(position)
            self._seek_slider.blockSignals(False)
        duration = self._player.duration()
        if duration > 0:
            current = position // 1000
            total = duration // 1000
            self._time_label.setText(
                f"{current // 60}:{current % 60:02d} / {total // 60}:{total % 60:02d}"
            )

    def _on_seek_released(self) -> None:
        self._player.setPosition(self._seek_slider.value())
        self._seeking = False

    def set_solver(self, solver: SolverResult) -> None:
        self._solver = solver
        self._rebuild_canvas()

    def _rebuild_canvas(self) -> None:
        if not self._solver:
            return
        # Preserve any live slider adjustments instead of resetting to defaults.
        params = dict(self._solver.variables)
        current = getattr(self._live_canvas, "_state", None)
        if current and current.params:
            params.update(current.params)
        state = build_canvas_state(
            title=self._solver.summary[:60] if self._solver.summary else "Simulation",
            params=params,
            phase_portrait=self._phase_check.isChecked(),
        )
        self._live_canvas.set_state(state)

    def toggle_phase(self, enabled: bool) -> None:
        """Rebuild the canvas with/without the phase-portrait overlay curve."""
        self._rebuild_canvas()
        self.status.setText(
            "Phase portrait overlay on" if enabled else "Phase portrait overlay off"
        )

    def show_loading(self) -> None:
        self._stack.setCurrentIndex(0)
        self.status.setText("Computing analytical pipeline\u2026")
        self.status.setObjectName("StatusWorking")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def hide_loading(self) -> None:
        self._stack.setCurrentIndex(1)
        self.status.setText("Live canvas active \u2014 rendering video\u2026")
        self.status.setObjectName("StatusWorking")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        # Select Canvas pill
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)

    def show_code(self) -> None:
        self._stack.setCurrentIndex(3)
        pills = self._pill_group.buttons()
        if len(pills) > 2:
            pills[2].setChecked(True)

    def show_canvas(self) -> None:
        self._stack.setCurrentIndex(1)
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)

    def set_scene_bundle(self, scene: SceneBundle) -> None:
        self._stack.setCurrentIndex(1)
        self.status.setText(f"Engine: {scene.engine} | Status: {scene.status}")
        if scene.status == "compiled":
            self.status.setObjectName("StatusReady")
        else:
            self.status.setObjectName("StatusError")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        diagnostics = "\n".join(scene.diagnostics)
        self.code.setPlainText(
            scene.code if not diagnostics else f"{scene.code}\n# Diagnostics:\n# {diagnostics}"
        )
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)

    def set_video(self, scene: SceneBundle) -> None:
        from PyQt6.QtCore import QUrl

        if scene.video_path and Path(scene.video_path).exists():
            self._stack.setCurrentIndex(2)
            self._player.setSource(QUrl.fromLocalFile(scene.video_path))
            self._player.play()
            self.status.setText(f"\U0001f3ac Playing: {Path(scene.video_path).name}")
            self.status.setObjectName("StatusReady")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            pills = self._pill_group.buttons()
            if len(pills) > 1:
                pills[1].setChecked(True)
        else:
            self.show_code()
            if scene.video_path:
                self.status.setText(f"Video path set but file missing: {scene.video_path}")
            else:
                self.status.setText(f"Video not rendered. Status: {scene.status}")
            self.status.setObjectName("StatusError")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            if scene.diagnostics:
                self.code.setPlainText(
                    scene.code + "\n\n# Diagnostics:\n# " + "\n# ".join(scene.diagnostics)
                )

    def apply_parameter_update(self, name: str, value: float) -> None:
        self.status.setText(f"Parameter: {name} = {value:g}")
        self._live_canvas.update_params({name: value})
        self.parameter_changed.emit(name, value)

    def show_error_banner(self, stage: str, message: str, traceback: str = "") -> None:
        """Show an inline error banner instead of a modal popup."""
        self._error_text.setText(f"{stage} failed: {message}")
        self._error_traceback = traceback or message
        self._error_banner.show()

    def clear_error_banner(self) -> None:
        """Dismiss the error banner."""
        self._error_banner.hide()
        self._error_traceback = ""

    def _show_error_details(self) -> None:
        """Open the full traceback in a non-modal window."""
        if not self._error_traceback:
            return
        detail = QtWidgets.QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(self._error_traceback)
        detail.setWindowTitle("Pipeline Traceback")
        detail.resize(900, 500)
        detail.show()
        detail.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
