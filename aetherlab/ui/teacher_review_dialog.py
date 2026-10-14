"""Local-only review screen for school mock results and camera flags."""

from __future__ import annotations

from aetherlab.core.language import normalize_language
from aetherlab.services.student_profiles import StudentProfile, StudentProfileStore
from aetherlab.services.teacher_review import LocalMockReviewEntry, local_school_mock_review
from aetherlab.ui.qt_compat import QtCore, QtWidgets, require_qt
from aetherlab.ui.style import AETHERLAB_QSS

require_qt()

_COPY = {
    "kk": {
        "title": "Сынақ нәтижелерін жергілікті қарау",
        "description": "Осы құрылғыда сақталған, мектеп ID-і бірдей профильдердің толық сынақтары.",
        "privacy": "Бұл экранға осы құрылғыны қолданатын кез келген адам кіре алады. Дерек серверге жіберілмейді. Камера белгілері тек тексеруге арналған сигналдар, олар көшірудің дәлелі емес және балға әсер етпейді.",
        "date": "Күні", "student": "Оқушы", "class": "Сынып", "score": "Ұпай", "camera": "Камера", "signals": "Белгілер",
        "events": "Таңдалған сынақтағы оқиғалар", "event_time": "Уақыты", "event_type": "Сигнал",
        "empty": "Ортақ мектеп ID-і бар толық сынақтар табылмады.", "select": "Оқиғаларын көру үшін сынақты таңдаңыз.",
        "load_error": "Профильдерді оқу мүмкін болмады. Бұрын жүктелген деректер көрсетіледі; жаңартып көріңіз.", "reload": "Жаңарту",
        "enabled": "Қосулы", "disabled": "Қосылмаған", "unknown": "Дерек жоқ", "none": "Сигнал жоқ", "count": "{count} сигнал",
        "face_not_visible": "Бет камерада көрінбеді", "multiple_faces": "Кадрда бірнеше бет байқалды", "camera_unavailable": "Камера қолжетімсіз", "camera_lost": "Камера байланысы үзілді", "app_focus_lost": "Қолданба фокустан шықты", "close": "Жабу",
    },
    "ru": {
        "title": "Локальная проверка пробников",
        "description": "Полные пробники профилей с тем же ID школы, сохранённые на этом устройстве.",
        "privacy": "Экран доступен всем, кто пользуется этим устройством. Данные не отправляются на сервер. Флаги камеры — только сигналы для проверки, не доказательство списывания; на балл они не влияют.",
        "date": "Дата", "student": "Ученик", "class": "Класс", "score": "Баллы", "camera": "Камера", "signals": "Сигналы",
        "events": "События выбранного пробника", "event_time": "Время", "event_type": "Сигнал",
        "empty": "Полных пробников с общим ID школы пока нет.", "select": "Выберите пробник, чтобы увидеть события.",
        "load_error": "Не удалось прочитать профили. Показаны ранее загруженные данные; попробуйте обновить.", "reload": "Обновить",
        "enabled": "Включена", "disabled": "Не включалась", "unknown": "Нет данных", "none": "Нет сигналов", "count": "Сигналов: {count}",
        "face_not_visible": "Лицо не видно в кадре", "multiple_faces": "В кадре замечено несколько лиц", "camera_unavailable": "Камера недоступна", "camera_lost": "Связь с камерой потеряна", "app_focus_lost": "Приложение потеряло фокус", "close": "Закрыть",
    },
    "en": {
        "title": "Local mock review",
        "description": "Full mock exams saved on this device for profiles with the same school ID.",
        "privacy": "Anyone using this device can open this screen. Data is not sent to a server. Camera flags are review signals, not proof of cheating, and never affect scores.",
        "date": "Date", "student": "Student", "class": "Class", "score": "Score", "camera": "Camera", "signals": "Signals",
        "events": "Events in the selected mock", "event_time": "Time", "event_type": "Signal",
        "empty": "No full mocks for a shared school ID were found.", "select": "Select a mock to view its events.",
        "load_error": "Could not read profiles. Any previously loaded data is retained; please reload.", "reload": "Reload",
        "enabled": "Enabled", "disabled": "Not enabled", "unknown": "No data", "none": "No signals", "count": "{count} signal(s)",
        "face_not_visible": "Face not visible in frame", "multiple_faces": "Multiple faces observed", "camera_unavailable": "Camera unavailable", "camera_lost": "Camera connection lost", "app_focus_lost": "App lost focus", "close": "Close",
    },
}


