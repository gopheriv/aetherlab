"""Sidebar destinations, workflow timeline, and recent-history panels."""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime
from pathlib import Path

from aetherlab.ui import icons
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt

require_qt()

class _NavRailButton(QtWidgets.QToolButton):
    """Full-width, keyboard-accessible destination in the student sidebar."""

    def __init__(self, icon_name: str, label: str, tooltip: str) -> None:
        super().__init__()
        self.setObjectName("NavRailItem")
        self._icon_name = icon_name
        self.setText(label)
        self.setToolTip(f"{label} - {tooltip}")
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QtCore.QSize(18, 18))
        self.setFixedHeight(58)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._sync_icon()
        self.toggled.connect(lambda _checked: self._sync_icon())

    def _sync_icon(self) -> None:
        if not self.isEnabled():
            color = "#65758A"
        elif self.isChecked():
            color = "#486A91"
        else:
            color = "#65758A"
        self.setIcon(icons.icon(self._icon_name, 18, color))

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        if event.type() == QtCore.QEvent.Type.EnabledChange:
            self._sync_icon()
        super().changeEvent(event)

class SidebarNav(QtWidgets.QWidget):
    """Persistent student sidebar with preparation and physics-lab destinations."""

    item_selected = QtCore.pyqtSignal(int)

    _ITEMS = [
        ("atom", "Home", "Student dashboard"),
        ("book-open", "Topics", "Physics topics for ЕНТ/ҰБТ"),
        ("play", "Practice", "ЕНТ/ҰБТ practice and mock exam"),
        ("history", "Progress", "Scores and topics to revisit"),
        ("lightbulb", "AI Tutor", "Ask a physics question or build a lesson"),
        ("library", "Library", "Textbooks and references"),
        ("history", "History", "Past physics runs"),
        ("clapperboard", "Lab", "Physics simulations and video lessons"),
        ("spider", "Spider", "See the workbench and repair visible bugs"),
    ]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = False
        self._dense = False
        self._tight = False
        self._full_labels = [item[1] for item in self._ITEMS]
        self._compact_labels = self._full_labels[:]
        self.setObjectName("NavRail")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedWidth(92)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Ignored)
        layout = QtWidgets.QVBoxLayout(self)
        # Let resizeEvent reduce density before old tall button minima can
        # force the parent window back to its previous height.
        layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetNoConstraint)
        self._layout = layout
        layout.setContentsMargins(10, 16, 10, 12)
        layout.setSpacing(5)
        mark = QtWidgets.QLabel("P")
        self._mark = mark
        mark.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(40, 40)
        mark.setStyleSheet("background:#486A91; color:#FFFFFF; border-radius:14px; font-size:21px; font-weight:800;")
        layout.addWidget(mark, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        self._brand_gap = QtWidgets.QSpacerItem(0, 14, QtWidgets.QSizePolicy.Policy.Minimum,
                                               QtWidgets.QSizePolicy.Policy.Fixed)
        layout.addSpacerItem(self._brand_gap)
        # These labels retain the translated accessible descriptions.
        self._brand_descriptor = QtWidgets.QLabel(self)
        self._section_label = QtWidgets.QLabel(self)
        self._tools_label = None
        self._footer_title = QtWidgets.QLabel(self)
        self._footer_hint = QtWidgets.QLabel(self)
        for label in (self._brand_descriptor, self._section_label, self._footer_title, self._footer_hint):
            label.hide()
        self._buttons = []
        for idx, (icon_name, label, tooltip) in enumerate(self._ITEMS):
            if idx == 4:
                line = QtWidgets.QFrame()
                line.setFixedHeight(1)
                line.setStyleSheet("background:#D8E1EC;")
                layout.addSpacing(6)
                layout.addWidget(line)
                layout.addSpacing(6)
            btn = _NavRailButton(icon_name, label, tooltip)
            btn.clicked.connect(lambda checked, i=idx: self._on_click(i))
            self._buttons.append(btn)
            layout.addWidget(btn)
        layout.addStretch()

        if self._buttons:
            self._buttons[0].setChecked(True)
        self._apply_density()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_density()

    def _apply_density(self) -> None:
        dense = self.height() < 650
        tight = self.height() < 520
        if (dense, tight) == (self._dense, self._tight):
            return
        self._dense = dense
        self._tight = tight
        self._layout.setContentsMargins(10, 8 if dense else 16, 10, 8 if dense else 12)
        self._layout.setSpacing(2 if dense else 5)
        self._mark.setFixedSize(32 if dense else 40, 32 if dense else 40)
        self._brand_gap.changeSize(0, 6 if tight else 14, QtWidgets.QSizePolicy.Policy.Minimum,
                                   QtWidgets.QSizePolicy.Policy.Fixed)
        for button in self._buttons:
            button.setFixedHeight(self._item_height())
        self._layout.invalidate()

    def _item_height(self) -> int:
        if self._tight:
            return 40
        return (42 if self._dense else 48) if self._expanded else (44 if self._dense else 58)

    def set_result_available(self, available: bool) -> None:
        """The lab view is available before and after the first run."""
        self._buttons[7].setEnabled(True)

    def set_language(self, language: str) -> None:
        compact_labels = {
            "kk": ["Бет", "Тақырып", "ҰБТ", "Ұпай", "AI", "Кітап", "Тарих", "Зертхана", "Өрмекші"],
            "ru": ["Главная", "Темы", "ЕНТ", "Баллы", "AI", "Книги", "История", "Лаба", "Паук"],
            "en": ["Home", "Topics", "Practice", "Stats", "AI", "Library", "History", "Lab", "Spider"],
        }.get(language, [item[1] for item in self._ITEMS])
        self._compact_labels = compact_labels
        self._full_labels = {
            "kk": ["Басты бет", "Тақырыптар", "Жаттығу", "Прогресс", "AI көмекші", "Кітапхана", "Тарих", "Зертхана", "Өрмекші"],
            "ru": ["Главная", "Темы", "Практика", "Прогресс", "AI-помощник", "Библиотека", "История", "Лаборатория", "Паук"],
            "en": ["Home", "Topics", "Practice", "Progress", "AI tutor", "Library", "History", "Laboratory", "Spider"],
        }.get(language, [item[1] for item in self._ITEMS])
        hints = {
            "kk": ["Оқушының басты беті", "ҰБТ физика тақырыптары", "ҰБТ жаттығуы және сынақ нұсқасы", "Ұпайлар мен қайталау тақырыптары", "Физика сұрағын қой немесе сабақ жаса", "Оқулықтар мен дереккөздер", "Алдыңғы физика жұмыстары", "Физикалық симуляциялар", "Экраннан ақау тауып, түзету"],
            "ru": ["План подготовки к ЕНТ", "Темы физики для ЕНТ", "Тренировка и пробный вариант", "Баллы и темы для повторения", "Задай вопрос или создай урок", "Учебники и материалы", "История занятий", "Физические симуляции", "Найти и исправить ошибки на экране"],
            "en": ["Student study plan", "Physics topics for UNT", "Practice and full mock", "Scores and topics to revisit", "Ask or learn physics", "Textbooks and references", "Past learning runs", "Physics simulations", "Scan the screen and repair bugs"],
        }.get(language, [item[2] for item in self._ITEMS])
        self._brand_descriptor.setText(
            {"kk": "ҰБТ · Физика", "ru": "ЕНТ · Физика", "en": "UNT · Physics"}.get(language, "UNT · Physics")
        )
        self._section_label.setText(
            {"kk": "ДАЙЫНДЫҚ", "ru": "ПОДГОТОВКА", "en": "PREPARATION"}.get(language, "STUDY")
        )
        if self._tools_label is not None:
            self._tools_label.setText(
                {"kk": "ФИЗИКА ҚҰРАЛДАРЫ", "ru": "ИНСТРУМЕНТЫ ФИЗИКИ", "en": "PHYSICS TOOLS"}.get(language, "TOOLS")
            )
        self._footer_title.setText(
            {"kk": "Физиканы сенімді меңгер", "ru": "Уверенно разбирайся в физике", "en": "Build confidence in physics"}.get(language, "Build confidence in physics")
        )
        self._footer_hint.setText(
            {"kk": "Күн сайынғы дайындық жоспары", "ru": "Твой план подготовки на каждый день", "en": "A clear plan for each study day"}.get(language, "A clear plan for each study day")
        )
        for index, (button, hint) in enumerate(zip(self._buttons, hints)):
            button.setText(self._full_labels[index] if self._expanded else compact_labels[index])
            button.setToolTip(f"{self._full_labels[index]} · {hint}")

    def set_expanded(self, expanded: bool) -> None:
        """Show readable labels when the desktop window has room for them."""
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self.setFixedWidth(208 if expanded else 92)
        for index, button in enumerate(self._buttons):
            button.setToolButtonStyle(
                QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
                if expanded else QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            )
            button.setFixedHeight(self._item_height())
            button.setText(
                self._full_labels[index] if expanded else self._compact_labels[index]
            )
            button.setProperty("expanded", expanded)
            button.style().unpolish(button)
            button.style().polish(button)

    def _on_click(self, index: int) -> None:
        self.set_current(index)
        self.item_selected.emit(index)

    def set_current(self, index: int) -> None:
        """Update the selected destination without opening its route again."""
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)

    def select(self, index: int) -> None:
        self._on_click(index)

    def label_for(self, index: int) -> str:
        if 0 <= index < len(self._buttons):
            return self._full_labels[index]
        return ""

    def selected_index(self) -> int:
        return next(
            (index for index, button in enumerate(self._buttons) if button.isChecked()),
            0,
        )

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

