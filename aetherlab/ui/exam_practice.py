"""Three-language, answer-keyed ENТ physics practice dialog."""

from __future__ import annotations

import random
import time
from datetime import date
from html import escape
from pathlib import Path
from uuid import uuid4

from aetherlab.core.language import LANGUAGE_NAMES, normalize_language
from aetherlab.services.ent_physics_bank import (
    ENT_FULL_MOCK_DURATION_S,
    ENT_MAX_POINTS,
    ENT_TOPIC_IDS,
    ENT_TOTAL_QUESTIONS,
    EXERCISE_TOTAL,
    FREE_MOCK_URL,
    SOURCE_URL,
    glossary_for_language,
    mock_questions_for_language,
    question_max_points,
    questions_for_language,
    score_question,
)
from aetherlab.services.ent_practice_progress import (
    aggregate_topic_progress,
    clear_active_session,
    full_mock_history,
    load_active_session,
    record_attempt,
    save_active_session,
    save_goals,
    weekly_question_count,
)
from aetherlab.services.practice_math import readable_explanation, readable_formula
from aetherlab.ui.fonts import install_ui_fonts
from aetherlab.ui.progress_notice import ProgressReadNotice
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt
from aetherlab.ui.style import AETHERLAB_QSS

require_qt()


_PROCTOR_TEXT = {
    "kk": {
        "opt_in": "Камераны тексеру",
        "details": "Бет саны мен қолданба фокусы ғана құрылғыда тексеріледі. Көз қозғалысын талдау бұл пилотта жоқ. Бейне сақталмайды, ал белгілер баллға әсер етпейді.",
        "active": "Камера: сынақ бақылауы қосулы · бейне сақталмайды",
        "unavailable": "Камера қолжетімсіз · сынақ жалғасады, баллға әсер етпейді",
        "lost": "Камера байланысы үзілді · бұл алдау деп есептелмейді",
        "events": "Камера белгілері: {events}. Олар құрылғыда сақталады және баллды өзгертпейді. Мұғалімге арналған бөлек қарау беті әлі қосылмаған.",
        "resume_title": "Аяқталмаған ҰБТ сынағы табылды",
        "resume_prompt": "Соңғы әрекетті жалғастырасыз ба? Сақталған жауаптар тек осы құрылғыда қалады. «Қайта бастау» сақталған жауаптарды өшіреді. Бас тартсаңыз, әрекет сақталады.",
        "resume_yes": "Жалғастыру", "resume_no": "Қайта бастау", "cancel": "Бас тарту",
        "finish_yes": "Сынақты аяқтау", "finish_no": "Сынақты жалғастыру",
        "math_unavailable": "Формула көрсетілмеді. Жоғарыдағы мәтіндік түсіндірмені пайдаланыңыз.",
        "finish_prompt": "Сынақты қазір аяқтайсыз ба? Жауапсыз тапсырмалар қате ретінде аталмайды, бірақ оларға ұпай берілмейді.",
        "event_names": {"face_not_visible": "бет ұзақ уақыт көрінбеді", "multiple_faces": "бірнеше бет байқалды", "camera_unavailable": "камера ашылмады", "camera_lost": "камера байланысы үзілді", "app_focus_lost": "қолданба фокусты жоғалтты"},
    },
    "ru": {
        "opt_in": "Теневая проверка камеры",
        "details": "На устройстве проверяются только наличие лиц и фокус приложения. Анализ направления взгляда в этом пилоте не включён. Видео не сохраняется, отметки не влияют на балл.",
        "active": "Камера: теневой контроль включён · видео не сохраняется",
        "unavailable": "Камера недоступна · экзамен продолжается, на балл это не влияет",
        "lost": "Связь с камерой прервалась · это не считается списыванием",
        "events": "Отметки камеры: {events}. Они сохранены на этом устройстве и не меняют балл. Отдельный экран просмотра учителем пока не реализован.",
        "resume_title": "Найдена незавершённая попытка ЕНТ",
        "resume_prompt": "Продолжить последнюю попытку? Сохранённые ответы остаются только на этом устройстве. «Начать заново» удалит сохранённые ответы. Отмена сохранит попытку.",
        "resume_yes": "Продолжить попытку", "resume_no": "Начать заново", "cancel": "Отмена",
        "finish_yes": "Завершить пробник", "finish_no": "Продолжить пробник",
        "math_unavailable": "Не удалось отобразить формулу. Используйте текстовое объяснение выше.",
        "finish_prompt": "Завершить пробник сейчас? Пропуски не записываются как ошибки, но за них начисляется 0 баллов.",
        "event_names": {"face_not_visible": "лицо долго не было видно", "multiple_faces": "обнаружено несколько лиц", "camera_unavailable": "камера не открылась", "camera_lost": "камера отключилась", "app_focus_lost": "приложение потеряло фокус"},
    },
    "en": {
        "opt_in": "Camera shadow check",
        "details": "Only face presence and app focus are checked locally. Gaze analysis is not enabled in this pilot. Video is not saved, and event flags do not affect your score.",
        "active": "Camera: shadow check active · no video is saved",
        "unavailable": "Camera unavailable · the exam continues and your score is unaffected",
        "lost": "Camera connection was lost · this is not treated as cheating",
        "events": "Camera flags: {events}. They are stored on this device and do not change your score. A separate teacher review screen is not implemented yet.",
        "resume_title": "An unfinished UNT attempt was found",
        "resume_prompt": "Resume the last attempt? Saved answers remain on this device only. Start again removes the saved answers. Cancel keeps the attempt.",
        "resume_yes": "Resume attempt", "resume_no": "Start again", "cancel": "Cancel",
        "finish_yes": "Finish mock", "finish_no": "Continue mock",
        "math_unavailable": "The formula could not be displayed. Use the text explanation above.",
        "finish_prompt": "Finish the mock now? Unanswered items are not recorded as wrong, but earn zero points.",
        "event_names": {"face_not_visible": "face was not visible for a while", "multiple_faces": "more than one face was detected", "camera_unavailable": "camera could not start", "camera_lost": "camera connection was lost", "app_focus_lost": "app focus was lost"},
    },
}