class TeacherReviewDialog(QtWidgets.QDialog):
    """Review local full mock summaries and non-judgmental camera signals."""

    def __init__(
        self,
        profile_store: StudentProfileStore,
        profile: StudentProfile,
        language: str = "kk",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.language = normalize_language(language, "kk")
        self.text = _COPY[self.language]
        self.profile_store = profile_store
        self.entries: list[LocalMockReviewEntry] = []
        self._load_error = False
        self.setObjectName("TeacherReviewDialog")
        self.setStyleSheet(AETHERLAB_QSS)
        self.setWindowTitle(self.text["title"])
        self.setMinimumSize(900, 620)
        self.resize(1080, 700)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(11)
        title = QtWidgets.QLabel(self.text["title"])
        title.setStyleSheet("font-size:22px; font-weight:700; color:#18283D;")
        root.addWidget(title)
        description = QtWidgets.QLabel(self.text["description"])
        description.setWordWrap(True)
        description.setStyleSheet("color:#65758A; font-size:12px;")
        root.addWidget(description)
        privacy = QtWidgets.QLabel(self.text["privacy"])
        privacy.setWordWrap(True)
        privacy.setStyleSheet(
            "color:#53647A; background:#E9EFF7; border:1px solid #D8E1EC; "
            "border-radius:8px; padding:9px 11px; font-size:11px;"
        )
        root.addWidget(privacy)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setObjectName("TeacherReviewTable")
        self.table.setHorizontalHeaderLabels([
            self.text["date"], self.text["student"], self.text["class"],
            self.text["score"], self.text["camera"], self.text["signals"],
        ])
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        root.addWidget(self.table, 3)

        event_title = QtWidgets.QLabel(self.text["events"])
        event_title.setStyleSheet("font-size:14px; font-weight:700; color:#18283D;")
        root.addWidget(event_title)
        self.events_table = QtWidgets.QTableWidget(0, 2)
        self.events_table.setObjectName("TeacherReviewEvents")
        self.events_table.setHorizontalHeaderLabels([self.text["event_time"], self.text["event_type"]])
        self.events_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.events_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.events_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.events_table.setMaximumHeight(160)
        root.addWidget(self.events_table)

        close = QtWidgets.QPushButton(self.text["close"])
        close.setObjectName("SecondaryButton")
        close.clicked.connect(self.accept)
        actions = QtWidgets.QHBoxLayout()
        self.reload_button = QtWidgets.QPushButton(self.text["reload"])
        self.reload_button.setObjectName("SecondaryButton")
        self.reload_button.clicked.connect(self._reload)
        actions.addWidget(self.reload_button)
        actions.addStretch(1)
        actions.addWidget(close)
        root.addLayout(actions)
        self._reload()

    def _reload(self) -> bool:
        try:
            entries = local_school_mock_review(self.profile_store.list_profiles(), self.profile.school_id)
        except (OSError, UnicodeError):
            self._load_error = True
            self.status.setText(self.text["load_error"])
            if not self.entries:
                self._render()
            return False
        self._load_error = False
        self.entries = entries
        self.status.clear()
        self._render()
        return True

    def _camera_status(self, entry: LocalMockReviewEntry) -> str:
        if entry.proctor_enabled is None:
            return self.text["unknown"]
        return self.text["enabled"] if entry.proctor_enabled else self.text["disabled"]

    def _render(self) -> None:
        self.table.clearSpans()
        self.events_table.clearSpans()
        self.table.clearSelection()
        self.table.setRowCount(len(self.entries) or 1)
        if not self.entries:
            self.table.setSpan(0, 0, 1, 6)
            key = "load_error" if self._load_error else "empty"
            self.table.setItem(0, 0, QtWidgets.QTableWidgetItem(self.text[key]))
            self.events_table.setRowCount(1)
            self.events_table.setSpan(0, 0, 1, 2)
            self.events_table.setItem(0, 0, QtWidgets.QTableWidgetItem(self.text["select"]))
            return
        for row, entry in enumerate(self.entries):
            stamp = self._format_date(entry.completed_at)
            signal_summary = self.text["count"].format(count=len(entry.integrity_events)) if entry.integrity_events else self.text["none"]
            values = (stamp, entry.student_name, entry.class_name or "—", f"{entry.score}/50", self._camera_status(entry), signal_summary)
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if column in {3, 4, 5}:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 36)
        self.table.selectRow(0)

    @staticmethod
    def _format_date(value: str) -> str:
        try:
            parsed = QtCore.QDateTime.fromString(value, QtCore.Qt.DateFormat.ISODateWithMs)
            if not parsed.isValid():
                parsed = QtCore.QDateTime.fromString(value, QtCore.Qt.DateFormat.ISODate)
            return parsed.toLocalTime().toString("yyyy-MM-dd HH:mm") if parsed.isValid() else (value or "—")
        except (AttributeError, TypeError):
            return value or "—"

    def _selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            self.events_table.clearSpans()
            self.events_table.setRowCount(1)
            self.events_table.setSpan(0, 0, 1, 2)
            self.events_table.setItem(0, 0, QtWidgets.QTableWidgetItem(self.text["select"]))
            return
        events = self.entries[row].integrity_events
        self.events_table.clearSpans()
        self.events_table.setRowCount(len(events) or 1)
        if not events:
            self.events_table.setSpan(0, 0, 1, 2)
            self.events_table.setItem(0, 0, QtWidgets.QTableWidgetItem(self.text["none"]))
            return
        for index, (event_type, event_at) in enumerate(events):
            self.events_table.setItem(index, 0, QtWidgets.QTableWidgetItem(self._format_date(event_at)))
            self.events_table.setItem(index, 1, QtWidgets.QTableWidgetItem(self.text[event_type]))
