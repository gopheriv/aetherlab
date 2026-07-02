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

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802 (#13)
        """Arrow key navigation between sidebar items."""
        current = -1
        for i, btn in enumerate(self._buttons):
            if btn.isChecked():
                current = i
                break

        if event.key() in (QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Right):
            next_idx = min(current + 1, len(self._buttons) - 1)
            if next_idx != current:
                self._on_click(next_idx)
        elif event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Left):
            prev_idx = max(current - 1, 0)
            if prev_idx != current:
                self._on_click(prev_idx)
        else:
            super().keyPressEvent(event)


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
    """Chronological list of past pipeline runs, clickable to re-run.
    Persists entries to SQLite across restarts (#5)."""

    prompt_selected = QtCore.pyqtSignal(str)

    _HISTORY_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            scene_status TEXT NOT NULL,
            num_refs INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """

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
        self._db_path: Path | None = None

    def init_persistence(self, db_path: Path) -> None:
        """Set up SQLite persistence and load saved entries (#5)."""
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute(self._HISTORY_TABLE_SQL)
        conn.commit()
        # Load last 100 entries
        rows = conn.execute(
            "SELECT prompt, cache_key, scene_status, num_refs, created_at "
            "FROM history ORDER BY id DESC LIMIT 100"
        ).fetchall()
        conn.close()
        for prompt, cache_key, scene_status, num_refs, created_at in reversed(rows):
            self._add_entry_ui(prompt, cache_key, scene_status, num_refs, created_at)

    def add_entry(self, prompt: str, cache_key: str, scene_status: str, num_refs: int) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._add_entry_ui(prompt, cache_key, scene_status, num_refs, ts)
        # Persist to SQLite
        if self._db_path:
            import sqlite3
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(self._HISTORY_TABLE_SQL)
            conn.execute(
                "INSERT INTO history (prompt, cache_key, scene_status, num_refs, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (prompt, cache_key, scene_status, num_refs, datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()

    def _add_entry_ui(self, prompt: str, cache_key: str, scene_status: str,
                      num_refs: int, ts: str) -> None:
        # Normalize timestamp — strip date part if ISO format
        if "T" in ts:
            ts = ts.split("T")[1][:8]
        status_icon = "\u2705" if scene_status in ("rendered", "compiled") else "\u26a0\ufe0f"
        text = f"{status_icon}  {ts}  [{cache_key[:12]}]  {prompt[:80]}"
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
        if self._db_path:
            import sqlite3
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("DELETE FROM history")
            conn.commit()
            conn.close()


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
    """Single-line command input with example prompts, quality selector, run/cancel (#2)."""

    submitted = QtCore.pyqtSignal(str)
    cancel_requested = QtCore.pyqtSignal()

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

        # Cancel button (#2) — hidden by default
        self.cancel_button = QtWidgets.QPushButton("\u2715  Cancel")
        self.cancel_button.setObjectName("CancelButton")
        self.cancel_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setStyleSheet(
            "QPushButton#CancelButton { background-color: #7F1D1D; border: 1px solid #F43F5E; "
            "border-radius: 12px; color: #FCA5A5; padding: 14px 20px; font-weight: 600; font-size: 13px; }"
            "QPushButton#CancelButton:hover { background-color: #991B1B; border-color: #FB7185; }"
        )
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)

    def get_render_quality(self) -> str:
        """Return the Manim quality flag (l/m/h) for the selected quality."""
        label = self._quality.currentText()
        return self._QUALITIES.get(label, "l")

    def set_busy(self, busy: bool) -> None:
        self.run_button.setDisabled(busy)
        self.run_button.setText("\u23f3  Running\u2026" if busy else "\u25b6  Run")
        self.input.setDisabled(busy)
        self.cancel_button.setVisible(busy)
        # Restore cancel button state (may have been put in 'Cancelling' mode).
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("\u2715  Cancel")

    def set_cancelling(self) -> None:
        """Cancel requested: keep Run disabled until the worker actually finishes.

        Re-enabling Run immediately would mislead - the pipeline thread may
        still be finishing its current stage. The worker's finished signal
        calls set_busy(False), which restores everything.
        """
        self.cancel_button.setDisabled(True)
        self.cancel_button.setText("\u23f3  Cancelling\u2026")

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
    """Collapsible horizontal strip of parameter sliders with spin boxes and reset (#7, #8)."""

    parameter_changed = QtCore.pyqtSignal(str, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        # (slider, spinbox, value_label, original_value)
        self._sliders: dict[str, tuple[QtWidgets.QSlider, QtWidgets.QDoubleSpinBox, QtWidgets.QLabel, float]] = {}
        # Per-parameter (lo, hi) slider/spinbox range. lo is negative when the
        # original value is negative so e.g. charge=-1.0 is representable (#F62).
        self._ranges: dict[str, tuple[float, float]] = {}
        self._collapsed = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(4)

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
        if self._collapsed:
            self._toggle()

    _SLIDER_TICKS = 1000

    def _span_for(self, value: float) -> float:
        return max(abs(float(value)) * 2.0, 1.0)

    def _range_for(self, value: float) -> tuple[float, float]:
        """Slider/spinbox range: [0, span] for non-negative values, symmetric
        [-span, span] when the value is negative so it stays representable (#F62)."""
        span = self._span_for(value)
        return (-span if value < 0 else 0.0, span)

    def set_variables(self, variables: dict[str, float]) -> None:
        self._clear()
        for name, value in sorted(variables.items()):
            value = float(value)
            lo, hi = self._range_for(value)
            self._ranges[name] = (lo, hi)

            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(0, self._SLIDER_TICKS)
            slider.setValue(self._value_to_tick(value, lo, hi))
            slider.valueChanged.connect(
                lambda raw, key=name: self._on_slider_change(key, raw)
            )

            # Spin box for precise numeric input (#7)
            spinbox = QtWidgets.QDoubleSpinBox()
            spinbox.setRange(lo, hi)
            spinbox.setValue(value)
            spinbox.setDecimals(4)
            spinbox.setSingleStep((hi - lo) / 100)
            spinbox.setFixedWidth(90)
            spinbox.setStyleSheet(
                "QDoubleSpinBox { background-color: #0F0F17; border: 1px solid #1E293B; "
                "border-radius: 4px; color: #06B6D4; padding: 2px 4px; "
                "font-family: 'Cascadia Code', monospace; font-size: 11px; }"
                "QDoubleSpinBox:focus { border-color: #06B6D4; }"
            )
            spinbox.valueChanged.connect(
                lambda val, key=name: self._on_spinbox_change(key, val)
            )

            # Reset button (#8)
            reset_btn = QtWidgets.QPushButton("\u21ba")
            reset_btn.setFixedWidth(28)
            reset_btn.setToolTip(f"Reset {name} to {value:g}")
            reset_btn.setStyleSheet(
                "background: transparent; border: 1px solid #334155; border-radius: 4px; "
                "color: #64748B; font-size: 14px; padding: 2px;"
            )
            reset_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            reset_btn.clicked.connect(
                lambda checked, key=name, orig=value: self._reset_param(key, orig)
            )

            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(slider, 1)
            row_layout.addWidget(spinbox)
            row_layout.addWidget(reset_btn)

            self._sliders[name] = (slider, spinbox, QtWidgets.QLabel(), value)
            self._container_layout.addRow(name, row_widget)

    def _on_slider_change(self, name: str, raw: int) -> None:
        lo, hi = self._ranges.get(name, (0.0, 1.0))
        value = lo + raw / self._SLIDER_TICKS * (hi - lo)
        if name in self._sliders:
            _, spinbox, _, _ = self._sliders[name]
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
        self.parameter_changed.emit(name, value)

    def _grow_range(self, name: str, value: float) -> tuple[float, float]:
        """Expand the stored range so ``value`` fits; sync the spinbox limits."""
        lo, hi = self._ranges.get(name, self._range_for(value))
        if value > hi or value < lo:
            span = self._span_for(value)
            lo = min(lo, -span if value < 0 else lo)
            hi = max(hi, span)
            self._ranges[name] = (lo, hi)
            if name in self._sliders:
                self._sliders[name][1].setRange(lo, hi)
        return self._ranges.get(name, (lo, hi))

    def _on_spinbox_change(self, name: str, value: float) -> None:
        if name in self._sliders:
            slider, _, _, _ = self._sliders[name]
            lo, hi = self._grow_range(name, value)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(value, lo, hi))
            slider.blockSignals(False)
        self.parameter_changed.emit(name, value)

    def _reset_param(self, name: str, original_value: float) -> None:
        if name in self._sliders:
            slider, spinbox, _, _ = self._sliders[name]
            lo, hi = self._ranges.get(name, self._range_for(original_value))
            spinbox.blockSignals(True)
            spinbox.setValue(original_value)
            spinbox.blockSignals(False)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(original_value, lo, hi))
            slider.blockSignals(False)
            self.parameter_changed.emit(name, original_value)

    def _value_to_tick(self, value: float, lo: float, hi: float) -> int:
        if hi <= lo:
            return 0
        tick = int((value - lo) / (hi - lo) * self._SLIDER_TICKS)
        return max(0, min(self._SLIDER_TICKS, tick))

    def update_variable(self, name: str, value: float) -> None:
        if name in self._sliders:
            slider, spinbox, _, _ = self._sliders[name]
            lo, hi = self._grow_range(name, value)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(value, lo, hi))
            slider.blockSignals(False)
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)

    def _clear(self) -> None:
        while self._container_layout.rowCount():
            self._container_layout.removeRow(0)
        self._sliders.clear()
        self._ranges.clear()


