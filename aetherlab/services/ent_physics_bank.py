"""Original multilingual ЕНТ physics practice form and answer key.

These questions are authored for PhysLab and are not copied from published
test variants. Their topics follow the National Testing Center's 2026 physics
specification. Keep the answer key and worked explanations explicit so the
practice flow does not depend on an LLM for grading.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from aetherlab.services.ent_mock_solutions import MOCK_SOLUTIONS

SOURCE_URL = "https://new.testcenter.kz/?lang=ru&page_id=15094"
FREE_MOCK_URL = "https://prob-ent.testcenter.kz/"
SPECIFICATION_URL = (
    "https://new.testcenter.kz/wp-content/uploads/2025/10/"
    "11_%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0_%D0%BA%D0%B0%D0%B7.pdf"
)
SPECIFICATION_RU_URL = (
    "https://new.testcenter.kz/wp-content/uploads/2025/10/"
    "12_%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0_%D1%80%D1%83%D1%81.pdf"
)

ENT_TOTAL_QUESTIONS = 40
ENT_MAX_POINTS = 50
ENT_FULL_MOCK_DURATION_S = 90 * 60


@dataclass(frozen=True)
class PracticeQuestion:
    id: str
    topic: str
    difficulty: str
    prompt: dict[str, str]
    choices: dict[str, tuple[str, ...]]
    correct_indices: tuple[int, ...]
    explanation: dict[str, str]
    kazakh_term: str
    kind: str = "single"
    context: dict[str, str] | None = None
    matching_left: dict[str, tuple[str, ...]] | None = None
    source_note: str = SPECIFICATION_URL
    reuse_status: str = "original_aetherlab_item"
    author: str = "PhysLab"
    reviewer: str = "pending_kazakhstan_physics_teacher"
    language_review_status: str = "pending_teacher_review_kk_ru_en"
    answer_verification_status: str = "author_checked_teacher_review_pending"
    solution_latex: tuple[str, ...] = ()


QUESTIONS = (
    PracticeQuestion(
        id="kinematics-velocity-01",
        topic="kinematics",
        difficulty="A",
        prompt={
            "kk": "Дене 2 м/с бастапқы жылдамдықпен қозғалады. Оның үдеуі 3 м/с². 4 секундтан кейінгі жылдамдығын табыңыз.",
            "ru": "Тело движется с начальной скоростью 2 м/с и ускорением 3 м/с². Найдите скорость через 4 секунды.",
            "en": "An object starts at 2 m/s and accelerates at 3 m/s². What is its speed after 4 seconds?",
        },
        choices={
            "kk": ("14 м/с", "12 м/с", "9 м/с", "6 м/с"),
            "ru": ("14 м/с", "12 м/с", "9 м/с", "6 м/с"),
            "en": ("14 m/s", "12 m/s", "9 m/s", "6 m/s"),
        },
        correct_indices=(0,),
        explanation={
            "kk": "Үдеу жылдамдықты әр секунд сайын 3 м/с-қа арттырады. Сондықтан v = v₀ + at = 2 + 3·4 = 14 м/с.",
            "ru": "Ускорение каждую секунду увеличивает скорость на 3 м/с. Поэтому v = v₀ + at = 2 + 3·4 = 14 м/с.",
            "en": "Acceleration adds 3 m/s of speed each second. So v = v₀ + at = 2 + 3·4 = 14 m/s.",
        },
        kazakh_term="үдеу",
    ),
    PracticeQuestion(
        id="dynamics-freefall-01",
        topic="dynamics",
        difficulty="A",
        prompt={
            "kk": "Дене тыныштық күйден еркін құлайды. g = 10 м/с² деп алыңыз. 2 секундтан кейін дененің жылдамдығы қандай болады?",
            "ru": "Тело свободно падает из состояния покоя. Примите g = 10 м/с². Какой будет скорость тела через 2 секунды?",
            "en": "An object falls freely from rest. Take g = 10 m/s². What is its speed after 2 seconds?",
        },
        choices={
            "kk": ("20 м/с", "10 м/с", "5 м/с", "40 м/с"),
            "ru": ("20 м/с", "10 м/с", "5 м/с", "40 м/с"),
            "en": ("20 m/s", "10 m/s", "5 m/s", "40 m/s"),
        },
        correct_indices=(0,),
        explanation={
            "kk": "Еркін құлауда жылдамдық v = gt формуласымен табылады: 10·2 = 20 м/с. Ауа кедергісін елемейміз.",
            "ru": "При свободном падении скорость находим по формуле v = gt: 10·2 = 20 м/с. Сопротивлением воздуха пренебрегаем.",
            "en": "For free fall, use v = gt: 10·2 = 20 m/s. Air resistance is ignored.",
        },
        kazakh_term="еркін түсу үдеуі",
    ),
    PracticeQuestion(
        id="electricity-ohm-01",
        topic="electricity",
        difficulty="A",
        prompt={
            "kk": "Өткізгіштің ұштарындағы кернеу 12 В, ал кедергісі 6 Ом. Ток күшін табыңыз.",
            "ru": "Напряжение на проводнике равно 12 В, а сопротивление — 6 Ом. Найдите силу тока.",
            "en": "A conductor has a voltage of 12 V and a resistance of 6 Ω. Find the current.",
        },
        choices={
            "kk": ("2 А", "18 А", "72 А", "0,5 А"),
            "ru": ("2 А", "18 А", "72 А", "0,5 А"),
            "en": ("2 A", "18 A", "72 A", "0.5 A"),
        },
        correct_indices=(0,),
        explanation={
            "kk": "Ом заңы: I = U/R. Кернеуді кедергіге бөлеміз: 12/6 = 2 А.",
            "ru": "Закон Ома: I = U/R. Делим напряжение на сопротивление: 12/6 = 2 А.",
            "en": "Ohm's law gives I = U/R. Divide voltage by resistance: 12/6 = 2 A.",
        },
        kazakh_term="кедергі",
    ),
    PracticeQuestion(
        id="energy-kinetic-01",
        topic="conservation",
        difficulty="B",
        prompt={
            "kk": "Массасы 2 кг дене 3 м/с жылдамдықпен қозғалады. Оның кинетикалық энергиясын табыңыз.",
            "ru": "Тело массой 2 кг движется со скоростью 3 м/с. Найдите его кинетическую энергию.",
            "en": "A 2 kg object moves at 3 m/s. Find its kinetic energy.",
        },
        choices={
            "kk": ("9 Дж", "6 Дж", "18 Дж", "3 Дж"),
            "ru": ("9 Дж", "6 Дж", "18 Дж", "3 Дж"),
            "en": ("9 J", "6 J", "18 J", "3 J"),
        },
        correct_indices=(0,),
        explanation={
            "kk": "Кинетикалық энергия Eₖ = mv²/2. Есептейміз: 2·3²/2 = 9 Дж.",
            "ru": "Кинетическая энергия Eₖ = mv²/2. Подставляем: 2·3²/2 = 9 Дж.",
            "en": "Kinetic energy is Eₖ = mv²/2. Substitution gives 2·3²/2 = 9 J.",
        },
        kazakh_term="кинетикалық энергия",
    ),
    PracticeQuestion(
        id="waves-period-01",
        topic="wave_motion",
        difficulty="B",
        prompt={
            "kk": "Толқынның жиілігі 5 Гц. Тербеліс периоды неге тең?",
            "ru": "Частота волны равна 5 Гц. Чему равен период колебаний?",
            "en": "A wave has a frequency of 5 Hz. What is its period?",
        },
        choices={
            "kk": ("0,2 с", "5 с", "2 с", "0,5 с"),
            "ru": ("0,2 с", "5 с", "2 с", "0,5 с"),
            "en": ("0.2 s", "5 s", "2 s", "0.5 s"),
        },
        correct_indices=(0,),
        explanation={
            "kk": "Период — бір толық тербеліске кететін уақыт. T = 1/f = 1/5 = 0,2 с.",
            "ru": "Период — время одного полного колебания. T = 1/f = 1/5 = 0,2 с.",
            "en": "The period is the time for one complete oscillation. T = 1/f = 1/5 = 0.2 s.",
        },
        kazakh_term="тербеліс периоды",
    ),
)


_LANGS = ("kk", "ru", "en")

ENT_TOPIC_IDS = (
    "kinematics", "dynamics", "statics", "fluids",
    "molecular_kinetic_theory", "gas_laws", "thermodynamics", "liquids_solids",
    "electrostatics", "electricity", "current_media", "magnetic_field", "induction",
    "mechanical_oscillations", "ac_circuits", "electromagnetic_waves", "wave_optics",
    "geometric_optics", "relativity", "quantum_physics", "nuclear_physics",
    "nanotechnology", "cosmology", "conservation", "wave_motion",
)

_TOPIC_ALIASES = {"energy": "conservation", "mechanics": "dynamics"}


def question_max_points(question: PracticeQuestion | dict) -> int:
    """Maximum points for an item in the full-duration physics ЕНТ format."""
    kind = question.kind if isinstance(question, PracticeQuestion) else question.get("kind", "single")
    return 2 if kind in {"multi", "matching"} else 1


def score_question(answer: tuple[int, ...] | None, question: PracticeQuestion | dict) -> int:
    """Score one answer using the current ЕНТ partial-credit rules.

    Single-answer and context items are worth one point. Multiple-answer and
    matching items are worth up to two points and use the official 0/1/2
    partial-credit patterns. This is deliberately independent of an LLM.
    """
    if answer is None:
        return 0
    if isinstance(question, PracticeQuestion):
        kind = question.kind
        correct = question.correct_indices
    else:
        kind = str(question.get("kind", "single"))
        correct = tuple(question.get("correct_indices", ()))
    selected = tuple(int(index) for index in answer)

    if kind not in {"multi", "matching"}:
        return int(selected == tuple(correct))

    correct_count = len(correct)
    if not 1 <= correct_count <= 3:
        return 0

    if kind == "matching":
        # A standard profile-subject matching task has two matched pairs.
        if correct_count != 2:
            return 0
        matched = sum(
            1 for row, expected in enumerate(correct)
            if row < len(selected) and selected[row] == expected
        )
        wrong = sum(
            1 for row, selected_index in enumerate(selected)
            if selected_index >= 0 and (row >= len(correct) or selected_index != correct[row])
        )
    else:
        selected_set = {index for index in selected if index >= 0}
        correct_set = set(correct)
        matched = len(selected_set & correct_set)
        wrong = len(selected_set - correct_set)

    if matched == correct_count and wrong == 0:
        return 2
    if correct_count == 1:
        return int(matched == 1 and wrong == 1)
    if correct_count == 2:
        return int((matched == 1 and wrong <= 1) or (matched == 2 and wrong == 1))
    # Three correct options: two correct (with at most one distractor), or all
    # three correct plus one distractor, earn one point.
    return int((matched == 2 and wrong <= 1) or (matched == 3 and wrong == 1))


def canonical_topic(topic: str) -> str:
    """Map question tags onto the 25 selectable ENT topic buckets."""
    return _TOPIC_ALIASES.get(topic, topic)


def _q(
    question_id: str,
    topic: str,
    difficulty: str,
    prompts: tuple[str, str, str],
    choices: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
    correct_indices: tuple[int, ...],
    explanations: tuple[str, str, str],
    kazakh_term: str,
    *,
    kind: str = "single",
    context: tuple[str, str, str] | None = None,
    matching_left: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]] | None = None,
) -> PracticeQuestion:
    return PracticeQuestion(
        id=question_id,
        topic=topic,
        difficulty=difficulty,
        prompt=dict(zip(_LANGS, prompts)),
        choices={code: tuple(labels) for code, labels in zip(_LANGS, choices)},
        correct_indices=correct_indices,
        explanation=dict(zip(_LANGS, explanations)),
        kazakh_term=kazakh_term,
        kind=kind,
        context=dict(zip(_LANGS, context)) if context else None,
        matching_left=(
            {code: tuple(labels) for code, labels in zip(_LANGS, matching_left)}
            if matching_left else None
        ),
    )


_MORE_SINGLE_QUESTIONS = (
    _q(
        "statics-moment-01", "statics", "A",
        (
            "Ұзындығы 0,20 м иінге 40 Н күш түсірілген. Екінші иін 0,50 м болса, тепе-теңдік үшін оған қандай күш түсіру керек?",
            "К плечу длиной 0,20 м приложена сила 40 Н. Какая сила уравновесит её на плече 0,50 м?",
            "A 40 N force acts at a 0.20 m lever arm. What force balances it at a 0.50 m arm?",
        ),
        (("16 Н", "10 Н", "20 Н", "40 Н"), ("16 Н", "10 Н", "20 Н", "40 Н"), ("16 N", "10 N", "20 N", "40 N")),
        (0,),
        (
            "Тепе-теңдікте күш моменттері тең: 40·0,20 = F·0,50. Сондықтан F = 16 Н.",
            "При равновесии моменты равны: 40·0,20 = F·0,50. Поэтому F = 16 Н.",
            "At balance, the moments are equal: 40·0.20 = F·0.50, so F = 16 N.",
        ),
        "күш моменті",
    ),
    _q(
        "fluids-pressure-01", "fluids", "A",
        (
            "Судың тығыздығы 1000 кг/м³. 3 м тереңдіктегі сұйық қысымын табыңыз (g = 10 м/с²).",
            "Плотность воды 1000 кг/м³. Найдите давление воды на глубине 3 м (g = 10 м/с²).",
            "Water has density 1000 kg/m³. Find the water pressure at 3 m depth (g = 10 m/s²).",
        ),
        (("30 кПа", "3 кПа", "300 кПа", "3000 кПа"), ("30 кПа", "3 кПа", "300 кПа", "3000 кПа"), ("30 kPa", "3 kPa", "300 kPa", "3000 kPa")),
        (0,),
        (
            "Сұйық қысымы p = ρgh. 1000·10·3 = 30000 Па = 30 кПа.",
            "Давление жидкости p = ρgh. 1000·10·3 = 30000 Па = 30 кПа.",
            "Liquid pressure is p = ρgh. 1000·10·3 = 30,000 Pa = 30 kPa.",
        ),
        "қысым",
    ),
    _q(
        "mkt-kinetic-energy-01", "molecular_kinetic_theory", "A",
        (
            "Идеал газдың абсолют температурасы 300 К-нен 600 К-ге артты. Молекулалардың орташа кинетикалық энергиясы қалай өзгереді?",
            "Абсолютная температура идеального газа выросла с 300 К до 600 К. Как изменилась средняя кинетическая энергия молекул?",
            "An ideal gas warms from 300 K to 600 K. How does the molecules' average kinetic energy change?",
        ),
        (("2 есе артады", "2 есе кемиді", "Өзгермейді", "4 есе артады"), ("Увеличится в 2 раза", "Уменьшится в 2 раза", "Не изменится", "Увеличится в 4 раза"), ("It doubles", "It halves", "It stays the same", "It quadruples")),
        (0,),
        (
            "Орташа кинетикалық энергия абсолют температураға тура пропорционал. Температура екі есе артты, демек энергия да екі есе артады.",
            "Средняя кинетическая энергия прямо пропорциональна абсолютной температуре. Температура выросла вдвое — энергия тоже.",
            "Average kinetic energy is proportional to absolute temperature. Doubling the temperature doubles the energy.",
        ),
        "молекуланың кинетикалық энергиясы",
    ),
    _q(
        "gas-law-pressure-01", "gas_laws", "A",
        (
            "Газ жабық ыдыста тұр. Температура 300 К-нен 450 К-ге артса, бастапқы қысым 100 кПа болғанда жаңа қысым қандай?",
            "Газ находится в закрытом жёстком сосуде. Температура выросла с 300 К до 450 К. Каково новое давление, если сначала оно было 100 кПа?",
            "A gas is sealed in a rigid container. Its temperature rises from 300 K to 450 K. What is the new pressure if it started at 100 kPa?",
        ),
        (("150 кПа", "100 кПа", "200 кПа", "50 кПа"), ("150 кПа", "100 кПа", "200 кПа", "50 кПа"), ("150 kPa", "100 kPa", "200 kPa", "50 kPa")),
        (0,),
        (
            "Көлем тұрақты болса, p/T тұрақты. p₂ = 100·450/300 = 150 кПа.",
            "При постоянном объёме p/T постоянно. p₂ = 100·450/300 = 150 кПа.",
            "At fixed volume, p/T stays constant. p₂ = 100·450/300 = 150 kPa.",
        ),
        "абсолют температура",
    ),
    _q(
        "thermodynamics-first-law-01", "thermodynamics", "B",
        (
            "Газға 500 Дж жылу берілді. Ішкі энергиясы 200 Дж-ға артты. Газ қандай жұмыс атқарды?",
            "Газ получил 500 Дж теплоты, а его внутренняя энергия выросла на 200 Дж. Какую работу совершил газ?",
            "A gas receives 500 J of heat and its internal energy rises by 200 J. How much work does it do?",
        ),
        (("300 Дж", "700 Дж", "200 Дж", "500 Дж"), ("300 Дж", "700 Дж", "200 Дж", "500 Дж"), ("300 J", "700 J", "200 J", "500 J")),
        (0,),
        (
            "Бірінші заң: Q = ΔU + A. Сондықтан A = 500 − 200 = 300 Дж.",
            "Первый закон: Q = ΔU + A. Значит, A = 500 − 200 = 300 Дж.",
            "The first law gives Q = ΔU + W. So W = 500 − 200 = 300 J.",
        ),
        "жылу мөлшері",
    ),
    _q(
        "materials-melting-01", "liquids_solids", "A",
        (
            "Массасы 0,50 кг мұзды 0°C-та толық ерітуге қанша жылу керек? Мұздың меншікті балқу жылуы 3,3·10⁵ Дж/кг.",
            "Сколько теплоты нужно, чтобы полностью растопить 0,50 кг льда при 0°C? Удельная теплота плавления льда 3,3·10⁵ Дж/кг.",
            "How much heat melts 0.50 kg of ice at 0°C? The specific latent heat of fusion is 3.3·10⁵ J/kg.",
        ),
        (("165 кДж", "33 кДж", "660 кДж", "1,65 кДж"), ("165 кДж", "33 кДж", "660 кДж", "1,65 кДж"), ("165 kJ", "33 kJ", "660 kJ", "1.65 kJ")),
        (0,),
        (
            "Балқу кезінде Q = λm. 3,3·10⁵·0,50 = 165000 Дж = 165 кДж.",
            "При плавлении Q = λm. 3,3·10⁵·0,50 = 165000 Дж = 165 кДж.",
            "During melting, Q = Lm. 3.3·10⁵·0.50 = 165,000 J = 165 kJ.",
        ),
        "меншікті балқу жылуы",
    ),
    _q(
        "electrostatics-distance-01", "electrostatics", "A",
        (
            "Екі нүктелік зарядтың арақашықтығы 2 есе артты. Зарядтар арасындағы күш қалай өзгереді?",
            "Расстояние между двумя точечными зарядами увеличили в 2 раза. Как изменится сила взаимодействия?",
            "The distance between two point charges is doubled. How does their electric force change?",
        ),
        (("4 есе кемиді", "2 есе кемиді", "2 есе артады", "Өзгермейді"), ("Уменьшится в 4 раза", "Уменьшится в 2 раза", "Увеличится в 2 раза", "Не изменится"), ("It becomes one quarter", "It halves", "It doubles", "It stays the same")),
        (0,),
        (
            "Кулон заңы бойынша күш r²-ке кері пропорционал. Арақашықтықты 2 есе арттыру күшті 4 есе азайтады.",
            "По закону Кулона сила обратно пропорциональна r². Увеличение расстояния вдвое уменьшает силу в 4 раза.",
            "Coulomb's law gives force proportional to 1/r². Doubling distance makes the force one quarter as large.",
        ),
        "электр заряды",
    ),
    _q(
        "current-media-electrolyte-01", "current_media", "A",
        (
            "Электролит ерітіндісіндегі электр тогын қандай бөлшектер тасымалдайды?",
            "Какие частицы переносят электрический ток в растворе электролита?",
            "Which particles carry electric current through an electrolyte solution?",
        ),
        (("Оң және теріс иондар", "Тек электрондар", "Бейтарап атомдар", "Тек фотондар"), ("Положительные и отрицательные ионы", "Только электроны", "Нейтральные атомы", "Только фотоны"), ("Positive and negative ions", "Electrons only", "Neutral atoms", "Photons only")),
        (0,),
        (
            "Ерітіндіде оң және теріс иондар қарама-қарсы бағытта қозғалып, ток тудырады.",
            "В растворе положительные и отрицательные ионы движутся в противоположных направлениях и создают ток.",
            "Positive and negative ions move in opposite directions through the solution and carry the current.",
        ),
        "ион",
    ),
    _q(
        "magnetic-force-parallel-01", "magnetic_field", "B",
        (
            "Электрон магнит өрісінің күш сызықтарына параллель қозғалады. Оған магнит күші әсер ете ме?",
            "Электрон движется параллельно линиям магнитного поля. Действует ли на него магнитная сила?",
            "An electron moves parallel to magnetic field lines. Does a magnetic force act on it?",
        ),
        (("Жоқ, күш нөлге тең", "Иә, күш ең үлкен", "Иә, күш жылдамдық бағытымен бағытталған", "Тек тыныштықта күш болады"), ("Нет, сила равна нулю", "Да, сила максимальна", "Да, сила направлена вдоль скорости", "Сила есть только в покое"), ("No, the force is zero", "Yes, the force is maximum", "Yes, it points along the velocity", "Force acts only at rest")),
        (0,),
        (
            "F = |q|vB sin θ. Қозғалыс өріске параллель, сондықтан θ = 0° және sin θ = 0.",
            "F = |q|vB sin θ. Скорость параллельна полю, поэтому θ = 0° и sin θ = 0.",
            "F = |q|vB sin θ. The velocity is parallel to the field, so θ = 0° and the force is zero.",
        ),
        "магнит өрісі",
    ),
    _q(
        "induction-emf-01", "induction", "B",
        (
            "Бір орамды катушкадағы магнит ағыны 0,40 Вб-қа 0,10 с ішінде өзгерді. Индукция ЭҚК-інің модулі қандай?",
            "Магнитный поток через один виток изменился на 0,40 Вб за 0,10 с. Чему равен модуль ЭДС индукции?",
            "The magnetic flux through a one-turn coil changes by 0.40 Wb in 0.10 s. What is the induced emf magnitude?",
        ),
        (("4 В", "0,04 В", "0,4 В", "40 В"), ("4 В", "0,04 В", "0,4 В", "40 В"), ("4 V", "0.04 V", "0.4 V", "40 V")),
        (0,),
        (
            "Фарадей заңы бойынша |ε| = |ΔΦ|/Δt = 0,40/0,10 = 4 В.",
            "По закону Фарадея |ε| = |ΔΦ|/Δt = 0,40/0,10 = 4 В.",
            "Faraday's law gives |ε| = |ΔΦ|/Δt = 0.40/0.10 = 4 V.",
        ),
        "электромагниттік индукция",
    ),
    _q(
        "oscillation-frequency-01", "mechanical_oscillations", "B",
        (
            "Дене секундына 2,5 толық тербеліс жасайды. Оның периоды қандай?",
            "Тело совершает 2,5 полных колебания за секунду. Чему равен период?",
            "An object makes 2.5 complete oscillations each second. What is its period?",
        ),
        (("0,40 с", "2,5 с", "4,0 с", "0,25 с"), ("0,40 с", "2,5 с", "4,0 с", "0,25 с"), ("0.40 s", "2.5 s", "4.0 s", "0.25 s")),
        (0,),
        (
            "Жиілік f = 2,5 Гц. Бір тербелістің уақыты T = 1/f = 1/2,5 = 0,40 с.",
            "Частота f = 2,5 Гц. Период T = 1/f = 1/2,5 = 0,40 с.",
            "The frequency is 2.5 Hz, so T = 1/f = 1/2.5 = 0.40 s.",
        ),
        "тербеліс жиілігі",
    ),
    _q(
        "ac-rms-voltage-01", "ac_circuits", "C",
        (
            "Синусоидалы айнымалы кернеудің амплитудасы 311 В. Оның әсерлік мәнін табыңыз (√2 ≈ 1,414).",
            "Амплитуда синусоидального переменного напряжения равна 311 В. Найдите действующее значение (√2 ≈ 1,414).",
            "A sinusoidal AC voltage has a peak value of 311 V. Find its RMS value (√2 ≈ 1.414).",
        ),
        (("220 В", "311 В", "440 В", "110 В"), ("220 В", "311 В", "440 В", "110 В"), ("220 V", "311 V", "440 V", "110 V")),
        (0,),
        (
            "Синусоидалы кернеу үшін Uәс = Umax/√2 = 311/1,414 ≈ 220 В.",
            "Для синусоидального напряжения Uдейств = Umax/√2 = 311/1,414 ≈ 220 В.",
            "For a sine wave, Uᵣₘₛ = Uₚₑₐₖ/√2 = 311/1.414 ≈ 220 V.",
        ),
        "әсерлік кернеу",
    ),
    _q(
        "em-wave-speed-01", "electromagnetic_waves", "A",
        (
            "Вакуумдағы радиотолқын мен рентген сәулесінің таралу жылдамдығы қандай?",
            "Какова скорость радиоволны и рентгеновского излучения в вакууме?",
            "What is the speed of a radio wave and an X-ray in a vacuum?",
        ),
        (("Бірдей: 3·10⁸ м/с", "Радиотолқын жылдамырақ", "Рентген сәулесі жылдамырақ", "Жиілікке тәуелді"), ("Одинакова: 3·10⁸ м/с", "Радиоволна быстрее", "Рентген быстрее", "Зависит от частоты"), ("The same: 3·10⁸ m/s", "Radio is faster", "X-rays are faster", "It depends on frequency")),
        (0,),
        (
            "Электромагниттік толқындардың вакуумдағы жылдамдығы бірдей: жарық жылдамдығы c ≈ 3·10⁸ м/с.",
            "Все электромагнитные волны в вакууме движутся одинаково быстро: c ≈ 3·10⁸ м/с.",
            "All electromagnetic waves travel at the same speed in vacuum: c ≈ 3·10⁸ m/s.",
        ),
        "электромагниттік толқын",
    ),
    _q(
        "wave-optics-fringe-01", "wave_optics", "C",
        (
            "Қос саңылау тәжірибесінде λ = 500 нм, экранға дейінгі қашықтық L = 2 м, саңылаулар арасы d = 1 мм. Жолақ аралығын табыңыз.",
            "В опыте с двумя щелями λ = 500 нм, расстояние до экрана L = 2 м, между щелями d = 1 мм. Найдите расстояние между полосами.",
            "In a double-slit setup, λ = 500 nm, screen distance L = 2 m, and slit spacing d = 1 mm. Find the fringe spacing.",
        ),
        (("1 мм", "0,25 мм", "2 мм", "0,5 мм"), ("1 мм", "0,25 мм", "2 мм", "0,5 мм"), ("1 mm", "0.25 mm", "2 mm", "0.5 mm")),
        (0,),
        (
            "Жолақ аралығы Δx = λL/d. 500·10⁻⁹·2/(10⁻³) = 10⁻³ м = 1 мм.",
            "Расстояние между полосами Δx = λL/d. 500·10⁻⁹·2/(10⁻³) = 10⁻³ м = 1 мм.",
            "Fringe spacing is Δx = λL/d = 500·10⁻⁹·2/(10⁻³) = 10⁻³ m = 1 mm.",
        ),
        "интерференция",
    ),
    _q(
        "geometric-optics-lens-01", "geometric_optics", "B",
        (
            "Жинағыш линзаның фокустық аралығы 10 см. Нәрсе линзадан 30 см жерде тұр. Кескін линзадан қандай қашықтықта пайда болады?",
            "Собирающая линза имеет фокусное расстояние 10 см. Предмет находится в 30 см от линзы. На каком расстоянии возникнет изображение?",
            "A converging lens has focal length 10 cm. An object is 30 cm away. How far from the lens is the image?",
        ),
        (("15 см", "10 см", "20 см", "30 см"), ("15 см", "10 см", "20 см", "30 см"), ("15 cm", "10 cm", "20 cm", "30 cm")),
        (0,),
        (
            "Линза формуласы: 1/f = 1/dₒ + 1/dᵢ. 1/dᵢ = 1/10 − 1/30 = 1/15, сондықтан dᵢ = 15 см.",
            "Формула линзы: 1/f = 1/dₒ + 1/dᵢ. 1/dᵢ = 1/10 − 1/30 = 1/15, значит dᵢ = 15 см.",
            "The lens equation gives 1/dᵢ = 1/10 − 1/30 = 1/15, so the image is 15 cm away.",
        ),
        "сыну көрсеткіші",
    ),
    _q(
        "relativity-gamma-01", "relativity", "C",
        (
            "Ғарыш кемесі 0,60c жылдамдықпен ұшады. Лоренц көбейткіші γ қандай?",
            "Космический корабль летит со скоростью 0,60c. Чему равен фактор Лоренца γ?",
            "A spacecraft travels at 0.60c. What is the Lorentz factor γ?",
        ),
        (("1,25", "1,06", "1,67", "2,00"), ("1,25", "1,06", "1,67", "2,00"), ("1.25", "1.06", "1.67", "2.00")),
        (0,),
        (
            "γ = 1/√(1 − v²/c²) = 1/√(1 − 0,36) = 1/0,8 = 1,25.",
            "γ = 1/√(1 − v²/c²) = 1/√(1 − 0,36) = 1/0,8 = 1,25.",
            "γ = 1/√(1 − v²/c²) = 1/√(1 − 0.36) = 1/0.8 = 1.25.",
        ),
        "Лоренц көбейткіші",
    ),
    _q(
        "quantum-photon-energy-01", "quantum_physics", "C",
        (
            "Жарық жиілігі 2 есе артты. Бір фотонның энергиясы қалай өзгереді?",
            "Частоту света увеличили в 2 раза. Как изменится энергия одного фотона?",
            "The light frequency is doubled. How does the energy of one photon change?",
        ),
        (("2 есе артады", "Өзгермейді", "4 есе артады", "2 есе кемиді"), ("Увеличится в 2 раза", "Не изменится", "Увеличится в 4 раза", "Уменьшится в 2 раза"), ("It doubles", "It stays the same", "It quadruples", "It halves")),
        (0,),
        (
            "Фотон энергиясы E = hf. Планк тұрақтысы өзгермейді, сондықтан жиілік 2 есе артса, энергия да 2 есе артады.",
            "Энергия фотона E = hf. Постоянная Планка неизменна, поэтому при удвоении частоты энергия тоже удваивается.",
            "Photon energy is E = hf. Since h is constant, doubling frequency doubles photon energy.",
        ),
        "фотон",
    ),
    _q(
        "nuclear-half-life-01", "nuclear_physics", "A",
        (
            "Радиоактивті үлгінің жартылай ыдырау периоды 4 күн. 8 күннен кейін бастапқы ядролардың қандай бөлігі қалады?",
            "Период полураспада образца равен 4 дням. Какая часть исходных ядер останется через 8 дней?",
            "A radioactive sample has a half-life of 4 days. What fraction of its original nuclei remains after 8 days?",
        ),
        (("1/4", "1/2", "1/8", "3/4"), ("1/4", "1/2", "1/8", "3/4"), ("1/4", "1/2", "1/8", "3/4")),
        (0,),
        (
            "8 күнде екі жартылай ыдырау периоды өтеді: 1 → 1/2 → 1/4.",
            "За 8 дней проходят два периода полураспада: 1 → 1/2 → 1/4.",
            "Eight days is two half-lives: 1 → 1/2 → 1/4 remains.",
        ),
        "жартылай ыдырау периоды",
    ),
    _q(
        "nanotechnology-surface-ratio-01", "nanotechnology", "A",
        (
            "Бірдей пішіндегі бөлшектің өлшемін 10 есе кішірейтті. Оның бет ауданының көлемге қатынасы қалай өзгереді?",
            "Размер частицы той же формы уменьшили в 10 раз. Как изменится отношение площади поверхности к объёму?",
            "A particle's dimensions are reduced tenfold without changing its shape. How does its surface-area-to-volume ratio change?",
        ),
        (("10 есе артады", "10 есе кемиді", "100 есе артады", "Өзгермейді"), ("Увеличится в 10 раз", "Уменьшится в 10 раз", "Увеличится в 100 раз", "Не изменится"), ("It increases tenfold", "It decreases tenfold", "It increases a hundredfold", "It stays the same")),
        (0,),
        (
            "Ұқсас пішіндерде бет ауданы өлшемнің квадратымен, ал көлем кубымен өзгереді. Сондықтан бет/көлем қатынасы 10 есе артады.",
            "У подобных тел площадь меняется как квадрат размера, а объём — как куб. Поэтому отношение площади к объёму вырастет в 10 раз.",
            "For similar shapes, area scales as length² and volume as length³. The area-to-volume ratio therefore rises tenfold.",
        ),
        "наноматериал",
    ),
    _q(
        "cosmology-redshift-01", "cosmology", "B",
        (
            "Алыс галактиканың спектрлік сызықтары қызыл жаққа ығысқан. Бұл нені көрсетеді?",
            "Спектральные линии далёкой галактики смещены к красной части спектра. Что это означает?",
            "The spectral lines of a distant galaxy are shifted toward red. What does this indicate?",
        ),
        (("Галактика бізден алыстап барады", "Галактика міндетті түрде жақындап келеді", "Жарық жылдамдығы азайды", "Галактикада жарық жоқ"), ("Галактика удаляется от нас", "Галактика обязательно приближается", "Скорость света уменьшилась", "Галактика не излучает свет"), ("The galaxy is moving away from us", "The galaxy must be approaching", "The speed of light has decreased", "The galaxy emits no light")),
        (0,),
        (
            "Қызыл ығысу жарық толқын ұзындығының ұзарғанын білдіреді. Бұл алыстаған галактикалар үшін кеңейіп жатқан Ғаламның белгісі.",
            "Красное смещение означает увеличение длины волны света. Для далёких галактик это признак расширения Вселенной.",
            "Redshift means the light's wavelength has stretched. For distant galaxies, this is evidence of an expanding universe.",
        ),
        "қызыл ығысу",
    ),
)


_CONTEXT_QUESTIONS = (
    _q(
        "context-solar-heater-energy-01", "energy", "A",
        (
            "Күн коллекторы суды қыздырады. 2 кг судың температурасын 20°C-тан 30°C-қа көтеру үшін қанша жылу қажет? c = 4200 Дж/(кг·°C).",
            "Солнечный коллектор нагревает воду. Сколько теплоты нужно, чтобы нагреть 2 кг воды с 20°C до 30°C? c = 4200 Дж/(кг·°C).",
            "A solar collector heats water. How much heat is needed to warm 2 kg of water from 20°C to 30°C? c = 4200 J/(kg·°C).",
        ),
        (("84 кДж", "8,4 кДж", "42 кДж", "840 кДж"), ("84 кДж", "8,4 кДж", "42 кДж", "840 кДж"), ("84 kJ", "8.4 kJ", "42 kJ", "840 kJ")),
        (0,),
        (
            "Q = cmΔT. Мұнда ΔT = 10°C, сондықтан Q = 4200·2·10 = 84000 Дж = 84 кДж.",
            "Q = cmΔT. Здесь ΔT = 10°C, поэтому Q = 4200·2·10 = 84000 Дж = 84 кДж.",
            "Q = cmΔT. Here ΔT = 10°C, so Q = 4200·2·10 = 84,000 J = 84 kJ.",
        ),
        "меншікті жылусыйымдылық",
        kind="context",
        context=(
            "Мектеп күн коллекторын қолданып, суды жылытады. Есептеулерде судың жылусыйымдылығы 4200 Дж/(кг·°C), g = 10 м/с² деп алыңыз. Жылу шығынын елемеңіз.",
            "Школьный солнечный коллектор нагревает воду. В расчётах примите удельную теплоёмкость воды 4200 Дж/(кг·°C), g = 10 м/с². Потерями тепла пренебрегите.",
            "A school solar collector heats water. Use a specific heat capacity of 4200 J/(kg·°C) for water and g = 10 m/s². Ignore heat losses.",
        ),
    ),
    _q(
        "context-solar-heater-power-02", "energy", "A",
        (
            "Коллектор 84 кДж жылуды 20 минутта береді. Оның орташа қуаты қандай?",
            "Коллектор передал 84 кДж теплоты за 20 минут. Какова его средняя мощность?",
            "The collector transfers 84 kJ of heat in 20 minutes. What is its average power?",
        ),
        (("70 Вт", "700 Вт", "1400 Вт", "7 Вт"), ("70 Вт", "700 Вт", "1400 Вт", "7 Вт"), ("70 W", "700 W", "1400 W", "7 W")),
        (0,),
        (
            "Қуат P = A/t. 20 минут = 1200 с, сондықтан P = 84000/1200 = 70 Вт.",
            "Мощность P = A/t. 20 минут = 1200 с, поэтому P = 84000/1200 = 70 Вт.",
            "Power is P = E/t. 20 minutes is 1200 s, so P = 84,000/1200 = 70 W.",
        ),
        "қуат",
        kind="context",
        context=(
            "Мектеп күн коллекторын қолданып, суды жылытады. Есептеулерде судың жылусыйымдылығы 4200 Дж/(кг·°C), g = 10 м/с² деп алыңыз. Жылу шығынын елемеңіз.",
            "Школьный солнечный коллектор нагревает воду. В расчётах примите удельную теплоёмкость воды 4200 Дж/(кг·°C), g = 10 м/с². Потерями тепла пренебрегите.",
            "A school solar collector heats water. Use a specific heat capacity of 4200 J/(kg·°C) for water and g = 10 m/s². Ignore heat losses.",
        ),
    ),
    _q(
        "context-solar-heater-height-03", "dynamics", "B",
        (
            "Су сорғысы суды 5 м биіктікке көтереді. 2 кг судың ауырлық күшіне қарсы потенциалдық энергиясының өсімін табыңыз.",
            "Насос поднимает воду на высоту 5 м. Найдите прирост потенциальной энергии 2 кг воды относительно силы тяжести.",
            "A pump raises water by 5 m. Find the increase in gravitational potential energy for 2 kg of water.",
        ),
        (("100 Дж", "25 Дж", "50 Дж", "1000 Дж"), ("100 Дж", "25 Дж", "50 Дж", "1000 Дж"), ("100 J", "25 J", "50 J", "1000 J")),
        (0,),
        (
            "Потенциалдық энергия өсімі ΔEₚ = mgh = 2·10·5 = 100 Дж.",
            "Прирост потенциальной энергии ΔEₚ = mgh = 2·10·5 = 100 Дж.",
            "The gain in potential energy is ΔEₚ = mgh = 2·10·5 = 100 J.",
        ),
        "потенциалдық энергия",
        kind="context",
        context=(
            "Мектеп күн коллекторын қолданып, суды жылытады. Есептеулерде судың жылусыйымдылығы 4200 Дж/(кг·°C), g = 10 м/с² деп алыңыз. Жылу шығынын елемеңіз.",
            "Школьный солнечный коллектор нагревает воду. В расчётах примите удельную теплоёмкость воды 4200 Дж/(кг·°C), g = 10 м/с². Потерями тепла пренебрегите.",
            "A school solar collector heats water. Use a specific heat capacity of 4200 J/(kg·°C) for water and g = 10 m/s². Ignore heat losses.",
        ),
    ),
    _q(
        "context-solar-heater-efficiency-04", "energy", "B",
        (
            "Коллектордан 120 кДж энергия алынды, ал су 84 кДж жылу алды. Пайдалы әсер коэффициенті қандай?",
            "Коллектор получил 120 кДж энергии, а вода — 84 кДж теплоты. Каков КПД установки?",
            "The collector receives 120 kJ of energy, and the water gains 84 kJ of heat. What is the system efficiency?",
        ),
        (("70%", "36%", "84%", "143%"), ("70%", "36%", "84%", "143%"), ("70%", "36%", "84%", "143%")),
        (0,),
        (
            "ПӘК η = Eпайдалы/Eенгізілген · 100%. 84/120 · 100% = 70%.",
            "КПД η = Eполезная/Eзатраченная · 100%. 84/120 · 100% = 70%.",
            "Efficiency η = useful energy/input energy × 100%. 84/120 × 100% = 70%.",
        ),
        "пайдалы әсер коэффициенті",
        kind="context",
        context=(
            "Мектеп күн коллекторын қолданып, суды жылытады. Есептеулерде судың жылусыйымдылығы 4200 Дж/(кг·°C), g = 10 м/с² деп алыңыз. Жылу шығынын елемеңіз.",
            "Школьный солнечный коллектор нагревает воду. В расчётах примите удельную теплоёмкость воды 4200 Дж/(кг·°C), g = 10 м/с². Потерями тепла пренебрегите.",
            "A school solar collector heats water. Use a specific heat capacity of 4200 J/(kg·°C) for water and g = 10 m/s². Ignore heat losses.",
        ),
    ),
    _q(
        "context-solar-heater-volume-05", "fluids", "C",
        (
            "Ыдыстағы су бағанының биіктігі 5 м. Ыдыс түбінің ауданы 0,20 м² болса, түбіндегі гидростатикалық қысым қандай?",
            "Высота столба воды в баке равна 5 м. Площадь дна бака 0,20 м². Каково гидростатическое давление на дно?",
            "The water column in a tank is 5 m high. The tank base area is 0.20 m². What is the hydrostatic pressure at the base?",
        ),
        (("50 кПа", "10 кПа", "100 кПа", "25 кПа"), ("50 кПа", "10 кПа", "100 кПа", "25 кПа"), ("50 kPa", "10 kPa", "100 kPa", "25 kPa")),
        (0,),
        (
            "Гидростатикалық қысым p = ρgh. 1000·10·5 = 50000 Па = 50 кПа. Ыдыс ауданы қысымға әсер етпейді.",
            "Гидростатическое давление p = ρgh. 1000·10·5 = 50000 Па = 50 кПа. Площадь бака на давление не влияет.",
            "Hydrostatic pressure is p = ρgh = 1000·10·5 = 50,000 Pa = 50 kPa. The tank area does not affect pressure.",
        ),
        "гидростатикалық қысым",
        kind="context",
        context=(
            "Мектеп күн коллекторын қолданып, суды жылытады. Есептеулерде судың жылусыйымдылығы 4200 Дж/(кг·°C), g = 10 м/с² деп алыңыз. Жылу шығынын елемеңіз.",
            "Школьный солнечный коллектор нагревает воду. В расчётах примите удельную теплоёмкость воды 4200 Дж/(кг·°C), g = 10 м/с². Потерями тепла пренебрегите.",
            "A school solar collector heats water. Use a specific heat capacity of 4200 J/(kg·°C) for water and g = 10 m/s². Ignore heat losses.",
        ),
    ),
)

_MULTI_QUESTIONS = (
    _q(
        "multi-kinematics-velocity-01", "kinematics", "A",
        ("Тұрақты үдеумен қозғалған дене үшін дұрыс тұжырымдарды таңдаңыз.", "Выберите верные утверждения о движении тела с постоянным ускорением.", "Choose the correct statements for an object moving with constant acceleration."),
        (("Үдеу жылдамдықтың өзгеру шапшаңдығын көрсетеді", "Үдеу нөл болса, жылдамдық тұрақты болуы мүмкін", "Үдеу әрқашан қозғалыс бағытымен бағытталады", "Жылдамдықтың SI бірлігі — м/с²"), ("Ускорение показывает скорость изменения скорости", "При нулевом ускорении скорость может быть постоянной", "Ускорение всегда направлено по движению", "Единица скорости в СИ — м/с²"), ("Acceleration measures the rate of change of velocity", "With zero acceleration, velocity can be constant", "Acceleration always points along the motion", "The SI unit of speed is m/s²")),
        (0, 1),
        ("Үдеу жылдамдықтың өзгерісін сипаттайды; a = 0 болса, жылдамдық өзгермейді. Үдеу қозғалысқа қарсы да бағытталуы мүмкін.", "Ускорение описывает изменение скорости; при a = 0 скорость постоянна. Ускорение может быть направлено и против движения.", "Acceleration describes velocity change; if a = 0, velocity stays constant. Acceleration can also point opposite to motion."),
        "үдеу",
        kind="multi",
    ),
    _q(
        "multi-newton-laws-01", "dynamics", "A",
        ("Ньютонның екінші заңы туралы дұрыс тұжырымдарды таңдаңыз.", "Выберите верные утверждения о втором законе Ньютона.", "Choose the correct statements about Newton's second law."),
        (("Қорытқы күш нөл болса, үдеу нөлге тең", "Бірдей массада күш артса, үдеу де артады", "Үдеу күшке кері пропорционал", "Күштің SI бірлігі — джоуль"), ("Если равнодействующая сила равна нулю, ускорение равно нулю", "При одинаковой массе увеличение силы увеличивает ускорение", "Ускорение обратно пропорционально силе", "Единица силы в СИ — джоуль"), ("If the net force is zero, acceleration is zero", "For the same mass, more force means more acceleration", "Acceleration is inversely proportional to force", "The SI unit of force is the joule")),
        (0, 1),
        ("F = ma: үдеу қорытқы күшке тура, массаға кері пропорционал. Күш ньютонмен өлшенеді.", "F = ma: ускорение прямо пропорционально равнодействующей силе и обратно пропорционально массе. Сила измеряется в ньютонах.", "F = ma: acceleration is proportional to net force and inversely proportional to mass. Force is measured in newtons."),
        "қорытқы күш",
        kind="multi",
    ),
    _q(
        "multi-electricity-ohm-01", "electricity", "A",
        ("Тізбектің бір бөлігі үшін Ом заңы орындалғанда дұрыс болатын тұжырымдарды таңдаңыз.", "Выберите верные утверждения для участка цепи, подчиняющегося закону Ома.", "Choose the correct statements for an ohmic part of a circuit."),
        (("I = U/R", "Кедергі тұрақты болса, кернеуді екі есе арттыру токты да екі есе арттырады", "Ток кедергіге тура пропорционал", "Кедергінің SI бірлігі — ампер"), ("I = U/R", "При постоянном сопротивлении удвоение напряжения удваивает ток", "Ток прямо пропорционален сопротивлению", "Единица сопротивления в СИ — ампер"), ("I = U/R", "At fixed resistance, doubling voltage doubles current", "Current is directly proportional to resistance", "The SI unit of resistance is the ampere")),
        (0, 1),
        ("Ом заңы I = U/R. Тұрақты R кезінде I кернеуге тура, ал кедергіге кері пропорционал.", "Закон Ома I = U/R. При постоянном R ток прямо пропорционален напряжению и обратно пропорционален сопротивлению.", "Ohm's law is I = U/R. At fixed R, current is proportional to voltage and inversely proportional to resistance."),
        "Ом заңы",
        kind="multi",
    ),
    _q(
        "multi-energy-conservation-01", "conservation", "B",
        ("Ауа кедергісі еленбейтін жағдайда жоғары лақтырылған дене үшін дұрыс тұжырымдарды таңдаңыз.", "Выберите верные утверждения для тела, брошенного вертикально вверх, если сопротивлением воздуха пренебречь.", "Choose the correct statements for an object thrown vertically upward when air resistance is ignored."),
        (("Механикалық энергия сақталады", "Ең жоғары нүктеде жылдамдық нөл, бірақ үдеу g-ге тең", "Көтерілу кезінде кинетикалық энергия артады", "Төмен түскенде ауырлық күшінің потенциалдық энергиясы артады"), ("Механическая энергия сохраняется", "В верхней точке скорость равна нулю, но ускорение равно g", "При подъёме кинетическая энергия увеличивается", "При падении потенциальная энергия тяжести увеличивается"), ("Mechanical energy is conserved", "At the top, speed is zero but acceleration is g", "Kinetic energy increases while rising", "Gravitational potential energy increases while falling")),
        (0, 1),
        ("Ауа кедергісі жоқ кезде энергия кинетикалық және потенциалдық түрлер арасында алмасады. Жоғарғы нүктеде жылдамдық сәттік нөл болса да, g үдеуі төмен бағытталған.", "Без сопротивления воздуха энергия переходит между кинетической и потенциальной. В верхней точке скорость мгновенно равна нулю, но ускорение g направлено вниз.", "Without air resistance, energy shifts between kinetic and potential forms. At the top, speed is momentarily zero, while acceleration g still points downward."),
        "механикалық энергияның сақталуы",
        kind="multi",
    ),
    _q(
        "multi-wave-optics-01", "wave_optics", "C",
        ("Тұрақты интерференциялық жолақтар байқалуы үшін қажетті шарттарды таңдаңыз.", "Выберите условия, необходимые для наблюдения устойчивой интерференционной картины.", "Choose conditions needed to observe a stable interference pattern."),
        (("Көздер когерентті болуы керек", "Жиіліктері бірдей болуы керек", "Жарық міндетті түрде поляризацияланбаған болуы керек", "Жолақ аралығы тек жарықтың интенсивтілігіне тәуелді"), ("Источники должны быть когерентными", "Частоты источников должны совпадать", "Свет обязательно должен быть неполяризованным", "Расстояние между полосами зависит только от интенсивности света"), ("The sources must be coherent", "The sources must have the same frequency", "The light must be unpolarized", "Fringe spacing depends only on light intensity")),
        (0, 1),
        ("Тұрақты жолақ үшін фазалар айырымы тұрақты болуы қажет; когерентті көздер бірдей жиілікті болады. Жолақ аралығы геометрия мен толқын ұзындығына тәуелді.", "Для устойчивых полос нужна постоянная разность фаз; когерентные источники имеют одинаковую частоту. Ширина полос зависит от длины волны и геометрии опыта.", "A stable pattern needs a constant phase difference; coherent sources have the same frequency. Fringe spacing depends on wavelength and setup geometry."),
        "когерентті толқындар",
        kind="multi",
    ),
)

_MATCHING_QUESTIONS = (
    _q(
        "matching-mechanics-units-01", "mechanics", "A",
        ("Жылдамдық пен күшті олардың SI бірліктерімен сәйкестендіріңіз.", "Сопоставьте скорость и силу с их единицами СИ.", "Match speed and force with their SI units."),
        (("м/с", "Н", "Дж", "Па"), ("м/с", "Н", "Дж", "Па"), ("m/s", "N", "J", "Pa")),
        (0, 1),
        ("Жылдамдық м/с-пен, күш ньютонмен (Н) өлшенеді.", "Скорость измеряют в м/с, силу — в ньютонах (Н).", "Speed is measured in m/s and force in newtons (N)."),
        "халықаралық бірліктер жүйесі",
        kind="matching",
        matching_left=(("Жылдамдық", "Күш"), ("Скорость", "Сила"), ("Speed", "Force")),
    ),
    _q(
        "matching-electricity-units-02", "electricity", "A",
        ("Ток күші мен кедергіні олардың SI бірліктерімен сәйкестендіріңіз.", "Сопоставьте силу тока и сопротивление с их единицами СИ.", "Match current and resistance with their SI units."),
        (("А", "В", "Ом", "Кл"), ("А", "В", "Ом", "Кл"), ("A", "V", "Ω", "C")),
        (0, 2),
        ("Ток күші ампермен, кедергі оммен өлшенеді.", "Силу тока измеряют в амперах, сопротивление — в омах.", "Current is measured in amperes and resistance in ohms."),
        "электр шамасының бірлігі",
        kind="matching",
        matching_left=(("Ток күші", "Кедергі"), ("Сила тока", "Сопротивление"), ("Current", "Resistance")),
    ),
    _q(
        "matching-thermodynamics-processes-03", "thermodynamics", "B",
        ("Изобаралық және изохоралық процестерді тұрақты шамасымен сәйкестендіріңіз.", "Сопоставьте изобарный и изохорный процессы с постоянной величиной.", "Match isobaric and isochoric processes with the quantity held constant."),
        (("Қысым", "Көлем", "Температура", "Ішкі энергия"), ("Давление", "Объём", "Температура", "Внутренняя энергия"), ("Pressure", "Volume", "Temperature", "Internal energy")),
        (0, 1),
        ("Изобаралық процесте қысым, изохоралық процесте көлем тұрақты.", "В изобарном процессе постоянно давление, в изохорном — объём.", "Pressure is constant in an isobaric process, and volume in an isochoric process."),
        "термодинамикалық процесс",
        kind="matching",
        matching_left=(("Изобаралық", "Изохоралық"), ("Изобарный", "Изохорный"), ("Isobaric", "Isochoric")),
    ),
    _q(
        "matching-optics-images-04", "geometric_optics", "C",
        ("Жинағыш линзада екі нысан орнын кескін қасиетімен сәйкестендіріңіз.", "Сопоставьте два положения предмета со свойством изображения в собирающей линзе.", "For a converging lens, match two object positions with image properties."),
        (("Шын, төңкерілген, кішірейген", "Шын, төңкерілген, өлшемі бірдей", "Шын, төңкерілген, үлкейген", "Жалған, тура, үлкейген"), ("Действительное, перевёрнутое, уменьшенное", "Действительное, перевёрнутое, равное по размеру", "Действительное, перевёрнутое, увеличенное", "Мнимое, прямое, увеличенное"), ("Real, inverted, reduced", "Real, inverted, same size", "Real, inverted, enlarged", "Virtual, upright, enlarged")),
        (0, 2),
        ("Жинағыш линзада дене 2F-тен ары болса кескін кішірейеді; F пен 2F арасында үлкейеді.", "У собирающей линзы предмет дальше 2F даёт уменьшенное изображение; между F и 2F — увеличенное.", "For a converging lens, an object beyond 2F gives a reduced image; between F and 2F, an enlarged image."),
        "жинағыш линза",
        kind="matching",
        matching_left=(("Нысан 2F-тен ары", "Нысан F пен 2F арасында"), ("Предмет дальше 2F", "Предмет между F и 2F"), ("Object beyond 2F", "Object between F and 2F")),
    ),
    _q(
        "matching-radiation-05", "nuclear_physics", "C",
        ("Альфа- және бета-сәулелерді олардың бөлшектерімен сәйкестендіріңіз.", "Сопоставьте альфа- и бета-излучение с частицами, из которых они состоят.", "Match alpha and beta radiation with the particles they contain."),
        (("Электрондар ағыны", "Гелий ядролары", "Фотондар", "Нейтрондар ағыны"), ("Поток электронов", "Ядра гелия", "Фотоны", "Поток нейтронов"), ("Electrons", "Helium nuclei", "Photons", "Neutrons")),
        (1, 0),
        ("Альфа-сәуле гелий ядроларынан, бета-сәуле электрондардан тұрады.", "Альфа-излучение состоит из ядер гелия, бета-излучение — из электронов.", "Alpha radiation consists of helium nuclei; beta-minus radiation consists of electrons."),
        "иондаушы сәулелену",
        kind="matching",
        matching_left=(("Альфа-сәуле", "Бета-минус-сәуле"), ("Альфа-излучение", "Бета-минус-излучение"), ("Alpha radiation", "Beta-minus radiation")),
    ),
)

QUESTIONS = tuple(
    replace(question, solution_latex=MOCK_SOLUTIONS[question.id])
    for question in QUESTIONS + _MORE_SINGLE_QUESTIONS + _CONTEXT_QUESTIONS + _MULTI_QUESTIONS + _MATCHING_QUESTIONS
)

# Keep the 40-item, 50-point set above fixed for the full mock exam. The
# additional deterministic variants below are for repeatable topic practice;
# they are original exercises and never appear in the 40-item mock.
def _localized_number(value: float, language: str) -> str:
    rounded = round(float(value), 2)
    text = str(int(rounded)) if rounded.is_integer() else f"{rounded:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if language in {"kk", "ru"} else text


def _exercise_family(
    family_id: str,
    topic: str,
    term: str,
    prompt_templates: tuple[str, str, str],
    cases: tuple[tuple[float, ...], ...],
    formula: str,
    result_unit: str,
    solve,
    distractors,
    show_work,
) -> tuple[PracticeQuestion, ...]:
    items: list[PracticeQuestion] = []
    for index, values in enumerate(cases):
        answer = round(float(solve(*values)), 2)
        wrong = list(distractors(values, answer))
        options = [answer]
        for option in wrong:
            option = round(float(option), 2)
            if option not in options:
                options.append(option)
            if len(options) == 4:
                break
        fallback = 1
        while len(options) < 4:
            candidate = round(answer + fallback * 3.7, 2)
            if candidate not in options:
                options.append(candidate)
            fallback += 1
        # Rotate the correct answer so learners cannot rely on a fixed option.
        rotation = index % 4
        options = options[rotation:] + options[:rotation]
        correct_index = options.index(answer)
        prompt = tuple(
            template.format(*(f"{_localized_number(v, lang)}" for v in values))
            for lang, template in zip(_LANGS, prompt_templates)
        )
        unit_en = {
            "м/с": "m/s", "м": "m", "Н": "N", "Дж": "J", "кПа": "kPa",
            "А": "A", "Вт": "W", "с": "s",
        }.get(result_unit, result_unit)
        option_labels = tuple(
            tuple(
                f"{_localized_number(option, lang)} {unit_en if lang == 'en' else result_unit}"
                for option in options
            )
            for lang in _LANGS
        )
        explanations_list: list[str] = []
        for lang in _LANGS:
            substitution = show_work(values, lang)
            result = _localized_number(answer, lang)
            unit = unit_en if lang == "en" else result_unit
            if lang == "kk":
                explanations_list.append(
                    f"Формула: {formula}. Мәндерді қоямыз: {substitution} = {result} {unit}. "
                    "Жауапты өлшем бірлігімен бірге таңдаңыз."
                )
            elif lang == "ru":
                explanations_list.append(
                    f"Формула: {formula}. Подставляем значения: {substitution} = {result} {unit}. "
                    "Выберите ответ вместе с единицей измерения."
                )
            else:
                explanations_list.append(
                    f"Use {formula}. Substitute the values: {substitution} = {result} {unit}. "
                    "Choose the answer with its unit."
                )
        explanations = tuple(explanations_list)
        difficulty = ("A", "A", "B", "B", "C", "C")[index]
        items.append(_q(
            f"exercise-{family_id}-{index + 1:02d}", topic, difficulty,
            prompt, option_labels, (correct_index,), explanations, term,
        ))
    return tuple(items)


_EXTRA_EXERCISES = (
    _exercise_family(
        "kinematics-speed", "kinematics", "үдеу",
        (
            "Дене бастапқыда {0} м/с жылдамдықпен қозғалады. Үдеуі {1} м/с² болса, {2} секундтан кейінгі жылдамдығын табыңыз.",
            "Тело движется с начальной скоростью {0} м/с и ускорением {1} м/с². Найдите скорость через {2} с.",
            "An object starts at {0} m/s and accelerates at {1} m/s². Find its speed after {2} s.",
        ),
        ((2, 2, 3), (3, 1, 5), (4, 2, 4), (1, 3, 6), (5, 2, 5), (2, 4, 7)),
        "v = v₀ + at", "м/с", lambda v0, a, t: v0 + a * t,
        lambda p, a: (p[1] * p[2], p[0] + p[1], a + p[0]),
        lambda p, lang: f"{_localized_number(p[0], lang)} + {_localized_number(p[1], lang)}·{_localized_number(p[2], lang)}",
    ),
    _exercise_family(
        "kinematics-distance", "kinematics", "бірқалыпты үдемелі қозғалыс",
        (
            "Дене тыныштықтан {0} м/с² үдеумен қозғалады. {1} секундта жүрген жолын табыңыз.",
            "Тело начинает движение из покоя с ускорением {0} м/с². Какой путь оно пройдёт за {1} с?",
            "An object starts from rest and accelerates at {0} m/s². How far does it travel in {1} s?",
        ),
        ((2, 3), (4, 2), (2, 5), (6, 3), (4, 4), (2, 6)),
        "s = at²/2", "м", lambda a, t: 0.5 * a * t * t,
        lambda p, a: (p[0] * p[1], p[0] * p[1] ** 2, 0.5 * p[0] * p[1]),
        lambda p, lang: f"{_localized_number(p[0], lang)}·{_localized_number(p[1], lang)}²/2",
    ),
    _exercise_family(
        "newton-force", "dynamics", "қорытқы күш",
        (
            "Массасы {0} кг дене {1} м/с² үдеумен қозғалады. Қорытқы күшті табыңыз.",
            "Тело массой {0} кг движется с ускорением {1} м/с². Найдите равнодействующую силу.",
            "A {0} kg object accelerates at {1} m/s². Find the net force.",
        ),
        ((2, 3), (4, 5), (6, 2), (3, 8), (5, 4), (7, 3)),
        "F = ma", "Н", lambda m, a: m * a,
        lambda p, a: (p[0] + p[1], max(1, abs(p[0] - p[1])), 2 * a),
        lambda p, lang: f"{_localized_number(p[0], lang)}·{_localized_number(p[1], lang)}",
    ),
    _exercise_family(
        "work", "conservation", "механикалық жұмыс",
        (
            "{0} Н күш денені күш бағытымен {1} м жылжытады. Атқарылған жұмысты табыңыз.",
            "Сила {0} Н перемещает тело на {1} м по направлению силы. Найдите работу.",
            "A {0} N force moves an object {1} m in the force direction. Find the work done.",
        ),
        ((2, 3), (5, 4), (10, 2), (6, 5), (4, 8), (12, 3)),
        "A = Fs", "Дж", lambda f, s: f * s,
        lambda p, a: (p[0] + p[1], max(1, a // 2), 2 * a),
        lambda p, lang: f"{_localized_number(p[0], lang)}·{_localized_number(p[1], lang)}",
    ),
    _exercise_family(
        "kinetic-energy", "conservation", "кинетикалық энергия",
        (
            "Массасы {0} кг дене {1} м/с жылдамдықпен қозғалады. Кинетикалық энергиясын табыңыз.",
            "Тело массой {0} кг движется со скоростью {1} м/с. Найдите его кинетическую энергию.",
            "A {0} kg object moves at {1} m/s. Find its kinetic energy.",
        ),
        ((3, 2), (4, 2), (2, 5), (6, 2), (4, 3), (2, 6)),
        "Eₖ = mv²/2", "Дж", lambda m, v: 0.5 * m * v * v,
        lambda p, a: (p[0] * p[1], p[0] * p[1] ** 2, 2 * a),
        lambda p, lang: f"{_localized_number(p[0], lang)}·{_localized_number(p[1], lang)}²/2",
    ),
    _exercise_family(
        "hydrostatic-pressure", "fluids", "гидростатикалық қысым",
        (
            "Судың тығыздығы 1000 кг/м³. {0} м тереңдіктегі қысымды табыңыз (g = 10 м/с²).",
            "Плотность воды 1000 кг/м³. Найдите давление на глубине {0} м (g = 10 м/с²).",
            "Water has density 1000 kg/m³. Find the pressure at a depth of {0} m (g = 10 m/s²).",
        ),
        ((0.5,), (1,), (1.5,), (2,), (2.5,), (3,)),
        "p = ρgh", "кПа", lambda h: 10 * h,
        lambda p, a: (2 * a, a * 10, max(1, a - 2)),
        lambda p, lang: f"10·{_localized_number(p[0], lang)}",
    ),
    _exercise_family(
        "ohm-current", "electricity", "Ом заңы",
        (
            "Кернеу {0} В, кедергі {1} Ом. Ток күшін табыңыз.",
            "Напряжение равно {0} В, сопротивление — {1} Ом. Найдите силу тока.",
            "The voltage is {0} V and the resistance is {1} Ω. Find the current.",
        ),
        ((12, 3), (18, 6), (20, 4), (24, 8), (30, 5), (16, 4)),
        "I = U/R", "А", lambda u, r: u / r,
        lambda p, a: (p[0] + p[1], p[0] * p[1], p[1] / p[0]),
        lambda p, lang: f"{_localized_number(p[0], lang)}/{_localized_number(p[1], lang)}",
    ),
    _exercise_family(
        "electric-power", "electricity", "электр қуаты",
        (
            "Электр құралы {0} В кернеуде {1} А ток тұтынады. Қуатын табыңыз.",
            "Электроприбор работает при напряжении {0} В и токе {1} А. Найдите его мощность.",
            "An appliance uses a current of {1} A at {0} V. Find its power.",
        ),
        ((12, 2), (6, 3), (20, 2), (24, 3), (9, 4), (15, 2)),
        "P = UI", "Вт", lambda u, i: u * i,
        lambda p, a: (p[0] + p[1], p[0] / p[1], a / 2),
        lambda p, lang: f"{_localized_number(p[0], lang)}·{_localized_number(p[1], lang)}",
    ),
    _exercise_family(
        "heating-water", "thermodynamics", "жылу мөлшері",
        (
            "{0} кг суды {1}°C-қа қыздыру үшін қанша жылу керек? c = 4,2 кДж/(кг·°C).",
            "Сколько теплоты нужно, чтобы нагреть {0} кг воды на {1}°C? c = 4,2 кДж/(кг·°C).",
            "How much heat is needed to warm {0} kg of water by {1}°C? c = 4.2 kJ/(kg·°C).",
        ),
        ((1, 10), (2, 10), (1.5, 10), (0.5, 10), (2, 15), (1, 40)),
        "Q = cmΔT", "кДж", lambda m, dt: 4.2 * m * dt,
        lambda p, a: (a / 2, a + 10, 2 * a),
        lambda p, lang: f"{_localized_number(4.2, lang)}·{_localized_number(p[0], lang)}·{_localized_number(p[1], lang)}",
    ),
    _exercise_family(
        "wave-period", "wave_motion", "тербеліс периоды",
        (
            "Толқын жиілігі {0} Гц. Тербеліс периодын табыңыз.",
            "Частота волны равна {0} Гц. Найдите период колебаний.",
            "A wave has a frequency of {0} Hz. Find its period.",
        ),
        ((2,), (4,), (5,), (10,), (20,), (25,)),
        "T = 1/f", "с", lambda f: 1 / f,
        lambda p, a: (p[0], a / 2, 2 * a),
        lambda p, lang: f"1/{_localized_number(p[0], lang)}",
    ),
)

from aetherlab.services.ent_topic_bank import build_topic_exercises

_GENERATED_EXERCISES = build_topic_exercises()
EXTRA_EXERCISES = tuple(
    PracticeQuestion(
        id=item["id"], topic=item["topic"], difficulty=item["difficulty"],
        prompt=item["prompt"], choices=item["choices"],
        correct_indices=item["correct_indices"], explanation=item["explanation"],
        kazakh_term=item["kazakh_term"], source_note=item["source_note"],
        reuse_status=item["reuse_status"], author=item["author"],
        reviewer=item["reviewer"], language_review_status=item["language_review_status"],
        answer_verification_status=item["answer_verification_status"],
        solution_latex=item["solution_latex"],
    ) for item in _GENERATED_EXERCISES
)
EXERCISES = EXTRA_EXERCISES
EXERCISE_TOTAL = 2500
if len(EXERCISES) != EXERCISE_TOTAL:
    raise RuntimeError(f"Expected {EXERCISE_TOTAL} practice questions, found {len(EXERCISES)}")
if any(sum(q.topic == topic for q in EXERCISES) != 100 for topic in ENT_TOPIC_IDS):
    raise RuntimeError("Each official ENT topic must have exactly 100 practice questions")
if len({question.id for question in EXERCISES}) != len(EXERCISES):
    raise RuntimeError("Practice question IDs must be unique")


def _glossary_item(ru: str, en: str, kk_meaning: str, ru_meaning: str, en_meaning: str) -> dict:
    return {
        "translation": {"kk": "", "ru": ru, "en": en},
        "meaning": {"kk": kk_meaning, "ru": ru_meaning, "en": en_meaning},
    }


GLOSSARY = {
    "үдеу": _glossary_item("ускорение", "acceleration", "Жылдамдықтың уақыт бойынша өзгеруін көрсетеді.", "Показывает, как скорость меняется со временем.", "How quickly velocity changes over time."),
    "бірқалыпты үдемелі қозғалыс": _glossary_item("равноускоренное движение", "uniformly accelerated motion", "Жылдамдық әрбір тең уақыт аралығында бірдей шамаға өзгеретін қозғалыс.", "Движение, при котором скорость за равные промежутки времени меняется на одинаковую величину.", "Motion in which velocity changes by the same amount during equal time intervals."),
    "механикалық жұмыс": _glossary_item("механическая работа", "mechanical work", "Күш әсер еткенде дене орын ауыстырса, күш жұмыс атқарады; осы есепте A = Fs.", "Работа силы при перемещении тела; в этой задаче A = Fs.", "Work done by a force when an object moves; here A = Fs."),
    "еркін түсу үдеуі": _glossary_item("ускорение свободного падения", "gravitational acceleration", "Жерге жақын денелердің төмен құлау үдеуі.", "Ускорение падения тела рядом с Землёй.", "The acceleration of a freely falling object near Earth."),
    "кедергі": _glossary_item("электрическое сопротивление", "electrical resistance", "Өткізгіштің токқа қаншалықты қарсы әсер ететінін сипаттайды.", "Показывает, насколько проводник препятствует току.", "How strongly a conductor opposes electric current."),
    "кинетикалық энергия": _glossary_item("кинетическая энергия", "kinetic energy", "Қозғалысқа байланысты энергия.", "Энергия тела, связанная с его движением.", "Energy an object has because of its motion."),
    "тербеліс периоды": _glossary_item("период колебаний", "period of oscillation", "Бір толық тербеліске кететін уақыт.", "Время одного полного колебания.", "Time for one complete oscillation."),
    "күш моменті": _glossary_item("момент силы", "moment of force", "Күштің денені айналдыру әсерін сипаттайды.", "Показывает, как сила стремится повернуть тело.", "Measures how a force tends to rotate an object."),
    "қысым": _glossary_item("давление", "pressure", "Бетке түсетін күштің ауданға қатынасы.", "Сила, приходящаяся на единицу площади.", "Force applied per unit area."),
    "молекуланың кинетикалық энергиясы": _glossary_item("кинетическая энергия молекулы", "molecular kinetic energy", "Молекуланың қозғалысына байланысты энергия.", "Энергия движения молекулы.", "Energy associated with a molecule's motion."),
    "абсолют температура": _glossary_item("абсолютная температура", "absolute temperature", "Кельвинмен өлшенетін температура.", "Температура, отсчитываемая в кельвинах.", "Temperature measured on the kelvin scale."),
    "жылу мөлшері": _glossary_item("количество теплоты", "heat energy", "Жылу алмасу кезінде берілетін немесе алынатын энергия.", "Энергия, переданная или полученная при теплообмене.", "Energy transferred during heating or cooling."),
    "меншікті балқу жылуы": _glossary_item("удельная теплота плавления", "specific latent heat of fusion", "1 кг затты балқытуға қажет жылу мөлшері.", "Количество теплоты для плавления 1 кг вещества.", "Heat needed to melt one kilogram of a substance."),
    "электр заряды": _glossary_item("электрический заряд", "electric charge", "Денелердің электрлік әсерлесуін сипаттайтын шама.", "Величина, описывающая электрическое взаимодействие тел.", "A property that describes electrical interaction."),
    "ион": _glossary_item("ион", "ion", "Электрон жоғалтқан не қосып алған зарядталған бөлшек.", "Заряженная частица, потерявшая или получившая электроны.", "An atom or group with a net charge after losing or gaining electrons."),
    "магнит өрісі": _glossary_item("магнитное поле", "magnetic field", "Қозғалыстағы зарядтар мен магниттерге әсер ететін өріс.", "Поле, действующее на магниты и движущиеся заряды.", "A field that acts on magnets and moving charges."),
    "электромагниттік индукция": _glossary_item("электромагнитная индукция", "electromagnetic induction", "Магнит ағыны өзгергенде тізбекте кернеу пайда болуы.", "Возникновение напряжения при изменении магнитного потока.", "The production of voltage when magnetic flux changes."),
    "тербеліс жиілігі": _glossary_item("частота колебаний", "frequency of oscillation", "Бір секундтағы толық тербелістер саны.", "Число полных колебаний за одну секунду.", "Number of complete oscillations per second."),
    "әсерлік кернеу": _glossary_item("действующее напряжение", "RMS voltage", "Айнымалы токтың тұрақты токпен бірдей жылулық әсер беретін кернеуі.", "Напряжение переменного тока с таким же тепловым действием, как постоянное.", "The AC voltage equivalent to a DC voltage for heating effect."),
    "электромагниттік толқын": _glossary_item("электромагнитная волна", "electromagnetic wave", "Электр және магнит өрістері таралатын толқын.", "Распространяющееся колебание электрического и магнитного полей.", "A traveling oscillation of electric and magnetic fields."),
    "интерференция": _glossary_item("интерференция", "interference", "Толқындар қосылғанда күшеюі немесе әлсіреуі.", "Усиление или ослабление при сложении волн.", "Reinforcement or cancellation when waves overlap."),
    "сыну көрсеткіші": _glossary_item("показатель преломления", "refractive index", "Жарықтың ортада вакууммен салыстырғанда қаншалық баяу тарайтынын сипаттайды.", "Показывает, насколько свет в среде медленнее, чем в вакууме.", "How much slower light travels in a material than in vacuum."),
    "Лоренц көбейткіші": _glossary_item("фактор Лоренца", "Lorentz factor", "Жарық жылдамдығына жақын қозғалыста уақыт пен ұзындық өзгерісін сипаттайтын көбейткіш.", "Множитель для описания релятивистских эффектов при скоростях, близких к скорости света.", "A factor used to describe relativistic effects near the speed of light."),
    "фотон": _glossary_item("фотон", "photon", "Жарықтың энергия таситын бөлшегі.", "Частица света, переносящая энергию.", "A particle of light that carries energy."),
    "жартылай ыдырау периоды": _glossary_item("период полураспада", "half-life", "Радиоактивті ядролар саны екі есе азаятын уақыт.", "Время, за которое число радиоактивных ядер уменьшается вдвое.", "Time for half of the radioactive nuclei to decay."),
    "наноматериал": _glossary_item("наноматериал", "nanomaterial", "Өлшемі нанометр шамасында болатын құрылымды материал.", "Материал со структурой размером порядка нанометров.", "A material with structural features around the nanometer scale."),
    "қызыл ығысу": _glossary_item("красное смещение", "redshift", "Жарық толқынының ұзындығының қызыл жаққа қарай ұзаруы.", "Смещение света к большим длинам волн, к красной части спектра.", "A shift of light toward longer, redder wavelengths."),
    "меншікті жылусыйымдылық": _glossary_item("удельная теплоёмкость", "specific heat capacity", "1 кг заттың температурасын 1°C-қа өзгертуге қажет жылу.", "Количество теплоты для изменения температуры 1 кг вещества на 1°C.", "Heat required to change 1 kg of a substance by 1°C."),
    "қуат": _glossary_item("мощность", "power", "Жұмыстың немесе энергияның уақыт бойынша өзгеру шапшаңдығы.", "Работа или энергия за единицу времени.", "Work done or energy transferred per unit time."),
    "потенциалдық энергия": _glossary_item("потенциальная энергия", "potential energy", "Дененің орнына немесе күйіне байланысты энергия.", "Энергия, связанная с положением или состоянием тела.", "Energy associated with an object's position or configuration."),
    "пайдалы әсер коэффициенті": _glossary_item("коэффициент полезного действия", "efficiency", "Пайдалы алынған энергияның енгізілген энергияға қатынасы.", "Отношение полезной энергии к затраченной.", "Useful output energy divided by input energy."),
    "гидростатикалық қысым": _glossary_item("гидростатическое давление", "hydrostatic pressure", "Тыныш тұрған сұйықтың салмағынан пайда болатын қысым.", "Давление, создаваемое покоящейся жидкостью.", "Pressure caused by a fluid at rest."),
    "электр қуаты": _glossary_item("электрическая мощность", "electric power", "Электр тогының бір секундта атқаратын жұмысы; тұрақты токта P = UI.", "Работа электрического тока за единицу времени; для этой цепи P = UI.", "Electrical work per unit time; for this circuit, P = VI."),
    "қорытқы күш": _glossary_item("равнодействующая сила", "net force", "Денеге әсер ететін барлық күштердің векторлық қосындысы.", "Векторная сумма всех сил, действующих на тело.", "The vector sum of all forces acting on an object."),
    "Ом заңы": _glossary_item("закон Ома", "Ohm's law", "Кернеу, ток және кедергіні байланыстыратын I = U/R қатынасы.", "Связь напряжения, тока и сопротивления: I = U/R.", "The relation I = V/R between voltage, current, and resistance."),
    "механикалық энергияның сақталуы": _glossary_item("сохранение механической энергии", "conservation of mechanical energy", "Кедергі күштері жоқ кезде кинетикалық және потенциалдық энергия қосындысы тұрақты.", "Без сил сопротивления сумма кинетической и потенциальной энергий постоянна.", "Without dissipative forces, kinetic plus potential energy stays constant."),
    "когерентті толқындар": _glossary_item("когерентные волны", "coherent waves", "Жиілігі бірдей және фазалар айырымы тұрақты толқындар.", "Волны одной частоты с постоянной разностью фаз.", "Waves of the same frequency with a constant phase difference."),
    "халықаралық бірліктер жүйесі": _glossary_item("Международная система единиц", "International System of Units", "Физикалық шамаларды ортақ стандартты бірліктермен өлшеу жүйесі.", "Система стандартных единиц для физических величин.", "A shared standard system for measuring physical quantities."),
    "электр шамасының бірлігі": _glossary_item("единица электрической величины", "electrical unit", "Электр шамасын өлшеуге арналған стандартты бірлік.", "Стандартная единица для измерения электрической величины.", "A standard unit used to measure an electrical quantity."),
    "термодинамикалық процесс": _glossary_item("термодинамический процесс", "thermodynamic process", "Газдың күйі өзгергенде қысым, көлем не температураның өзгеру жолы.", "Изменение состояния газа с постоянством или изменением давления, объёма и температуры.", "A change in a gas state involving pressure, volume, and temperature."),
    "жинағыш линза": _glossary_item("собирающая линза", "converging lens", "Параллель сәулелерді фокусқа жинайтын линза.", "Линза, собирающая параллельные лучи в фокусе.", "A lens that brings parallel rays together at a focus."),
    "иондаушы сәулелену": _glossary_item("ионизирующее излучение", "ionizing radiation", "Атомдардан электрон жұлып, ион түзе алатын сәулелену.", "Излучение, способное выбивать электроны и создавать ионы.", "Radiation energetic enough to remove electrons and create ions."),
}

GLOSSARY.update({
    "Лоренц күші": _glossary_item("сила Лоренца", "Lorentz force", "Магнит өрісінде қозғалған зарядқа әсер ететін күш.", "Сила, действующая на движущийся заряд в магнитном поле.", "The magnetic force acting on a moving electric charge."),
    "газ заңы": _glossary_item("газовый закон", "gas law", "Газдың қысымы, көлемі және температурасы қалай байланысатынын көрсететін ереже.", "Правило, связывающее давление, объём и температуру газа.", "A rule relating a gas's pressure, volume, and temperature."),
    "жартылай ыдырау": _glossary_item("период полураспада", "half-life", "Радиоактивті ядролар саны екі есе азаятын уақыт.", "Время, за которое число радиоактивных ядер уменьшается вдвое.", "Time for half of the radioactive nuclei to decay."),
    "индукция ЭҚК-і": _glossary_item("ЭДС индукции", "induced emf", "Магнит ағыны өзгергенде тізбекте пайда болатын кернеу.", "Напряжение, возникающее в цепи при изменении магнитного потока.", "Voltage produced in a circuit when magnetic flux changes."),
    "интерференциялық жолақ аралығы": _glossary_item("расстояние между интерференционными полосами", "fringe spacing", "Экрандағы екі көршілес жарық жолақтың арақашықтығы.", "Расстояние между соседними светлыми полосами на экране.", "Distance between neighbouring bright fringes on a screen."),
    "кескін қашықтығы": _glossary_item("расстояние до изображения", "image distance", "Линзадан пайда болған кескінге дейінгі арақашықтық.", "Расстояние от линзы до полученного изображения.", "Distance from a lens to the image it forms."),
    "күш": _glossary_item("сила", "force", "Дененің қозғалысын немесе пішінін өзгерте алатын әсер.", "Воздействие, которое может изменить движение или форму тела.", "An influence that can change an object's motion or shape."),
    "нанометр": _glossary_item("нанометр", "nanometre", "Өте кішкентай ұзындық бірлігі: 1 нм = 10⁻⁹ м.", "Очень малая единица длины: 1 нм = 10⁻⁹ м.", "A very small unit of length: 1 nm = 10⁻⁹ m."),
    "орташа кинетикалық энергия": _glossary_item("средняя кинетическая энергия", "mean kinetic energy", "Газ молекулаларының қозғалыс энергиясының орташа мәні.", "Среднее значение энергии движения молекул газа.", "The average energy of motion of gas molecules."),
    "серіппе периоды": _glossary_item("период пружинного маятника", "spring oscillation period", "Серіппеге ілінген дененің бір толық тербеліс жасау уақыты.", "Время одного полного колебания груза на пружине.", "Time for one complete oscillation of a mass on a spring."),
    "ток күші": _glossary_item("сила тока", "electric current", "Өткізгіш қимасы арқылы бір секундта өтетін заряд мөлшері.", "Количество заряда, проходящее через сечение проводника за секунду.", "Amount of charge passing a conductor's cross-section each second."),
    "толқын жылдамдығы": _glossary_item("скорость волны", "wave speed", "Толқынның таралу қашықтығының уақытқа қатынасы.", "Расстояние, которое проходит волна за единицу времени.", "Distance a wave travels per unit of time."),
    "толқын ұзындығы": _glossary_item("длина волны", "wavelength", "Толқынның бірдей фазадағы жақын екі нүктесінің арасы.", "Расстояние между ближайшими точками волны в одинаковой фазе.", "Distance between nearest points in the same phase of a wave."),
    "фотон энергиясы": _glossary_item("энергия фотона", "photon energy", "Жарықтың бір фотоны алып жүретін энергиясы.", "Энергия, переносимая одним фотоном света.", "Energy carried by one photon of light."),
    "электр күші": _glossary_item("электрическая сила", "electric force", "Зарядталған денелердің бір-біріне әсер ету күші.", "Сила взаимодействия между электрическими зарядами.", "The force of interaction between electric charges."),
    "электролиз массасы": _glossary_item("масса при электролизе", "electrolysis mass", "Электр тогы өткенде электродта бөлінетін заттың массасы.", "Масса вещества, выделившегося на электроде при прохождении тока.", "Mass of material deposited at an electrode by electric current."),
})

for _term, _item in GLOSSARY.items():
    _item["translation"]["kk"] = _term


def questions_for_language(language: str, topic: str | None = None) -> tuple[dict, ...]:
    """Return the full exercise bank in the selected language, optionally filtered by topic."""
    from aetherlab.core.language import normalize_language

    code = normalize_language(language)
    selected_topic = canonical_topic(topic) if topic else None
    return tuple(_localized_question(q, code)
        for q in EXERCISES
        if selected_topic is None or canonical_topic(q.topic) == selected_topic
    )


def _localized_question(q: PracticeQuestion, code: str) -> dict:
    return {
            "id": q.id,
            "topic": canonical_topic(q.topic),
            "difficulty": q.difficulty,
            "kind": q.kind,
            "prompt": q.prompt[code],
            "choices": q.choices[code],
            "correct_indices": q.correct_indices,
            "answer": (
                " · ".join(q.choices[code][i] for i in q.correct_indices)
                if q.kind != "matching" else " · ".join(
                    f"{q.matching_left[code][row]} → {q.choices[code][choice]}"
                    for row, choice in enumerate(q.correct_indices)
                )
            ),
            "explanation": q.explanation[code],
            "kazakh_term": q.kazakh_term,
            "context": q.context[code] if q.context else "",
            "matching_left": q.matching_left[code] if q.matching_left else (),
            "source_note": q.source_note,
            "reuse_status": q.reuse_status,
            "author": q.author,
            "reviewer": q.reviewer,
            "language_review_status": q.language_review_status,
            "answer_verification_status": q.answer_verification_status,
            "solution_latex": q.solution_latex,
        }


def mock_questions_for_language(language: str, topic: str | None = None) -> tuple[dict, ...]:
    """Return only the fixed 40-question, 50-point UNT mock form."""
    from aetherlab.core.language import normalize_language

    code = normalize_language(language)
    selected_topic = canonical_topic(topic) if topic else None
    return tuple(
        _localized_question(question, code) for question in QUESTIONS
        if selected_topic is None or canonical_topic(question.topic) == selected_topic
    )


def glossary_for_language(language: str) -> tuple[dict[str, str], ...]:
    """Kazakh terms with their translation and a student-friendly definition."""
    from aetherlab.core.language import normalize_language

    code = normalize_language(language)
    return tuple(
        {
            "term_kk": term,
            "translation": item["translation"][code],
            "meaning": item["meaning"][code],
        }
        for term, item in GLOSSARY.items()
    )
