"""Reusable shell primitives: loading, empty, title, toast, and backdrop widgets."""

from __future__ import annotations

import math

from aetherlab.ui import icons
from aetherlab.ui.command_bar import EXAMPLE_PROMPTS
from aetherlab.ui.profile_avatar import ProfileAvatarButton
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt

require_qt()

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
        painter.fillRect(rect, QtGui.QColor("#F4F7FB"))

        cx, cy = rect.width() // 2, rect.height() // 2

        # Subtle grid
        grid_pen = QtGui.QPen(QtGui.QColor("#EEECF4"), 1)
        painter.setPen(grid_pen)
        for x in range(0, rect.width(), 48):
            painter.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), 48):
            painter.drawLine(0, y, rect.width(), y)

        # Crosshair axes
        accent_pen = QtGui.QPen(QtGui.QColor("#E9EFF7"), 1)
        accent_pen.setStyle(QtCore.Qt.PenStyle.DotLine)
        painter.setPen(accent_pen)
        painter.drawLine(cx, 0, cx, rect.height())
        painter.drawLine(0, cy, rect.width(), cy)

        # Concentric rings
        for i, radius in enumerate([40, 80, 120, 160, 200]):
            opacity = max(0.08, 0.25 - i * 0.04)
            color = QtGui.QColor("#486A91")
            color.setAlphaF(opacity)
            painter.setPen(QtGui.QPen(color, 1))
            painter.drawEllipse(QtCore.QPoint(cx, cy), radius, radius)

        # Primary rotating arc
        arc_pen = QtGui.QPen(QtGui.QColor("#486A91"), 3)
        arc_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(cx - 35, cy - 35, 70, 70, int(self._angle * 16), 100 * 16)

        # Counter-rotating secondary arc
        arc_pen2 = QtGui.QPen(QtGui.QColor("#26725C"), 2)
        arc_pen2.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen2)
        painter.drawArc(cx - 55, cy - 55, 110, 110, int(-self._angle * 16), 80 * 16)

        # Orbiting dots
        for radius, speed, color_hex, dot_r in [
            (80, 1.0, "#486A91", 4),
            (120, -0.7, "#26725C", 3),
            (160, 0.5, "#536F90", 3),
        ]:
            angle_rad = math.radians(self._angle * speed)
            ox = cx + radius * math.cos(angle_rad)
            oy = cy + radius * math.sin(angle_rad)
            painter.setBrush(QtGui.QColor(color_hex))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawEllipse(QtCore.QPoint(int(ox), int(oy)), dot_r, dot_r)

        # Center dot with glow
        glow = QtGui.QRadialGradient(float(cx), float(cy), 16)
        glow.setColorAt(0, QtGui.QColor("#486A9140"))
        glow.setColorAt(1, QtGui.QColor("#00000000"))
        painter.fillRect(cx - 16, cy - 16, 32, 32, glow)
        painter.setBrush(QtGui.QColor("#486A91"))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(QtCore.QPoint(cx, cy), 5, 5)

def _copy_to_clipboard(text: str) -> None:
    clipboard = QtWidgets.QApplication.clipboard()
    if clipboard:
        clipboard.setText(text)

