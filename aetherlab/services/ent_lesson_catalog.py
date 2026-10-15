"""Small source-grounded lesson packages for Kazakhstan ENT physics.

These lessons deliberately bypass free-form lesson authoring: wording, worked
values, and the answer key are fixed before a lesson is rendered in any
language. Local textbook/test citations are retained on the chapter cards.
"""

from __future__ import annotations

import re

from aetherlab.core.language import normalize_language
from aetherlab.core.models import LessonChapter, LessonPlan, LessonQuestion

ACCELERATED_MOTION_ID = "constant_acceleration"
ACCELERATED_MOTION_VERSION = "physlab-ent-constant-acceleration-v1"

# Stage O: the v2 5-minute lesson (8 prebuilt cloud-rendered blocks B0–B7 +
# 45-cue subtitles + study PDF + H1–H5 practice). A distinct topic id keeps its
# course-progress key separate from the v1 route, so existing answers are
# never re-attributed to the new question list.
ACCELERATED_MOTION_5MIN_ID = "constant_acceleration_5min"
ACCELERATED_MOTION_5MIN_VERSION = "physlab-ent-constant-acceleration-5min-v2"
ACCELERATED_MOTION_5MIN_REVIEW = {
    "content_version": "v2",
    "physics_calculation": "checked_by_deterministic_calculation",
    "teacher_translation_review": "pending",
}

BOOK_CITATION = (
    "Н.А. Закирова, «Физика», 10 класс, ЖМ направление, §3, PDF с. 15–18; "
    "задачи: PDF с. 20."
)
QUESTION_CITATION = (
    "НЦТ, «Ұлттық тестілеу орталығының нұсқалық тест жинақтары-3», "
    "задание 1: PDF с. 2; ключ: PDF с. 37. Переводы kk/ru/en — черновые."
)
SPECIFICATION_CITATION = (
    "Спецификация НЦТ по физике для ЕНТ, применяется с 2026 года: "
    "https://testcenter.kz/wp-content/uploads/2025/10/12_%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0_%D1%80%D1%83%D1%81.pdf"
)


