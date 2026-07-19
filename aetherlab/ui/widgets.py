"""Composable PyQt6 widgets for the redesigned dashboard shell."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from aetherlab.core.models import RagResult, SceneBundle, SolverResult
from aetherlab.ui import icons
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


class _NavRailButton(QtWidgets.QToolButton):
    """Icon-over-label rail item with a painted cyan left-edge indicator."""

    def __init__(self, icon_name: str, label: str, tooltip: str) -> None:
        super().__init__()
        self.setObjectName("NavRailItem")
        self._icon_name = icon_name
        self.setText(label)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QtCore.QSize(18, 18))
        self.setFixedSize(64, 56)
        self._sync_icon()
        self.toggled.connect(lambda _checked: self._sync_icon())

    def _sync_icon(self) -> None:
        if not self.isEnabled():
            color = "#3D4B5F"
        elif self.isChecked():
            color = "#06B6D4"
        else:
            color = "#94A3B8"
        self.setIcon(icons.icon(self._icon_name, 18, color))

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        if event.type() == QtCore.QEvent.Type.EnabledChange:
            self._sync_icon()
        super().changeEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        if self.isChecked():
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor("#06B6D4"))
            painter.drawRoundedRect(QtCore.QRectF(0, self.height() / 2 - 10, 3, 20), 1.5, 1.5)


class SidebarNav(QtWidgets.QWidget):
    """Persistent left icon rail \u2014 pure destinations (design: Rail.jsx).

    84px wide; every item maps 1:1 to what the single workspace shows.
    """

    item_selected = QtCore.pyqtSignal(int)

    _ITEMS = [
        ("sigma", "Solve", "Analytical derivation"),
        ("book-open", "Refs", "Library and references"),
        ("clapperboard", "Scene", "Visual sandbox"),
        ("sliders-horizontal", "Params", "Parameter panel"),
        ("history", "History", "Past pipeline runs"),
    ]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavRail")
        self.setFixedWidth(84)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(6)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        self._buttons: list[_NavRailButton] = []
        for idx, (icon_name, label, tooltip) in enumerate(self._ITEMS):
            btn = _NavRailButton(icon_name, label, tooltip)
            btn.clicked.connect(lambda checked, i=idx: self._on_click(i))
            self._buttons.append(btn)
            layout.addWidget(btn, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        if self._buttons:
            self._buttons[0].setChecked(True)

    def set_result_available(self, available: bool) -> None:
        """Params stays disabled until a run produced parameters (design: Rail.jsx)."""
        self._buttons[3].setEnabled(available)

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
    """Pipeline timeline \u2014 the design's hero component.

    Design: components/pipeline/PipelineTimeline.jsx. 32px circular nodes with
    2px status-colored borders (pending gray / active cyan + pulse glow /
    complete filled emerald + check / error rose + x), 2px connectors that fill
    emerald once the preceding stage completes, mono elapsed times, and an
    inline Cancel affordance under the active node.
    """

    STAGES = ["Solve", "RAG", "Scene", "Render"]

    cancel_requested = QtCore.pyqtSignal()

    _COLORS = {
        "pending": "#64748B",
        "active": "#06B6D4",
        "complete": "#10B981",
        "error": "#F43F5E",
    }
    _NODE_R = 15  # node radius
    _LABEL_FONT = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.DemiBold)
    _MONO_FONT = QtGui.QFont("Cascadia Code", 8)
    _CANCEL_FONT = QtGui.QFont("Segoe UI", 8)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PipelineStepper")
        self.setFixedHeight(84)
        self.setMouseTracking(True)

        self._statuses: list[str] = ["pending"] * len(self.STAGES)
        self._started: dict[int, float] = {}
        self._elapsed: dict[int, float] = {}
        self._current_stage = -1
        self._pulse_phase = 0.0
        self._cancel_rect: QtCore.QRectF | None = None
        self._cancellable = False

        self._pulse_timer = QtCore.QTimer(self)
        self._pulse_timer.timeout.connect(self._tick)
        self._pulse_timer.setInterval(50)

    # \u2500\u2500 public API (kept compatible with the previous stepper) \u2500\u2500

    def set_cancellable(self, cancellable: bool) -> None:
        self._cancellable = cancellable
        self.update()

    def set_stage(self, stage: int, status: str = "active") -> None:
        """Update pipeline stage. status: 'active', 'complete', 'error'."""
        import time

        self._current_stage = stage
        for i in range(len(self.STAGES)):
            if i < stage:
                new = "complete"
            elif i == stage:
                new = status if status in self._COLORS else "active"
            else:
                new = "pending"

            old = self._statuses[i]
            if new == "active" and old != "active":
                self._started[i] = time.monotonic()
            elif old == "active" and new in ("complete", "error"):
                if i in self._started:
                    self._elapsed[i] = time.monotonic() - self._started[i]
            elif new == "complete" and i not in self._elapsed and i in self._started:
                self._elapsed[i] = time.monotonic() - self._started[i]
            self._statuses[i] = new

        # Motion is a status signal: pulse only while a stage is live.
        if "active" in self._statuses:
            if not self._pulse_timer.isActive():
                self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
        self.update()

    def reset(self) -> None:
        self._statuses = ["pending"] * len(self.STAGES)
        self._started.clear()
        self._elapsed.clear()
        self._current_stage = -1
        self._pulse_timer.stop()
        self.update()

    # \u2500\u2500 painting \u2500\u2500

    def _tick(self) -> None:
        self._pulse_phase += 0.196  # ~1.6s period at 50ms ticks
        if self._pulse_phase > math.tau:
            self._pulse_phase -= math.tau
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        import time

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        n = len(self.STAGES)
        margin = 48
        avail = self.width() - 2 * margin
        step = avail / max(n - 1, 1)
        cy = 26.0
        r = self._NODE_R
        self._cancel_rect = None

        # Connectors first (under the nodes)
        for i in range(n - 1):
            x1 = margin + i * step + r
            x2 = margin + (i + 1) * step - r
            color = (
                self._COLORS["complete"]
                if self._statuses[i] == "complete"
                else "#1E293B"
            )
            painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
            painter.drawLine(QtCore.QPointF(x1, cy), QtCore.QPointF(x2, cy))

        for i, name in enumerate(self.STAGES):
            cx = margin + i * step
            status = self._statuses[i]
            color = QtGui.QColor(self._COLORS[status])
            center = QtCore.QPointF(cx, cy)

            # Active pulse glow (design: aeth-pulse, 1.6s)
            if status == "active":
                glow = QtGui.QColor(self._COLORS["active"])
                pulse = (math.sin(self._pulse_phase) + 1) / 2  # 0..1
                glow.setAlphaF(0.28 * (1 - pulse * 0.6))
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(glow)
                painter.drawEllipse(center, r + 4 + pulse * 5, r + 4 + pulse * 5)

            # Node circle
            painter.setPen(QtGui.QPen(color, 2))
            painter.setBrush(
                QtGui.QColor(self._COLORS["complete"])
                if status == "complete"
                else QtGui.QColor("#0D0D14")
            )
            painter.drawEllipse(center, r, r)

            # Node glyph
            if status == "complete":
                painter.drawPixmap(
                    QtCore.QPointF(cx - 8, cy - 8),
                    icons.icon_pixmap("check", 16, "#04141A"),
                )
            elif status == "error":
                painter.drawPixmap(
                    QtCore.QPointF(cx - 8, cy - 8),
                    icons.icon_pixmap("x", 16, self._COLORS["error"]),
                )
            elif status == "active":
                # Rotating arc spinner
                pen = QtGui.QPen(color, 2)
                pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                start_angle = int(-self._pulse_phase / math.tau * 360 * 16 * 3)
                painter.drawArc(
                    QtCore.QRectF(cx - 8, cy - 8, 16, 16), start_angle, 120 * 16
                )

            # Label
            painter.setFont(self._LABEL_FONT)
            painter.setPen(
                QtGui.QColor("#64748B" if status == "pending" else "#F8FAFC")
            )
            painter.drawText(
                QtCore.QRectF(cx - step / 2, cy + r + 4, step, 16),
                QtCore.Qt.AlignmentFlag.AlignHCenter,
                name,
            )

            # Elapsed (mono) or Cancel under the active node
            sub_rect = QtCore.QRectF(cx - step / 2, cy + r + 20, step, 14)
            if status == "active" and self._cancellable:
                painter.setFont(self._CANCEL_FONT)
                painter.setPen(QtGui.QColor(self._COLORS["error"]))
                painter.drawText(
                    sub_rect, QtCore.Qt.AlignmentFlag.AlignHCenter, "Cancel"
                )
                self._cancel_rect = QtCore.QRectF(cx - 24, cy + r + 18, 48, 18)
            else:
                elapsed = self._elapsed.get(i)
                if elapsed is None and status == "active" and i in self._started:
                    elapsed = time.monotonic() - self._started[i]
                if elapsed is not None:
                    painter.setFont(self._MONO_FONT)
                    painter.setPen(QtGui.QColor("#64748B"))
                    painter.drawText(
                        sub_rect,
                        QtCore.Qt.AlignmentFlag.AlignHCenter,
                        f"{elapsed:.1f}s",
                    )

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._cancel_rect and self._cancel_rect.contains(event.position()):
            self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._cancel_rect and self._cancel_rect.contains(event.position()):
            self.cancel_requested.emit()
        super().mousePressEvent(event)


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

        title = QtWidgets.QLabel("History")
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
        clear_btn.setObjectName("GhostButton")
        clear_btn.setIcon(icons.icon("trash", 13, "#94A3B8"))
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
        try:
            conn.execute(self._HISTORY_TABLE_SQL)
            conn.commit()
            # Load last 100 entries
            rows = conn.execute(
                "SELECT prompt, cache_key, scene_status, num_refs, created_at "
                "FROM history ORDER BY id DESC LIMIT 100"
            ).fetchall()
        finally:
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
            try:
                conn.execute(self._HISTORY_TABLE_SQL)
                conn.execute(
                    "INSERT INTO history (prompt, cache_key, scene_status, num_refs, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (prompt, cache_key, scene_status, num_refs, datetime.now().isoformat()),
                )
                conn.commit()
            finally:
                conn.close()

    def _add_entry_ui(self, prompt: str, cache_key: str, scene_status: str,
                      num_refs: int, ts: str) -> None:
        # Normalize timestamp: strip date part if ISO format
        if "T" in ts:
            ts = ts.split("T")[1][:8]
        ok = scene_status in ("rendered", "compiled")

        item = QtWidgets.QListWidgetItem()
        item.setData(QtCore.Qt.ItemDataRole.UserRole, prompt)
        item.setToolTip("Double-click to re-run")

        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(14, 8, 14, 8)
        row_layout.setSpacing(12)
        row_layout.addWidget(icons.icon_label(
            "check-circle" if ok else "x-circle", 16,
            "#10B981" if ok else "#F43F5E",
        ))
        text_col = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        prompt_label = QtWidgets.QLabel(prompt[:96])
        prompt_label.setStyleSheet(
            "color: #F8FAFC; font-size: 13px; background: transparent;")
        text_layout.addWidget(prompt_label)
        meta = QtWidgets.QLabel(f"{ts} · {num_refs} refs · {cache_key[:12]}")
        meta.setStyleSheet(
            "color: #64748B; font-size: 10.5px; "
            "font-family: 'Cascadia Code', monospace; background: transparent;")
        text_layout.addWidget(meta)
        row_layout.addWidget(text_col, 1)
        row_layout.addWidget(icons.icon_label("rotate-cw", 14, "#64748B"))

        item.setSizeHint(row.sizeHint())
        self._list.insertItem(0, item)
        self._list.setItemWidget(item, row)
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
            try:
                conn.execute("DELETE FROM history")
                conn.commit()
            finally:
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
    """Command bar (design: components/forms/CommandBar.jsx).

    A raised shell containing: Examples popup (lightbulb + chevron), hairline
    divider, borderless prompt field, quality selector, and a primary Run
    button that swaps to a danger Cancel while busy.
    """

    submitted = QtCore.pyqtSignal(str)
    cancel_requested = QtCore.pyqtSignal()

    _QUALITIES = {"Draft": "l", "Standard": "m", "High": "h"}

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommandBarDock")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(20, 14, 20, 14)

        shell = QtWidgets.QFrame()
        shell.setObjectName("CommandBarShell")
        layout = QtWidgets.QHBoxLayout(shell)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # Examples popup button (ghost, menu anchored above the bar)
        self._examples_btn = QtWidgets.QPushButton("Examples")
        self._examples_btn.setObjectName("ExamplesButton")
        self._examples_btn.setIcon(icons.icon("lightbulb", 14, "#94A3B8"))
        self._examples_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._examples_btn.clicked.connect(self._show_examples_menu)
        layout.addWidget(self._examples_btn)

        divider = QtWidgets.QFrame()
        divider.setObjectName("VDivider")
        divider.setFixedWidth(1)
        layout.addWidget(divider)

        # Prompt field - transparent inside the shell
        self.input = QtWidgets.QLineEdit()
        self.input.setObjectName("CommandInput")
        self.input.setPlaceholderText(
            "Describe a physics or math problem…  (Ctrl+Enter to run)"
        )
        self.input.returnPressed.connect(self._submit)
        layout.addWidget(self.input, 1)

        # Render quality selector
        self._quality = QtWidgets.QComboBox()
        self._quality.setObjectName("QualityCombo")
        self._quality.addItems(list(self._QUALITIES.keys()))
        self._quality.setCurrentIndex(0)
        self._quality.setFixedWidth(104)
        self._quality.setToolTip(
            "Render quality — Draft 480p / Standard 720p / High 1080p"
        )
        layout.addWidget(self._quality)

        # Run button (primary) / Cancel (danger) swap
        self.run_button = QtWidgets.QPushButton("Run")
        self.run_button.setObjectName("RunButton")
        self.run_button.setIcon(icons.icon("play", 14, "#04141A"))
        self.run_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.run_button.clicked.connect(self._submit)
        layout.addWidget(self.run_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setObjectName("CancelButton")
        self.cancel_button.setIcon(icons.icon("square", 14, "#F43F5E"))
        self.cancel_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)

        outer.addWidget(shell)

    def _show_examples_menu(self) -> None:
        menu = QtWidgets.QMenu(self)
        for prompt in EXAMPLE_PROMPTS:
            label = prompt[:64] + "…" if len(prompt) > 64 else prompt
            action = menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, p=prompt: self._pick_example(p)
            )
        # Anchor above the button (design: popover opens upward)
        menu.adjustSize()
        pos = self._examples_btn.mapToGlobal(
            QtCore.QPoint(0, -menu.sizeHint().height() - 6)
        )
        menu.exec(pos)

    def _pick_example(self, prompt: str) -> None:
        self.input.setText(prompt)
        self.input.setFocus()

    def get_render_quality(self) -> str:
        """Return the Manim quality flag (l/m/h) for the selected quality."""
        label = self._quality.currentText()
        return self._QUALITIES.get(label, "l")

    def set_quality(self, flag: str) -> None:
        """Select quality by Manim flag (used by the Settings default)."""
        for label, value in self._QUALITIES.items():
            if value == flag:
                self._quality.setCurrentText(label)
                return

    def set_busy(self, busy: bool) -> None:
        self.run_button.setVisible(not busy)
        self.cancel_button.setVisible(busy)
        self.input.setDisabled(busy)

    def _submit(self) -> None:
        prompt = self.input.text().strip()
        if prompt and self.run_button.isVisible():
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
        self._spans: dict[str, float] = {}
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
                lambda raw, key=name: self._on_slider_change(key, raw)
            )

            # Spin box for precise numeric input (#7) — allow negative values
            spinbox = QtWidgets.QDoubleSpinBox()
            spinbox.setRange(-span, span)
            spinbox.setValue(value)
            spinbox.setDecimals(4)
            spinbox.setSingleStep(span / 100)
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
        span = self._spans.get(name, 1.0)
        value = (raw / self._SLIDER_TICKS) * 2 * span - span  # map [0,1000] to [-span, +span]
        if name in self._sliders:
            _, spinbox, _, _ = self._sliders[name]
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
        self.parameter_changed.emit(name, value)

    def _on_spinbox_change(self, name: str, value: float) -> None:
        if name in self._sliders:
            slider, _, _, _ = self._sliders[name]
            span = self._spans.get(name, self._span_for(value))
            if abs(value) > span:
                span = self._span_for(value)
                self._spans[name] = span
                spinbox = self._sliders[name][1]
                spinbox.setRange(-span, span)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(value, span))
            slider.blockSignals(False)
        self.parameter_changed.emit(name, value)

    def _reset_param(self, name: str, original_value: float) -> None:
        if name in self._sliders:
            slider, spinbox, _, _ = self._sliders[name]
            span = self._spans.get(name, self._span_for(original_value))
            spinbox.blockSignals(True)
            spinbox.setValue(original_value)
            spinbox.blockSignals(False)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(original_value, span))
            slider.blockSignals(False)
            self.parameter_changed.emit(name, original_value)

    def _value_to_tick(self, value: float, span: float) -> int:
        if span <= 0:
            return self._SLIDER_TICKS // 2  # center for zero span
        return max(0, min(self._SLIDER_TICKS, int((value + span) / (2 * span) * self._SLIDER_TICKS)))

    def update_variable(self, name: str, value: float) -> None:
        if name in self._sliders:
            slider, spinbox, _, _ = self._sliders[name]
            span = self._spans.get(name, self._span_for(value))
            if abs(value) > span:
                span = self._span_for(value)
                self._spans[name] = span
                spinbox.setRange(-span, span)  # keep negative range (matches set_variables)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(value, span))
            slider.blockSignals(False)
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)

    def _clear(self) -> None:
        while self._container_layout.rowCount():
            self._container_layout.removeRow(0)
        self._sliders.clear()
        self._spans.clear()


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

        copy_btn = QtWidgets.QPushButton()
        copy_btn.setIcon(icons.icon("copy", 12, "#64748B"))
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
    """Derivation block (design: components/content/DerivationBlock.jsx).

    Card with a cyan mono summary banner, violet keyword chips, collapsible
    numbered steps, and a Copy / Export footer.
    """

    export_latex_requested = QtCore.pyqtSignal()
    export_pdf_requested = QtCore.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        card = QtWidgets.QFrame()
        card.setObjectName("CardFrame")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 16)
        card_layout.setSpacing(14)

        # Summary banner (design: summaryEquation — cyan italic mono)
        self.summary = QtWidgets.QLabel("")
        self.summary.setObjectName("EquationBanner")
        self.summary.setWordWrap(True)
        self.summary.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.summary.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        card_layout.addWidget(self.summary)

        # Keyword chips (violet pills)
        self._chips_row = QtWidgets.QWidget()
        self._chips_layout = QtWidgets.QHBoxLayout(self._chips_row)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch()
        self._chips_row.hide()
        card_layout.addWidget(self._chips_row)

        # Steps header row
        steps_header = QtWidgets.QWidget()
        sth_layout = QtWidgets.QHBoxLayout(steps_header)
        sth_layout.setContentsMargins(0, 0, 0, 0)
        sth_label = QtWidgets.QLabel("DERIVATION STEPS")
        sth_label.setObjectName("SectionTitle")
        sth_layout.addWidget(sth_label)
        sth_layout.addStretch()
        self._expand_all_btn = QtWidgets.QPushButton("Expand all")
        self._expand_all_btn.setObjectName("GhostButton")
        self._expand_all_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._expand_all_btn.clicked.connect(self._toggle_all_steps)
        sth_layout.addWidget(self._expand_all_btn)
        card_layout.addWidget(steps_header)

        # Collapsible steps in a scroll area
        self._steps_scroll = QtWidgets.QScrollArea()
        self._steps_scroll.setWidgetResizable(True)
        self._steps_scroll.setMinimumHeight(120)
        self._steps_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        self._steps_container = QtWidgets.QWidget()
        self._steps_vbox = QtWidgets.QVBoxLayout(self._steps_container)
        self._steps_vbox.setContentsMargins(0, 0, 0, 0)
        self._steps_vbox.setSpacing(4)
        self._steps_vbox.addStretch()
        self._steps_scroll.setWidget(self._steps_container)
        card_layout.addWidget(self._steps_scroll, 1)

        # Empty state
        self._empty_label = QtWidgets.QLabel(
            "Solve a problem to see the analytical derivation and "
            "step-by-step breakdown."
        )
        self._empty_label.setObjectName("EmptyHint")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._empty_label)

        # Footer: Copy / Export (design: DerivationBlock footer)
        footer = QtWidgets.QWidget()
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 6, 0, 0)
        footer_layout.setSpacing(8)

        copy_btn = QtWidgets.QPushButton("Copy")
        copy_btn.setObjectName("SecondaryButton")
        copy_btn.setIcon(icons.icon("copy", 13, "#94A3B8"))
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_all)
        footer_layout.addWidget(copy_btn)

        export_btn = QtWidgets.QPushButton("Export")
        export_btn.setObjectName("SecondaryButton")
        export_btn.setIcon(icons.icon("download", 13, "#94A3B8"))
        export_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(lambda: self._show_export_menu(export_btn))
        footer_layout.addWidget(export_btn)
        footer_layout.addStretch()
        card_layout.addWidget(footer)

        layout.addWidget(card, 1)

        self._step_widgets: list[_CollapsibleStepWidget] = []
        self._all_expanded = False
        self._steps_text: list[str] = []

    def _show_export_menu(self, anchor: QtWidgets.QWidget) -> None:
        menu = QtWidgets.QMenu(self)
        menu.addAction("Export as LaTeX…", self.export_latex_requested.emit)
        menu.addAction("Export as PDF…", self.export_pdf_requested.emit)
        menu.exec(anchor.mapToGlobal(QtCore.QPoint(0, anchor.height() + 4)))

    def _copy_all(self) -> None:
        parts = [self.summary.text()]
        parts += [f"{i}. {s}" for i, s in enumerate(self._steps_text, start=1)]
        _copy_to_clipboard("\n".join(p for p in parts if p))

    def _toggle_all_steps(self) -> None:
        self._all_expanded = not self._all_expanded
        for w in self._step_widgets:
            if w._expanded != self._all_expanded:
                w._toggle()
        self._expand_all_btn.setText(
            "Collapse all" if self._all_expanded else "Expand all"
        )

    def set_solver_result(self, solver: SolverResult) -> None:
        cache_note = "  [cache]" if solver.cached else ""
        self.summary.setText(f"{solver.summary}{cache_note}")
        self._empty_label.hide()

        # Keyword chips
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        keywords = list(solver.keywords)[:6]
        for kw in keywords:
            chip = QtWidgets.QLabel(kw)
            chip.setObjectName("KeywordChip")
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)
        self._chips_row.setVisible(bool(keywords))

        # Steps
        for w in self._step_widgets:
            w.setParent(None)
            w.deleteLater()
        self._step_widgets.clear()
        self._steps_text = list(solver.derivation_steps)

        for index, step in enumerate(solver.derivation_steps, start=1):
            widget = _CollapsibleStepWidget(index, step)
            self._steps_vbox.insertWidget(self._steps_vbox.count() - 1, widget)
            self._step_widgets.append(widget)

    def update_variable(self, name: str, value: float) -> None:
        pass  # Parameters live in the parameter panel


# ────────────────────────────────────────────────────────────────────────────
# Reference Panel
# ────────────────────────────────────────────────────────────────────────────


class _RagHitCard(QtWidgets.QFrame):
    """Reference card (design: components/content/ReferenceCard.jsx).

    Book icon + source + page, threshold-colored score pill, excerpt,
    and an Open link that opens the source file.
    """

    def __init__(self, source: str, page: int | None, score: float, excerpt: str,
                 source_path: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFrame")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header row: icon + source + page + score pill + copy
        header = QtWidgets.QWidget()
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        h_layout.addWidget(icons.icon_label("book-open", 14, "#06B6D4"))

        src_label = QtWidgets.QLabel(source)
        src_label.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 600;")
        h_layout.addWidget(src_label)

        if page:
            page_label = QtWidgets.QLabel(f"p.{page}")
            page_label.setStyleSheet("color: #64748B; font-size: 11px;")
            h_layout.addWidget(page_label)
        h_layout.addStretch()

        # Score pill — emerald >= 0.8, amber >= 0.5, else tertiary (design thresholds)
        score_color = "#10B981" if score >= 0.8 else "#F59E0B" if score >= 0.5 else "#64748B"
        score_label = QtWidgets.QLabel(f"{score:.2f}")
        score_label.setStyleSheet(
            f"color: {score_color}; border: 1px solid {score_color}; "
            "border-radius: 9px; padding: 1px 8px; font-size: 11px; "
            "font-family: 'Cascadia Code', monospace;"
        )
        h_layout.addWidget(score_label)

        copy_btn = QtWidgets.QPushButton()
        copy_btn.setIcon(icons.icon("copy", 13, "#64748B"))
        copy_btn.setFixedSize(24, 24)
        copy_btn.setToolTip("Copy excerpt")
        copy_btn.setStyleSheet("background: transparent; border: none;")
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: _copy_to_clipboard(excerpt))
        h_layout.addWidget(copy_btn)

        layout.addWidget(header)

        # Excerpt
        excerpt_label = QtWidgets.QLabel(excerpt)
        excerpt_label.setWordWrap(True)
        excerpt_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(excerpt_label)

        # Open link (design: "Open" + arrow-up-right)
        if source_path:
            open_btn = QtWidgets.QPushButton("Open")
            open_btn.setObjectName("LinkButton")
            open_btn.setIcon(icons.icon("arrow-up-right", 12, "#06B6D4"))
            open_btn.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
            open_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(
                lambda: QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(source_path)
                )
            )
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(open_btn)
            row.addStretch()
            layout.addLayout(row)


class ReferencePanel(QtWidgets.QWidget):
    """References column (design: DerivationView right column)."""

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("REFERENCES")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self._backend_label = QtWidgets.QLabel("")
        self._backend_label.setStyleSheet(
            "color: #64748B; font-size: 11px; font-family: 'Cascadia Code', monospace;"
        )
        layout.addWidget(self._backend_label)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._card_container = QtWidgets.QWidget()
        self._card_layout = QtWidgets.QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(10)
        self._card_layout.addStretch()
        self._scroll.setWidget(self._card_container)
        layout.addWidget(self._scroll, 1)

        # Empty state (design copy: name the missing thing, one action)
        self._empty_label = QtWidgets.QLabel(
            "Textbook references will appear here after a run.\n"
            "Add PDFs or text files to the library to enable retrieval."
        )
        self._empty_label.setObjectName("EmptyHint")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
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
        self._backend_label.setText(f"{rag.backend} · {len(rag.hits)} hits")

        for hit in rag.hits:
            card = _RagHitCard(
                source=hit.source_name,
                page=hit.page_number,
                score=hit.score,
                excerpt=hit.excerpt,
                source_path=hit.source_path,
            )
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)


# ────────────────────────────────────────────────────────────────────────────
# Simulation Panel (Visual Sandbox)
# ────────────────────────────────────────────────────────────────────────────


class SimulationPanel(QtWidgets.QWidget):
    parameter_changed = QtCore.pyqtSignal(str, float)
    phase_toggled = QtCore.pyqtSignal(bool)
    save_video_requested = QtCore.pyqtSignal()
    export_gif_requested = QtCore.pyqtSignal()
    export_scene_requested = QtCore.pyqtSignal()

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
        self._phase_check = QtWidgets.QCheckBox("Phase-portrait overlay")
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
        copy_code_btn = QtWidgets.QPushButton("Copy code")
        copy_code_btn.setIcon(icons.icon("copy", 12, "#64748B"))
        copy_code_btn.setFixedHeight(26)
        copy_code_btn.setStyleSheet(
            "background: transparent; border: 1px solid #334155; border-radius: 4px; "
            "color: #64748B; font-size: 11px; padding: 2px 10px;"
        )
        copy_code_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_code_btn.clicked.connect(lambda: _copy_to_clipboard(self.code.toPlainText()))
        ch_layout.addWidget(copy_code_btn)

        export_code_btn = QtWidgets.QPushButton("Export scene.py")
        export_code_btn.setObjectName("SecondaryButton")
        export_code_btn.setIcon(icons.icon("download", 13, "#94A3B8"))
        export_code_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        export_code_btn.clicked.connect(self.export_scene_requested.emit)
        ch_layout.addWidget(export_code_btn)
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

    def apply_plan(self, plan) -> None:
        """Show only the view pills the planner enabled for this problem.

        Canvas is shown when a 2-D or 3-D graphic is warranted; Video only when
        an animation is planned; Code is always available. If the active pill
        gets hidden, fall back to the first visible one.
        """
        self._plan = plan
        want = {
            0: bool(getattr(plan, "needs_2d", True) or getattr(plan, "needs_3d", False)),
            1: bool(getattr(plan, "needs_animation", True)),
            2: True,
        }
        for btn in self._pill_group.buttons():
            btn.setVisible(want.get(self._pill_group.id(btn), True))
        checked = self._pill_group.checkedButton()
        if checked is None or not checked.isVisible():
            for btn in self._pill_group.buttons():
                if btn.isVisible():
                    btn.setChecked(True)
                    self._switch_view(self._pill_group.id(btn))
                    break

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

        # Controls bar (design: components/media/VideoControls.jsx)
        controls = QtWidgets.QFrame()
        controls.setObjectName("VideoControlsBar")
        controls.setMaximumHeight(52)
        controls_layout = QtWidgets.QHBoxLayout(controls)
        controls_layout.setContentsMargins(14, 8, 14, 8)
        controls_layout.setSpacing(10)

        # Frame step buttons (#14)
        self._prev_frame_btn = QtWidgets.QPushButton()
        self._prev_frame_btn.setIcon(icons.icon("skip-back", 14, "#94A3B8"))
        self._prev_frame_btn.setFixedSize(28, 28)
        self._prev_frame_btn.setObjectName("VideoControlBtn")
        self._prev_frame_btn.setToolTip("Previous frame")

        # Round cyan primary play button (design)
        self._play_btn = QtWidgets.QPushButton()
        self._play_btn.setIcon(icons.icon("play", 15, "#04141A"))
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setObjectName("VideoPlayBtn")
        self._play_btn.setToolTip("Play")

        self._pause_btn = QtWidgets.QPushButton()
        self._pause_btn.setIcon(icons.icon("pause", 14, "#94A3B8"))
        self._pause_btn.setFixedSize(28, 28)
        self._pause_btn.setObjectName("VideoControlBtn")
        self._pause_btn.setToolTip("Pause")

        self._stop_btn = QtWidgets.QPushButton()
        self._stop_btn.setIcon(icons.icon("square", 13, "#94A3B8"))
        self._stop_btn.setFixedSize(28, 28)
        self._stop_btn.setObjectName("VideoControlBtn")
        self._stop_btn.setToolTip("Stop")

        self._next_frame_btn = QtWidgets.QPushButton()
        self._next_frame_btn.setIcon(icons.icon("skip-forward", 14, "#94A3B8"))
        self._next_frame_btn.setFixedSize(28, 28)
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
        self._time_label.setMinimumWidth(90)

        self._speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._speed_slider.setRange(25, 200)
        self._speed_slider.setValue(100)
        self._speed_slider.setToolTip("Playback speed")
        self._speed_slider.setFixedWidth(72)
        speed_label = QtWidgets.QLabel("1.0x")
        speed_label.setObjectName("VideoTimeLabel")

        # Save / GIF export (design: Save affordance on the controls bar)
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setObjectName("SecondaryButton")
        save_btn.setIcon(icons.icon("save", 13, "#94A3B8"))
        save_btn.setToolTip("Save the rendered MP4")
        save_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.save_video_requested.emit)

        gif_btn = QtWidgets.QPushButton("GIF")
        gif_btn.setObjectName("SecondaryButton")
        gif_btn.setIcon(icons.icon("film", 13, "#94A3B8"))
        gif_btn.setToolTip("Export as animated GIF (needs ffmpeg)")
        gif_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        gif_btn.clicked.connect(self.export_gif_requested.emit)

        controls_layout.addWidget(self._play_btn)
        controls_layout.addWidget(self._pause_btn)
        controls_layout.addWidget(self._stop_btn)
        controls_layout.addWidget(self._prev_frame_btn)  # #14
        controls_layout.addWidget(self._next_frame_btn)  # #14
        controls_layout.addWidget(self._seek_slider, 1)
        controls_layout.addWidget(self._time_label)
        controls_layout.addWidget(self._speed_slider)
        controls_layout.addWidget(speed_label)
        controls_layout.addWidget(save_btn)
        controls_layout.addWidget(gif_btn)

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
            plot=getattr(self._solver, "plot", None),
            numeric_spec=getattr(self._solver, "numeric_spec", None),
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
        if scene.status == "skipped":
            # Planner decided this problem doesn't need an animation — present it
            # as an intentional state, not an error, and point at the PDF.
            self.status.setText("No animation needed — export the research PDF from Analysis.")
            self.status.setObjectName("StatusReady")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.code.setPlainText(
                "# No Manim animation was generated for this problem.\n"
                "# The planner judged an animation unnecessary here.\n"
                "# Use 'Export PDF' in the Analysis panel for the written result."
            )
            return
        self.status.setText(f"Engine: {scene.engine} | Status: {scene.status}")
        if scene.status == "compiled":
            self.status.setObjectName("StatusReady")
        else:
            self.status.setObjectName("StatusError")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        if scene.diagnostics:
            diag_lines = "\n".join(f"# {line}" for line in scene.diagnostics)
            self.code.setPlainText(f"{scene.code}\n\n# Diagnostics:\n{diag_lines}")
        else:
            self.code.setPlainText(scene.code)
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)

    def set_video(self, scene: SceneBundle) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QMediaPlayer

        if scene.video_path and Path(scene.video_path).exists():
            self._stack.setCurrentIndex(2)
            self._player.setSource(QUrl.fromLocalFile(scene.video_path))
            # Play when media is loaded (async loading)
            try:
                self._player.mediaStatusChanged.disconnect(self._auto_play)
            except (TypeError, RuntimeError):
                pass
            self._player.mediaStatusChanged.connect(self._auto_play)
            self.status.setText(f"\U0001f3ac Loading: {Path(scene.video_path).name}")
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
                diag_lines = "\n".join(f"# {line}" for line in scene.diagnostics)
                self.code.setPlainText(scene.code + "\n\n# Diagnostics:\n" + diag_lines)

    def _auto_play(self, media_status) -> None:
        """Play video once media is loaded."""
        from PyQt6.QtMultimedia import QMediaPlayer
        if media_status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._player.play()
            try:
                self._player.mediaStatusChanged.disconnect(self._auto_play)
            except (TypeError, RuntimeError):
                pass
            self.status.setText(f"\U0001f3ac Playing")

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
        # Prevent duplicate windows
        if hasattr(self, "_detail_window") and self._detail_window is not None:
            self._detail_window.setPlainText(self._error_traceback)
            self._detail_window.raise_()
            return
        detail = QtWidgets.QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(self._error_traceback)
        detail.setWindowTitle("Pipeline Traceback")
        detail.resize(900, 500)
        detail.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        detail.destroyed.connect(lambda: setattr(self, "_detail_window", None))
        self._detail_window = detail
        detail.show()



# ────────────────────────────────────────────────────────────────────────────
# Title Bar (design: ui_kits/aetherlab-desktop/TitleBar.jsx)
# ────────────────────────────────────────────────────────────────────────────


class TitleBar(QtWidgets.QWidget):
    """44px brand strip: atom mark + wordmark + settings gear."""

    settings_requested = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(44)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 10, 0)
        layout.setSpacing(10)

        layout.addWidget(icons.icon_label("atom", 16, "#06B6D4"))

        wordmark = QtWidgets.QLabel("AetherLab")
        wordmark.setObjectName("TitleWordmark")
        layout.addWidget(wordmark)
        layout.addStretch()

        settings_btn = QtWidgets.QToolButton()
        settings_btn.setObjectName("TitleIconButton")
        settings_btn.setIcon(icons.icon("settings", 16, "#94A3B8"))
        settings_btn.setToolTip("Settings")
        settings_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(settings_btn)


# ────────────────────────────────────────────────────────────────────────────
# Toast (design: components/feedback/Toast.jsx)
# ────────────────────────────────────────────────────────────────────────────


class Toast(QtWidgets.QFrame):
    """Inline kind-colored banner: icon, message, optional Details, dismiss."""

    details_requested = QtCore.pyqtSignal()

    _KINDS = {
        "error": ("#F43F5E", "rgba(244, 63, 94, 0.10)", "alert-triangle"),
        "warning": ("#F59E0B", "rgba(245, 158, 11, 0.10)", "alert-circle"),
        "success": ("#10B981", "rgba(16, 185, 129, 0.10)", "check-circle"),
        "info": ("#06B6D4", "rgba(6, 182, 212, 0.10)", "info"),
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = "error"

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self._icon = QtWidgets.QLabel()
        self._icon.setFixedSize(18, 18)
        self._icon.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._icon, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        self._message = QtWidgets.QLabel("")
        self._message.setWordWrap(True)
        self._message.setStyleSheet(
            "color: #F8FAFC; font-size: 12.5px; font-weight: 500; "
            "background: transparent; border: none;"
        )
        layout.addWidget(self._message, 1)

        self._details_btn = QtWidgets.QPushButton("Details")
        self._details_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._details_btn.clicked.connect(self.details_requested.emit)
        layout.addWidget(self._details_btn)

        dismiss = QtWidgets.QPushButton()
        dismiss.setIcon(icons.icon("x", 13, "#64748B"))
        dismiss.setFixedSize(22, 22)
        dismiss.setStyleSheet("background: transparent; border: none;")
        dismiss.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        dismiss.clicked.connect(self.hide)
        layout.addWidget(dismiss, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        self.hide()

    def show_message(self, kind: str, message: str, details: bool = False) -> None:
        color, bg, icon_name = self._KINDS.get(kind, self._KINDS["info"])
        self._kind = kind
        self._icon.setPixmap(icons.icon_pixmap(icon_name, 16, color))
        self._message.setText(message)
        self._details_btn.setVisible(details)
        self._details_btn.setStyleSheet(
            f"background: transparent; border: none; color: {color}; "
            "font-size: 11px; font-weight: 700; padding: 2px 6px;"
        )
        self.setStyleSheet(
            f"Toast {{ background-color: {bg}; border: 1px solid {color}; "
            f"border-radius: 8px; }}"
        )
        self.show()


# ────────────────────────────────────────────────────────────────────────────
# Empty / first-run state (design: ui_kits EmptyState.jsx — screen 01)
# ────────────────────────────────────────────────────────────────────────────


class EmptyStateView(QtWidgets.QWidget):
    """Describe-a-problem hero with example chips and setup call-to-actions."""

    example_picked = QtCore.pyqtSignal(str)
    settings_requested = QtCore.pyqtSignal()
    library_requested = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        mark = icons.icon_label("atom", 40, "#06B6D4")
        layout.addWidget(mark, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        headline = QtWidgets.QLabel("Describe a problem to begin")
        headline.setStyleSheet("color: #F8FAFC; font-size: 28px; font-weight: 700;")
        headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(headline)

        sub = QtWidgets.QLabel(
            "Type a physics or math prompt below, or start from an example."
        )
        sub.setStyleSheet("color: #94A3B8; font-size: 14px;")
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        # Example chips
        chips_row = QtWidgets.QWidget()
        chips_layout = QtWidgets.QHBoxLayout(chips_row)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(10)
        chips_layout.addStretch()
        for example in EXAMPLE_PROMPTS[:3]:
            label = example[:52] + "…" if len(example) > 52 else example
            chip = QtWidgets.QPushButton(label)
            chip.setObjectName("ExampleChip")
            chip.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(
                lambda checked=False, p=example: self.example_picked.emit(p)
            )
            chips_layout.addWidget(chip)
        chips_layout.addStretch()
        layout.addWidget(chips_row)

        # Setup status strip (dashed border, API key / library CTAs)
        self._setup_strip = QtWidgets.QFrame()
        self._setup_strip.setStyleSheet(
            "QFrame { background-color: #0D0D14; border: 1px dashed #334155; "
            "border-radius: 12px; }"
            "QLabel, QPushButton { border: none; background: transparent; }"
        )
        strip_layout = QtWidgets.QHBoxLayout(self._setup_strip)
        strip_layout.setContentsMargins(20, 12, 20, 12)
        strip_layout.setSpacing(16)

        self._key_icon = icons.icon_label("key-round", 16, "#F59E0B")
        strip_layout.addWidget(self._key_icon)
        self._key_label = QtWidgets.QLabel("No API key configured")
        self._key_label.setStyleSheet("color: #94A3B8; font-size: 12.5px;")
        strip_layout.addWidget(self._key_label)
        key_btn = QtWidgets.QPushButton("Open Settings")
        key_btn.setStyleSheet("color: #06B6D4; font-size: 12.5px; font-weight: 600;")
        key_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        key_btn.clicked.connect(self.settings_requested.emit)
        strip_layout.addWidget(key_btn)

        div = QtWidgets.QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet("background-color: #1E293B; border: none;")
        strip_layout.addWidget(div)

        strip_layout.addWidget(icons.icon_label("library", 16, "#F59E0B"))
        self._lib_label = QtWidgets.QLabel("No textbooks indexed")
        self._lib_label.setStyleSheet("color: #94A3B8; font-size: 12.5px;")
        strip_layout.addWidget(self._lib_label)
        lib_btn = QtWidgets.QPushButton("Add textbooks")
        lib_btn.setStyleSheet("color: #06B6D4; font-size: 12.5px; font-weight: 600;")
        lib_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        lib_btn.clicked.connect(self.library_requested.emit)
        strip_layout.addWidget(lib_btn)

        layout.addSpacing(6)
        layout.addWidget(self._setup_strip, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

    def set_status(self, has_api_key: bool, model: str, library_count: int) -> None:
        if has_api_key:
            self._key_icon.setPixmap(icons.icon_pixmap("check-circle", 16, "#10B981"))
            self._key_label.setText(f"Model: {model}")
        else:
            self._key_icon.setPixmap(icons.icon_pixmap("key-round", 16, "#F59E0B"))
            self._key_label.setText("No API key configured")
        if library_count:
            plural = "s" if library_count != 1 else ""
            self._lib_label.setText(f"{library_count} textbook{plural} in library")
        else:
            self._lib_label.setText("No textbooks indexed")


# ────────────────────────────────────────────────────────────────────────────
# Running view (design: ui_kits RunningView.jsx — screen 02)
# ────────────────────────────────────────────────────────────────────────────


class RunningView(QtWidgets.QWidget):
    """Pipeline-in-flight state: animated overlay + live stage status text."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._overlay = BlueprintLoadingOverlay()
        layout.addWidget(self._overlay, 1)

        strip = QtWidgets.QWidget()
        strip.setStyleSheet("background-color: #0A0A0F;")
        strip_layout = QtWidgets.QVBoxLayout(strip)
        strip_layout.setContentsMargins(20, 8, 20, 24)
        strip_layout.setSpacing(4)

        self._headline = QtWidgets.QLabel("Working…")
        self._headline.setStyleSheet(
            "color: #F8FAFC; font-size: 18px; font-weight: 600;"
        )
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        strip_layout.addWidget(self._headline)

        self._detail = QtWidgets.QLabel("")
        self._detail.setStyleSheet(
            "color: #64748B; font-size: 12px; font-family: 'Cascadia Code', monospace;"
        )
        self._detail.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        strip_layout.addWidget(self._detail)

        layout.addWidget(strip)

    def set_stage_text(self, headline: str, detail: str = "") -> None:
        self._headline.setText(headline)
        self._detail.setText(detail)


