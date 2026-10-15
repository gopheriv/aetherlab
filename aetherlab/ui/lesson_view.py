"""Multi-chapter lesson player, checks, and chapter navigation."""

from __future__ import annotations

import html
from pathlib import Path

from aetherlab.ui import icons
from aetherlab.ui.live_canvas import LiveCanvas, build_canvas_state
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt

require_qt()


def video_file_available(path: str) -> bool:
    """Cheap UI availability check; decoding is verified by the render backend."""
    if not path:
        return False
    try:
        candidate = Path(path)
        return candidate.is_file() and candidate.stat().st_size > 0
    except (OSError, TypeError, ValueError):
        return False


_COPY = {
    "kk": {
        "lesson": "Сабақ", "regenerate": "Қайта жасау", "regenerate_tip": "Бұл сабақты кэшті пайдаланбай, басынан құрастыру",
        "guide": "Оқу құралын экспорттау", "bundle": "Сабақты жинақтау", "bundle_tip": "Бейнені, субтитрді, оқу құралын және HTML ойнатқышты ZIP архивіне сақтау",
        "pdf": "PDF конспект", "pdf_tip": "Оқу PDF конспектісін ашу", "content_review": "Мазмұн тексерісі қажет", "cc": "Субтитр · {n} жол",
        "video": "Бейне", "transcript": "Мәтін", "terms": "Қазақша терминдер", "questions": "Сұрақтар", "references": "Дереккөздер", "explore": "Тәжірибе жасау",
        "course_status": "Курс прогресі сұраққа жауап бергеннен кейін басталады.", "review_due": "Қайталау уақыты келген сұрақтар", "review_count": "Қайталау керек сұрақтар: {n}",
        "empty": "Тақырып енгізіп, «Оқу» түймесін бассаңыз, сабақ жасалады.", "video_unavailable": "Бұл нұсқада бейне ойнатқыш қолжетімсіз.",
        "video_empty": "Бұл сабақтың бейнесі әлі жасалмаған.",
        "no_citations": "Дереккөздер көрсетілмеген.", "chapter_not_rendered": "Бұл бөлім рендерленбеді. Сабақ қолжетімді бөлімдермен жалғасады.",
        "play": "Ойнату", "pause": "Кідірту", "stop": "Тоқтату",
        "confidence_low": "Сенімділік: төмен", "confidence_medium": "Сенімділік: орташа", "confidence_high": "Сенімділік: жоғары",
        "confidence_tip": "Жауапты тексермес бұрын өз сенімділігіңізді белгілеңіз.", "reveal": "Жауапты көрсету", "correct": "✓ Дұрыс", "wrong": "✗ Дұрыс емес. Жауабы:", "answer": "Үлгі жауап:",
        "predict_title": "Ойнатпас бұрын болжаңыз", "review_title": "Қайталау", "recall_title": "Еске түсіру",
        "predict_hint": "Бұл бөлім басталмас бұрын болжам жасаңыз.", "retrieval_hint": "Жалғастырмас бұрын алдыңғы бөлімді еске түсіріңіз.", "review_hint": "Түсіндірмені қарамай тұрып жауапты еске түсіріңіз.",
        "recall_hint": "Түсіндірмені ашпас бұрын сұраққа жауап беріңіз.", "your_answer": "Жауабыңыз", "submit": "Жауапты жіберу", "continue": "Жалғастыру",
        "choose_first": "Алдымен нұсқаны таңдаңыз немесе жауап енгізіңіз.", "right": "Дұрыс.", "compare": "Дұрыс емес. Жауабыңызды түсіндірмемен салыстырыңыз.", "recorded": "Жауап тіркелді. Үлгі жауаппен салыстырыңыз.",
        "model_answer": "Үлгі жауап:", "play_hint": "Параметрлерді өзгертіп, графиктердің қалай өзгеретінін бақылаңыз.", "explore_unavailable": "Бұл сабақ үшін интерактивті тәжірибе қолжетімсіз.",
    },
    "ru": {
        "lesson": "Урок", "regenerate": "Создать заново", "regenerate_tip": "Собрать урок заново без использования кэша",
        "guide": "Экспорт конспекта", "bundle": "Экспорт урока", "bundle_tip": "Сохранить видео, субтитры, конспект и HTML-плеер в ZIP-архив",
        "pdf": "PDF-конспект", "pdf_tip": "Открыть учебный PDF-конспект", "content_review": "Требуется проверка содержания", "cc": "Субтитры · {n}",
        "video": "Видео", "transcript": "Текст", "terms": "Казахские термины", "questions": "Вопросы", "references": "Источники", "explore": "Эксперимент",
        "course_status": "Прогресс курса начнётся после ответа на вопрос.", "review_due": "Повторить вопросы по расписанию", "review_count": "Вопросов для повторения: {n}",
        "empty": "Введите тему и нажмите «Изучить», чтобы создать урок.", "video_unavailable": "В этой сборке видеоплеер недоступен.",
        "video_empty": "Видео этого урока ещё не создано.",
        "no_citations": "Источники не указаны.", "chapter_not_rendered": "Этот раздел не был обработан. Урок продолжится с доступными разделами.",
        "play": "Воспроизвести", "pause": "Пауза", "stop": "Остановить",
        "confidence_low": "Уверенность: низкая", "confidence_medium": "Уверенность: средняя", "confidence_high": "Уверенность: высокая",
        "confidence_tip": "Оцените уверенность до проверки ответа.", "reveal": "Показать ответ", "correct": "✓ Верно", "wrong": "✗ Неверно. Ответ:", "answer": "Пример ответа:",
        "predict_title": "Сначала предположите", "review_title": "Повторение", "recall_title": "Вспомните",
        "predict_hint": "Предположите, что произойдёт, до начала этой главы.", "retrieval_hint": "Вспомните предыдущую главу, прежде чем продолжить.", "review_hint": "Вспомните ответ до просмотра объяснения.",
        "recall_hint": "Ответьте на вопрос до просмотра объяснения.", "your_answer": "Ваш ответ", "submit": "Отправить ответ", "continue": "Продолжить",
        "choose_first": "Сначала выберите вариант или введите ответ.", "right": "Верно.", "compare": "Неверно. Сравните свой ответ с объяснением.", "recorded": "Ответ сохранён. Сравните его с примером.",
        "model_answer": "Пример ответа:", "play_hint": "Изменяйте параметры и наблюдайте за графиками.", "explore_unavailable": "Интерактивный эксперимент для этого урока недоступен.",
    },
    "en": {
        "lesson": "Lesson", "regenerate": "Regenerate", "regenerate_tip": "Rebuild this lesson from scratch without using the cache",
        "guide": "Export study guide", "bundle": "Export lesson bundle", "bundle_tip": "Export a ZIP with video, subtitles, study guide, and HTML player",
        "pdf": "Study PDF", "pdf_tip": "Open the study PDF", "content_review": "Needs content review", "cc": "Subtitles · {n}",
        "video": "Video", "transcript": "Transcript", "terms": "Kazakh terms", "questions": "Questions", "references": "References", "explore": "Explore",
        "course_status": "Course progress starts when you answer a quiz question.", "review_due": "Review due questions", "review_count": "Review {n} due question(s)",
        "empty": "Enter a topic and press Learn to generate a lesson.", "video_unavailable": "Video playback is unavailable in this build.",
        "video_empty": "This lesson does not have a rendered video yet.",
        "no_citations": "No citations available.", "chapter_not_rendered": "This chapter did not render; the lesson continues with available chapters.",
        "play": "Play", "pause": "Pause", "stop": "Stop",
        "confidence_low": "Confidence: low", "confidence_medium": "Confidence: medium", "confidence_high": "Confidence: high",
        "confidence_tip": "Rate your confidence before checking the answer.", "reveal": "Reveal answer", "correct": "✓ Correct", "wrong": "✗ Not quite. Answer:", "answer": "Model answer:",
        "predict_title": "Predict before play", "review_title": "Spaced review", "recall_title": "Quick recall",
        "predict_hint": "Make a prediction before this chapter starts.", "retrieval_hint": "Recall the previous chapter before continuing.", "review_hint": "Answer from memory before checking the explanation.",
        "recall_hint": "Answer the question before checking the explanation.", "your_answer": "Your answer", "submit": "Submit answer", "continue": "Continue",
        "choose_first": "Choose an option or enter a response first.", "right": "That's right.", "compare": "Not quite; compare your answer with the explanation.", "recorded": "Response recorded. Compare it with the model answer.",
        "model_answer": "Model answer:", "play_hint": "Adjust the parameters and watch the curves respond.", "explore_unavailable": "Interactive exploration is unavailable for this lesson.",
    },
}