_TEXT = {
    "kk": {
        "title": "Тұрақты үдеумен түзу сызықты қозғалыс",
        "topic": "Бірқалыпты үдемелі қозғалыс",
        "prerequisites": [
            "Жылдамдық қашықтықтың уақытқа қатынасы екенін білу.",
            "Секунд пен метр/секунд бірліктерін тану.",
        ],
        "objectives": [
            "Үдеуді жылдамдықтың әр секундтағы өзгерісі арқылы түсіндіру.",
            "Тұрақты үдеу формуласымен жылдамдық пен орын ауыстыруды есептеу.",
            "Жылдамдық–уақыт графигінен жүрілген жолды табу.",
        ],
        "misconception": (
            "Үдеу жылдамдықтың өзіне тең емес. Үдеу жылдамдықтың уақыт өткенде "
            "қалай өзгеретінін көрсетеді."
        ),
        "terms": [
            {
                "term_kk": "үдеу",
                "translation": "ускорение; acceleration",
                "meaning": "Жылдамдықтың әр секундта қаншаға өзгеретінін көрсетеді.",
            },
            {
                "term_kk": "бастапқы жылдамдық",
                "translation": "начальная скорость; initial velocity",
                "meaning": "Қозғалыс басталған сәттегі жылдамдық.",
            },
            {
                "term_kk": "орын ауыстыру",
                "translation": "перемещение; displacement",
                "meaning": "Дененің бастапқы орнынан соңғы орнына дейінгі бағытталған өзгеріс.",
            },
        ],
        "chapters": [
            {
                "id": "hook",
                "title": "Велосипед неліктен жылдамдайды?",
                "goal": "Үдеуді таныс қозғалыс арқылы сезіну.",
                "beats": [
                    "Велосипед орнынан қозғалып, жылдамдығын арттырады.",
                    "Бір секундта жылдамдыққа бірдей шама қосылса, үдеу тұрақты болады.",
                ],
                "narration": (
                    "Велосипедті педальмен жылдамдатқанда, ол әр секунд сайын жылдамырақ жүреді. "
                    "Үдеу — жылдамдықтың бір секундта қаншаға өзгергенін көрсететін шама. "
                    "Қазір жылдамдықтың өзгерісін және жүрілген жолды қарапайым мысалмен табамыз."
                ),
                "key_equations": [],
                "key_symbols": [],
                "citation_query": "жылдамдық пен үдеу, тұрақты үдеулі қозғалыс",
                "citations": [BOOK_CITATION],
                "visual": "dot_accelerates_on_road",
            },
            {
                "id": "velocity",
                "title": "Үдеу және жылдамдық",
                "goal": "Үдеу, бастапқы жылдамдық және уақытты байланыстыру.",
                "beats": [
                    "Бір өлшемді түзу сызықты осьті таңдау.",
                    "Әр секундтағы бірдей жылдамдық өзгерісін a деп белгілеу.",
                    "Соңғы жылдамдық v = v₀ + at формуласымен табылады.",
                ],
                "narration": (
                    "Бір түзу бойымен қозғалған дененің бастапқы жылдамдығын v нөл, ал уақытты t деп белгілейік. "
                    "Үдеу a әр секундтағы жылдамдық өзгерісін өлшейді. "
                    "Үдеу тұрақты болса, t секундтан кейінгі жылдамдық v = v нөл + a көбейту t болады."
                ),
                "key_equations": [r"v = v_0 + at", r"a = (v - v_0)/t"],
                "key_symbols": [
                    "v₀: бастапқы жылдамдық, м/с",
                    "v: t уақыттан кейінгі жылдамдық, м/с",
                    "a: үдеу, м/с²",
                    "t: уақыт, с",
                ],
                "citation_query": "§3, PDF с. 15–16, үдеу және лездік жылдамдық",
                "citations": [BOOK_CITATION],
                "visual": "velocity_ticks_and_equation",
            },
            {
                "id": "displacement",
                "title": "Жылдамдық қалай жолға айналады?",
                "goal": "Тұрақты үдеудегі орын ауыстыру формуласын түсіну.",
                "beats": [
                    "v–t графигінде жүрген жол график астындағы ауданмен байланысады.",
                    "Тұрақты үдеуде орын ауыстыру s = v₀t + at²/2 болады.",
                    "Тек жылдамдық бағыты өзгермейтін аралықта жол мен орын ауыстыру модулі тең.",
                ],
                "narration": (
                    "Жылдамдық–уақыт графигіндегі талдау дененің жүрген жолын көрсетеді. "
                    "Тұрақты үдеуде бастапқы жылдамдықтан келген бөлікке үдеу тудыратын бөлік қосылады: "
                    "s = v нөл t + a t квадрат бөлінген екі. "
                    "Бұл таңбалы орын ауыстыру; қозғалыс кері бұрылмаса, оның модулі жүрген жолға тең."
                ),
                "key_equations": [r"s = v_0t + at^2/2", r"s = (v_0 + v)t/2"],
                "key_symbols": [
                    "s: таңдалған ось бойындағы орын ауыстыру, м",
                    "v₀: бастапқы жылдамдық, м/с",
                    "a: тұрақты үдеудің проекциясы, м/с²",
                    "t: уақыт, с",
                ],
                "citation_query": "§3, PDF с. 16–18, орын ауыстыру формуласы және v–t графигі",
                "citations": [BOOK_CITATION],
                "visual": "velocity_time_graph_area",
            },
            {
                "id": "worked-example",
                "title": "Бірге есептейік",
                "goal": "Формулаларды бірізді қолданып, нәтижені тексеру.",
                "beats": [
                    "Берілгені: v₀ = 2 м/с, a = 1,5 м/с², t = 4 с.",
                    "v = 2 + 1,5·4 = 8 м/с.",
                    "s = 2·4 + 1,5·4²/2 = 20 м.",
                    "Орташа жылдамдық 5 м/с; 5·4 = 20 м.",
                ],
                "narration": (
                    "Велосипедші 2 метр/секунд жылдамдықпен қозғалады, ал үдеуі 1,5 метр/секунд квадрат. "
                    "Төрт секундтан кейін жылдамдық 2 + 1,5 көбейту 4, яғни 8 метр/секунд. "
                    "Орын ауыстыру 2 көбейту 4 + 1,5 көбейту 4 квадрат бөлінген 2, яғни 20 метр. "
                    "Тексеру: орташа жылдамдық 5 метр/секунд; төрт секундтағы жол да 20 метр."
                ),
                "key_equations": [
                    r"v = 2 + 1.5\cdot 4 = 8\,\mathrm{m/s}",
                    r"s = 2\cdot 4 + (1.5\cdot 4^2)/2 = 20\,\mathrm{m}",
                    r"s = ((2+8)/2)\cdot 4 = 20\,\mathrm{m}",
                ],
                "key_symbols": [
                    "v₀ = 2 м/с",
                    "a = 1,5 м/с²",
                    "t = 4 с",
                    "v = 8 м/с",
                    "s = 20 м",
                ],
                "citation_query": "§3, PDF с. 16, үдеу тұрақты кездегі жылдамдық және орын ауыстыру",
                "citations": [BOOK_CITATION],
                "visual": "worked_values_and_units",
            },
            {
                "id": "ent-question",
                "title": "ЕНТ тапсырмасы: графиктен жолды тап",
                "goal": "НЦТ жинағындағы график тапсырмасын шешіп, ауданмен тексеру.",
                "beats": [
                    "Ресми жинақтағы 1-тапсырмада v–t графигі 0–4 с аралығын көрсетеді.",
                    "Нүктелер: (0 с, 0 м/с), (1 с, 4 м/с), (3 с, 4 м/с), (4 с, 0 м/с).",
                    "График астын екі үшбұрыш пен тік төртбұрышқа бөліп, аудандарын қосу.",
                    "Түпнұсқа жауап кестесінде 1-тапсырманың жауабы B.",
                ],
                "narration": (
                    "Ұлттық тестілеу орталығының үшінші нұсқалық жинағындағы тапсырманы қарайық. "
                    "Нөлден бір секундқа дейінгі үшбұрыш ауданы 2 метр. "
                    "Бірден үш секундқа дейінгі тіктөртбұрыш ауданы 8 метр, ал соңғы үшбұрыш тағы 2 метр. "
                    "Барлығы 12 метр. Жинақтың жауап кестесі де B жауабын көрсетеді."
                ),
                "key_equations": [
                    r"s = (1\cdot 4)/2 + (3-1)\cdot 4 + (4-3)\cdot 4/2",
                    r"s = 2 + 8 + 2 = 12\,\mathrm{m}",
                ],
                "key_symbols": [
                    "графиктің тік осі: жылдамдық, м/с",
                    "графиктің көлденең осі: уақыт, с",
                    "график астындағы аудан: жүрген жол, м",
                ],
                "citation_query": "НЦТ нұсқалық тест жинағы 3, PDF с. 2, 37",
                "citations": [QUESTION_CITATION, SPECIFICATION_CITATION],
                "visual": "official_question_vt_graph",
            },
            {
                "id": "recap",
                "title": "Есте сақта",
                "goal": "Үдеудің мағынасын және үш тексеру қадамын бекіту.",
                "beats": [
                    "Бірқалыпты үдемелі қозғалыста үдеу тұрақты.",
                    "Белгілерді жаз; шамаларды SI бірліктеріне ауыстыр; формуланы және график ауданын тексер.",
                ],
                "narration": (
                    "Есте сақта: тұрақты үдеу жылдамдықты әр секундта бірдей шамаға өзгертеді. "
                    "Есепте алдымен белгілі шамаларды және олардың бірліктерін жаз. "
                    "Содан соң лайықты формуланы таңда да, жауабыңды графикпен немесе бірліктермен тексер."
                ),
                "key_equations": [r"v = v_0 + at", r"s = v_0t + at^2/2"],
                "key_symbols": [],
                "citation_query": "§3, PDF с. 15–18",
                "citations": [BOOK_CITATION],
                "visual": "three_step_recap",
            },
        ],
        "question": {
            "q": "Суретте материалдық нүктенің жылдамдық–уақыт графигі берілген. 4 с-тағы жүрген жолды табыңыз.",
            "choices": ["A) 13 м", "B) 12 м", "C) 9 м", "D) 15 м"],
            "answer": "B) 12 м",
            "why": (
                "Жол график астындағы аудандар қосындысына тең: 2 м + 8 м + 2 м = 12 м. "
                "Түпнұсқадағы жауап кестесі, PDF с. 37, B нұсқасын растайды."
            ),
        },
        # Stage H practice: H1 mirrors bank item kinematics-velocity-01
        # (equality enforced by tests/test_lesson_practice_h.py); H2–H5 are
        # original lesson items. kk/ru/en wording is draft, teacher review pending.
        "practice": [
            {
                "q": "Дене 2 м/с бастапқы жылдамдықпен қозғалады. Оның үдеуі 3 м/с². 4 секундтан кейінгі жылдамдығын табыңыз.",
                "choices": ["A) 14 м/с", "B) 12 м/с", "C) 9 м/с", "D) 6 м/с"],
                "answer": "A) 14 м/с",
                "why": "Үдеу жылдамдықты әр секунд сайын 3 м/с-қа арттырады. Сондықтан v = v₀ + at = 2 + 3·4 = 14 м/с.",
            },
            {
                "q": "Дене 2 м/с бастапқы жылдамдықпен, 3 м/с² үдеумен қозғалады. Бағыты өзгермесе, 4 с-тағы орын ауыстыруын табыңыз.",
                "choices": ["A) 32 м", "B) 56 м", "C) 24 м", "D) 20 м"],
                "answer": "A) 32 м",
                "why": "s = v₀t + at²/2 = 2·4 + 3·16/2 = 8 + 24 = 32 м. 56 м жауабы соңғы жылдамдықты бірқалыпты қозғалыс формуласына қойғанда шығады.",
            },
            {
                "q": "Қандай қозғалыс теңүдемелі деп аталады?",
                "choices": ["A) Жылдамдық тең уақыт аралықтарында бірдей шамаға өзгереді", "B) Жылдамдық тұрақты", "C) Үдеу уақыт өте келе өзгереді", "D) Тең уақыт аралықтарында жол бірдей"],
                "answer": "A) Жылдамдық тең уақыт аралықтарында бірдей шамаға өзгереді",
                "why": "Теңүдемелі қозғалыста жылдамдық тең уақытта бірдей шамаға артады, үдеу тұрақты (Закирова 9, §3). D нұсқасы бірқалыпты қозғалысты сипаттайды.",
            },
            {
                "q": "Жылдамдықтың уақытқа тәуелділік графигіндегі түзудің көлбеуі нені көрсетеді?",
                "choices": ["A) Үдеуді", "B) Орын ауыстыруды", "C) Жылдамдықты", "D) Уақытты"],
                "answer": "A) Үдеуді",
                "why": "v(t) графигінің көлбеуі үдеуге тең: a = Δv/Δt. Орын ауыстыру — график астындағы аудан (Закирова 10, §3).",
            },
            {
                "q": "v(t) графигінде түзу (0 с; 2 м/с) нүктесінен (4 с; 14 м/с) нүктесіне барады. Орын ауыстыруды табыңыз.",
                "choices": ["A) 32 м", "B) 48 м", "C) 56 м", "D) 24 м"],
                "answer": "A) 32 м",
                "why": "Трапеция ауданы: (2 + 14)/2 · 4 = 32 м. 24 м — тіктөртбұрышсыз тек үшбұрыштың ауданы.",
            },
        ],
    },
    "ru": {
        "title": "Прямолинейное движение с постоянным ускорением",
        "topic": "Равноускоренное движение",
        "prerequisites": [
            "Помнить, что скорость связана с пройденным расстоянием и временем.",
            "Знать единицы секунд и метров в секунду.",
        ],
        "objectives": [
            "Объяснить ускорение через изменение скорости за каждую секунду.",
            "Вычислить скорость и перемещение при постоянном ускорении.",
            "Найти путь по графику скорости от времени.",
        ],
        "misconception": (
            "Ускорение не равно самой скорости. Оно показывает, как скорость меняется со временем."
        ),
        "terms": [
            {"term_kk": "үдеу", "translation": "ускорение", "meaning": "Изменение скорости за единицу времени."},
            {"term_kk": "бастапқы жылдамдық", "translation": "начальная скорость", "meaning": "Скорость тела в начале рассматриваемого движения."},
            {"term_kk": "орын ауыстыру", "translation": "перемещение", "meaning": "Изменение положения тела с учётом направления."},
        ],
        "chapters": [
            {
                "id": "hook", "title": "Почему велосипед разгоняется?",
                "goal": "Почувствовать смысл ускорения на знакомом движении.",
                "beats": ["Велосипед начинает движение и увеличивает скорость.", "Если за каждую секунду скорость изменяется одинаково, ускорение постоянно."],
                "narration": "Когда велосипедист крутит педали, велосипед за каждую секунду едет быстрее. Ускорение показывает, на сколько меняется скорость за секунду. Сейчас на простом примере найдём изменение скорости и пройденный путь.",
                "key_equations": [], "key_symbols": [], "citation_query": "скорость, ускорение и равноускоренное движение",
                "citations": [BOOK_CITATION], "visual": "dot_accelerates_on_road",
            },
            {
                "id": "velocity", "title": "Ускорение и скорость",
                "goal": "Связать ускорение, начальную скорость и время.",
                "beats": ["Выбираем прямую ось для движения.", "Обозначаем одинаковое изменение скорости за секунду через a.", "Скорость через время t: v = v₀ + at."],
                "narration": "Рассмотрим тело, движущееся вдоль прямой. Начальную скорость обозначим v нулём, а время — t. Ускорение a показывает изменение скорости за одну секунду. При постоянном ускорении через t секунд скорость равна v ноль плюс a умножить на t.",
                "key_equations": [r"v = v_0 + at", r"a = (v - v_0)/t"],
                "key_symbols": ["v₀: начальная скорость, м/с", "v: скорость через время t, м/с", "a: ускорение, м/с²", "t: время, с"],
                "citation_query": "§3, PDF с. 15–16: ускорение и мгновенная скорость", "citations": [BOOK_CITATION], "visual": "velocity_ticks_and_equation",
            },
            {
                "id": "displacement", "title": "Как скорость связана с путём?",
                "goal": "Понять формулу перемещения при постоянном ускорении.",
                "beats": ["Путь связан с площадью под графиком v–t.", "При постоянном ускорении s = v₀t + at²/2.", "Модуль перемещения равен пути, если направление движения не меняется."],
                "narration": "На графике скорости от времени пройденный путь связан с площадью под графиком. При постоянном ускорении перемещение равно v ноль умножить на t плюс a умножить на t в квадрате, делённое на два. Это проекция перемещения; если тело не меняет направление, её модуль равен пути.",
                "key_equations": [r"s = v_0t + at^2/2", r"s = (v_0 + v)t/2"],
                "key_symbols": ["s: проекция перемещения, м", "v₀: начальная скорость, м/с", "a: проекция постоянного ускорения, м/с²", "t: время, с"],
                "citation_query": "§3, PDF с. 16–18: перемещение и график v–t", "citations": [BOOK_CITATION], "visual": "velocity_time_graph_area",
            },
            {
                "id": "worked-example", "title": "Решим вместе",
                "goal": "Последовательно применить формулы и проверить результат.",
                "beats": ["Дано: v₀ = 2 м/с, a = 1,5 м/с², t = 4 с.", "v = 2 + 1,5·4 = 8 м/с.", "s = 2·4 + 1,5·4²/2 = 20 м.", "Средняя скорость 5 м/с; за 4 с это 20 м."],
                "narration": "Велосипед движется со скоростью 2 метра в секунду, а его ускорение равно 1,5 метра в секунду за секунду. Через четыре секунды скорость составит 2 плюс 1,5 умножить на 4, то есть 8 метров в секунду. Перемещение равно 2 умножить на 4 плюс 1,5 умножить на 4 в квадрате, делённое на 2: получаем 20 метров. Проверка: средняя скорость 5 метров в секунду, за четыре секунды это те же 20 метров.",
                "key_equations": [r"v = 2 + 1.5\cdot 4 = 8\,\mathrm{m/s}", r"s = 2\cdot 4 + (1.5\cdot 4^2)/2 = 20\,\mathrm{m}", r"s = ((2+8)/2)\cdot 4 = 20\,\mathrm{m}"],
                "key_symbols": ["v₀ = 2 м/с", "a = 1,5 м/с²", "t = 4 с", "v = 8 м/с", "s = 20 м"],
                "citation_query": "§3, PDF с. 16: скорость и перемещение при постоянном ускорении", "citations": [BOOK_CITATION], "visual": "worked_values_and_units",
            },
            {
                "id": "ent-question", "title": "Задание ЕНТ: путь по графику",
                "goal": "Решить задание из сборника НЦТ и проверить ответ по площади.",
                "beats": ["В задании 1 сборника НЦТ дан график v–t от 0 до 4 с.", "Точки графика: (0 с, 0 м/с), (1 с, 4 м/с), (3 с, 4 м/с), (4 с, 0 м/с).", "Разбиваем площадь под графиком на два треугольника и прямоугольник.", "В таблице ответов оригинала для задания 1 указан вариант B."],
                "narration": "Разберём задание из третьего сборника вариантов Национального центра тестирования. Площадь первого треугольника равна 2 метрам. Площадь прямоугольника от первой до третьей секунды — 8 метров. Последний треугольник даёт ещё 2 метра. Всего 12 метров. Таблица ответов сборника также указывает вариант B.",
                "key_equations": [r"s = (1\cdot 4)/2 + (3-1)\cdot 4 + (4-3)\cdot 4/2", r"s = 2 + 8 + 2 = 12\,\mathrm{m}"],
                "key_symbols": ["вертикальная ось: скорость, м/с", "горизонтальная ось: время, с", "площадь под графиком: путь, м"],
                "citation_query": "сборник вариантов теста НЦТ №3, PDF с. 2 и 37", "citations": [QUESTION_CITATION, SPECIFICATION_CITATION], "visual": "official_question_vt_graph",
            },
            {
                "id": "recap", "title": "Главное",
                "goal": "Закрепить смысл ускорения и три шага проверки.",
                "beats": ["При равноускоренном движении ускорение постоянно.", "Запиши величины; проверь единицы СИ; сравни решение с формулой и площадью графика."],
                "narration": "Запомни: при постоянном ускорении скорость за каждую секунду изменяется одинаково. Сначала выпиши известные величины и единицы. Затем выбери формулу и проверь ответ по графику или единицам измерения.",
                "key_equations": [r"v = v_0 + at", r"s = v_0t + at^2/2"], "key_symbols": [],
                "citation_query": "§3, PDF с. 15–18", "citations": [BOOK_CITATION], "visual": "three_step_recap",
            },
        ],
        "question": {
            "q": "На рисунке показан график скорости материальной точки. Найдите путь за 4 с.",
            "choices": ["A) 13 м", "B) 12 м", "C) 9 м", "D) 15 м"],
            "answer": "B) 12 м",
            "why": "Путь равен сумме площадей под графиком: 2 м + 8 м + 2 м = 12 м. В таблице ответов оригинала (PDF с. 37) указан вариант B.",
        },
        # Stage H practice: H1 mirrors bank item kinematics-velocity-01
        # (equality enforced by tests/test_lesson_practice_h.py); H2–H5 are
        # original lesson items. kk/ru/en wording is draft, teacher review pending.
        "practice": [
            {
                "q": "Тело движется с начальной скоростью 2 м/с и ускорением 3 м/с². Найдите скорость через 4 секунды.",
                "choices": ["A) 14 м/с", "B) 12 м/с", "C) 9 м/с", "D) 6 м/с"],
                "answer": "A) 14 м/с",
                "why": "Ускорение каждую секунду увеличивает скорость на 3 м/с. Поэтому v = v₀ + at = 2 + 3·4 = 14 м/с.",
            },
            {
                "q": "Тело движется с начальной скоростью 2 м/с и ускорением 3 м/с². Найдите перемещение за 4 с. Направление движения не меняется.",
                "choices": ["A) 32 м", "B) 56 м", "C) 24 м", "D) 20 м"],
                "answer": "A) 32 м",
                "why": "s = v₀t + at²/2 = 2·4 + 3·16/2 = 8 + 24 = 32 м. Вариант 56 м получается, если подставить конечную скорость в формулу равномерного движения.",
            },
            {
                "q": "Какое движение называется равноускоренным?",
                "choices": ["A) Скорость за равные промежутки времени меняется одинаково", "B) Скорость постоянна", "C) Ускорение меняется со временем", "D) Путь за равные промежутки времени одинаков"],
                "answer": "A) Скорость за равные промежутки времени меняется одинаково",
                "why": "Равноускоренное движение — скорость получает равные прибавки за равные времена при постоянном ускорении (Закирова 9, §3). Вариант D описывает равномерное движение.",
            },
            {
                "q": "Что показывает наклон прямой на графике скорости от времени?",
                "choices": ["A) Ускорение", "B) Перемещение", "C) Скорость", "D) Время"],
                "answer": "A) Ускорение",
                "why": "Наклон v(t) равен ускорению: a = Δv/Δt. Перемещение — это площадь под графиком, а не наклон (Закирова 10, §3).",
            },
            {
                "q": "На графике v(t) прямая идёт от точки (0 с; 2 м/с) до точки (4 с; 14 м/с). Найдите перемещение.",
                "choices": ["A) 32 м", "B) 48 м", "C) 56 м", "D) 24 м"],
                "answer": "A) 32 м",
                "why": "Площадь трапеции: (2 + 14)/2 · 4 = 32 м. Вариант 24 м — только треугольник без прямоугольника.",
            },
        ],
    },
    "en": {
        "title": "Straight-line motion with constant acceleration",
        "topic": "Uniformly accelerated motion",
        "prerequisites": [
            "Know that speed relates distance to time.",
            "Recognize seconds and metres per second.",
        ],
        "objectives": [
            "Explain acceleration as the change in velocity each second.",
            "Find velocity and displacement for constant acceleration.",
            "Find distance from a velocity–time graph.",
        ],
        "misconception": "Acceleration is not the velocity itself. It describes how velocity changes over time.",
        "terms": [
            {"term_kk": "үдеу", "translation": "acceleration", "meaning": "How much velocity changes in each unit of time."},
            {"term_kk": "бастапқы жылдамдық", "translation": "initial velocity", "meaning": "The velocity at the start of the motion being studied."},
            {"term_kk": "орын ауыстыру", "translation": "displacement", "meaning": "The change from starting to ending position, including direction."},
        ],
        "chapters": [
            {
                "id": "hook", "title": "Why does a bicycle speed up?",
                "goal": "Build an intuitive feel for acceleration using familiar motion.",
                "beats": ["A bicycle starts moving and gains speed.", "If its velocity changes by the same amount each second, its acceleration is constant."],
                "narration": "When a cyclist pedals harder, the bicycle travels faster each second. Acceleration tells us how much velocity changes in one second. We will use a simple example to find the change in velocity and the distance travelled.",
                "key_equations": [], "key_symbols": [], "citation_query": "velocity, acceleration, and motion at constant acceleration", "citations": [BOOK_CITATION], "visual": "dot_accelerates_on_road",
            },
            {
                "id": "velocity", "title": "Acceleration and velocity",
                "goal": "Connect acceleration, initial velocity, and time.",
                "beats": ["Choose a straight axis for the motion.", "Call the equal velocity change per second a.", "After time t, v = v₀ + at."],
                "narration": "Consider an object moving along a straight line. We call its starting velocity v nought and the time t. Acceleration a measures how much velocity changes each second. With constant acceleration, the velocity after t seconds is v nought plus a times t.",
                "key_equations": [r"v = v_0 + at", r"a = (v - v_0)/t"],
                "key_symbols": ["v₀: initial velocity, m/s", "v: velocity after time t, m/s", "a: acceleration, m/s²", "t: time, s"], "citation_query": "§3, PDF pp. 15–16: acceleration and instantaneous velocity", "citations": [BOOK_CITATION], "visual": "velocity_ticks_and_equation",
            },
            {
                "id": "displacement", "title": "How does velocity build distance?",
                "goal": "Understand the displacement equation for constant acceleration.",
                "beats": ["Distance relates to the area under a v–t graph.", "For constant acceleration, s = v₀t + at²/2.", "Displacement magnitude equals distance while direction does not reverse."],
                "narration": "On a velocity–time graph, distance travelled relates to the area underneath the graph. With constant acceleration, displacement is v nought times t plus a times t squared divided by two. This is signed displacement; its magnitude equals distance if the object does not reverse direction.",
                "key_equations": [r"s = v_0t + at^2/2", r"s = (v_0 + v)t/2"],
                "key_symbols": ["s: displacement along the chosen axis, m", "v₀: initial velocity, m/s", "a: constant acceleration component, m/s²", "t: time, s"], "citation_query": "§3, PDF pp. 16–18: displacement and the v–t graph", "citations": [BOOK_CITATION], "visual": "velocity_time_graph_area",
            },
            {
                "id": "worked-example", "title": "Let’s work it out",
                "goal": "Apply the equations step by step and check the result.",
                "beats": ["Given: v₀ = 2 m/s, a = 1.5 m/s², t = 4 s.", "v = 2 + 1.5·4 = 8 m/s.", "s = 2·4 + 1.5·4²/2 = 20 m.", "Average velocity is 5 m/s; over 4 s that gives 20 m."],
                "narration": "A cyclist moves at 2 metres per second and accelerates at 1.5 metres per second squared. After four seconds, the velocity is 2 plus 1.5 times 4: that is 8 metres per second. The displacement is 2 times 4 plus 1.5 times 4 squared, divided by 2: that is 20 metres. Check: the average velocity is 5 metres per second, so in four seconds the cyclist travels 20 metres.",
                "key_equations": [r"v = 2 + 1.5\cdot 4 = 8\,\mathrm{m/s}", r"s = 2\cdot 4 + (1.5\cdot 4^2)/2 = 20\,\mathrm{m}", r"s = ((2+8)/2)\cdot 4 = 20\,\mathrm{m}"],
                "key_symbols": ["v₀ = 2 m/s", "a = 1.5 m/s²", "t = 4 s", "v = 8 m/s", "s = 20 m"], "citation_query": "§3, PDF p. 16: velocity and displacement at constant acceleration", "citations": [BOOK_CITATION], "visual": "worked_values_and_units",
            },
            {
                "id": "ent-question", "title": "UNT task: find distance from a graph",
                "goal": "Solve a task in an NCT collection and verify the key using area.",
                "beats": ["Task 1 in the NCT collection shows a v–t graph from 0 to 4 s.", "Graph points: (0 s, 0 m/s), (1 s, 4 m/s), (3 s, 4 m/s), (4 s, 0 m/s).", "Split the area below the graph into two triangles and a rectangle.", "The original answer table gives B for task 1."],
                "narration": "Let’s solve task 1 from the National Testing Center’s third variant collection. The first triangle has an area of 2 metres. The rectangle from one to three seconds has an area of 8 metres. The last triangle adds another 2 metres. The total is 12 metres. The collection’s answer table also marks choice B.",
                "key_equations": [r"s = (1\cdot 4)/2 + (3-1)\cdot 4 + (4-3)\cdot 4/2", r"s = 2 + 8 + 2 = 12\,\mathrm{m}"],
                "key_symbols": ["vertical axis: velocity, m/s", "horizontal axis: time, s", "area under graph: distance, m"], "citation_query": "NCT test collection no. 3, PDF pp. 2 and 37", "citations": [QUESTION_CITATION, SPECIFICATION_CITATION], "visual": "official_question_vt_graph",
            },
            {
                "id": "recap", "title": "Remember",
                "goal": "Recall what acceleration means and use three checking steps.",
                "beats": ["In uniformly accelerated motion, acceleration stays constant.", "List values; check SI units; verify with the equation and graph area."],
                "narration": "Remember: with constant acceleration, velocity changes by the same amount every second. First write down the known values and units. Then choose an equation and check the answer using the graph or the units.",
                "key_equations": [r"v = v_0 + at", r"s = v_0t + at^2/2"], "key_symbols": [], "citation_query": "§3, PDF pp. 15–18", "citations": [BOOK_CITATION], "visual": "three_step_recap",
            },
        ],
        "question": {
            "q": "The velocity–time graph of a material point is shown. Find the distance travelled in 4 s.",
            "choices": ["A) 13 m", "B) 12 m", "C) 9 m", "D) 15 m"],
            "answer": "B) 12 m",
            "why": "Distance is the sum of the areas under the graph: 2 m + 8 m + 2 m = 12 m. The original answer table (PDF p. 37) confirms choice B.",
        },
        # Stage H practice: H1 mirrors bank item kinematics-velocity-01
        # (equality enforced by tests/test_lesson_practice_h.py); H2–H5 are
        # original lesson items. kk/ru/en wording is draft, teacher review pending.
        "practice": [
            {
                "q": "An object starts at 2 m/s and accelerates at 3 m/s². What is its speed after 4 seconds?",
                "choices": ["A) 14 m/s", "B) 12 m/s", "C) 9 m/s", "D) 6 m/s"],
                "answer": "A) 14 m/s",
                "why": "Acceleration adds 3 m/s of speed each second. So v = v₀ + at = 2 + 3·4 = 14 m/s.",
            },
            {
                "q": "An object moves with initial speed 2 m/s and acceleration 3 m/s² without changing direction. Find its displacement in 4 s.",
                "choices": ["A) 32 m", "B) 56 m", "C) 24 m", "D) 20 m"],
                "answer": "A) 32 m",
                "why": "s = v₀t + at²/2 = 2·4 + 3·16/2 = 8 + 24 = 32 m. 56 m comes from plugging the final speed into the uniform-motion formula.",
            },
            {
                "q": "Which motion is called uniformly accelerated?",
                "choices": ["A) Velocity changes by equal amounts in equal times", "B) Velocity stays constant", "C) Acceleration changes over time", "D) Distance is the same in equal times"],
                "answer": "A) Velocity changes by equal amounts in equal times",
                "why": "In uniformly accelerated motion velocity gains equal increments in equal times while acceleration stays constant (Zakirova 9, §3). D describes uniform motion.",
            },
            {
                "q": "What does the slope of the line on a velocity–time graph show?",
                "choices": ["A) Acceleration", "B) Displacement", "C) Velocity", "D) Time"],
                "answer": "A) Acceleration",
                "why": "The slope of v(t) equals acceleration: a = Δv/Δt. Displacement is the area under the graph, not the slope (Zakirova 10, §3).",
            },
            {
                "q": "On a v(t) graph a straight line runs from (0 s; 2 m/s) to (4 s; 14 m/s). Find the displacement.",
                "choices": ["A) 32 m", "B) 48 m", "C) 56 m", "D) 24 m"],
                "answer": "A) 32 m",
                "why": "Trapezoid area: (2 + 14)/2 · 4 = 32 m. 24 m is the triangle alone, without the rectangle.",
            },
        ],
    },
}


