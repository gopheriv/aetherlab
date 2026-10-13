"""Picker for the three profile-owned study companions."""

from __future__ import annotations

from aetherlab.core.language import normalize_language
from aetherlab.services.gamification import COMPANION_IDS, companion_progress
from aetherlab.ui.fonts import install_ui_fonts
from aetherlab.ui.qt_compat import QtCore, QtWidgets, require_qt
from aetherlab.ui.study_visuals import CompanionArt

require_qt()


_COPY = {
    "kk": {
        "title": "Физика компаньонын таңда",
        "description": "Бір компаньонды таңда. Ол сен жинаған ұпаймен бірге дамиды.",
        "level": "Қазір: {level}-деңгей · {points} ұпай",
        "names": {"quantum": "Квант", "photon": "Фотон", "lab_bot": "Зертхана боты"},
        "descriptions": {
            "quantum": "Кішкентай кванттық бөлшек",
            "photon": "Жарықтан туған кристалл",
            "lab_bot": "Зертханадағы көмекшің",
        },
        "choose": "Осыны таңдау",
        "selected": "Таңдалды",
        "confirm": "Таңдауды сақтау",
        "cancel": "Болдырмау",
        "rule": "50 ұпай — өсу · 150 ұпай — жаңа пішін",
    },
    "ru": {
        "title": "Выбери компаньона",
        "description": "Выбери помощника по физике. Он будет развиваться вместе с твоими очками.",
        "level": "Сейчас: уровень {level} · {points} очков",
        "names": {"quantum": "Квант", "photon": "Фотон", "lab_bot": "Лаб-бот"},
        "descriptions": {
            "quantum": "Любопытная квантовая частица",
            "photon": "Световой кристалл",
            "lab_bot": "Помощник лаборатории",
        },
        "choose": "Выбрать",
        "selected": "Выбран",
        "confirm": "Сохранить выбор",
        "cancel": "Отмена",
        "rule": "50 очков — рост · 150 очков — новая форма",
    },
    "en": {
        "title": "Choose a physics companion",
        "description": "Choose a study companion. It develops as you earn practice points.",
        "level": "Now: level {level} · {points} points",
        "names": {"quantum": "Quantum", "photon": "Photon", "lab_bot": "Lab bot"},
        "descriptions": {
            "quantum": "A curious quantum particle",
            "photon": "A gentle light crystal",
            "lab_bot": "A friendly lab assistant",
        },
        "choose": "Choose this companion",
        "selected": "Selected",
        "confirm": "Save choice",
        "cancel": "Cancel",
        "rule": "50 points — grow · 150 points — new form",
    },
}


class _CompanionChoiceCard(QtWidgets.QFrame):
    """Make the whole preview card selectable while keeping its button usable."""

    clicked = QtCore.pyqtSignal(str)

    def __init__(self, companion_id: str) -> None:
        super().__init__()
        self.companion_id = companion_id
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self.companion_id)
        super().mouseReleaseEvent(event)


