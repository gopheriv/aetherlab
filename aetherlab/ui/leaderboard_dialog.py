"""Shared UNT full-mock leaderboard and score history."""

from __future__ import annotations

from aetherlab.core.language import normalize_language
from aetherlab.services.leaderboard_client import (
    LeaderboardError,
    LeaderboardSettingsStore,
    sync_school_leaderboard,
)
from aetherlab.services.school_leaderboard import SchoolLeaderboardEntry, school_leaderboard
from aetherlab.services.student_profiles import StudentProfile, StudentProfileStore
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt
from aetherlab.ui.style import AETHERLAB_QSS

require_qt()


_COPY = {
    "kk": {
        "title": "Мектеп рейтингі",
        "intro": "Мектеп ID-і бірдей оқушылар толық ҰБТ сынақтарындағы ұпайлар бойынша жарысады.",
        "endpoint": "Рейтинг сервері",
        "endpoint_placeholder": "https://school.example.kz",
        "save": "Сақтау",
        "sync": "Рейтингке қосылу және жаңарту",
        "local_review": "Сынақтарды жергілікті қарау",
        "close": "Жабу",
        "privacy": "Атыңыз, сыныбыңыз және толық сынақ ұпайлары жіберіледі. Мектеп ID-і топқа бөлу үшін қолданылады, серверде оның хэші ғана сақталады. Фото мен логин жіберілмейді. Әр құрылғыда бірдей username қолданыңыз.",
        "local_only": "Сервер қосылмаған: төменде осы құрылғыдағы профильдер ғана көрсетілген. Басқа құрылғыларды қосу үшін мектептің HTTPS сервер URL мекенжайын енгізіңіз.",
        "local_configured": "Сервер мекенжайы сақталған. Басқа құрылғылардың нәтижесін алу үшін «Рейтингке қосылу және жаңарту» батырмасын басыңыз.",
        "saved": "Сервер мекенжайы сақталды. Рейтингке қосылу үшін жаңарту батырмасын басыңыз.",
        "local_mode": "Сервер мекенжайы өшірілді. Жергілікті рейтинг көрсетіліп тұр.",
        "joined": "Рейтинг жаңартылды.",
        "needs_id": "Алдымен профильге ортақ мектеп ID-ін енгізіңіз.",
        "needs_username": "Құрылғылар арасында профильді сәйкестендіру үшін username енгізіңіз.",
        "bad_url": "Сервер мекенжайы жарамсыз. HTTPS қолданыңыз; HTTP тек жергілікті желіде қолжетімді.",
        "busy": "Рейтинг жаңартылып жатыр…",
        "network_error": "Серверге қосылмады немесе рейтингті жаңарту мүмкін болмады. Сервер мекенжайын және интернет байланысын тексеріңіз.",
        "local_read_error": "Жергілікті профильдерді оқу мүмкін болмады. Бұрын жүктелген рейтинг сақталады. Қайталап көріңіз.",
        "settings_error": "Сервер мекенжайын осы құрылғыда сақтау мүмкін болмады. Қайталап көріңіз.",
        "environment_override": "Белсенді мекенжайды AETHERLAB_LEADERBOARD_URL анықтайды. Сақталған таңдау айнымалы өшірілгенде қолданылады. Рейтингті алу үшін жаңартыңыз.",
        "invalid_environment_override": "AETHERLAB_LEADERBOARD_URL мекенжайы жарамсыз. Айнымалыны түзетіңіз немесе өшіріңіз; қосылу басталмады.",
        "rank": "Орын",
        "student": "Оқушы",
        "class": "Сынып",
        "best": "Үздік",
        "latest": "Соңғы",
        "count": "Сынақ",
        "history": "Таңдалған оқушының толық сынақтары",
        "date": "Өткізілген күні",
        "score": "Ұпай /50",
        "no_history": "Бұл оқушы толық сынақ әлі тапсырмаған.",
        "select_student": "Сынақтарының тізімін көру үшін оқушыны таңдаңыз.",
        "no_school": "Ортақ мектеп ID-сі бар профильдер әзірге табылмады.",
        "no_mock": "Толық сынақ жоқ",
        "empty_score": "—",
        "help": "Орын ең жоғары толық сынақ ұпайымен анықталады. Тек толық, 50 ұпайлық пробниктер саналады.",
    },
    "ru": {
        "title": "Рейтинг школы",
        "intro": "Ученики с одинаковым ID школы соревнуются по баллам полных пробников ЕНТ.",
        "endpoint": "Сервер рейтинга",
        "endpoint_placeholder": "https://school.example.kz",
        "save": "Сохранить",
        "sync": "Подключиться и обновить рейтинг",
        "local_review": "Локальная проверка пробников",
        "close": "Закрыть",
        "privacy": "На сервер отправятся ваше имя, класс и баллы полных пробников. ID школы используется для группировки, сервер хранит только его хеш. Фото и логин не передаются. Используйте одинаковый username на всех устройствах.",
        "local_only": "Сервер не подключён: ниже показаны только профили на этом устройстве. Чтобы добавить другие устройства, введите HTTPS-адрес сервера школы.",
        "local_configured": "Адрес сервера сохранён. Нажмите «Подключиться и обновить рейтинг», чтобы получить результаты с других устройств.",
        "saved": "Адрес сервера сохранён. Нажмите кнопку обновления, чтобы подключиться к рейтингу.",
        "local_mode": "Адрес сервера удалён. Показан локальный рейтинг.",
        "joined": "Рейтинг обновлён.",
        "needs_id": "Сначала укажите общий ID школы в профиле.",
        "needs_username": "Укажите username, чтобы связать профиль между устройствами.",
        "bad_url": "Неверный адрес сервера. Используйте HTTPS; HTTP разрешён только в локальной сети.",
        "busy": "Обновляю рейтинг…",
        "network_error": "Не удалось подключиться или обновить рейтинг. Проверьте адрес сервера и интернет-соединение.",
        "local_read_error": "Не удалось прочитать локальные профили. Сохранён ранее загруженный рейтинг. Повторите попытку.",
        "settings_error": "Не удалось сохранить адрес сервера на этом устройстве. Повторите попытку.",
        "environment_override": "Адрес задан через AETHERLAB_LEADERBOARD_URL. Сохранённый выбор будет действовать после удаления переменной. Для загрузки рейтинга нажмите обновление.",
        "invalid_environment_override": "Неверный адрес в AETHERLAB_LEADERBOARD_URL. Исправьте или удалите переменную; подключение не запущено.",
        "rank": "Место",
        "student": "Ученик",
        "class": "Класс",
        "best": "Лучший",
        "latest": "Последний",
        "count": "Пробники",
        "history": "Полные пробники выбранного ученика",
        "date": "Дата прохождения",
        "score": "Баллы /50",
        "no_history": "У этого ученика пока нет полных пробников.",
        "select_student": "Выберите ученика, чтобы увидеть список его пробников.",
        "no_school": "Профили с общим ID школы пока не найдены.",
        "no_mock": "Полных пробников нет",
        "empty_score": "—",
        "help": "Место определяется лучшим результатом. Учитываются только полные пробники на 50 баллов.",
    },
    "en": {
        "title": "School leaderboard",
        "intro": "Students with the same school ID compete on full UNT mock exam scores.",
        "endpoint": "Leaderboard server",
        "endpoint_placeholder": "https://school.example.com",
        "save": "Save",
        "sync": "Join and refresh leaderboard",
        "local_review": "Local mock review",
        "close": "Close",
        "privacy": "Your name, class, and full mock scores are sent to the server. The school ID groups students and only its hash is stored. Your photo and login are not sent. Use the same username on every device.",
        "local_only": "No server is connected. Only profiles on this device are shown. Enter your school's HTTPS server address to include other devices.",
        "local_configured": "Server address is saved. Press Join and refresh to retrieve results from other devices.",
        "saved": "Server address saved. Press refresh to join the leaderboard.",
        "local_mode": "Server address cleared. Showing the local leaderboard.",
        "joined": "Leaderboard updated.",
        "needs_id": "Add the shared school ID to your profile first.",
        "needs_username": "Add a username so your profile can be matched across devices.",
        "bad_url": "Invalid server address. Use HTTPS; HTTP is allowed only on a local network.",
        "busy": "Refreshing leaderboard…",
        "network_error": "Could not connect or refresh the leaderboard. Check the server address and internet connection.",
        "local_read_error": "Could not read local profiles. Any previously loaded ranking is retained. Please retry.",
        "settings_error": "Could not save the server address on this device. Please retry.",
        "environment_override": "AETHERLAB_LEADERBOARD_URL sets the active address. The saved choice applies when the override is removed. Refresh to fetch the ranking.",
        "invalid_environment_override": "AETHERLAB_LEADERBOARD_URL contains an invalid address. Fix or remove it; no connection was started.",
        "rank": "Rank",
        "student": "Student",
        "class": "Class",
        "best": "Best",
        "latest": "Latest",
        "count": "Mocks",
        "history": "Full mocks for the selected student",
        "date": "Date completed",
        "score": "Score /50",
        "no_history": "This student has not completed a full mock yet.",
        "select_student": "Select a student to see each of their full mock scores.",
        "no_school": "No profiles with the same school ID were found yet.",
        "no_mock": "No full mocks yet",
        "empty_score": "—",
        "help": "Rank is based on the highest full mock score. Only complete 50-point mocks count.",
    },
}