# ────────────────────────────────────────────────────────────────────────────
# Collapsible Step Widget (#9)
# ────────────────────────────────────────────────────────────────────────────


class _CollapsibleStepWidget(QtWidgets.QWidget):
    """Single collapsible derivation step with expand/collapse toggle."""

    def __init__(self, index: int, text: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(6, 4, 6, 4)
        header_layout.setSpacing(8)

        self._arrow = QtWidgets.QLabel("\u25b6")
        self._arrow.setFixedWidth(14)
        self._arrow.setStyleSheet("color: #475569; font-size: 10px;")
        header_layout.addWidget(self._arrow)

        step_num = QtWidgets.QLabel(f"Step {index}")
        step_num.setStyleSheet(
            "color: #06B6D4; font-size: 11px; font-weight: 700; "
            "font-family: 'Cascadia Code', monospace;"
        )
        header_layout.addWidget(step_num)

        preview = text[:60] + "\u2026" if len(text) > 60 else text
        preview_label = QtWidgets.QLabel(preview)
        preview_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        header_layout.addWidget(preview_label, 1)

        copy_btn = QtWidgets.QPushButton("\U0001f4cb")
        copy_btn.setFixedWidth(28)
        copy_btn.setToolTip("Copy step")
        copy_btn.setStyleSheet(
            "background: transparent; border: none; font-size: 12px; padding: 2px;"
        )
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: _copy_to_clipboard(text))
        header_layout.addWidget(copy_btn)

        self._body = QtWidgets.QLabel(text)
        self._body.setWordWrap(True)
        self._body.setStyleSheet(
            "color: #E2E8F0; font-size: 12px; padding: 8px 8px 8px 28px; "
            "background-color: #0F0F17; border-radius: 6px; margin-top: 4px;"
        )
        self._body.hide()

        self._expanded = False
        self._full_text = text

        header.mousePressEvent = lambda e: self._toggle()  # type: ignore[assignment]
        layout.addWidget(header)
        layout.addWidget(self._body)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._arrow.setText("\u25bc" if self._expanded else "\u25b6")
        self._arrow.setStyleSheet(
            f"color: {'#06B6D4' if self._expanded else '#475569'}; font-size: 10px;"
        )


