"""A translated, retryable progress read state shared by student screens."""

from __future__ import annotations

from pathlib import Path

from aetherlab.services.ent_practice_progress import load_progress_snapshot
from aetherlab.ui.qt_compat import QtWidgets

_COPY = {
    "kk": {
        "unavailable": "Оқу деректерін оқу мүмкін болмады. Нәтиже белгісіз. Файлға қолжетімділікті қалпына келтіріп, қайта жүктеңіз.",
        "stale": "Деректер жаңартылмады. Соңғы жүктелген нәтижелер көрсетілген. Файлға қолжетімділікті қалпына келтіріп, қайта жүктеңіз.",
        "retry": "Қайта жүктеу",
        "unknown": "Прогресс қолжетімсіз",
        "recovered": "Кейбір сақталған мәндерді пайдалану мүмкін болмады. Тек дұрыс оқылған деректер көрсетілген.",
    },
    "ru": {
        "unavailable": "Не удалось прочитать данные подготовки. Результаты неизвестны. Восстановите доступ к файлу и повторите загрузку.",
        "stale": "Данные не обновились. Показаны последние загруженные результаты. Восстановите доступ к файлу и повторите загрузку.",
        "retry": "Повторить загрузку",
        "unknown": "Прогресс недоступен",
        "recovered": "Некоторые сохранённые значения не удалось использовать. Показаны только корректно прочитанные данные.",
    },
    "en": {
        "unavailable": "Study data could not be read. Results are unknown. Restore file access and reload.",
        "stale": "Data could not be refreshed. The last loaded results are shown. Restore file access and reload.",
        "retry": "Reload",
        "unknown": "Progress unavailable",
        "recovered": "Some saved values could not be used. Only valid stored data is shown.",
    },
}


class ProgressReadNotice(QtWidgets.QWidget):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.language = "ru"
        self.last_read_ok = False
        self._snapshot = None
        self._path = None
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#8A5A24; padding:8px;")
        self.retry = QtWidgets.QPushButton()
        self.retry.setObjectName("SecondaryButton")
        self.retry.clicked.connect(callback)
        layout.addWidget(self.status, 1)
        layout.addWidget(self.retry)
        self.hide()

    @property
    def copy(self):
        return _COPY[self.language]

    def read(self, path, language):
        self.language = language
        self.retry.setText(self.copy["retry"])
        key = Path(path).resolve() if path is not None else None
        if key != self._path:
            self._snapshot = None
            self._path = key
        try:
            snapshot = load_progress_snapshot(path)
        except (OSError, UnicodeError):
            self.last_read_ok = False
            self.status.setText(self.copy["stale"] if self._snapshot is not None else self.copy["unavailable"])
            self.show()
            return self._snapshot
        self._snapshot = snapshot
        self.last_read_ok = True
        self.status.setText(self.copy["recovered"] if snapshot.recovered_values else "")
        self.setVisible(snapshot.recovered_values)
        return snapshot