def _is_accelerated_motion_topic(topic: str) -> bool:
    value = re.sub(r"[^a-zа-яәіңғүұқөһё]+", " ", str(topic or "").casefold())
    aliases = (
        "constant acceleration",
        "uniformly accelerated",
        "uniformly accelerating",
        "accelerated motion",
        "constant acceleration",
        "равноускор",
        "равноперем",
        "теңүдем",
        "тең үдем",
        "бірқалыпты үдемелі",
        "бірқалыпты айнымалы қозғалыс",
        "constant_acceleration",
    )
    return any(alias in value for alias in aliases)


def accelerated_motion_plan(language: str = "ru") -> LessonPlan:
    """Return one hand-authored lesson plan in the requested language."""
    lang = normalize_language(language, "ru")
    content = _TEXT[lang]
    chapters = [
        LessonChapter(
            id=chapter["id"],
            title=chapter["title"],
            goal=chapter["goal"],
            kind="recap" if chapter["id"] == "recap" else "scene",
            beats=list(chapter["beats"]),
            narration=chapter["narration"],
            key_equations=list(chapter["key_equations"]),
            citation_query=chapter["citation_query"],
            citations=list(chapter["citations"]),
            key_symbols=list(chapter["key_symbols"]),
        )
        for chapter in content["chapters"]
    ]
    return LessonPlan(
        title=content["title"],
        topic=content["topic"],
        audience="high_school",
        prerequisites=list(content["prerequisites"]),
        objectives=list(content["objectives"]),
        misconception=content["misconception"],
        chapters=chapters,
        questions=[
            LessonQuestion(**content["question"]),
            # Stage H: the NCT anchor stays first; lesson practice follows.
            *(LessonQuestion(**item) for item in content.get("practice", [])),
        ],
        model_name=ACCELERATED_MOTION_VERSION,
        language=lang,
        kazakh_terms=[dict(item) for item in content["terms"]],
    )