_TEXT = {
    "kk": {
        "title": "ҰБТ · Физика",
        "intro": f"{EXERCISE_TOTAL} түрлі жаттығу және бөлек 40 тапсырмалық сынақ ЕНТ форматына сай. Жаттығулар авторлық, бұл ресми нұсқа емес.",
        "language": "Оқу тілі",
        "topic_filter": "Тақырып",
        "all_topics": "Барлық 25 тақырып",
        "difficulty": "Қиындық",
        "all_difficulties": "Барлық деңгей",
        "difficulty_A": "Базалық",
        "difficulty_B": "Орташа",
        "difficulty_C": "Жоғары",
        "mode": "Режим",
        "practice": f"{EXERCISE_TOTAL} тапсырма · түсіндірмесі бар жаттығу",
        "timed": "Сынақ ЕНТ · 40 тапсырма · 90 минут",
        "start": "Бастау",
        "back": "Артқа",
        "next": "Келесі",
        "check": "Жауапты тексеру",
        "finish": "Аяқтау",
        "close": "Жабу",
        "choose": "Барлық жолға жауап беріңіз.",
        "right": "Дұрыс жауап.",
        "wrong": "Бұл жолы дұрыс болмады.",
        "correct": "Дұрыс жауап",
        "score": "Нәтиже",
        "time": "Қалған уақыт",
        "timer": "01:20:00",
        "result": "Дайындық нәтижесі",
        "key": "Жауап кілті және түсіндіру",
        "term": "Қазақша термин",
        "practice_set": f"Жаттығуда {EXERCISE_TOTAL} есеп бар. Бөлек сынақ ҰБТ форматын сақтайды: 40 тапсырма, 50 балл. Бұл ресми нұсқа емес, авторлық оқу материалы.",
        "your_answer": "Сіздің жауабыңыз",
        "not_answered": "Жауап берілмеді",
        "official_prep": "Ресми материалдар мен нұсқалар",
        "free_mock": "Тегін ресми байқау ҰБТ",
        "local_sources": "Менің ҰБТ сынақ нұсқаларым",
        "context": "Жағдаят",
        "select_all": "Бір немесе бірнеше жауапты таңдаңыз.",
        "match": "Сәйкестендіріңіз",
        "select_match": "Таңдаңыз…",
        "format_single": "Бір дұрыс жауап",
        "format_multi": "Бір немесе бірнеше дұрыс жауап",
        "format_matching": "Сәйкестендіру",
        "hero_badge": f"25 ТАҚЫРЫП · {EXERCISE_TOTAL} ЖАТТЫҒУ",
        "topic_progress": "Тақырыптар бойынша прогресс",
        "no_progress": "Бастапқы деңгей: әлі аяқталған әрекет жоқ.",
        "save_pdf": "PDF сақтау",
        "save_pdf_title": "Дайындық нәтижесін сақтау",
        "pdf_filter": "PDF файлы (*.pdf)",
        "pdf_saved": "PDF сақталды: {path}",
        "pdf_error": "PDF жасау мүмкін болмады: {error}",
        "save_close": "Жабу",
        "topic_count": "25 тақырып бойынша жауаптарыңыз осында жинақталады.",
        "progress_line": "Тарихи нәтиже: {correct}/{total}",
        "all_progress_line": "Жалпы тарих: {correct}/{total} жауап · 25 тақырып",
        "target_score": "Мақсатты балл / 50",
        "exam_date": "ҰБТ күні",
        "weekly_goal": "Апталық тапсырма мақсаты",
        "weekly_goal_suffix": " / апта",
        "weekly_mock_day": "Апталық сынақ ЕНТ күні",
        "weekly_mock_none": "Күн таңдалмаған",
        "weekdays": ("Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"),
        "prep_level": "Дайындық деңгейі",
        "save_goals": "Оқу жоспарын сақтау",
        "goals_saved": "Жоспар осы құрылғыда сақталды.",
        "dashboard_empty": "Толық сынақтан кейін болжамды нәтиже мен тақырыптық прогресс осында көрінеді.",
        "dashboard_latest": "Соңғы толық сынақ: {score}/50 · мақсат: {target}.",
        "dashboard_best": "Үздік толық сынақ: {score}/50.",
        "dashboard_week": "Осы аптада: {count} тапсырма · мақсат: {goal}.",
        "dashboard_date": "ҰБТ-ға дейін: {days} күн.",
        "mistake_review": "Қателерді қайталау · {count}",
        "no_mistakes": "Қайталауға белгіленген қате тапсырма жоқ.",
        "score_result": "{score}/{possible} балл · {questions} тапсырма",
        "result_stats": "Дұрыс: {correct} · қате: {incorrect} · жауапсыз: {unanswered} · уақыт: {elapsed}",
        "points_feedback": "Жаттығу ұпайы: {score}/{possible}.",
        "not_counted": "Бұл тапсырма орындалмады және жаттығу нәтижесіне кірмейді.",
        "recommendation": "Келесі қадам: {topic} тақырыбын қайталаңыз — бұл жолы {correct}/{total} дұрыс.",
        "practice_weakest": "Әлсіз тақырыпты жаттықтыру",
        "practice_more": "Тақырыпты жаттықтыру",
        "success_recommendation": "{topic}: {correct}/{total} дұрыс, қате жоқ. Бұл тек осы әрекеттің нәтижесі. Келесі қадам: тағы бірнеше тапсырма орындаңыз.",
        "no_question_match": "Бұл тақырып пен қиындық деңгейіне тапсырма табылмады.",
        "topic_col": "Тақырып",
        "mastery_col": "Игеру",
        "correct_total_col": "Дұрыс / барлығы",
        "points_col": "Ұпай",
        "setup_heading": "Жаттығуды баптау",
        "plan_heading": "Дайындық жоспары",
    },
    "ru": {
        "title": "ЕНТ · Физика",
        "intro": f"{EXERCISE_TOTAL} разных упражнений и отдельный пробник из 40 заданий в формате ЕНТ. Упражнения авторские, это не официальный вариант.",
        "language": "Язык обучения",
        "topic_filter": "Тема",
        "all_topics": "Все 25 тем",
        "difficulty": "Сложность",
        "all_difficulties": "Все уровни",
        "difficulty_A": "Базовый",
        "difficulty_B": "Средний",
        "difficulty_C": "Высокий",
        "mode": "Режим",
        "practice": f"{EXERCISE_TOTAL} заданий · тренировка с разбором",
        "timed": "Пробник ЕНТ · 40 заданий · 90 минут",
        "start": "Начать",
        "back": "Назад",
        "next": "Дальше",
        "check": "Проверить ответ",
        "finish": "Завершить",
        "close": "Закрыть",
        "choose": "Заполните все строки ответа.",
        "right": "Верно.",
        "wrong": "Пока неверно.",
        "correct": "Правильный ответ",
        "score": "Результат",
        "time": "Осталось",
        "timer": "01:20:00",
        "result": "Результат тренировки",
        "key": "Ответы и разбор",
        "term": "Термин на казахском",
        "practice_set": f"В тренировке доступны {EXERCISE_TOTAL} задач. Отдельный пробник сохраняет формат ЕНТ: 40 заданий и 50 баллов. Это авторский учебный материал, не официальный вариант.",
        "your_answer": "Ваш ответ",
        "not_answered": "Без ответа",
        "official_prep": "Официальные материалы и варианты",
        "free_mock": "Бесплатное официальное пробное ЕНТ",
        "local_sources": "Мои пробники ЕНТ из файлов",
        "context": "Контекст",
        "select_all": "Выберите один или несколько ответов.",
        "match": "Сопоставьте",
        "select_match": "Выберите…",
        "format_single": "Один правильный ответ",
        "format_multi": "Один или несколько правильных ответов",
        "format_matching": "Сопоставление",
        "hero_badge": f"25 ТЕМ · {EXERCISE_TOTAL} УПРАЖНЕНИЙ",
        "topic_progress": "Прогресс по темам",
        "no_progress": "Стартовая точка: завершённых попыток пока нет.",
        "save_pdf": "Сохранить PDF",
        "save_pdf_title": "Сохранить результат подготовки",
        "pdf_filter": "Файл PDF (*.pdf)",
        "pdf_saved": "PDF сохранён: {path}",
        "pdf_error": "Не удалось создать PDF: {error}",
        "save_close": "Закрыть",
        "topic_count": "Ваши результаты по 25 темам будут собраны здесь.",
        "progress_line": "История по теме: {correct}/{total} верно",
        "all_progress_line": "Общая история: {correct}/{total} ответов · 25 тем",
        "target_score": "Целевой балл / 50",
        "exam_date": "Дата ЕНТ",
        "weekly_goal": "Цель заданий на неделю",
        "weekly_goal_suffix": " / неделю",
        "weekly_mock_day": "День пробного ЕНТ каждую неделю",
        "weekly_mock_none": "Не выбран",
        "weekdays": ("Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"),
        "prep_level": "Уровень подготовки",
        "save_goals": "Сохранить план подготовки",
        "goals_saved": "План сохранён на этом устройстве.",
        "dashboard_empty": "После полного пробника здесь появятся оценка результата и прогресс по темам.",
        "dashboard_latest": "Последний полный пробник: {score}/50 · цель: {target}.",
        "dashboard_best": "Лучший полный пробник: {score}/50.",
        "dashboard_week": "На этой неделе: {count} заданий · цель: {goal}.",
        "dashboard_date": "До ЕНТ: {days} дн.",
        "mistake_review": "Повторить ошибки · {count}",
        "no_mistakes": "Нет заданий, отмеченных для повторения.",
        "score_result": "{score}/{possible} баллов · {questions} заданий",
        "result_stats": "Верно: {correct} · ошибок: {incorrect} · без ответа: {unanswered} · время: {elapsed}",
        "points_feedback": "Баллы за попытку: {score}/{possible}.",
        "not_counted": "Это задание не решено и не входит в результат тренировки.",
        "recommendation": "Следующий шаг: повторите тему «{topic}» — в этой попытке верно {correct}/{total}.",
        "practice_weakest": "Тренировать слабую тему",
        "practice_more": "Продолжить практику темы",
        "success_recommendation": "«{topic}»: верно {correct}/{total}, ошибок нет. Это результат только этой попытки. Следующий шаг: решите ещё несколько задач.",
        "no_question_match": "Для этой темы и уровня сложности заданий пока нет.",
        "topic_col": "Тема",
        "mastery_col": "Освоение",
        "correct_total_col": "Верно / всего",
        "points_col": "Баллы",
        "setup_heading": "Настройки тренировки",
        "plan_heading": "План подготовки",
    },
    "en": {
        "title": "UNT · Physics",
        "intro": f"{EXERCISE_TOTAL} different exercises plus a separate 40-question UNT-format mock. The exercises are original study material, not an official test.",
        "language": "Study language",
        "topic_filter": "Topic",
        "all_topics": "All 25 topics",
        "difficulty": "Difficulty",
        "all_difficulties": "All levels",
        "difficulty_A": "Basic",
        "difficulty_B": "Intermediate",
        "difficulty_C": "Advanced",
        "mode": "Mode",
        "practice": f"{EXERCISE_TOTAL} exercises · learn with explanations",
        "timed": "UNT mock · 40 questions · 90 minutes",
        "start": "Start",
        "back": "Back",
        "next": "Next",
        "check": "Check answer",
        "finish": "Finish",
        "close": "Close",
        "choose": "Complete every answer row.",
        "right": "Correct.",
        "wrong": "Not this time.",
        "correct": "Correct answer",
        "score": "Score",
        "time": "Time left",
        "timer": "01:20:00",
        "result": "Practice result",
        "key": "Answer key and explanations",
        "term": "Kazakh term",
        "practice_set": f"Practice includes {EXERCISE_TOTAL} exercises. The separate mock keeps the 40-question, 50-point UNT format. These are original study materials, not an official test.",
        "your_answer": "Your answer",
        "not_answered": "Not answered",
        "official_prep": "Official materials and sample tests",
        "free_mock": "Free official UNT practice test",
        "local_sources": "My source mock sets",
        "context": "Context",
        "select_all": "Select one or more answers.",
        "match": "Match the items",
        "select_match": "Choose…",
        "format_single": "One correct answer",
        "format_multi": "One or more correct answers",
        "format_matching": "Matching",
        "hero_badge": f"25 TOPICS · {EXERCISE_TOTAL} EXERCISES",
        "topic_progress": "Progress by topic",
        "no_progress": "Starting point: no completed attempts yet.",
        "save_pdf": "Save PDF",
        "save_pdf_title": "Save practice results",
        "pdf_filter": "PDF file (*.pdf)",
        "pdf_saved": "PDF saved: {path}",
        "pdf_error": "Could not create PDF: {error}",
        "save_close": "Close",
        "topic_count": "Your results across 25 topics will appear here.",
        "progress_line": "Topic history: {correct}/{total}",
        "all_progress_line": "All-time: {correct}/{total} answers · 25 topics",
        "target_score": "Target score / 50",
        "exam_date": "UNT date",
        "weekly_goal": "Weekly question goal",
        "weekly_goal_suffix": " / week",
        "weekly_mock_day": "Weekly UNT mock day",
        "weekly_mock_none": "Not set",
        "weekdays": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
        "prep_level": "Preparation level",
        "save_goals": "Save study plan",
        "goals_saved": "Plan saved on this device.",
        "dashboard_empty": "Your estimated score and topic progress will appear after a full mock exam.",
        "dashboard_latest": "Latest full mock: {score}/50 · target: {target}.",
        "dashboard_best": "Best full mock: {score}/50.",
        "dashboard_week": "This week: {count} questions · goal: {goal}.",
        "dashboard_date": "Days until the UNT: {days}.",
        "mistake_review": "Review mistakes · {count}",
        "no_mistakes": "There are no questions marked for review.",
        "score_result": "{score}/{possible} points · {questions} questions",
        "result_stats": "Correct: {correct} · incorrect: {incorrect} · unanswered: {unanswered} · time: {elapsed}",
        "points_feedback": "Practice points: {score}/{possible}.",
        "not_counted": "This question was not attempted and does not count in the practice result.",
        "recommendation": "Next step: review {topic} — {correct}/{total} correct in this attempt.",
        "practice_weakest": "Practice the weakest topic",
        "practice_more": "Continue topic practice",
        "success_recommendation": "{topic}: {correct}/{total} correct with no mistakes. This reflects only this attempt. Next step: try a few more questions.",
        "no_question_match": "There are no questions for this topic and difficulty yet.",
        "topic_col": "Topic",
        "mastery_col": "Mastery",
        "correct_total_col": "Correct / total",
        "points_col": "Points",
        "setup_heading": "Practice setup",
        "plan_heading": "Study plan",
    },
}

_TOPIC_NAMES = {
    "kk": {
        "kinematics": "Кинематика", "dynamics": "Динамика", "statics": "Статика",
        "fluids": "Сұйықтар мен газдар", "molecular_kinetic_theory": "Молекулалық физика",
        "gas_laws": "Идеал газ заңдары", "thermodynamics": "Термодинамика",
        "liquids_solids": "Сұйықтар мен қатты денелер", "electrostatics": "Электростатика",
        "electricity": "Тұрақты ток", "current_media": "Әртүрлі ортадағы ток",
        "magnetic_field": "Магнит өрісі", "induction": "Электромагниттік индукция",
        "mechanical_oscillations": "Механикалық тербелістер", "ac_circuits": "Айнымалы ток",
        "electromagnetic_waves": "Электромагниттік толқындар", "wave_optics": "Толқындық оптика",
        "geometric_optics": "Геометриялық оптика", "relativity": "Арнайы салыстырмалылық теориясы",
        "quantum_physics": "Кванттық физика", "nuclear_physics": "Атом ядросы мен радиоактивтілік",
        "nanotechnology": "Нанотехнология", "cosmology": "Космология",
        "conservation": "Сақталу заңдары", "wave_motion": "Толқындық қозғалыс",
    },
    "ru": {
        "kinematics": "Кинематика", "dynamics": "Динамика", "statics": "Статика",
        "fluids": "Жидкости и газы", "molecular_kinetic_theory": "Молекулярная физика",
        "gas_laws": "Законы идеального газа", "thermodynamics": "Термодинамика",
        "liquids_solids": "Жидкости и твёрдые тела", "electrostatics": "Электростатика",
        "electricity": "Постоянный ток", "current_media": "Ток в различных средах",
        "magnetic_field": "Магнитное поле", "induction": "Электромагнитная индукция",
        "mechanical_oscillations": "Механические колебания", "ac_circuits": "Переменный ток",
        "electromagnetic_waves": "Электромагнитные волны", "wave_optics": "Волновая оптика",
        "geometric_optics": "Геометрическая оптика", "relativity": "Специальная теория относительности",
        "quantum_physics": "Квантовая физика", "nuclear_physics": "Атомное ядро и радиоактивность",
        "nanotechnology": "Нанотехнологии", "cosmology": "Космология",
        "conservation": "Законы сохранения", "wave_motion": "Волновое движение",
    },
    "en": {
        "kinematics": "Kinematics", "dynamics": "Dynamics", "statics": "Statics",
        "fluids": "Fluids and gases", "molecular_kinetic_theory": "Kinetic molecular theory",
        "gas_laws": "Ideal gas laws", "thermodynamics": "Thermodynamics",
        "liquids_solids": "Liquids and solids", "electrostatics": "Electrostatics",
        "electricity": "Direct current", "current_media": "Current in different media",
        "magnetic_field": "Magnetic field", "induction": "Electromagnetic induction",
        "mechanical_oscillations": "Mechanical oscillations", "ac_circuits": "Alternating current",
        "electromagnetic_waves": "Electromagnetic waves", "wave_optics": "Wave optics",
        "geometric_optics": "Geometrical optics", "relativity": "Special relativity",
        "quantum_physics": "Quantum physics", "nuclear_physics": "Atomic nucleus and radioactivity",
        "nanotechnology": "Nanotechnology", "cosmology": "Cosmology",
        "conservation": "Conservation laws", "wave_motion": "Wave motion",
    },
}

