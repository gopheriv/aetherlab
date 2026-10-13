"""Browser for the user's separate textbook-reference and ENT-mock sources."""

from __future__ import annotations

from pathlib import Path

from aetherlab.core.language import normalize_language
from aetherlab.services.reference_catalog import (
    SourceMaterial,
    default_reference_root,
    openable_path,
    scan_reference_catalog,
    searchable_reference_files,
)
from aetherlab.ui.fonts import install_ui_fonts
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt

require_qt()


_COPY = {
    "kk": {
        "title": "Физика ҰБТ · дереккөздер",
        "heading": "Оқулықтар мен ҰБТ жинақтары",
        "intro": "7–11-сынып оқулықтары теория мен түсіндіруге арналған. ҰБТ тапсырмалары бөлек берілген: файлды ашып, оны жеке сынақ нұсқасы ретінде орындаңыз.",
        "missing_folder": "Дереккөздер бумасы табылмады",
        "choose_folder": "Буманы таңдау…",
        "books_tab": "Оқулықтар мен анықтамалықтар",
        "mocks_tab": "ҰБТ сынақ нұсқалары мен тапсырмалар",
        "open_file": "Таңдалған файлды ашу",
        "close": "Жабу",
        "choose_folder_title": "Оқулықтар мен сынақ нұсқаларының бумасы",
        "save_error_title": "Дереккөздер бумасы сақталмады",
        "env_override": "Жол сақталды, бірақ PhysLab іске қосылғанда AETHERLAB_REFERENCE_SOURCES айнымалысы оны ауыстырады. Таңдалған буманы қайта іске қосқаннан кейін де пайдалану үшін осы айнымалыны өзгертіңіз.",
        "empty_books": "Оқулықтарды көру үшін дереккөздер бумасын таңдаңыз.",
        "empty_mocks": "Дереккөздер бумасын таңдағаннан кейін сынақ нұсқалары осында шығады.",
        "grade_book": "{grade}-сынып оқулығы · түсіндіруге арналған дереккөз",
        "scan_pdf": "скан · PDF ретінде ашылады, бірақ жасанды интеллект мәтінді оқи алмайды",
        "indexed": "анықтамалықта индекстелген · {count:,} үзінді",
        "needs_index": "мәтіні бар · іздеу үшін «Қайта индекстеу» түймесін басыңыз",
        "reference_material": "Қосымша физика материалы",
        "specification": "ҰБТ физикасына қойылатын талаптар",
        "question_set": "Сұрақтар жинағы",
        "unclear_material": "Физика материалы · тапсырма түрі анықталмаған",
        "archive_physics": "ZIP архивіндегі ҰБТ физика материалы",
        "folder_material": "Дереккөздер бумасындағы материал",
        "no_books": "Таңдалған бумадан физика оқулықтары мен анықтамалықтары табылмады.",
        "no_mocks": "Таңдалған бумадан физика бойынша ҰБТ сынақтары табылмады.",
        "books_note": "Кітаптар бастапқы бумада қалады. Мәтіні бар PDF файлдарын түсіндіру үшін индекстеуге болады; скан-нұсқаларды анықтамалық ретінде ашуға болады, бірақ жасанды интеллект әзірге мәтінін оқи алмайды.",
        "mocks_note": "Сынақ PDF/DOCX файлдары әдепкі қолданбада ашылады. PhysLab бұл файлдар бойынша ұпай есептемейді: оларды жеке орындап, жауаптарды дереккөздегі жауап кілтімен тексеріңіз. ZIP архивінен тек таңдалған файл шығарылады.",
        "open_error": "Дереккөзді ашу мүмкін болмады",
        "open_failed": "Жүйе файлды аша алмады:\n{path}",
    },
    "ru": {
        "title": "Физика ЕНТ · источники",
        "heading": "Учебники и сборники ЕНТ",
        "intro": "Учебники 7–11 классов служат справочниками для теории. Задания ЕНТ показаны отдельно: откройте файл и проходите его как самостоятельный пробник.",
        "missing_folder": "Папка источников не найдена",
        "choose_folder": "Выбрать папку…",
        "books_tab": "Учебники и справочники",
        "mocks_tab": "Пробники ЕНТ и задания",
        "open_file": "Открыть выбранный файл",
        "close": "Закрыть",
        "choose_folder_title": "Папка с учебниками и пробниками",
        "save_error_title": "Папка источников не сохранена",
        "env_override": "Путь сохранён, но при запуске PhysLab его переопределяет переменная AETHERLAB_REFERENCE_SOURCES. Измените её, чтобы выбранная папка использовалась после перезапуска.",
        "empty_books": "Выберите папку References, чтобы увидеть источники.",
        "empty_mocks": "Пробники появятся после выбора папки References.",
        "grade_book": "Учебник {grade} класса · источник для объяснений",
        "scan_pdf": "скан · откроется как PDF, текст для ИИ недоступен",
        "indexed": "в справочном индексе · {count:,} фрагм.",
        "needs_index": "текст доступен · нажмите Re-index для поиска ИИ",
        "reference_material": "Дополнительный материал по физике",
        "specification": "Спецификация ЕНТ по физике",
        "question_set": "Набор заданий",
        "unclear_material": "Материал по физике · тип заданий не уточнён",
        "archive_physics": "Материал по физике ЕНТ из ZIP",
        "folder_material": "Материал из папки References",
        "no_books": "В выбранной папке не найдены учебники и справочники по физике.",
        "no_mocks": "В выбранной папке не найдены пробники ЕНТ по физике.",
        "books_note": "Книги остаются в исходной папке. Текстовые PDF можно индексировать для объяснений; сканы открываются как справочники, но пока не читаются ИИ.",
        "mocks_note": "Пробные PDF/DOCX открываются исходным приложением. PhysLab не считает по ним баллы: используйте их как самостоятельный пробник и сверяйте ответы с ключом источника. Из архива извлекается только выбранный файл.",
        "open_error": "Не удалось открыть источник",
        "open_failed": "Система не открыла файл:\n{path}",
    },
    "en": {
        "title": "UNT Physics · Sources",
        "heading": "Textbooks and UNT practice sets",
        "intro": "Grades 7–11 textbooks are references for theory. UNT tasks are listed separately: open a file and use it as a standalone practice test.",
        "missing_folder": "Source folder not found",
        "choose_folder": "Choose folder…",
        "books_tab": "Textbooks and references",
        "mocks_tab": "UNT practice tests and questions",
        "open_file": "Open selected file",
        "close": "Close",
        "choose_folder_title": "Textbook and practice-test folder",
        "save_error_title": "Source folder was not saved",
        "env_override": "The path was saved, but AETHERLAB_REFERENCE_SOURCES overrides it when PhysLab starts. Change that environment variable to use the selected folder after restart.",
        "empty_books": "Choose a References folder to see its sources.",
        "empty_mocks": "Practice tests will appear after you choose a References folder.",
        "grade_book": "Grade {grade} textbook · explanation reference",
        "scan_pdf": "scanned · opens as PDF, but AI cannot read its text",
        "indexed": "indexed for reference · {count:,} chunks",
        "needs_index": "searchable text · select Re-index for AI search",
        "reference_material": "Supplementary physics reference",
        "specification": "UNT physics specification",
        "question_set": "Question set",
        "unclear_material": "Physics material · question type is unclear",
        "archive_physics": "UNT physics material from ZIP",
        "folder_material": "Material from References folder",
        "no_books": "No physics textbooks or references were found in this folder.",
        "no_mocks": "No UNT physics practice tests were found in this folder.",
        "books_note": "Books remain in their original folder. Text-based PDFs can be indexed for explanations; scans can be opened as references, but AI cannot read them yet.",
        "mocks_note": "Practice PDFs/DOCX files open in your default app. PhysLab does not grade these files: use them as standalone tests and check answers against their source key. ZIP archives extract only the selected file.",
        "open_error": "Could not open source",
        "open_failed": "The system could not open this file:\n{path}",
    },
}