def curated_ent_lesson(topic: str, language: str = "ru") -> LessonPlan | None:
    """Resolve an explicit accelerated-motion topic alias to the curated route.

    Every free-text alias resolves to the v2 5-minute lesson; only the exact
    legacy id still resolves to v1, so existing records and saved progress
    keep working.
    """
    raw = str(topic or "").strip().casefold()
    normalized = raw.replace("-", " ").replace("_", " ")
    if raw == ACCELERATED_MOTION_5MIN_ID or normalized == "constant acceleration 5min":
        return accelerated_motion_5min_plan(language)
    if raw == ACCELERATED_MOTION_ID:
        return accelerated_motion_plan(language)
    if not _is_accelerated_motion_topic(topic):
        return None
    return accelerated_motion_5min_plan(language)


def route_content(language: str = "ru") -> dict:
    """Serializable plan plus the visual cue key used by the media builder."""
    plan = accelerated_motion_plan(language)
    lang = plan.language
    entries = _TEXT[lang]
    return {
        "route_id": ACCELERATED_MOTION_ID,
        "version": ACCELERATED_MOTION_VERSION,
        "language": lang,
        "review_status": {
            "physics_calculation": "checked_by_deterministic_calculation",
            "nct_source_key": "matched_original_answer_table",
            "kazakh_terms_and_translations": "needs_teacher_review",
        },
        "sources": {
            "textbook": {
                "title": "Физика Закирова 10 ЖМ.pdf",
                "pdf_pages_1based": [15, 16, 17, 18, 20],
                "role": "theory_and_original_textbook_exercises",
                "sha256_prefix": "cc39b02f972aff31dfca",
            },
            "nct_question": {
                "title": "Testcenter -3.pdf",
                "pdf_question_page_1based": 2,
                "pdf_answer_key_page_1based": 37,
                "question_number": 1,
                "source_answer": "B",
                "sha256_prefix": "966d33a26005cb58b7cb",
                "edition_note": "Local NCT variant collection; not a complete 2026 mock.",
            },
            "current_ent_specification": {
                "url": "https://testcenter.kz/wp-content/uploads/2025/10/12_%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0_%D1%80%D1%83%D1%81.pdf",
                "applies_from": 2026,
                "role": "current topic and test-format reference",
            },
        },
        "content": plan.to_json(),
        "video_visuals": [
            {
                "chapter_id": chapter["id"],
                "visual": chapter["visual"],
                "narration": chapter["narration"],
                "beats": list(chapter["beats"]),
            }
            for chapter in entries["chapters"]
        ],
        "answer_key": {
            "id": "nct3-question-1",
            "choice_id": "B",
            "answer": plan.questions[0].answer if plan.questions else "B) 12 m",
            "check": "2 m + 8 m + 2 m = 12 m",
            "teacher_translation_review": "pending",
        },
        # These points and the answer decomposition were transcribed from the
        # inspected original NCT question page and checked against its key.
        # PDF, video and voiceover builders consume this one record.
        "verified_question_visual": {
            "source_pdf_page_1based": 2,
            "answer_key_pdf_page_1based": 37,
            "graph_points_time_s_velocity_mps": [[0, 0], [1, 4], [3, 4], [4, 0]],
            "area_segments_m": [2, 8, 2],
            "answer_m": 12,
            "choice_id": "B",
        },
        "common_mistakes": {
            "kk": [
                "Үдеуді жылдамдықтың өзі деп қабылдама: үдеу жылдамдықтың уақыт ішінде қанша өзгеретінін көрсетеді.",
                "s = v₀t + at²/2 формуласын тек үдеу тұрақты болғанда қолдан; s таңдалған ось бойындағы орын ауыстыру.",
                "График есебінде t = 4 с кезіндегі жылдамдықты жол деп алма: жол график астындағы ауданнан табылады.",
            ],
            "ru": [
                "Не путай ускорение со скоростью: ускорение показывает изменение скорости за время.",
                "Применяй s = v₀t + at²/2 при постоянном ускорении; s — перемещение вдоль выбранной оси.",
                "В задаче по графику не принимай скорость при t = 4 с за путь: путь равен площади под графиком.",
            ],
            "en": [
                "Do not treat acceleration as velocity: acceleration describes how velocity changes over time.",
                "Use s = v₀t + at²/2 for constant acceleration; s is displacement along the chosen axis.",
                "For the graph question, do not use the velocity at t = 4 s as the distance: distance is the area under the graph.",
            ],
        }[lang],
    }