_LEVEL_NAMES = {
    "kk": {"beginner": "Бастап жүрмін", "intermediate": "Негізін білемін", "advanced": "Жоғары деңгей"},
    "ru": {"beginner": "Начинаю", "intermediate": "Знаю основы", "advanced": "Уверенный уровень"},
    "en": {"beginner": "Starting out", "intermediate": "Know the basics", "advanced": "Confident"},
}

_STORAGE_TEXT = {
    "kk": {
        "goals_error": "Жоспар сақталмады. Енгізілген мәндер қалды. Файлға қолжетімділікті қалпына келтіріп, қайта сақтаңыз.",
        "session_error": "Жауаптарды файлға сақтау мүмкін болмады. Олар осы терезеде сақталған. Қолжетімділікті қалпына келтіріп, қайта сақтаңыз; терезені жабу үшін сақтау қажет.",
        "resume_error": "Сақталған жаттығуды оқу мүмкін болмады. Файл өзгертілмеді. Қолжетімділікті қалпына келтіріп, қайта бастаңыз.",
        "restart_error": "Сақталған әрекеттің жойылғанын растау мүмкін болмады. Жаңа әрекет басталған жоқ. Файлға қолжетімділікті тексеріп, қайталаңыз.",
        "result_error": "Нәтиже сақталмады. Жауаптар осы терезеде сақталған және өзгертілмейді. Қолжетімділікті қалпына келтіріп, нәтижені қайта сақтаңыз.",
        "retry_result": "Нәтижені қайта сақтау",
    },
    "ru": {
        "goals_error": "План не сохранён. Введённые значения остались. Восстановите доступ к файлу и сохраните ещё раз.",
        "session_error": "Не удалось сохранить ответы в файл. Они остались в этом окне. Восстановите доступ и повторите сохранение; для закрытия окна нужно сохранить ответы.",
        "resume_error": "Не удалось прочитать сохранённую попытку. Файл не изменён. Восстановите доступ и повторите запуск.",
        "restart_error": "Не удалось подтвердить удаление сохранённой попытки. Новая попытка не начата. Проверьте доступ к файлу и повторите.",
        "result_error": "Результат не сохранён. Ответы остались в этом окне и больше не меняются. Восстановите доступ и повторите сохранение результата.",
        "retry_result": "Повторить сохранение результата",
    },
    "en": {
        "goals_error": "The plan was not saved. Your entered values remain. Restore file access and save again.",
        "session_error": "Answers could not be saved to the file. They remain in this window. Restore access and retry saving; answers must be saved before closing.",
        "resume_error": "The saved attempt could not be read. Its file was not changed. Restore access and try starting again.",
        "restart_error": "The saved attempt could not be confirmed as removed. A new attempt was not started. Check file access and try again.",
        "result_error": "The result was not saved. Answers remain in this window and cannot be changed. Restore access and retry saving the result.",
        "retry_result": "Retry saving result",
    },
}