def _copy_to_clipboard(text: str) -> None:
    clipboard = QtWidgets.QApplication.clipboard()
    if clipboard:
        clipboard.setText(text)


# ────────────────────────────────────────────────────────────────────────────
# Analysis Panel (#3 copy, #4 no dead signal, #9 collapsible steps, #12 empty)
# ────────────────────────────────────────────────────────────────────────────


class AnalysisPanel(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("\U0001f4d0 Analytical Core")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Summary card with copy button (#3)
        self._summary_frame = QtWidgets.QFrame()
        self._summary_frame.setObjectName("CardFrame")
        summary_layout = QtWidgets.QVBoxLayout(self._summary_frame)
        summary_layout.setContentsMargins(14, 10, 14, 10)
        summary_layout.setSpacing(6)

        summary_header = QtWidgets.QWidget()
        sh_layout = QtWidgets.QHBoxLayout(summary_header)
        sh_layout.setContentsMargins(0, 0, 0, 0)
        sh_label = QtWidgets.QLabel("Derivation")
        sh_label.setObjectName("SectionTitle")
        sh_layout.addWidget(sh_label)
        sh_layout.addStretch()
        copy_btn = QtWidgets.QPushButton("\U0001f4cb Copy")
        copy_btn.setFixedHeight(24)
        copy_btn.setStyleSheet(
            "background: transparent; border: 1px solid #334155; border-radius: 4px; "
            "color: #64748B; font-size: 10px; padding: 2px 8px;"
        )
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: _copy_to_clipboard(self.summary.toPlainText()))
        sh_layout.addWidget(copy_btn)
        summary_layout.addWidget(summary_header)

        self.summary = QtWidgets.QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMinimumHeight(60)
        summary_layout.addWidget(self.summary)

        # Steps card with collapsible steps (#9)
        self._steps_frame = QtWidgets.QFrame()
        self._steps_frame.setObjectName("CardFrame")
        steps_layout = QtWidgets.QVBoxLayout(self._steps_frame)
        steps_layout.setContentsMargins(14, 10, 14, 10)
        steps_layout.setSpacing(6)

        steps_header = QtWidgets.QWidget()
        sth_layout = QtWidgets.QHBoxLayout(steps_header)
        sth_layout.setContentsMargins(0, 0, 0, 0)
        sth_label = QtWidgets.QLabel("Steps")
        sth_label.setObjectName("SectionTitle")
        sth_layout.addWidget(sth_label)
        sth_layout.addStretch()
        self._expand_all_btn = QtWidgets.QPushButton("Expand all")
        self._expand_all_btn.setFixedHeight(24)
        self._expand_all_btn.setStyleSheet(
            "background: transparent; border: 1px solid #334155; border-radius: 4px; "
            "color: #64748B; font-size: 10px; padding: 2px 8px;"
        )
        self._expand_all_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._expand_all_btn.clicked.connect(self._toggle_all_steps)
        sth_layout.addWidget(self._expand_all_btn)
        steps_layout.addWidget(steps_header)

        self._steps_scroll = QtWidgets.QScrollArea()
        self._steps_scroll.setWidgetResizable(True)
        self._steps_scroll.setMinimumHeight(100)
        self._steps_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._steps_container = QtWidgets.QWidget()
        self._steps_vbox = QtWidgets.QVBoxLayout(self._steps_container)
        self._steps_vbox.setContentsMargins(0, 0, 0, 0)
        self._steps_vbox.setSpacing(4)
        self._steps_vbox.addStretch()
        self._steps_scroll.setWidget(self._steps_container)
        steps_layout.addWidget(self._steps_scroll)

        # Empty state (#12)
        self._empty_label = QtWidgets.QLabel(
            "\U0001f52c  Solve a problem to see the analytical derivation and step-by-step breakdown."
        )
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #475569; font-size: 12px; padding: 24px;")
        steps_layout.addWidget(self._empty_label)

        layout.addWidget(self._summary_frame, 2)
        layout.addWidget(self._steps_frame, 3)

        self._step_widgets: list[_CollapsibleStepWidget] = []
        self._all_expanded = False

    def _toggle_all_steps(self) -> None:
        self._all_expanded = not self._all_expanded
        for w in self._step_widgets:
            if w._expanded != self._all_expanded:
                w._toggle()
        self._expand_all_btn.setText("Collapse all" if self._all_expanded else "Expand all")

    def set_solver_result(self, solver: SolverResult) -> None:
        cache_note = " [cache]" if solver.cached else ""
        self.summary.setPlainText(f"{solver.summary}{cache_note}")
        self._empty_label.hide()

        for w in self._step_widgets:
            w.setParent(None)
            w.deleteLater()
        self._step_widgets.clear()

        for index, step in enumerate(solver.derivation_steps, start=1):
            widget = _CollapsibleStepWidget(index, step)
            self._steps_vbox.insertWidget(self._steps_vbox.count() - 1, widget)
            self._step_widgets.append(widget)


# ────────────────────────────────────────────────────────────────────────────
# Reference Panel
# ────────────────────────────────────────────────────────────────────────────


class _RagHitCard(QtWidgets.QFrame):
    """Single RAG hit card with source, score, excerpt, and copy button (#10)."""

    def __init__(self, source: str, page: int | None, score: float, excerpt: str,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFrame")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header row: source + score + copy
        header = QtWidgets.QWidget()
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        source_text = source
        if page:
            source_text += f" \u2022 p.{page}"
        src_label = QtWidgets.QLabel(source_text)
        src_label.setStyleSheet(
            "color: #06B6D4; font-size: 11px; font-weight: 600; "
            "font-family: 'Cascadia Code', monospace;"
        )
        h_layout.addWidget(src_label)
        h_layout.addStretch()

        score_label = QtWidgets.QLabel(f"{score:.2f}")
        score_color = "#10B981" if score > 0.7 else "#F59E0B" if score > 0.4 else "#64748B"
        score_label.setStyleSheet(
            f"color: {score_color}; font-size: 11px; font-weight: 700; "
            "font-family: 'Cascadia Code', monospace;"
        )
        h_layout.addWidget(score_label)

        copy_btn = QtWidgets.QPushButton("\U0001f4cb")
        copy_btn.setFixedWidth(28)
        copy_btn.setToolTip("Copy excerpt")
        copy_btn.setStyleSheet(
            "background: transparent; border: none; font-size: 12px; padding: 2px;"
        )
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: _copy_to_clipboard(excerpt))
        h_layout.addWidget(copy_btn)

        layout.addWidget(header)

        # Excerpt
        excerpt_label = QtWidgets.QLabel(excerpt)
        excerpt_label.setWordWrap(True)
        excerpt_label.setStyleSheet("color: #CBD5E1; font-size: 11px; line-height: 1.4;")
        layout.addWidget(excerpt_label)


class ReferencePanel(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("\U0001f4da Textbook Viewport")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # Backend label
        self._backend_label = QtWidgets.QLabel("")
        self._backend_label.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(self._backend_label)

        # Scrollable card container (#10)
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._card_container = QtWidgets.QWidget()
        self._card_layout = QtWidgets.QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(8)
        self._card_layout.addStretch()
        self._scroll.setWidget(self._card_container)
        layout.addWidget(self._scroll, 1)

        # Empty state (#12)
        self._empty_label = QtWidgets.QLabel(
            "\U0001f4d6  Textbook references will appear here after a pipeline run.\n"
            "Add PDFs to your library directory for richer results."
        )
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #475569; font-size: 12px; padding: 24px;")
        layout.addWidget(self._empty_label)

    def set_rag_result(self, rag: RagResult) -> None:
        # Clear old cards
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        if not rag.hits:
            self._empty_label.setText(
                f"No local references found via {rag.backend}.\n"
                "Add PDFs or text files to the library directory."
            )
            self._empty_label.show()
            self._backend_label.setText("")
            return

        self._empty_label.hide()
        self._backend_label.setText(f"Backend: {rag.backend} \u2022 {len(rag.hits)} hits")

        for hit in rag.hits:
            card = _RagHitCard(
                source=hit.source_name,
                page=hit.page_number,
                score=hit.score,
                excerpt=hit.excerpt,
            )
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)


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

        # Index 3: code viewer with copy button (#3)
        self._code_frame = QtWidgets.QFrame()
        self._code_frame.setObjectName("CardFrame")
        code_layout = QtWidgets.QVBoxLayout(self._code_frame)
        code_layout.setContentsMargins(14, 10, 14, 10)

        code_header = QtWidgets.QWidget()
        ch_layout = QtWidgets.QHBoxLayout(code_header)
        ch_layout.setContentsMargins(0, 0, 0, 0)
        ch_label = QtWidgets.QLabel("Generated Scene Code")
        ch_label.setStyleSheet(
            "color: #64748B; font-size: 9pt; font-weight: 700; "
            "text-transform: uppercase; letter-spacing: 1.2px;"
        )
        ch_layout.addWidget(ch_label)
        ch_layout.addStretch()
        copy_code_btn = QtWidgets.QPushButton("\U0001f4cb Copy code")
        copy_code_btn.setFixedHeight(26)
        copy_code_btn.setStyleSheet(
            "background: transparent; border: 1px solid #334155; border-radius: 4px; "
            "color: #64748B; font-size: 11px; padding: 2px 10px;"
        )
        copy_code_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_code_btn.clicked.connect(lambda: _copy_to_clipboard(self.code.toPlainText()))
        ch_layout.addWidget(copy_code_btn)
        code_layout.addWidget(code_header)

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

        # Frame step buttons (#14)
        self._prev_frame_btn = QtWidgets.QPushButton("\u23ea")
        self._prev_frame_btn.setFixedWidth(36)
        self._prev_frame_btn.setObjectName("VideoControlBtn")
        self._prev_frame_btn.setToolTip("Previous frame")

        self._play_btn = QtWidgets.QPushButton("\u25b6")
        self._play_btn.setFixedWidth(36)
        self._play_btn.setObjectName("VideoControlBtn")

        self._pause_btn = QtWidgets.QPushButton("\u23f8")
        self._pause_btn.setFixedWidth(36)
        self._pause_btn.setObjectName("VideoControlBtn")

        self._stop_btn = QtWidgets.QPushButton("\u23f9")
        self._stop_btn.setFixedWidth(36)
        self._stop_btn.setObjectName("VideoControlBtn")

        self._next_frame_btn = QtWidgets.QPushButton("\u23e9")
        self._next_frame_btn.setFixedWidth(36)
        self._next_frame_btn.setObjectName("VideoControlBtn")
        self._next_frame_btn.setToolTip("Next frame")

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

        controls_layout.addWidget(self._prev_frame_btn)  # #14
        controls_layout.addWidget(self._play_btn)
        controls_layout.addWidget(self._pause_btn)
        controls_layout.addWidget(self._stop_btn)
        controls_layout.addWidget(self._next_frame_btn)  # #14
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

        # Frame stepping: assume ~30fps, step by ~33ms (#14)
        self._prev_frame_btn.clicked.connect(lambda: self._step_frame(-33))
        self._next_frame_btn.clicked.connect(lambda: self._step_frame(33))

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

    def _step_frame(self, delta_ms: int) -> None:
        """Step forward/backward by ~1 frame (33ms at 30fps) (#14)."""
        self._player.pause()
        new_pos = max(0, self._player.position() + delta_ms)
        self._player.setPosition(new_pos)

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