# ────────────────────────────────────────────────────────────────────────────
# Library manager (design: ui_kits LibraryManager.jsx — screen 06)
# ────────────────────────────────────────────────────────────────────────────


class _IngestWorker(QtCore.QThread):
    """Background library ingestion so Re-index never blocks the UI."""

    finished_count = QtCore.pyqtSignal(int)
    failed = QtCore.pyqtSignal(str)
    # (file_name, files_done, files_total, detail)
    progress = QtCore.pyqtSignal(str, int, int, str)

    def __init__(self, settings, reset: bool = False) -> None:
        super().__init__()
        self._settings = settings
        self._reset = reset

    def run(self) -> None:
        try:
            from aetherlab.services.ingestion import LibraryIngestor

            count = LibraryIngestor(self._settings).ingest(
                reset=self._reset,
                progress=lambda f, d, t, x: self.progress.emit(f, d, t, x),
                should_cancel=self.isInterruptionRequested,
            )
            self.finished_count.emit(count)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class _DownloadWorker(QtCore.QThread):
    """Background OpenStax starter-library downloader.

    One failed book does not abort the rest; cancel via requestInterruption().
    """

    book_progress = QtCore.pyqtSignal(str, int, int)  # title, bytes_done, bytes_total
    book_done = QtCore.pyqtSignal(str)
    book_failed = QtCore.pyqtSignal(str, str)
    all_done = QtCore.pyqtSignal(int, int)  # succeeded, failed

    def __init__(self, books: list, dest_dir: Path) -> None:
        super().__init__()
        self._books = books
        self._dest_dir = dest_dir

    def run(self) -> None:
        from aetherlab.services.starter_library import download_book, resolve_pdf_urls

        urls = resolve_pdf_urls(self._books)
        ok = bad = 0
        for book in self._books:
            if self.isInterruptionRequested():
                break
            try:
                result = download_book(
                    book,
                    urls[book.key],
                    self._dest_dir,
                    progress_cb=lambda done, total, b=book: self.book_progress.emit(
                        b.title, done, total
                    ),
                    cancel_check=self.isInterruptionRequested,
                )
            except Exception as exc:  # noqa: BLE001
                bad += 1
                self.book_failed.emit(book.title, str(exc))
                continue
            if result is None:  # cancelled mid-book (.part already cleaned)
                break
            ok += 1
            self.book_done.emit(book.title)
        self.all_done.emit(ok, bad)


