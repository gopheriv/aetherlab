"""AetherLab main window — design-system shell.

Spatial model (design/readme.md): a persistent left icon rail whose items are
pure destinations driving ONE workspace, a first-class pipeline timeline strip
across the top of the workspace, a toast area for errors, and a fixed command
bar at the bottom. Screens follow design/ui_kits/aetherlab-desktop/.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path

from aetherlab.core.language import normalize_language
from aetherlab.core.lesson_messages import lesson_message
from aetherlab.core.models import (
    PipelineError,
    PipelineResult,
    ProblemRequest,
    RagResult,
    SceneBundle,
    SolverResult,
)
from aetherlab.core.settings import AppSettings
from aetherlab.services.pdf import (
    export_derivation_to_latex,
    export_scene_code,
)
from aetherlab.ui import icons
from aetherlab.ui.background_task import BackgroundTask
from aetherlab.ui.fonts import install_ui_fonts
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt
from aetherlab.ui.student_views import (
    ProgressOverview,
    StudentDashboard,
    TopicCatalogView,
)
from aetherlab.ui.style import AETHERLAB_QSS
from aetherlab.ui.widgets import (
    AnalysisPanel,
    CommandBar,
    EmptyStateView,
    HistoryPanel,
    LessonView,
    LibraryPanel,
    ParameterDock,
    PipelineStepper,
    ReferencePanel,
    RunningView,
    SidebarNav,
    SimulationPanel,
    TitleBar,
    Toast,
)
from aetherlab.ui.workers import LessonWorker, PipelineWorker

require_qt()


def _install_ui_fonts() -> None:
    """Backward-compatible hook for the shared UI font loader."""
    install_ui_fonts()


# Workspace stack pages
PAGE_EMPTY = 0
PAGE_RUNNING = 1
PAGE_SOLVE = 2
PAGE_SCENE = 3
PAGE_LIBRARY = 4
PAGE_HISTORY = 5
PAGE_LESSON = 6
PAGE_STUDENT_HOME = 7
PAGE_TOPICS = 8
PAGE_PROGRESS = 9


_SETTINGS_COPY = {
    "kk": {
        "Settings": "Баптаулар", "PROVIDER": "AI ПРОВАЙДЕРІ", "RENDERING": "РЕНДЕР", "VISION · CRITIQUE": "КӨРУ · САПАНЫ БАҒАЛАУ",
        "REFERENCES": "ДЕРЕККӨЗДЕР", "NARRATION": "ДИКТОР ДАУЫСЫ", "LEARNING": "ОҚУ", "PATHS": "ЖОЛДАР",
        "Provider": "Провайдер", "API key": "API кілті", "Base URL": "Негізгі URL", "Model": "Модель",
        "Model timeout": "Модельді күту уақыты", "Timeout retries": "Қайталау саны", "Test connection": "Қосылымды тексеру",
        "Render engine": "Рендер қозғалтқышы", "Default quality": "Әдепкі сапа", "Render mode": "Рендер режимі",
        "GitHub render repo": "GitHub рендер репозиторийі", "GitHub token": "GitHub токені", "Workflow file": "Workflow файлы",
        "Render branch": "Рендер тармағы", "Auto cloud threshold": "Бұлтқа автоматты жіберу шегі", "Test cloud render": "Бұлтты рендерді тексеру",
        "View render ledger": "Рендер тарихын көру", "Get token": "Токен алу", "Vision model": "Көру моделі",
        "Voice": "Диктор дауысы", "Review intervals (days)": "Қайталау аралығы (күн)", "Library path": "Кітапхана бумасы",
        "Data path": "Деректер бумасы", "Cancel": "Болдырмау", "Save": "Сақтау", "Browse…": "Шолу…",
        "Custom endpoint": "Теңшелетін сервер", "Local Ollama": "Жергілікті Ollama", "No AI (offline)": "ЖИ жоқ (офлайн)",
        "No automatic retries": "Автоматты қайталау жоқ", "Retry once": "Бір рет қайталау", "Manim (Community)": "Manim (Community)",
        "Draft (480p)": "Нобай (480p)", "Standard (720p · 30 fps)": "Қалыпты (720p · 30 кадр/сек)", "High (1080p)": "Жоғары (1080p)",
        "Local": "Жергілікті", "Cloud": "Бұлт", "Auto": "Автоматты",
        "When set, rendered videos are watched frame-by-frame and revised toward a quality rubric; blank skips the critique loop.": "Көрсетілсе, дайын бейне кадр бойынша тексеріліп, сапа өлшеміне сай түзетіледі. Бос қалса, тексеру жүргізілмейді.",
        "Multi-candidate quality (auto): render extra takes only when the first is weak": "Бірнеше нұсқаны бағалау: алғашқы рендер әлсіз болса ғана қосымша нұсқалар жасалады",
        "When a vision model is set, PhysLab renders one scene and only generates more candidates (picking the best) if that first render scores low — so most runs still cost a single render. No effect without a vision model.": "Көру моделі таңдалса, PhysLab алдымен бір нұсқаны рендерлейді. Бағасы төмен болса, қосымша нұсқалар жасап, ең жақсысын таңдайды. Көру моделі болмаса, бұл баптау әсер етпейді.",
        "Pull web references (Wikipedia) alongside the local library": "Жергілікті кітапханамен бірге веб-дереккөздерді (Wikipedia) іздеу",
        "Fetches relevant encyclopedia intros for each run; fail-soft and time-boxed, so it never blocks a solve. Turn off for offline use.": "Әр есепке қатысты энциклопедия түсіндірмелерін іздейді. Уақыты шектелген, қате болса есепті тоқтатпайды. Офлайн режимде өшіріңіз.",
        "Add a voiceover fit to the rendered video": "Дайын бейнеге сай диктор дауысын қосу",
        "Narration is derived from the finished animation, then time-fit to the video (whole-clip sync). Needs edge-tts; fail-soft — a problem just keeps the silent render.": "Диктор мәтіні дайын анимацияға бейімделіп, бейнемен синхрондалады. edge-tts қажет. Қате болса, бейне дыбыссыз сақталады.",
        "Days between successful retrieval checks, as comma-separated values (1 to 365).": "Дұрыс жауаптан кейін қайталау аралығы, күнмен және үтір арқылы (1–365).",
        "Where indexed textbooks are stored": "Индекстелген оқулықтар сақталатын бума", "Where cache and history are stored": "Кэш пен тарих сақталатын бума",
        "Saved to the app config and applied to the next pipeline run. Environment variables (AETHERLAB_*) still take precedence.": "Баптаулар келесі іске қосылғанда қолданылады. AETHERLAB_* орта айнымалыларының басымдығы сақталады.",
        "Local Ollama runs models on this computer — free, private, no key.\nNo AI still solves with built-in templates and textbook references.": "Жергілікті Ollama модельді осы компьютерде іске қосады: тегін, жеке және кілт қажет емес.\nЖИ өшірулі болса да, кіріктірілген үлгілер мен оқулықтар қолжетімді.",
        "Scene generation and rendering both target Manim Community.": "Сахнаны құрастыру мен рендер үшін Manim Community қолданылады.",
        "Local renders on this computer. Cloud uses GitHub Actions. Auto uses cloud only for heavy scenes.": "Жергілікті режим осы компьютерде рендерлейді. Бұлт GitHub Actions қызметін қолданады. Автоматты режим бұлтты тек күрделі сахналарға қосады.",
        "Show / hide": "Көрсету / жасыру", "Lesson and practice language": "Сабақ пен жаттығу тілі",
    },
    "ru": {
        "Settings": "Настройки", "PROVIDER": "ПРОВАЙДЕР", "RENDERING": "РЕНДЕРИНГ", "VISION · CRITIQUE": "ВИЗУАЛЬНАЯ ОЦЕНКА",
        "REFERENCES": "ИСТОЧНИКИ", "NARRATION": "ОЗВУЧКА", "LEARNING": "ОБУЧЕНИЕ", "PATHS": "ПУТИ",
        "Provider": "Провайдер", "API key": "Ключ API", "Base URL": "Базовый URL", "Model": "Модель",
        "Model timeout": "Тайм-аут модели", "Timeout retries": "Повторы при тайм-ауте", "Test connection": "Проверить подключение",
        "Render engine": "Движок рендера", "Default quality": "Качество по умолчанию", "Render mode": "Режим рендера",
        "GitHub render repo": "Репозиторий рендера GitHub", "GitHub token": "Токен GitHub", "Workflow file": "Файл workflow",
        "Render branch": "Ветка рендера", "Auto cloud threshold": "Порог облачного рендера", "Test cloud render": "Проверить облачный рендер",
        "View render ledger": "Журнал рендеров", "Get token": "Получить токен", "Vision model": "Модель для анализа видео",
        "Voice": "Голос", "Review intervals (days)": "Интервалы повторения (дни)", "Library path": "Папка библиотеки",
        "Data path": "Папка данных", "Cancel": "Отмена", "Save": "Сохранить", "Browse…": "Обзор…",
        "Custom endpoint": "Другой сервер", "Local Ollama": "Локальная Ollama", "No AI (offline)": "Без ИИ (офлайн)",
        "No automatic retries": "Без автоматических повторов", "Retry once": "Повторить один раз", "Manim (Community)": "Manim (Community)",
        "Draft (480p)": "Черновик (480p)", "Standard (720p · 30 fps)": "Обычное (720p · 30 кадров/с)", "High (1080p)": "Высокое (1080p)",
        "Local": "Локально", "Cloud": "Облако", "Auto": "Авто",
        "When set, rendered videos are watched frame-by-frame and revised toward a quality rubric; blank skips the critique loop.": "Если указана модель, готовое видео анализируется покадрово и при необходимости улучшается. Пустое поле отключает проверку.",
        "Multi-candidate quality (auto): render extra takes only when the first is weak": "Несколько вариантов: дополнительные рендеры создаются, только если первый получился слабым",
        "When a vision model is set, PhysLab renders one scene and only generates more candidates (picking the best) if that first render scores low — so most runs still cost a single render. No effect without a vision model.": "С моделью анализа видео PhysLab сначала создаёт один вариант. Если оценка низкая, создаёт ещё несколько и выбирает лучший. Без модели настройка не действует.",
        "Pull web references (Wikipedia) alongside the local library": "Искать материалы в интернете (Wikipedia) вместе с локальной библиотекой",
        "Fetches relevant encyclopedia intros for each run; fail-soft and time-boxed, so it never blocks a solve. Turn off for offline use.": "Ищет подходящие энциклопедические материалы для каждой задачи. Ошибка или тайм-аут не блокируют решение. Для офлайн-режима отключите.",
        "Add a voiceover fit to the rendered video": "Добавить озвучку, синхронизированную с видео",
        "Narration is derived from the finished animation, then time-fit to the video (whole-clip sync). Needs edge-tts; fail-soft — a problem just keeps the silent render.": "Текст озвучки создаётся по готовой анимации и синхронизируется с видео. Нужен edge-tts. При ошибке видео останется без звука.",
        "Days between successful retrieval checks, as comma-separated values (1 to 365).": "Интервалы повторения после правильных ответов, через запятую (1–365 дней).",
        "Where indexed textbooks are stored": "Папка для проиндексированных учебников", "Where cache and history are stored": "Папка для кэша и истории",
        "Saved to the app config and applied to the next pipeline run. Environment variables (AETHERLAB_*) still take precedence.": "Настройки сохраняются и применяются при следующем запуске. Переменные AETHERLAB_* имеют приоритет.",
        "Local Ollama runs models on this computer — free, private, no key.\nNo AI still solves with built-in templates and textbook references.": "Локальная Ollama запускает модель на компьютере: бесплатно, конфиденциально и без ключа.\nБез ИИ доступны встроенные шаблоны и учебники.",
        "Scene generation and rendering both target Manim Community.": "Сцены создаются и рендерятся через Manim Community.",
        "Local renders on this computer. Cloud uses GitHub Actions. Auto uses cloud only for heavy scenes.": "Локальный режим работает на компьютере. Облачный использует GitHub Actions. Авто включает облако только для сложных сцен.",
        "Show / hide": "Показать / скрыть", "Lesson and practice language": "Язык урока и тренировки",
    },
    "en": {},
}


# ────────────────────────────────────────────────────────────────────────────
# Settings Dialog (design: ui_kits SettingsDialog.jsx — screen 07)
# ────────────────────────────────────────────────────────────────────────────


class SettingsDialog(QtWidgets.QDialog):
    """Provider / Rendering / Paths sections with secret + path fields."""

    def __init__(self, settings: AppSettings, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        _install_ui_fonts()
        self._settings = settings
        self._provider_task: BackgroundTask | None = None
        self._cloud_task: BackgroundTask | None = None
        self._github_task: BackgroundTask | None = None
        self.setWindowTitle("Settings")
        self.setMinimumSize(420, 420)
        self.setStyleSheet(AETHERLAB_QSS)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row
        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 14, 14)
        header_layout.setSpacing(8)
        header_layout.addWidget(icons.icon_label("settings", 16, "#65758A"))
        title = QtWidgets.QLabel("Settings")
        title.setStyleSheet("color: #18283D; font-size: 17px; font-weight: 600;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addWidget(header)
        layout.addWidget(self._hairline())

        body = QtWidgets.QWidget()
        body.setObjectName("SettingsBody")
        body.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        body.setStyleSheet("QWidget#SettingsBody { background-color: #FFFFFF; }")
        form = QtWidgets.QVBoxLayout(body)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(12)

        # ── Provider ──
        form.addWidget(self._section("PROVIDER"))

        from aetherlab.core.settings import load_app_config

        app_config = load_app_config()
        self._preset_combo = QtWidgets.QComboBox()
        self._preset_combo.addItems(["Custom endpoint", "Local Ollama", "No AI (offline)"])
        saved_preset = app_config.get("provider_preset", "")
        self._preset_combo.setCurrentIndex(
            {"": 0, "custom": 0, "ollama": 1, "none": 2}.get(saved_preset, 0)
        )
        self._preset_combo.setToolTip(
            "Local Ollama runs models on this computer — free, private, no key.\n"
            "No AI still solves with built-in templates and textbook references."
        )
        form.addLayout(self._labeled("Provider", self._preset_combo))

        editable_key = (
            app_config.get("api_key", "")
            if str(getattr(settings, "api_key_source", "")).startswith("environment:")
            else (settings.openai_api_key or "")
        )
        self._api_key_edit = QtWidgets.QLineEdit(editable_key)
        self._api_key_edit.setObjectName("MonoField")
        self._api_key_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-…")
        form.addLayout(self._labeled("API key", self._secret_row(self._api_key_edit)))

        self._base_url_edit = QtWidgets.QLineEdit(settings.openai_base_url or "")
        self._base_url_edit.setObjectName("MonoField")
        form.addLayout(self._labeled("Base URL", self._base_url_edit))

        self._model_edit = QtWidgets.QLineEdit(settings.llm_model)
        self._model_edit.setObjectName("MonoField")
        form.addLayout(self._labeled("Model", self._model_edit))

        from aetherlab.ui.provider_status import ProviderStatusPanel

        self._provider_status = ProviderStatusPanel(settings, self)
        form.addWidget(self._provider_status)
        self._model_edit.textChanged.connect(self._provider_status.set_model)

        self._llm_timeout = QtWidgets.QSpinBox()
        self._llm_timeout.setRange(5, 900)
        self._llm_timeout.setSuffix(" s")
        self._llm_timeout.setValue(int(settings.llm_timeout_seconds))
        form.addLayout(self._labeled("Model timeout", self._llm_timeout))

        self._llm_retries = QtWidgets.QComboBox()
        self._llm_retries.addItems(["No automatic retries", "Retry once"])
        self._llm_retries.setCurrentIndex(min(1, max(0, settings.llm_max_retries)))
        form.addLayout(self._labeled("Timeout retries", self._llm_retries))

        # Test connection row
        test_row = QtWidgets.QHBoxLayout()
        test_row.setSpacing(8)
        self._test_btn = QtWidgets.QPushButton("Test connection")
        self._test_btn.setObjectName("SecondaryButton")
        self._test_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self._test_btn)
        self._test_result = QtWidgets.QLabel("")
        self._test_result.setStyleSheet("color: #65758A; font-size: 11px;")
        self._test_result.setWordWrap(True)
        test_row.addWidget(self._test_result, 1)
        form.addLayout(test_row)

        self._preset_combo.currentIndexChanged.connect(self._apply_preset)

        # ── Rendering ──
        form.addSpacing(4)
        form.addWidget(self._section("RENDERING"))

        self._engine_combo = QtWidgets.QComboBox()
        self._engine_combo.addItems(["Manim (Community)"])
        self._engine_combo.setToolTip("Scene generation and rendering both target Manim Community.")
        form.addLayout(self._labeled("Render engine", self._engine_combo))

        self._quality_combo = QtWidgets.QComboBox()
        self._quality_combo.addItems(["Draft (480p)", "Standard (720p · 30 fps)", "High (1080p)"])
        from aetherlab.core.settings import load_app_config
        saved_quality = load_app_config().get("default_quality", "m")
        self._quality_combo.setCurrentIndex({"l": 0, "m": 1, "h": 2}.get(saved_quality, 1))
        form.addLayout(self._labeled("Default quality", self._quality_combo))

        self._render_mode_combo = QtWidgets.QComboBox()
        self._render_mode_combo.addItems(["Local", "Cloud", "Auto"])
        self._render_mode_combo.setCurrentIndex(
            {"local": 0, "cloud": 1, "auto": 2}.get(getattr(settings, "render_mode", "local"), 0)
        )
        self._render_mode_combo.setToolTip(
            "Local renders on this computer. Cloud uses GitHub Actions. Auto uses cloud only for heavy scenes."
        )
        form.addLayout(self._labeled("Render mode", self._render_mode_combo))

        self._github_repo_edit = QtWidgets.QLineEdit(getattr(settings, "github_repo", "") or "")
        self._github_repo_edit.setObjectName("MonoField")
        self._github_repo_edit.setPlaceholderText("owner/render-repo")
        form.addLayout(self._labeled("GitHub render repo", self._github_repo_edit))

        self._github_token_edit = QtWidgets.QLineEdit(getattr(settings, "github_token", "") or "")
        self._github_token_edit.setObjectName("MonoField")
        self._github_token_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._github_token_edit.setPlaceholderText("github_pat_…")
        token_row = self._secret_row(self._github_token_edit)
        self._get_token_btn = QtWidgets.QPushButton("Get token")
        self._get_token_btn.setObjectName("SecondaryButton")
        self._get_token_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._get_token_btn.clicked.connect(self._get_github_token)
        token_row.addWidget(self._get_token_btn)
        form.addLayout(self._labeled("GitHub token", token_row))

        self._github_workflow_edit = QtWidgets.QLineEdit(getattr(settings, "github_workflow", "render.yml") or "render.yml")
        self._github_workflow_edit.setObjectName("MonoField")
        form.addLayout(self._labeled("Workflow file", self._github_workflow_edit))
        self._github_branch_edit = QtWidgets.QLineEdit(getattr(settings, "github_branch", "renders") or "renders")
        self._github_branch_edit.setObjectName("MonoField")
        form.addLayout(self._labeled("Render branch", self._github_branch_edit))
        self._cloud_threshold = QtWidgets.QDoubleSpinBox()
        self._cloud_threshold.setRange(1.0, 5.0)
        self._cloud_threshold.setSingleStep(0.25)
        self._cloud_threshold.setValue(float(getattr(settings, "cloud_render_threshold", 3.0) or 3.0))
        form.addLayout(self._labeled("Auto cloud threshold", self._cloud_threshold))
        cloud_row = QtWidgets.QHBoxLayout()
        cloud_row.setSpacing(8)
        self._cloud_test_btn = QtWidgets.QPushButton("Test cloud render")
        self._cloud_test_btn.setObjectName("SecondaryButton")
        self._cloud_test_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._cloud_test_btn.clicked.connect(self._test_cloud_render)
        cloud_row.addWidget(self._cloud_test_btn)
        self._ledger_btn = QtWidgets.QPushButton("View render ledger")
        self._ledger_btn.setObjectName("SecondaryButton")
        self._ledger_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._ledger_btn.clicked.connect(self._open_render_ledger)
        cloud_row.addWidget(self._ledger_btn)
        self._cloud_result = QtWidgets.QLabel("")
        self._cloud_result.setStyleSheet("color: #65758A; font-size: 11px;")
        self._cloud_result.setWordWrap(True)
        cloud_row.addWidget(self._cloud_result, 1)
        form.addLayout(cloud_row)

        # ── Vision · Critique (design v2 §8, new) ──
        form.addSpacing(4)
        form.addWidget(self._section("VISION · CRITIQUE"))

        self._vision_edit = QtWidgets.QLineEdit(settings.vision_model or "")
        self._vision_edit.setObjectName("MonoField")
        self._vision_edit.setPlaceholderText("e.g. gpt-4o, claude-3-5-sonnet (leave blank to disable)")
        form.addLayout(
            self._labeled(
                "Vision model",
                self._vision_edit,
            )
        )
        vision_hint = QtWidgets.QLabel(
            "When set, rendered videos are watched frame-by-frame and revised "
            "toward a quality rubric; blank skips the critique loop."
        )
        vision_hint.setStyleSheet("color: #65758A; font-size: 11px;")
        vision_hint.setWordWrap(True)
        form.addWidget(vision_hint)

        self._auto_tournament_check = QtWidgets.QCheckBox(
            "Multi-candidate quality (auto): render extra takes only when the first is weak"
        )
        self._auto_tournament_check.setChecked(getattr(settings, "auto_tournament", True))
        self._auto_tournament_check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        form.addWidget(self._auto_tournament_check)
        auto_hint = QtWidgets.QLabel(
            "When a vision model is set, PhysLab renders one scene and only "
            "generates more candidates (picking the best) if that first render "
            "scores low — so most runs still cost a single render. No effect "
            "without a vision model."
        )
        auto_hint.setStyleSheet("color: #65758A; font-size: 11px;")
        auto_hint.setWordWrap(True)
        form.addWidget(auto_hint)

        # ── References (design v3: web references) ──
        form.addSpacing(4)
        form.addWidget(self._section("REFERENCES"))
        self._web_refs_check = QtWidgets.QCheckBox(
            "Pull web references (Wikipedia) alongside the local library"
        )
        self._web_refs_check.setChecked(getattr(settings, "web_references", True))
        self._web_refs_check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        form.addWidget(self._web_refs_check)
        web_hint = QtWidgets.QLabel(
            "Fetches relevant encyclopedia intros for each run; fail-soft and "
            "time-boxed, so it never blocks a solve. Turn off for offline use."
        )
        web_hint.setStyleSheet("color: #65758A; font-size: 11px;")
        web_hint.setWordWrap(True)
        form.addWidget(web_hint)

        # ── Narration (narration↔visual sync) ──
        form.addSpacing(4)
        form.addWidget(self._section("NARRATION"))
        self._narration_check = QtWidgets.QCheckBox(
            "Add a voiceover fit to the rendered video"
        )
        self._narration_check.setChecked(getattr(settings, "narration_enabled", False))
        self._narration_check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        form.addWidget(self._narration_check)
        self._tts_voice_edit = QtWidgets.QLineEdit(getattr(settings, "tts_voice", "") or "")
        self._tts_voice_edit.setObjectName("MonoField")
        self._tts_voice_edit.setPlaceholderText("edge-tts voice, e.g. en-US-AndrewMultilingualNeural")
        form.addLayout(self._labeled("Voice", self._tts_voice_edit))
        narr_hint = QtWidgets.QLabel(
            "Narration is derived from the finished animation, then time-fit to "
            "the video (whole-clip sync). Needs edge-tts; fail-soft — a problem "
            "just keeps the silent render."
        )
        narr_hint.setStyleSheet("color: #65758A; font-size: 11px;")
        narr_hint.setWordWrap(True)
        form.addWidget(narr_hint)

        form.addSpacing(4)
        form.addWidget(self._section("LEARNING"))
        self._review_intervals_combo = QtWidgets.QComboBox()
        self._review_intervals_combo.setEditable(True)
        self._review_intervals_combo.addItems(["1,3,7,14", "1,2,4,8", "1,7,14", "1"])
        saved_intervals = str(
            getattr(settings, "review_intervals_days", "1,3,7,14") or "1,3,7,14"
        )
        if self._review_intervals_combo.findText(saved_intervals) < 0:
            self._review_intervals_combo.addItem(saved_intervals)
        self._review_intervals_combo.setCurrentText(saved_intervals)
        self._review_intervals_combo.setToolTip(
            "Days between successful retrieval checks, as comma-separated values (1 to 365)."
        )
        form.addLayout(self._labeled("Review intervals (days)", self._review_intervals_combo))

        # ── Paths ──
        form.addSpacing(4)
        form.addWidget(self._section("PATHS"))

        self._library_edit = QtWidgets.QLineEdit(str(settings.library_path))
        self._library_edit.setObjectName("MonoField")
        form.addLayout(
            self._labeled(
                "Library path",
                self._path_row(self._library_edit, "Where indexed textbooks are stored"),
            )
        )

        self._data_edit = QtWidgets.QLineEdit(str(settings.data_dir))
        self._data_edit.setObjectName("MonoField")
        form.addLayout(
            self._labeled(
                "Data path",
                self._path_row(self._data_edit, "Where cache and history are stored"),
            )
        )

        note = QtWidgets.QLabel(
            "Saved to the app config and applied to the next pipeline run. "
            "Environment variables (AETHERLAB_*) still take precedence."
        )
        note.setStyleSheet("color: #65758A; font-size: 11px;")
        note.setWordWrap(True)
        form.addWidget(note)

        self._settings_scroll = QtWidgets.QScrollArea()
        self._settings_scroll.setWidgetResizable(True)
        self._settings_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._settings_scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._settings_scroll.setStyleSheet(
            "QScrollArea { background: #FFFFFF; border: none; }"
            "QScrollArea > QWidget > QWidget { background: #FFFFFF; }"
        )
        self._settings_scroll.setWidget(body)
        layout.addWidget(self._settings_scroll, 1)
        layout.addWidget(self._hairline())

        # Footer: Cancel / Save
        footer = QtWidgets.QWidget()
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 12)
        footer_layout.addStretch()
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("GhostButton")
        cancel_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        footer_layout.addWidget(save_btn)
        layout.addWidget(footer)
        self._cache_translatable_widgets()
        self.set_language("kk")
        self._fit_to_screen()

    def _cache_translatable_widgets(self) -> None:
        self._translated_widgets = []
        for widget in self.findChildren(QtWidgets.QWidget):
            row = {"widget": widget}
            if isinstance(widget, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
                row["text"] = widget.text()
            if isinstance(widget, QtWidgets.QComboBox):
                row["items"] = [widget.itemText(index) for index in range(widget.count())]
            if hasattr(widget, "toolTip"):
                row["tooltip"] = widget.toolTip()
            if isinstance(widget, QtWidgets.QLineEdit):
                row["placeholder"] = widget.placeholderText()
            self._translated_widgets.append(row)

    def set_language(self, language: str) -> None:
        self._language = language if language in _SETTINGS_COPY else "kk"
        copy = _SETTINGS_COPY[self._language]
        for row in self._translated_widgets:
            widget = row["widget"]
            if isinstance(widget, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
                original = row.get("text", "")
                widget.setText(copy.get(original, original))
            if isinstance(widget, QtWidgets.QComboBox):
                for index, original in enumerate(row.get("items", [])):
                    if index < widget.count():
                        widget.setItemText(index, copy.get(original, original))
            if "tooltip" in row and row["tooltip"]:
                widget.setToolTip(copy.get(row["tooltip"], row["tooltip"]))
            if "placeholder" in row and row["placeholder"]:
                widget.setPlaceholderText(copy.get(row["placeholder"], row["placeholder"]))
        self._provider_status.set_language(self._language)
        self.setWindowTitle(copy.get("Settings", "Settings"))

    def _fit_to_screen(self) -> None:
        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            width = min(920, max(520, int(geo.width() * 0.68)))
            height = min(780, max(420, int(geo.height() * 0.86)))
            min_width = min(520, max(420, int(geo.width() * 0.45)))
            min_height = min(480, max(360, int(geo.height() * 0.55)))
        else:
            width, height = 860, 720
            min_width, min_height = 420, 420
        self.setMinimumSize(min_width, min_height)
        self.resize(width, height)

    def _hairline(self) -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #D8E1EC;")
        return line

    def _section(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("SettingsSection")
        return label

    def _labeled(self, text: str, field: QtWidgets.QWidget | QtWidgets.QLayout) -> QtWidgets.QVBoxLayout:
        box = QtWidgets.QVBoxLayout()
        box.setSpacing(4)
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("color: #65758A; font-size: 12px; font-weight: 500;")
        box.addWidget(label)
        if isinstance(field, QtWidgets.QLayout):
            box.addLayout(field)
        else:
            box.addWidget(field)
        return box

    def _secret_row(self, edit: QtWidgets.QLineEdit) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(edit, 1)
        reveal = QtWidgets.QPushButton()
        reveal.setIcon(icons.icon("eye", 14, "#65758A"))
        reveal.setFixedSize(32, 32)
        reveal.setCheckable(True)
        reveal.setToolTip("Show / hide")
        reveal.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #D8E1EC; border-radius: 8px; }"
            "QPushButton:hover { border-color: #A5B6CB; }"
        )
        reveal.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        def _toggle(checked: bool) -> None:
            edit.setEchoMode(
                QtWidgets.QLineEdit.EchoMode.Normal
                if checked
                else QtWidgets.QLineEdit.EchoMode.Password
            )
            reveal.setIcon(icons.icon("eye-off" if checked else "eye", 14, "#65758A"))

        reveal.toggled.connect(_toggle)
        row.addWidget(reveal)
        return row

    def _path_row(self, edit: QtWidgets.QLineEdit, hint: str) -> QtWidgets.QHBoxLayout:
        edit.setToolTip(hint)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(edit, 1)
        browse = QtWidgets.QPushButton("Browse…")
        browse.setObjectName("SecondaryButton")
        browse.setIcon(icons.icon("folder-open", 13, "#65758A"))
        browse.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        def _browse() -> None:
            folder = QtWidgets.QFileDialog.getExistingDirectory(self, hint, edit.text())
            if folder:
                edit.setText(folder)

        browse.clicked.connect(_browse)
        row.addWidget(browse)
        return row

    def _apply_preset(self, index: int) -> None:
        """Fill provider fields when the user picks a preset."""
        from aetherlab.core.settings import OLLAMA_OPENAI_BASE_URL

        if index == 1:  # Local Ollama
            from aetherlab.services.providers import detect_ollama

            self._base_url_edit.setText(OLLAMA_OPENAI_BASE_URL)
            if not self._api_key_edit.text().strip():
                self._api_key_edit.setText("ollama")
            models = detect_ollama()
            if models:
                self._model_edit.setText(models[0])
                self._model_edit.setToolTip("Installed: " + ", ".join(models[:12]))
                self._test_result.setStyleSheet("color: #26725C; font-size: 11px;")
                self._test_result.setText(f"Ollama detected — {len(models)} model(s) installed.")
            else:
                self._test_result.setStyleSheet("color: #8A5A24; font-size: 11px;")
                self._test_result.setText(
                    "Ollama not detected. Install from ollama.com, then run "
                    "`ollama pull qwen2.5:7b` and reopen Settings."
                )
        elif index == 2:  # No AI (offline)
            self._test_result.setStyleSheet("color: #65758A; font-size: 11px;")
            self._test_result.setText(
                "Offline mode: built-in domain templates + textbook references, no LLM."
            )

    def _test_connection(self) -> None:
        from dataclasses import replace

        from aetherlab.services.providers import test_connection

        if self._provider_task and self._provider_task.is_running:
            return
        self._test_btn.setEnabled(False)
        self._test_result.setStyleSheet("color: #65758A; font-size: 11px;")
        self._test_result.setText("Testing…")
        probe = replace(
            self._settings,
            openai_api_key=self._api_key_edit.text().strip() or None,
            openai_base_url=self._base_url_edit.text().strip() or None,
            llm_model=self._model_edit.text().strip() or self._settings.llm_model,
        )
        self._provider_task = BackgroundTask(
            lambda _cancel, _progress: test_connection(probe)
        )
        self._provider_task.succeeded.connect(self._on_provider_test_result)
        # Bound methods, not lambdas: PyQt drops a bound-method connection when
        # the dialog is destroyed, so a finished signal still queued from a
        # closed dialog can never run against its deleted widgets. A lambda has
        # no receiver; one queued from an earlier dialog crashed the CI runner
        # with an access violation (F157, 2026-10-01).
        self._provider_task.failed.connect(self._on_provider_test_failed)
        self._provider_task.finished.connect(self._on_provider_task_finished)
        self._provider_task.start()

    def _on_provider_test_failed(self, message: str) -> None:
        self._on_provider_test_result((False, f"Connection failed: {message}"))

    def _on_provider_task_finished(self) -> None:
        self._test_btn.setEnabled(True)

    def _on_provider_test_result(self, result: object) -> None:
        ok, message = result if isinstance(result, tuple) and len(result) == 2 else (
            False,
            "Connection test returned an invalid result.",
        )
        self._test_result.setStyleSheet(
            f"color: {'#26725C' if ok else '#AC4055'}; font-size: 11px;"
        )
        self._test_result.setText(str(message))

    def _open_render_ledger(self) -> None:
        """Open the read-only render-farm dashboard for this data dir."""
        from aetherlab.ui.ledger_panel import RenderLedgerPanel

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Render farm")
        dialog.resize(780, 540)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(RenderLedgerPanel(self._settings.data_dir / "render_ledger.json", dialog))
        dialog.exec()

    def _test_cloud_render(self) -> None:
        from dataclasses import replace

        from aetherlab.services.render_backend import (
            CloudRenderBackend,
            GitHubActionsClient,
            _mask,
            provision_render_repo,
        )

        if self._cloud_task and self._cloud_task.is_running:
            return
        probe = replace(
            self._settings,
            render_mode={0: "local", 1: "cloud", 2: "auto"}.get(self._render_mode_combo.currentIndex(), "local"),
            github_repo=self._github_repo_edit.text().strip(),
            github_token=self._github_token_edit.text().strip(),
            github_workflow=self._github_workflow_edit.text().strip() or "render.yml",
            github_branch=self._github_branch_edit.text().strip() or "renders",
            cloud_render_threshold=float(self._cloud_threshold.value()),
        )
        self._cloud_test_btn.setEnabled(False)
        self._cloud_result.setStyleSheet("color: #65758A; font-size: 11px;")
        self._cloud_result.setText("Setting up render repo…")

        def setup_cloud(cancel, _progress):
            backend = CloudRenderBackend(probe)
            ok, message = backend.available()
            if ok and not cancel.is_set():
                try:
                    client = GitHubActionsClient.from_settings(probe)
                    client._request("GET", f"/repos/{client.owner}/{client.repo}")
                    if cancel.is_set():
                        return False, "Cloud setup cancelled."
                    status = provision_render_repo(
                        client,
                        branch=probe.github_branch,
                        workflow=probe.github_workflow,
                    )
                    message = f"Cloud rendering is ready — {status}"
                except Exception as exc:  # noqa: BLE001
                    ok = False
                    message = f"Cloud setup failed: {_mask(str(exc))[:180]}"
            return ok, message

        self._cloud_task = BackgroundTask(setup_cloud)
        self._cloud_task.succeeded.connect(self._on_cloud_test_result)
        self._cloud_task.failed.connect(self._on_cloud_test_failed)
        self._cloud_task.finished.connect(self._on_cloud_task_finished)
        self._cloud_task.start()

    def _on_cloud_test_failed(self, message: str) -> None:
        self._on_cloud_test_result((False, f"Cloud setup failed: {message}"))

    def _on_cloud_task_finished(self) -> None:
        self._cloud_test_btn.setEnabled(True)

    def _on_cloud_test_result(self, result: object) -> None:
        ok, message = result if isinstance(result, tuple) and len(result) == 2 else (
            False,
            "Cloud setup returned an invalid result.",
        )
        self._cloud_result.setStyleSheet(
            f"color: {'#26725C' if ok else '#AC4055'}; font-size: 11px;"
        )
        self._cloud_result.setText(str(message))

    def _get_github_token(self) -> None:
        client_id = getattr(self._settings, "github_oauth_client_id", "") or ""
        if not client_id:
            self._cloud_result.setStyleSheet("color: #8A5A24; font-size: 11px;")
            self._cloud_result.setText(
                "Device login needs a PhysLab GitHub OAuth client id. Set AETHERLAB_GITHUB_CLIENT_ID or paste a fine-grained token."
            )
            return
        if self._github_task and self._github_task.is_running:
            return

        def authorize(cancel, report):
            import time

            from aetherlab.services.render_backend import (
                poll_github_device_token,
                request_github_device_code,
            )

            device = request_github_device_code(client_id)
            if not isinstance(device, dict):
                raise RuntimeError("GitHub returned an invalid device-code response.")
            device_code = str(device.get("device_code", ""))
            user_code = str(device.get("user_code", ""))
            url = str(device.get("verification_uri") or "https://github.com/login/device")
            if not device_code or not user_code:
                raise RuntimeError("GitHub device response omitted a required code.")
            report((url, user_code))
            interval = max(1, min(30, int(device.get("interval", 5) or 5)))
            expires = max(1, int(device.get("expires_in", 900) or 900))
            deadline = time.monotonic() + min(expires, 180)
            while time.monotonic() < deadline:
                if cancel.wait(interval):
                    return None
                token = poll_github_device_token(client_id, device_code)
                if not isinstance(token, dict):
                    raise RuntimeError("GitHub returned an invalid token response.")
                access_token = token.get("access_token")
                if access_token:
                    return str(access_token)
                error = str(token.get("error", ""))
                if error == "slow_down":
                    interval = min(60, interval + 5)
                    continue
                if error != "authorization_pending":
                    raise RuntimeError(
                        str(token.get("error_description") or error or "unknown error")
                    )
            raise TimeoutError("GitHub device login timed out.")

        self._get_token_btn.setEnabled(False)
        self._cloud_result.setStyleSheet("color: #65758A; font-size: 11px;")
        self._cloud_result.setText("Requesting GitHub device code…")
        self._github_task = BackgroundTask(authorize)
        self._github_task.progress.connect(self._on_github_device_code)
        self._github_task.succeeded.connect(self._on_github_token)
        self._github_task.failed.connect(self._on_github_login_failed)
        self._github_task.finished.connect(self._on_github_task_finished)
        self._github_task.start()

    def _on_github_task_finished(self) -> None:
        self._get_token_btn.setEnabled(True)

    def _on_github_device_code(self, payload: object) -> None:
        import webbrowser

        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        url, code = str(payload[0]), str(payload[1])
        self._cloud_result.setStyleSheet("color: #65758A; font-size: 11px;")
        self._cloud_result.setText(f"Enter code {code} at {url}. Waiting for authorization…")
        webbrowser.open(url)

    def _on_github_token(self, token: object) -> None:
        if not token:
            return
        self._github_token_edit.setText(str(token))
        self._cloud_result.setStyleSheet("color: #26725C; font-size: 11px;")
        self._cloud_result.setText("GitHub token received.")

    def _on_github_login_failed(self, message: str) -> None:
        self._cloud_result.setStyleSheet("color: #AC4055; font-size: 11px;")
        self._cloud_result.setText(f"GitHub device login failed: {message[:160]}")

    def _cancel_background_tasks(self) -> None:
        for task in (self._provider_task, self._cloud_task, self._github_task):
            if task is not None:
                task.cancel()

    def done(self, result: int) -> None:
        self._cancel_background_tasks()
        super().done(result)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        self._cancel_background_tasks()
        super().closeEvent(event)

    def get_settings(self) -> dict:
        quality_map = {0: "l", 1: "m", 2: "h"}
        preset_map = {0: "custom", 1: "ollama", 2: "none"}
        mode_map = {0: "local", 1: "cloud", 2: "auto"}
        return {
            "provider_preset": preset_map.get(self._preset_combo.currentIndex(), "custom"),
            "model": self._model_edit.text().strip(),
            "llm_timeout_seconds": str(self._llm_timeout.value()),
            "llm_max_retries": str(self._llm_retries.currentIndex()),
            "api_key": self._api_key_edit.text().strip() or None,
            "base_url": self._base_url_edit.text().strip() or None,
            "library_path": self._library_edit.text().strip(),
            "data_dir": self._data_edit.text().strip(),
            "default_quality": quality_map.get(self._quality_combo.currentIndex(), "m"),
            "render_mode": mode_map.get(self._render_mode_combo.currentIndex(), "local"),
            "github_repo": self._github_repo_edit.text().strip(),
            "github_token": self._github_token_edit.text().strip() or None,
            "github_workflow": self._github_workflow_edit.text().strip() or "render.yml",
            "github_branch": self._github_branch_edit.text().strip() or "renders",
            "cloud_render_threshold": str(float(self._cloud_threshold.value())),
            "vision_model": self._vision_edit.text().strip() or None,
            "web_references": self._web_refs_check.isChecked(),
            "narration_enabled": self._narration_check.isChecked(),
            "auto_tournament": self._auto_tournament_check.isChecked(),
            "tts_voice": self._tts_voice_edit.text().strip() or None,
            "review_intervals_days": self._review_intervals_combo.currentText().strip(),
        }


# ────────────────────────────────────────────────────────────────────────────
# Main Window
# ────────────────────────────────────────────────────────────────────────────


class _OllamaProbe(QtCore.QThread):
    """Background check for a locally running Ollama (never blocks the UI)."""

    found = QtCore.pyqtSignal(list)

    def run(self) -> None:
        from aetherlab.services.providers import detect_ollama

        models = detect_ollama()
        if models:
            self.found.emit(models)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        _install_ui_fonts()
        self.settings = settings
        self.worker: PipelineWorker | None = None
        self._export_task: BackgroundTask | None = None
        self._close_pending = False
        self._last_result: PipelineResult | None = None
        self._active_solver: SolverResult | None = None
        self._has_result = False
        self._timeline_started = False

        self.setObjectName("MainWindow")
        self.setWindowTitle("PhysLab")
        self.setWindowIcon(icons.icon("atom", 24, "#486A91"))

        # Responsive sizing (#15)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w = min(1500, int(geo.width() * 0.92))
            h = min(950, int(geo.height() * 0.92))
            min_w = min(960, max(640, int(geo.width() * 0.72)))
            min_h = min(640, max(460, int(geo.height() * 0.72)))
        else:
            w, h = 1500, 950
            min_w, min_h = 720, 520
        self.resize(w, h)
        self.setMinimumSize(min_w, min_h)
        self.setStyleSheet(AETHERLAB_QSS)

        # ── Components ──
        self.title_bar = TitleBar()
        self.sidebar = SidebarNav()
        self.toast = Toast()
        self.stepper = PipelineStepper()
        self.command_bar = CommandBar()
        # Apply the saved Settings default: without this a restart always falls
        # back to Standard (m) even when the user saved Draft or High.
        from aetherlab.core.settings import load_app_config

        self.command_bar.set_quality(load_app_config().get("default_quality", "m"))

        current_language = self.command_bar.get_language()
        from aetherlab.services.course_mode import CourseProgressStore
        from aetherlab.services.student_profiles import StudentProfileStore

        default_profile_name = {
            "kk": "Оқушы 1",
            "ru": "Ученик 1",
            "en": "Learner 1",
        }[current_language]
        self.student_profile_store = StudentProfileStore(
            self.settings.data_dir, default_name=default_profile_name
        )
        self.active_student_profile = self.student_profile_store.active_profile()
        from aetherlab.services.ai_help_quota import DAILY_AI_HELP_LIMIT
        self._daily_ai_help_limit = DAILY_AI_HELP_LIMIT
        self._update_ai_help_quota()
        self.ent_progress_path = self.active_student_profile.progress_path
        self.course_progress = CourseProgressStore(
            self.active_student_profile.course_progress_path,
            review_intervals_days=self.settings.review_intervals_days,
        )
        self.student_dashboard = StudentDashboard(
            self.ent_progress_path,
            language=current_language,
            profile_name=self.active_student_profile.name,
        )
        self._dashboard_refresh_date = date.today()
        self.student_dashboard.set_profile(
            self.active_student_profile.name,
            self.active_student_profile.avatar_path,
        )
        self.title_bar.set_profile(
            self.active_student_profile.name,
            self.active_student_profile.avatar_path,
        )
        self.topic_catalog = TopicCatalogView(
            self.ent_progress_path, language=current_language
        )
        self.progress_overview = ProgressOverview(
            self.ent_progress_path, language=current_language
        )

        self.empty_view = EmptyStateView()
        self.running_view = RunningView()
        self.analysis_panel = AnalysisPanel()
        self.reference_panel = ReferencePanel()
        self.simulation_panel = SimulationPanel()
        self.parameter_dock = ParameterDock()
        self.library_panel = LibraryPanel()
        self.history_panel = HistoryPanel()
        self.lesson_view = LessonView()
        self.lesson_worker: LessonWorker | None = None
        self._pending_lesson_answers: dict = {}

        # ── Solve page: derivation | references ──
        solve_page = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        solve_page.addWidget(self.analysis_panel)
        solve_page.addWidget(self.reference_panel)
        solve_page.setSizes([int(w * 0.55), int(w * 0.35)])
        solve_page.setCollapsible(0, False)

        # ── Scene page: simulation | parameter side panel ──
        scene_page = QtWidgets.QWidget()
        scene_layout = QtWidgets.QHBoxLayout(scene_page)
        scene_layout.setContentsMargins(0, 0, 0, 0)
        scene_layout.setSpacing(0)
        scene_layout.addWidget(self.simulation_panel, 1)
        self._param_side = QtWidgets.QFrame()
        self._param_side.setMinimumWidth(220)
        self._param_side.setMaximumWidth(320)
        self._param_side.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._param_side.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border-left: 1px solid #D8E1EC; }"
        )
        side_layout = QtWidgets.QVBoxLayout(self._param_side)
        side_layout.setContentsMargins(0, 8, 0, 8)
        side_layout.addWidget(self.parameter_dock)
        side_layout.addStretch()
        scene_layout.addWidget(self._param_side)
        self._param_side.hide()

        # ── Workspace stack (one workspace, rail-driven) ──
        self._workspace = QtWidgets.QStackedWidget()
        # Transparent so the dark graphite backdrop shows through card gaps.
        self._workspace.setStyleSheet("QStackedWidget { background: transparent; }")
        self._workspace.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self._workspace.addWidget(self.empty_view)      # 0
        self._workspace.addWidget(self.running_view)    # 1
        self._workspace.addWidget(solve_page)           # 2
        self._workspace.addWidget(scene_page)           # 3
        self._workspace.addWidget(self.library_panel)   # 4
        self._workspace.addWidget(self.history_panel)   # 5
        self._workspace.addWidget(self.lesson_view)     # 6
        self._workspace.addWidget(self.student_dashboard)  # 7
        self._workspace.addWidget(self.topic_catalog)      # 8
        self._workspace.addWidget(self.progress_overview)  # 9
        self._workspace.setCurrentIndex(PAGE_STUDENT_HOME)

        # ── Timeline strip (hidden until first run) ──
        self._timeline_strip = QtWidgets.QWidget()
        strip_layout = QtWidgets.QVBoxLayout(self._timeline_strip)
        strip_layout.setContentsMargins(28, 8, 28, 4)
        strip_layout.addWidget(self.stepper)
        self._timeline_strip.setStyleSheet("border-bottom: 1px solid #D8E1EC;")
        self._timeline_strip.hide()

        # ── Toast area ──
        toast_area = QtWidgets.QWidget()
        toast_layout = QtWidgets.QVBoxLayout(toast_area)
        toast_layout.setContentsMargins(20, 8, 20, 0)
        toast_layout.addWidget(self.toast)

        # ── Center column: toast / timeline / workspace / command bar ──
        center = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(toast_area)
        center_layout.addWidget(self._timeline_strip)
        # Deep graphite backdrop behind the workspace.
        from aetherlab.ui.widgets import BlueprintBackdrop
        center_layout.addWidget(BlueprintBackdrop(self._workspace), 1)
        center_layout.addWidget(self.command_bar)
        self.command_bar.hide()

        # ── Shell: title bar over (rail | center) ──
        shell = QtWidgets.QWidget()
        shell_layout = QtWidgets.QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(center, 1)

        root = QtWidgets.QWidget()
        root.setObjectName("Root")
        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.title_bar)
        root_layout.addWidget(shell, 1)
        self.setCentralWidget(root)

        self._build_shortcuts()
        self._connect_signals()

        # Initial state
        self.sidebar.set_language(current_language)
        self.empty_view.set_language(current_language)
        self.title_bar.set_language(current_language)
        self.toast.set_language(current_language)
        self.stepper.set_language(current_language)
        self.command_bar.set_language(current_language)
        self.simulation_panel.set_language(current_language)
        self.library_panel.set_language(current_language)
        self.history_panel.set_language(current_language)
        self.lesson_view.set_language(current_language)
        self.title_bar.set_page_title(self.sidebar.label_for(0))
        self.sidebar.set_result_available(False)
        self.library_panel.set_settings(settings)
        self.empty_view.set_status(
            bool(settings.openai_api_key),
            settings.llm_model,
            self.library_panel.library_file_count(),
        )
        self.history_panel.init_persistence(settings.data_dir / "history.sqlite3")

        provider_note = settings.llm_model if settings.openai_api_key else "No API key"
        self.statusBar().showMessage(f"PhysLab ready · {provider_note}")

        self._ai_quota_timer = QtCore.QTimer(self)
        self._ai_quota_timer.setInterval(60_000)
        self._ai_quota_timer.timeout.connect(self._refresh_ai_help_quota)
        self._ai_quota_timer.start()

        # When no provider is configured, quietly look for a local Ollama and
        # offer one-click local AI on the empty state.
        self._ollama_models: list[str] = []
        if not settings.openai_api_key:
            self._ollama_probe = _OllamaProbe(self)
            self._ollama_probe.found.connect(self._on_ollama_found)
            self._ollama_probe.start()
        self._apply_responsive_layout()

    # ── wiring ──

    def _build_shortcuts(self) -> None:
        sc_submit = QtGui.QShortcut("Ctrl+Return", self)
        sc_submit.activated.connect(self.command_bar._submit)

        sc_toggle_code = QtGui.QShortcut("Ctrl+Shift+C", self)
        sc_toggle_code.activated.connect(self._toggle_code_view)

        for i in range(len(SidebarNav._ITEMS)):
            sc = QtGui.QShortcut(f"Ctrl+{i + 1}", self)
            sc.activated.connect(lambda idx=i: self.sidebar.select(idx))

        sc_cancel = QtGui.QShortcut("Escape", self)
        sc_cancel.activated.connect(self._cancel_pipeline)

        sc_reset = QtGui.QShortcut("Ctrl+0", self)
        sc_reset.activated.connect(self.simulation_panel._live_canvas.reset_view)

        sc_settings = QtGui.QShortcut("Ctrl+,", self)
        sc_settings.activated.connect(self._open_settings)

    def _connect_signals(self) -> None:
        self.sidebar.item_selected.connect(self._on_sidebar_select)
        self.title_bar.settings_requested.connect(self._open_settings)
        self.title_bar.language_changed.connect(self._on_title_language_changed)
        self.title_bar.profile_requested.connect(self._manage_student_profiles)
        self.command_bar._language.currentIndexChanged.connect(
            self._on_student_language_changed
        )

        self.command_bar.submitted.connect(self.start_pipeline)
        self.command_bar.learn_requested.connect(self.start_lesson)
        self.command_bar.practice_requested.connect(self.open_exam_practice)
        self.command_bar.cancel_requested.connect(self._cancel_pipeline)
        self.lesson_view.export_requested.connect(self._export_study_guide)
        self.lesson_view.share_bundle_requested.connect(self._export_lesson_bundle)
        self.lesson_view.study_pdf_requested.connect(self._open_study_pdf)
        self.lesson_view.quiz_answered.connect(self._record_lesson_quiz_answer)
        self.lesson_view.quiz_save_retry_requested.connect(self._retry_lesson_quiz_answer)
        self.lesson_view.review_due_clicked.connect(self._review_due_questions)
        self.lesson_view.regenerate_requested.connect(self.regenerate_lesson)
        self.stepper.cancel_requested.connect(self._cancel_pipeline)

        self.history_panel.prompt_selected.connect(self.start_pipeline)
        self.library_panel.status_message.connect(self.statusBar().showMessage)

        # Empty-state calls to action
        self.empty_view.example_picked.connect(self._prefill_prompt)
        self.empty_view.ent_requested.connect(
            lambda: self.open_exam_practice(self.command_bar.get_language())
        )
        self.empty_view.ollama_requested.connect(self._enable_ollama)
        self.empty_view.settings_requested.connect(self._open_settings)
        self.empty_view.library_requested.connect(lambda: self.sidebar.select(5))

        self.student_dashboard.profile_requested.connect(self._manage_student_profiles)
        self.student_dashboard.leaderboard_requested.connect(self._open_school_leaderboard)
        self.student_dashboard.plan_settings_requested.connect(
            lambda: self.open_exam_practice(self.command_bar.get_language())
        )
        self.student_dashboard.weekly_mock_requested.connect(
            lambda: self.open_exam_practice(
                self.command_bar.get_language(), start_mode="timed"
            )
        )
        self.student_dashboard.learn_topic_requested.connect(self._start_ent_topic_lesson)
        self.student_dashboard.topics_requested.connect(lambda: self.sidebar.select(1))
        self.student_dashboard.progress_requested.connect(lambda: self.sidebar.select(3))
        self.student_dashboard.mistakes_requested.connect(
            lambda: self.open_exam_practice(self.command_bar.get_language(), review_mistakes=True)
        )
        self.student_dashboard.practice_topic_requested.connect(
            lambda topic_id: self.open_exam_practice(
                self.command_bar.get_language(), topic_id=topic_id
            )
        )
        self.topic_catalog.learn_topic_requested.connect(self._start_ent_topic_lesson)
        self.topic_catalog.practice_topic_requested.connect(
            lambda topic_id: self.open_exam_practice(
                self.command_bar.get_language(), topic_id=topic_id
            )
        )
        self.progress_overview.mistakes_requested.connect(
            lambda: self.open_exam_practice(self.command_bar.get_language(), review_mistakes=True)
        )
        self.progress_overview.practice_requested.connect(
            lambda: self.open_exam_practice(self.command_bar.get_language())
        )

        # In-context exports (design: actions live on the content, no menu bar)
        self.analysis_panel.export_latex_requested.connect(self._export_latex)
        self.analysis_panel.export_pdf_requested.connect(self._export_pdf)
        self.simulation_panel.export_scene_requested.connect(self._export_scene)
        self.simulation_panel.save_video_requested.connect(self._save_video)
        self.simulation_panel.export_gif_requested.connect(self._export_gif)

        # Toast details opens the traceback viewer
        self.toast.details_requested.connect(self.simulation_panel._show_error_details)

        # Parameter propagation
        self.parameter_dock.parameter_changed.connect(
            self.simulation_panel.apply_parameter_update
        )
        self.parameter_dock.parameter_changed.connect(
            self.analysis_panel.update_variable
        )
        self.simulation_panel.parameter_changed.connect(
            self.parameter_dock.update_variable
        )
        self.simulation_panel.phase_toggled.connect(
            self.simulation_panel.toggle_phase
        )

    def _apply_responsive_layout(self) -> None:
        """Keep the scene drawer usable without letting it crowd the stage."""
        if not hasattr(self, "_param_side"):
            return
        width = max(self.width(), self.minimumWidth())
        if hasattr(self, "sidebar"):
            self.sidebar.set_expanded(width >= 1320)
        side_width = max(220, min(320, int(width * 0.24)))
        if width < 900:
            side_width = 220
        self._param_side.setFixedWidth(side_width)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _prefill_prompt(self, prompt: str) -> None:
        self.command_bar.input.setText(prompt)
        self.command_bar.input.setFocus()

    def _on_ollama_found(self, models: list) -> None:
        self._ollama_models = list(models)
        if not self.settings.openai_api_key:
            self.empty_view.offer_ollama(len(self._ollama_models))
            self.statusBar().showMessage(
                f"Ollama detected — {len(self._ollama_models)} local model(s) available."
            )

    def _enable_ollama(self) -> None:
        """One-click local AI: persist the Ollama preset and reload settings."""
        from aetherlab.core.settings import (
            OLLAMA_OPENAI_BASE_URL,
            load_settings,
            save_app_config,
        )

        model = self._ollama_models[0] if self._ollama_models else ""
        try:
            save_app_config(
                {
                    "provider_preset": "ollama",
                    "model": model,
                    "base_url": OLLAMA_OPENAI_BASE_URL,
                    "api_key": "ollama",
                }
            )
        except (OSError, ValueError):
            self._report_settings_save_failure()
            return
        self.settings = load_settings()
        self._refresh_empty_status()
        self.toast.show_message(
            "success",
            f"Local AI enabled via Ollama ({self.settings.llm_model}). "
            "You can change the model in Settings.",
        )
        self.statusBar().showMessage(f"PhysLab ready · {self.settings.llm_model} (local)")

    def _on_sidebar_select(self, index: int) -> None:
        """Route the student-first rail while keeping the original lab available."""
        previous_destination = getattr(self, "_current_nav_index", 0)
        if index != 2:
            self._current_nav_index = index
        language = self.command_bar.get_language()
        self.sidebar.set_language(language)
        self.title_bar.set_page_title(self.sidebar.label_for(previous_destination if index == 2 else index))
        if index == 0:
            self.student_dashboard.set_language(language)
            self._workspace.setCurrentIndex(
                PAGE_RUNNING if self._is_running() else PAGE_STUDENT_HOME
            )
        elif index == 1:
            self.topic_catalog.set_language(language)
            self._workspace.setCurrentIndex(PAGE_TOPICS)
        elif index == 2:
            self.sidebar.set_current(previous_destination)
            self.open_exam_practice(language)
            return
        elif index == 3:
            self.progress_overview.set_language(language)
            self._workspace.setCurrentIndex(PAGE_PROGRESS)
        elif index == 4:
            self._refresh_empty_status()
            self._workspace.setCurrentIndex(PAGE_EMPTY)
        elif index == 5:
            self.library_panel.refresh()
            self._workspace.setCurrentIndex(PAGE_LIBRARY)
        elif index == 6:
            self._workspace.setCurrentIndex(PAGE_HISTORY)
        elif index == 7:
            if self._is_running():
                self._workspace.setCurrentIndex(PAGE_RUNNING)
            else:
                self._param_side.setVisible(self._has_result)
                self._apply_responsive_layout()
                self._workspace.setCurrentIndex(PAGE_SCENE)

        # The timeline belongs to the pipeline views (design: workspace strip);
        # keep Library and History uncluttered.
        self._timeline_strip.setVisible(
            self._timeline_started and self._workspace.currentIndex()
            in (PAGE_RUNNING, PAGE_SOLVE, PAGE_SCENE)
        )
        # Keep the exam-preparation screens focused. The prompt dock remains
        # available in the tutor and physics-workbench sections.
        self.command_bar.setVisible(index >= 4)

    def _refresh_empty_status(self) -> None:
        self.empty_view.set_status(
            bool(self.settings.openai_api_key),
            self.settings.llm_model,
            self.library_panel.library_file_count(),
        )

    def _on_student_language_changed(self, _index: int = -1) -> None:
        language = self.command_bar.get_language()
        self.title_bar.set_language(language)
        self.sidebar.set_language(language)
        self.command_bar.set_language(language)
        self.toast.set_language(language)
        self.stepper.set_language(language)
        self.simulation_panel.set_language(language)
        self.library_panel.set_language(language)
        self.history_panel.set_language(language)
        self.lesson_view.set_language(language)
        self.title_bar.set_page_title(
            self.sidebar.label_for(self.sidebar.selected_index())
        )
        self.student_dashboard.set_language(language)
        self.topic_catalog.set_language(language)
        self.progress_overview.set_language(language)
        self.empty_view.set_language(language)
        if getattr(self, "_last_lesson", None) is not None:
            self._refresh_course_summary(self._last_lesson)
        self._refresh_prebuilt_lesson_language(language)

    def _refresh_prebuilt_lesson_language(self, language: str) -> None:
        """Select packaged content in the header language without an AI request."""
        from aetherlab.services.ent_lesson_catalog import (
            ACCELERATED_MOTION_5MIN_ID,
            ACCELERATED_MOTION_5MIN_VERSION,
            is_prebuilt_ent_topic,
        )

        worker = self.lesson_worker
        if worker and worker.isRunning():
            if is_prebuilt_ent_topic(getattr(worker, "topic", "")):
                self._pending_prebuilt_language = language
            return
        if self.worker and self.worker.isRunning():
            return
        bundle = getattr(self, "_last_lesson", None)
        route_known = is_prebuilt_ent_topic(getattr(self, "_last_lesson_topic", ""))
        if (bundle is not None and (route_known or bundle.plan.model_name == ACCELERATED_MOTION_5MIN_VERSION)
                and bundle.plan.language != language):
            self.start_lesson(ACCELERATED_MOTION_5MIN_ID, language=language)

    def _manage_student_profiles(self) -> None:
        from aetherlab.services.course_mode import CourseProgressStore
        from aetherlab.ui.profile_dialog import _COPY, StudentProfileDialog

        language = self.command_bar.get_language()
        previous_profile_id = self.active_student_profile.id
        dialog = None
        try:
            # Read before opening a modal dialog, so an inaccessible registry
            # reports an error without stranding the user in an empty selector.
            self.student_profile_store.active_profile()
            dialog = StudentProfileDialog(self.student_profile_store, language=language, parent=self)
            result = dialog.exec()
            profile = (
                dialog.selected_profile
                if result == QtWidgets.QDialog.DialogCode.Accepted
                else self.student_profile_store.active_profile()
            )
        except (OSError, ValueError):
            self.statusBar().showMessage(_COPY[language]["load_error"])
            if dialog is not None:
                dialog.deleteLater()
            return
        if profile is None:
            return

        self.active_student_profile = profile
        quota_ready = self._update_ai_help_quota()
        self.ent_progress_path = profile.progress_path
        self.student_dashboard.progress_path = profile.progress_path
        self.student_dashboard.set_profile(profile.name, profile.avatar_path)
        self.title_bar.set_profile(profile.name, profile.avatar_path)
        self.topic_catalog.progress_path = profile.progress_path
        self.progress_overview.progress_path = profile.progress_path
        self.course_progress = CourseProgressStore(
            profile.course_progress_path,
            review_intervals_days=self.settings.review_intervals_days,
        )
        self.student_dashboard.refresh()
        self.topic_catalog.refresh()
        self.progress_overview.refresh()
        if getattr(self, "_last_lesson", None) is not None:
            if profile.id != previous_profile_id:
                # Public lesson content can be shared; selected answers,
                # confidence and completed gates belong to the learner.
                self.lesson_view.set_lesson(self._last_lesson)
                self.lesson_view.restart_for_student()
                self._restore_pending_lesson_answers()
            self._refresh_course_summary(self._last_lesson)
        if quota_ready:
            self.statusBar().showMessage(profile.name)

    def _open_school_leaderboard(self) -> None:
        from aetherlab.ui.leaderboard_dialog import LeaderboardDialog

        dialog = LeaderboardDialog(
            self.student_profile_store,
            self.active_student_profile,
            language=self.command_bar.get_language(),
            parent=self,
        )
        dialog.exec()

    def _on_title_language_changed(self, language: str) -> None:
        index = self.command_bar._language.findData(language)
        if index >= 0 and index != self.command_bar._language.currentIndex():
            self.command_bar._language.setCurrentIndex(index)

    def _is_running(self) -> bool:
        return bool(self.worker and self.worker.isRunning())

    # ── exports (in-context, design: DerivationBlock / SceneView / VideoControls) ──

    def _start_export_task(self, status: str, operation) -> bool:
        if self._export_task and self._export_task.is_running:
            self.statusBar().showMessage("An export is already running.")
            return False
        task = BackgroundTask(operation)
        self._export_task = task
        # Bound methods, not lambdas: an export can finish after its window is
        # gone (closed, or torn down by a test), and a lambda slot then runs
        # against the deleted window - an access violation on Windows (CI,
        # F157, 2026-10-01). PyQt drops bound-method slots with the window.
        task.succeeded.connect(self._on_export_succeeded)
        task.failed.connect(self._on_export_failed)
        task.finished.connect(self._on_export_finished)
        self.statusBar().showMessage(status)
        task.start()
        return True

    def _on_export_succeeded(self, result: object) -> None:
        if result:
            self.statusBar().showMessage(str(result))

    def _on_export_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"Export failed: {message}")

    def _on_export_finished(self) -> None:
        # The finished task is no longer running; a newer export that already
        # started keeps its slot.
        if self._export_task is not None and not self._export_task.is_running:
            self._export_task = None

    def _export_latex(self) -> None:
        if not self._last_result:
            self.statusBar().showMessage("No pipeline result to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export LaTeX", "derivation.tex", "LaTeX Files (*.tex)"
        )
        if not path:
            return
        solver = self._last_result.solver
        export_derivation_to_latex(
            solver.summary, solver.derivation_steps, solver.variables, Path(path),
            key_equations=getattr(solver, "key_equations", None),
        )
        self.statusBar().showMessage(f"LaTeX exported: {path}")

    def _export_pdf(self) -> None:
        if not self._last_result:
            self.statusBar().showMessage("No pipeline result to export.")
            return
        from aetherlab.services.study_document import classify

        request = self._last_result.request
        mode = classify(request.normalized_prompt())
        default_name = "worked_solution.pdf" if mode == "problem" else "study_guide.pdf"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export PDF", default_name, "PDF Files (*.pdf)"
        )
        if not path:
            return
        destination = Path(path)
        solver = self._last_result.solver
        rag = self._last_result.rag
        settings = self.settings

        def export_pdf(cancel, progress):
            import asyncio
            from tempfile import TemporaryDirectory

            from aetherlab.core.atomic_file import atomic_copy_file
            from aetherlab.services.research import build_research_pdf
            from aetherlab.services.study_document import write_study_document

            def report(message: str) -> None:
                if callable(progress):
                    progress(message)

            with TemporaryDirectory(prefix="aetherlab_export_") as tmp_name:
                # Well-explained study document: a topic guide, or theory plus a
                # step-by-step worked solution for a problem (study_document.py).
                doc = asyncio.run(write_study_document(
                    request, solver, rag, settings, Path(tmp_name),
                    progress=report, cancel_check=cancel.is_set,
                ))
                if doc.pdf_path and doc.pdf_path.exists():
                    atomic_copy_file(doc.pdf_path, destination, cancel_check=cancel.is_set)
                    kind = "Worked solution" if doc.mode == "problem" else "Study guide"
                    extra = f" ({doc.note})" if doc.note else ""
                    return f"{kind} PDF exported ({doc.authored_by}): {destination}{extra}"
                # Fall back to the cited research PDF (services/research.py).
                research = build_research_pdf(request, solver, rag, Path(tmp_name) / "research")
                if research.pdf_path and research.pdf_path.exists():
                    atomic_copy_file(research.pdf_path, destination, cancel_check=cancel.is_set)
                    return f"Research PDF exported via {research.backend}: {destination}"
                fallback = destination.with_suffix(".tex")
                atomic_copy_file(doc.tex_path, fallback, cancel_check=cancel.is_set)
                return f"No PDF backend available. LaTeX saved instead: {fallback}"

        self._start_export_task("Writing the PDF (this can take a few minutes)…", export_pdf)

    def _export_scene(self) -> None:
        if not self._last_result:
            self.statusBar().showMessage("No pipeline result to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Scene Code", "scene.py", "Python Files (*.py)"
        )
        if not path:
            return
        export_scene_code(self._last_result.scene.code, Path(path))
        self.statusBar().showMessage(f"Scene code exported: {path}")

    def _save_video(self) -> None:
        """Save the rendered MP4 to a user-chosen location (design: Save)."""
        if not self._last_result or not self._last_result.scene.video_path:
            self.statusBar().showMessage("No rendered video to save.")
            return
        video_path = Path(self._last_result.scene.video_path)
        if not video_path.exists():
            self.statusBar().showMessage("Video file not found.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Video", video_path.name, "MP4 Files (*.mp4)"
        )
        if not path:
            return
        destination = Path(path)

        def save_video(cancel, _progress):
            from aetherlab.core.atomic_file import atomic_copy_file

            atomic_copy_file(
                video_path, destination, cancel_check=cancel.is_set
            )
            return f"Video saved: {destination}"

        self._start_export_task("Saving video…", save_video)

    def _export_gif(self) -> None:
        """Export the rendered video as an animated GIF via ffmpeg (#17)."""
        if not self._last_result or not self._last_result.scene.video_path:
            self.statusBar().showMessage("No rendered video to export.")
            return
        video_path = Path(self._last_result.scene.video_path)
        if not video_path.exists():
            self.statusBar().showMessage("Video file not found.")
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export GIF", "animation.gif", "GIF Files (*.gif)"
        )
        if not path:
            return

        destination = Path(path)

        def export_gif(cancel, _progress):
            import os

            from aetherlab.core.atomic_file import unique_staging_path
            from aetherlab.core.proc import run_process_tree, subprocess_kwargs

            staging = unique_staging_path(destination)
            try:
                result = run_process_tree(
                    [
                        "ffmpeg", "-y", "-i", str(video_path),
                        "-vf", "fps=15,scale=480:-1:flags=lanczos",
                        "-loop", "0", str(staging),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                    cancel_check=cancel.is_set,
                    **subprocess_kwargs(),
                )
                if result.returncode != 0 or not staging.exists():
                    return "GIF conversion failed. Is ffmpeg installed?"
                os.replace(staging, destination)
                size_mb = destination.stat().st_size / 1e6
                return f"GIF exported: {destination} ({size_mb:.1f} MB)"
            except FileNotFoundError:
                return "ffmpeg not found. Install ffmpeg to export GIFs."
            except subprocess.TimeoutExpired:
                return "GIF conversion timed out."
            finally:
                staging.unlink(missing_ok=True)

        self._start_export_task("Converting video to GIF…", export_gif)

    def _open_settings(self) -> None:
        dialog = getattr(self, "_settings_save_draft", None)
        if dialog is None:
            dialog = SettingsDialog(self.settings, self)
        dialog.set_language(self.command_bar.get_language())
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            vals = dialog.get_settings()

            # Persist to the app config so the values survive restarts.
            from aetherlab.core.settings import load_settings, save_app_config
            try:
                save_app_config({
                    "provider_preset": vals["provider_preset"],
                    "model": vals["model"],
                    "llm_timeout_seconds": vals["llm_timeout_seconds"],
                    "llm_max_retries": vals["llm_max_retries"],
                    "api_key": vals["api_key"],
                    "base_url": vals["base_url"],
                    "library_path": vals["library_path"],
                    "data_dir": vals["data_dir"],
                    "default_quality": vals["default_quality"],
                    "render_mode": vals["render_mode"],
                    "cloud_provider": "github_actions",
                    "github_repo": vals["github_repo"],
                    "github_token": vals["github_token"],
                    "github_workflow": vals["github_workflow"],
                    "github_branch": vals["github_branch"],
                    "cloud_render_threshold": vals["cloud_render_threshold"],
                    "vision_model": vals["vision_model"],
                    "web_references": "1" if vals["web_references"] else "0",
                    "narration_enabled": "1" if vals["narration_enabled"] else "0",
                    "auto_tournament": "1" if vals["auto_tournament"] else "0",
                    "tts_voice": vals["tts_voice"],
                    "review_intervals_days": vals["review_intervals_days"],
                })
            except (OSError, ValueError):
                self._settings_save_draft = dialog
                self._report_settings_save_failure(reopen=True)
                return
            self._settings_save_draft = None

            # Re-resolve the just-saved config through the canonical precedence
            # chain. Direct replacement made a saved key appear active until
            # restart even when an environment key actually shadows it.
            self.settings = load_settings()
            self.command_bar.set_quality(vals["default_quality"])
            self.history_panel.init_persistence(self.settings.data_dir / "history.sqlite3")
            from aetherlab.services.course_mode import CourseProgressStore

            self.course_progress = CourseProgressStore(
                self.active_student_profile.course_progress_path,
                review_intervals_days=self.settings.review_intervals_days,
            )
            self.library_panel.set_settings(self.settings)
            self.empty_view.set_status(
                bool(self.settings.openai_api_key),
                self.settings.llm_model,
                self.library_panel.library_file_count(),
            )
            provider_note = (
                self.settings.llm_model if self.settings.openai_api_key else "No API key"
            )
            self.statusBar().showMessage(f"Settings saved · {provider_note}")
        else:
            self._settings_save_draft = None

    def _report_settings_save_failure(self, *, reopen: bool = False) -> None:
        message, retry = {
            "kk": ("Баптауларды сақтау мүмкін болмады. Баптаулар папкасына қолжетімділікті тексеріңіз.",
                   "Енгізілген мәндер сақталды. Қайталау үшін баптауларды қайта ашыңыз."),
            "ru": ("Не удалось сохранить настройки. Проверьте доступ к папке настроек.",
                   "Введённые значения сохранены. Откройте настройки снова, чтобы повторить."),
            "en": ("Could not save settings. Check access to the settings folder.",
                   "Your entries are retained. Open Settings again to retry."),
        }[normalize_language(self.command_bar.get_language(), "kk")]
        if reopen:
            message += " " + retry
        self.statusBar().showMessage(message)
        self.toast.show_message("warning", message)

    def _apply_reference_sources_settings(self, settings) -> None:
        """Apply a folder chosen from either the library or ENT practice UI."""
        self.settings = settings
        if hasattr(self, "library_panel"):
            self.library_panel.set_settings(settings)
        path = getattr(settings, "reference_sources_path", None)
        self.statusBar().showMessage(
            f"Reference source folder saved · {path}" if path else "Reference source folder cleared."
        )

    def _toggle_code_view(self) -> None:
        self._workspace.setCurrentIndex(PAGE_SCENE)
        if self.simulation_panel._stack.currentIndex() == 3:
            self.simulation_panel.show_canvas()
        else:
            self.simulation_panel.show_code()

    def _cancel_pipeline(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.statusBar().showMessage("Cancelling pipeline…")
            self.command_bar.set_busy(True)
            self.command_bar.cancel_button.setEnabled(False)
            self.stepper.set_cancellable(False)
            self.running_view.set_stage_text("Cancelling pipeline…", "")
        elif self.lesson_worker and self.lesson_worker.isRunning():
            # Learn is cancellable too — the pipeline stops after the current
            # chapter and returns whatever rendered (on_lesson_ready handles it).
            self.lesson_worker.cancel()
            self.statusBar().showMessage("Cancelling lesson… (stops after this chapter)")
            self.toast.show_message("warning", "Cancelling lesson…")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        if self._pending_lesson_answers and not self._confirm_discard_pending_lesson_answers():
            self._close_pending = False
            event.ignore()
            return
        self._pending_lesson_answers.clear()
        probe = getattr(self, "_ollama_probe", None)
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        if self.lesson_worker and self.lesson_worker.isRunning():
            self.lesson_worker.cancel()
        if self._export_task and self._export_task.is_running:
            self._export_task.cancel()
        self.library_panel.request_background_cancel()

        threads = [
            thread
            for thread in (probe, self.worker, self.lesson_worker)
            if thread is not None and thread.isRunning()
        ]
        threads.extend(self.library_panel.active_workers())
        lingering = [thread for thread in threads if not thread.wait(5000)]
        if lingering:
            event.ignore()
            self.statusBar().showMessage("Cancelling pipeline…")
            if not self._close_pending:
                self._close_pending = True
                for thread in lingering:
                    thread.finished.connect(self._close_when_idle)
            return

        self._close_pending = False
        super().closeEvent(event)

    def _confirm_discard_pending_lesson_answers(self) -> bool:
        language = self.command_bar.get_language()
        title, message, discard_text, keep_text = {
            "kk": ("Жауаптар әлі расталмады", "Кейбір жауаптардың сақталғаны расталмады. Барлық профильдердің расталмаған жауаптарын сақтамай жабу керек пе?", "Сақтамай жабу", "Қосымшада қалу"),
            "ru": ("Сохранение ответов не подтверждено", "Для некоторых ответов сохранение не подтверждено. Закрыть приложение без сохранения этих ответов во всех профилях?", "Закрыть без сохранения", "Остаться в приложении"),
            "en": ("Answer saving is unconfirmed", "Some answer saves could not be confirmed. Close without saving these answers in all profiles?", "Close without saving", "Stay in the app"),
        }[language]
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        discard = dialog.addButton(discard_text, QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        keep = dialog.addButton(keep_text, QtWidgets.QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(keep)
        dialog.setEscapeButton(keep)
        dialog.exec()
        return dialog.clickedButton() is discard

    def _close_when_idle(self) -> None:
        if not self._close_pending:
            return
        threads = [
            getattr(self, "_ollama_probe", None),
            self.worker,
            self.lesson_worker,
        ]
        threads.extend(self.library_panel.active_workers())
        if any(thread is not None and thread.isRunning() for thread in threads):
            return
        self._close_pending = False
        QtCore.QTimer.singleShot(0, self.close)

    # ── pipeline ──

    # ── topic explainer (Learn) ──

    def start_lesson(
        self,
        topic: str,
        language: str | None = None,
        voiceover: bool | None = None,
        regenerate: bool = False,
    ) -> None:
        if self.lesson_worker and self.lesson_worker.isRunning():
            self.statusBar().showMessage("A lesson is already being built.")
            return
        if self.worker and self.worker.isRunning():
            self.statusBar().showMessage("Finish or cancel the current run first.")
            return
        from aetherlab.services.ent_lesson_catalog import is_prebuilt_ent_topic

        if not is_prebuilt_ent_topic(topic) and not self._try_consume_ai_help():
            return

        self._last_lesson_topic = topic
        language = normalize_language(language or self.command_bar.get_language(), "kk")
        self._last_lesson_language = language
        voiceover = (
            self.command_bar.get_voiceover_enabled()
            if voiceover is None else bool(voiceover)
        )
        self._last_lesson_voiceover = voiceover
        lesson_settings = replace(self.settings, narration_enabled=voiceover)
        self.lesson_worker = LessonWorker(
            topic, lesson_settings, audience="high_school", language=language,
            quality=self.command_bar.get_render_quality(),
            regenerate=regenerate,
        )
        self.lesson_worker.progress.connect(self._on_lesson_progress)
        self.lesson_worker.lesson_ready.connect(self.on_lesson_ready)
        self.lesson_worker.failure.connect(self.on_failure)
        self.lesson_worker.finished.connect(self._on_lesson_worker_finished)

        self.command_bar.set_busy(True)
        self.toast.hide()
        verb = "Rebuilding" if regenerate else "Building"
        self.running_view.set_stage_text(f"{verb} lesson…", topic[:80])
        # Learn is cancellable (Esc / the running view's Cancel button).
        self.stepper.set_cancellable(True)
        self._workspace.setCurrentIndex(PAGE_RUNNING)
        self.statusBar().showMessage(f"{verb} lesson: {topic}")
        self.lesson_worker.start()

    def regenerate_lesson(self) -> None:
        """Rebuild the current lesson from scratch (ignore plan + clip caches)."""
        topic = getattr(self, "_last_lesson_topic", "")
        if not topic:
            self.statusBar().showMessage("No lesson to regenerate yet.")
            return
        self.start_lesson(
            topic,
            language=getattr(self, "_last_lesson_language", self.command_bar.get_language()),
            voiceover=getattr(
                self, "_last_lesson_voiceover", self.command_bar.get_voiceover_enabled()
            ),
            regenerate=True,
        )

    def open_exam_practice(
        self, language: str = "kk", *, topic_id: str | None = None,
        review_mistakes: bool = False, start_mode: str | None = None,
    ) -> None:
        from aetherlab.ui.exam_practice import ExamPracticeDialog

        active_dialog = getattr(self, "_practice_dialog", None)
        if active_dialog is not None:
            active_dialog.raise_()
            active_dialog.activateWindow()
            return
        dialog = ExamPracticeDialog(
            language, self, progress_path=self.ent_progress_path, topic_id=topic_id,
            start_mode=start_mode,
        )
        self._practice_dialog = dialog
        if review_mistakes:
            dialog._start_mistake_review()
        try:
            dialog.exec()
        finally:
            self._practice_dialog = None
            dialog.deleteLater()
        self.student_dashboard.refresh()
        self.topic_catalog.refresh()
        self.progress_overview.refresh()

    def _start_ent_topic_lesson(self, topic: str) -> None:
        from aetherlab.services.ent_lesson_catalog import is_prebuilt_ent_topic

        language = self.command_bar.get_language()
        normalized = str(topic or "").casefold().replace("_", " ").replace("-", " ")
        if is_prebuilt_ent_topic(topic) or normalized == "constant acceleration":
            self.start_lesson(
                "constant_acceleration_5min", language=language,
                voiceover=self.command_bar.get_voiceover_enabled(),
            )
            return
        if "кинематик" in normalized or "kinematic" in normalized or "кинематика" in normalized:
            # The prebuilt 5-minute lesson covers this specific kinematics unit.
            self.start_lesson(
                "constant_acceleration_5min", language=language,
                voiceover=self.command_bar.get_voiceover_enabled(),
            )
            return
        self.start_lesson(
            f"Explain {topic} for a high-school student preparing for Kazakhstan's UNT. "
            "Use simple language, define every new term, show one worked example, "
            "then give a short practice question.",
            language=language,
            voiceover=self.command_bar.get_voiceover_enabled(),
        )

    def _on_lesson_worker_finished(self) -> None:
        # Bound method (not a lambda) so a QThread finishing after the window
        # is destroyed cannot touch the deleted command bar.
        self.command_bar.set_busy(False)
        pending = getattr(self, "_pending_prebuilt_language", "")
        self._pending_prebuilt_language = ""
        cancel = getattr(self.lesson_worker, "_cancel", None)
        if pending and not (cancel is not None and cancel.is_set()):
            self._refresh_prebuilt_lesson_language(self.command_bar.get_language())

    def _on_lesson_progress(self, message: str, done: int, total: int) -> None:
        self.running_view.set_stage_text(message, f"{done}/{total}" if total else "")
        language = getattr(getattr(self, "lesson_worker", None), "language", self.command_bar.get_language())
        self.statusBar().showMessage(f"{lesson_message(language, 'lesson')} · {message}")

    def on_lesson_ready(self, bundle) -> None:
        self.command_bar.set_busy(False)
        self.stepper.set_cancellable(False)
        previous = getattr(self, "_last_lesson", None)
        previous_hash = getattr(getattr(previous, "plan", None), "prebuilt_content_hash", "")
        # A translation is the same attempt. Only a validated shared content
        # snapshot permits choice-index mapping; new lessons and explicit
        # same-language restarts keep their normal fresh-question behaviour.
        translated_answers = (
            self.lesson_view.question_answer_state()
            if previous_hash
            and previous_hash == getattr(bundle.plan, "prebuilt_content_hash", "")
            and previous.plan.language != bundle.plan.language
            else {}
        )

        # A cancelled lesson may have partial/no video — never dump the student
        # on a blank page with no explanation.
        if bundle.status == "cancelled":
            if bundle.video_path:
                self._last_lesson = bundle
                self.lesson_view.set_lesson(bundle)
                self.lesson_view.set_audio_enabled(getattr(self, "_last_lesson_voiceover", True))
                self._restore_pending_lesson_answers()
                self._refresh_course_summary(bundle)
                self.lesson_view.set_video(bundle.video_path)
                self._workspace.setCurrentIndex(PAGE_LESSON)
                self.toast.show_message(
                    "warning",
                    lesson_message(bundle.plan.language, "cancel_partial"),
                )
            else:
                self._workspace.setCurrentIndex(PAGE_LESSON if getattr(self, "_last_lesson", None) else PAGE_EMPTY)
                self.toast.show_message(
                    "warning", lesson_message(bundle.plan.language, "cancel_empty"),
                )
            self.statusBar().showMessage(lesson_message(bundle.plan.language, "stage_cancelled"))
            return

        self._last_lesson = bundle
        self.lesson_view.set_lesson(bundle)
        self.lesson_view.set_audio_enabled(getattr(self, "_last_lesson_voiceover", True))
        for index, answer in translated_answers.items():
            self.lesson_view.restore_question_answer(index, **answer)
        self._restore_pending_lesson_answers()
        if bundle.status == "package_error":
            self.lesson_view.set_video("")
            self._workspace.setCurrentIndex(PAGE_LESSON)
            note = str(bundle.package_error_message)
            self.statusBar().showMessage(note)
            self.toast.show_message("warning", note)
            return
        self._refresh_course_summary(bundle)
        # Always refresh the player: a lesson without video must clear a stale
        # clip from the previous lesson, not keep playing it.
        self.lesson_view.set_video(bundle.video_path or "")
        self._workspace.setCurrentIndex(PAGE_LESSON)
        if bundle.status == "offline_practice_available":
            note = bundle.plan.chapters[0].goal if bundle.plan.chapters else "Offline practice is available."
            self.statusBar().showMessage(note)
            self.toast.show_message("warning", note)
            return
        if bundle.status == "planning_error":
            note = bundle.plan.chapters[0].goal if bundle.plan.chapters else "The lesson could not be prepared."
            self.statusBar().showMessage(note)
            self.toast.show_message("warning", note)
            return
        if bundle.status == "error":
            missing = getattr(bundle, "missing_media", None)
            invalid = getattr(bundle, "invalid_media", None)
            media_copy = {
                "kk": ("Сабақ файлдары жоқ: {files}.", "Сабақ файлдарын растау мүмкін болмады: {files}.", "Сабақ медиасын жүктеу мүмкін болмады.", "Мәтін, тапсырмалар және дереккөздер қолжетімді."),
                "ru": ("Отсутствуют файлы урока: {files}.", "Не удалось подтвердить файлы урока: {files}.", "Не удалось загрузить медиа урока.", "Текст, задания и источники доступны."),
                "en": ("Lesson files are missing: {files}.", "Could not verify lesson files: {files}.", "Could not load lesson media.", "Transcript, questions and references remain available."),
            }[normalize_language(self.command_bar.get_language(), "kk")]
            parts = []
            if missing:
                parts.append(media_copy[0].format(files=", ".join(missing)))
            if invalid:
                parts.append(media_copy[1].format(files=", ".join(invalid)))
            note = " ".join((parts or [media_copy[2]]) + [media_copy[3]])
            self.statusBar().showMessage(note)
            self.toast.show_message("warning", note)
            return
        language = normalize_language(getattr(bundle.plan, "language", "en"))
        ready, watch, text_ready, video_pending = {
            "kk": ("Сабақ дайын · {count} бөлім", "Бейнені көріңіз, мәтінді оқыңыз немесе тапсырмаларды орындаңыз.", "Сабақ мәтіні дайын · {count} бөлім", "Бейне әлі дайын емес. Мәтін мен тапсырмалар қолжетімді."),
            "ru": ("Урок готов · {count} разделов", "Посмотрите видео, прочитайте текст или решите задания.", "Текст урока готов · {count} разделов", "Видео ещё не готово. Текст и задания доступны."),
            "en": ("Lesson ready · {count} chapters", "Watch the video, read the transcript, or try the questions.", "Lesson text ready · {count} chapters", "The video is not ready yet. Transcript and questions are available."),
        }[language]
        video_ready = bundle.status == "assembled" and bool(bundle.video_path)
        note = (ready if video_ready else text_ready).format(count=len(bundle.plan.chapters))
        self.statusBar().showMessage(note)
        self.toast.show_message("success" if video_ready else "info", f"{note}. {watch if video_ready else video_pending}")

    def _refresh_course_summary(self, bundle) -> None:
        try:
            summary = self.course_progress.summary(bundle.plan, language=self.command_bar.get_language())
            self.lesson_view.set_course_summary(summary.message)
            self.lesson_view.set_due_review_count(self.course_progress.due_review_count())
        except Exception:  # noqa: BLE001
            self.lesson_view.set_course_summary(
                lesson_message(self.command_bar.get_language(), "course_unavailable")
            )

    def _record_lesson_quiz_answer(
        self, question_index: int, correct: bool, choice: str
    ) -> None:
        bundle = getattr(self, "_last_lesson", None)
        if not bundle or not 0 <= int(question_index) < len(bundle.plan.questions):
            return
        from uuid import uuid4

        key = self._lesson_answer_draft_key(bundle.plan, question_index)
        draft = self._pending_lesson_answers.get(key)
        if draft is None:
            from datetime import datetime, timezone

            question = bundle.plan.questions[int(question_index)]
            draft = {
                "plan": bundle.plan, "correct": bool(correct), "choice": str(choice),
                "choice_index": question.choices.index(str(choice)) if str(choice) in question.choices else -1,
                "confidence": self.lesson_view.confidence_for_question(question_index),
                "operation_id": uuid4().hex,
                "answered_at": datetime.now(timezone.utc),
            }
            self._pending_lesson_answers[key] = draft
        try:
            summary = self.course_progress.record_quiz_answer(
                draft["plan"], int(question_index), draft["correct"], draft["choice"],
                confidence_level=draft["confidence"], operation_id=draft["operation_id"],
                now=draft["answered_at"],
            )
        except Exception:  # noqa: BLE001 - preserve the draft for an explicit retry
            self.lesson_view.set_question_save_pending(int(question_index), True)
            self.statusBar().showMessage(self.lesson_view._question_cards[int(question_index)]._save_status.text())
            return
        self._pending_lesson_answers.pop(key, None)
        self.lesson_view.set_question_save_pending(int(question_index), False)
        self._refresh_course_summary(bundle)
        self.statusBar().showMessage(
            lesson_message(self.command_bar.get_language(), "course_saved", correct=summary.correct, attempts=summary.attempts)
        )

    def _lesson_answer_draft_key(self, plan, question_index: int) -> tuple:
        import hashlib
        import json

        identity = getattr(plan, "prebuilt_content_hash", "") or hashlib.sha256(
            json.dumps(plan.to_json(), ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return self.active_student_profile.id, identity, int(question_index)

    def _retry_lesson_quiz_answer(self, question_index: int) -> None:
        bundle = getattr(self, "_last_lesson", None)
        if bundle is None:
            return
        draft = self._pending_lesson_answers.get(self._lesson_answer_draft_key(bundle.plan, question_index))
        if draft:
            self._record_lesson_quiz_answer(question_index, draft["correct"], draft["choice"])

    def _restore_pending_lesson_answers(self) -> None:
        bundle = getattr(self, "_last_lesson", None)
        if bundle is None:
            return
        for index, _question in enumerate(bundle.plan.questions):
            draft = self._pending_lesson_answers.get(self._lesson_answer_draft_key(bundle.plan, index))
            if draft:
                self.lesson_view.restore_pending_question(index, draft["choice_index"], draft["confidence"])

    def _review_due_questions(self) -> None:
        try:
            self._run_due_question_reviews()
        except (OSError, ValueError):
            message = {
                "kk": "Қайталау тарихын оқу немесе сақтау мүмкін болмады. Тарихқа қолжетімділікті тексеріп, қайта көріңіз.",
                "ru": "Не удалось прочитать или сохранить историю повторения. Проверьте доступ к истории и попробуйте снова.",
                "en": "Review history could not be read or saved. Check access to the history and retry.",
            }[self.command_bar.get_language()]
            self.statusBar().showMessage(message)
            self.lesson_view.set_course_summary(message)
            self.toast.show_message("warning", message)

    def _run_due_question_reviews(self) -> None:
        """Run due retrieval prompts, objectively scoring multiple-choice items."""
        from aetherlab.ui.widgets import _LessonCheckDialog

        reviews = self.course_progress.due_reviews(limit=20)
        if not reviews:
            self.lesson_view.set_due_review_count(0)
            self.statusBar().showMessage(lesson_message(self.command_bar.get_language(), "review_none"))
            return
        saved_count = 0
        stale_review = False
        language = self.command_bar.get_language()
        for item in reviews:
            choices = item.get("choices")
            answer = str(item.get("answer", "")).strip()
            if isinstance(choices, list) and choices and answer:
                question = {
                    "q": str(item.get("prompt") or lesson_message(language, "review_prompt")),
                    "choices": choices,
                    "answer": answer,
                    "why": str(item.get("why", "")),
                }
                dialog = _LessonCheckDialog(question, "spaced_review", self,
                                            language=self.command_bar.get_language())
                if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                    break
                if not dialog.answer_submitted or dialog.answer_correct is None:
                    break
                correct = dialog.answer_correct
                interval = self.course_progress.record_review_result(
                    item, correct, correct=correct
                )
                if interval <= 0:
                    stale_review = True
                    break
                saved_count += 1
                continue

            # Open responses cannot be reliably auto-graded. Keep them separate
            # as self-reported recall rather than counting them as objective accuracy.
            ask = QtWidgets.QMessageBox(self)
            ask.setWindowTitle(lesson_message(language, "review_title"))
            ask.setText(str(item.get("prompt") or lesson_message(language, "review_prompt")))
            ask.setInformativeText(
                f"{item.get('lesson_title') or lesson_message(language, 'lesson')} · {item.get('concept', '')}\n\n"
                + lesson_message(language, "review_hint")
            )
            reveal = ask.addButton(lesson_message(language, "review_reveal"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            later = ask.addButton(lesson_message(language, "review_later"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            ask.setDefaultButton(later)
            ask.setEscapeButton(later)
            ask.exec()
            if ask.clickedButton() is not reveal:
                break

            answer_box = QtWidgets.QMessageBox(self)
            answer_box.setWindowTitle(lesson_message(language, "review_self_title"))
            answer_box.setText(
                str(item.get("answer") or lesson_message(language, "review_open"))
            )
            explanation = str(item.get("why", "")).strip()
            answer_box.setInformativeText(explanation or str(item.get("concept", "")))
            recalled = answer_box.addButton(
                lesson_message(language, "review_recalled"), QtWidgets.QMessageBox.ButtonRole.YesRole
            )
            missed = answer_box.addButton(
                lesson_message(language, "review_missed"), QtWidgets.QMessageBox.ButtonRole.NoRole
            )
            skip = answer_box.addButton(lesson_message(language, "review_stop"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            answer_box.setDefaultButton(skip)
            answer_box.setEscapeButton(skip)
            answer_box.exec()
            selected = answer_box.clickedButton()
            if selected is skip or selected not in {recalled, missed}:
                break
            interval = self.course_progress.record_review_result(item, selected is recalled)
            if interval <= 0:
                stale_review = True
                break
            saved_count += 1

        count = self.course_progress.due_review_count()
        self.lesson_view.set_due_review_count(count)
        if getattr(self, "_last_lesson", None):
            self._refresh_course_summary(self._last_lesson)
        message = lesson_message(language, "review_changed") if stale_review else {
            "kk": f"Сақталған қайталау жауаптары: {saved_count}. Қайталау керек сұрақтар: {count}." if saved_count else "Қайталау жаңа жауаптарсыз аяқталды.",
            "ru": f"Сохранено ответов повторения: {saved_count}. Осталось вопросов: {count}." if saved_count else "Повторение завершено без новых ответов.",
            "en": f"Review responses saved: {saved_count}. Questions still due: {count}." if saved_count else "Review ended without new responses.",
        }[self.command_bar.get_language()]
        self.statusBar().showMessage(message)

    def _export_study_guide(self) -> None:
        bundle = getattr(self, "_last_lesson", None)
        if not bundle:
            self.statusBar().showMessage("No lesson to export yet.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export study guide", "study_guide.tex", "LaTeX Files (*.tex)"
        )
        if not path:
            return
        from aetherlab.services.pdf import export_lesson_study_guide

        export_lesson_study_guide(bundle.plan, Path(path))
        self.statusBar().showMessage(f"Study guide exported: {path}")

    def _open_study_pdf(self) -> None:
        from aetherlab.ui.lesson_view import _COPY

        language = normalize_language(self.command_bar.get_language(), "kk")
        copy = _COPY[language]
        bundle = getattr(self, "_last_lesson", None)
        pdf = Path(str(getattr(bundle, "pdf_path", "") or "")) if bundle else Path()
        if not pdf.is_file():
            self.statusBar().showMessage(copy["pdf_missing"])
            return
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf))):
            self.statusBar().showMessage(copy["pdf_open_failed"])
            return
        self.statusBar().showMessage(copy["pdf_dispatched"].format(name=pdf.name))

    def _export_lesson_bundle(self) -> None:
        bundle = getattr(self, "_last_lesson", None)
        if not bundle or not getattr(bundle, "video_path", ""):
            self.statusBar().showMessage("No assembled lesson to export yet.")
            return
        default_name = "aetherlab_lesson_bundle.zip"
        title = getattr(getattr(bundle, "plan", None), "title", "")
        if title:
            import re

            slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
            if slug:
                default_name = f"{slug[:48]}_bundle.zip"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export lesson bundle", default_name, "ZIP Files (*.zip)"
        )
        if not path:
            return
        destination = Path(path)

        def export_bundle(_cancel, _progress):
            from aetherlab.services.share_export import export_lesson_bundle

            summary = export_lesson_bundle(bundle, destination)
            size_mb = summary.size_bytes / 1e6
            return f"Lesson bundle exported: {summary.path} ({size_mb:.1f} MB)"

        self._start_export_task("Exporting lesson bundle…", export_bundle)

    def start_pipeline(self, prompt: str) -> None:
        if self.worker and self.worker.isRunning():
            self.statusBar().showMessage("Pipeline is already running.")
            return
        if not self._try_consume_ai_help():
            return

        # Disconnect and clean up old worker to prevent signal accumulation
        if self.worker is not None:
            try:
                self.worker.status.disconnect()
                self.worker.plan_ready.disconnect()
                self.worker.solver_ready.disconnect()
                self.worker.rag_ready.disconnect()
                self.worker.scene_ready.disconnect()
                self.worker.render_ready.disconnect()
                self.worker.failure.disconnect()
                self.worker.pipeline_finished.disconnect()
                self.worker.progress.disconnect()
                self.worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.worker.deleteLater()
            self.worker = None

        request = ProblemRequest(
            prompt=prompt,
            duration_target_s=self.command_bar.get_duration_target(),
        )
        render_quality = self.command_bar.get_render_quality()
        self.worker = PipelineWorker(
            request=request, settings=self.settings, render_quality=render_quality
        )
        self.worker.status.connect(self.statusBar().showMessage)
        self.worker.plan_ready.connect(self.on_plan_ready)
        self.worker.solver_ready.connect(self.on_solver_ready)
        self.worker.rag_ready.connect(self.on_rag_ready)
        self.worker.scene_ready.connect(self.on_scene_ready)
        self.worker.render_ready.connect(self.on_render_ready)
        self.worker.failure.connect(self.on_failure)
        self.worker.pipeline_finished.connect(self.on_pipeline_finished)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_worker_finished)

        self.command_bar.set_busy(True)
        self.toast.hide()
        self.simulation_panel.clear_error_banner()

        self._timeline_started = True
        self._timeline_strip.show()
        self.stepper.reset()
        self.stepper.set_cancellable(True)
        self.stepper.set_stage(0)

        self.running_view.set_stage_text("Running Solve…", prompt[:80])
        self._workspace.setCurrentIndex(PAGE_RUNNING)
        self.statusBar().showMessage("Launching pipeline…")
        self.worker.start()

    def _try_consume_ai_help(self) -> bool:
        """Meter explicit learner AI requests without touching background jobs."""
        from aetherlab.services.ai_help_quota import consume_ai_help

        try:
            allowed, remaining = consume_ai_help(
                self.active_student_profile.ai_help_quota_path,
                limit=self._daily_ai_help_limit,
            )
        except OSError:
            self._ai_help_quota_unavailable()
            return False
        self.command_bar.set_ai_quota(remaining, self._daily_ai_help_limit)
        if allowed:
            return True
        messages = {
            "kk": "Бүгінгі AI көмегінің 10 мүмкіндігі аяқталды. Ертең қайта көр.",
            "ru": "На сегодня использованы все 10 запросов AI-помощи. Попробуй завтра.",
            "en": "All 10 AI help requests for today have been used. Try again tomorrow.",
        }
        message = messages.get(self.command_bar.get_language(), messages["kk"])
        self.statusBar().showMessage(message)
        self.toast.show_message("warning", message)
        return False

    def _ai_help_quota_unavailable(self) -> None:
        self.command_bar.set_ai_quota(None, self._daily_ai_help_limit)
        self._ai_quota_error_message = self.command_bar._ai_quota.toolTip()
        self.statusBar().showMessage(self._ai_quota_error_message)

    def _update_ai_help_quota(self) -> bool:
        from aetherlab.services.ai_help_quota import remaining_ai_help

        try:
            remaining = remaining_ai_help(self.active_student_profile.ai_help_quota_path)
        except OSError:
            self._ai_help_quota_unavailable()
            return False
        self.command_bar.set_ai_quota(remaining, self._daily_ai_help_limit)
        previous_error = getattr(self, "_ai_quota_error_message", "")
        if previous_error and self.statusBar().currentMessage() == previous_error:
            self.statusBar().clearMessage()
        self._ai_quota_error_message = ""
        return True

    def _refresh_ai_help_quota(self) -> None:
        self._update_ai_help_quota()
        today = date.today()
        if today != self._dashboard_refresh_date:
            self.student_dashboard.refresh()
            self._dashboard_refresh_date = today

    def _on_worker_finished(self) -> None:
        cancelled = bool(self.worker and self.worker._cancelled)
        self.command_bar.set_busy(False)
        self.command_bar.cancel_button.setEnabled(True)
        self.stepper.set_cancellable(False)
        if cancelled:
            self.simulation_panel.hide_loading()
            self.toast.show_message("warning", "Run cancelled by user.")
            self._workspace.setCurrentIndex(
                PAGE_SOLVE if self._has_result else PAGE_EMPTY
            )

    def _on_progress(self, value: int, text: str = "") -> None:
        if value < 30:
            stage, label = 0, "Solve"
        elif value < 50:
            stage, label = 1, "RAG"
        elif value < 70:
            stage, label = 2, "Scene"
        elif value < 100:
            stage, label = 3, "Render"
        else:
            stage, label = 3, "Render"

        for i in range(stage):
            self.stepper.set_stage(i, "complete")
        self.stepper.set_stage(stage, "complete" if value >= 100 else "active")
        self.running_view.set_stage_text(
            "Pipeline complete" if value >= 100 else f"Running {label}…",
            text,
        )

    def on_plan_ready(self, plan) -> None:
        self._current_plan = plan
        self.simulation_panel.apply_plan(plan)
        enabled = ", ".join(plan.enabled()) or "none"
        self.statusBar().showMessage(f"Plan: {enabled}")

    def on_solver_ready(self, solver: SolverResult) -> None:
        self._active_solver = solver
        self.analysis_panel.set_solver_result(solver)
        self.parameter_dock.set_variables(solver.variables)
        self.simulation_panel.set_solver(solver)
        self.stepper.set_stage(0, "complete")
        self.sidebar.set_result_available(True)

    def _apply_scene_spec_to_ui(self, solver: SolverResult, scene_spec: dict) -> None:
        self.analysis_panel.set_solver_result(solver, scene_spec)
        self.simulation_panel.set_solver(solver, scene_spec)

    def on_rag_ready(self, rag: RagResult) -> None:
        self.reference_panel.set_rag_result(rag)
        self.stepper.set_stage(1, "complete")

    def on_scene_ready(self, scene: SceneBundle) -> None:
        self._has_result = True
        self.simulation_panel.hide_loading()
        if self._active_solver and isinstance(scene.scene_spec, dict):
            self._apply_scene_spec_to_ui(self._active_solver, scene.scene_spec)
        self.simulation_panel.set_scene_bundle(scene)
        self.stepper.set_stage(2, "complete")
        # Reveal the result: switch the workspace to the Scene view
        self.sidebar.select(7)

    def on_render_ready(self, scene: SceneBundle) -> None:
        if self._active_solver and isinstance(scene.scene_spec, dict):
            self._apply_scene_spec_to_ui(self._active_solver, scene.scene_spec)
        self.simulation_panel.set_video(scene)
        self.stepper.set_stage(3, "complete")
        if any("Cloud render unavailable; rendered locally." in d for d in scene.diagnostics):
            self.statusBar().showMessage("Cloud render unavailable — rendered locally.")
            self.toast.show_message("warning", "Cloud render unavailable — rendered locally.")
        elif (
            str(getattr(self.settings, "render_mode", "local")).lower() == "cloud"
            and scene.status in {"cloud-unavailable", "render-error", "render-timeout"}
        ):
            detail = next((
                str(message) for message in reversed(scene.diagnostics)
                if "cloud" in str(message).lower()
            ), f"Cloud render failed with status {scene.status}.")
            message = f"Cloud render failed; local rendering was not started. {detail}"
            self.statusBar().showMessage(message)
            self.toast.show_message("error", message, details=True)
            self.simulation_panel.show_error_banner(
                "Cloud render", detail, "\n".join(scene.diagnostics[-12:]),
            )

    def on_failure(self, error: PipelineError) -> None:
        self.simulation_panel.hide_loading()
        self.stepper.set_stage(self.stepper._current_stage, "error")
        self.stepper.set_cancellable(False)
        self.statusBar().showMessage(f"{error.stage} failed: {error.message}")
        # Error voice (design): fact + cause, Details affordance
        self.toast.show_message(
            "error", f"{error.stage} failed: {error.message}", details=True
        )
        self.simulation_panel.show_error_banner(
            error.stage, error.message, error.traceback or error.message
        )
        self._workspace.setCurrentIndex(
            PAGE_SOLVE if self._has_result else PAGE_EMPTY
        )

    def on_pipeline_finished(self, result: PipelineResult) -> None:
        self._last_result = result
        self._has_result = True
        self.history_panel.add_entry(
            result.request.prompt,
            result.cache_key[:12],
            result.scene.status,
            len(result.rag.hits),
        )
        self.statusBar().showMessage(
            f"Pipeline complete · cache {result.cache_key[:12]} · scene {result.scene.status}"
        )