class ExamPracticeDialog(QtWidgets.QDialog):
    """Run topic-selected practice from the 2,500-item bank or fixed mock."""

    def __init__(
        self,
        language: str = "kk",
        parent=None,
        progress_path: Path | None = None,
        topic_id: str | None = None,
        start_mode: str | None = None,
    ) -> None:
        super().__init__(parent)
        install_ui_fonts()
        self._language = normalize_language(language, "kk")
        self._mode = "practice"
        self._questions: tuple[dict, ...] = ()
        self._index = 0
        self._answers: list[tuple[int, ...] | None] = []
        self._checked: set[int] = set()
        self._seconds_left = ENT_FULL_MOCK_DURATION_S
        self._answer_widgets: list[QtWidgets.QWidget] = []
        self._answer_group = None
        self._session_finished = False
        self._completion_pending = False
        self._attempt_id = ""
        self._goals_loaded = False
        self._deadline_monotonic: float | None = None
        self._proctor_enabled = False
        self._camera_worker = None
        from aetherlab.services.proctoring import ShadowEventTracker

        self._proctor = ShadowEventTracker()
        self._progress_path = Path(progress_path) if progress_path else None
        self._initial_topic_id = topic_id
        self._topic_names = _TOPIC_NAMES[self._language]
        self._current_topic_progress: dict[str, dict[str, int]] = {}
        self._recommended_topic = ""
        self._full_mock = False
        self.setObjectName("ENTPracticeDialog")
        self.setStyleSheet(AETHERLAB_QSS)
        self.setMinimumSize(640, 580)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                min(820, max(680, int(available.width() * 0.58))),
                min(780, max(620, int(available.height() * 0.90))),
            )
        else:
            self.resize(780, 740)
        self.setWindowTitle(_TEXT[self._language]["title"])

        self._stack = QtWidgets.QStackedWidget()
        outer = QtWidgets.QVBoxLayout(self)
        self._storage_notice = QtWidgets.QLabel()
        self._storage_notice.setWordWrap(True)
        self._storage_notice.setStyleSheet("color:#8A5A24; padding:8px;")
        self._storage_notice.hide()
        outer.addWidget(self._storage_notice)
        self.progress_notice = ProgressReadNotice(self._retry_progress, self)
        outer.addWidget(self.progress_notice)
        outer.addWidget(self._stack)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._build_start_page()
        self._build_session_page()
        self._build_result_page()
        if start_mode in {"practice", "timed"}:
            self._mode_combo.setCurrentIndex(self._mode_combo.findData(start_mode))

    @property
    def _t(self) -> dict[str, str]:
        return _TEXT[self._language]

    def done(self, result: int) -> None:
        if not self._persist_active_session():
            return
        # Closing a timed attempt must not grade it later in a hidden dialog.
        self._timer.stop()
        self._stop_camera_monitor()
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt virtual override
        if not self._persist_active_session():
            event.ignore()
            return
        super().closeEvent(event)

    @property
    def _storage_text(self) -> dict[str, str]:
        return _STORAGE_TEXT[self._language]

    def _storage_status(self, key: str | None) -> None:
        self._storage_notice.setText(self._storage_text[key] if key else "")
        self._storage_notice.setVisible(bool(key))

    def _build_start_page(self) -> None:
        page = QtWidgets.QWidget()
        page_layout = QtWidgets.QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QtWidgets.QScrollArea(page)
        scroll.setObjectName("PracticeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea#PracticeScroll { background:transparent; border:none; }"
            "QScrollArea#PracticeScroll > QWidget > QWidget { background:transparent; }"
        )
        content = QtWidgets.QWidget()
        content.setMinimumWidth(0)
        content.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(22, 17, 22, 12)
        layout.setSpacing(10)

        hero = QtWidgets.QFrame()
        hero.setObjectName("PracticeHero")
        hero.setStyleSheet(
            "QFrame#PracticeHero { background:#EDF2F8; border:1px solid #A5B6CB; "
            "border-radius:18px; border-top:3px solid #486A91; }"
        )
        hero_layout = QtWidgets.QVBoxLayout(hero)
        hero_layout.setContentsMargins(17, 12, 17, 12)
        hero_layout.setSpacing(5)
        badge = QtWidgets.QLabel(self._t["hero_badge"])
        badge.setStyleSheet(
            "color:#26725C; background:rgba(75,99,133,0.08); border-radius:8px; "
            "padding:5px 9px; font-size:10px; font-weight:700;"
        )
        badge.setMaximumWidth(240)
        hero_layout.addWidget(badge, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        title = QtWidgets.QLabel(self._t["title"])
        title.setStyleSheet("font-size:25px; font-weight:700; color:#18283D;")
        hero_layout.addWidget(title)
        intro = QtWidgets.QLabel(self._t["intro"])
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#65758A; font-size:13px; line-height:1.4;")
        hero_layout.addWidget(intro)
        layout.addWidget(hero)

        def make_field(label_text: str, control: QtWidgets.QWidget) -> QtWidgets.QWidget:
            field = QtWidgets.QWidget()
            field_layout = QtWidgets.QVBoxLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(5)
            label = QtWidgets.QLabel(label_text)
            label.setObjectName("PracticeFieldLabel")
            label.setStyleSheet("color:#65758A; font-size:11px; font-weight:600;")
            control.setMinimumHeight(36)
            control.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            field_layout.addWidget(label)
            field_layout.addWidget(control)
            return field

        setup = QtWidgets.QFrame()
        setup.setObjectName("PracticeSetupCard")
        setup.setStyleSheet(
            "QFrame#PracticeSetupCard { background:#FFFFFF; border:1px solid #D8E1EC; "
            "border-radius:16px; }"
        )
        setup_layout = QtWidgets.QVBoxLayout(setup)
        setup_layout.setContentsMargins(16, 12, 16, 12)
        setup_layout.setSpacing(8)
        setup_title = QtWidgets.QLabel(self._t["setup_heading"])
        setup_title.setObjectName("PracticeSectionTitle")
        setup_title.setStyleSheet("color:#24364B; font-size:13px; font-weight:700;")
        setup_layout.addWidget(setup_title)

        filters = QtWidgets.QGridLayout()
        filters.setContentsMargins(0, 0, 0, 0)
        filters.setHorizontalSpacing(14)
        filters.setVerticalSpacing(8)
        filters.setColumnStretch(0, 1)
        filters.setColumnStretch(1, 1)

        self._language_combo = QtWidgets.QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self._language_combo.addItem(name, code)
        self._language_combo.setCurrentIndex(
            max(0, self._language_combo.findData(self._language))
        )
        self._language_combo.currentIndexChanged.connect(self._change_language)
        filters.addWidget(make_field(self._t["language"], self._language_combo), 0, 0)

        self._topic_combo = QtWidgets.QComboBox()
        self._topic_combo.addItem(self._t["all_topics"], "")
        initial_topic_id = self._initial_topic_id
        for topic_id in ENT_TOPIC_IDS:
            self._topic_combo.addItem(self._topic_names[topic_id], topic_id)
        if initial_topic_id in ENT_TOPIC_IDS:
            self._topic_combo.setCurrentIndex(self._topic_combo.findData(initial_topic_id))
        self._topic_combo.currentIndexChanged.connect(self._update_topic_hint)
        filters.addWidget(make_field(self._t["topic_filter"], self._topic_combo), 0, 1)

        self._difficulty_combo = QtWidgets.QComboBox()
        self._difficulty_combo.addItem(self._t["all_difficulties"], "")
        for level in ("A", "B", "C"):
            self._difficulty_combo.addItem(self._t[f"difficulty_{level}"], level)
        self._difficulty_combo.currentIndexChanged.connect(self._update_topic_hint)
        filters.addWidget(make_field(self._t["difficulty"], self._difficulty_combo), 1, 0, 1, 2)

        self._session_size = QtWidgets.QComboBox()
        size_labels = {
            "kk": ((5, "5 тапсырма"), (10, "10 тапсырма"), (20, "20 тапсырма"), (50, "50 тапсырма"), (100, "Барлығы · 100")),
            "ru": ((5, "5 заданий"), (10, "10 заданий"), (20, "20 заданий"), (50, "50 заданий"), (100, "Все · 100")),
            "en": ((5, "5 questions"), (10, "10 questions"), (20, "20 questions"), (50, "50 questions"), (100, "All · 100")),
        }[self._language]
        for amount, label in size_labels:
            self._session_size.addItem(label, amount)
        self._session_size.setCurrentIndex(1)
        self._session_size_field = make_field(
            {"kk":"Бір жолғы жаттығу","ru":"Размер занятия","en":"Session size"}[self._language],
            self._session_size,
        )
        filters.addWidget(self._session_size_field, 2, 0, 1, 2)

        self._mode_combo = QtWidgets.QComboBox()
        self._mode_combo.addItem(self._t["practice"], "practice")
        self._mode_combo.addItem(self._t["timed"], "timed")
        self._mode_combo.hide()
        mode_cards = QtWidgets.QHBoxLayout()
        self._mode_buttons = []
        self._mode_group = QtWidgets.QButtonGroup(page)
        mode_labels = {
            "kk": (f"{EXERCISE_TOTAL} жаттығу\nӨз қарқыныңмен", "Сынақ ҰБТ\n40 сұрақ · 90 минут"),
            "ru": (f"{EXERCISE_TOTAL} упражнений\nВ своём темпе", "Пробник ЕНТ\n40 заданий · 90 минут"),
            "en": (f"{EXERCISE_TOTAL} exercises\nLearn at your own pace", "UNT mock\n40 questions · 90 min"),
        }[self._language]
        for index, key in enumerate(("practice", "timed")):
            button = QtWidgets.QPushButton(mode_labels[index])
            button.setToolTip(self._t[key])
            button.setObjectName("PracticeMode")
            button.setCheckable(True)
            button.setChecked(index == self._mode_combo.currentIndex())
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, value=index: self._mode_combo.setCurrentIndex(value))
            self._mode_group.addButton(button, index)
            self._mode_buttons.append(button)
            mode_cards.addWidget(button, 1)
        self._mode_combo.currentIndexChanged.connect(
            lambda index: self._mode_buttons[index].setChecked(True)
        )
        self._mode_combo.currentIndexChanged.connect(self._update_topic_hint)
        self._mode_combo.currentIndexChanged.connect(lambda index: self._session_size_field.setVisible(index == 0))
        layout.addLayout(mode_cards)
        setup_layout.addLayout(filters)
        layout.addWidget(setup)

        plan = QtWidgets.QFrame()
        plan.setObjectName("StudyPlanCard")
        plan.setStyleSheet(
            "QFrame#StudyPlanCard { background:#FFFFFF; border:1px solid #D8E1EC; "
            "border-radius:16px; }"
        )
        plan_layout = QtWidgets.QVBoxLayout(plan)
        plan_layout.setContentsMargins(16, 12, 16, 12)
        plan_layout.setSpacing(8)
        plan_title = QtWidgets.QLabel(self._t["plan_heading"])
        plan_title.setObjectName("PracticeSectionTitle")
        plan_title.setStyleSheet("color:#24364B; font-size:13px; font-weight:700;")
        plan_layout.addWidget(plan_title)

        goals_grid = QtWidgets.QGridLayout()
        goals_grid.setContentsMargins(0, 0, 0, 0)
        goals_grid.setHorizontalSpacing(14)
        goals_grid.setVerticalSpacing(7)
        goals_grid.setColumnStretch(0, 1)
        goals_grid.setColumnStretch(1, 1)

        self._target_score = QtWidgets.QDoubleSpinBox()
        self._target_score.setDecimals(0)
        self._target_score.setRange(0, ENT_MAX_POINTS)
        self._target_score.setSpecialValueText("—")
        self._target_score.setSuffix(" / 50")
        goals_grid.addWidget(make_field(self._t["target_score"], self._target_score), 0, 0)

        self._exam_date = QtWidgets.QDateEdit()
        self._exam_date.setCalendarPopup(True)
        self._exam_date.setDisplayFormat(
            "MMM d, yyyy" if self._language == "en" else "dd.MM.yyyy"
        )
        self._exam_date.setMinimumDate(QtCore.QDate(2000, 1, 1))
        self._exam_date.setSpecialValueText("—")
        goals_grid.addWidget(make_field(self._t["exam_date"], self._exam_date), 0, 1)

        self._weekly_goal = QtWidgets.QDoubleSpinBox()
        self._weekly_goal.setDecimals(0)
        self._weekly_goal.setRange(0, 500)
        self._weekly_goal.setSpecialValueText("—")
        self._weekly_goal.setSuffix(self._t["weekly_goal_suffix"])
        goals_grid.addWidget(make_field(self._t["weekly_goal"], self._weekly_goal), 1, 0)

        self._prep_level = QtWidgets.QComboBox()
        for level, label in _LEVEL_NAMES[self._language].items():
            self._prep_level.addItem(label, level)
        goals_grid.addWidget(make_field(self._t["prep_level"], self._prep_level), 1, 1)

        self._weekly_mock_day = QtWidgets.QComboBox()
        self._weekly_mock_day.addItem(self._t["weekly_mock_none"], None)
        for day, label in enumerate(self._t["weekdays"]):
            self._weekly_mock_day.addItem(label, day)
        goals_grid.addWidget(
            make_field(self._t["weekly_mock_day"], self._weekly_mock_day),
            2, 0, 1, 2,
        )
        plan_layout.addLayout(goals_grid)

        save_plan = QtWidgets.QPushButton(self._t["save_goals"])
        self._save_plan_button = save_plan
        save_plan.setObjectName("SecondaryButton")
        save_plan.clicked.connect(self._save_goals)
        save_plan.setMinimumHeight(36)
        plan_actions = QtWidgets.QHBoxLayout()
        plan_actions.addStretch(1)
        plan_actions.addWidget(save_plan)
        plan_layout.addLayout(plan_actions)
        layout.addWidget(plan)

        self._dashboard_summary = QtWidgets.QLabel("")
        self._dashboard_summary.setWordWrap(True)
        self._dashboard_summary.setStyleSheet(
            "color:#53647A; padding:9px 12px; border-radius:11px; "
            "background:#EDF2F8; border:1px solid #D8E1EC; font-size:12px;"
        )
        layout.addWidget(self._dashboard_summary)

        source_note = QtWidgets.QLabel(self._t["practice_set"])
        source_note.setWordWrap(True)
        source_note.setStyleSheet("color:#65758A; font-size:11px; padding:0 1px;")
        layout.addWidget(source_note)
        self._camera_opt_in = QtWidgets.QCheckBox(_PROCTOR_TEXT[self._language]["opt_in"])
        self._camera_opt_in.setObjectName("CameraShadowOptIn")
        self._camera_opt_in.setToolTip(_PROCTOR_TEXT[self._language]["details"])
        self._camera_opt_in.setStyleSheet(
            "QCheckBox { color:#53647A; font-size:11px; spacing:8px; }"
        )
        layout.addWidget(self._camera_opt_in)
        camera_note = QtWidgets.QLabel(_PROCTOR_TEXT[self._language]["details"])
        camera_note.setWordWrap(True)
        camera_note.setMinimumWidth(0)
        camera_note.setMaximumWidth(540)
        camera_note.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        camera_note.setStyleSheet("color:#65758A; font-size:10px; padding-left:22px;")
        layout.addWidget(camera_note)
        source_link = QtWidgets.QLabel(
            f'<a style="color:#486A91" href="{SOURCE_URL}">{self._t["official_prep"]}</a>'
            f' · <a style="color:#486A91" href="{FREE_MOCK_URL}">{self._t["free_mock"]}</a>'
        )
        source_link.setOpenExternalLinks(True)
        source_link.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.LinksAccessibleByMouse)
        source_link.setStyleSheet("color:#26725C; font-size:12px;")
        layout.addWidget(source_link)

        local_sources_btn = QtWidgets.QPushButton(self._t["local_sources"])
        local_sources_btn.setObjectName("SecondaryButton")
        local_sources_btn.setMinimumHeight(34)
        local_sources_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        local_sources_btn.clicked.connect(self._open_local_mock_sources)
        layout.addWidget(local_sources_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)

        footer = QtWidgets.QWidget()
        footer.setObjectName("PracticeFooter")
        footer.setStyleSheet(
            "QWidget#PracticeFooter { background:#EDF2F8; border-top:1px solid #D8E1EC; }"
        )
        buttons = QtWidgets.QHBoxLayout(footer)
        buttons.setContentsMargins(22, 11, 22, 14)
        buttons.setSpacing(10)
        self._topic_hint = QtWidgets.QLabel(self._t["topic_count"])
        self._topic_hint.setWordWrap(True)
        self._topic_hint.setStyleSheet("color:#65758A; font-size:11px;")
        self._topic_hint.setMinimumWidth(110)
        buttons.addWidget(self._topic_hint, 1)
        self._mistakes_button = QtWidgets.QPushButton()
        self._mistakes_button.setObjectName("SecondaryButton")
        self._mistakes_button.clicked.connect(self._start_mistake_review)
        self._mistakes_button.setMinimumHeight(40)
        buttons.addWidget(self._mistakes_button)
        start = QtWidgets.QPushButton(self._t["start"])
        self._start_button = start
        start.setObjectName("RunButton")
        start.setMinimumHeight(42)
        start.setMinimumWidth(138)
        start.clicked.connect(self._start)
        buttons.addWidget(start)
        page_layout.addWidget(footer)
        self._stack.addWidget(page)
        self._populate_goal_controls()
        self._update_topic_hint()
        self._update_dashboard_summary()

    def _open_local_mock_sources(self) -> None:
        from aetherlab.ui.reference_sources import ReferenceSourcesDialog

        dialog = ReferenceSourcesDialog(
            parent=self, initial_tab=1, language=self._language
        )
        apply_settings = getattr(self.window(), "_apply_reference_sources_settings", None)
        if callable(apply_settings):
            dialog.settings_changed.connect(apply_settings)
        dialog.exec()

    def _update_topic_hint(self, _index: int = -1) -> None:
        if not hasattr(self, "_topic_hint"):
            return
        snapshot = self.progress_notice.read(self._progress_path, self._language)
        history = aggregate_topic_progress(snapshot.attempts) if snapshot is not None else {}
        topic_id = str(self._topic_combo.currentData() or "")
        if topic_id:
            progress = history.get(topic_id, {"correct": 0, "total": 0, "points": 0, "max_points": 0})
            if progress["total"]:
                self._topic_hint.setText(
                    f"{self._topic_names.get(topic_id, topic_id)} · "
                    + self._t["progress_line"].format(**progress)
                )
            else:
                self._topic_hint.setText(self._t["no_progress"])
        else:
            correct = sum(item["correct"] for item in history.values())
            total = sum(item["total"] for item in history.values())
            if total:
                self._topic_hint.setText(self._t["all_progress_line"].format(correct=correct, total=total))
            else:
                self._topic_hint.setText(self._t["no_progress"])
        is_mock = self._mode_combo.currentData() == "timed"
        questions = (
            mock_questions_for_language(self._language, topic_id or None)
            if is_mock else questions_for_language(self._language, topic_id or None)
        )
        available_levels = {question["difficulty"] for question in questions}
        for index in range(1, self._difficulty_combo.count()):
            self._difficulty_combo.model().item(index).setEnabled(
                self._difficulty_combo.itemData(index) in available_levels
            )
        difficulty = self._difficulty_combo.currentData()
        if difficulty and difficulty not in available_levels:
            self._difficulty_combo.blockSignals(True)
            self._difficulty_combo.setCurrentIndex(0)
            self._difficulty_combo.blockSignals(False)
            difficulty = ""
        count = sum(not difficulty or question["difficulty"] == difficulty for question in questions)
        self._start_button.setEnabled(count > 0)
        count_text = {"kk": "{count} тапсырма", "ru": "{count} заданий", "en": "{count} questions"}[self._language]
        if snapshot is None:
            self._topic_hint.setText(self.progress_notice.copy["unknown"])
        self._topic_hint.setText(self._topic_hint.text() + " · " + count_text.format(count=count))
        if hasattr(self, "_mistakes_button"):
            count = len(snapshot.mistake_ids) if snapshot is not None else 0
            self._mistakes_button.setText(self._t["mistake_review"].format(count=count if snapshot is not None else "—"))
            self._mistakes_button.setEnabled(count > 0 and self.progress_notice.last_read_ok)

    def _populate_goal_controls(self) -> None:
        snapshot = self.progress_notice.read(self._progress_path, self._language)
        for control in (self._target_score, self._weekly_goal, self._weekly_mock_day, self._exam_date, self._prep_level, self._save_plan_button):
            control.setEnabled(snapshot is not None)
        if snapshot is None:
            self._goals_loaded = False
            return
        self._goals_loaded = True
        goals = snapshot.goals
        self._target_score.setValue(int(goals.get("target_score") or 0))
        self._weekly_goal.setValue(int(goals.get("weekly_question_goal") or 0))
        mock_day_index = self._weekly_mock_day.findData(goals.get("weekly_mock_day"))
        self._weekly_mock_day.setCurrentIndex(max(0, mock_day_index))
        exam_date = str(goals.get("exam_date") or "")
        parsed = QtCore.QDate.fromString(exam_date, QtCore.Qt.DateFormat.ISODate)
        self._exam_date.setDate(parsed if parsed.isValid() else self._exam_date.minimumDate())
        level_index = self._prep_level.findData(goals.get("preparation_level", "beginner"))
        self._prep_level.setCurrentIndex(max(0, level_index))

    def _retry_progress(self) -> None:
        self.progress_notice.read(self._progress_path, self._language)
        if not self.progress_notice.last_read_ok:
            return
        if not self._goals_loaded:
            self._populate_goal_controls()
        self._update_dashboard_summary()
        self._update_topic_hint()

    def _save_goals(self) -> None:
        if not self._goals_loaded:
            self._retry_progress()
            return
        selected_date = self._exam_date.date()
        try:
            save_goals(
                self._progress_path,
                {
                    "target_score": int(self._target_score.value()) or None,
                    "exam_date": (
                        selected_date.toString(QtCore.Qt.DateFormat.ISODate)
                        if selected_date > self._exam_date.minimumDate() else ""
                    ),
                    "weekly_question_goal": int(self._weekly_goal.value()) or None,
                    "weekly_mock_day": self._weekly_mock_day.currentData(),
                    "preparation_level": str(self._prep_level.currentData() or "beginner"),
                },
            )
        except (OSError, UnicodeError):
            self._storage_status("goals_error")
            return
        self._storage_status(None)
        self._update_dashboard_summary()
        self._topic_hint.setText(self._t["goals_saved"])

    def _update_dashboard_summary(self) -> None:
        if not hasattr(self, "_dashboard_summary"):
            return
        snapshot = self.progress_notice.read(self._progress_path, self._language)
        if snapshot is None:
            self._dashboard_summary.setText(self.progress_notice.copy["unknown"])
            return
        attempts = snapshot.attempts
        full_attempts = full_mock_history(attempts)
        goals = snapshot.goals
        count = weekly_question_count(attempts)
        goal = goals.get("weekly_question_goal")
        lines = [self._t["dashboard_week"].format(count=count, goal=goal or "—")]
        if goals.get("exam_date"):
            until_exam = (date.fromisoformat(goals["exam_date"]) - date.today()).days
            lines.append(self._t["dashboard_date"].format(days=max(0, until_exam)))
        if full_attempts:
            latest = full_attempts[-1]
            best = max(full_attempts, key=lambda item: int(item.get("score", 0)))
            lines.insert(
                0,
                self._t["dashboard_latest"].format(
                    score=int(latest.get("score", 0)),
                    target=goals.get("target_score") or "—",
                ),
            )
            lines.insert(1, self._t["dashboard_best"].format(score=int(best.get("score", 0))))
        else:
            lines.insert(0, self._t["dashboard_empty"])
        self._dashboard_summary.setText("  ·  ".join(lines))

    def _start_mistake_review(self) -> None:
        snapshot = self.progress_notice.read(self._progress_path, self._language)
        if not self.progress_notice.last_read_ok:
            return
        mistake_ids = set(snapshot.mistake_ids)
        available = {
            question["id"]: question
            for question in (
                *questions_for_language(self._language),
                *mock_questions_for_language(self._language),
            )
        }
        questions = tuple(
            question for question_id, question in available.items()
            if question_id in mistake_ids
        )
        if not questions:
            self._topic_hint.setText(self._t["no_mistakes"])
            self._update_topic_hint()
            return
        if not self._resolve_saved_attempt():
            return
        self._full_mock = False
        self._begin_session(questions, "mistake_review")

    def _practice_weakest_topic(self) -> None:
        if not self._recommended_topic:
            return
        self._topic_combo.setCurrentIndex(self._topic_combo.findData(self._recommended_topic))
        self._mode_combo.setCurrentIndex(self._mode_combo.findData("practice"))
        self._stack.setCurrentIndex(0)
        self._update_topic_hint()

    def _build_session_page(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        top = QtWidgets.QHBoxLayout()
        self._counter = QtWidgets.QLabel("")
        self._counter.setStyleSheet(
            "color:#486A91; background:rgba(75,99,133,0.10); border-radius:10px; "
            "padding:5px 10px; font-size:11px; font-weight:700;"
        )
        top.addWidget(self._counter)
        top.addStretch()
        self._clock = QtWidgets.QLabel("")
        self._clock.setStyleSheet("color: #486A91; font-size: 12px; font-weight: 600;")
        top.addWidget(self._clock)
        self._camera_status = QtWidgets.QLabel("")
        self._camera_status.setWordWrap(True)
        self._camera_status.setStyleSheet(
            "color:#53647A; background:#EDF2F8; border:1px solid #D8E1EC; "
            "border-radius:8px; padding:4px 8px; font-size:10px;"
        )
        self._camera_status.hide()
        top.addWidget(self._camera_status, 1)
        layout.addLayout(top)
        self._camera_preview = QtWidgets.QLabel()
        self._camera_preview.setObjectName("CameraShadowPreview")
        self._camera_preview.setFixedSize(160, 90)
        self._camera_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._camera_preview.setStyleSheet(
            "background:#18283D; border:1px solid #A5B6CB; border-radius:8px;"
        )
        self._camera_preview.hide()
        layout.addWidget(self._camera_preview, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setObjectName("PracticeProgress")
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        layout.addWidget(self._progress_bar)

        self._question_content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self._question_content)
        content_layout.setContentsMargins(4, 4, 4, 8)
        content_layout.setSpacing(8)
        self._topic = QtWidgets.QLabel("")
        self._topic.setStyleSheet(
            "color:#536F90; background:rgba(82,110,145,0.10); border-radius:9px; "
            "padding:5px 9px; font-size:10px; font-weight:700;"
        )
        self._topic.setMaximumWidth(360)
        self._topic.setMaximumHeight(40)
        content_layout.addWidget(self._topic)
        self._context = QtWidgets.QLabel("")
        self._context.setWordWrap(True)
        self._context.setStyleSheet(
            "color:#53647A; padding:14px; border-radius:11px; background:#FFFFFF; "
            "border:1px solid #D8E1EC;"
        )
        content_layout.addWidget(self._context)
        self._prompt = QtWidgets.QLabel("")
        self._prompt.setWordWrap(True)
        self._prompt.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self._prompt.setStyleSheet("font-size:18px; line-height:1.4; color:#18283D; padding:9px 0;")
        content_layout.addWidget(self._prompt)

        self._choices_host = QtWidgets.QWidget()
        self._choices_layout = QtWidgets.QVBoxLayout(self._choices_host)
        self._choices_layout.setContentsMargins(0, 0, 0, 0)
        self._choices_layout.setSpacing(8)
        content_layout.addWidget(self._choices_host)
        self._feedback = QtWidgets.QLabel("")
        self._feedback.setWordWrap(True)
        self._feedback.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self._feedback.setStyleSheet(
            "color:#65758A; padding:14px; border-radius:11px; background:#FFFFFF; "
            "border:1px solid #D8E1EC;"
        )
        content_layout.addWidget(self._feedback)
        self._solution_math = QtWidgets.QWidget()
        self._solution_math_layout = QtWidgets.QVBoxLayout(self._solution_math)
        self._solution_math_layout.setContentsMargins(12, 0, 12, 8)
        self._solution_math_layout.setSpacing(3)
        self._solution_math.hide()
        content_layout.addWidget(self._solution_math)
        content_layout.addStretch(1)
        self._question_scroll = QtWidgets.QScrollArea()
        self._question_scroll.setWidgetResizable(True)
        self._question_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._question_scroll.setStyleSheet("QScrollArea { background:#F4F7FB; border:none; }")
        self._question_scroll.viewport().setStyleSheet("background:#F4F7FB; border:none;")
        self._question_content.setStyleSheet("background:#F4F7FB;")
        self._question_scroll.setWidget(self._question_content)
        layout.addWidget(self._question_scroll, 1)

        buttons = QtWidgets.QHBoxLayout()
        self._back = QtWidgets.QPushButton(self._t["back"])
        self._back.setObjectName("SecondaryButton")
        self._back.clicked.connect(self._previous)
        buttons.addWidget(self._back)
        buttons.addStretch()
        self._check = QtWidgets.QPushButton(self._t["check"])
        self._check.setObjectName("SecondaryButton")
        self._check.clicked.connect(self._check_answer)
        buttons.addWidget(self._check)
        self._next = QtWidgets.QPushButton(self._t["next"])
        self._next.setObjectName("RunButton")
        self._next.clicked.connect(self._next_question)
        buttons.addWidget(self._next)
        self._finish = QtWidgets.QPushButton(self._t["finish"])
        self._finish.setObjectName("RunButton")
        self._finish.clicked.connect(self._request_finish)
        buttons.addWidget(self._finish)
        layout.addLayout(buttons)
        self._stack.addWidget(page)

    def _build_result_page(self) -> None:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(8)
        self._result_title = QtWidgets.QLabel(self._t["result"])
        self._result_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #24364B;")
        layout.addWidget(self._result_title)
        self._score = QtWidgets.QLabel("")
        self._score.setStyleSheet(
            "font-size:17px; color:#486A91; background:rgba(75,99,133,0.08); "
            "border-radius:10px; padding:10px 12px;"
        )
        layout.addWidget(self._score)
        self._result_stats = QtWidgets.QLabel("")
        self._result_stats.setStyleSheet("color:#65758A; font-size:11px;")
        layout.addWidget(self._result_stats)
        self._integrity_summary = QtWidgets.QLabel("")
        self._integrity_summary.setWordWrap(True)
        self._integrity_summary.setStyleSheet(
            "color:#53647A; background:#EDF2F8; border:1px solid #D8E1EC; "
            "border-radius:8px; padding:7px 9px; font-size:10px;"
        )
        self._integrity_summary.hide()
        layout.addWidget(self._integrity_summary)
        self._topic_progress_title = QtWidgets.QLabel(self._t["topic_progress"])
        self._topic_progress_title.setStyleSheet("color:#18283D; font-size:12px; font-weight:700;")
        layout.addWidget(self._topic_progress_title)
        self._topic_progress_view = QtWidgets.QTextBrowser()
        self._topic_progress_view.setOpenExternalLinks(False)
        self._topic_progress_view.setMaximumHeight(170)
        self._topic_progress_view.setStyleSheet(
            "QTextBrowser { background:#FFFFFF; border:1px solid #D8E1EC; "
            "border-radius:10px; padding:5px; color:#53647A; }"
        )
        layout.addWidget(self._topic_progress_view)
        self._review = QtWidgets.QTextBrowser()
        self._review.setObjectName("PracticeReview")
        family = QtWidgets.QApplication.font().family().replace('"', "")
        self._review.setStyleSheet(
            f'QTextBrowser#PracticeReview {{ font-family:"{family}"; font-size:14px; '
            "background:#FFFFFF; color:#18283D; border:1px solid #D8E1EC; "
            "border-radius:10px; padding:8px; }"
        )
        self._review.setOpenExternalLinks(True)
        layout.addWidget(self._review, 1)
        self._recommendation = QtWidgets.QLabel("")
        self._recommendation.setWordWrap(True)
        self._recommendation.setStyleSheet(
            "color:#8A5A24; background:rgba(251,191,36,0.12); border:1px solid #8A5A24; "
            "border-radius:9px; padding:9px 12px;"
        )
        layout.addWidget(self._recommendation)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        self._recommend_button = QtWidgets.QPushButton(self._t["practice_weakest"])
        self._recommend_button.setObjectName("SecondaryButton")
        self._recommend_button.clicked.connect(self._practice_weakest_topic)
        self._recommend_button.hide()
        buttons.addWidget(self._recommend_button)
        self._save_pdf_button = QtWidgets.QPushButton(self._t["save_pdf"])
        self._save_pdf_button.setObjectName("SecondaryButton")
        self._save_pdf_button.clicked.connect(self._save_pdf)
        buttons.addWidget(self._save_pdf_button)
        close = QtWidgets.QPushButton(self._t["close"])
        close.setObjectName("RunButton")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._stack.addWidget(page)

    def _change_language(self, _index: int) -> None:
        if self._stack.currentIndex() != 0:
            return
        state = {
            "topic": self._topic_combo.currentData(),
            "difficulty": self._difficulty_combo.currentData(),
            "mode": self._mode_combo.currentData(),
            "target": self._target_score.value(),
            "weekly": self._weekly_goal.value(),
            "weekly_mock_day": self._weekly_mock_day.currentData(),
            "date": self._exam_date.date(),
            "level": self._prep_level.currentData(),
            "session_size": self._session_size.currentData(),
        }
        self._language = normalize_language(self._language_combo.currentData(), "kk")
        self._topic_names = _TOPIC_NAMES[self._language]
        self.setWindowTitle(self._t["title"])
        self._answer_group = None
        while self._stack.count():
            widget = self._stack.widget(0)
            self._stack.removeWidget(widget)
            if widget is not None:
                widget.deleteLater()
        self._build_start_page()
        self._build_session_page()
        self._build_result_page()
        self._stack.setCurrentIndex(0)
        for combo, key in ((self._topic_combo, "topic"), (self._difficulty_combo, "difficulty"),
                           (self._mode_combo, "mode"), (self._prep_level, "level")):
            combo.setCurrentIndex(max(0, combo.findData(state[key])))
        self._session_size.setCurrentIndex(max(0, self._session_size.findData(state["session_size"])))
        self._target_score.setValue(state["target"])
        self._weekly_goal.setValue(state["weekly"])
        self._weekly_mock_day.setCurrentIndex(
            max(0, self._weekly_mock_day.findData(state["weekly_mock_day"]))
        )
        self._exam_date.setDate(state["date"])
        self._update_topic_hint()

    def _resolve_saved_attempt(self) -> bool:
        """Allow replacement only after the learner resolves an existing attempt."""
        try:
            saved_session = load_active_session(self._progress_path)
        except (OSError, UnicodeError):
            self._storage_status("resume_error")
            return False
        self._storage_status(None)
        if saved_session:
            choice = self._confirm_exam_action("resume")
            if choice == QtWidgets.QMessageBox.StandardButton.Yes:
                if not self._resume_active_session(saved_session):
                    self._storage_status("resume_error")
                return False
            if choice != QtWidgets.QMessageBox.StandardButton.No:
                return False
            try:
                clear_active_session(self._progress_path)
                # Cleanup intentionally tolerates a failed unlink after result
                # commit. Replacement requires confirmed removal instead.
                if load_active_session(self._progress_path) is not None:
                    self._storage_status("restart_error")
                    return False
            except (OSError, UnicodeError):
                self._storage_status("restart_error")
                return False
        return True

    def _start(self) -> None:
        if not self._resolve_saved_attempt():
            return
        self._language = normalize_language(self._language_combo.currentData(), "kk")
        self._mode = str(self._mode_combo.currentData() or "practice")
        topic_filter = str(self._topic_combo.currentData() or "")
        questions = (
            mock_questions_for_language(self._language, topic_filter or None)
            if self._mode == "timed"
            else questions_for_language(self._language, topic_filter or None)
        )
        difficulty = str(self._difficulty_combo.currentData() or "")
        if difficulty:
            questions = tuple(question for question in questions if question["difficulty"] == difficulty)
        if not questions:
            QtWidgets.QMessageBox.information(self, self._t["title"], self._t["no_question_match"])
            return
        if self._mode == "practice":
            count = int(self._session_size.currentData() or 10)
            if len(questions) > count:
                questions = tuple(random.SystemRandom().sample(list(questions), count))
        self._full_mock = (
            self._mode == "timed"
            and not topic_filter
            and not difficulty
            and len(questions) == ENT_TOTAL_QUESTIONS
        )
        self._begin_session(questions, self._mode)

    def _resume_active_session(self, state: dict) -> bool:
        language = str(state.get("language", "kk"))
        mode = str(state.get("mode", "practice"))
        language_index = self._language_combo.findData(language)
        if language_index >= 0 and self._language_combo.currentIndex() != language_index:
            self._language_combo.setCurrentIndex(language_index)
        if mode == "timed":
            bank = mock_questions_for_language(language)
        elif mode == "mistake_review":
            bank = (*questions_for_language(language), *mock_questions_for_language(language))
        else:
            bank = questions_for_language(language)
        by_id = {question["id"]: question for question in bank}
        ids = state.get("question_ids", [])
        if not ids or any(question_id not in by_id for question_id in ids):
            return False
        questions = tuple(by_id[question_id] for question_id in ids)
        self._language = language
        self._topic_names = _TOPIC_NAMES[language]
        self._mode_combo.setCurrentIndex(max(0, self._mode_combo.findData("timed" if mode == "timed" else "practice")))
        self._full_mock = bool(state.get("full_mock"))
        self._camera_opt_in.setChecked(bool(state.get("proctor_enabled")))
        self._begin_session(
            questions,
            mode,
            answers=state.get("answers"),
            index=int(state.get("index", 0)),
            seconds_left=int(state.get("seconds_left", 0)),
            proctor_enabled=bool(state.get("proctor_enabled")),
            proctor_events=list(state.get("proctor_events", [])),
            attempt_id=str(state.get("attempt_id", "")),
            completion_pending=bool(state.get("completion_pending")),
        )
        return True

    def _begin_session(
        self,
        questions: tuple[dict, ...],
        mode: str,
        *,
        answers: list[tuple[int, ...] | None] | None = None,
        index: int = 0,
        seconds_left: int | None = None,
        proctor_enabled: bool | None = None,
        proctor_events: list[dict] | None = None,
        attempt_id: str = "",
        completion_pending: bool = False,
    ) -> None:
        self._timer.stop()
        self._stop_camera_monitor()
        self._session_finished = False
        self._completion_pending = completion_pending
        self._attempt_id = attempt_id or str(uuid4())
        self._storage_status(None)
        self._choices_host.setEnabled(not completion_pending)
        self._finish.setText(self._t["finish"])
        self._back.setEnabled(True)
        self._next.setEnabled(True)
        self._check.setEnabled(True)
        self._mode = mode
        self._questions = tuple(questions)
        self._answers = list(answers) if answers is not None and len(answers) == len(questions) else [None] * len(self._questions)
        self._checked.clear()
        self._index = max(0, min(index, len(self._questions) - 1))
        duration = (
            ENT_FULL_MOCK_DURATION_S
            if self._full_mock
            else max(1, len(self._questions)) * 2 * 60
        )
        self._seconds_left = max(0, min(duration, int(seconds_left))) if seconds_left is not None else duration
        self._deadline_monotonic = time.monotonic() + self._seconds_left if mode == "timed" else None
        self._session_started_at = time.monotonic() - max(0, duration - self._seconds_left)
        self._proctor_enabled = (
            bool(self._camera_opt_in.isChecked() and self._full_mock)
            if proctor_enabled is None
            else bool(proctor_enabled and self._full_mock)
        )
        from aetherlab.services.proctoring import ShadowEventTracker

        self._proctor = ShadowEventTracker()
        self._proctor.events = list(proctor_events or [])[:100]
        self._render_question()
        self._stack.setCurrentIndex(1)
        if self._completion_pending:
            self._show_results()
            return
        if self._proctor_enabled:
            self._start_camera_monitor()
        if self._mode == "timed":
            if self._seconds_left <= 0:
                self._finish_session()
                return
            self._timer.start()

    def _persist_active_session(self) -> bool:
        if not self._questions or self._session_finished:
            return True
        self._capture_current_answer()
        if self._mode == "timed" and self._deadline_monotonic is not None:
            self._seconds_left = max(0, int(self._deadline_monotonic - time.monotonic() + 0.999))
        try:
            saved = save_active_session(
                self._progress_path,
                {
                    "question_ids": [question["id"] for question in self._questions],
                    "answers": self._answers,
                    "index": self._index,
                    "seconds_left": self._seconds_left,
                    "mode": self._mode,
                    "language": self._language,
                    "full_mock": self._full_mock,
                    "proctor_enabled": self._proctor_enabled,
                    "proctor_events": self._proctor.snapshot(),
                    "attempt_id": self._attempt_id,
                    "completion_pending": self._completion_pending,
                },
            )
        except (OSError, UnicodeError):
            self._storage_status("session_error")
            return False
        if not saved and self._progress_path is not None:
            self._storage_status("session_error")
            return False
        if self._storage_notice.text() == self._storage_text["session_error"]:
            self._storage_status(None)
        return True

    def _start_camera_monitor(self) -> None:
        from aetherlab.ui.camera_monitor import CameraMonitorThread

        self._camera_status.setText(_PROCTOR_TEXT[self._language]["active"])
        self._camera_status.show()
        self._camera_worker = CameraMonitorThread(self)
        self._camera_worker.face_count.connect(self._on_camera_face_count)
        self._camera_worker.status.connect(self._on_camera_status)
        self._camera_worker.preview.connect(self._on_camera_preview)
        self._camera_worker.start()

    def _stop_camera_monitor(self) -> None:
        worker = self._camera_worker
        self._camera_worker = None
        if worker is not None:
            worker.stop()
        if hasattr(self, "_camera_preview"):
            self._camera_preview.clear()
            self._camera_preview.hide()

    def _on_camera_preview(self, image) -> None:
        if image is None or image.isNull():
            return
        self._camera_preview.setPixmap(
            QtGui.QPixmap.fromImage(image).scaled(
                self._camera_preview.size(),
                QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._camera_preview.show()

    def _on_camera_status(self, status: str) -> None:
        if status == "active":
            self._camera_status.setText(_PROCTOR_TEXT[self._language]["active"])
        elif status == "lost":
            self._camera_status.setText(_PROCTOR_TEXT[self._language]["lost"])
            self._proctor.note_camera_lost()
            self._persist_active_session()
        else:
            self._camera_status.setText(_PROCTOR_TEXT[self._language]["unavailable"])
            self._camera_preview.hide()
        self._camera_status.show()

    def _on_camera_face_count(self, count: int) -> None:
        events = self._proctor.observe_face_count(count, now=time.monotonic())
        if events:
            self._persist_active_session()

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt virtual override
        super().changeEvent(event)
        if (
            event.type() == QtCore.QEvent.Type.WindowDeactivate
            and hasattr(self, "_stack")
            and self._proctor_enabled
            and not self._session_finished
            and self._stack.currentIndex() == 1
        ):
            self._proctor.note_focus_loss()
            self._persist_active_session()

    def _render_question(self) -> None:
        question = self._questions[self._index]
        total = len(self._questions)
        self._counter.setText(f"{self._index + 1} / {total}")
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(self._index + 1)
        self._question_scroll.verticalScrollBar().setValue(0)
        self._clock.setText(self._format_time() if self._mode == "timed" else "")
        self._topic.setText(self._topic_names.get(question["topic"], question["topic"]))
        self._prompt.setText(question["prompt"])
        if question["context"]:
            self._context.setText(f"{self._t['context']}: {question['context']}")
            self._context.show()
        else:
            self._context.clear()
            self._context.hide()
        while self._choices_layout.count():
            item = self._choices_layout.takeAt(0)
            if item.widget():
                old_widget = item.widget()
                old_widget.hide()
                old_widget.deleteLater()
        self._answer_widgets.clear()
        if self._answer_group is not None:
            self._answer_group.deleteLater()
        self._answer_group = QtWidgets.QButtonGroup(self._choices_host)
        self._answer_group.setExclusive(True)
        saved = self._answers[self._index]
        kind = question["kind"]
        if kind == "matching":
            label = QtWidgets.QLabel(self._t["match"])
            label.setStyleSheet("color: #65758A; font-size: 12px;")
            self._choices_layout.addWidget(label)
            for row, left_text in enumerate(question["matching_left"]):
                row_widget = QtWidgets.QFrame()
                row_widget.setObjectName("PracticeAnswerOption")
                row_widget.setStyleSheet(
                    "QFrame#PracticeAnswerOption { background:#FFFFFF; border:1px solid #D8E1EC; "
                    "border-radius:10px; }"
                )
                row_layout = QtWidgets.QHBoxLayout(row_widget)
                row_layout.setContentsMargins(12, 7, 12, 7)
                left = QtWidgets.QLabel(left_text)
                left.setWordWrap(True)
                row_layout.addWidget(left, 1)
                combo = QtWidgets.QComboBox()
                combo.addItem(self._t["select_match"], -1)
                for option_index, option in enumerate(question["choices"]):
                    combo.addItem(option, option_index)
                if saved is not None and row < len(saved) and 0 <= saved[row] < len(question["choices"]):
                    combo.setCurrentIndex(saved[row] + 1)
                row_layout.addWidget(combo, 1)
                self._choices_layout.addWidget(row_widget)
                self._answer_widgets.append(combo)
        else:
            hint_key = "select_all" if kind == "multi" else "format_single"
            hint = QtWidgets.QLabel(self._t[hint_key])
            hint.setStyleSheet("color: #65758A; font-size: 12px;")
            self._choices_layout.addWidget(hint)
            for option_index, option in enumerate(question["choices"]):
                option_row = QtWidgets.QFrame()
                option_row.setObjectName("PracticeAnswerOption")
                option_row.setStyleSheet(
                    "QFrame#PracticeAnswerOption { background:#FFFFFF; border:1px solid #D8E1EC; "
                    "border-radius:10px; } QFrame#PracticeAnswerOption:hover { border-color:#A5B6CB; }"
                )
                option_layout = QtWidgets.QHBoxLayout(option_row)
                option_layout.setContentsMargins(12, 7, 12, 7)
                if kind == "multi":
                    control = QtWidgets.QCheckBox(option)
                    control.setChecked(saved is not None and option_index in saved)
                else:
                    control = QtWidgets.QRadioButton(option)
                    self._answer_group.addButton(control, option_index)
                    control.setChecked(saved is not None and option_index in saved)
                control.setStyleSheet("font-size:14px; padding:3px;")
                option_layout.addWidget(control)
                self._choices_layout.addWidget(option_row)
                self._answer_widgets.append(control)
        checked = self._index in self._checked
        for control in self._answer_widgets:
            control.setEnabled(not checked)
        if checked:
            self._show_feedback(question)
        else:
            self._feedback.clear()
            self._feedback.hide()
            self._clear_solution_math()
            self._feedback.setStyleSheet(
                "color: #65758A; padding: 10px; border-radius: 8px; background: #FFFFFF;"
            )
        self._back.setEnabled(self._index > 0)
        self._check.setVisible(self._mode != "timed" and not checked)
        self._next.setVisible(self._index < total - 1)
        self._finish.setVisible(True)
        self._persist_active_session()

    def _read_answer(self) -> tuple[int, ...] | None:
        question = self._questions[self._index]
        if question["kind"] == "matching":
            selected = tuple(int(widget.currentData()) for widget in self._answer_widgets)
            return selected if any(index >= 0 for index in selected) else None
        if question["kind"] == "multi":
            selected = tuple(index for index, widget in enumerate(self._answer_widgets) if widget.isChecked())
            return selected or None
        selected = next((index for index, widget in enumerate(self._answer_widgets) if widget.isChecked()), None)
        return (selected,) if selected is not None else None

    @staticmethod
    def _is_complete(answer: tuple[int, ...] | None) -> bool:
        return answer is not None and bool(answer) and all(index >= 0 for index in answer)

    def _capture_current_answer(self) -> None:
        """Replace an editable response, including a deliberately cleared one."""
        if (not self._questions or self._session_finished or self._completion_pending
                or self._index in self._checked or not hasattr(self, "_answer_widgets")):
            return
        self._answers[self._index] = self._read_answer()

    @staticmethod
    def _is_correct(answer: tuple[int, ...] | None, question: dict) -> bool:
        return answer is not None and answer == tuple(question["correct_indices"])

    def _format_answer(self, answer: tuple[int, ...] | None, question: dict) -> str:
        if answer is None:
            return self._t["not_answered"]
        if question["kind"] == "matching":
            pairs = []
            for row, left in enumerate(question["matching_left"]):
                choice_index = answer[row] if row < len(answer) else -1
                right = question["choices"][choice_index] if 0 <= choice_index < len(question["choices"]) else "—"
                pairs.append(f"{left} → {right}")
            return "; ".join(pairs)
        selected = [question["choices"][index] for index in answer if 0 <= index < len(question["choices"])]
        return ", ".join(selected) if selected else self._t["not_answered"]

    def _check_answer(self) -> None:
        if self._completion_pending or self._session_finished or self._index in self._checked:
            return
        self._capture_current_answer()
        selected = self._read_answer()
        if not self._is_complete(selected):
            self._feedback.setText(self._t["choose"])
            self._feedback.show()
            return
        self._answers[self._index] = selected
        self._checked.add(self._index)
        for control in self._answer_widgets:
            control.setEnabled(False)
        self._show_feedback(self._questions[self._index])
        self._check.hide()

    def _show_feedback(self, question: dict) -> None:
        self._feedback.show()
        selected = self._answers[self._index]
        correct = self._is_correct(selected, question)
        title = self._t["right"] if correct else self._t["wrong"]
        points = score_question(selected, question)
        maximum = question_max_points(question)
        answer = question["answer"]
        term = question["kazakh_term"]
        meaning = next(
            (item["meaning"] for item in glossary_for_language(self._language)
             if item["term_kk"] == term),
            "",
        )
        self._feedback.setText(
            f"{title} {self._t['points_feedback'].format(score=points, possible=maximum)}\n"
            f"{self._t['correct']}: {answer}\n\n{readable_explanation(question, self._language)}\n\n"
            f"{self._t['term']}: {term}. {meaning}"
        )
        self._feedback.setStyleSheet(
            "color:#26725C; padding:14px; border-radius:11px; background:#E8F3ED; "
            "border:1px solid #C9DFD0;"
            if correct else
            "color:#8A5A24; padding:14px; border-radius:11px; background:rgba(251,191,36,0.12); "
            "border:1px solid #D7B77A;"
        )

        self._clear_solution_math()
        from aetherlab.services.mathtext import render_math

        for expression in question.get("solution_latex", ()):
            formula = str(expression).strip()
            if not formula:
                continue
            pixmap = render_math(formula, px_size=20, color="#18283D")
            equation = QtWidgets.QLabel()
            if pixmap is not None:
                equation.setPixmap(pixmap)
            else:
                equation.setText(self._readable_solution_formula(formula))
                equation.setStyleSheet("font-family:Cambria Math,serif; font-size:16px; color:#18283D;")
            self._solution_math_layout.addWidget(equation)
        self._solution_math.setVisible(bool(question.get("solution_latex")))

    def _clear_solution_math(self) -> None:
        if not hasattr(self, "_solution_math_layout"):
            return
        while self._solution_math_layout.count():
            item = self._solution_math_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._solution_math.hide()

    def _previous(self) -> None:
        if self._completion_pending:
            return
        self._capture_current_answer()
        if self._index > 0:
            self._index -= 1
            self._render_question()

    def _next_question(self) -> None:
        if self._completion_pending:
            return
        self._capture_current_answer()
        if self._index < len(self._questions) - 1:
            self._index += 1
            self._render_question()

    def _request_finish(self) -> None:
        if self._completion_pending or self._mode != "timed":
            self._finish_session()
            return
        choice = self._confirm_exam_action("finish")
        if choice == QtWidgets.QMessageBox.StandardButton.Yes:
            self._finish_session()

    def _confirm_exam_action(self, action: str) -> QtWidgets.QMessageBox.StandardButton:
        text = _PROCTOR_TEXT[self._language]
        buttons = QtWidgets.QMessageBox.StandardButton
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        box.setWindowTitle(text["resume_title"] if action == "resume" else self._t["title"])
        box.setText(text[f"{action}_prompt"])
        box.setStandardButtons(buttons.Yes | buttons.No | (buttons.Cancel if action == "resume" else buttons.NoButton))
        box.button(buttons.Yes).setText(text[f"{action}_yes"])
        box.button(buttons.No).setText(text[f"{action}_no"])
        if action == "resume":
            box.button(buttons.Cancel).setText(text["cancel"])
            box.setEscapeButton(buttons.Cancel)
            box.setDefaultButton(buttons.Yes)
        else:
            box.setEscapeButton(buttons.No)
            box.setDefaultButton(buttons.No)
        result = box.exec()
        box.deleteLater()
        # Closing a resume prompt must never act as Start again.
        return buttons(result) if result else (buttons.Cancel if action == "resume" else buttons.No)

    def _readable_solution_formula(self, formula: str) -> str:
        try:
            return readable_formula(formula)
        except ValueError:
            return _PROCTOR_TEXT[self._language]["math_unavailable"]

    def _finish_session(self) -> None:
        if self._session_finished:
            return
        self._capture_current_answer()
        self._timer.stop()
        self._stop_camera_monitor()
        self._show_results()

    def _tick(self) -> None:
        if self._deadline_monotonic is not None:
            self._seconds_left = max(0, int(self._deadline_monotonic - time.monotonic() + 0.999))
        else:
            self._seconds_left = max(0, self._seconds_left - 1)
        self._clock.setText(self._format_time())
        if self._seconds_left <= 0:
            self._finish_session()
        elif self._seconds_left % 10 == 0:
            self._persist_active_session()

    def _format_time(self) -> str:
        minutes, seconds = divmod(max(0, self._seconds_left), 60)
        return f"{self._t['time']}: {minutes:02d}:{seconds:02d}"

    def _show_results(self) -> None:
        if self._session_finished:
            return
        self._timer.stop()
        self._stop_camera_monitor()
        self._completion_pending = True
        self._choices_host.setEnabled(False)
        self._back.setEnabled(False)
        self._next.setEnabled(False)
        self._check.setEnabled(False)
        self._finish.setText(self._storage_text["retry_result"])
        # A completed snapshot must be durable before the history commit:
        # cleanup can fail or the process can exit between the two writes.
        if not self._persist_active_session():
            self._storage_status("result_error")
            return
        scored_pairs = self._scored_pairs()
        score = sum(score_question(answer, question) for answer, question in scored_pairs)
        possible_points = sum(question_max_points(question) for _, question in scored_pairs)
        attempted_pairs = [(answer, question) for answer, question in scored_pairs if answer is not None]
        question_results = {
            question["id"]: self._is_correct(answer, question)
            for answer, question in attempted_pairs
        }
        topic_results: dict[str, dict[str, int]] = {}
        for answer, question in attempted_pairs:
            stat = topic_results.setdefault(
                question["topic"],
                {"correct": 0, "total": 0, "points": 0, "max_points": 0},
            )
            stat["total"] += 1
            stat["correct"] += int(self._is_correct(answer, question))
            stat["points"] += score_question(answer, question)
            stat["max_points"] += question_max_points(question)
        try:
            attempts = record_attempt(
                self._progress_path,
                language=self._language,
                topic_results=topic_results,
                question_results=question_results,
                score=score,
                possible_points=possible_points,
                mode=self._mode,
                full_mock=(
                    self._full_mock
                    and len(self._questions) == ENT_TOTAL_QUESTIONS
                    and possible_points == ENT_MAX_POINTS
                ),
                integrity_events=self._proctor.snapshot() if self._proctor_enabled else None,
                proctor_enabled=self._proctor_enabled,
                attempt_id=self._attempt_id,
            )
        except (OSError, UnicodeError):
            self._storage_status("result_error")
            return
        self._session_finished = True
        self._completion_pending = False
        self._storage_status(None)
        clear_active_session(self._progress_path)
        self._current_topic_progress = aggregate_topic_progress(attempts)
        self._score.setText(
            f"{self._t['score']}: "
            + self._t["score_result"].format(
                score=score, possible=possible_points, questions=len(scored_pairs)
            )
        )
        correct_count = sum(question_results.values())
        elapsed = max(0, int(time.monotonic() - self._session_started_at))
        elapsed_minutes, elapsed_seconds = divmod(elapsed, 60)
        self._result_stats.setText(
            self._t["result_stats"].format(
                correct=correct_count,
                incorrect=len(question_results) - correct_count,
                unanswered=len(self._questions) - len(attempted_pairs),
                elapsed=f"{elapsed_minutes:02d}:{elapsed_seconds:02d}",
            )
        )
        if self._proctor_enabled and self._proctor.events:
            event_names = _PROCTOR_TEXT[self._language]["event_names"]
            names = [event_names.get(event["type"], event["type"]) for event in self._proctor.snapshot()]
            self._integrity_summary.setText(
                _PROCTOR_TEXT[self._language]["events"].format(events="; ".join(names))
            )
            self._integrity_summary.show()
        else:
            self._integrity_summary.hide()
        self._topic_progress_title.setText(self._t["topic_progress"])
        progress_rows = []
        for topic_id in ENT_TOPIC_IDS:
            stat = self._current_topic_progress.get(
                topic_id, {"correct": 0, "total": 0, "points": 0, "max_points": 0}
            )
            current = topic_results.get(
                topic_id, {"correct": 0, "total": 0, "points": 0, "max_points": 0}
            )
            total, correct = stat["total"], stat["correct"]
            filled = round(6 * correct / total) if total else 0
            bar = "█" * filled + "░" * (6 - filled)
            ratio = f"{correct}/{total}" if total else "—"
            session_ratio = f"{current['correct']}/{current['total']}" if current["total"] else ""
            point_ratio = f"{stat['points']}/{stat['max_points']}" if stat["max_points"] else "—"
            progress_rows.append(
                f"<tr><td>{escape(self._topic_names[topic_id])}</td>"
                f"<td style='color:#486A91;font-family:monospace;font-size:9pt'>{bar}</td>"
                f"<td>{ratio}{(' · ' + session_ratio) if session_ratio else ''}</td>"
                f"<td>{point_ratio}</td></tr>"
            )
        self._topic_progress_view.setHtml(
            "<table cellspacing='0' cellpadding='2'>"
            f"<tr><th>{escape(self._t['topic_col'])}</th>"
            f"<th>{escape(self._t['mastery_col'])}</th>"
            f"<th>{escape(self._t['correct_total_col'])}</th>"
            f"<th>{escape(self._t['points_col'])}</th></tr>"
            + "".join(progress_rows)
            + "</table>"
        )

        practiced_topics = [
            (stat["correct"] / stat["total"], topic_id, stat)
            for topic_id, stat in topic_results.items() if stat["total"]
        ]
        if practiced_topics:
            _accuracy, self._recommended_topic, weakest = min(practiced_topics)
            all_correct = weakest["correct"] == weakest["total"]
            self._recommend_button.setText(self._t["practice_more" if all_correct else "practice_weakest"])
            self._recommendation.setText(
                self._t["success_recommendation" if all_correct else "recommendation"].format(
                    topic=self._topic_names.get(self._recommended_topic, self._recommended_topic),
                    correct=weakest["correct"],
                    total=weakest["total"],
                )
            )
            self._recommend_button.show()
        else:
            self._recommended_topic = ""
            self._recommendation.clear()
            self._recommend_button.hide()

        # A new owned document drops images from the previous attempt and keeps
        # resources scoped to this result, never to a global or filesystem URL.
        document = QtGui.QTextDocument(self._review)
        document.setDefaultFont(self._review.font())
        from aetherlab.services.mathtext import render_math

        blocks = [f"<h3>{self._t['key']}</h3>"]
        for index, (answer, question) in enumerate(zip(self._answers, self._questions), 1):
            selected = self._format_answer(answer, question)
            earned = score_question(answer, question)
            maximum = question_max_points(question)
            prompt = escape(question["prompt"])
            if question["context"]:
                context = escape(f"{self._t['context']}: {question['context']}")
                prompt = f"{context}<br><b>{prompt}</b>"
            meaning = next(
                (item["meaning"] for item in glossary_for_language(self._language)
                 if item["term_kk"] == question["kazakh_term"]),
                "",
            )
            points = self._t["points_feedback"].format(score=earned, possible=maximum)
            if self._mode == "practice" and answer is None:
                points = self._t["not_counted"]
            blocks.append(
                f"<p><b>{index}.</b> {prompt}<br>"
                f"{escape(self._t['your_answer'])}: {escape(selected)}<br>"
                f"{escape(self._t['correct'])}: {escape(question['answer'])}<br>"
                f"{escape(points)}<br>{escape(readable_explanation(question, self._language))}<br>"
                f"{escape(self._t['term'])}: {escape(question['kazakh_term'])} — {escape(meaning)}</p>"
            )
            for equation_index, formula in enumerate(question.get("solution_latex", ())):
                formula = str(formula).strip()
                if not formula:
                    continue
                pixmap = render_math(formula, px_size=20, color="#18283D")
                if pixmap is None:
                    blocks.append(f"<p>{escape(self._readable_solution_formula(formula))}</p>")
                    continue
                url = QtCore.QUrl(f"physlab-review-equation:{self._attempt_id}-{index}-{equation_index}")
                document.addResource(QtGui.QTextDocument.ResourceType.ImageResource, url, pixmap.toImage())
                size = pixmap.deviceIndependentSize()
                blocks.append(
                    f"<p><img src='{url.toString()}' width='{max(1, round(size.width()))}' "
                    f"height='{max(1, round(size.height()))}' /></p>"
                )
        self._review.setDocument(document)
        self._review.setHtml("".join(blocks))
        self._update_dashboard_summary()
        self._update_topic_hint()
        self._stack.setCurrentIndex(2)

    def _scored_pairs(self) -> list[tuple]:
        pairs = list(zip(self._answers, self._questions))
        return [(answer, question) for answer, question in pairs if answer is not None] if self._mode == "practice" else pairs

    def _save_pdf(self) -> None:
        if not self._questions:
            return
        default_name = f"PhysLab_ENT_Physics_{self._language}.pdf"
        path, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self._t["save_pdf_title"],
            str(Path.home() / default_name),
            self._t["pdf_filter"],
        )
        if not path:
            return
        output_path = Path(path)
        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")
        meanings = {
            item["term_kk"]: item["meaning"]
            for item in glossary_for_language(self._language)
        }
        export_questions = tuple(
            {**question, "term_meaning": meanings.get(question["kazakh_term"], "")}
            for question in self._questions
        )
        scored_pairs = self._scored_pairs()
        score = sum(
            score_question(answer, question)
            for answer, question in scored_pairs
        )
        possible_points = sum(question_max_points(question) for _, question in scored_pairs)
        try:
            from aetherlab.services.ent_practice_pdf import export_practice_pdf

            export_practice_pdf(
                output_path,
                language=self._language,
                questions=export_questions,
                user_answers=[
                    self._format_answer(answer, question)
                    for answer, question in zip(self._answers, self._questions)
                ],
                topic_names={topic: self._topic_names[topic] for topic in ENT_TOPIC_IDS},
                topic_progress=self._current_topic_progress,
                score=score,
                possible_points=possible_points,
                scored_question_count=len(scored_pairs),
                question_counted=[self._mode != "practice" or answer is not None for answer in self._answers],
                question_points=[
                    score_question(answer, question)
                    for answer, question in zip(self._answers, self._questions)
                ],
            )
        except Exception as exc:  # noqa: BLE001 — keep an optional export failure in the UI
            QtWidgets.QMessageBox.warning(
                self,
                self._t["save_pdf_title"],
                self._t["pdf_error"].format(error=str(exc)[:300]),
            )
            return
        QtWidgets.QMessageBox.information(
            self,
            self._t["save_pdf_title"],
            self._t["pdf_saved"].format(path=output_path),
        )