class CompanionPickerDialog(QtWidgets.QDialog):
    """Let a learner select one of three physics companions."""

    def __init__(
        self,
        selected_pet: str | None = None,
        points: int = 0,
        language: str = "ru",
        parent=None,
        *,
        selected_companion: str | None = None,
    ) -> None:
        super().__init__(parent)
        install_ui_fonts()
        self.language = normalize_language(language, "ru")
        self.text = _COPY[self.language]
        self.points = max(0, int(points))
        requested = selected_companion if selected_companion is not None else selected_pet
        self.selected_companion = requested if requested in COMPANION_IDS else None
        self._choice_buttons: dict[str, QtWidgets.QPushButton] = {}
        self._cards: dict[str, QtWidgets.QFrame] = {}
        self._art: dict[str, CompanionArt] = {}
        self._build()

    def _build(self) -> None:
        text = self.text
        progress = companion_progress(self.points)
        self.setObjectName("CompanionPickerDialog")
        self.setWindowTitle(text["title"])
        self.setMinimumSize(760, 510)
        self.setStyleSheet("QDialog#CompanionPickerDialog { background:#F4F7FB; }")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(9)
        title = QtWidgets.QLabel(text["title"])
        title.setStyleSheet("color:#18283D; font-size:23px; font-weight:700;")
        layout.addWidget(title)
        description = QtWidgets.QLabel(text["description"])
        description.setWordWrap(True)
        description.setStyleSheet("color:#65758A; font-size:12px;")
        layout.addWidget(description)

        companion_row = QtWidgets.QHBoxLayout()
        companion_row.setSpacing(12)
        for companion_id in COMPANION_IDS:
            card = _CompanionChoiceCard(companion_id)
            card.setObjectName("CompanionChoiceCard")
            card.setFixedHeight(316)
            card.clicked.connect(self._select_companion)
            self._cards[companion_id] = card
            box = QtWidgets.QVBoxLayout(card)
            box.setContentsMargins(10, 10, 10, 12)
            box.setSpacing(5)
            art = CompanionArt(companion_id=companion_id, stage=progress.stage)
            art.setFixedSize(166, 136)
            self._art[companion_id] = art
            box.addWidget(art, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
            name = QtWidgets.QLabel(text["names"][companion_id])
            name.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            name.setStyleSheet("color:#18283D; font-size:14px; font-weight:700;")
            box.addWidget(name)
            hint = QtWidgets.QLabel(text["descriptions"][companion_id])
            hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#65758A; font-size:11px;")
            box.addWidget(hint)
            level = QtWidgets.QLabel(
                text["level"].format(level=progress.level, points=progress.points)
            )
            level.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            level.setStyleSheet("color:#486A91; font-size:11px; font-weight:600;")
            box.addWidget(level)
            choose = QtWidgets.QPushButton(text["choose"])
            choose.setCheckable(True)
            choose.setMinimumHeight(40)
            choose.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            choose.clicked.connect(
                lambda _checked=False, value=companion_id: self._select_companion(value)
            )
            box.addWidget(choose)
            self._choice_buttons[companion_id] = choose
            companion_row.addWidget(card, 1, QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addLayout(companion_row)
        layout.addStretch(1)

        rule = QtWidgets.QLabel(text["rule"])
        rule.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        rule.setStyleSheet("color:#65758A; font-size:10px;")
        layout.addWidget(rule)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        cancel = QtWidgets.QPushButton(text["cancel"])
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.confirm_button = QtWidgets.QPushButton(text["confirm"])
        self.confirm_button.setMinimumHeight(38)
        self.confirm_button.setStyleSheet(
            "QPushButton { background:#486A91; color:#FFFFFF; border:0; "
            "border-radius:9px; padding:8px 16px; font-weight:700; }"
            "QPushButton:hover { background:#3B587A; }"
        )
        self.confirm_button.clicked.connect(self.accept)
        footer.addWidget(self.confirm_button)
        layout.addLayout(footer)
        self._update_selection()

    @property
    def selected_pet(self) -> str | None:
        """Compatibility alias for earlier pet-picker builds."""
        return self.selected_companion

    @property
    def selected_companion_id(self) -> str | None:
        return self.selected_companion

    def _select_companion(self, companion_id: str) -> None:
        self.selected_companion = (
            companion_id if companion_id in COMPANION_IDS else None
        )
        self._update_selection()

    _select_pet = _select_companion

    def _update_selection(self) -> None:
        for companion_id, button in self._choice_buttons.items():
            selected = companion_id == self.selected_companion
            button.setChecked(selected)
            button.setText(self.text["selected"] if selected else self.text["choose"])
            paper = self._art[companion_id].background_color()
            self._cards[companion_id].setStyleSheet(
                f"QFrame#CompanionChoiceCard {{ background:{paper}; "
                f"border:2px solid {'#486A91' if selected else '#D8E1EC'}; "
                "border-radius:16px; }"
            )
        self.confirm_button.setEnabled(self.selected_companion is not None)