# Stage O: trilingual cards for the v2 5-minute lesson. Chapter narrations are
# the canonical Stage F voiceovers verbatim (output/stage_f_content/canonical.json
# v2); block titles for kk/en are new translations, teacher review pending.
# Practice mirrors output/stage_h_practice/practice.json exactly — no NCT anchor
# question here (the v2 lesson checks v=14/s=32, not the NCT graph task).
_TEXT_5MIN = {
    "kk": {
        "title": "Тұрақты үдеумен қозғалыс — 5 минуттық сабақ",
        "topic": ACCELERATED_MOTION_5MIN_ID,
        "prerequisites": [
            "Жылдамдық қашықтықтың уақытқа қатынасы екенін білу.",
            "Секунд пен метр/секунд бірліктерін тану.",
        ],
        "objectives": [
            "Үдеуді жылдамдықтың әр секундтағы өзгерісі арқылы түсіндіру.",
            "Тұрақты үдеу формуласымен жылдамдық пен орын ауыстыруды есептеу.",
            "Жылдамдық–уақыт графигінен жүрілген жолды табу.",
        ],
        "misconception": (
            "Үдеу жылдамдықтың өзіне тең емес. Үдеу жылдамдықтың уақыт өткенде "
            "қалай өзгеретінін көрсетеді."
        ),
        "chapters": [
            {
                "id": "B0", "title": "Ілмек және мақсат",
                "goal": "Сабақ сұрағын қою: машина 4 с-та қанша метр жүреді?",
                "beats": [
                    "Машина 2 м/с-тан 14 м/с-қа дейін 4 с-та үдейді.",
                    "Сабақ соңында жауапты екі тәсілмен табасың.",
                ],
                "narration": "Мәшине секундына екі метр жылдамдықпен келе жатыр және бірқалыпты үдейді. Төрт секундтан кейін жылдамдық он төрт метр секундқа жетеді. Ол қанша метр жүрді? Сабақ соңында жауапты екі тәсілмен табасың.",
                "key_equations": [], "key_symbols": [],
                "citation_query": "§3, PDF с. 15–18", "citations": [BOOK_CITATION],
            },
            {
                "id": "B1", "title": "«Теңүдемелі» деген не",
                "goal": "«Теңүдемелі» ұғымын енгізу: әр секундтағы өсім бірдей.",
                "beats": [
                    "Бірқалыпты қозғалыс: v = s / t.",
                    "Бізде әр секундта +3 м/с — бұл a = 3 м/с².",
                    "Ox осін қозғалыс бағытымен бағыттаймыз.",
                ],
                "narration": "Егер жылдамдық өзгермесе — қозғалыс бірқалыпты: v тең s бөлінген t. Бізде жылдамдық өседі — бірақ әр секундта бірдей шамаға өседі. Әр секундта жылдамдық секундына үш метрге артады — бұл үдеудің үшке тең екенін білдіреді. Мұндай қозғалыс теңүдемелі деп аталады. Жылдамдықтың өсу шапшаңдығын үдеу көрсетеді: a тең жылдамдық өзгерісін уақытқа бөлгенге. Өлшем бірлігі — метр секундына квадрат. Икс осін қозғалыс бағытымен бағыттаймыз: алға бағытталғанның бәрі плюс таңбасымен.",
                "key_equations": [r"a = \Delta v / \Delta t"],
                "key_symbols": ["a = 3 м/с²", "[a] = м/с²"],
                "citation_query": "§3, PDF с. 15–16: үдеу", "citations": [BOOK_CITATION],
            },
            {
                "id": "B2", "title": "Жылдамдық v = v0 + at",
                "goal": "v = v0 + at формуласын қолданып 14 м/с-ты алу.",
                "beats": [
                    "Жылдамдық = бастапқы + өсімше (a·t).",
                    "2 + 3·4 = 14 м/с.",
                    "Бірліктерді тексер: м/с² · с = м/с.",
                ],
                "narration": "Кез келген сәттегі жылдамдық — бастапқы жылдамдық пен өсімшенің қосындысы. Өсімше — үдеу мен уақыттың көбейтіндісі: v тең v нөл плюс a t. Сандарды қоямыз: екі плюс үш көбейту төрт — секундына он төрт метр. Бірліктерді тексер: метр секундына квадратты секундқа көбейткенде метр секунд шығады. Бәрі сәйкес.",
                "key_equations": [r"v = v_0 + at", r"v = 2 + 3\cdot 4 = 14"],
                "key_symbols": ["v₀ = 2 м/с", "a = 3 м/с²", "t = 4 с", "v = 14 м/с"],
                "citation_query": "§3, PDF с. 16: жылдамдық", "citations": [BOOK_CITATION],
            },
            {
                "id": "B3", "title": "Орын ауыстыру s = v0t + at²/2",
                "goal": "s = v0t + at²/2 формуласымен 32 м-ді есептеу.",
                "beats": [
                    "Орын ауыстыру — старттан ығысу.",
                    "s = v0t + at²/2: 8 + 24 = 32 м.",
                    "Бірінші мүше — үдемей жүрген жол, екіншісі — үдеу үлесі.",
                ],
                "narration": "Орын ауыстыру — дененің старттан қанша ығысқаны. Бағыт өзгермесе, ол жүрілген жолға тең. Формула: s тең v нөл t плюс a t квадраттың жартысы. Бірінші қосылғыш — үдемей жүрген жол, екіншісі — үдеуден қосылғаны. Есептейміз: екі көбейту төрт — сегіз, плюс үш көбейту он алтының жартысы — жиырма төрт. Барлығы отыз екі метр.",
                "key_equations": [r"s = v_0t + at^2/2", r"s = 2\cdot 4 + (3\cdot 4^2)/2 = 32"],
                "key_symbols": ["v₀ = 2 м/с", "a = 3 м/с²", "t = 4 с", "s = 32 м"],
                "citation_query": "§3, PDF с. 16–18: орын ауыстыру", "citations": [BOOK_CITATION],
            },
            {
                "id": "B4", "title": "v(t) графигі",
                "goal": "Көрсету: v(t) графигінің көлбеуі үдеуге тең.",
                "beats": [
                    "v = 2 + 3t — түзу: (0 с; 2 м/с) → (4 с; 14 м/с).",
                    "Көлбеу неғұрлым тік — a соғұрлым үлкен.",
                    "v(t) көлбеуі = a.",
                ],
                "narration": "Жылдамдықтың уақытқа тәуелділік графигін саламыз: v тең екі плюс үш t. Бұл түзу: нөлде — екі, төрт секундтан кейін — он төрт. Түзудің көлбеуі — бұл үдеу: неғұрлым тік болса, a соғұрлым үлкен. Есте сақта: v-ның t-ға тәуелділік графигінің көлбеуі үдеуге тең.",
                "key_equations": [r"v = 2 + 3t", r"a = \Delta v / \Delta t"],
                "key_symbols": ["көлбеу = a", "a = 3 м/с²"],
                "citation_query": "§3, PDF с. 16–18: v(t) графигі", "citations": [BOOK_CITATION],
            },
            {
                "id": "B5", "title": "Ауданмен тексеру",
                "goal": "Ауданмен тексеру: трапеция 32 м береді.",
                "beats": [
                    "График астындағы аудан = орын ауыстыру.",
                    "(2 + 14)/2 · 4 = 32 м.",
                    "Екі тәсіл — бір жауап.",
                ],
                "narration": "Енді тексереміз. Жылдамдық графигі астындағы аудан сан жағынан орын ауыстыруға тең. Бізде табандары екі мен он төрт, биіктігі төрт трапеция: табандардың жарты қосындысын биіктікке көбейтеміз — сегіз көбейту төрт — отыз екі метр. Формуламен сәйкес келді. Екі тәсіл — бір жауап.",
                "key_equations": [r"s = ((2+14)/2)\cdot 4 = 32"],
                "key_symbols": ["s = 32 м"],
                "citation_query": "§3, PDF с. 16–18: ауданмен тексеру", "citations": [BOOK_CITATION],
            },
            {
                "id": "B6", "title": "Кідіртіп шығаратын есеп",
                "goal": "Өздік есеп: v0 = 0, a = 2 м/с², t = 5 с → 25 м.",
                "beats": [
                    "Видеоны кідірт те, өзің шығар.",
                    "s = 0·5 + 2·25/2 = 25 м.",
                ],
                "narration": "Енді өзің. Мәшине орнынан секундына квадрат екі метр үдеумен қозғалды. Бес секундта қанша жол жүреді? Видеоны кідірте тұр да, өзің шығар. Жауабы: нөл көбейту бес плюс екі көбейту жиырма бестің жартысы — жиырма бес метр.",
                "key_equations": [r"s = 0\cdot 5 + (2\cdot 5^2)/2 = 25"],
                "key_symbols": ["v₀ = 0 м/с", "a = 2 м/с²", "t = 5 с", "s = 25 м"],
                "citation_query": "§3, PDF с. 20: есептер", "citations": [BOOK_CITATION],
            },
            {
                "id": "B7", "title": "Қақпандар және қорытынды",
                "goal": "Екі қақпанды бекіту және сабақты қорытындылау.",
                "kind": "recap",
                "beats": [
                    "Қақпан 1: 14·4 = 56 — орташа жылдамдықты алу керек.",
                    "Қақпан 2: көлбеу = a, аудан = s.",
                    "v = v0 + at; s = v0t + at²/2.",
                ],
                "narration": "Екі қақпан. Біріншісі: соңғы жылдамдықты бірқалыпты қозғалыс формуласына қою: он төрт көбейту төрт — елу алты. Қате: жылдамдық өсіп отыр, орташасын алу керек. Екіншісі: көлбеу мен ауданды шатастыру. Көлбеу — бұл үдеу, аудан — орын ауыстыру. Қорытынды: v тең v нөл плюс a t; s тең v нөл t плюс a t квадраттың жартысы; v-ның t-ға графигі астындағы аудан — орын ауыстыру. График ауданына есептер ҰБТ байқау сынақтарында кездеседі — енді оларды танисың.",
                "key_equations": [r"v = v_0 + at", r"s = v_0t + at^2/2"],
                "key_symbols": [],
                "citation_query": "§3, PDF с. 15–18; ҰБТ спецификациясы",
                "citations": [BOOK_CITATION, SPECIFICATION_CITATION],
            },
        ],
        "practice": [
            {
                "q": "Дене 2 м/с бастапқы жылдамдықпен қозғалады. Оның үдеуі 3 м/с². 4 секундтан кейінгі жылдамдығын табыңыз.",
                "choices": ["A) 14 м/с", "B) 12 м/с", "C) 9 м/с", "D) 6 м/с"],
                "answer": "A) 14 м/с",
                "why": "Үдеу жылдамдықты әр секунд сайын 3 м/с-қа арттырады. Сондықтан v = v₀ + at = 2 + 3·4 = 14 м/с.",
            },
            {
                "q": "Дене 2 м/с бастапқы жылдамдықпен, 3 м/с² үдеумен қозғалады. Бағыты өзгермесе, 4 с-тағы орын ауыстыруын табыңыз.",
                "choices": ["A) 32 м", "B) 56 м", "C) 24 м", "D) 20 м"],
                "answer": "A) 32 м",
                "why": "s = v₀t + at²/2 = 2·4 + 3·16/2 = 8 + 24 = 32 м. 56 м жауабы соңғы жылдамдықты бірқалыпты қозғалыс формуласына қойғанда шығады.",
            },
            {
                "q": "Қандай қозғалыс теңүдемелі деп аталады?",
                "choices": ["A) Жылдамдық тең уақыт аралықтарында бірдей шамаға өзгереді", "B) Жылдамдық тұрақты", "C) Үдеу уақыт өте келе өзгереді", "D) Тең уақыт аралықтарында жол бірдей"],
                "answer": "A) Жылдамдық тең уақыт аралықтарында бірдей шамаға өзгереді",
                "why": "Теңүдемелі қозғалыста жылдамдық тең уақытта бірдей шамаға артады, үдеу тұрақты (Закирова 9, §3). D нұсқасы бірқалыпты қозғалысты сипаттайды.",
            },
            {
                "q": "Жылдамдықтың уақытқа тәуелділік графигіндегі түзудің көлбеуі нені көрсетеді?",
                "choices": ["A) Үдеуді", "B) Орын ауыстыруды", "C) Жылдамдықты", "D) Уақытты"],
                "answer": "A) Үдеуді",
                "why": "v(t) графигінің көлбеуі үдеуге тең: a = Δv/Δt. Орын ауыстыру — график астындағы аудан (Закирова 10, §3).",
            },
            {
                "q": "v(t) графигінде түзу (0 с; 2 м/с) нүктесінен (4 с; 14 м/с) нүктесіне барады. Орын ауыстыруды табыңыз.",
                "choices": ["A) 32 м", "B) 48 м", "C) 56 м", "D) 24 м"],
                "answer": "A) 32 м",
                "why": "Трапеция ауданы: (2 + 14)/2 · 4 = 32 м. 24 м — тіктөртбұрышсыз тек үшбұрыштың ауданы.",
            },
        ],
    },
    "ru": {
        "title": "Равноускоренное движение — 5-минутный урок",
        "topic": ACCELERATED_MOTION_5MIN_ID,
        "prerequisites": [
            "Помнить, что скорость связана с пройденным расстоянием и временем.",
            "Знать единицы секунд и метров в секунду.",
        ],
        "objectives": [
            "Объяснить ускорение через изменение скорости за каждую секунду.",
            "Вычислить скорость и перемещение при постоянном ускорении.",
            "Найти путь по графику скорости от времени.",
        ],
        "misconception": (
            "Ускорение не равно самой скорости. Оно показывает, как скорость меняется со временем."
        ),
        "chapters": [
            {
                "id": "B0", "title": "Крючок и цель",
                "goal": "Поставить вопрос урока: сколько метров пройдёт машина за 4 с?",
                "beats": [
                    "Машина разгоняется с 2 м/с до 14 м/с за 4 с.",
                    "К концу урока найдёшь ответ двумя способами.",
                ],
                "narration": "Машина едет со скоростью два метра в секунду и плавно разгоняется. Через четыре секунды — уже четырнадцать. Сколько метров она прошла? К концу урока ты найдёшь ответ двумя способами.",
                "key_equations": [], "key_symbols": [],
                "citation_query": "§3, PDF с. 15–18", "citations": [BOOK_CITATION],
            },
            {
                "id": "B1", "title": "Что значит «равноускоренно»",
                "goal": "Ввести «равноускоренно»: равные прибавки скорости за равные времена.",
                "beats": [
                    "Равномерное движение: v = s / t.",
                    "У нас каждую секунду +3 м/с — это a = 3 м/с².",
                    "Ось Ox направляем по движению.",
                ],
                "narration": "Если скорость не меняется — движение равномерное: v равно s делить на t. У нас скорость растёт — но растёт одинаково за каждую секунду. Каждую секунду прибавка три метра в секунду — это и значит, что ускорение равно трём. Такое движение называется равноускоренным. Быстроту роста скорости показывает ускорение: a равно изменение скорости, делённое на время. Единица — метр на секунду в квадрате. Направим ось икс по движению: всё, что вперёд, — со знаком плюс.",
                "key_equations": [r"a = \Delta v / \Delta t"],
                "key_symbols": ["a = 3 м/с²", "[a] = м/с²"],
                "citation_query": "§3, PDF с. 15–16: ускорение", "citations": [BOOK_CITATION],
            },
            {
                "id": "B2", "title": "Скорость v = v0 + at",
                "goal": "Применить v = v0 + at и получить 14 м/с.",
                "beats": [
                    "Скорость = стартовая + прибавка (a·t).",
                    "2 + 3·4 = 14 м/с.",
                    "Проверь единицы: м/с² · с = м/с.",
                ],
                "narration": "Скорость в любой момент — это стартовая скорость плюс прибавка. Прибавка — ускорение умножить на время: v равно v нулевое плюс a t. Подставим наши числа: два плюс три умножить на четыре — четырнадцать метров в секунду. Проверь единицы: метр на секунду в квадрате умножить на секунду даёт метр на секунду. Всё сходится.",
                "key_equations": [r"v = v_0 + at", r"v = 2 + 3\cdot 4 = 14"],
                "key_symbols": ["v₀ = 2 м/с", "a = 3 м/с²", "t = 4 с", "v = 14 м/с"],
                "citation_query": "§3, PDF с. 16: скорость", "citations": [BOOK_CITATION],
            },
            {
                "id": "B3", "title": "Перемещение s = v0t + at²/2",
                "goal": "Вычислить s = v0t + at²/2 и получить 32 м.",
                "beats": [
                    "Перемещение — сдвиг от старта.",
                    "s = v0t + at²/2: 8 + 24 = 32 м.",
                    "Первое слагаемое — путь без разгона, второе — добавка разгона.",
                ],
                "narration": "Перемещение — это насколько тело сдвинулось от старта. Пока направление не меняется, оно равно пройденному пути. Формула: s равно v нулевое t плюс a t квадрат пополам. Первое слагаемое — что прошли бы без разгона, второе — добавка от разгона. Считаем: два умножить на четыре — восемь, плюс три умножить на шестнадцать пополам — двадцать четыре. Итого тридцать два метра.",
                "key_equations": [r"s = v_0t + at^2/2", r"s = 2\cdot 4 + (3\cdot 4^2)/2 = 32"],
                "key_symbols": ["v₀ = 2 м/с", "a = 3 м/с²", "t = 4 с", "s = 32 м"],
                "citation_query": "§3, PDF с. 16–18: перемещение", "citations": [BOOK_CITATION],
            },
            {
                "id": "B4", "title": "График v(t)",
                "goal": "Показать: наклон графика v(t) равен ускорению.",
                "beats": [
                    "v = 2 + 3t — прямая: (0 с; 2 м/с) → (4 с; 14 м/с).",
                    "Чем круче наклон, тем больше a.",
                    "Наклон v(t) = a.",
                ],
                "narration": "Построим график скорости от времени: v равно два плюс три t. Это прямая: в нуле — два, через четыре секунды — четырнадцать. Наклон прямой — это ускорение: чем круче, тем больше a. Запомни: наклон графика v от t равен ускорению.",
                "key_equations": [r"v = 2 + 3t", r"a = \Delta v / \Delta t"],
                "key_symbols": ["наклон = a", "a = 3 м/с²"],
                "citation_query": "§3, PDF с. 16–18: график v(t)", "citations": [BOOK_CITATION],
            },
            {
                "id": "B5", "title": "Проверка площадью",
                "goal": "Проверить площадью: трапеция даёт 32 м.",
                "beats": [
                    "Площадь под графиком = перемещение.",
                    "(2 + 14)/2 · 4 = 32 м.",
                    "Два способа — один ответ.",
                ],
                "narration": "А теперь проверка. Площадь под графиком скорости численно равна перемещению. У нас трапеция с основаниями два и четырнадцать и высотой четыре: полусумма оснований на высоту — восемь умножить на четыре — тридцать два метра. Сошлось с формулой. Два способа — один ответ.",
                "key_equations": [r"s = ((2+14)/2)\cdot 4 = 32"],
                "key_symbols": ["s = 32 м"],
                "citation_query": "§3, PDF с. 16–18: проверка площадью", "citations": [BOOK_CITATION],
            },
            {
                "id": "B6", "title": "Пауза-задача",
                "goal": "Самостоятельная задача: v0 = 0, a = 2 м/с², t = 5 с → 25 м.",
                "beats": [
                    "Поставь видео на паузу и реши сам.",
                    "s = 0·5 + 2·25/2 = 25 м.",
                ],
                "narration": "А теперь ты. Машина стартует с места с ускорением два метра на секунду в квадрате. Сколько она пройдёт за пять секунд? Поставь видео на паузу и реши. Ответ: ноль умножить на пять плюс два умножить на двадцать пять пополам — двадцать пять метров.",
                "key_equations": [r"s = 0\cdot 5 + (2\cdot 5^2)/2 = 25"],
                "key_symbols": ["v₀ = 0 м/с", "a = 2 м/с²", "t = 5 с", "s = 25 м"],
                "citation_query": "§3, PDF с. 20: задачи", "citations": [BOOK_CITATION],
            },
            {
                "id": "B7", "title": "Ловушки и итог",
                "goal": "Закрепить две ловушки и подвести итог.",
                "kind": "recap",
                "beats": [
                    "Ловушка 1: 14·4 = 56 — брать надо среднюю скорость.",
                    "Ловушка 2: наклон = a, площадь = s.",
                    "v = v0 + at; s = v0t + at²/2.",
                ],
                "narration": "Две ловушки. Первая: подставить конечную скорость в формулу равномерного движения: четырнадцать умножить на четыре — пятьдесят шесть. Неверно: скорость-то росла, брать надо среднюю. Вторая: перепутать наклон и площадь. Наклон — это ускорение, площадь — перемещение. Итог: v равно v нулевое плюс a t; s равно v нулевое t плюс a t квадрат пополам; площадь под v от t — перемещение. Задачи на площадь графика встречаются в пробниках ЕНТ — теперь ты их узнаешь.",
                "key_equations": [r"v = v_0 + at", r"s = v_0t + at^2/2"],
                "key_symbols": [],
                "citation_query": "§3, PDF с. 15–18; спецификация ЕНТ",
                "citations": [BOOK_CITATION, SPECIFICATION_CITATION],
            },
        ],
        "practice": [
            {
                "q": "Тело движется с начальной скоростью 2 м/с и ускорением 3 м/с². Найдите скорость через 4 секунды.",
                "choices": ["A) 14 м/с", "B) 12 м/с", "C) 9 м/с", "D) 6 м/с"],
                "answer": "A) 14 м/с",
                "why": "Ускорение каждую секунду увеличивает скорость на 3 м/с. Поэтому v = v₀ + at = 2 + 3·4 = 14 м/с.",
            },
            {
                "q": "Тело движется с начальной скоростью 2 м/с и ускорением 3 м/с². Найдите перемещение за 4 с. Направление движения не меняется.",
                "choices": ["A) 32 м", "B) 56 м", "C) 24 м", "D) 20 м"],
                "answer": "A) 32 м",
                "why": "s = v₀t + at²/2 = 2·4 + 3·16/2 = 8 + 24 = 32 м. Вариант 56 м получается, если подставить конечную скорость в формулу равномерного движения.",
            },
            {
                "q": "Какое движение называется равноускоренным?",
                "choices": ["A) Скорость за равные промежутки времени меняется одинаково", "B) Скорость постоянна", "C) Ускорение меняется со временем", "D) Путь за равные промежутки времени одинаков"],
                "answer": "A) Скорость за равные промежутки времени меняется одинаково",
                "why": "Равноускоренное движение — скорость получает равные прибавки за равные времена при постоянном ускорении (Закирова 9, §3). Вариант D описывает равномерное движение.",
            },
            {
                "q": "Что показывает наклон прямой на графике скорости от времени?",
                "choices": ["A) Ускорение", "B) Перемещение", "C) Скорость", "D) Время"],
                "answer": "A) Ускорение",
                "why": "Наклон v(t) равен ускорению: a = Δv/Δt. Перемещение — это площадь под графиком, а не наклон (Закирова 10, §3).",
            },
            {
                "q": "На графике v(t) прямая идёт от точки (0 с; 2 м/с) до точки (4 с; 14 м/с). Найдите перемещение.",
                "choices": ["A) 32 м", "B) 48 м", "C) 56 м", "D) 24 м"],
                "answer": "A) 32 м",
                "why": "Площадь трапеции: (2 + 14)/2 · 4 = 32 м. Вариант 24 м — только треугольник без прямоугольника.",
            },
        ],
    },
    "en": {
        "title": "Uniformly accelerated motion — 5-minute lesson",
        "topic": ACCELERATED_MOTION_5MIN_ID,
        "prerequisites": [
            "Know that speed relates distance to time.",
            "Recognize seconds and metres per second.",
        ],
        "objectives": [
            "Explain acceleration as the change in velocity each second.",
            "Find velocity and displacement for constant acceleration.",
            "Find distance from a velocity–time graph.",
        ],
        "misconception": "Acceleration is not the velocity itself. It describes how velocity changes over time.",
        "chapters": [
            {
                "id": "B0", "title": "Hook and goal",
                "goal": "Pose the lesson question: how far does the car go in 4 s?",
                "beats": [
                    "A car speeds up from 2 m/s to 14 m/s in 4 s.",
                    "By the end you will find the answer two ways.",
                ],
                "narration": "A car travels at two metres per second and accelerates smoothly. After four seconds it already does fourteen. How many metres did it cover? By the end of the lesson you will find the answer two ways.",
                "key_equations": [], "key_symbols": [],
                "citation_query": "§3, PDF pp. 15–18", "citations": [BOOK_CITATION],
            },
            {
                "id": "B1", "title": "What “uniformly accelerated” means",
                "goal": "Define “uniformly accelerated”: equal velocity gains in equal times.",
                "beats": [
                    "Uniform motion: v = s / t.",
                    "Here +3 m/s every second — that is a = 3 m/s².",
                    "We point the Ox axis along the motion.",
                ],
                "narration": "If speed never changes, motion is uniform: v equals s over t. Here speed grows — but grows by the same amount each second. Every second adds three metres per second — that is what an acceleration of three means. Such motion is called uniformly accelerated. Acceleration measures how fast velocity grows: a equals the change in velocity divided by time. Its unit is the metre per second squared. We point the x axis along the motion: everything forward takes the plus sign.",
                "key_equations": [r"a = \Delta v / \Delta t"],
                "key_symbols": ["a = 3 m/s²", "[a] = m/s²"],
                "citation_query": "§3, PDF pp. 15–16: acceleration", "citations": [BOOK_CITATION],
            },
            {
                "id": "B2", "title": "Velocity v = v₀ + at",
                "goal": "Apply v = v₀ + at and get 14 m/s.",
                "beats": [
                    "Velocity = start + gain (a·t).",
                    "2 + 3·4 = 14 m/s.",
                    "Check the units: m/s² · s = m/s.",
                ],
                "narration": "Velocity at any moment is the starting velocity plus the gain. The gain is acceleration times time: v equals v naught plus a t. Plug in our numbers: two plus three times four — fourteen metres per second. Check the units: metres per second squared times seconds gives metres per second. It all fits.",
                "key_equations": [r"v = v_0 + at", r"v = 2 + 3\cdot 4 = 14\,\mathrm{m/s}"],
                "key_symbols": ["v₀ = 2 m/s", "a = 3 m/s²", "t = 4 s", "v = 14 m/s"],
                "citation_query": "§3, PDF p. 16: velocity", "citations": [BOOK_CITATION],
            },
            {
                "id": "B3", "title": "Displacement s = v₀t + at²/2",
                "goal": "Compute s = v₀t + at²/2 and get 32 m.",
                "beats": [
                    "Displacement is the shift from the start.",
                    "s = v₀t + at²/2: 8 + 24 = 32 m.",
                    "First term — coasting distance, second — the acceleration boost.",
                ],
                "narration": "Displacement is how far the body shifted from the start. While direction stays the same, it equals the distance travelled. The formula: s equals v naught t plus a t squared over two. The first term is what we would cover without accelerating; the second is the boost from acceleration. Let's compute: two times four is eight, plus three times sixteen over two — twenty-four. Thirty-two metres in total.",
                "key_equations": [r"s = v_0t + at^2/2", r"s = 2\cdot 4 + (3\cdot 4^2)/2 = 32\,\mathrm{m}"],
                "key_symbols": ["v₀ = 2 m/s", "a = 3 m/s²", "t = 4 s", "s = 32 m"],
                "citation_query": "§3, PDF pp. 16–18: displacement", "citations": [BOOK_CITATION],
            },
            {
                "id": "B4", "title": "The v(t) graph",
                "goal": "Show the slope of the v(t) graph equals the acceleration.",
                "beats": [
                    "v = 2 + 3t is a straight line: (0 s; 2 m/s) → (4 s; 14 m/s).",
                    "The steeper the slope, the larger the a.",
                    "Slope of v(t) = a.",
                ],
                "narration": "Let's plot velocity against time: v equals two plus three t. It is a straight line: two at zero, fourteen after four seconds. The slope of the line is the acceleration: the steeper, the larger the a. Remember: the slope of the v–t graph equals the acceleration.",
                "key_equations": [r"v = 2 + 3t", r"a = \Delta v / \Delta t"],
                "key_symbols": ["slope = a", "a = 3 m/s²"],
                "citation_query": "§3, PDF pp. 16–18: the v(t) graph", "citations": [BOOK_CITATION],
            },
            {
                "id": "B5", "title": "Check by area",
                "goal": "Check by area: the trapezoid gives 32 m.",
                "beats": [
                    "Area under the graph = displacement.",
                    "(2 + 14)/2 · 4 = 32 m.",
                    "Two ways, one answer.",
                ],
                "narration": "Now the check. The area under the velocity graph numerically equals the displacement. We have a trapezoid with bases two and fourteen and height four: half the sum of the bases times the height — eight times four — thirty-two metres. It matches the formula. Two ways, one answer.",
                "key_equations": [r"s = ((2+14)/2)\cdot 4 = 32\,\mathrm{m}"],
                "key_symbols": ["s = 32 m"],
                "citation_query": "§3, PDF pp. 16–18: check by area", "citations": [BOOK_CITATION],
            },
            {
                "id": "B6", "title": "Pause-and-solve task",
                "goal": "Solo task: v₀ = 0, a = 2 m/s², t = 5 s → 25 m.",
                "beats": [
                    "Pause the video and solve it yourself.",
                    "s = 0·5 + 2·25/2 = 25 m.",
                ],
                "narration": "Now you. A car starts from rest with an acceleration of two metres per second squared. How far does it go in five seconds? Pause the video and solve it. Answer: zero times five plus two times twenty-five over two — twenty-five metres.",
                "key_equations": [r"s = 0\cdot 5 + (2\cdot 5^2)/2 = 25\,\mathrm{m}"],
                "key_symbols": ["v₀ = 0 m/s", "a = 2 m/s²", "t = 5 s", "s = 25 m"],
                "citation_query": "§3, PDF p. 20: exercises", "citations": [BOOK_CITATION],
            },
            {
                "id": "B7", "title": "Traps and takeaway",
                "goal": "Lock in the two traps and wrap up.",
                "kind": "recap",
                "beats": [
                    "Trap 1: 14·4 = 56 — take the average speed.",
                    "Trap 2: slope = a, area = s.",
                    "v = v₀ + at; s = v₀t + at²/2.",
                ],
                "narration": "Two traps. First: plugging the final speed into the uniform-motion formula: fourteen times four is fifty-six. Wrong: the speed was growing, you must take the average. Second: mixing up slope and area. Slope is acceleration; area is displacement. To sum up: v equals v naught plus a t; s equals v naught t plus a t squared over two; the area under the v–t graph is the displacement. Graph-area problems appear in UNT mocks — now you will recognise them.",
                "key_equations": [r"v = v_0 + at", r"s = v_0t + at^2/2"],
                "key_symbols": [],
                "citation_query": "§3, PDF pp. 15–18; UNT specification",
                "citations": [BOOK_CITATION, SPECIFICATION_CITATION],
            },
        ],
        "practice": [
            {
                "q": "An object starts at 2 m/s and accelerates at 3 m/s². What is its speed after 4 seconds?",
                "choices": ["A) 14 m/s", "B) 12 m/s", "C) 9 m/s", "D) 6 m/s"],
                "answer": "A) 14 m/s",
                "why": "Acceleration adds 3 m/s of speed each second. So v = v₀ + at = 2 + 3·4 = 14 m/s.",
            },
            {
                "q": "An object moves with initial speed 2 m/s and acceleration 3 m/s² without changing direction. Find its displacement in 4 s.",
                "choices": ["A) 32 m", "B) 56 m", "C) 24 m", "D) 20 m"],
                "answer": "A) 32 m",
                "why": "s = v₀t + at²/2 = 2·4 + 3·16/2 = 8 + 24 = 32 m. 56 m comes from plugging the final speed into the uniform-motion formula.",
            },
            {
                "q": "Which motion is called uniformly accelerated?",
                "choices": ["A) Velocity changes by equal amounts in equal times", "B) Velocity stays constant", "C) Acceleration changes over time", "D) Distance is the same in equal times"],
                "answer": "A) Velocity changes by equal amounts in equal times",
                "why": "In uniformly accelerated motion velocity gains equal increments in equal times while acceleration stays constant (Zakirova 9, §3). D describes uniform motion.",
            },
            {
                "q": "What does the slope of the line on a velocity–time graph show?",
                "choices": ["A) Acceleration", "B) Displacement", "C) Velocity", "D) Time"],
                "answer": "A) Acceleration",
                "why": "The slope of v(t) equals acceleration: a = Δv/Δt. Displacement is the area under the graph, not the slope (Zakirova 10, §3).",
            },
            {
                "q": "On a v(t) graph a straight line runs from (0 s; 2 m/s) to (4 s; 14 m/s). Find the displacement.",
                "choices": ["A) 32 m", "B) 48 m", "C) 56 m", "D) 24 m"],
                "answer": "A) 32 m",
                "why": "Trapezoid area: (2 + 14)/2 · 4 = 32 m. 24 m is the triangle alone, without the rectangle.",
            },
        ],
    },
}


