"""Student-facing ENT preparation screens.

These views sit above the existing lesson, practice, library, and history
workflows. They make the student preparation path the default without
removing the physics lab tools.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from aetherlab.core.language import normalize_language
from aetherlab.services.ent_physics_bank import (
    ENT_TOPIC_IDS,
    mock_questions_for_language,
    questions_for_language,
)
from aetherlab.services.ent_practice_progress import (
    aggregate_topic_progress,
    full_mock_history,
    save_companion_choice,
    weekly_question_count,
)
from aetherlab.services.gamification import companion_progress, topic_confidence
from aetherlab.ui.exam_practice import _TOPIC_NAMES
from aetherlab.ui.profile_avatar import ProfileAvatarButton
from aetherlab.ui.progress_notice import ProgressReadNotice
from aetherlab.ui.qt_compat import QtCore, QtWidgets, require_qt
from aetherlab.ui.study_visuals import CompanionArt, GoalRing, OrbitArt

require_qt()


_COPY = {
    "kk": {
        "hello": "Физикадан ҰБТ-ға дайындық",
        "subtitle": "Бүгінгі шағын қадам — емтиханға жақын бір қадам.",
        "start": "Жаттығуды бастау",
        "default_profile": "Оқушы 1",
        "profile_tooltip": "Оқушы профилін көру, өңдеу немесе ауыстыру",
        "leaderboard": "Топ",
        "leaderboard_tooltip": "Мектептегі толық сынақтар рейтингін көру",
        "topics": "Тақырыптарды ашу",
        "practice_title": "ҰБТ жаттығуы",
        "practice_desc": "Тақырып бойынша немесе толық нұсқамен жаттық.",
        "study_title": "Тақырыпты оқу",
        "study_desc": "Қарапайым түсіндіру мен мысалдан баста.",
        "progress_title": "Менің прогресім",
        "progress_desc": "Нәтижең мен қайталау керек тақырыптарды көр.",
        "weekly": "Осы аптада",
        "goal": "Апталық мақсат",
        "no_goal": "Мақсат әлі қойылмаған",
        "target": "Мақсатты балл",
        "not_set": "қойылмаған",
        "exam": "ҰБТ күні",
        "days": "емтиханға дейін күн",
        "no_date": "Емтихан күнін енгіз",
        "next": "Келесі қадам",
        "next_desc": "Алдымен кинематикадан бастап, бірнеше тапсырма шеш.",
        "next_new": "Бұл тақырып әлі басталмаған. Бірнеше тапсырмадан баста.",
        "next_review": "Бұл тақырыптағы дәлдік {accuracy}%. Қателерді қайталап көр.",
        "next_success": "Әзірге {correct}/{total} дұрыс, қате жоқ. Бұл тек орындалған тапсырмалар нәтижесі. Тағы бірнеше тапсырмамен біліміңді тексер.",
        "next_reinforce": "Барлық әрекетте {correct}/{total} дұрыс. Бұл тақырыпта қайталауға белгіленген тапсырма жоқ. Жаңа есептермен біліміңді бекіт.",
        "best": "Үздік сынақ нұсқасы",
        "no_score": "Әлі жоқ",
        "attempts": "Аяқталған жаттығу",
        "mistakes": "Қайталау керек қате",
        "continue": "Тақырыпты жаттықтыру",
        "all_topics": "Физика тақырыптары",
        "catalog_desc": "ҰБТ бағдарламасындағы 25 тақырып. Алдымен түсіндірмені оқы немесе бірден тапсырма шеш.",
        "learn": "Оқу",
        "drill": "Жаттығу",
        "seen": "Бұл тақырып бойынша әзірге жаттығу орындалмады",
        "no_mock_results": "Толық сынақ нәтижесі әзірге жоқ",
        "mastery": "Дәлдік",
        "weak": "Қайталау керек тақырыптар",
        "empty_progress": "Алғашқы жаттығудан кейін нәтижең мен тақырыптар бойынша прогресің осында көрінеді.",
        "completed": "Жаттығулар аяқталды",
        "questions": "Сұрақ",
        "score": "Соңғы толық сынақ",
        "review": "Қателерді қайталау",
        "no_mistakes": "Қайталау керек қате тапсырма жоқ.",
        "study_plan": "Оқу жоспары",
        "set_goal": "Мақсатты баптау",
        "weekly_mock_not_set": "Апталық сынақ күнін жоспар баптауынан таңда.",
        "weekly_mock_today": "Бүгін апталық сынақ күні: {day}.",
        "weekly_mock_tomorrow": "Келесі сынақ ертең: {day}.",
        "weekly_mock_next": "Келесі сынақ: {day} · {days} күннен кейін.",
        "weekly_mock_start": "Бүгінгі сынақты бастау",
        "plan_hint": "Мақсат, ҰБТ күні және апталық сынақ күнін практика баптауынан өзгертуге болады.",
        "mock_history": "Сынақ нұсқаларының нәтижесі",
        "no_mock_history": "Толық сынақ нәтижелері осы жерде көрсетіледі.",
        "recommendations": "Жалғастыруға болатын тақырыптар",
        "mastery_new": "Басталмаған",
        "mastery_learning": "Жаттығуда",
        "mastery_confident": "Сенімді",
        "mastery_summary": "Сенімді меңгерілген тақырыптар: {count}/{total}",
        "mastery_rule": "«Сенімді»: кемінде 5 тапсырма және дәлдік ≥80%.",
        "companion_title": "Физикадағы серігің",
        "companion_level": "Деңгей {level}",
        "companion_progress": "{points} ұпай · өсуге дейін {remaining} ұпай",
        "companion_final": "Соңғы пішіні ашылды · {points} ұпай",
        "companion_points": "{points} ұпай",
        "companion_names": {"quantum": "Квант", "photon": "Фотон", "lab_bot": "Зертхана боты"},
        "companion_choose": "Компаньон таңдау",
        "companion_change": "Компаньонды ауыстыру",
    },
    "ru": {
        "hello": "Подготовка к ЕНТ по физике",
        "subtitle": "Небольшой шаг сегодня — ещё один шаг к экзамену.",
        "start": "Начать тренировку",
        "default_profile": "Ученик 1",
        "profile_tooltip": "Посмотреть, изменить профиль или переключиться на другой",
        "leaderboard": "Рейтинг",
        "leaderboard_tooltip": "Посмотреть школьный рейтинг по полным пробникам",
        "topics": "Открыть темы",
        "practice_title": "Тренировка ЕНТ",
        "practice_desc": "Решай задания по теме или проходи полный пробник.",
        "study_title": "Изучить тему",
        "study_desc": "Начни с простого объяснения и примеров.",
        "progress_title": "Мой прогресс",
        "progress_desc": "Посмотри результаты и темы для повторения.",
        "weekly": "На этой неделе",
        "goal": "Цель на неделю",
        "no_goal": "Цель пока не задана",
        "target": "Целевой балл",
        "not_set": "не задан",
        "exam": "Дата ЕНТ",
        "days": "дней до экзамена",
        "no_date": "Укажи дату ЕНТ",
        "next": "Следующий шаг",
        "next_desc": "Начни с кинематики и реши несколько заданий.",
        "next_new": "Ты ещё не решал задания по этой теме. Начни с небольшой тренировки.",
        "next_review": "Точность по теме — {accuracy}%. Повтори ошибки и попробуй ещё раз.",
        "next_success": "Пока верно {correct}/{total}, ошибок нет. Это результат только решённых заданий. Проверь знания ещё на нескольких задачах.",
        "next_reinforce": "За все попытки верно {correct}/{total}. В этой теме нет заданий, отмеченных для повторения. Закрепи знания на новых задачах.",
        "best": "Лучший пробник",
        "no_score": "Пока нет",
        "attempts": "Завершено тренировок",
        "mistakes": "Ошибок к повторению",
        "continue": "Тренировать тему",
        "all_topics": "Темы физики",
        "catalog_desc": "25 тем программы ЕНТ. Сначала прочитай объяснение или сразу переходи к заданиям.",
        "learn": "Изучить",
        "drill": "Тренировать",
        "seen": "Пока нет попыток по этой теме",
        "no_mock_results": "Пока нет результатов полного пробника",
        "mastery": "Точность",
        "weak": "Темы для повторения",
        "empty_progress": "После первой тренировки здесь появятся твои результаты и прогресс по темам.",
        "completed": "Тренировок завершено",
        "questions": "Заданий",
        "score": "Последний полный пробник",
        "review": "Повторить ошибки",
        "no_mistakes": "Нет заданий, отмеченных для повторения.",
        "study_plan": "План подготовки",
        "set_goal": "Настроить цель",
        "weekly_mock_not_set": "Выбери день пробного ЕНТ в настройках плана.",
        "weekly_mock_today": "Сегодня день недельного пробника: {day}.",
        "weekly_mock_tomorrow": "Следующий пробник завтра: {day}.",
        "weekly_mock_next": "Следующий пробник: {day} · через {days} дн.",
        "weekly_mock_start": "Начать пробник на сегодня",
        "plan_hint": "Цель, дату ЕНТ и день недельного пробника можно изменить в настройках тренировки.",
        "mock_history": "Результаты пробных вариантов",
        "no_mock_history": "Результаты полных пробных вариантов появятся здесь.",
        "recommendations": "Темы для следующего занятия",
        "mastery_new": "Не начата",
        "mastery_learning": "В работе",
        "mastery_confident": "Уверенно",
        "mastery_summary": "Уверенно освоено тем: {count}/{total}",
        "mastery_rule": "«Уверенно»: от 5 заданий и точность не ниже 80%.",
        "companion_title": "Твой компаньон",
        "companion_level": "Уровень {level}",
        "companion_progress": "{points} очков · до роста ещё {remaining}",
        "companion_final": "Последняя форма открыта · {points} очков",
        "companion_points": "{points} очков",
        "companion_names": {"quantum": "Квант", "photon": "Фотон", "lab_bot": "Лаб-бот"},
        "companion_choose": "Выбрать компаньона",
        "companion_change": "Сменить компаньона",
    },
    "en": {
        "hello": "Your physics study space",
        "subtitle": "A small step today brings you closer to exam day.",
        "start": "Start practice",
        "default_profile": "Learner 1",
        "profile_tooltip": "View, edit, or switch the student profile",
        "leaderboard": "Top",
        "leaderboard_tooltip": "View the school ranking for full mock exams",
        "topics": "Browse topics",
        "practice_title": "UNT practice",
        "practice_desc": "Practice by topic or try the full mock set.",
        "study_title": "Study a topic",
        "study_desc": "Start with a plain-language explanation and examples.",
        "progress_title": "My progress",
        "progress_desc": "Review your results and topics to revisit.",
        "weekly": "This week",
        "goal": "Weekly goal",
        "no_goal": "No goal set yet",
        "target": "Target score",
        "not_set": "not set",
        "exam": "UNT date",
        "days": "days until exam",
        "no_date": "Set an exam date",
        "next": "Next step",
        "next_desc": "Start with kinematics and solve a few questions.",
        "next_new": "You have not practiced this topic yet. Start with a short session.",
        "next_review": "Your accuracy here is {accuracy}%. Review mistakes and try again.",
        "next_success": "So far, {correct}/{total} correct with no mistakes. This reflects only the questions answered. Check your understanding with a few more.",
        "next_reinforce": "Across all attempts, {correct}/{total} correct. No questions in this topic are marked for review. Build confidence with new questions.",
        "best": "Best mock score",
        "no_score": "Not yet",
        "attempts": "Practices completed",
        "mistakes": "Mistakes to review",
        "continue": "Practice this topic",
        "all_topics": "Physics topics",
        "catalog_desc": "25 topics from the UNT programme. Read an explanation first or go straight to practice.",
        "learn": "Study",
        "drill": "Practice",
        "seen": "No attempts for this topic yet",
        "no_mock_results": "No full mock result yet",
        "mastery": "Accuracy",
        "weak": "Topics to revisit",
        "empty_progress": "Your results and topic progress will appear here after your first practice.",
        "completed": "Practices completed",
        "questions": "Questions",
        "score": "Latest full mock",
        "review": "Review mistakes",
        "no_mistakes": "There are no questions marked for review.",
        "study_plan": "Study plan",
        "set_goal": "Set a goal",
        "weekly_mock_not_set": "Choose a weekly mock day in study plan settings.",
        "weekly_mock_today": "Today is your weekly mock day: {day}.",
        "weekly_mock_tomorrow": "Your next mock is tomorrow: {day}.",
        "weekly_mock_next": "Next mock: {day} · in {days} days.",
        "weekly_mock_start": "Start this week's mock",
        "plan_hint": "Change your target score, UNT date, and weekly mock day in practice setup.",
        "mock_history": "Mock exam history",
        "no_mock_history": "Completed full mock results will appear here.",
        "recommendations": "Topics to continue with",
        "mastery_new": "Not started",
        "mastery_learning": "In progress",
        "mastery_confident": "Confident",
        "mastery_summary": "Confident topics: {count}/{total}",
        "mastery_rule": "“Confident” means 5+ questions answered at 80% accuracy or higher.",
        "companion_title": "Your companion",
        "companion_level": "Level {level}",
        "companion_progress": "{points} points · {remaining} to next form",
        "companion_final": "Final form unlocked · {points} points",
        "companion_points": "{points} points",
        "companion_names": {"quantum": "Quantum", "photon": "Photon", "lab_bot": "Lab bot"},
        "companion_choose": "Choose companion",
        "companion_change": "Change companion",
    },
}

_WEEKDAY_NAMES = {
    "kk": ("Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"),
    "ru": ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
}


def _card(parent=None) -> QtWidgets.QFrame:
    frame = QtWidgets.QFrame(parent)
    frame.setObjectName("StudentCard")
    frame.setStyleSheet(
        "QFrame#StudentCard { background:#FFFFFF; border:1px solid #D8E1EC; border-radius:16px; }"
    )
    return frame


def _heading(text: str, size: int = 20) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setStyleSheet(f"color:#18283D; font-size:{size}px; font-weight:700;")
    label.setWordWrap(True)
    return label


def _button(text: str, primary: bool = False) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(42)
    if primary:
        button.setStyleSheet(
            "QPushButton { background:#486A91; color:#FFFFFF; border:1px solid #486A91; "
            "border-radius:8px; padding:8px 14px; font-weight:700; }"
            "QPushButton:hover { background:#3B587A; }"
            "QPushButton:pressed { background:#3B587A; }"
            "QPushButton:focus { border:2px solid #335F92; }"
        )
    else:
        button.setObjectName("SecondaryButton")
    return button


class StudentDashboard(QtWidgets.QWidget):
    profile_requested = QtCore.pyqtSignal()
    leaderboard_requested = QtCore.pyqtSignal()
    topics_requested = QtCore.pyqtSignal()
    progress_requested = QtCore.pyqtSignal()
    mistakes_requested = QtCore.pyqtSignal()
    practice_topic_requested = QtCore.pyqtSignal(str)
    learn_topic_requested = QtCore.pyqtSignal(str)
    plan_settings_requested = QtCore.pyqtSignal()
    weekly_mock_requested = QtCore.pyqtSignal()

    def __init__(
        self,
        progress_path: Path,
        language: str = "ru",
        parent=None,
        profile_name: str = "",
    ) -> None:
        super().__init__(parent)
        self.progress_path = Path(progress_path)
        self.language = normalize_language(language, "ru")
        self.profile_name = profile_name or _COPY[self.language]["default_profile"]
        self.profile_avatar_path = ""
        self._build()

    def _build(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 22)
        outer.setSpacing(16)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        scroll.viewport().setObjectName("StudentViewport")
        scroll.viewport().setStyleSheet("QWidget#StudentViewport { background:transparent; }")
        content = QtWidgets.QWidget()
        content.setObjectName("StudentContent")
        content.setStyleSheet("QWidget#StudentContent { background:transparent; }")
        self.content_layout = QtWidgets.QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)

        header = QtWidgets.QHBoxLayout()
        title_block = QtWidgets.QVBoxLayout()
        self.title = _heading("", 28)
        self.subtitle = QtWidgets.QLabel("")
        self.subtitle.setStyleSheet("color:#65758A; font-size:13px;")
        self.subtitle.setWordWrap(True)
        title_block.addWidget(self.title)
        title_block.addWidget(self.subtitle)
        header.addLayout(title_block, 1)
        self.leaderboard_button = QtWidgets.QPushButton()
        self.leaderboard_button.setObjectName("SecondaryButton")
        self.leaderboard_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.leaderboard_button.setMinimumHeight(40)
        self.leaderboard_button.clicked.connect(self.leaderboard_requested.emit)
        header.addWidget(self.leaderboard_button)
        self.profile_button = ProfileAvatarButton(self.profile_name)
        self.profile_button.clicked.connect(self.profile_requested.emit)
        header.addWidget(self.profile_button)
        self.profile_button.hide()  # The persistent title bar owns the visible profile entry.
        self.content_layout.addLayout(header)
        self.progress_notice = ProgressReadNotice(self.refresh, self)
        self.content_layout.addWidget(self.progress_notice)

        self.feature_grid = QtWidgets.QGridLayout()
        self.feature_grid.setSpacing(16)
        self._feature_columns = 0
        self.hero = _card()
        self.hero.setObjectName("StudyHero")
        self.hero.setStyleSheet("QFrame#StudyHero { background:#E9EFF7; border:1px solid #D8E1EC; border-radius:20px; }")
        self.hero.setMinimumHeight(232)
        hero_layout = QtWidgets.QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(26, 24, 20, 24)
        hero_copy = QtWidgets.QVBoxLayout()
        hero_copy.setSpacing(12)
        self.next_title = _heading("", 12)
        self.next_title.setStyleSheet("color:#486A91; font-size:12px; font-weight:700; letter-spacing:1px;")
        hero_copy.addWidget(self.next_title)
        self.hero_topic = _heading("", 30)
        self.hero_topic.setStyleSheet("color:#18283D; font-size:30px; font-weight:700;")
        hero_copy.addWidget(self.hero_topic)
        self.next_description = QtWidgets.QLabel("")
        self.next_description.setStyleSheet("color:#53647A; font-size:14px;")
        self.next_description.setWordWrap(True)
        hero_copy.addWidget(self.next_description)
        hero_copy.addStretch(1)
        self.topic_button = _button("", True)
        self.topic_button.clicked.connect(lambda: self.practice_topic_requested.emit(self._hero_topic_id))
        self.hero_learn_button = _button("")
        self.hero_learn_button.clicked.connect(
            lambda: self.learn_topic_requested.emit(
                "constant_acceleration"
                if self._hero_topic_id == "kinematics"
                else self.hero_topic.text()
            )
        )
        hero_actions = QtWidgets.QHBoxLayout()
        hero_actions.setSpacing(10)
        hero_actions.addWidget(self.topic_button)
        hero_actions.addWidget(self.hero_learn_button)
        hero_actions.addStretch(1)
        hero_copy.addLayout(hero_actions)
        hero_layout.addLayout(hero_copy, 1)
        self.companion_panel = QtWidgets.QFrame()
        self.companion_panel.setObjectName("CompanionPanel")
        self.companion_panel.setStyleSheet(
            "QFrame#CompanionPanel { background:#FBF6ED; "
            "border:1px solid #D8E1EC; border-radius:20px; }"
        )
        self.companion_panel.setMinimumHeight(232)
        companion_layout = QtWidgets.QVBoxLayout(self.companion_panel)
        companion_layout.setContentsMargins(18, 13, 18, 14)
        companion_layout.setSpacing(5)
        self.companion_title = QtWidgets.QLabel()
        self.companion_title.setStyleSheet("color:#53647A; font-size:12px; font-weight:700;")
        companion_layout.addWidget(self.companion_title)
        companion_content = QtWidgets.QHBoxLayout()
        companion_content.setSpacing(10)
        self.companion_art = CompanionArt()
        self.companion_art.setFixedSize(140, 122)
        companion_content.addWidget(self.companion_art, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        companion_identity = QtWidgets.QVBoxLayout()
        companion_identity.setSpacing(3)
        companion_identity.addStretch(1)
        self.companion_stage_label = QtWidgets.QLabel()
        self.companion_stage_label.setStyleSheet("color:#18283D; font-size:17px; font-weight:700;")
        companion_identity.addWidget(self.companion_stage_label)
        self.companion_level_label = QtWidgets.QLabel()
        self.companion_level_label.setStyleSheet("color:#53647A; font-size:12px;")
        companion_identity.addWidget(self.companion_level_label)
        self.companion_progress_label = QtWidgets.QLabel()
        self.companion_progress_label.setWordWrap(True)
        self.companion_progress_label.setStyleSheet("color:#53647A; font-size:11px;")
        companion_identity.addWidget(self.companion_progress_label)
        companion_identity.addStretch(1)
        companion_content.addLayout(companion_identity, 1)
        companion_layout.addLayout(companion_content, 1)
        self.companion_progress_bar = QtWidgets.QProgressBar()
        self.companion_progress_bar.setRange(0, 100)
        self.companion_progress_bar.setTextVisible(False)
        self.companion_progress_bar.setFixedHeight(6)
        self.companion_progress_bar.setStyleSheet(
            "QProgressBar { background:#D8E1EC; border:0; border-radius:3px; }"
            "QProgressBar::chunk { background:#26725C; border-radius:3px; }"
        )
        companion_layout.addWidget(self.companion_progress_bar)
        self.companion_select_button = QtWidgets.QPushButton()
        self.companion_select_button.setObjectName("CompanionSelectButton")
        self.companion_select_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.companion_select_button.setMinimumHeight(40)
        self.companion_select_button.setStyleSheet(
            "QPushButton#CompanionSelectButton { background:#486A91; color:#FFFFFF; "
            "border:1px solid #486A91; border-radius:10px; padding:7px 11px; font-weight:700; font-size:12px; }"
            "QPushButton#CompanionSelectButton:hover { background:#3B587A; }"
            "QPushButton#CompanionSelectButton:focus { border:2px solid #335F92; }"
        )
        self.companion_select_button.clicked.connect(self._choose_companion)
        companion_layout.addWidget(self.companion_select_button)
        self.plan_card = _card()
        plan_layout = QtWidgets.QVBoxLayout(self.plan_card)
        plan_layout.setContentsMargins(22, 20, 22, 20)
        plan_layout.setSpacing(10)
        self.plan_title = _heading("", 16)
        plan_layout.addWidget(self.plan_title)
        goal_row = QtWidgets.QHBoxLayout()
        self.goal_ring = GoalRing()
        goal_row.addWidget(self.goal_ring)
        self.goal_caption = QtWidgets.QLabel()
        self.goal_caption.setWordWrap(True)
        self.goal_caption.setStyleSheet("color:#53647A; font-size:12px;")
        goal_row.addWidget(self.goal_caption, 1)
        plan_layout.addLayout(goal_row)
        self.plan_summary = QtWidgets.QLabel()
        self.plan_summary.setStyleSheet("color:#486A91; font-size:12px; font-weight:600;")
        self.plan_summary.setWordWrap(True)
        plan_layout.addWidget(self.plan_summary)
        self.weekly_mock_label = QtWidgets.QLabel()
        self.weekly_mock_label.setWordWrap(True)
        self.weekly_mock_label.setStyleSheet(
            "color:#486A91; font-size:12px; font-weight:600;"
        )
        plan_layout.addWidget(self.weekly_mock_label)
        self.weekly_mock_button = _button("")
        self.weekly_mock_button.clicked.connect(self.weekly_mock_requested.emit)
        self.weekly_mock_button.hide()
        plan_layout.addWidget(self.weekly_mock_button, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.plan_hint = QtWidgets.QLabel()
        self.plan_hint.setWordWrap(True)
        self.plan_hint.setStyleSheet("color:#65758A; font-size:11px;")
        plan_layout.addWidget(self.plan_hint)
        self.plan_settings_button = _button("")
        self.plan_settings_button.clicked.connect(self.plan_settings_requested.emit)
        plan_layout.addWidget(self.plan_settings_button, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.weekly_progress = QtWidgets.QProgressBar()
        self.weekly_progress.setTextVisible(False)
        self.weekly_progress.setFixedHeight(6)
        self.weekly_progress.hide()
        plan_layout.addWidget(self.weekly_progress)
        plan_layout.addStretch(1)
        self.content_layout.addLayout(self.feature_grid)

        self.stats_row = QtWidgets.QGridLayout()
        self.stats_row.setHorizontalSpacing(12)
        self.stats_row.setVerticalSpacing(12)
        self.metric_labels: dict[str, tuple[QtWidgets.QLabel, QtWidgets.QLabel]] = {}
        self.metric_cards: list[QtWidgets.QFrame] = []
        self._metric_columns = 0
        for key in ("weekly", "best", "mistakes", "attempts"):
            card = _card()
            card.setStyleSheet("QFrame#StudentCard { background:#FFFFFF; border:1px solid #D8E1EC; border-radius:16px; }")
            box = QtWidgets.QVBoxLayout(card)
            box.setContentsMargins(15, 13, 15, 13)
            value = _heading("—", 22)
            caption = QtWidgets.QLabel("")
            caption.setStyleSheet("color:#65758A; font-size:11px;")
            caption.setWordWrap(True)
            box.addWidget(value)
            box.addWidget(caption)
            self.metric_labels[key] = (value, caption)
            self.metric_cards.append(card)
        self.content_layout.addLayout(self.stats_row)

        recommendations = _card()
        self.recommendations_panel = recommendations
        recommendations_layout = QtWidgets.QVBoxLayout(recommendations)
        recommendations_layout.setContentsMargins(18, 17, 18, 18)
        recommendations_layout.setSpacing(12)
        recommendation_heading_row = QtWidgets.QHBoxLayout()
        self.recommendation_title = _heading("", 15)
        recommendation_heading_row.addWidget(self.recommendation_title, 1)
        self.all_topics_button = QtWidgets.QPushButton("")
        self.all_topics_button.setObjectName("LinkButton")
        self.all_topics_button.clicked.connect(self.topics_requested.emit)
        recommendation_heading_row.addWidget(self.all_topics_button)
        recommendations_layout.addLayout(recommendation_heading_row)
        self.recommendation_cards = QtWidgets.QGridLayout()
        self.recommendation_cards.setHorizontalSpacing(12)
        self.recommendation_cards.setVerticalSpacing(12)
        self._recommendation_card_widgets: list[QtWidgets.QFrame] = []
        self._recommendation_columns = 0
        recommendations_layout.addLayout(self.recommendation_cards)
        self.study_grid = QtWidgets.QGridLayout()
        self.study_grid.setSpacing(16)
        self._study_columns = 0
        self.content_layout.addLayout(self.study_grid)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.refresh()
        self._apply_responsive_layout()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        """Reflow metric and recommendation cards before their content clips."""
        if not hasattr(self, "stats_row") or not hasattr(self, "recommendation_cards"):
            return
        available = max(0, self.width() - 56)
        columns = 2 if available >= 890 else 1
        if columns != self._feature_columns:
            while self.feature_grid.count():
                self.feature_grid.takeAt(0)
            self.feature_grid.addWidget(self.hero, 0, 0)
            self.feature_grid.addWidget(self.companion_panel, 0 if columns == 2 else 1, 1 if columns == 2 else 0)
            self.feature_grid.setColumnStretch(0, 7 if columns == 2 else 1)
            self.feature_grid.setColumnStretch(1, 3 if columns == 2 else 0)
            self._feature_columns = columns
        study_columns = 2 if available >= 890 else 1
        if study_columns != self._study_columns:
            while self.study_grid.count():
                self.study_grid.takeAt(0)
            self.study_grid.addWidget(self.recommendations_panel, 0, 0)
            self.study_grid.addWidget(self.plan_card, 0 if study_columns == 2 else 1, 1 if study_columns == 2 else 0)
            self.study_grid.setColumnStretch(0, 7 if study_columns == 2 else 1)
            self.study_grid.setColumnStretch(1, 3 if study_columns == 2 else 0)
            self._study_columns = study_columns
        metric_columns = 4 if available >= 900 else 2 if available >= 520 else 1
        recommendation_columns = 3 if available >= 1120 else 2 if available >= 890 else 1

        def place(layout, widgets, columns, previous_columns):
            if columns == previous_columns:
                return
            for column in range(max(columns, previous_columns)):
                layout.setColumnStretch(column, 0)
            while layout.count():
                layout.takeAt(0)
            for index, widget in enumerate(widgets):
                layout.addWidget(widget, index // columns, index % columns)
            for column in range(columns):
                layout.setColumnStretch(column, 1)

        place(self.stats_row, self.metric_cards, metric_columns, self._metric_columns)
        self._metric_columns = metric_columns
        place(
            self.recommendation_cards,
            self._recommendation_card_widgets,
            recommendation_columns,
            self._recommendation_columns,
        )
        self._recommendation_columns = recommendation_columns

    def set_language(self, language: str) -> None:
        safe = normalize_language(language, self.language)
        if safe != self.language:
            self.language = safe
            self._retranslate()
        self.refresh()

    def _retranslate(self) -> None:
        text = _COPY[self.language]
        self.title.setText(text["hello"])
        self.subtitle.setText(text["subtitle"])
        self.profile_button.set_profile(
            self.profile_name, self.profile_avatar_path, text["profile_tooltip"]
        )
        self.leaderboard_button.setText(text["leaderboard"])
        self.leaderboard_button.setToolTip(text["leaderboard_tooltip"])
        self.next_title.setText(text["next"])
        self.next_description.setText(text["next_desc"])
        self.topic_button.setText(text["continue"] + "  →")
        self.hero_learn_button.setText(text["learn"])
        self.plan_title.setText(text["study_plan"])
        self.recommendation_title.setText(text["recommendations"])
        self.all_topics_button.setText(text["all_topics"])
        self.plan_hint.setText(text["plan_hint"])
        self.plan_settings_button.setText(text["set_goal"])
        self.weekly_mock_button.setText(text["weekly_mock_start"])
        self.companion_title.setText(text["companion_title"])
        self.companion_select_button.setText(
            text["companion_change"]
            if getattr(self, "companion_id", None)
            else text["companion_choose"]
        )
        labels = {key: text[key] for key in self.metric_labels}
        for key, (value, caption) in self.metric_labels.items():
            caption.setText(labels[key])

    def set_profile_name(self, name: str) -> None:
        self.profile_name = str(name or _COPY[self.language]["default_profile"])
        self.set_profile(self.profile_name, self.profile_avatar_path)

    def set_profile(self, name: str, avatar_path: str = "") -> None:
        self.profile_name = str(name or _COPY[self.language]["default_profile"])
        self.profile_avatar_path = str(avatar_path or "")
        self.profile_button.set_profile(
            self.profile_name,
            self.profile_avatar_path,
            _COPY[self.language]["profile_tooltip"],
        )

    def refresh(self) -> None:
        text = _COPY[self.language]
        if not hasattr(self, "title"):
            return
        self._retranslate() if self.title.text() != text["hello"] else None
        snapshot = self.progress_notice.read(self.progress_path, self.language)
        for panel in (self.hero, self.companion_panel, self.plan_card, self.recommendations_panel):
            panel.setVisible(snapshot is not None)
        if snapshot is None:
            self.companion_id = None
            for value, _ in self.metric_labels.values():
                value.setText("—")
            return
        attempts = snapshot.attempts
        goals = snapshot.goals
        mocks = full_mock_history(attempts)
        weekly = weekly_question_count(attempts)
        mistakes = len(snapshot.mistake_ids)
        best = max((int(item.get("score", 0) or 0) for item in mocks), default=None)
        exam_day = None
        try:
            exam_day = date.fromisoformat(str(goals.get("exam_date", "")))
        except ValueError:
            pass
        target_score = goals.get("target_score")
        target_label = f"{target_score}/50" if target_score else text["not_set"]
        if exam_day:
            days = max(0, (exam_day - date.today()).days)
            self.plan_summary.setText(
                f"{days} {text['days']} · {text['target']}: {target_label}"
            )
        else:
            self.plan_summary.setText(f"{text['no_date']} · {target_label}")
        weekly_goal = goals.get("weekly_question_goal")
        mock_day = goals.get("weekly_mock_day")
        if isinstance(mock_day, int) and 0 <= mock_day <= 6:
            day_name = _WEEKDAY_NAMES[self.language][mock_day]
            days_until = (mock_day - date.today().weekday()) % 7
            if days_until == 0:
                self.weekly_mock_label.setText(
                    text["weekly_mock_today"].format(day=day_name)
                )
                self.weekly_mock_button.show()
            elif days_until == 1:
                self.weekly_mock_label.setText(
                    text["weekly_mock_tomorrow"].format(day=day_name)
                )
                self.weekly_mock_button.hide()
            else:
                self.weekly_mock_label.setText(
                    text["weekly_mock_next"].format(day=day_name, days=days_until)
                )
                self.weekly_mock_button.hide()
        else:
            self.weekly_mock_label.setText(text["weekly_mock_not_set"])
            self.weekly_mock_button.hide()
        self.goal_ring.set_progress(weekly, int(weekly_goal or 0))
        self.goal_ring.setVisible(bool(weekly_goal))
        self.goal_caption.setText(
            f"{weekly} / {weekly_goal}\n{text['questions']}"
            if weekly_goal
            else text["no_goal"]
        )
        self.metric_labels["weekly"][0].setText(str(weekly))
        self.metric_labels["weekly"][1].setText(
            f"{text['weekly']} · {weekly_goal} {text['goal'].lower()}" if weekly_goal else text["weekly"]
        )
        if weekly_goal:
            goal = max(1, int(weekly_goal))
            self.weekly_progress.setValue(min(100, round(weekly * 100 / goal)))
            self.weekly_progress.show()
        else:
            self.weekly_progress.hide()
        self.metric_labels["best"][0].setText(
            f"{best}/50" if best is not None else text["no_score"]
        )
        self.metric_labels["best"][1].setText(text["best"])
        self.metric_labels["mistakes"][0].setText(str(mistakes))
        self.metric_labels["mistakes"][1].setText(text["mistakes"])
        self.metric_labels["attempts"][0].setText(str(len(attempts)))
        self.metric_labels["attempts"][1].setText(text["attempts"])
        self._refresh_companion(snapshot)
        self._refresh_recommendations(attempts, set(snapshot.mistake_ids))

    def _refresh_companion(self, snapshot) -> None:
        text = _COPY[self.language]
        self.companion_id = snapshot.companion_choice
        companion_id = self.companion_id or "quantum"
        points = snapshot.companion_points
        progress = companion_progress(points)
        self.companion_art.set_companion(companion_id, progress.stage)
        self.companion_panel.setStyleSheet(
            "QFrame#CompanionPanel { background:"
            f"{self.companion_art.background_color()}; "
            "border:1px solid #D8E1EC; border-radius:20px; }"
        )
        self.companion_stage_label.setText(text["companion_names"][companion_id])
        self.companion_level_label.setText(text["companion_level"].format(level=progress.level))
        if progress.next_milestone is None:
            self.companion_progress_label.setText(
                text["companion_final"].format(points=progress.points)
            )
        else:
            self.companion_progress_label.setText(
                text["companion_progress"].format(
                    points=progress.points,
                    remaining=max(0, progress.next_milestone - progress.points),
                )
            )
        self.companion_progress_bar.setValue(round(progress.progress_to_milestone * 100))
        self.companion_select_button.setText(
            text["companion_change"] if self.companion_id else text["companion_choose"]
        )
        rule = {"kk": "Ұпай әр аяқталған жаттығудағы нәтижеден жиналады.",
                "ru": "Очки суммируют баллы за завершённые тренировки и пробники.",
                "en": "Points add up from completed practice and mock scores."}[self.language]
        for widget in (
            self.companion_panel,
            self.companion_title,
            self.companion_stage_label,
            self.companion_progress_label,
            self.companion_progress_bar,
        ):
            widget.setToolTip(rule)

    def _choose_companion(self) -> None:
        from aetherlab.ui.companion_dialog import CompanionPickerDialog

        snapshot = self.progress_notice.read(self.progress_path, self.language)
        if not self.progress_notice.last_read_ok:
            QtWidgets.QMessageBox.warning(self, self.companion_title.text(), self.progress_notice.status.text())
            return
        dialog = CompanionPickerDialog(
            selected_companion=self.companion_id,
            points=snapshot.companion_points,
            language=self.language,
            parent=self,
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            try:
                saved_choice = save_companion_choice(
                    self.progress_path, dialog.selected_companion
                )
            except (OSError, UnicodeError):
                message = {
                    "kk": "Серіктес сақталмады. Алдыңғы таңдау өзгермеді. Файлға қолжетімділікті қалпына келтіріп, қайта таңдаңыз.",
                    "ru": "Спутник не сохранён. Прежний выбор не изменён. Восстановите доступ к файлу и выберите ещё раз.",
                    "en": "The companion was not saved. Your previous choice is unchanged. Restore file access and select again.",
                }[self.language]
                QtWidgets.QMessageBox.warning(self, self.companion_title.text(), message)
                return
            self.companion_id = saved_choice
            self.refresh()

    def _refresh_recommendations(self, attempts: list[dict], mistake_ids: set[str]) -> None:
        self._recommendation_card_widgets.clear()
        while self.recommendation_cards.count():
            item = self.recommendation_cards.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()

        topic_progress = aggregate_topic_progress(attempts)
        names = _TOPIC_NAMES[self.language]
        practiced = [
            (values["correct"] / max(1, values["total"]), topic_id, values)
            for topic_id, values in topic_progress.items()
            if int(values.get("total", 0)) > 0
        ]
        practiced.sort(key=lambda entry: (entry[0], entry[1]))
        ordered_ids = [entry[1] for entry in practiced]
        ordered_ids.extend(topic_id for topic_id in ENT_TOPIC_IDS if topic_id not in topic_progress)
        ordered_ids.extend(topic_id for topic_id in ENT_TOPIC_IDS if topic_id not in ordered_ids)

        self._hero_topic_id = ordered_ids[0]
        self.hero_topic.setText(names.get(self._hero_topic_id, self._hero_topic_id))
        hero_values = topic_progress.get(self._hero_topic_id, {})
        hero_total = int(hero_values.get("total", 0))
        hero_correct = int(hero_values.get("correct", 0))
        hero_has_mistakes = bool(mistake_ids) and any(
            question["id"] in mistake_ids
            for question in (
                *questions_for_language(self.language, self._hero_topic_id),
                *mock_questions_for_language(self.language, self._hero_topic_id),
            )
        )
        if hero_total and hero_correct == hero_total:
            description = _COPY[self.language]["next_success"].format(correct=hero_correct, total=hero_total)
        elif hero_total and hero_has_mistakes:
            description = _COPY[self.language]["next_review"].format(accuracy=round(100 * hero_correct / hero_total))
        elif hero_total:
            description = _COPY[self.language]["next_reinforce"].format(correct=hero_correct, total=hero_total)
        else:
            description = _COPY[self.language]["next_new"]
        self.next_description.setText(description)
        for number, topic_id in enumerate(ordered_ids[:3]):
            values = topic_progress.get(topic_id, {})
            total = int(values.get("total", 0))
            correct = int(values.get("correct", 0))
            accuracy = round(correct * 100 / total) if total else 0
            card = _card()
            color = ("#E9EFF7", "#E8F3ED", "#FBF1E4")[number % 3]
            card.setStyleSheet(f"QFrame#StudentCard {{ background:{color}; border:none; border-radius:18px; }}")
            column = QtWidgets.QVBoxLayout(card)
            number_label = QtWidgets.QLabel(f"0{number + 1}   ↗")
            number_label.setStyleSheet("color:#486A91; font-size:20px; font-weight:700;")
            column.addWidget(number_label)
            column.setContentsMargins(14, 12, 14, 12)
            column.setSpacing(7)
            name = _heading(names.get(topic_id, topic_id), 13)
            name.setMinimumHeight(36)
            column.addWidget(name)
            detail = QtWidgets.QLabel(
                f"{_COPY[self.language]['mastery']}: {accuracy}% · {correct}/{total}"
                if total else _COPY[self.language]["seen"]
            )
            detail.setWordWrap(True)
            detail.setStyleSheet("color:#65758A; font-size:11px;")
            column.addWidget(detail)
            progress = QtWidgets.QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(accuracy)
            progress.setTextVisible(False)
            progress.setFixedHeight(6)
            progress.setStyleSheet(
                "QProgressBar { background:#D8E1EC; border:0; border-radius:3px; }"
                "QProgressBar::chunk { background:#26725C; border-radius:3px; }"
            )
            column.addWidget(progress)
            practice = _button(_COPY[self.language]["drill"] + "  →")
            practice.clicked.connect(
                lambda _checked=False, value=topic_id: self.practice_topic_requested.emit(value)
            )
            column.addWidget(practice)
            self._recommendation_card_widgets.append(card)
        self._recommendation_columns = 0
        self._apply_responsive_layout()


class TopicCatalogView(QtWidgets.QWidget):
    learn_topic_requested = QtCore.pyqtSignal(str)
    practice_topic_requested = QtCore.pyqtSignal(str)

    def __init__(self, progress_path: Path, language: str = "ru", parent=None) -> None:
        super().__init__(parent)
        self.progress_path = Path(progress_path)
        self.language = normalize_language(language, "ru")
        self._build()

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 20)
        layout.setSpacing(14)
        self.title = _heading("", 28)
        self.description = QtWidgets.QLabel()
        self.description.setWordWrap(True)
        self.description.setStyleSheet("color:#65758A; font-size:13px;")
        layout.addWidget(self.title)
        layout.addWidget(self.description)
        self.progress_notice = ProgressReadNotice(self.refresh, self)
        layout.addWidget(self.progress_notice)
        tools = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("TopicSearch")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._reflow)
        self.search.textChanged.connect(lambda _text: self.scroll.verticalScrollBar().setValue(0))
        tools.addWidget(self.search, 1)
        self.filter = QtWidgets.QComboBox()
        self.filter.setMinimumWidth(175)
        self.filter.currentIndexChanged.connect(self._reflow)
        self.filter.currentIndexChanged.connect(lambda _index: self.scroll.verticalScrollBar().setValue(0))
        tools.addWidget(self.filter)
        layout.addLayout(tools)
        self.result_count = QtWidgets.QLabel()
        self.result_count.setStyleSheet("color:#65758A; font-size:11px;")
        layout.addWidget(self.result_count)
        self.mastery_summary = QtWidgets.QLabel()
        self.mastery_summary.setWordWrap(True)
        self.mastery_summary.setStyleSheet("color:#486A91; font-size:11px; font-weight:600;")
        layout.addWidget(self.mastery_summary)
        self.mastery_rule_label = QtWidgets.QLabel()
        self.mastery_rule_label.setWordWrap(True)
        self.mastery_rule_label.setStyleSheet("color:#65758A; font-size:10px;")
        layout.addWidget(self.mastery_rule_label)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        content = QtWidgets.QWidget()
        content.setObjectName("StudentContent")
        content.setStyleSheet("QWidget#StudentContent { background:transparent; }")
        self.rows = QtWidgets.QGridLayout(content)
        self._cards_host = content
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(14)
        self.rows.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)
        self.cards = []
        self.refresh()

    def set_language(self, language: str) -> None:
        self.language = normalize_language(language, self.language)
        self.refresh()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "cards"):
            self._reflow()

    def _reflow(self, *_):
        if not hasattr(self, "cards"):
            return
        while self.rows.count():
            self.rows.takeAt(0)
        query = self.search.text().strip().casefold()
        mode = self.filter.currentData() or "all"
        columns = 3 if self.width() >= 1080 else 2 if self.width() >= 650 else 1
        count = 0
        for card, name, practiced in self.cards:
            visible = query in name.casefold() and (mode == "all" or (mode == "new" and not practiced) or (mode == "practiced" and practiced))
            if visible:
                self.rows.addWidget(card, count // columns, count % columns)
                count += 1
            card.setVisible(visible)
        for column in range(3):
            self.rows.setColumnStretch(column, 1 if column < columns else 0)
        noun = {"kk":"тақырып", "ru":"тем", "en":"topics"}[self.language]
        self.result_count.setText(f"{count} / {len(ENT_TOPIC_IDS)} {noun}")

    def refresh(self) -> None:
        text = _COPY[self.language]
        self.title.setText(text["all_topics"])
        self.description.setText(text["catalog_desc"])
        snapshot = self.progress_notice.read(self.progress_path, self.language)
        self.filter.setEnabled(snapshot is not None)
        self.mastery_rule_label.setText(text["mastery_rule"])
        self.search.setPlaceholderText({"kk":"Тақырыпты іздеу…", "ru":"Найти тему…", "en":"Search physics topics…"}[self.language])
        mode = (self.filter.currentData() or "all") if snapshot is not None else "all"
        self.filter.blockSignals(True)
        self.filter.clear()
        labels = {"kk":["Барлық тақырып", "Жаңа тақырып", "Жаттығылған"], "ru":["Все темы", "Без попыток", "Уже изученные"], "en":["All topics", "Not started", "Practiced"]}[self.language]
        for label, value in zip(labels, ("all", "new", "practiced")):
            self.filter.addItem(label, value)
        self.filter.setCurrentIndex(max(0, self.filter.findData(mode)))
        self.filter.blockSignals(False)
        while self.rows.count():
            self.rows.takeAt(0)
        for card, _, _ in self.cards:
            card.hide()
            card.deleteLater()
        self.cards = []
        progress = aggregate_topic_progress(snapshot.attempts) if snapshot is not None else {}
        names = _TOPIC_NAMES[self.language]
        confident_count = sum(
            topic_confidence(values.get("correct", 0), values.get("total", 0)) == "confident"
            for values in progress.values()
        )
        self.mastery_summary.setText(
            text["mastery_summary"].format(count=confident_count, total=len(ENT_TOPIC_IDS)) if snapshot is not None else "— / " + str(len(ENT_TOPIC_IDS))
        )
        for number, topic_id in enumerate(ENT_TOPIC_IDS):
            stat = progress.get(topic_id, {})
            total = int(stat.get("total", 0))
            correct = int(stat.get("correct", 0))
            accuracy = round(correct * 100 / total) if total else 0
            card = _card(self._cards_host)
            box = QtWidgets.QVBoxLayout(card)
            box.setContentsMargins(18, 18, 18, 16)
            box.setSpacing(12)
            subject = {"kk":"ФИЗИКА", "ru":"ФИЗИКА", "en":"PHYSICS"}[self.language]
            tint = ("#E9EFF7", "#E8F3ED", "#FBF1E4")[number % 3]
            number_label = QtWidgets.QLabel(f"{number + 1:02d}   /   {subject}")
            number_label.setStyleSheet(f"background:{tint}; color:#53647A; border-radius:8px; padding:8px; font-size:10px; font-weight:700;")
            status = topic_confidence(correct, total)
            status_text = {
                "not_started": text["mastery_new"],
                "practicing": text["mastery_learning"],
                "confident": text["mastery_confident"],
            }[status]
            if snapshot is None:
                status_text = self.progress_notice.copy["unknown"]
            status_colors = {
                "not_started": ("#EEF1F5", "#596579"),
                "practicing": ("#E7EEF6", "#486A91"),
                "confident": ("#E8F3ED", "#2F725E"),
            }
            status_bg, status_fg = status_colors[status]
            status_label = QtWidgets.QLabel(status_text)
            status_label.setObjectName("TopicMasteryStatus")
            status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            status_label.setStyleSheet(
                f"background:{status_bg}; color:{status_fg}; border-radius:8px; "
                "padding:7px 9px; font-size:10px; font-weight:700;"
            )
            status_label.setToolTip(text["mastery_rule"])
            number_row = QtWidgets.QHBoxLayout()
            number_row.addWidget(number_label, 1)
            number_row.addWidget(status_label)
            box.addLayout(number_row)
            name = names.get(topic_id, topic_id)
            heading = _heading(name, 17)
            heading.setMinimumHeight(46)
            box.addWidget(heading)
            detail = QtWidgets.QLabel(f"{text['mastery']}: {accuracy}% · {correct}/{total}" if total else text["seen"])
            if snapshot is None:
                detail.setText(self.progress_notice.copy["unknown"])
            detail.setWordWrap(True)
            detail.setStyleSheet("color:#65758A; font-size:11px;")
            box.addWidget(detail)
            bar = QtWidgets.QProgressBar()
            bar.setValue(accuracy)
            bar.setVisible(snapshot is not None)
            bar.setTextVisible(False)
            bar.setFixedHeight(5)
            box.addWidget(bar)
            actions = QtWidgets.QHBoxLayout()
            learn = _button(text["learn"])
            target = "constant_acceleration" if topic_id == "kinematics" else name
            learn.clicked.connect(lambda _checked=False, value=target: self.learn_topic_requested.emit(value))
            drill = _button(text["drill"], True)
            drill.clicked.connect(lambda _checked=False, value=topic_id: self.practice_topic_requested.emit(value))
            actions.addWidget(learn)
            actions.addWidget(drill)
            box.addLayout(actions)
            self.cards.append((card, name, bool(total)))
        self._reflow()


class ProgressOverview(QtWidgets.QWidget):
    mistakes_requested = QtCore.pyqtSignal()
    practice_requested = QtCore.pyqtSignal()

    def __init__(self, progress_path: Path, language: str = "ru", parent=None) -> None:
        super().__init__(parent)
        self.progress_path = Path(progress_path)
        self.language = normalize_language(language, "ru")
        self._build()

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(12)
        self.title = _heading("", 28)
        layout.addWidget(self.title)
        self.summary = QtWidgets.QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#65758A; font-size:12px;")
        layout.addWidget(self.summary)
        self.progress_notice = ProgressReadNotice(self.refresh, self)
        layout.addWidget(self.progress_notice)
        self.mock_history_card = _card()
        history_layout = QtWidgets.QVBoxLayout(self.mock_history_card)
        history_layout.setContentsMargins(16, 14, 16, 14)
        history_layout.setSpacing(10)
        self.mock_history_title = _heading("", 14)
        history_layout.addWidget(self.mock_history_title)
        self.mock_history_row = QtWidgets.QHBoxLayout()
        self.mock_history_row.setSpacing(12)
        history_layout.addLayout(self.mock_history_row)
        layout.addWidget(self.mock_history_card)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self.scroll.viewport().setObjectName("StudentViewport")
        self.scroll.viewport().setStyleSheet("QWidget#StudentViewport { background:transparent; }")
        content = QtWidgets.QWidget()
        content.setObjectName("StudentContent")
        content.setStyleSheet("QWidget#StudentContent { background:transparent; }")
        self.rows = QtWidgets.QVBoxLayout(content)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(8)
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)
        buttons = QtWidgets.QHBoxLayout()
        self.review_button = _button("")
        self.review_button.clicked.connect(self.mistakes_requested.emit)
        self.practice_button = _button("", True)
        self.practice_button.clicked.connect(self.practice_requested.emit)
        buttons.addWidget(self.review_button)
        buttons.addStretch(1)
        buttons.addWidget(self.practice_button)
        layout.addLayout(buttons)
        self.refresh()

    def set_language(self, language: str) -> None:
        self.language = normalize_language(language, self.language)
        self.refresh()

    def refresh(self) -> None:
        text = _COPY[self.language]
        self.title.setText(text["progress_title"])
        self.mock_history_title.setText(text["mock_history"])
        snapshot = self.progress_notice.read(self.progress_path, self.language)
        if snapshot is None:
            self.summary.setText(self.progress_notice.copy["unknown"])
            self.mock_history_card.hide()
            self._clear_rows()
            self.review_button.setText(text["review"] + " · —")
            self.review_button.setEnabled(False)
            self.review_button.show()
            self.practice_button.setText(text["start"])
            self.practice_button.show()
            return
        mistake_count = len(snapshot.mistake_ids)
        self.review_button.setText(f"{text['review']} · {mistake_count}")
        self.review_button.setEnabled(mistake_count > 0)
        self.practice_button.setText(text["start"])
        attempts = snapshot.attempts
        if not attempts:
            self.summary.setText(text["empty_progress"])
            self.mock_history_card.hide()
            self.review_button.hide()
            self.practice_button.hide()
            self._clear_rows()
            empty = _card()
            empty.setObjectName("ProgressEmpty")
            empty.setStyleSheet(
                "QFrame#ProgressEmpty { background:#FFFFFF; border:1px solid #D8E1EC; "
                "border-radius:18px; }"
            )
            empty.setMaximumWidth(680)
            box = QtWidgets.QVBoxLayout(empty)
            box.setContentsMargins(32, 26, 32, 28)
            box.setSpacing(12)
            art = OrbitArt(light=False)
            art.setFixedSize(150, 130)
            box.addWidget(art, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
            heading = _heading(text["start"], 22)
            heading.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            box.addWidget(heading)
            caption = QtWidgets.QLabel(text["empty_progress"])
            caption.setWordWrap(True)
            caption.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            caption.setStyleSheet("color:#65758A; font-size:13px;")
            box.addWidget(caption)
            empty_action = _button(text["start"], True)
            empty_action.clicked.connect(self.practice_requested.emit)
            box.addWidget(empty_action, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
            self.rows.addWidget(empty, 0, QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
            self.rows.addStretch(1)
            self.summary.clear()
            return
        mocks = full_mock_history(attempts)
        self.review_button.show()
        self.practice_button.show()
        self.mock_history_card.show()
        self._refresh_mock_history(mocks)
        latest = mocks[-1] if mocks else None
        best = max((int(item.get("score", 0) or 0) for item in mocks), default=None)
        summary_parts = [
            f"{text['completed']}: {len(attempts)}",
            f"{text['weekly']}: {weekly_question_count(attempts)} {text['questions']}",
        ]
        if latest:
            summary_parts.append(f"{text['score']}: {latest.get('score', 0)}/50")
        if best is not None:
            summary_parts.append(f"{text['best']}: {best}/50")
        self.summary.setText(" · ".join(summary_parts))
        self._clear_rows()
        topic_results = aggregate_topic_progress(attempts)
        names = _TOPIC_NAMES[self.language]
        practiced = [
            (values["correct"] / values["total"], topic_id, values)
            for topic_id, values in topic_results.items() if values["total"]
        ]
        if not practiced:
            return
        self.rows.addWidget(_heading(text["weak"], 14))
        for accuracy, topic_id, values in sorted(practiced)[:8]:
            row = _card()
            box = QtWidgets.QVBoxLayout(row)
            box.setContentsMargins(14, 9, 14, 9)
            box.setSpacing(7)
            label = _heading(names.get(topic_id, topic_id), 12)
            detail = QtWidgets.QLabel(f"{round(accuracy * 100)}% · {values['correct']}/{values['total']}")
            detail.setStyleSheet("color:#486A91; font-size:11px; font-weight:600;")
            title_row = QtWidgets.QHBoxLayout()
            title_row.addWidget(label, 1)
            title_row.addWidget(detail)
            topic_progress = QtWidgets.QProgressBar()
            topic_progress.setRange(0, 100)
            topic_progress.setValue(round(accuracy * 100))
            topic_progress.setTextVisible(False)
            topic_progress.setFixedHeight(6)
            topic_progress.setStyleSheet(
                "QProgressBar { background:#D8E1EC; border:0; border-radius:3px; }"
                "QProgressBar::chunk { background:#26725C; border-radius:3px; }"
            )
            box.addLayout(title_row)
            box.addWidget(topic_progress)
            self.rows.addWidget(row)
        self.rows.addStretch(1)

    def _refresh_mock_history(self, mocks: list[dict]) -> None:
        while self.mock_history_row.count():
            item = self.mock_history_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        if not mocks:
            empty = QtWidgets.QLabel(_COPY[self.language]["no_mock_history"])
            empty.setWordWrap(True)
            empty.setStyleSheet("color:#65758A; font-size:11px; padding:3px 0;")
            self.mock_history_row.addWidget(empty, 1)
            return
        for attempt in mocks[-5:]:
            item = QtWidgets.QWidget()
            column = QtWidgets.QVBoxLayout(item)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(5)
            score = max(0, min(50, int(attempt.get("score", 0) or 0)))
            value = QtWidgets.QLabel(f"{score}/50")
            value.setStyleSheet("color:#18283D; font-size:15px; font-weight:700;")
            timestamp = str(attempt.get("completed_at", ""))
            try:
                date_label = date.fromisoformat(timestamp[:10]).strftime("%d.%m.%Y")
            except ValueError:
                date_label = "—"
            day = QtWidgets.QLabel(date_label)
            day.setStyleSheet("color:#65758A; font-size:10px;")
            bar = QtWidgets.QProgressBar()
            bar.setRange(0, 50)
            bar.setValue(score)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet(
                "QProgressBar { background:#D8E1EC; border:0; border-radius:3px; }"
                "QProgressBar::chunk { background:#486A91; border-radius:3px; }"
            )
            column.addWidget(value)
            column.addWidget(day)
            column.addWidget(bar)
            self.mock_history_row.addWidget(item, 1)

    def _clear_rows(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                old_widget = item.widget()
                old_widget.hide()
                old_widget.deleteLater()