class TitleBar(QtWidgets.QWidget):
    """Page header with persistent language and settings controls."""

    settings_requested = QtCore.pyqtSignal()
    language_changed = QtCore.pyqtSignal(str)
    profile_requested = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedHeight(68)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 22, 0)
        layout.setSpacing(10)

        brand = QtWidgets.QLabel("physlab")
        brand.setStyleSheet("color:#18283D; font-size:22px; font-weight:800; letter-spacing:-1px;")
        layout.addWidget(brand)
        divider = QtWidgets.QLabel("/")
        divider.setStyleSheet("color:#A5B6CB; font-size:22px; padding:0 12px;")
        layout.addWidget(divider)
        self.page_title = QtWidgets.QLabel("Home")
        self.page_title.setObjectName("TitleWordmark")
        layout.addWidget(self.page_title)
        layout.addStretch()

        self.subject_badge = QtWidgets.QLabel("UNT · Physics")
        self.subject_badge.setStyleSheet("background:#E9EFF7; color:#3B587A; border-radius:10px; padding:7px 12px; font-size:11px; font-weight:600;")
        layout.addWidget(self.subject_badge, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.setObjectName("HeaderLanguageCombo")
        self.language_combo.addItem("Қазақша", "kk")
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.addItem("English", "en")
        self.language_combo.setFixedWidth(112)
        self.language_combo.setToolTip("Language / Тіл / Язык")
        self.language_combo.currentIndexChanged.connect(
            lambda index: self.language_changed.emit(
                str(self.language_combo.itemData(index) or "kk")
            )
        )
        layout.addWidget(self.language_combo)

        self._settings_btn = QtWidgets.QToolButton()
        self._settings_btn.setObjectName("TitleIconButton")
        self._settings_btn.setIcon(icons.icon("settings", 16, "#65758A"))
        self._settings_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self._settings_btn)
        self.profile_button = ProfileAvatarButton(size=42)
        self.profile_button.clicked.connect(self.profile_requested.emit)
        layout.addWidget(self.profile_button)

    def set_language(self, language: str) -> None:
        self.subject_badge.setText({"kk":"ҰБТ · Физика", "ru":"ЕНТ · Физика", "en":"UNT · Physics"}.get(language,"UNT · Physics"))
        self._settings_btn.setToolTip({"kk":"Баптаулар", "ru":"Настройки", "en":"Settings"}.get(language, "Settings"))
        self.language_combo.setToolTip({"kk":"Тіл", "ru":"Язык", "en":"Language"}.get(language, "Language"))
        self.profile_button.set_profile(
            self.profile_button.name,
            self.profile_button.avatar_path,
            {"kk": "Профильді ашу", "ru": "Открыть профиль", "en": "Open profile"}.get(language, "Open profile"),
        )
        index = self.language_combo.findData(language)
        if index >= 0 and index != self.language_combo.currentIndex():
            self.language_combo.setCurrentIndex(index)

    def set_page_title(self, title: str) -> None:
        self.page_title.setText(title)

    def set_profile(self, name: str, avatar_path: str = "") -> None:
        self.profile_button.set_profile(name, avatar_path, self.profile_button.toolTip())

