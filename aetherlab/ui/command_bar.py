"""Prompt entry dock and examples for solve, learn, and practice workflows."""

from __future__ import annotations

from aetherlab.ui import icons
from aetherlab.ui.qt_compat import QtCore, QtWidgets, require_qt

require_qt()

# Authored school-physics prompts, not official UNT questions. Keep each
# translated row's physical conditions and numerical data identical.
EXAMPLE_PROMPTS_BY_LANGUAGE = {
    "kk": (
        "Дене тыныштықтан қозғалады: бастапқы жылдамдығы 0 м/с, тұрақты үдеуі 2 м/с², уақыт 5 с. Үдеу нені білдіретінін қарапайым тілмен түсіндір, соңғы жылдамдық пен жүрген жолды тап, жылдамдық–уақыт графигін көрсет.",
        "Массасы 2 кг дененің үдеуі 3 м/с². Қорытқы күшті тап. Алдымен күш пен үдеудің мағынасын түсіндір, содан кейін Ньютон заңын қолданып, өлшем бірліктерін тексер.",
        "Массасы 2 кг дене 5 м биіктікке көтерілді. Еркін түсу үдеуі 10 м/с². Ауырлық күшінің потенциалдық энергиясының артуын тап, жерге қатысты нөлдік деңгейді және энергияның мағынасын түсіндір.",
        "Массасы 2 кг арба 3 м/с жылдамдықпен қозғалып, массасы 1 кг, жылдамдығы 0 м/с арбамен соқтығысады да, екеуі бірігіп қозғалады. Сыртқы күштердің импульсін елеме. Ортақ жылдамдықты тап, импульсті қозғалыс мөлшері ретінде түсіндір.",
        "Бетке перпендикуляр 200 Н күш әсер етеді, жанасу ауданы 0.5 м². Қысымды тап. Бірдей күш кіші ауданға түссе не өзгеретінін күнделікті мысалмен түсіндір.",
        "Массасы 0.2 кг су қызады. Судың меншікті жылусыйымдылығы 4200 Дж/(кг·°C), температурасы 20 °C-қа артады. Жылу шығынын елемей, қажетті жылу мөлшерін тап және меншікті жылусыйымдылықты қарапайым тілмен түсіндір.",
        "Резистордағы кернеу 12 В, кедергісі 6 Ом. Ток күшін тап. Алдымен кернеу, ток күші және кедергіні түсіндір, содан кейін Ом заңын қолдан.",
        "Кедергілері 2 Ом және 4 Ом екі резистор тізбектей жалғанған. Жалпы кернеу 12 В. Жалпы кедергі мен ток күшін тап, қарапайым тізбек сызбасын көрсет.",
        "Толқынның жиілігі 5 Гц, толқын ұзындығы 2 м. Таралу жылдамдығын тап, жиілік пен толқын ұзындығының мағынасын суретпен түсіндір.",
        "Жинағыш линзаның фокус аралығы 20 см. Нәрсе линзадан 30 см қашықтықта тұр. Жұқа линза формуласымен кескіннің қашықтығын тап, сәулелер сызбасын және кескіннің шын не жалған екенін түсіндір.",
    ),
    "ru": (
        "Тело начинает движение из состояния покоя: начальная скорость 0 м/с, постоянное ускорение 2 м/с², время 5 с. Объясни смысл ускорения простыми словами, найди конечную скорость и пройденный путь, покажи график скорости от времени.",
        "Масса тела 2 кг, ускорение 3 м/с². Найди равнодействующую силу. Сначала объясни смысл силы и ускорения, затем примени закон Ньютона и проверь единицы.",
        "Тело массой 2 кг подняли на высоту 5 м. Ускорение свободного падения 10 м/с². Найди увеличение потенциальной энергии силы тяжести, объясни выбор нулевого уровня у земли и смысл энергии.",
        "Тележка массой 2 кг движется со скоростью 3 м/с и сталкивается с тележкой массой 1 кг со скоростью 0 м/с. После удара они движутся вместе. Импульсом внешних сил пренебречь. Найди общую скорость и объясни импульс как количество движения.",
        "На поверхность перпендикулярно действует сила 200 Н, площадь контакта 0.5 м². Найди давление. На бытовом примере объясни, что изменится при уменьшении площади с той же силой.",
        "Нагревают воду массой 0.2 кг. Удельная теплоёмкость воды 4200 Дж/(кг·°C), температура увеличивается на 20 °C. Пренебрегая потерями, найди количество теплоты и объясни удельную теплоёмкость простыми словами.",
        "Напряжение на резисторе 12 В, сопротивление 6 Ом. Найди силу тока. Сначала объясни напряжение, силу тока и сопротивление, затем примени закон Ома.",
        "Два резистора сопротивлением 2 Ом и 4 Ом соединены последовательно. Общее напряжение 12 В. Найди общее сопротивление и силу тока, покажи простую схему цепи.",
        "Частота волны 5 Гц, длина волны 2 м. Найди скорость распространения, объясни смысл частоты и длины волны с помощью рисунка.",
        "Фокусное расстояние собирающей линзы 20 см. Предмет находится в 30 см от линзы. По формуле тонкой линзы найди расстояние до изображения, покажи ход лучей и объясни, действительное оно или мнимое.",
    ),
    "en": (
        "A body starts from rest: initial speed 0 m/s, constant acceleration 2 m/s², time 5 s. Explain acceleration in simple words, find the final speed and distance travelled, and show a velocity–time graph.",
        "A body has mass 2 kg and acceleration 3 m/s². Find the net force. Explain force and acceleration first, then apply Newton's law and check the units.",
        "A body of mass 2 kg is raised by 5 m. Gravitational acceleration is 10 m/s². Find the increase in gravitational potential energy, explaining the zero level at the ground and the meaning of energy.",
        "A cart of mass 2 kg moving at 3 m/s hits a cart of mass 1 kg with speed 0 m/s. They move together after the collision. Ignore external impulse. Find their common speed and explain momentum as quantity of motion.",
        "A force of 200 N acts perpendicular to a surface with contact area 0.5 m². Find the pressure. Use an everyday example to explain what changes when the area decreases with the same force.",
        "Water of mass 0.2 kg is heated. Its specific heat capacity is 4200 J/(kg·°C), and its temperature rises by 20 °C. Ignore heat loss, find the heat required, and explain specific heat capacity in simple words.",
        "The voltage across a resistor is 12 V and its resistance is 6 ohms. Find the current. Explain voltage, current and resistance before applying Ohm's law.",
        "Two resistors of 2 ohms and 4 ohms are connected in series. The total voltage is 12 V. Find the total resistance and current, and show a simple circuit diagram.",
        "A wave has frequency 5 Hz and wavelength 2 m. Find its propagation speed and explain frequency and wavelength with a diagram.",
        "A converging lens has focal length 20 cm. An object is 30 cm from the lens. Use the thin-lens formula to find the image distance, draw the rays, and explain whether the image is real or virtual.",
    ),
}
# Compatibility for callers that inspect the English example inventory.
EXAMPLE_PROMPTS = list(EXAMPLE_PROMPTS_BY_LANGUAGE["en"])