class PipelineStepper(QtWidgets.QWidget):
    """Pipeline timeline \u2014 the design's hero component.

    Design: components/pipeline/PipelineTimeline.jsx. 32px circular nodes with
    2px status-colored borders (pending gray / active sky blue + pulse glow /
    complete filled emerald + check / error rose + x), 2px connectors that fill
    emerald once the preceding stage completes, mono elapsed times, and an
    inline Cancel affordance under the active node.
    """

    STAGES = ["Solve", "RAG", "Scene", "Render"]

    cancel_requested = QtCore.pyqtSignal()

    _COLORS = {
        "pending": "#65758A",
        "active": "#486A91",
        "complete": "#26725C",
        "error": "#AC4055",
        "cancelled": "#65758A",
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
        self._language = "kk"
        self._stage_labels = ["Шешу", "Іздеу", "Сахна", "Рендер"]
        self._cancel_label = "Тоқтату"
        self._cancelled_label = "Тоқтатылды"
        self._cancel_rect: QtCore.QRectF | None = None
        self._cancellable = False

        self._pulse_timer = QtCore.QTimer(self)
        self._pulse_timer.timeout.connect(self._tick)
        self._pulse_timer.setInterval(50)

    def set_language(self, language: str) -> None:
        copy = {
            "kk": (["Шешу", "Іздеу", "Сахна", "Рендер"], "Тоқтату", "Тоқтатылды"),
            "ru": (["Решение", "Поиск", "Сцена", "Рендер"], "Отмена", "Отменено"),
            "en": (["Solve", "RAG", "Scene", "Render"], "Cancel", "Cancelled"),
        }
        self._language = language if language in copy else "kk"
        self._stage_labels, self._cancel_label, self._cancelled_label = copy[self._language]
        self.update()

    # \u2500\u2500 public API (kept compatible with the previous stepper) \u2500\u2500

    def set_cancellable(self, cancellable: bool) -> None:
        self._cancellable = cancellable
        self.update()

    def set_stage(self, stage: int, status: str = "active") -> None:
        """Update pipeline stage, including a terminal neutral cancellation."""
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
            elif old == "active" and new in ("complete", "error", "cancelled"):
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
                else "#D8E1EC"
            )
            painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
            painter.drawLine(QtCore.QPointF(x1, cy), QtCore.QPointF(x2, cy))

        for i, name in enumerate(self._stage_labels):
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
                else QtGui.QColor("#F4F7FB" if status in {"active", "complete"} else "#53647A")
            )
            painter.drawEllipse(center, r, r)

            # Node glyph
            if status == "complete":
                painter.drawPixmap(
                    QtCore.QPointF(cx - 8, cy - 8),
                    icons.icon_pixmap("check", 16, "#F4F7FB"),
                )
            elif status == "error":
                painter.drawPixmap(
                    QtCore.QPointF(cx - 8, cy - 8),
                    icons.icon_pixmap("x", 16, self._COLORS["error"]),
                )
            elif status == "cancelled":
                painter.setPen(QtGui.QPen(QtGui.QColor("#F4F7FB"), 2))
                painter.drawLine(QtCore.QPointF(cx - 5, cy), QtCore.QPointF(cx + 5, cy))
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
                QtGui.QColor("#65758A" if status == "pending" else "#18283D")
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
                    sub_rect, QtCore.Qt.AlignmentFlag.AlignHCenter, self._cancel_label
                )
                self._cancel_rect = QtCore.QRectF(cx - 24, cy + r + 18, 48, 18)
            else:
                elapsed = self._elapsed.get(i)
                if status == "cancelled":
                    painter.setFont(self._CANCEL_FONT)
                    painter.setPen(QtGui.QColor("#65758A"))
                    text = self._cancelled_label + (f" · {elapsed:.1f}s" if elapsed is not None else "")
                    painter.drawText(sub_rect, QtCore.Qt.AlignmentFlag.AlignHCenter, text)
                    continue
                if elapsed is None and status == "active" and i in self._started:
                    elapsed = time.monotonic() - self._started[i]
                if elapsed is not None:
                    painter.setFont(self._MONO_FONT)
                    painter.setPen(QtGui.QColor("#65758A"))
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