class StarterLibraryDialog(QtWidgets.QDialog):
    """Pick OpenStax starter books to download (design-system styled)."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        from aetherlab.services.starter_library import STARTER_BOOKS

        self.setWindowTitle("Get starter library")
        self.setMinimumWidth(430)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Get starter library")
        title.setStyleSheet("color: #F8FAFC; font-size: 17px; font-weight: 700;")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "OpenStax physics textbooks — free, CC BY 4.0. Downloaded into your "
            "library folder and indexed for references."
        )
        subtitle.setStyleSheet("color: #94A3B8; font-size: 12px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._checks: list[tuple[QtWidgets.QCheckBox, object]] = []
        for book in STARTER_BOOKS:
            check = QtWidgets.QCheckBox(f"{book.title}  (~{book.approx_mb} MB)")
            check.setChecked(book.default_checked)
            check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            check.toggled.connect(self._update_warning)
            layout.addWidget(check)
            self._checks.append((check, book))

        self._warning = QtWidgets.QLabel(
            "Astronomy, Calculus, and College Physics deepen coverage (orbits, the "
            "underlying calculus, and a broad algebra-based survey) but add "
            "substantial download and indexing time."
        )
        self._warning.setStyleSheet(
            "color: #F59E0B; font-size: 11px; background-color: rgba(245,158,11,0.10); "
            "border: 1px solid #F59E0B; border-radius: 8px; padding: 8px 10px;"
        )
        self._warning.setWordWrap(True)
        self._warning.hide()
        layout.addWidget(self._warning)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch()
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        download_btn = QtWidgets.QPushButton("Download")
        download_btn.setObjectName("PrimaryButton")
        download_btn.setIcon(icons.icon("download", 14, "#04141A"))
        download_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        download_btn.clicked.connect(self.accept)
        footer.addWidget(download_btn)
        layout.addLayout(footer)

    def _update_warning(self) -> None:
        extra = any(
            check.isChecked() and not book.default_checked
            for check, book in self._checks
        )
        self._warning.setVisible(extra)

    def selected_books(self) -> list:
        return [book for check, book in self._checks if check.isChecked()]


class LibraryPanel(QtWidgets.QWidget):
    """Library manager: starter downloads, indexed sources, incremental re-index."""

    status_message = QtCore.pyqtSignal(str)

    _SUFFIXES = {".pdf", ".txt", ".md", ".tex"}

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = None
        self._worker: _IngestWorker | None = None
        self._downloader: _DownloadWorker | None = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        title = QtWidgets.QLabel("Library")
        title.setObjectName("PanelTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        starter_btn = QtWidgets.QPushButton("Get starter library")
        starter_btn.setObjectName("SecondaryButton")
        starter_btn.setIcon(icons.icon("download", 14, "#94A3B8"))
        starter_btn.setToolTip("Download free OpenStax physics textbooks (CC BY 4.0)")
        starter_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        starter_btn.clicked.connect(self._get_starter_library)
        header_layout.addWidget(starter_btn)

        add_btn = QtWidgets.QPushButton("Add folder")
        add_btn.setObjectName("SecondaryButton")
        add_btn.setIcon(icons.icon("folder-plus", 14, "#94A3B8"))
        add_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_folder)
        header_layout.addWidget(add_btn)

        self._reindex_btn = QtWidgets.QPushButton("Re-index")
        self._reindex_btn.setObjectName("SecondaryButton")
        self._reindex_btn.setIcon(icons.icon("refresh-cw", 14, "#94A3B8"))
        self._reindex_btn.setToolTip(
            "Index new/changed files. Ctrl+click for a full rebuild."
        )
        self._reindex_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._reindex_btn.clicked.connect(self._reindex_clicked)
        header_layout.addWidget(self._reindex_btn)

        layout.addWidget(header)

        # ── Progress strip (downloads + indexing), hidden by default ──
        self._progress_strip = QtWidgets.QFrame()
        self._progress_strip.setObjectName("CardFrame")
        strip_layout = QtWidgets.QHBoxLayout(self._progress_strip)
        strip_layout.setContentsMargins(14, 8, 14, 8)
        strip_layout.setSpacing(12)

        self._progress_label = QtWidgets.QLabel("")
        self._progress_label.setStyleSheet(
            "color: #94A3B8; font-size: 11px; font-family: 'Cascadia Code', monospace; "
            "background: transparent; border: none;"
        )
        strip_layout.addWidget(self._progress_label, 1)

        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background-color: #1E293B; border: none; border-radius: 3px; }"
            "QProgressBar::chunk { background-color: #06B6D4; border-radius: 3px; }"
        )
        strip_layout.addWidget(self._progress_bar, 2)

        cancel_work_btn = QtWidgets.QPushButton("Cancel")
        cancel_work_btn.setObjectName("GhostButton")
        cancel_work_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        cancel_work_btn.clicked.connect(self._cancel_work)
        strip_layout.addWidget(cancel_work_btn)

        self._progress_strip.hide()
        layout.addWidget(self._progress_strip)

        self._path_label = QtWidgets.QLabel("")
        self._path_label.setStyleSheet(
            "color: #64748B; font-size: 11px; font-family: 'Cascadia Code', monospace;"
        )
        layout.addWidget(self._path_label)

        # Source list shell
        self._list_shell = QtWidgets.QFrame()
        self._list_shell.setObjectName("ListShell")
        shell_layout = QtWidgets.QVBoxLayout(self._list_shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        self._list = QtWidgets.QListWidget()
        shell_layout.addWidget(self._list)
        layout.addWidget(self._list_shell, 1)

        # Empty state (design: ReferenceEmptyState — dashed border + actions)
        self._empty = QtWidgets.QFrame()
        self._empty.setStyleSheet(
            "QFrame { border: 1px dashed #334155; border-radius: 12px; }"
            "QLabel, QPushButton { border: none; }"
        )
        empty_layout = QtWidgets.QVBoxLayout(self._empty)
        empty_layout.setContentsMargins(32, 32, 32, 32)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(
            icons.icon_label("library", 24, "#64748B"), 0,
            QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        empty_text = QtWidgets.QLabel("No textbooks indexed yet")
        empty_text.setStyleSheet("color: #94A3B8; font-size: 14px;")
        empty_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_text)
        empty_add = QtWidgets.QPushButton("Add textbooks…")
        empty_add.setObjectName("PrimaryButton")
        empty_add.setIcon(icons.icon("folder-plus", 14, "#04141A"))
        empty_add.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        empty_add.clicked.connect(self._add_folder)
        empty_layout.addWidget(empty_add, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        empty_starter = QtWidgets.QPushButton("Get starter library")
        empty_starter.setObjectName("SecondaryButton")
        empty_starter.setIcon(icons.icon("download", 14, "#94A3B8"))
        empty_starter.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        empty_starter.clicked.connect(self._get_starter_library)
        empty_layout.addWidget(empty_starter, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._empty, 1)
        self._empty.hide()

    # ── shared state ──

    def set_settings(self, settings) -> None:
        self._settings = settings
        self.refresh()

    def library_file_count(self) -> int:
        if not self._settings:
            return 0
        root = Path(self._settings.library_path)
        if not root.exists():
            return 0
        return sum(1 for p in root.rglob("*") if p.suffix.lower() in self._SUFFIXES)

    def _busy(self) -> bool:
        return bool(
            (self._worker and self._worker.isRunning())
            or (self._downloader and self._downloader.isRunning())
        )

    def refresh(self) -> None:
        self._list.clear()
        if not self._settings:
            return
        root = Path(self._settings.library_path)
        self._path_label.setText(str(root))
        files = (
            sorted(p for p in root.rglob("*") if p.suffix.lower() in self._SUFFIXES)
            if root.exists()
            else []
        )
        self._list_shell.setVisible(bool(files))
        self._empty.setVisible(not files)

        indexed_paths = self._indexed_paths()
        for path in files:
            item = QtWidgets.QListWidgetItem()
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(14, 8, 14, 8)
            row_layout.setSpacing(12)
            row_layout.addWidget(icons.icon_label("file-text", 15, "#64748B"))
            name = QtWidgets.QLabel(path.name)
            name.setStyleSheet(
                "color: #F8FAFC; font-size: 12.5px; background: transparent;"
            )
            row_layout.addWidget(name, 1)
            size_kb = path.stat().st_size / 1024
            size = QtWidgets.QLabel(
                f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
            )
            size.setStyleSheet(
                "color: #64748B; font-size: 11px; "
                "font-family: 'Cascadia Code', monospace; background: transparent;"
            )
            row_layout.addWidget(size)
            indexed = str(path) in indexed_paths
            chip = QtWidgets.QLabel("Indexed" if indexed else "Pending")
            chip_color = "#10B981" if indexed else "#06B6D4"
            chip.setStyleSheet(
                f"color: {chip_color}; border: 1px solid {chip_color}; "
                "border-radius: 9px; padding: 1px 9px; font-size: 11px; "
                "background: transparent;"
            )
            row_layout.addWidget(chip)
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

    def _indexed_paths(self) -> set[str]:
        """Paths recorded in the ingest manifest (per-file 'Indexed' chips)."""
        if not self._settings:
            return set()
        try:
            from aetherlab.services.ingestion import LibraryIngestor

            ingestor = LibraryIngestor(self._settings)
            return set(ingestor._load_manifest().keys())
        except Exception:  # noqa: BLE001
            return set()

    # ── starter library download flow ──

    def _get_starter_library(self) -> None:
        if not self._settings:
            return
        if self._busy():
            self.status_message.emit("A download or indexing task is already running.")
            return

        dialog = StarterLibraryDialog(self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        books = dialog.selected_books()
        if not books:
            return

        from aetherlab.services.starter_library import free_disk_mb

        root = Path(self._settings.library_path)
        if free_disk_mb(root) < 500:
            self.status_message.emit(
                "Not enough disk space: the starter library needs at least 500 MB free."
            )
            return

        self._progress_strip.show()
        self._progress_bar.setRange(0, 0)  # indeterminate until sizes known
        self._progress_label.setText("Resolving download URLs…")

        self._downloader = _DownloadWorker(books, root)
        self._downloader.book_progress.connect(self._on_book_progress)
        self._downloader.book_done.connect(self._on_book_done)
        self._downloader.book_failed.connect(self._on_book_failed)
        self._downloader.all_done.connect(self._on_downloads_done)
        self._downloader.start()

    def _on_book_progress(self, title: str, done: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setRange(0, 1000)
            self._progress_bar.setValue(int(done / total * 1000))
            self._progress_label.setText(
                f"Downloading {title} — {done / 1e6:.1f} / {total / 1e6:.1f} MB"
            )
        else:
            self._progress_bar.setRange(0, 0)
            self._progress_label.setText(
                f"Downloading {title} — {done / 1e6:.1f} MB"
            )

    def _on_book_done(self, title: str) -> None:
        self.status_message.emit(f"Downloaded: {title}")
        self.refresh()

    def _on_book_failed(self, title: str, message: str) -> None:
        self.status_message.emit(f"Download failed: {title} — {message}")

    def _on_downloads_done(self, ok: int, bad: int) -> None:
        from aetherlab.services.starter_library import write_attribution

        # BUG-6: a user-cancelled run must not silently roll into indexing.
        # Cancel just hid the progress strip; auto-starting the ingest here
        # re-shows it and keeps the machine busy against the user's intent.
        # Index what already arrived only on a natural, uncancelled finish.
        cancelled = bool(
            self._downloader and self._downloader.isInterruptionRequested()
        )
        if ok:
            write_attribution(Path(self._settings.library_path))
        self.refresh()
        if cancelled:
            self._progress_strip.hide()
            if ok:
                self.status_message.emit(
                    f"Download cancelled — {ok} book{'s' if ok != 1 else ''} saved; "
                    "click Re-index to add them to references."
                )
            else:
                self.status_message.emit("Download cancelled.")
            return
        if ok == 0:
            self._progress_strip.hide()
            self.status_message.emit(
                f"Starter library: nothing downloaded ({bad} failed)."
            )
            return
        self.status_message.emit(
            f"Starter library: {ok} book{'s' if ok != 1 else ''} downloaded"
            + (f", {bad} failed" if bad else "")
            + ". Indexing…"
        )
        # Auto-start incremental indexing of the new books.
        self._start_ingest(reset=False)

    # ── indexing ──

    def _reindex_clicked(self) -> None:
        # Incremental by default; Ctrl+click forces a full rebuild.
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        full = bool(modifiers & QtCore.Qt.KeyboardModifier.ControlModifier)
        self._reindex(reset=full)

    def _reindex(self, reset: bool = False) -> None:
        if not self._settings or self._busy():
            return
        self._start_ingest(reset=reset)

    def _start_ingest(self, reset: bool) -> None:
        self._reindex_btn.setEnabled(False)
        self._reindex_btn.setText("Indexing…")
        self._progress_strip.show()
        self._progress_bar.setRange(0, 0)
        self._progress_label.setText(
            "Rebuilding index…" if reset else "Indexing new files…"
        )
        self.status_message.emit("Indexing library into ChromaDB…")
        self._worker = _IngestWorker(self._settings, reset=reset)
        self._worker.progress.connect(self._on_ingest_progress)
        self._worker.finished_count.connect(self._on_ingested)
        self._worker.failed.connect(self._on_ingest_failed)
        self._worker.start()

    def _on_ingest_progress(self, file_name: str, done: int, total: int, detail: str) -> None:
        self._progress_bar.setRange(0, 0)  # chunk totals are per-file; keep sweep
        self._progress_label.setText(
            f"Indexing {file_name} ({done + 1}/{total}) — {detail}"
        )

    def _on_ingested(self, count: int) -> None:
        self._reindex_btn.setEnabled(True)
        self._reindex_btn.setText("Re-index")
        self._progress_strip.hide()
        if count:
            self.status_message.emit(f"Indexed {count:,} chunks into ChromaDB.")
        else:
            self.status_message.emit("Library index is already up to date.")
        self.refresh()

    def _on_ingest_failed(self, message: str) -> None:
        self._reindex_btn.setEnabled(True)
        self._reindex_btn.setText("Re-index")
        self._progress_strip.hide()
        self.status_message.emit(f"Indexing failed: {message}")

    def _cancel_work(self) -> None:
        if self._downloader and self._downloader.isRunning():
            self._downloader.requestInterruption()
            self.status_message.emit("Cancelling download…")
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self.status_message.emit(
                "Cancelling indexing — progress is saved and resumes on Re-index."
            )
        self._progress_strip.hide()
        self._reindex_btn.setEnabled(True)
        self._reindex_btn.setText("Re-index")

    # ── add folder ──

    def _add_folder(self) -> None:
        if not self._settings:
            return
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Add textbooks from folder"
        )
        if not folder:
            return
        import shutil

        root = Path(self._settings.library_path)
        root.mkdir(parents=True, exist_ok=True)
        copied = 0
        for path in sorted(Path(folder).rglob("*")):
            if path.suffix.lower() in self._SUFFIXES and path.is_file():
                target = root / path.name
                if not target.exists():
                    shutil.copy2(path, target)
                    copied += 1
        self.status_message.emit(f"Added {copied} files to the library.")
        self.refresh()
        if copied:
            self._reindex()