class _QuestionCard(QtWidgets.QFrame):
    """One check-yourself item: MCQ radios with immediate feedback, or an open
    question that reveals a model answer."""

    answer_recorded = QtCore.pyqtSignal(bool, str)

    def __init__(self, index: int, question, language: str = "kk", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFrame")
        self._q = question
        self._language = language if language in _COPY else "kk"
        self._answered = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        prompt = QtWidgets.QLabel(f"{index}. {question.q}")
        prompt.setWordWrap(True)
        prompt.setStyleSheet("color: #18283D; font-size: 13px; font-weight: 600;")
        layout.addWidget(prompt)

        self._confidence = None

        self._feedback = QtWidgets.QLabel("")
        self._feedback.setWordWrap(True)
        self._feedback.setStyleSheet("color: #65758A; font-size: 12px;")

        if question.choices:  # MCQ
            self._confidence = QtWidgets.QComboBox()
            self._confidence.addItem("", "low")
            self._confidence.addItem("", "medium")
            self._confidence.addItem("", "high")
            self._confidence.setCurrentIndex(1)
            self._confidence.setToolTip("")
            layout.addWidget(self._confidence)
            self._group = QtWidgets.QButtonGroup(self)
            for choice in question.choices:
                rb = QtWidgets.QRadioButton(choice)
                rb.setStyleSheet("color: #24364B; font-size: 12.5px; spacing: 8px;")
                rb.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                rb.toggled.connect(lambda checked, c=choice: checked and self._answer_mcq(c))
                self._group.addButton(rb)
                layout.addWidget(rb)
            layout.addWidget(self._feedback)
        else:  # open question
            self._reveal = QtWidgets.QPushButton()
            self._reveal.setObjectName("SecondaryButton")
            self._reveal.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self._reveal.clicked.connect(self._reveal_open)
            layout.addWidget(self._reveal)
            layout.addWidget(self._feedback)
        self.set_language(self._language)

    def set_language(self, language: str) -> None:
        self._language = language if language in _COPY else "kk"
        text = _COPY[self._language]
        if self._confidence is not None:
            for index, key in enumerate(("confidence_low", "confidence_medium", "confidence_high")):
                self._confidence.setItemText(index, text[key])
            self._confidence.setToolTip(text["confidence_tip"])
        if hasattr(self, "_reveal"):
            self._reveal.setText(text["reveal"])

    def _answer_mcq(self, choice: str) -> None:
        # BUG-27: only the first selection counts. toggled fires on every
        # radio change, so without this guard a student who switches options
        # (or clicks each until Correct appears) would record multiple
        # attempts, inflating the persisted course score. Lock after answering.
        if self._answered:
            return
        self._answered = True
        if self._confidence is not None:
            self._confidence.setEnabled(False)
        correct = str(choice).strip() == str(self._q.answer).strip()
        why = f" — {self._q.why}" if self._q.why else ""
        text = _COPY[self._language]
        self._feedback.setText(
            (text["correct"] if correct else f"{text['wrong']} {self._q.answer}") + why
        )
        self._feedback.setStyleSheet(
            f"color: {'#26725C' if correct else '#AC4055'}; font-size: 12px;"
        )
        for button in self._group.buttons():
            button.setEnabled(False)
        self.answer_recorded.emit(correct, str(choice))

    def confidence_level(self) -> str:
        return str(self._confidence.currentData() or "medium") if self._confidence else "medium"

    def _reveal_open(self) -> None:
        self._feedback.setText(f"{_COPY[self._language]['model_answer']} {self._q.answer}")
        self._feedback.setStyleSheet("color: #26725C; font-size: 12px;")

class _LessonCheckDialog(QtWidgets.QDialog):
    """Prediction/retrieval gate that reveals feedback only after submission."""

    def __init__(self, question: dict, kind: str, parent: QtWidgets.QWidget | None = None,
                 language: str = "kk") -> None:
        super().__init__(parent)
        self._question = question
        self._kind = kind
        self._language = language if language in _COPY else "kk"
        text = _COPY[self._language]
        self._radios: list[QtWidgets.QRadioButton] = []
        self.answer_submitted = False
        self.answer_correct: bool | None = None
        self.setWindowTitle(
            text["predict_title"] if kind == "prediction"
            else text["review_title"] if kind == "spaced_review"
            else text["recall_title"]
        )
        self.setMinimumWidth(420)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        heading_text = {
            "prediction": text["predict_hint"],
            "retrieval": text["retrieval_hint"],
            "spaced_review": text["review_hint"],
        }
        heading = QtWidgets.QLabel(
            heading_text.get(kind, text["recall_hint"])
        )
        heading.setStyleSheet("color: #486A91; font-size: 13px; font-weight: 700;")
        layout.addWidget(heading)
        prompt = QtWidgets.QLabel(str(question.get("q", "")))
        prompt.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        choices = [str(choice) for choice in question.get("choices", []) if str(choice).strip()]
        self._answer_edit = None
        if choices:
            for choice in choices:
                radio = QtWidgets.QRadioButton(choice)
                self._radios.append(radio)
                layout.addWidget(radio)
        else:
            self._answer_edit = QtWidgets.QLineEdit()
            self._answer_edit.setPlaceholderText(text["your_answer"])
            layout.addWidget(self._answer_edit)

        self._feedback = QtWidgets.QLabel("")
        self._feedback.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._feedback.setWordWrap(True)
        self._feedback.setStyleSheet("color: #65758A; font-size: 11px;")
        layout.addWidget(self._feedback)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        self._submit = QtWidgets.QPushButton(text["submit"])
        self._submit.setObjectName("PrimaryButton")
        self._continue = QtWidgets.QPushButton(text["continue"])
        self._continue.setObjectName("PrimaryButton")
        self._continue.setEnabled(False)
        buttons.addWidget(self._submit)
        buttons.addWidget(self._continue)
        layout.addLayout(buttons)
        self._submit.clicked.connect(self._submit_answer)
        self._continue.clicked.connect(self.accept)

    def _submit_answer(self) -> None:
        selected = next((radio.text() for radio in self._radios if radio.isChecked()), "")
        if self._answer_edit is not None:
            selected = self._answer_edit.text().strip()
        if not selected:
            self._feedback.setText(_COPY[self._language]["choose_first"])
            return

        choices = [str(choice) for choice in self._question.get("choices", [])]
        expected = str(self._question.get("answer", "")).strip()
        if choices and expected:
            selected_key = " ".join(selected.casefold().split())
            expected_key = " ".join(expected.casefold().split())
            correct = selected_key == expected_key
            if not correct and len(expected) == 1 and expected.isalpha():
                correct = (
                    0 <= ord(expected.upper()) - ord("A") < len(choices)
                    and selected == choices[ord(expected.upper()) - ord("A")]
                )
            if not correct and len(expected) > 2 and expected[1] in ".):":
                correct = expected_key[2:].strip() == selected_key
            verdict = _COPY[self._language]["right"] if correct else _COPY[self._language]["compare"]
            color = "#26725C" if correct else "#8A5A24"
            self.answer_correct = correct
        else:
            verdict = _COPY[self._language]["recorded"]
            color = "#335F92"
            self.answer_correct = None
        explanation = str(self._question.get("why", "")).strip()
        model_answer = f"{_COPY[self._language]['model_answer']} {expected}" if expected else ""
        detail = " ".join(part for part in (verdict, model_answer, explanation) if part)
        self._feedback.setText(detail)
        self._feedback.setStyleSheet(f"color: {color}; font-size: 11px;")
        for radio in self._radios:
            radio.setEnabled(False)
        if self._answer_edit is not None:
            self._answer_edit.setEnabled(False)
        self._submit.setEnabled(False)
        self._continue.setEnabled(True)
        self.answer_submitted = True

class LessonView(QtWidgets.QWidget):
    """The topic-explainer lesson surface: a chapter outline that seeks the
    assembled video, plus transcript, interactive questions, and references."""

    chapter_seek_requested = QtCore.pyqtSignal(float)  # seconds
    export_requested = QtCore.pyqtSignal()
    share_bundle_requested = QtCore.pyqtSignal()
    quiz_answered = QtCore.pyqtSignal(int, bool, str)  # question index, correct, choice
    review_due_clicked = QtCore.pyqtSignal()
    regenerate_requested = QtCore.pyqtSignal()  # rebuild this lesson from scratch
    study_pdf_requested = QtCore.pyqtSignal()  # open the bundled study PDF

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._language = "kk"
        self._question_cards: list[_QuestionCard] = []
        self._bundle = None
        self._chapter_offsets: list[float] = []
        self._chapter_playable: list[bool] = []
        self._completed_gate_checks: set[tuple[int, str]] = set()
        self._gate_in_progress = False
        self._quiz_confidence: dict[int, str] = {}
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        self._title = QtWidgets.QLabel()
        self._title.setObjectName("PanelTitle")
        header.addWidget(self._title)
        header.addStretch()
        self._audience = QtWidgets.QLabel("")
        self._audience.setStyleSheet("color: #65758A; font-size: 11px;")
        header.addWidget(self._audience)
        self._review_badge = QtWidgets.QLabel("")
        self._review_badge.setStyleSheet(
            "color: #8A5A1B; font-size: 11px; font-weight: 700; "
            "background: #FBF1E4; border: 1px solid #E3C98F; "
            "border-radius: 8px; padding: 3px 8px;"
        )
        self._review_badge.hide()
        header.addWidget(self._review_badge)
        self._regen_btn = QtWidgets.QPushButton()
        self._regen_btn.setObjectName("SecondaryButton")
        self._regen_btn.setIcon(icons.icon("refresh-cw", 13, "#65758A"))
        self._regen_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._regen_btn.clicked.connect(self.regenerate_requested.emit)
        header.addWidget(self._regen_btn)
        self._export_btn = QtWidgets.QPushButton()
        self._export_btn.setObjectName("SecondaryButton")
        self._export_btn.setIcon(icons.icon("download", 13, "#65758A"))
        self._export_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._export_btn.clicked.connect(self.export_requested.emit)
        header.addWidget(self._export_btn)
        self._bundle_btn = QtWidgets.QPushButton()
        self._bundle_btn.setObjectName("SecondaryButton")
        self._bundle_btn.setAccessibleName("Lesson bundle export")
        self._bundle_btn.setIcon(icons.icon("folder-open", 13, "#65758A"))
        self._bundle_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._bundle_btn.clicked.connect(self.share_bundle_requested.emit)
        header.addWidget(self._bundle_btn)
        self._pdf_btn = QtWidgets.QPushButton()
        self._pdf_btn.setObjectName("SecondaryButton")
        self._pdf_btn.setIcon(icons.icon("file-text", 13, "#65758A"))
        self._pdf_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._pdf_btn.clicked.connect(self.study_pdf_requested.emit)
        self._pdf_btn.hide()
        header.addWidget(self._pdf_btn)
        layout.addLayout(header)

        self._split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self._outline = QtWidgets.QListWidget()
        self._outline.setObjectName("HistoryList")
        self._outline.setMinimumWidth(160)
        self._outline.setMaximumWidth(280)
        self._outline.itemClicked.connect(self._on_outline_click)
        self._split.addWidget(self._outline)

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.addTab(self._build_video(), "")
        self._transcript = QtWidgets.QTextEdit()
        self._transcript.setReadOnly(True)
        self._tabs.addTab(self._transcript, "")

        self._glossary = QtWidgets.QTextEdit()
        self._glossary.setReadOnly(True)
        self._tabs.addTab(self._glossary, "")

        self._questions_page = QtWidgets.QWidget()
        questions_page_layout = QtWidgets.QVBoxLayout(self._questions_page)
        questions_page_layout.setContentsMargins(0, 0, 0, 0)
        questions_page_layout.setSpacing(8)
        self._course_status = QtWidgets.QLabel()
        self._course_status.setObjectName("CourseProgressStatus")
        self._course_status.setWordWrap(True)
        self._course_status.setStyleSheet(
            "color: #65758A; font-size: 12px; padding: 8px 10px; "
            "border: 1px solid #D8E1EC; border-radius: 8px; background: #FFFFFF;"
        )
        questions_page_layout.addWidget(self._course_status)
        self._review_due_button = QtWidgets.QPushButton()
        self._review_due_button.setObjectName("ReviewDueQuestions")
        self._review_due_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._review_due_button.setStyleSheet(
            "QPushButton { color: #536F90; background: #EDF2F8; border: 1px solid #536F90; "
            "border-radius: 8px; padding: 7px 10px; text-align: left; }"
                "QPushButton:hover { background: #E9EFF7; }"
        )
        self._review_due_button.clicked.connect(self.review_due_clicked.emit)
        self._review_due_button.hide()
        questions_page_layout.addWidget(self._review_due_button)

        self._questions_scroll = QtWidgets.QScrollArea()
        self._questions_scroll.setWidgetResizable(True)
        self._questions_host = QtWidgets.QWidget()
        self._questions_layout = QtWidgets.QVBoxLayout(self._questions_host)
        self._questions_layout.setSpacing(10)
        self._questions_layout.addStretch()
        self._questions_scroll.setWidget(self._questions_host)
        questions_page_layout.addWidget(self._questions_scroll, 1)
        self._tabs.addTab(self._questions_page, "")

        self._references = QtWidgets.QTextEdit()
        self._references.setReadOnly(True)
        self._tabs.addTab(self._references, "")

        # "Play with it" — an embedded live canvas seeded from the lesson's
        # domain, completing the pedagogy loop (interactive chapter).
        explore = QtWidgets.QWidget()
        ex_layout = QtWidgets.QVBoxLayout(explore)
        ex_layout.setContentsMargins(0, 0, 0, 0)
        ex_layout.setSpacing(6)
        self._explore_hint = QtWidgets.QLabel("")
        self._explore_hint.setWordWrap(True)
        self._explore_hint.setStyleSheet("color: #65758A; font-size: 12px; padding: 4px 2px;")
        ex_layout.addWidget(self._explore_hint)
        self._explore_canvas = LiveCanvas()
        ex_layout.addWidget(self._explore_canvas, 1)
        self._tabs.addTab(explore, "")

        self._split.addWidget(self._tabs)
        self._split.setSizes([260, 640])
        self._split.setStretchFactor(0, 0)
        self._split.setStretchFactor(1, 1)
        layout.addWidget(self._split, 1)

        self._empty = QtWidgets.QLabel()
        self._empty.setObjectName("EmptyHint")
        self._empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)
        self._set_populated(False)
        self.set_language(self._language)

    def _build_video(self) -> QtWidgets.QWidget:
        """Inline lesson player (true-black stage + play/pause/stop). Guarded so
        the widget still builds if QtMultimedia is unavailable."""
        container = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self._player = None
        self._video_control_buttons: list[tuple[QtWidgets.QPushButton, str]] = []
        self._cc_label = None
        self._video_unavailable_label = None
        try:
            from PyQt6.QtMultimedia import QMediaPlayer
            from PyQt6.QtMultimediaWidgets import QVideoWidget

            stage = QtWidgets.QWidget()
            stage.setStyleSheet("background:#000000; border-radius:8px;")
            stage_layout = QtWidgets.QGridLayout(stage)
            stage_layout.setContentsMargins(0, 0, 0, 0)
            self._video_widget = QVideoWidget()
            self._video_widget.setMinimumSize(280, 158)
            self._video_widget.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            self._video_widget.setStyleSheet("background-color: #000;")
            stage_layout.addWidget(self._video_widget, 0, 0)
            self._video_empty_overlay = QtWidgets.QLabel()
            self._video_empty_overlay.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self._video_empty_overlay.setStyleSheet(
                "color:#D7DEE8; background:rgba(0,0,0,150); padding:10px 16px; "
                "border-radius:8px; font-size:12px;"
            )
            self._video_empty_overlay.setAttribute(
                QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            stage_layout.addWidget(
                self._video_empty_overlay, 0, 0, QtCore.Qt.AlignmentFlag.AlignCenter
            )
            v.addWidget(stage, 1)
            self._player = QMediaPlayer()
            self._player.setVideoOutput(self._video_widget)

            controls = QtWidgets.QHBoxLayout()
            self._player.positionChanged.connect(self._on_player_position_changed)
            for label, slot in (("play", self._request_play),
                                ("pause", lambda: self._player.pause()),
                                ("square", lambda: self._player.stop())):
                b = QtWidgets.QPushButton()
                b.setIcon(icons.icon(label, 14, "#65758A"))
                b.setFixedSize(28, 28)
                b.setObjectName("VideoControlBtn")
                b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                self._video_control_buttons.append(
                    (b, {"play": "play", "pause": "pause", "square": "stop"}[label])
                )
                b.clicked.connect(slot)
                controls.addWidget(b)
            controls.addStretch()
            self._cc_label = QtWidgets.QLabel("")
            self._cc_label.setStyleSheet("color: #65758A; font-size: 11px;")
            self._cc_label.hide()
            controls.addWidget(self._cc_label)
            v.addLayout(controls)
        except Exception:  # noqa: BLE001 — multimedia optional
            self._video_unavailable_label = QtWidgets.QLabel()
            self._video_unavailable_label.setObjectName("EmptyHint")
            self._video_unavailable_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            v.addWidget(self._video_unavailable_label, 1)
        return container

    def set_language(self, language: str) -> None:
        self._language = language if language in _COPY else "kk"
        text = _COPY[self._language]
        self._title.setText(text["lesson"] if self._bundle is None else self._title.text())
        self._regen_btn.setText(text["regenerate"])
        self._regen_btn.setToolTip(text["regenerate_tip"])
        self._export_btn.setText(text["guide"])
        self._bundle_btn.setText(text["bundle"])
        self._bundle_btn.setToolTip(text["bundle_tip"])
        self._pdf_btn.setText(text["pdf"])
        self._pdf_btn.setToolTip(text["pdf_tip"])
        self._review_badge.setText(text["content_review"])
        self._refresh_cc_label()
        for index, key in enumerate(("video", "transcript", "terms", "questions", "references", "explore")):
            self._tabs.setTabText(index, text[key])
        self._course_status.setText(text["course_status"])
        self._review_due_button.setText(text["review_due"])
        self._empty.setText(text["empty"])
        if self._video_unavailable_label is not None:
            self._video_unavailable_label.setText(text["video_unavailable"])
        if hasattr(self, "_video_empty_overlay"):
            self._video_empty_overlay.setText(text["video_empty"])
        for button, key in self._video_control_buttons:
            button.setToolTip(text[key])
            button.setAccessibleName(text[key])
        for card in self._question_cards:
            card.set_language(self._language)
        if self._bundle is not None:
            self._tabs.setTabText(2, text["terms"])

    def clear_video(self) -> None:
        """Release the previous lesson's media before presenting new content."""
        if self._player:
            self._player.stop()
            self._player.setSource(QtCore.QUrl())
        if hasattr(self, "_video_empty_overlay"):
            self._video_empty_overlay.show()

    def set_video(self, path: str) -> None:
        """Load the assembled lesson MP4 into the inline player."""
        self.clear_video()
        if not self._player or not video_file_available(path):
            return
        from PyQt6.QtCore import QUrl

        self._video_empty_overlay.hide()
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._tabs.setCurrentIndex(0)  # Video tab

    def _refresh_cc_label(self) -> None:
        """Show the subtitle cue count for bundles that ship an .srt file."""
        if self._cc_label is None:
            return
        cues = 0
        srt_path = str(getattr(self._bundle, "srt_path", "") or "")
        if srt_path:
            try:
                cues = Path(srt_path).read_text(encoding="utf-8").count("-->")
            except (OSError, ValueError):
                cues = 0
        if cues > 0:
            self._cc_label.setText(_COPY[self._language]["cc"].format(n=cues))
            self._cc_label.show()
        else:
            self._cc_label.hide()

    def _set_populated(self, populated: bool) -> None:
        self._split.setVisible(populated)
        self._empty.setVisible(not populated)

    def set_lesson(self, bundle) -> None:
        """Populate the view from a LessonBundle (plan + rendered chapters)."""
        self.clear_video()
        self._bundle = bundle
        plan = bundle.plan
        from aetherlab.core.language import LANGUAGE_NAMES, normalize_language

        language = normalize_language(getattr(plan, "language", "en"))
        self.set_language(language)
        self._title.setText(plan.title or _COPY[language]["lesson"])
        self._tabs.setTabText(2, {
            "kk": "Қазақша терминдер",
            "ru": "Казахские термины",
            "en": "Kazakh terms",
        }[language])
        self._audience.setText(
            f"{plan.audience.replace('_', ' ')} · {LANGUAGE_NAMES[language]}"
        )
        terms = getattr(plan, "kazakh_terms", []) or []
        if not terms and plan.model_name != "localized-offline-notice":
            from aetherlab.services.ent_physics_bank import glossary_for_language

            terms = list(glossary_for_language(language))
        glossary_html = []
        for item in terms:
            if not isinstance(item, dict):
                continue
            term = html.escape(str(item.get("term_kk", "")).strip())
            translation = html.escape(str(item.get("translation", "")).strip())
            meaning = html.escape(str(item.get("meaning", "")).strip())
            if term:
                glossary_html.append(
                    f"<p><b style='color:#486A91'>{term}</b>"
                    f"{f' · {translation}' if translation else ''}<br>"
                    f"<span style='color:#24364B'>{meaning}</span></p>"
                )
        self._glossary.setHtml("".join(glossary_html))

        self._outline.clear()
        transcript_html: list[str] = []
        self._chapter_offsets = []
        self._chapter_playable = []
        self._completed_gate_checks.clear()
        self._quiz_confidence.clear()
        # True per-chapter start times in the assembled video (account for the
        # intro/chapter title cards + crossfades). These align with the RENDERED
        # chapters, so walk plan.chapters with a separate rendered index; a
        # non-rendered chapter (e.g. 'interactive') has no clip and stays at the
        # running position. Empty offsets (old cache / plain concat) fall back to
        # a running sum of clip durations.
        offsets = list(getattr(bundle, "chapter_offsets", []) or [])
        durations = _bundle_chapter_durations(bundle)
        rendered_indexes = list(getattr(bundle, "rendered_chapter_indexes", []) or [])
        mapped_rendered = (
            {idx: r for r, idx in enumerate(rendered_indexes)}
            if len(rendered_indexes) == len(getattr(bundle, "chapter_scenes", []) or [])
            else {}
        )
        try:
            from aetherlab.services import lesson_pipeline

            rendered_kinds = set(lesson_pipeline._RENDERED_KINDS)
        except Exception:  # noqa: BLE001
            rendered_kinds = {"scene", "equation_card", "recap"}
        t = 0.0
        r = 0  # index into the rendered-chapter-aligned offsets/durations
        for i, ch in enumerate(plan.chapters):
            is_rendered = ch.kind in rendered_kinds
            missing_render = bool(mapped_rendered and is_rendered and i not in mapped_rendered)
            if mapped_rendered:
                mapped_r = mapped_rendered.get(i)
                seek = float(offsets[mapped_r]) if mapped_r is not None and mapped_r < len(offsets) else t
            else:
                mapped_r = r if is_rendered else None
                seek = float(offsets[r]) if is_rendered and r < len(offsets) else t
            suffix = " (not rendered)" if missing_render else ""
            item = QtWidgets.QListWidgetItem(f"{i + 1}. {ch.title}{suffix}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, seek)
            item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, i)
            self._chapter_playable.append(is_rendered and not missing_render)
            if missing_render:
                item.setToolTip(_COPY[language]["chapter_not_rendered"])
                item.setForeground(QtGui.QColor("#65758A"))
            self._outline.addItem(item)
            self._chapter_offsets.append(seek)
            safe_title = html.escape(str(ch.title))
            fc = (
                f" <span style='color:#65758A'>({html.escape(str(ch.fact_check))})</span>"
                if ch.fact_check else ""
            )
            transcript_html.append(
                f"<p><b style='color:#486A91'>{i + 1}. {safe_title}</b>{fc}<br>"
                f"<span style='color:#24364B'>{html.escape(str(ch.narration or ch.goal))}</span></p>"
            )
            if mapped_r is not None:
                dur = durations[mapped_r] if mapped_r < len(durations) else 0.0
                t = seek + dur
            if is_rendered and not mapped_rendered:
                r += 1
        self._transcript.setHtml("".join(transcript_html))

        while self._questions_layout.count() > 1:
            w = self._questions_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._question_cards = []
        for i, q in enumerate(plan.questions, 1):
            card = _QuestionCard(i, q, language)
            self._question_cards.append(card)
            card.answer_recorded.connect(
                lambda correct, choice, idx=i - 1, question_card=card: self._on_quiz_answer(
                    idx, correct, choice, question_card.confidence_level()
                )
            )
            self._questions_layout.insertWidget(self._questions_layout.count() - 1, card)

        cites: list[str] = []
        for ch in plan.chapters:
            for c in ch.citations:
                if c not in cites:
                    cites.append(c)
        self._references.setHtml(
            " ".join(
                f"<span style='color:#C4B5FD;background:#1B2235;"
                f"border:1px solid #536F90;border-radius:10px;padding:3px 8px;margin:2px'>"
                f"{html.escape(c)}</span>"
                for c in cites
            ) if cites else f"<span style='color:#65758A'>{_COPY[language]['no_citations']}</span>"
        )

        self._seed_explore(plan)
        self._pdf_btn.setVisible(video_file_available(str(getattr(bundle, "pdf_path", "") or "")))
        review = getattr(bundle, "review_status", {}) or {}
        self._review_badge.setVisible(
            str(review.get("teacher_translation_review", "")) == "pending"
        )
        self._refresh_cc_label()
        self.set_course_summary(_COPY[language]["course_status"])
        self.set_due_review_count(0)
        self._set_populated(True)
        # Materials are usable before video generation; a subsequent valid
        # set_video() selects the Video tab when the assembled file is ready.
        self._tabs.setCurrentIndex(1)

    def set_course_summary(self, message: str) -> None:
        self._course_status.setText(message)

    def set_due_review_count(self, count: int) -> None:
        count = max(0, int(count))
        if self._language == "kk":
            label = f"Қайталау керек сұрақтар: {count}"
        elif self._language == "ru":
            label = f"Вопросов для повторения: {count}"
        else:
            label = f"Review {count} due question{'s' if count != 1 else ''}"
        self._review_due_button.setText(label)
        self._review_due_button.setVisible(count > 0)

    def confidence_for_question(self, question_index: int) -> str:
        return self._quiz_confidence.get(int(question_index), "medium")

    def _on_quiz_answer(
        self, question_index: int, correct: bool, choice: str,
        confidence_level: str = "medium",
    ) -> None:
        self._quiz_confidence[int(question_index)] = str(confidence_level)
        self.quiz_answered.emit(question_index, bool(correct), str(choice))

    def _request_play(self) -> None:
        if self._player is None:
            return
        chapter_index = self._chapter_for_position(self._player.position() / 1000.0)
        if chapter_index is None or self._show_chapter_checks(chapter_index):
            self._player.play()

    def _chapter_for_position(self, seconds: float) -> int | None:
        playable = [
            index for index, is_playable in enumerate(self._chapter_playable)
            if is_playable
        ]
        if not playable:
            return None
        current = playable[0]
        for index in playable:
            if index < len(self._chapter_offsets) and self._chapter_offsets[index] <= seconds:
                current = index
            elif index < len(self._chapter_offsets):
                break
        return current

    def _show_chapter_checks(self, chapter_index: int) -> bool:
        if self._gate_in_progress or self._bundle is None:
            return True
        chapters = self._bundle.plan.chapters
        checks: list[tuple[int, str, dict]] = []
        if chapter_index > 0 and chapter_index - 1 < len(chapters):
            previous = chapters[chapter_index - 1].retrieval
            if isinstance(previous, dict):
                checks.append((chapter_index - 1, "retrieval", previous))
        if 0 <= chapter_index < len(chapters):
            prediction = chapters[chapter_index].prediction
            if isinstance(prediction, dict):
                checks.append((chapter_index, "prediction", prediction))

        pending = [
            (owner, kind, question) for owner, kind, question in checks
            if (owner, kind) not in self._completed_gate_checks
            and str(question.get("q", "")).strip()
        ]
        if not pending:
            return True
        self._gate_in_progress = True
        try:
            for owner, kind, question in pending:
                dialog = _LessonCheckDialog(question, kind, self, self._language)
                if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                    return False
                self._completed_gate_checks.add((owner, kind))
            return True
        finally:
            self._gate_in_progress = False

    def _on_player_position_changed(self, milliseconds: int) -> None:
        if self._player is None or self._bundle is None or self._gate_in_progress:
            return
        try:
            from PyQt6.QtMultimedia import QMediaPlayer

            if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                return
        except Exception:  # noqa: BLE001 - multimedia state is optional
            return
        chapter_index = self._chapter_for_position(milliseconds / 1000.0)
        if chapter_index is None:
            return
        has_pending = any(
            (owner, kind) not in self._completed_gate_checks
            for owner, kind, _question in self._chapter_gate_candidates(chapter_index)
        )
        if has_pending:
            # Stop on the first update at a chapter boundary, then resume only
            # after the student submits each available check.
            self._player.pause()
            if self._show_chapter_checks(chapter_index):
                self._player.play()

    def _chapter_gate_candidates(self, chapter_index: int) -> list[tuple[int, str, dict]]:
        if self._bundle is None:
            return []
        chapters = self._bundle.plan.chapters
        candidates: list[tuple[int, str, dict]] = []
        if chapter_index > 0 and chapter_index - 1 < len(chapters):
            previous = chapters[chapter_index - 1].retrieval
            if isinstance(previous, dict) and str(previous.get("q", "")).strip():
                candidates.append((chapter_index - 1, "retrieval", previous))
        if 0 <= chapter_index < len(chapters):
            prediction = chapters[chapter_index].prediction
            if isinstance(prediction, dict) and str(prediction.get("q", "")).strip():
                candidates.append((chapter_index, "prediction", prediction))
        return candidates

    def _seed_explore(self, plan) -> None:
        """Seed the 'Play with it' canvas from the lesson's domain + the
        interactive chapter's guiding prompt (fail-soft)."""
        try:
            from aetherlab.services.llm import DEFAULT_VARIABLES, extract_keywords
            from aetherlab.services.scene_templates import detect_domain

            domain = detect_domain(extract_keywords(plan.topic) or [plan.topic], {})
            params = {
                "oscillator": {"damping": 0.15, "stiffness": 1.0, "mass": 1.0},
                "pendulum": {"gravity": 9.81, "length": 1.0},
                "orbit": {"eccentricity": 0.5, "semi_major": 1.0},
                "wave": {"frequency": 2.0, "wave_speed": 1.0},
            }.get(domain, dict(DEFAULT_VARIABLES))
            interactive = next((c for c in plan.chapters if c.kind == "interactive"), None)
            hint = (interactive.narration if interactive and interactive.narration
                    else _COPY[self._language]["play_hint"])
            self._explore_hint.setText("▶ " + hint)
            state = build_canvas_state(plan.title[:50], params)
            self._explore_canvas.set_state(state)
        except Exception:  # noqa: BLE001 — exploration is a bonus, never fatal
            self._explore_hint.setText(_COPY[self._language]["explore_unavailable"])

    def _on_outline_click(self, item: QtWidgets.QListWidgetItem) -> None:
        seconds = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if seconds is None:
            return
        seconds = float(seconds)
        index = item.data(QtCore.Qt.ItemDataRole.UserRole + 1)
        if index is None:
            return
        index = int(index)
        if self._player is not None:
            self._player.pause()
        self.chapter_seek_requested.emit(seconds)
        # Seek the inline player to the chapter start and show the Video tab.
        if self._player is not None:
            self._player.setPosition(int(seconds * 1000))
            self._tabs.setCurrentIndex(0)
            target = index
            while target < len(self._chapter_playable) and not self._chapter_playable[target]:
                target += 1
            if target >= len(self._chapter_playable):
                target = index - 1
                while target >= 0 and not self._chapter_playable[target]:
                    target -= 1
            if target < 0 or self._show_chapter_checks(target):
                self._player.play()

def _bundle_chapter_durations(bundle) -> list[float]:
    """Best-effort per-chapter clip durations (seconds) for outline seeking."""
    durations: list[float] = []
    try:
        from aetherlab.services.voiceover import _duration_sync
        for scene in bundle.chapter_scenes:
            vp = getattr(scene, "video_path", "")
            durations.append(_duration_sync(Path(vp)) if vp and Path(vp).exists() else 0.0)
    except Exception:  # noqa: BLE001
        pass
    return durations