class HistoryPanel(QtWidgets.QWidget):
    """Chronological list of past pipeline runs, clickable to re-run.
    Persists entries to SQLite across restarts (#5)."""

    prompt_selected = QtCore.pyqtSignal(str)

    _COPY = {
        "kk": {
            "title": "Тарих", "clear": "Тазалау", "empty": "Әзірге орындалған тапсырма жоқ.",
            "rerun": "Қайта орындау үшін екі рет басыңыз", "count": "{n} жазба",
        },
        "ru": {
            "title": "История", "clear": "Очистить", "empty": "Пока нет выполненных задач.",
            "rerun": "Дважды щёлкните, чтобы запустить снова", "count": "Записей: {n}",
        },
        "en": {
            "title": "History", "clear": "Clear", "empty": "Completed tasks will appear here.",
            "rerun": "Double-click to run again", "count": "{n} entries",
        },
    }

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
        self._language = "kk"
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._title = QtWidgets.QLabel()
        self._title.setObjectName("PanelTitle")
        layout.addWidget(self._title)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("HistoryList")
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._empty = QtWidgets.QLabel()
        self._empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            "color:#65758A; font-size:13px; padding:24px; "
            "background:#FFFFFF; border:1px dashed #A5B6CB; border-radius:12px;"
        )
        self._history_stack = QtWidgets.QStackedWidget()
        self._history_stack.addWidget(self._list)
        self._history_stack.addWidget(self._empty)
        layout.addWidget(self._history_stack, 1)

        bottom = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self._count_label = QtWidgets.QLabel("0 entries")
        self._count_label.setStyleSheet("color: #65758A; font-size: 11px;")
        bottom_layout.addWidget(self._count_label)
        bottom_layout.addStretch()

        self._clear_btn = QtWidgets.QPushButton()
        self._clear_btn.setObjectName("GhostButton")
        self._clear_btn.setIcon(icons.icon("trash", 13, "#65758A"))
        self._clear_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear)
        bottom_layout.addWidget(self._clear_btn)
        layout.addWidget(bottom)

        self._entries: list[str] = []
        self._db_path: Path | None = None
        self.set_language(self._language)

    def set_language(self, language: str) -> None:
        self._language = language if language in self._COPY else "kk"
        copy = self._COPY[self._language]
        self._title.setText(copy["title"])
        self._clear_btn.setText(copy["clear"])
        self._empty.setText(copy["empty"])
        self._count_label.setText(copy["count"].format(n=self._list.count()))
        for index in range(self._list.count()):
            self._list.item(index).setToolTip(copy["rerun"])
        self._history_stack.setCurrentWidget(
            self._list if self._list.count() else self._empty
        )

    def _update_count(self) -> None:
        copy = self._COPY[self._language]
        self._count_label.setText(copy["count"].format(n=self._list.count()))
        self._history_stack.setCurrentWidget(
            self._list if self._list.count() else self._empty
        )

    def init_persistence(self, db_path: Path) -> None:
        """Set up SQLite persistence and load saved entries (#5)."""
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            rows = self._load_history_rows(db_path)
        except sqlite3.DatabaseError as exc:
            from aetherlab.core.sqlite_recovery import (
                is_sqlite_corruption,
                quarantine_sqlite,
            )

            if not is_sqlite_corruption(exc):
                raise
            quarantine_sqlite(db_path)
            rows = self._load_history_rows(db_path)
        for prompt, cache_key, scene_status, num_refs, created_at in reversed(rows):
            self._add_entry_ui(prompt, cache_key, scene_status, num_refs, created_at)

    def _load_history_rows(self, db_path: Path) -> list[tuple]:
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
        return rows

    def add_entry(self, prompt: str, cache_key: str, scene_status: str, num_refs: int) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._add_entry_ui(prompt, cache_key, scene_status, num_refs, ts)
        # Persist to SQLite
        if self._db_path:
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
        item.setToolTip(self._COPY[self._language]["rerun"])

        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(14, 8, 14, 8)
        row_layout.setSpacing(12)
        row_layout.addWidget(icons.icon_label(
            "check-circle" if ok else "x-circle", 16,
            "#26725C" if ok else "#AC4055",
        ))
        text_col = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        prompt_label = QtWidgets.QLabel(prompt[:96])
        prompt_label.setStyleSheet(
            "color: #18283D; font-size: 13px; background: transparent;")
        text_layout.addWidget(prompt_label)
        meta = QtWidgets.QLabel(f"{ts} · {num_refs} refs · {cache_key[:12]}")
        meta.setStyleSheet(
            "color: #65758A; font-size: 10.5px; "
            "font-family: 'Cascadia Code', monospace; background: transparent;")
        text_layout.addWidget(meta)
        row_layout.addWidget(text_col, 1)
        row_layout.addWidget(icons.icon_label("rotate-cw", 14, "#65758A"))

        item.setSizeHint(row.sizeHint())
        self._list.insertItem(0, item)
        self._list.setItemWidget(item, row)
        self._entries.insert(0, prompt)
        self._update_count()

    def _on_double_click(self, item: QtWidgets.QListWidgetItem) -> None:
        prompt = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if prompt:
            self.prompt_selected.emit(str(prompt))

    def _clear(self) -> None:
        self._list.clear()
        self._entries.clear()
        self._update_count()
        if self._db_path:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute("DELETE FROM history")
                conn.commit()
            finally:
                conn.close()