class ReferenceSourcesDialog(QtWidgets.QDialog):
    """Show local school books and ENT question packs in clearly separate tabs."""

    settings_changed = QtCore.pyqtSignal(object)

    def __init__(
        self,
        settings=None,
        parent: QtWidgets.QWidget | None = None,
        *,
        initial_tab: int = 0,
        source_root: Path | None = None,
        language: str = "kk",
    ) -> None:
        super().__init__(parent)
        install_ui_fonts()
        if settings is None:
            from aetherlab.core.settings import load_settings

            settings = load_settings()
        self._settings = settings
        self._language = normalize_language(language, "kk")
        self._t = _COPY[self._language]
        settings_root = getattr(settings, "reference_sources_path", None)
        self._root = source_root or settings_root or default_reference_root()
        self.setWindowTitle(self._t["title"])
        self.setMinimumSize(740, 540)
        self.resize(900, 650)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(self._t["heading"])
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        intro = QtWidgets.QLabel(self._t["intro"])
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#65758A; font-size:12px;")
        layout.addWidget(intro)

        path_row = QtWidgets.QHBoxLayout()
        self._path_label = QtWidgets.QLabel(
            str(self._root) if self._root else self._t["missing_folder"]
        )
        self._path_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self._path_label.setStyleSheet(
            "color:#65758A; font-size:10.5px; font-family:'Cascadia Code',monospace;"
        )
        path_row.addWidget(self._path_label, 1)
        choose = QtWidgets.QPushButton(self._t["choose_folder"])
        choose.setObjectName("SecondaryButton")
        choose.clicked.connect(self._choose_root)
        path_row.addWidget(choose)
        layout.addLayout(path_row)

        self._tabs = QtWidgets.QTabWidget()
        self._books = QtWidgets.QListWidget()
        self._mocks = QtWidgets.QListWidget()
        for widget in (self._books, self._mocks):
            widget.setObjectName("ReferenceSourceList")
            widget.setSpacing(3)
            widget.itemDoubleClicked.connect(self._open_item)

        self._tabs.addTab(self._books, self._t["books_tab"])
        self._tabs.addTab(self._mocks, self._t["mocks_tab"])
        self._tabs.setCurrentIndex(max(0, min(1, initial_tab)))
        layout.addWidget(self._tabs, 1)

        self._note = QtWidgets.QLabel("")
        self._note.setWordWrap(True)
        self._note.setStyleSheet(
            "color:#65758A; font-size:11px; padding:9px 11px; "
            "background:#EDF2F8; border:1px solid #A5B6CB; border-radius:9px;"
        )
        layout.addWidget(self._note)

        footer = QtWidgets.QHBoxLayout()
        self._open_button = QtWidgets.QPushButton(self._t["open_file"])
        self._open_button.setObjectName("PrimaryButton")
        self._open_button.clicked.connect(self._open_current)
        footer.addWidget(self._open_button)
        footer.addStretch(1)
        close = QtWidgets.QPushButton(self._t["close"])
        close.setObjectName("SecondaryButton")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        layout.addLayout(footer)

        self._tabs.currentChanged.connect(self._update_note)
        self._books.currentItemChanged.connect(self._update_open_state)
        self._mocks.currentItemChanged.connect(self._update_open_state)
        self._refresh()

    def _choose_root(self) -> None:
        selected = QtWidgets.QFileDialog.getExistingDirectory(
            self, self._t["choose_folder_title"], str(self._root or Path.home())
        )
        if selected:
            try:
                from aetherlab.core.settings import load_settings, save_reference_sources_path

                selected_root = Path(selected).expanduser().resolve(strict=True)
                save_reference_sources_path(selected_root)
                updated_settings = load_settings()
            except (OSError, RuntimeError, ValueError) as exc:
                QtWidgets.QMessageBox.warning(self, self._t["save_error_title"], str(exc))
                return

            active_root = getattr(updated_settings, "reference_sources_path", None)
            if active_root is None or Path(active_root).resolve() != selected_root:
                # Environment settings remain authoritative. Avoid showing a
                # folder as active when the effective app setting differs.
                self._settings = updated_settings
                self._root = Path(active_root) if active_root else None
                self._refresh()
                self._note.setText(self._t["env_override"])
                return

            self._settings = updated_settings
            self._root = selected_root
            self.settings_changed.emit(updated_settings)
            self._refresh()

    def _refresh(self) -> None:
        root = self._root
        self._path_label.setText(str(root) if root else self._t["missing_folder"])
        self._books.clear()
        self._mocks.clear()
        if root is None or not root.is_dir():
            self._add_empty(self._books, self._t["empty_books"])
            self._add_empty(self._mocks, self._t["empty_mocks"])
            self._update_note()
            self._update_open_state()
            return

        catalog = scan_reference_catalog(root)
        readable = set(searchable_reference_files(root))
        manifest = {}
        try:
            from aetherlab.services.ingestion import LibraryIngestor

            manifest = LibraryIngestor(self._settings)._load_manifest()
        except Exception:  # noqa: BLE001 - source browsing works without an index
            pass
        for category in ("book", "reference", "specification"):
            for source in catalog[category]:
                if source.category == "book":
                    grade_label = (
                        self._t["grade_book"].format(grade=source.grade) + " · "
                        if source.grade else ""
                    )
                    entry = manifest.get(str(source.path), {})
                    try:
                        stat = source.path.stat()
                        is_fresh = (
                            entry.get("mtime") == stat.st_mtime
                            and entry.get("size") == stat.st_size
                            and int(entry.get("chunks", 0)) > 0
                        )
                    except OSError:
                        is_fresh = False
                    if source.path not in readable:
                        text_status = self._t["scan_pdf"]
                    elif is_fresh:
                        text_status = self._t["indexed"].format(count=int(entry["chunks"]))
                    else:
                        text_status = self._t["needs_index"]
                    detail = f"{grade_label}{text_status} · {source.path.name}"
                else:
                    detail = self._t[
                        "specification" if category == "specification" else "reference_material"
                    ]
                self._add_source(self._books, source, detail)

        for category in ("mock", "physics_material"):
            for source in catalog[category]:
                label = self._t["question_set"] if category == "mock" else self._t["unclear_material"]
                origin = self._t["archive_physics"] if source.is_archived else self._t["folder_material"]
                self._add_source(self._mocks, source, f"{label} · {origin}")

        if self._books.count() == 0:
            self._add_empty(self._books, self._t["no_books"])
        if self._mocks.count() == 0:
            self._add_empty(self._mocks, self._t["no_mocks"])
        self._update_note()
        self._update_open_state()

    @staticmethod
    def _add_empty(widget: QtWidgets.QListWidget, text: str) -> None:
        item = QtWidgets.QListWidgetItem(text)
        item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        widget.addItem(item)

    @staticmethod
    def _add_source(widget: QtWidgets.QListWidget, source: SourceMaterial, detail: str) -> None:
        row = QtWidgets.QListWidgetItem(f"{source.title}\n{detail}")
        row.setData(QtCore.Qt.ItemDataRole.UserRole, source)
        row.setToolTip(detail)
        row.setSizeHint(QtCore.QSize(0, 58))
        widget.addItem(row)

    def _current_list(self) -> QtWidgets.QListWidget:
        return self._books if self._tabs.currentIndex() == 0 else self._mocks

    def _update_open_state(self, *_args) -> None:
        item = self._current_list().currentItem()
        self._open_button.setEnabled(
            bool(item and isinstance(item.data(QtCore.Qt.ItemDataRole.UserRole), SourceMaterial))
        )

    def _update_note(self, *_args) -> None:
        if self._tabs.currentIndex() == 0:
            self._note.setText(self._t["books_note"])
        else:
            self._note.setText(self._t["mocks_note"])
        self._update_open_state()

    def _open_current(self) -> None:
        item = self._current_list().currentItem()
        source = item.data(QtCore.Qt.ItemDataRole.UserRole) if item else None
        if isinstance(source, SourceMaterial):
            self._open_source(source)

    def _open_item(self, item: QtWidgets.QListWidgetItem) -> None:
        source = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(source, SourceMaterial):
            self._open_source(source)

    def _open_source(self, source: SourceMaterial) -> None:
        try:
            path = openable_path(source)
        except Exception as exc:  # noqa: BLE001 - surface archive/read errors in the UI
            QtWidgets.QMessageBox.warning(self, self._t["open_error"], str(exc))
            return
        if not path.is_file() or not QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(path))
        ):
            QtWidgets.QMessageBox.warning(
                self,
                self._t["open_error"],
                self._t["open_failed"].format(path=path),
            )