def accelerated_motion_5min_plan(language: str = "ru") -> LessonPlan:
    """Return the v2 5-minute lesson plan (8 prebuilt blocks, H1–H5 practice).

    The topic is the ASCII lesson id on purpose: every language shares one
    course-progress key, and that key can never collide with the v1 route's
    per-language topics.
    """
    lang = normalize_language(language, "ru")
    content = _TEXT_5MIN[lang]
    chapters = [
        LessonChapter(
            id=chapter["id"],
            title=chapter["title"],
            goal=chapter["goal"],
            kind=str(chapter.get("kind", "scene")),
            beats=list(chapter["beats"]),
            narration=chapter["narration"],
            key_equations=list(chapter["key_equations"]),
            citation_query=chapter["citation_query"],
            citations=list(chapter["citations"]),
            key_symbols=list(chapter["key_symbols"]),
        )
        for chapter in content["chapters"]
    ]
    return LessonPlan(
        title=content["title"],
        topic=content["topic"],
        audience="high_school",
        prerequisites=list(content["prerequisites"]),
        objectives=list(content["objectives"]),
        misconception=content["misconception"],
        chapters=chapters,
        questions=[LessonQuestion(**item) for item in content["practice"]],
        model_name=ACCELERATED_MOTION_5MIN_VERSION,
        language=lang,
        kazakh_terms=[dict(item) for item in _TEXT[lang]["terms"]],
    )
