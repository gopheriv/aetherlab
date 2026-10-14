"""Reference-library browsing, ingestion, and download widgets."""

from __future__ import annotations

from pathlib import Path

from aetherlab.ui import icons
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt

require_qt()


_COPY = {
    "kk": {
        "dialog_title": "Бастапқы кітапхананы алу", "dialog_intro": "OpenStax физика оқулықтары тегін, CC BY 4.0 лицензиясымен таратылады. Кітаптар кітапхана бумасына жүктеліп, дереккөз ретінде индекстеледі.",
        "warning": "Астрономия, Calculus және College Physics бөлімдері қамтуды кеңейтеді, бірақ жүктеу мен индекстеуге көбірек уақыт қажет.",
        "cancel": "Болдырмау", "download": "Жүктеп алу", "title": "Кітапхана", "starter": "Бастапқы кітапхананы алу",
        "starter_tip": "OpenStax-тың тегін физика оқулықтарын жүктеу (CC BY 4.0)", "add_folder": "Бума қосу",
        "reindex": "Қайта индекстеу", "reindex_tip": "Жаңа не өзгерген файлдарды индекстеу. Толық жаңарту үшін Ctrl пернесін басып тұрып шертіңіз.",
        "source_hint": "Жергілікті дереккөздер бөлек сақталады: оқулықтар — анықтамаға, сынақ файлдары — пробникке арналған.",
        "books": "7–11-сынып оқулықтары", "mocks": "ҰБТ пробниктері", "cancel_work": "Тоқтату",
        "empty": "Әзірге оқулық индекстелмеген", "add_textbooks": "Оқулық қосу…", "path_title": "Бумадан оқулық қосу",
        "pending": "Кезекте", "indexed": "Индекстелген", "reindexing": "Индекстелуде", "chunks": "{n:,} үзінді",
        "busy": "Жүктеу немесе индекстеу жұмысы қазірдің өзінде жүріп жатыр.",
        "low_space": "Бос орын жеткіліксіз: бастапқы кітапханаға кемінде 500 МБ қажет.",
        "resolving": "Жүктеу сілтемелері анықталуда…", "downloading": "{title} жүктелуде — {done:.1f} / {total:.1f} МБ",
        "downloading_unknown": "{title} жүктелуде — {done:.1f} МБ", "downloaded": "Жүктелді: {title}",
        "download_failed": "Жүктеу сәтсіз аяқталды: {title} — {message}",
        "cancelled_download": "Жүктеу тоқтатылды. {ok} аяқталған кітап сақталды.",
        "nothing_downloaded": "Бастапқы кітапхана: ештеңе жүктелмеді ({bad} қате).",
        "download_summary": "Бастапқы кітапхана: {ok} кітап жүктелді{failed}. Индекстеу басталады…",
        "indexing": "Индекстелуде…", "rebuilding": "Индекс толық жаңартылуда…", "indexing_new": "Жаңа файлдар индекстелуде…",
        "index_started": "Кітапхана ChromaDB жүйесіне индекстелуде…", "index_progress": "{file} индекстелуде ({done}/{total}) — {detail}",
        "cancelled_index": "Индекстеу тоқтатылды. Аяқталған жұмыс сақталды.", "indexed_count": "ChromaDB жүйесіне {n:,} үзінді индекстелді.",
        "index_current": "Кітапхана индексі жаңартылған.", "index_failed": "Индекстеу сәтсіз аяқталды: {message}",
        "cancel_download": "Жүктеу тоқтатылуда…", "cancel_index": "Индекстеу тоқтатылуда. Жұмыс сақталады да, қайта индекстеу кезінде жалғасады.",
        "cancelling": "Фондық жұмыс тоқтатылуда…", "added": "Кітапханаға {n} файл қосылды.",
    },
    "ru": {
        "dialog_title": "Начальная библиотека", "dialog_intro": "Учебники физики OpenStax бесплатны и доступны по CC BY 4.0. Они будут загружены в папку библиотеки и проиндексированы как источники.",
        "warning": "Астрономия, Calculus и College Physics расширяют охват, но требуют больше времени на загрузку и индексирование.",
        "cancel": "Отмена", "download": "Скачать", "title": "Библиотека", "starter": "Начальная библиотека",
        "starter_tip": "Скачать бесплатные учебники физики OpenStax (CC BY 4.0)", "add_folder": "Добавить папку",
        "reindex": "Переиндексировать", "reindex_tip": "Индексировать новые и изменённые файлы. Для полной пересборки удерживайте Ctrl при нажатии.",
        "source_hint": "Локальные источники разделены: учебники — для справки, тестовые файлы — для пробников.",
        "books": "Учебники 7–11 классов", "mocks": "Пробники ЕНТ", "cancel_work": "Остановить",
        "empty": "Учебники ещё не проиндексированы", "add_textbooks": "Добавить учебники…", "path_title": "Добавить учебники из папки",
        "pending": "В очереди", "indexed": "Проиндексировано", "reindexing": "Индексирование", "chunks": "Фрагментов: {n:,}",
        "busy": "Загрузка или индексирование уже выполняется.", "low_space": "Недостаточно места: начальной библиотеке нужно не менее 500 МБ.",
        "resolving": "Поиск ссылок для загрузки…", "downloading": "Загрузка {title} — {done:.1f} / {total:.1f} МБ",
        "downloading_unknown": "Загрузка {title} — {done:.1f} МБ", "downloaded": "Загружено: {title}",
        "download_failed": "Не удалось загрузить {title}: {message}", "cancelled_download": "Загрузка остановлена. Сохранено книг: {ok}.",
        "nothing_downloaded": "Начальная библиотека: ничего не загружено (ошибок: {bad}).",
        "download_summary": "Начальная библиотека: загружено книг: {ok}{failed}. Индексирование начинается…",
        "indexing": "Индексирование…", "rebuilding": "Полная пересборка индекса…", "indexing_new": "Индексирование новых файлов…",
        "index_started": "Индексирование библиотеки в ChromaDB…", "index_progress": "Индексирование {file} ({done}/{total}) — {detail}",
        "cancelled_index": "Индексирование остановлено. Выполненная работа сохранена.", "indexed_count": "В ChromaDB проиндексировано фрагментов: {n:,}.",
        "index_current": "Индекс библиотеки уже актуален.", "index_failed": "Ошибка индексирования: {message}",
        "cancel_download": "Остановка загрузки…", "cancel_index": "Остановка индексирования. Работа сохранится и продолжится при переиндексации.",
        "cancelling": "Остановка фоновой задачи…", "added": "В библиотеку добавлено файлов: {n}.",
    },
    "en": {
        "dialog_title": "Get starter library", "dialog_intro": "OpenStax physics textbooks are free under CC BY 4.0. They will be downloaded into your library folder and indexed as references.",
        "warning": "Astronomy, Calculus, and College Physics broaden coverage but take longer to download and index.",
        "cancel": "Cancel", "download": "Download", "title": "Library", "starter": "Get starter library",
        "starter_tip": "Download free OpenStax physics textbooks (CC BY 4.0)", "add_folder": "Add folder",
        "reindex": "Re-index", "reindex_tip": "Index new or changed files. Hold Ctrl while clicking for a full rebuild.",
        "source_hint": "Local sources stay separate: textbooks are references; test files are practice sets.",
        "books": "Books for grades 7–11", "mocks": "UNT practice sets", "cancel_work": "Cancel",
        "empty": "No textbooks indexed yet", "add_textbooks": "Add textbooks…", "path_title": "Add textbooks from folder",
        "pending": "Pending", "indexed": "Indexed", "reindexing": "Re-indexing", "chunks": "{n:,} chunks",
        "busy": "A download or indexing task is already running.", "low_space": "Not enough disk space: the starter library needs at least 500 MB free.",
        "resolving": "Resolving download URLs…", "downloading": "Downloading {title} — {done:.1f} / {total:.1f} MB",
        "downloading_unknown": "Downloading {title} — {done:.1f} MB", "downloaded": "Downloaded: {title}",
        "download_failed": "Download failed: {title} — {message}", "cancelled_download": "Starter download cancelled; {ok} completed books were kept.",
        "nothing_downloaded": "Starter library: nothing downloaded ({bad} failed).",
        "download_summary": "Starter library: {ok} books downloaded{failed}. Indexing…",
        "indexing": "Indexing…", "rebuilding": "Rebuilding index…", "indexing_new": "Indexing new files…",
        "index_started": "Indexing library into ChromaDB…", "index_progress": "Indexing {file} ({done}/{total}) — {detail}",
        "cancelled_index": "Indexing cancelled; completed progress was saved.", "indexed_count": "Indexed {n:,} chunks into ChromaDB.",
        "index_current": "Library index is already up to date.", "index_failed": "Indexing failed: {message}",
        "cancel_download": "Cancelling download…", "cancel_index": "Cancelling indexing — progress is saved and resumes on Re-index.",
        "cancelling": "Cancelling background work…", "added": "Added {n} files to the library.",
    },
}

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

    def __init__(self, parent: QtWidgets.QWidget | None = None, language: str = "kk") -> None:
        super().__init__(parent)
        from aetherlab.services.starter_library import STARTER_BOOKS

        self._language = language if language in _COPY else "kk"
        self._copy = _COPY[self._language]
        self.setWindowTitle(self._copy["dialog_title"])
        self.setMinimumWidth(430)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        self._title = QtWidgets.QLabel(self._copy["dialog_title"])
        self._title.setStyleSheet("color: #18283D; font-size: 17px; font-weight: 700;")
        layout.addWidget(self._title)

        self._subtitle = QtWidgets.QLabel(self._copy["dialog_intro"])
        self._subtitle.setStyleSheet("color: #65758A; font-size: 12px;")
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

        self._checks: list[tuple[QtWidgets.QCheckBox, object]] = []
        for book in STARTER_BOOKS:
            check = QtWidgets.QCheckBox(f"{book.title}  (~{book.approx_mb} MB)")
            check.setChecked(book.default_checked)
            check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            check.toggled.connect(self._update_warning)
            layout.addWidget(check)
            self._checks.append((check, book))

        self._warning = QtWidgets.QLabel(self._copy["warning"])
        self._warning.setStyleSheet(
            "color: #8A5A24; font-size: 11px; background-color: rgba(251,191,36,0.12); "
            "border: 1px solid #8A5A24; border-radius: 8px; padding: 8px 10px;"
        )
        self._warning.setWordWrap(True)
        self._warning.hide()
        layout.addWidget(self._warning)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch()
        self._cancel_btn = QtWidgets.QPushButton(self._copy["cancel"])
        self._cancel_btn.setObjectName("SecondaryButton")
        self._cancel_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        footer.addWidget(self._cancel_btn)
        self._download_btn = QtWidgets.QPushButton(self._copy["download"])
        self._download_btn.setObjectName("PrimaryButton")
        self._download_btn.setIcon(icons.icon("download", 14, "#FFFFFF"))
        self._download_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._download_btn.clicked.connect(self.accept)
        footer.addWidget(self._download_btn)
        layout.addLayout(footer)

    def set_language(self, language: str) -> None:
        self._language = language if language in _COPY else "kk"
        self._copy = _COPY[self._language]
        self.setWindowTitle(self._copy["dialog_title"])
        self._title.setText(self._copy["dialog_title"])
        self._subtitle.setText(self._copy["dialog_intro"])
        self._warning.setText(self._copy["warning"])
        self._cancel_btn.setText(self._copy["cancel"])
        self._download_btn.setText(self._copy["download"])

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
        self._language = "kk"
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

        self._title = QtWidgets.QLabel()
        self._title.setObjectName("PanelTitle")
        header_layout.addWidget(self._title)
        header_layout.addStretch()

        self._starter_btn = QtWidgets.QPushButton()
        self._starter_btn.setObjectName("SecondaryButton")
        self._starter_btn.setIcon(icons.icon("download", 14, "#65758A"))
        self._starter_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._starter_btn.clicked.connect(self._get_starter_library)
        header_layout.addWidget(self._starter_btn)

        self._add_btn = QtWidgets.QPushButton()
        self._add_btn.setObjectName("SecondaryButton")
        self._add_btn.setIcon(icons.icon("folder-plus", 14, "#65758A"))
        self._add_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._add_btn.clicked.connect(self._add_folder)
        header_layout.addWidget(self._add_btn)

        self._reindex_btn = QtWidgets.QPushButton()
        self._reindex_btn.setObjectName("SecondaryButton")
        self._reindex_btn.setIcon(icons.icon("refresh-cw", 14, "#65758A"))
        self._reindex_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._reindex_btn.clicked.connect(self._reindex_clicked)
        header_layout.addWidget(self._reindex_btn)

        layout.addWidget(header)

        source_row = QtWidgets.QFrame()
        source_row.setObjectName("CardFrame")
        source_layout = QtWidgets.QHBoxLayout(source_row)
        source_layout.setContentsMargins(14, 8, 14, 8)
        source_layout.setSpacing(9)
        self._source_hint = QtWidgets.QLabel()
        self._source_hint.setWordWrap(True)
        self._source_hint.setStyleSheet("color:#65758A; font-size:11px; background:transparent;")
        source_layout.addWidget(self._source_hint, 1)
        self._book_sources_btn = QtWidgets.QPushButton()
        self._book_sources_btn.setObjectName("SecondaryButton")
        self._book_sources_btn.clicked.connect(lambda: self._open_reference_sources(0))
        source_layout.addWidget(self._book_sources_btn)
        self._mock_sources_btn = QtWidgets.QPushButton()
        self._mock_sources_btn.setObjectName("SecondaryButton")
        self._mock_sources_btn.clicked.connect(lambda: self._open_reference_sources(1))
        source_layout.addWidget(self._mock_sources_btn)
        layout.addWidget(source_row)

        # ── Progress strip (downloads + indexing), hidden by default ──
        self._progress_strip = QtWidgets.QFrame()
        self._progress_strip.setObjectName("CardFrame")
        strip_layout = QtWidgets.QHBoxLayout(self._progress_strip)
        strip_layout.setContentsMargins(14, 8, 14, 8)
        strip_layout.setSpacing(12)

        self._progress_label = QtWidgets.QLabel("")
        self._progress_label.setStyleSheet(
            "color: #65758A; font-size: 11px; font-family: 'Cascadia Code', monospace; "
            "background: transparent; border: none;"
        )
        strip_layout.addWidget(self._progress_label, 1)

        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background-color: #D8E1EC; border: none; border-radius: 3px; }"
            "QProgressBar::chunk { background-color: #486A91; border-radius: 3px; }"
        )
        strip_layout.addWidget(self._progress_bar, 2)

        self._cancel_work_btn = QtWidgets.QPushButton()
        self._cancel_work_btn.setObjectName("GhostButton")
        self._cancel_work_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._cancel_work_btn.clicked.connect(self._cancel_work)
        strip_layout.addWidget(self._cancel_work_btn)

        self._progress_strip.hide()
        layout.addWidget(self._progress_strip)

        self._path_label = QtWidgets.QLabel("")
        self._path_label.setStyleSheet(
            "color: #65758A; font-size: 11px; font-family: 'Cascadia Code', monospace;"
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
        self._empty.setObjectName("LibraryEmptyState")
        self._empty.setStyleSheet(
            "QFrame#LibraryEmptyState { background-color: #FFFFFF; border: 1px dashed #A5B6CB; border-radius: 8px; }"
            "QLabel, QPushButton { border: none; }"
        )
        empty_layout = QtWidgets.QVBoxLayout(self._empty)
        empty_layout.setContentsMargins(32, 32, 32, 32)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(
            icons.icon_label("library", 24, "#65758A"), 0,
            QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        self._empty_text = QtWidgets.QLabel()
        self._empty_text.setStyleSheet("color: #65758A; font-size: 14px;")
        self._empty_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self._empty_text)
        self._empty_add = QtWidgets.QPushButton()
        self._empty_add.setObjectName("PrimaryButton")
        self._empty_add.setIcon(icons.icon("folder-plus", 14, "#FFFFFF"))
        self._empty_add.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._empty_add.clicked.connect(self._add_folder)
        empty_layout.addWidget(self._empty_add, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        self._empty_starter = QtWidgets.QPushButton()
        self._empty_starter.setObjectName("SecondaryButton")
        self._empty_starter.setIcon(icons.icon("download", 14, "#65758A"))
        self._empty_starter.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._empty_starter.clicked.connect(self._get_starter_library)
        empty_layout.addWidget(self._empty_starter, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._empty, 1)
        self._empty.hide()
        self.set_language(self._language)

    # ── shared state ──

    def set_settings(self, settings) -> None:
        self._settings = settings
        self.refresh()

    def _t(self, key: str, **values) -> str:
        return _COPY[self._language][key].format(**values)

    def set_language(self, language: str) -> None:
        self._language = language if language in _COPY else "kk"
        self._title.setText(self._t("title"))
        self._starter_btn.setText(self._t("starter"))
        self._starter_btn.setToolTip(self._t("starter_tip"))
        self._add_btn.setText(self._t("add_folder"))
        self._reindex_btn.setToolTip(self._t("reindex_tip"))
        indexing = bool(self._worker and self._worker.isRunning())
        self._reindex_btn.setText(self._t("indexing") if indexing else self._t("reindex"))
        self._reindex_btn.setEnabled(not self._busy())
        self._source_hint.setText(self._t("source_hint"))
        self._book_sources_btn.setText(self._t("books"))
        self._mock_sources_btn.setText(self._t("mocks"))
        self._cancel_work_btn.setText(self._t("cancel_work"))
        self._empty_text.setText(self._t("empty"))
        self._empty_add.setText(self._t("add_textbooks"))
        self._empty_starter.setText(self._t("starter"))
        if self._settings:
            self.refresh()

    def _open_reference_sources(self, initial_tab: int = 0) -> None:
        from aetherlab.ui.reference_sources import ReferenceSourcesDialog

        window = self.window()
        command_bar = getattr(window, "command_bar", None)
        get_language = getattr(command_bar, "get_language", None)
        language = self._language if self._language in _COPY else (
            get_language() if callable(get_language) else "kk"
        )
        dialog = ReferenceSourcesDialog(
            self._settings,
            self,
            initial_tab=initial_tab,
            language=language,
        )
        dialog.settings_changed.connect(self.set_settings)
        apply_settings = getattr(window, "_apply_reference_sources_settings", None)
        if callable(apply_settings):
            dialog.settings_changed.connect(apply_settings)
        dialog.exec()

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

        manifest = self._manifest()
        # Research-bookshelf spine colors, assigned stably per file.
        spine_cycle = ("#486A91", "#536F90", "#26725C", "#8A5A24", "#AC4055")
        for i, path in enumerate(files):
            item = QtWidgets.QListWidgetItem()
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(14, 8, 14, 8)
            row_layout.setSpacing(12)

            # Painted book spine (design v2 §4: research bookshelf)
            entry = manifest.get(str(path))
            indexed = entry is not None
            reindexing = bool(getattr(self, "_worker", None)
                              and self._worker and self._worker.isRunning())
            spine = _BookSpine(spine_cycle[i % len(spine_cycle)])
            row_layout.addWidget(spine)

            name = QtWidgets.QLabel(path.name)
            name.setStyleSheet(
                "color: #18283D; font-size: 12.5px; background: transparent;"
            )
            row_layout.addWidget(name, 1)

            # chunk count from the manifest (freshness)
            chunks = int(entry.get("chunks", 0)) if entry else 0
            if chunks:
                chunk_lbl = QtWidgets.QLabel(self._t("chunks", n=chunks))
                chunk_lbl.setStyleSheet(
                    "color: #65758A; font-size: 10.5px; "
                    "font-family: 'Cascadia Code', monospace; background: transparent;"
                )
                row_layout.addWidget(chunk_lbl)

            size_kb = path.stat().st_size / 1024
            size = QtWidgets.QLabel(
                f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
            )
            size.setStyleSheet(
                "color: #65758A; font-size: 11px; "
                "font-family: 'Cascadia Code', monospace; background: transparent;"
            )
            row_layout.addWidget(size)

            # Freshness dot + status (emerald indexed / amber re-indexing / grey pending)
            if reindexing and not indexed:
                status_text, dot = self._t("reindexing"), "#8A5A24"
            elif indexed:
                status_text, dot = self._t("indexed"), "#26725C"
            else:
                status_text, dot = self._t("pending"), "#65758A"
            chip = QtWidgets.QLabel(status_text)
            chip.setStyleSheet(
                f"color: {dot}; border: 1px solid {dot}; "
                "border-radius: 9px; padding: 1px 9px; font-size: 11px; "
                "background: transparent;"
            )
            row_layout.addWidget(chip)
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

    def _manifest(self) -> dict:
        """The ingest manifest {path: {mtime, size, chunks}}."""
        if not self._settings:
            return {}
        try:
            from aetherlab.services.ingestion import LibraryIngestor

            return LibraryIngestor(self._settings)._load_manifest()
        except Exception:  # noqa: BLE001
            return {}

    def _indexed_paths(self) -> set[str]:
        """Paths recorded in the ingest manifest (per-file 'Indexed' chips)."""
        return set(self._manifest().keys())

    # ── starter library download flow ──

    def _get_starter_library(self) -> None:
        if not self._settings:
            return
        if self._busy():
            self.status_message.emit(self._t("busy"))
            return

        dialog = StarterLibraryDialog(self, self._language)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        books = dialog.selected_books()
        if not books:
            return

        from aetherlab.services.starter_library import free_disk_mb

        root = Path(self._settings.library_path)
        if free_disk_mb(root) < 500:
            self.status_message.emit(
                self._t("low_space")
            )
            return

        self._progress_strip.show()
        self._progress_bar.setRange(0, 0)  # indeterminate until sizes known
        self._progress_label.setText(self._t("resolving"))

        self._downloader = _DownloadWorker(books, root)
        self._downloader.book_progress.connect(self._on_book_progress)
        self._downloader.book_done.connect(self._on_book_done)
        self._downloader.book_failed.connect(self._on_book_failed)
        self._downloader.all_done.connect(self._on_downloads_done)
        self._reindex_btn.setEnabled(False)
        self._downloader.start()

    def _on_book_progress(self, title: str, done: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setRange(0, 1000)
            self._progress_bar.setValue(int(done / total * 1000))
            self._progress_label.setText(
                self._t("downloading", title=title, done=done / 1e6, total=total / 1e6)
            )
        else:
            self._progress_bar.setRange(0, 0)
            self._progress_label.setText(
                self._t("downloading_unknown", title=title, done=done / 1e6)
            )

    def _on_book_done(self, title: str) -> None:
        self.status_message.emit(self._t("downloaded", title=title))
        self.refresh()

    def _on_book_failed(self, title: str, message: str) -> None:
        self.status_message.emit(self._t("download_failed", title=title, message=message))

    def _on_downloads_done(self, ok: int, bad: int) -> None:
        from aetherlab.services.starter_library import write_attribution

        cancelled = bool(
            self._downloader and self._downloader.isInterruptionRequested()
        )
        if ok:
            write_attribution(Path(self._settings.library_path))
        self.refresh()
        if cancelled:
            self._progress_strip.hide()
            self._reindex_btn.setEnabled(True)
            self._reindex_btn.setText(self._t("reindex"))
            self.status_message.emit(
                self._t("cancelled_download", ok=ok)
            )
            return
        if ok == 0:
            self._progress_strip.hide()
            self._reindex_btn.setEnabled(True)
            self.status_message.emit(
                self._t("nothing_downloaded", bad=bad)
            )
            return
        self.status_message.emit(
            self._t("download_summary", ok=ok, failed=f"; {bad} қате" if bad and self._language == "kk"
                      else f"; ошибок: {bad}" if bad and self._language == "ru"
                      else f", {bad} failed" if bad else "")
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
        if not self._settings:
            return
        if self._busy():
            self.status_message.emit(self._t("busy"))
            return
        self._start_ingest(reset=reset)

    def _start_ingest(self, reset: bool) -> None:
        self._reindex_btn.setEnabled(False)
        self._reindex_btn.setText(self._t("indexing"))
        self._progress_strip.show()
        self._progress_bar.setRange(0, 0)
        self._progress_label.setText(
            self._t("rebuilding") if reset else self._t("indexing_new")
        )
        self.status_message.emit(self._t("index_started"))
        self._worker = _IngestWorker(self._settings, reset=reset)
        self._worker.progress.connect(self._on_ingest_progress)
        self._worker.finished_count.connect(self._on_ingested)
        self._worker.failed.connect(self._on_ingest_failed)
        self._worker.start()

    def _on_ingest_progress(self, file_name: str, done: int, total: int, detail: str) -> None:
        self._progress_bar.setRange(0, 0)  # chunk totals are per-file; keep sweep
        self._progress_label.setText(
            self._t("index_progress", file=file_name, done=done + 1, total=total, detail=detail)
        )

    def _on_ingested(self, count: int) -> None:
        cancelled = bool(self._worker and self._worker.isInterruptionRequested())
        self._reindex_btn.setEnabled(True)
        self._reindex_btn.setText(self._t("reindex"))
        self._progress_strip.hide()
        if cancelled:
            self.status_message.emit(
                self._t("cancelled_index")
            )
        elif count:
            self.status_message.emit(self._t("indexed_count", n=count))
        else:
            self.status_message.emit(self._t("index_current"))
        self.refresh()

    def _on_ingest_failed(self, message: str) -> None:
        self._reindex_btn.setEnabled(True)
        self._reindex_btn.setText(self._t("reindex"))
        self._progress_strip.hide()
        self.status_message.emit(self._t("index_failed", message=message))

    def active_workers(self) -> tuple[QtCore.QThread, ...]:
        """Return live library threads for the application shutdown barrier."""
        return tuple(
            worker
            for worker in (self._downloader, self._worker)
            if worker is not None and worker.isRunning()
        )

    def request_background_cancel(self, *, update_ui: bool = False) -> None:
        """Request cooperative cancellation without claiming work has stopped."""
        cancelling = False
        if self._downloader and self._downloader.isRunning():
            self._downloader.requestInterruption()
            cancelling = True
            if update_ui:
                self.status_message.emit(self._t("cancel_download"))
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            cancelling = True
            if update_ui:
                self.status_message.emit(
                    self._t("cancel_index")
                )
        if update_ui and cancelling:
            self._progress_strip.show()
            self._progress_label.setText(self._t("cancelling"))
            self._reindex_btn.setEnabled(False)

    def _cancel_work(self) -> None:
        self.request_background_cancel(update_ui=True)

    # ── add folder ──

    def _add_folder(self) -> None:
        if not self._settings:
            return
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, self._t("path_title")
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
        self.status_message.emit(self._t("added", n=copied))
        self.refresh()
        if copied:
            self._reindex()

class _BookSpine(QtWidgets.QWidget):
    """A little painted book spine for the library bookshelf (design v2 §4)."""

    def __init__(self, color: str, parent=None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(8, 24)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(self._color))
        painter.drawRoundedRect(QtCore.QRectF(1, 1, 6, 22), 2, 2)
        cap = QtGui.QColor(self._color)
        cap.setAlphaF(0.5)
        painter.setBrush(cap)
        painter.drawRoundedRect(QtCore.QRectF(1, 1, 6, 4), 2, 2)