class CommandBar(QtWidgets.QWidget):
    """Command bar (design: components/forms/CommandBar.jsx).

    A raised shell containing: Examples popup (lightbulb + chevron), hairline
    divider, borderless prompt field, quality selector, and a primary Run
    button that swaps to a danger Cancel while busy.
    """

    submitted = QtCore.pyqtSignal(str)
    cancel_requested = QtCore.pyqtSignal()
    learn_requested = QtCore.pyqtSignal(str, str, bool)  # topic, language, voiceover
    practice_requested = QtCore.pyqtSignal(str)  # language → ENТ physics practice

    _QUALITIES = {"Draft": "l", "Standard": "m", "High": "h"}
    _DURATIONS = {"30 sec": 30.0, "60 sec": 60.0, "2 min": 120.0, "3 min": 180.0}

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommandBarDock")

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(20, 14, 20, 14)

        shell = QtWidgets.QFrame()
        shell.setObjectName("CommandBarShell")
        layout = QtWidgets.QVBoxLayout(shell)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        input_row = QtWidgets.QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(10)
        action_row = QtWidgets.QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)

        # Examples popup button (ghost, menu anchored above the bar)
        self._examples_btn = QtWidgets.QPushButton("Examples")
        self._examples_btn.setObjectName("ExamplesButton")
        self._examples_btn.setIcon(icons.icon("lightbulb", 14, "#65758A"))
        self._examples_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._examples_btn.clicked.connect(self._show_examples_menu)
        input_row.addWidget(self._examples_btn)

        divider = QtWidgets.QFrame()
        divider.setObjectName("VDivider")
        divider.setFixedWidth(1)
        input_row.addWidget(divider)

        # Prompt field - transparent inside the shell
        self.input = QtWidgets.QLineEdit()
        self.input.setObjectName("CommandInput")
        self.input.setPlaceholderText(
            "Ask a physics question or topic to learn…  (Ctrl+Enter to run)"
        )
        self.input.returnPressed.connect(self._submit)
        # Command-bar focus filament: the shell lifts to a cyan hairline while
        # the prompt is focused (design v2 restrained-glow guideline).
        self._shell = shell
        self._busy = False
        self.input.installEventFilter(self)
        self.input.setMinimumWidth(220)
        input_row.addWidget(self.input, 1)

        layout.addLayout(input_row)
        action_row.addStretch(1)

        self._ai_quota = QtWidgets.QLabel()
        self._ai_quota.setObjectName("AIHelpQuota")
        self._ai_quota.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._ai_quota.setStyleSheet(
            "color:#53647A; background:#F1F5F9; border:1px solid #D8E1EC; "
            "border-radius:10px; padding:4px 8px; font-size:11px; font-weight:600;"
        )
        action_row.addWidget(self._ai_quota)

        # Render quality selector
        self._quality = QtWidgets.QComboBox()
        self._quality.setObjectName("QualityCombo")
        for label, value in self._QUALITIES.items():
            self._quality.addItem(label, value)
        self._quality.setCurrentIndex(1)
        # Leave room for the styled padding/arrow as well as translated text.
        self._quality.setMinimumWidth(120)
        self._quality.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._quality.setToolTip(
            "Render quality — Draft 480p / Standard 720p at 30 fps / High 1080p"
        )
        action_row.addWidget(self._quality)

        self._duration = QtWidgets.QComboBox()
        self._duration.setObjectName("DurationCombo")
        for label, value in self._DURATIONS.items():
            self._duration.addItem(label, value)
        self._duration.setCurrentIndex(0)
        self._duration.setFixedWidth(92)
        self._duration.setToolTip(
            "Target animation length. Durations over 45 seconds use resumable, "
            "independently reviewed segments."
        )
        action_row.addWidget(self._duration)

        self._language = QtWidgets.QComboBox()
        self._language.setObjectName("LanguageCombo")
        self._language.addItem("Қазақша", "kk")
        self._language.addItem("Русский", "ru")
        self._language.addItem("English", "en")
        self._language.setCurrentIndex(0)
        self._language.setFixedWidth(100)
        self._language.setToolTip("Lesson and practice language")
        # Language now lives in the persistent application header. Keep this
        # control as the shared value source for lesson/practice workflows.
        self._language.hide()

        self._narration = QtWidgets.QCheckBox("Voiceover")
        self._narration.setChecked(True)
        self._narration.setToolTip(
            "Add spoken narration to this lesson using a voice for the selected language"
        )
        action_row.addWidget(self._narration)

        self.practice_button = QtWidgets.QPushButton("Practice")
        self.practice_button.setObjectName("SecondaryButton")
        self.practice_button.setToolTip("Open a short physics practice test")
        self.practice_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.practice_button.clicked.connect(
            lambda: self.practice_requested.emit(self.get_language())
        )
        action_row.addWidget(self.practice_button)

        # Learn button (topic explainer): build a full narrated lesson.
        self.learn_button = QtWidgets.QPushButton("Learn")
        self.learn_button.setObjectName("SecondaryButton")
        self.learn_button.setIcon(icons.icon("book-open", 14, "#65758A"))
        self.learn_button.setToolTip("Build a full multi-chapter video lesson for this topic")
        self.learn_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.learn_button.clicked.connect(self._learn)
        action_row.addWidget(self.learn_button)

        # Run button (primary) / Cancel (danger) swap
        self.run_button = QtWidgets.QPushButton("Run")
        self.run_button.setObjectName("RunButton")
        self.run_button.setIcon(icons.icon("play", 14, "#FFFFFF"))
        self.run_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.run_button.clicked.connect(self._submit)
        action_row.addWidget(self.run_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setObjectName("CancelButton")
        self.cancel_button.setIcon(icons.icon("square", 14, "#AC4055"))
        self.cancel_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.cancel_button.hide()
        action_row.addWidget(self.cancel_button)

        layout.addLayout(action_row)

        outer.addWidget(shell)
        self._language.currentIndexChanged.connect(lambda _index: self._translate_controls())
        self._translate_controls()

    def _translate_controls(self) -> None:
        translations = {
            "kk": {
                "controls": ("Мысалдар", "Диктор", "Жаттығу", "Сабақ", "Шешу", "Тоқтату", "Физика сұрағын немесе оқу тақырыбын енгізіңіз…"),
                "quality": ("Нобай", "Қалыпты", "Жоғары"),
                "duration": ("30 сек", "1 мин", "2 мин", "3 мин"),
                "quality_tip": "Рендер сапасы: нобай 480p, қалыпты 720p/30 кадр/сек, жоғары 1080p.",
                "duration_tip": "Анимация ұзақтығы. 45 секундтан ұзақ бейне бөлек сегменттерге бөлініп жасалады.",
                "language_tip": "Сабақ пен жаттығу тілі", "voice_tip": "Таңдалған тілде сабаққа дыбыстық түсіндірме қосу",
                "practice_tip": "Физикадан 100 тапсырмалық жаттығуды немесе сынақ ҰБТ-ны ашу", "learn_tip": "Тақырып бойынша бірнеше бөлімнен тұратын бейнесабақ құрастыру",
                "ai_quota": "AI көмек/күн: {remaining}/{limit}",
                "ai_quota_tip": "Күніне 10 AI көмегі. Сұраныс басталғанда бір мүмкіндік жұмсалады.",
                "ai_quota_unavailable": "Лимитті оқу немесе сақтау мүмкін болмады. AI көмегі уақытша қолжетімсіз; жаттығуларды орындауға болады.",
            },
            "ru": {
                "controls": ("Примеры", "Озвучка", "Практика", "Урок", "Решить", "Отмена", "Введите вопрос по физике или тему урока…"),
                "quality": ("Черновик", "Обычное", "Высокое"),
                "duration": ("30 сек", "1 мин", "2 мин", "3 мин"),
                "quality_tip": "Качество рендера: черновик 480p, обычное 720p/30 кадров/с, высокое 1080p.",
                "duration_tip": "Длительность анимации. Видео длиннее 45 секунд собирается из отдельных сегментов.",
                "language_tip": "Язык урока и тренировки", "voice_tip": "Добавить озвучку урока на выбранном языке",
                "practice_tip": "Открыть 100 упражнений по физике или пробник ЕНТ", "learn_tip": "Создать многочастный видеоурок по теме",
                "ai_quota": "AI сегодня: {remaining}/{limit}",
                "ai_quota_tip": "До 10 запросов AI в день. Возможность расходуется при запуске запроса.",
                "ai_quota_unavailable": "Не удалось прочитать или сохранить лимит. AI-помощь временно недоступна; обычная практика доступна.",
            },
            "en": {
                "controls": ("Examples", "Voiceover", "Practice", "Learn", "Run", "Cancel", "Ask a physics question or topic to learn…"),
                "quality": ("Draft", "Standard", "High"),
                "duration": ("30 sec", "60 sec", "2 min", "3 min"),
                "quality_tip": "Render quality: Draft 480p, Standard 720p at 30 fps, High 1080p.",
                "duration_tip": "Target animation length. Durations over 45 seconds use resumable segments.",
                "language_tip": "Lesson and practice language", "voice_tip": "Add spoken narration in the selected language",
                "practice_tip": "Open 100 physics exercises or the UNT mock", "learn_tip": "Build a multi-chapter video lesson for this topic",
                "ai_quota": "AI today: {remaining}/{limit}",
                "ai_quota_tip": "Up to 10 AI help requests per day. A request is counted when it starts.",
                "ai_quota_unavailable": "Could not read or save the allowance. AI help is temporarily unavailable; ordinary practice is available.",
            },
        }
        language = self.get_language()
        copy = translations.get(language, translations["kk"])
        for control, text in zip((self._examples_btn, self._narration, self.practice_button, self.learn_button, self.run_button, self.cancel_button), copy["controls"]):
            control.setText(text)
        self.input.setPlaceholderText(copy["controls"][-1])
        for index, label in enumerate(copy["quality"]):
            self._quality.setItemText(index, label)
        for index, label in enumerate(copy["duration"]):
            self._duration.setItemText(index, label)
        self._quality.setToolTip(copy["quality_tip"])
        self._duration.setToolTip(copy["duration_tip"])
        self._language.setToolTip(copy["language_tip"])
        self._narration.setToolTip(copy["voice_tip"])
        self.practice_button.setToolTip(copy["practice_tip"])
        self.learn_button.setToolTip(copy["learn_tip"])
        self._quota_copy = copy
        self._refresh_ai_quota()

    def set_ai_quota(self, remaining: int | None, limit: int = 10) -> None:
        """Show the remaining student-facing AI help allowance."""
        self._ai_quota_remaining = None if remaining is None else max(0, min(int(limit), int(remaining)))
        self._ai_quota_limit = max(0, int(limit))
        self._refresh_ai_quota()
        self._apply_ai_quota_enabled_state()

    def _refresh_ai_quota(self) -> None:
        if not hasattr(self, "_ai_quota"):
            return
        remaining = getattr(self, "_ai_quota_remaining", 10)
        limit = getattr(self, "_ai_quota_limit", 10)
        copy = getattr(self, "_quota_copy", {})
        self._ai_quota.setText(
            str(copy.get("ai_quota", "AI help: {remaining}/{limit}")).format(
                remaining="—" if remaining is None else remaining, limit=limit
            )
        )
        key = "ai_quota_unavailable" if remaining is None else "ai_quota_tip"
        self._ai_quota.setToolTip(str(copy.get(key, "")))

    def _apply_ai_quota_enabled_state(self) -> None:
        remaining = getattr(self, "_ai_quota_remaining", 10)
        allowed = remaining is not None and remaining > 0
        self.run_button.setEnabled(allowed and not self._busy)
        self.learn_button.setEnabled(allowed and not self._busy)

    def set_language(self, language: str) -> None:
        index = self._language.findData(language)
        if index >= 0 and index != self._language.currentIndex():
            self._language.setCurrentIndex(index)
        else:
            self._translate_controls()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.input:
            if event.type() == QtCore.QEvent.Type.FocusIn:
                self._set_shell_focused(True)
            elif event.type() == QtCore.QEvent.Type.FocusOut:
                self._set_shell_focused(False)
        return super().eventFilter(obj, event)

    def _set_shell_focused(self, focused: bool) -> None:
        self._shell.setProperty("focused", "true" if focused else "false")
        self._shell.style().unpolish(self._shell)
        self._shell.style().polish(self._shell)

    def _show_examples_menu(self) -> None:
        menu = QtWidgets.QMenu(self)
        for prompt in EXAMPLE_PROMPTS_BY_LANGUAGE[self.get_language()]:
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
        return str(self._quality.currentData() or "l")

    def set_quality(self, flag: str) -> None:
        """Select quality by Manim flag (used by the Settings default)."""
        for index, value in enumerate(self._QUALITIES.values()):
            if value == flag:
                self._quality.setCurrentIndex(index)
                return

    def get_duration_target(self) -> float:
        """Return the requested animation duration in seconds."""
        return float(self._duration.currentData() or 30.0)

    def get_language(self) -> str:
        """Return the selected lesson/practice language code."""
        return str(self._language.currentData() or "kk")

    def get_voiceover_enabled(self) -> bool:
        return self._narration.isChecked()

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        self.run_button.setVisible(not busy)
        self.learn_button.setVisible(not busy)
        self.practice_button.setVisible(not busy)
        self.cancel_button.setVisible(busy)
        self.input.setDisabled(busy)
        self._apply_ai_quota_enabled_state()

    def _submit(self) -> None:
        draft = self.input.text()
        prompt = draft.strip()
        if prompt and self.run_button.isVisible() and self.run_button.isEnabled():
            self.input.clear()
            self._submission_draft = draft
            try:
                self.submitted.emit(prompt)
            finally:
                self._submission_draft = None

    def _learn(self) -> None:
        draft = self.input.text()
        topic = draft.strip()
        if topic and self.learn_button.isVisible() and self.learn_button.isEnabled():
            self.input.clear()
            self._lesson_submission_draft = draft
            try:
                self.learn_requested.emit(
                    topic, self.get_language(), self.get_voiceover_enabled()
                )
            finally:
                self._lesson_submission_draft = None