class Toast(QtWidgets.QFrame):
    """Inline kind-colored banner: icon, message, optional Details, dismiss."""

    details_requested = QtCore.pyqtSignal()

    _KINDS = {
        "error": ("#AC4055", "rgba(251, 113, 133, 0.10)", "alert-triangle"),
        "warning": ("#8A5A24", "rgba(251, 191, 36, 0.10)", "alert-circle"),
        "success": ("#26725C", "rgba(52, 211, 153, 0.10)", "check-circle"),
        "info": ("#486A91", "rgba(75, 99, 133, 0.10)", "info"),
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
            "color: #18283D; font-size: 12.5px; font-weight: 500; "
            "background: transparent; border: none;"
        )
        layout.addWidget(self._message, 1)

        self._details_btn = QtWidgets.QPushButton()
        self._details_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._details_btn.clicked.connect(self.details_requested.emit)
        layout.addWidget(self._details_btn)

        dismiss = QtWidgets.QPushButton()
        dismiss.setIcon(icons.icon("x", 13, "#65758A"))
        dismiss.setFixedSize(22, 22)
        dismiss.setStyleSheet("background: transparent; border: none;")
        dismiss.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        dismiss.clicked.connect(self.hide)
        layout.addWidget(dismiss, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        self.hide()

    def set_language(self, language: str) -> None:
        self._details_btn.setText({"kk": "Толығырақ", "ru": "Подробнее", "en": "Details"}.get(language, "Details"))

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

_EMPTY_STATE_COPY = {
    "kk": {
        "headline": "Физиканы бірге түсінейік.",
        "subtitle": "Физика не математика есебін енгізіңіз немесе мысалды таңдаңыз.",
        "examples": ("Өшетін тербеліс", "Қарапайым маятник", "Кеплер орбитасы"),
        "ent_title": "ҰБТ · Физика",
        "ent_caption": "100 жаттығу · сынақ: 40",
        "ent_tooltip": "25 тақырып · 100 жаттығу және 40 сұрақтық сынақ · қазақша, орысша және ағылшынша",
        "practice": "Жаттығуды бастау",
        "no_api": "API кілті бапталмаған",
        "settings": "Баптаулар",
        "local_ai": "Ollama арқылы жергілікті ЖИ",
        "no_books": "Оқулықтар әлі индекстелмеген",
        "library_count": "Оқулық: {count}",
        "add_books": "Оқулық қосу",
        "model": "Модель: {model}",
        "ollama": "Ollama табылды · {count} жергілікті модель дайын",
    },
    "ru": {
        "headline": "Разберёмся в физике вместе.",
        "subtitle": "Задайте вопрос по физике или математике либо выберите пример.",
        "examples": ("Затухающие колебания", "Простой маятник", "Орбита Кеплера"),
        "ent_title": "ЕНТ · Физика",
        "ent_caption": "100 упражнений · пробник: 40",
        "ent_tooltip": "25 тем · 100 упражнений и пробник на 40 заданий · казахский, русский и английский языки",
        "practice": "Начать тренировку",
        "no_api": "API-ключ не настроен",
        "settings": "Настройки",
        "local_ai": "Локальный AI (Ollama)",
        "no_books": "Учебники ещё не индексированы",
        "library_count": "Учебников: {count}",
        "add_books": "Добавить",
        "model": "Модель: {model}",
        "ollama": "Ollama обнаружена · готово локальных моделей: {count}",
    },
    "en": {
        "headline": "Make physics make sense.",
        "subtitle": "Type a physics or math prompt below, or start from an example.",
        "examples": ("Damped oscillator", "Simple pendulum", "Kepler orbit"),
        "ent_title": "UNT · Physics",
        "ent_caption": "100 exercises · mock: 40",
        "ent_tooltip": "25 topics · 100 exercises plus a 40-question mock · Kazakh, Russian, and English",
        "practice": "Open practice",
        "no_api": "No API key configured",
        "settings": "Open Settings",
        "local_ai": "Use local AI (Ollama)",
        "no_books": "No books indexed",
        "library_count": "{count} books",
        "add_books": "Add textbooks",
        "model": "Model: {model}",
        "ollama": "Ollama detected · {count} local model{plural} ready",
    },
}


class _ElidedLabel(QtWidgets.QLabel):
    """Keep a full tooltip while fitting one-line status text to its slot."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""

    def set_full_text(self, text: str) -> None:
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._fit_text()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_text()

    def _fit_text(self) -> None:
        visible = self.fontMetrics().elidedText(
            self._full_text,
            QtCore.Qt.TextElideMode.ElideRight,
            max(0, self.contentsRect().width()),
        )
        super().setText(visible)


class EmptyStateView(QtWidgets.QWidget):
    """Focused home screen for starting a physics task or UNT practice."""

    example_picked = QtCore.pyqtSignal(str)
    settings_requested = QtCore.pyqtSignal()
    library_requested = QtCore.pyqtSignal()
    ollama_requested = QtCore.pyqtSignal()
    ent_requested = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._language = "en"
        self._has_api_key = False
        self._model = ""
        self._library_count = 0
        self._ollama_count = 0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 20)
        layout.setSpacing(17)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        eyebrow = QtWidgets.QLabel("AI TUTOR")
        self._eyebrow = eyebrow
        eyebrow.setStyleSheet("color:#486A91; font-size:11px; font-weight:700; letter-spacing:2px;")
        layout.addWidget(eyebrow)

        self._headline = QtWidgets.QLabel()
        self._headline.setObjectName("EmptyStateHeadline")
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self._headline.setWordWrap(True)
        layout.addWidget(self._headline)

        self._subtitle = QtWidgets.QLabel()
        self._subtitle.setObjectName("EmptyStateSubtitle")
        self._subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

        chips_row = QtWidgets.QWidget()
        self._examples_widget = chips_row
        chips_layout = QtWidgets.QGridLayout(chips_row)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(9)
        self._examples_layout = chips_layout
        self._example_buttons: list[QtWidgets.QPushButton] = []
        self._example_columns = 0
        for example in EXAMPLE_PROMPTS[:3]:
            chip = QtWidgets.QPushButton()
            chip.setObjectName("ExampleChip")
            chip.setToolTip(example)
            chip.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(
                lambda checked=False, prompt=example: self.example_picked.emit(prompt)
            )
            chips_layout.addWidget(chip)
            self._example_buttons.append(chip)
        layout.addWidget(chips_row)

        self._ent_card = QtWidgets.QFrame()
        self._ent_card.setObjectName("ENTLaunchCard")
        self._ent_card.setMinimumWidth(0)
        self._ent_card.setMaximumWidth(16777215)
        self._ent_card.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        ent_layout = QtWidgets.QHBoxLayout(self._ent_card)
        ent_layout.setContentsMargins(16, 10, 14, 10)
        ent_layout.setSpacing(12)

        ent_mark = QtWidgets.QLabel()
        ent_mark.setObjectName("ENTLaunchMark")
        ent_mark.setPixmap(icons.icon_pixmap("atom", 24, "#486A91"))
        ent_mark.setFixedSize(38, 38)
        ent_mark.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        ent_layout.addWidget(ent_mark)

        ent_copy = QtWidgets.QVBoxLayout()
        ent_copy.setContentsMargins(0, 0, 0, 0)
        ent_copy.setSpacing(2)
        self._ent_title = QtWidgets.QLabel()
        self._ent_title.setObjectName("ENTLaunchTitle")
        self._ent_title.setMinimumHeight(18)
        self._ent_subtitle = QtWidgets.QLabel()
        self._ent_subtitle.setObjectName("ENTLaunchSubtitle")
        self._ent_subtitle.setWordWrap(False)
        self._ent_subtitle.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._ent_subtitle.setMinimumHeight(16)
        ent_copy.addWidget(self._ent_title)
        ent_copy.addWidget(self._ent_subtitle)
        ent_layout.addLayout(ent_copy, 1)

        self._ent_button = QtWidgets.QPushButton()
        self._ent_button.setObjectName("ENTPracticeButton")
        self._ent_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._ent_button.setMinimumSize(112, 38)
        self._ent_button.clicked.connect(self.ent_requested.emit)
        ent_layout.addWidget(self._ent_button)
        layout.addWidget(self._ent_card)

        self._setup_strip = QtWidgets.QFrame()
        self._setup_strip.setObjectName("SetupStrip")
        self._setup_strip.setStyleSheet(
            "QFrame#SetupStrip { background-color: #FFFFFF; border: 1px solid #D8E1EC; "
            "border-radius: 12px; }"
            "QLabel, QPushButton { border: none; background: transparent; }"
        )
        self._setup_strip.setMinimumWidth(0)
        self._setup_strip.setMaximumWidth(16777215)
        self._setup_strip.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        strip_layout = QtWidgets.QGridLayout(self._setup_strip)
        strip_layout.setContentsMargins(16, 10, 16, 10)
        strip_layout.setSpacing(12)
        self._status_layout = strip_layout
        self._status_columns = 0
        self._provider_group = QtWidgets.QWidget(self._setup_strip)
        provider_layout = QtWidgets.QHBoxLayout(self._provider_group)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        provider_layout.setSpacing(10)
        self._library_group = QtWidgets.QWidget(self._setup_strip)
        library_layout = QtWidgets.QHBoxLayout(self._library_group)
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_layout.setSpacing(10)

        self._key_icon = icons.icon_label("key-round", 16, "#8A5A24")
        provider_layout.addWidget(self._key_icon)
        self._key_label = _ElidedLabel()
        self._key_label.setMinimumWidth(0)
        self._key_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self._key_label.setStyleSheet("color: #53647A; font-size: 12.5px;")
        provider_layout.addWidget(self._key_label, 1)
        self._key_btn = QtWidgets.QPushButton()
        self._key_btn.setStyleSheet("color: #335F92; font-size: 12.5px; font-weight: 600;")
        self._key_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._key_btn.clicked.connect(self.settings_requested.emit)
        provider_layout.addWidget(self._key_btn)

        self._ollama_btn = QtWidgets.QPushButton()
        self._ollama_btn.setStyleSheet(
            "color: #26725C; font-size: 12.5px; font-weight: 600;"
        )
        self._ollama_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._ollama_btn.clicked.connect(self.ollama_requested.emit)
        self._ollama_btn.hide()
        provider_layout.addWidget(self._ollama_btn)

        library_layout.addWidget(icons.icon_label("library", 16, "#8A5A24"))
        self._lib_label = _ElidedLabel()
        self._lib_label.setMinimumWidth(0)
        self._lib_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self._lib_label.setStyleSheet("color: #53647A; font-size: 12.5px;")
        library_layout.addWidget(self._lib_label, 1)
        self._lib_btn = QtWidgets.QPushButton()
        self._lib_btn.setStyleSheet("color: #335F92; font-size: 12.5px; font-weight: 600;")
        self._lib_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._lib_btn.clicked.connect(self.library_requested.emit)
        library_layout.addWidget(self._lib_btn)

        layout.addStretch(1)
        layout.addWidget(self._setup_strip)
        self.set_language("en")
        self._apply_responsive_layout(columns=2)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self, columns: int | None = None) -> None:
        narrow = self.width() < 660
        self.layout().setSpacing(10 if narrow else 17)
        self.layout().setContentsMargins(28 if narrow else 36, 20 if narrow else 28,
                                        28 if narrow else 36, 16 if narrow else 20)
        if self._headline.property("compact") != narrow:
            self._headline.setProperty("compact", narrow)
            self._headline.style().unpolish(self._headline)
            self._headline.style().polish(self._headline)
            self._headline.updateGeometry()
        status_columns = 1 if self.width() < 740 else 2
        if status_columns != self._status_columns:
            while self._status_layout.count():
                self._status_layout.takeAt(0)
            self._status_layout.addWidget(self._provider_group, 0, 0)
            self._status_layout.addWidget(self._library_group, 0 if status_columns == 2 else 1,
                                          1 if status_columns == 2 else 0)
            self._status_layout.setColumnStretch(0, 1)
            self._status_layout.setColumnStretch(1, 1 if status_columns == 2 else 0)
            self._status_columns = status_columns
        columns = columns or (2 if self.width() < 660 else 3)
        if self._language == "ru" and self.width() < 740:
            columns = 1
        for button in self._example_buttons:
            compact = columns == 1
            if button.property("compact") != compact:
                button.setProperty("compact", compact)
                button.style().unpolish(button)
                button.style().polish(button)
                button.updateGeometry()
        if columns == self._example_columns:
            return
        while self._examples_layout.count():
            self._examples_layout.takeAt(0)
        for index, button in enumerate(self._example_buttons):
            if columns == 2 and index == 2:
                self._examples_layout.addWidget(
                    button, 1, 0, 1, 2
                )
            else:
                self._examples_layout.addWidget(
                    button, index // columns, index % columns,
                )
        for column in range(max(3, self._example_columns, columns)):
            self._examples_layout.setColumnStretch(column, 1 if column < columns else 0)
        self._examples_layout.invalidate()
        self._examples_widget.setMinimumHeight(self._examples_layout.minimumSize().height())
        self._example_columns = columns

    def _copy(self) -> dict[str, object]:
        return _EMPTY_STATE_COPY.get(self._language, _EMPTY_STATE_COPY["en"])

    @staticmethod
    def _plural(count: int) -> str:
        return "" if count == 1 else "s"

    def set_language(self, language: str) -> None:
        self._language = language if language in _EMPTY_STATE_COPY else "en"
        self._eyebrow.setText({"kk":"AI КӨМЕКШІ", "ru":"AI РЕПЕТИТОР", "en":"AI TUTOR"}[self._language])
        copy = self._copy()
        self._headline.setText(str(copy["headline"]))
        self._subtitle.setText(str(copy["subtitle"]))
        for button, label in zip(self._example_buttons, copy["examples"]):
            button.setText(str(label))
        self._ent_title.setText(str(copy["ent_title"]))
        self._ent_subtitle.setText(str(copy["ent_caption"]))
        self._ent_subtitle.setToolTip(str(copy["ent_tooltip"]))
        self._ent_button.setText(str(copy["practice"]))
        self._key_btn.setText(str(copy["settings"]))
        self._ollama_btn.setText({"kk": "Жергілікті ЖИ", "ru": "Локальный AI", "en": "Local AI"}[self._language])
        self._ollama_btn.setToolTip(str(copy["local_ai"]))
        self._lib_btn.setText(str(copy["add_books"]))
        self._refresh_status_labels()
        self._apply_responsive_layout()

    def _refresh_status_labels(self) -> None:
        copy = self._copy()
        if self._has_api_key:
            self._key_icon.setPixmap(icons.icon_pixmap("check-circle", 16, "#26725C"))
            self._key_label.set_full_text(str(copy["model"]).format(model=self._model))
            self._ollama_btn.hide()
        elif self._ollama_count:
            self._key_icon.setPixmap(icons.icon_pixmap("check-circle", 16, "#26725C"))
            self._key_label.set_full_text(
                str(copy["ollama"]).format(
                    count=self._ollama_count, plural=self._plural(self._ollama_count)
                )
            )
            self._ollama_btn.show()
        else:
            self._key_icon.setPixmap(icons.icon_pixmap("key-round", 16, "#8A5A24"))
            self._key_label.set_full_text(str(copy["no_api"]))
            self._ollama_btn.hide()

        if self._library_count:
            self._lib_label.set_full_text(
                str(copy["library_count"]).format(
                    count=self._library_count,
                    plural=self._plural(self._library_count),
                )
            )
        else:
            self._lib_label.set_full_text(str(copy["no_books"]))

    def set_status(self, has_api_key: bool, model: str, library_count: int) -> None:
        self._has_api_key = bool(has_api_key)
        self._model = str(model or "")
        self._library_count = max(0, int(library_count or 0))
        if self._has_api_key:
            self._ollama_count = 0
        self._refresh_status_labels()

    def offer_ollama(self, model_count: int) -> None:
        """Show the one-click local-AI CTA when Ollama is available."""
        self._ollama_count = max(0, int(model_count or 0))
        self._refresh_status_labels()

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
        strip.setObjectName("RunningStatusStrip")
        strip_layout = QtWidgets.QVBoxLayout(strip)
        strip_layout.setContentsMargins(20, 8, 20, 24)
        strip_layout.setSpacing(4)

        self._headline = QtWidgets.QLabel("Working…")
        self._headline.setStyleSheet(
            "color: #18283D; font-size: 18px; font-weight: 600;"
        )
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        strip_layout.addWidget(self._headline)

        self._detail = QtWidgets.QLabel("")
        self._detail.setStyleSheet(
            "color: #65758A; font-size: 12px; font-family: 'Cascadia Code', monospace;"
        )
        self._detail.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        strip_layout.addWidget(self._detail)

        layout.addWidget(strip)

    def set_stage_text(self, headline: str, detail: str = "") -> None:
        self._headline.setText(headline)
        self._detail.setText(detail)

class BlueprintBackdrop(QtWidgets.QWidget):
    """A quiet graphite backdrop that keeps focus on study content."""

    def __init__(self, child: QtWidgets.QWidget, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BlueprintBackdrop")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(child)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("#F4F7FB"))