class _SyncWorker(QtCore.QThread):
    completed = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, server_url: str, profile: StudentProfile, parent=None) -> None:
        super().__init__(parent)
        self.server_url = server_url
        self.profile = profile

    def run(self) -> None:
        try:
            self.completed.emit(sync_school_leaderboard(self.server_url, self.profile))
        except (OSError, UnicodeError):
            self.failed.emit("local_read_error")
        except (LeaderboardError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception:  # noqa: BLE001 — UI should stay usable on unexpected network errors
            self.failed.emit("sync_error")


class LeaderboardDialog(QtWidgets.QDialog):
    """Show the school ranking and every student's full mock score history."""

    def __init__(
        self,
        profile_store: StudentProfileStore,
        profile: StudentProfile,
        language: str = "kk",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.profile_store = profile_store
        self.profile = profile
        self.language = normalize_language(language, "kk")
        self.text = _COPY[self.language]
        self.settings = LeaderboardSettingsStore(profile_store.data_dir)
        self.entries: list[SchoolLeaderboardEntry] = []
        self.worker: _SyncWorker | None = None
        self.setObjectName("LeaderboardDialog")
        self.setStyleSheet(AETHERLAB_QSS)
        self.setWindowTitle(self.text["title"])
        self.setMinimumSize(850, 620)
        self.resize(980, 720)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(11)
        title = QtWidgets.QLabel(self.text["title"])
        title.setStyleSheet("font-size:22px; font-weight:700; color:#18283D;")
        root.addWidget(title)
        intro = QtWidgets.QLabel(self.text["intro"])
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#65758A; font-size:12px;")
        root.addWidget(intro)

        endpoint_row = QtWidgets.QHBoxLayout()
        endpoint_label = QtWidgets.QLabel(self.text["endpoint"])
        endpoint_row.addWidget(endpoint_label)
        self.server_edit = QtWidgets.QLineEdit(self.settings.get_server_url())
        self.server_edit.setPlaceholderText(self.text["endpoint_placeholder"])
        self.server_edit.setClearButtonEnabled(True)
        endpoint_row.addWidget(self.server_edit, 1)
        self.save_button = QtWidgets.QPushButton(self.text["save"])
        self.save_button.setObjectName("SecondaryButton")
        self.save_button.clicked.connect(self._save_server_url)
        endpoint_row.addWidget(self.save_button)
        root.addLayout(endpoint_row)

        self.privacy = QtWidgets.QLabel(self.text["privacy"])
        self.privacy.setWordWrap(True)
        self.privacy.setStyleSheet(
            "color:#53647A; background:#E9EFF7; border:1px solid #D8E1EC; "
            "border-radius:8px; padding:9px 11px; font-size:11px;"
        )
        root.addWidget(self.privacy)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#65758A; font-size:11px;")
        root.addWidget(self.status)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setObjectName("LeaderboardTable")
        self.table.setHorizontalHeaderLabels([
            self.text["rank"], self.text["student"], self.text["class"],
            self.text["best"], self.text["latest"], self.text["count"],
        ])
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget::item { padding:4px 6px; }"
            "QTableWidget::item:selected { background:#DFE8F2; color:#26384D; }"
            "QTableWidget:focus { border:1px solid #335F92; }"
        )
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 62)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for column, width in ((2, 72), (3, 86), (4, 96), (5, 82)):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        root.addWidget(self.table, 3)

        self.history_title = QtWidgets.QLabel(self.text["history"])
        self.history_title.setStyleSheet("font-size:14px; font-weight:700; color:#18283D;")
        root.addWidget(self.history_title)
        self.history_table = QtWidgets.QTableWidget(0, 2)
        self.history_table.setObjectName("LeaderboardScoreHistory")
        self.history_table.setHorizontalHeaderLabels([self.text["date"], self.text["score"]])
        self.history_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.history_table.setMaximumHeight(150)
        root.addWidget(self.history_table)

        self.help = QtWidgets.QLabel(self.text["help"])
        self.help.setStyleSheet("color:#65758A; font-size:11px;")
        root.addWidget(self.help)
        actions = QtWidgets.QHBoxLayout()
        self.sync_button = QtWidgets.QPushButton(self.text["sync"])
        self.sync_button.setObjectName("PrimaryButton")
        self.sync_button.clicked.connect(self._sync)
        actions.addWidget(self.sync_button)
        self.review_button = QtWidgets.QPushButton(self.text["local_review"])
        self.review_button.setObjectName("SecondaryButton")
        self.review_button.setEnabled(bool(str(profile.school_id or "").strip()))
        self.review_button.clicked.connect(self._open_local_review)
        actions.addWidget(self.review_button)
        actions.addStretch(1)
        self.close_button = QtWidgets.QPushButton(self.text["close"])
        self.close_button.setObjectName("SecondaryButton")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        root.addLayout(actions)

        self._show_local_ranking()

    def _open_local_review(self) -> None:
        from aetherlab.ui.teacher_review_dialog import TeacherReviewDialog

        dialog = TeacherReviewDialog(
            self.profile_store,
            self.profile,
            language=self.language,
            parent=self,
        )
        dialog.exec()

    def _show_local_ranking(self) -> bool:
        try:
            entries = school_leaderboard(
                self.profile_store.list_profiles(),
                self.profile.school_id,
                current_profile_id=self.profile.id,
            )
        except (OSError, UnicodeError):
            self.status.setText(self.text["local_read_error"])
            return False
        self._render_entries(entries)
        key = "local_configured" if self.settings.get_server_url() else "local_only"
        override = self.settings.environment_override()
        if override is not None:
            key = "environment_override" if override else "invalid_environment_override"
        self.status.setText(self.text[key])
        return True

    def _render_entries(self, entries: list[SchoolLeaderboardEntry]) -> None:
        self.entries = entries
        self.table.clearSelection()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = (
                str(entry.rank) if entry.rank is not None else self.text["empty_score"],
                entry.name,
                entry.class_name or self.text["empty_score"],
                f"{entry.best_score}/50" if entry.best_score is not None else self.text["no_mock"],
                f"{entry.latest_score}/50" if entry.latest_score is not None else self.text["empty_score"],
                str(entry.mock_count),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if column in {0, 3, 4, 5}:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                if entry.is_current_user:
                    item.setBackground(QtGui.QColor("#E8F0F8"))
                    if column == 1:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    item.setToolTip(self.profile.name)
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 38)
        self.history_table.setRowCount(0)
        if entries:
            self.table.selectRow(next(
                (i for i, entry in enumerate(entries) if entry.is_current_user), 0
            ))
        else:
            self._fill_history((), self.text["no_school"])

    def _selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            self._fill_history((), self.text["select_student"])
            return
        entry = self.entries[row]
        self._fill_history(entry.scores, self.text["no_history"])

    def _fill_history(self, scores, empty_message: str) -> None:
        self.history_table.clearSpans()
        self.history_table.setRowCount(len(scores))
        if not scores:
            self.history_table.setRowCount(1)
            self.history_table.setSpan(0, 0, 1, 2)
            self.history_table.setItem(0, 0, QtWidgets.QTableWidgetItem(empty_message))
            return
        for row, score in enumerate(scores):
            try:
                stamp = str(score.completed_at)
                parsed = QtCore.QDateTime.fromString(stamp, QtCore.Qt.DateFormat.ISODateWithMs)
                if not parsed.isValid():
                    parsed = QtCore.QDateTime.fromString(stamp, QtCore.Qt.DateFormat.ISODate)
                date_text = parsed.toLocalTime().toString("yyyy-MM-dd HH:mm") if parsed.isValid() else stamp
            except (AttributeError, TypeError):
                date_text = str(score.completed_at)
            self.history_table.setItem(row, 0, QtWidgets.QTableWidgetItem(date_text))
            score_item = QtWidgets.QTableWidgetItem(f"{score.score}/50")
            score_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(row, 1, score_item)
            self.history_table.setRowHeight(row, 30)

    def _save_server_url(self) -> None:
        try:
            value = self.settings.set_server_url(self.server_edit.text())
        except ValueError:
            self.status.setText(self.text["bad_url"])
            return
        except OSError:
            self.status.setText(self.text["settings_error"])
            return
        self.server_edit.setText(value)
        override = self.settings.environment_override()
        if override is not None:
            key = "environment_override" if override else "invalid_environment_override"
            self.status.setText(self.text[key])
        elif not value:
            if self._show_local_ranking():
                self.status.setText(self.text["local_mode"])
        else:
            self.status.setText(self.text["saved"])

    def _sync(self) -> None:
        if not str(self.profile.school_id or "").strip():
            self.status.setText(self.text["needs_id"])
            return
        if not str(self.profile.username or "").strip():
            self.status.setText(self.text["needs_username"])
            return
        try:
            server_url = self.settings.set_server_url(self.server_edit.text())
        except ValueError:
            self.status.setText(self.text["bad_url"])
            return
        except OSError:
            self.status.setText(self.text["settings_error"])
            return
        self.server_edit.setText(server_url)
        if self.settings.environment_override() == "":
            self.status.setText(self.text["invalid_environment_override"])
            return
        if not server_url:
            self._show_local_ranking()
            return
        self.sync_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.status.setText(self.text["busy"])
        self.worker = _SyncWorker(server_url, self.profile, self)
        self.worker.completed.connect(self._sync_completed)
        self.worker.failed.connect(self._sync_failed)
        self.worker.finished.connect(self._sync_finished)
        self.worker.start()

    def _sync_completed(self, entries: list[SchoolLeaderboardEntry]) -> None:
        self._render_entries(entries)
        self.status.setText(self.text["joined"])

    def _sync_failed(self, message: str) -> None:
        # Use only trusted error keys; never expose raw file/server diagnostics.
        key = "local_read_error" if message == "local_read_error" else "network_error"
        self.status.setText(self.text[key])

    def _sync_finished(self) -> None:
        self.sync_button.setEnabled(True)
        self.save_button.setEnabled(True)
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None and self.worker.isRunning():
            event.ignore()
            self.status.setText(self.text["busy"])
            return
        super().closeEvent(event)
