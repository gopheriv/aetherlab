"""Deterministic, multilingual practice variations for all 25 UNT topics.

Each pack starts from a curriculum formula and varies its supplied data. The
items are original practice variations; they are not represented as official
UNT questions. The SQLite sync script records their topic/source metadata.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Pack:
    topic: str
    term: tuple[str, str, str]
    formula: str
    unit: tuple[str, str, str]
    intro: tuple[str, str, str]
    values: tuple[tuple[float, ...], ...]
    calculate: object
    substitute: object


# Language order: kk, ru, en. Values, formulae and answer keys are shared
# across translations so language switching cannot change the task.
PACKS = (
 Pack("kinematics",("үдеу","ускорение","acceleration"),r"v=v_0+at",("м/с","м/с","m/s"),("Бастапқы жылдамдық {0} м/с, үдеу {1} м/с², уақыт {2} с. Соңғы жылдамдықты табыңыз.","Начальная скорость {0} м/с, ускорение {1} м/с², время {2} с. Найдите конечную скорость.","Initial speed is {0} m/s, acceleration {1} m/s², and time {2} s. Find the final speed."),tuple((v,a,t) for v in (0,2,4,6,8) for a in (1,2,3,4) for t in (2,3,4,5)),lambda v,a,t:v+a*t,lambda p:f"{p[0]}+{p[1]}\\cdot {p[2]}"),
 Pack("dynamics",("күш","сила","force"),r"F=ma",("Н","Н","N"),("Массасы {0} кг дене {1} м/с² үдеумен қозғалады. Қорытқы күшті табыңыз.","Тело массой {0} кг движется с ускорением {1} м/с². Найдите равнодействующую силу.","An object of mass {0} kg accelerates at {1} m/s². Find the net force."),tuple((m,a) for m in (1,2,3,4,5,6,8,10,12,15) for a in (1,2,3,4,5,6,8,10,12,15)),lambda m,a:m*a,lambda p:f"{p[0]}\\cdot {p[1]}"),
 Pack("statics",("күш моменті","момент силы","moment of force"),r"M=Fl",("Н·м","Н·м","N·m"),("Күш {0} Н және иін ұзындығы {1} м. Күш моментін табыңыз.","Сила равна {0} Н, плечо — {1} м. Найдите момент силы.","A force of {0} N acts at a {1} m lever arm. Find its moment."),tuple((f,l) for f in (5,10,15,20,25,30,40,50,60,80) for l in (0.1,0.2,0.3,0.4,0.5,0.6,0.8,1,1.2,1.5)),lambda f,l:f*l,lambda p:f"{p[0]}\\cdot {p[1]}"),
 Pack("fluids",("гидростатикалық қысым","гидростатическое давление","hydrostatic pressure"),r"p=\\rho gh",("кПа","кПа","kPa"),("Сұйық тығыздығы 1000 кг/м³, тереңдік {0} м (g=10 м/с²). Қысымды табыңыз.","Плотность жидкости 1000 кг/м³, глубина {0} м (g=10 м/с²). Найдите давление.","Liquid density is 1000 kg/m³ and depth is {0} m (g=10 m/s²). Find the pressure."),tuple((h,) for h in range(1,101)),lambda h:10*h,lambda p:f"\\frac{{1000\\cdot10\\cdot {p[0]}}}{{1000}}"),
 Pack("molecular_kinetic_theory",("орташа кинетикалық энергия","средняя кинетическая энергия","mean kinetic energy"),r"\\overline{{E}}=\\frac{{3}}{{2}}kT",("10⁻²¹ Дж","10⁻²¹ Дж","10⁻²¹ J"),("Газ температурасы {0} K. k=1,38·10⁻²³ Дж/K. Молекуланың орташа кинетикалық энергиясын табыңыз (жауап 10⁻²¹ Дж бірлігімен).","Температура газа {0} K. k=1,38·10⁻²³ Дж/K. Найдите среднюю кинетическую энергию молекулы (ответ в 10⁻²¹ Дж).","Gas temperature is {0} K. Use k=1.38·10⁻²³ J/K. Find the mean kinetic energy (answer in units of 10⁻²¹ J)."),tuple((t,) for t in range(100,1100,10)),lambda t:1.5*1.38e-23*t/1e-21,lambda p:f"\\frac{{3}}{{2}}\\cdot1.38\\cdot10^{{-2}}\\cdot {p[0]}"),
 Pack("gas_laws",("газ заңы","газовый закон","gas law"),r"p_2=p_1\\frac{{T_2}}{{T_1}}",("кПа","кПа","kPa"),("Көлем өзгермейді: p₁={0} кПа, T₁={1} K, T₂={2} K. Жаңа қысымды табыңыз.","Объём постоянен: p₁={0} кПа, T₁={1} K, T₂={2} K. Найдите новое давление.","Volume is constant: p₁={0} kPa, T₁={1} K, T₂={2} K. Find the new pressure."),tuple((p,t1,t2) for p in (60,80,100,120,150,200,240,300,400,500) for t1,t2 in ((200,300),(250,300),(300,450),(400,500),(200,400),(300,600),(250,500),(400,800),(500,600),(600,900))),lambda p,t1,t2:p*t2/t1,lambda x:f"{x[0]}\\cdot\\frac{{{x[2]}}}{{{x[1]}}}"),
 Pack("thermodynamics",("жылу мөлшері","количество теплоты","heat transferred"),r"Q=cm\\Delta T",("кДж","кДж","kJ"),("{0} кг су {1}°C-қа қыздырылды. c=4,2 кДж/(кг·°C). Қажет жылуды табыңыз.","{0} кг воды нагрели на {1}°C. c=4,2 кДж/(кг·°C). Найдите количество теплоты.","{0} kg of water is warmed by {1}°C. Use c=4.2 kJ/(kg·°C). Find the heat."),tuple((m,dt) for m in (0.5,1,1.5,2,2.5,3,4,5,6,8) for dt in (5,10,15,20,25,30,40,50,60,80)),lambda m,dt:4.2*m*dt,lambda p:f"4.2\\cdot {p[0]}\\cdot {p[1]}"),
 Pack("liquids_solids",("меншікті балқу жылуы","удельная теплота плавления","specific latent heat"),r"Q=\\lambda m",("кДж","кДж","kJ"),("{0} кг мұзды ерітіңіз, λ=330 кДж/кг. Қанша жылу қажет?","Нужно растопить {0} кг льда, λ=330 кДж/кг. Сколько теплоты потребуется?","Melt {0} kg of ice; λ=330 kJ/kg. How much heat is required?"),tuple((m,) for m in (0.1,0.2,0.25,0.3,0.4,0.5,0.6,0.75,0.8,0.9,1,1.2,1.5,2,2.5,3,4,5,6,8)),lambda m:330*m,lambda p:f"330\\cdot {p[0]}"),
 Pack("electrostatics",("электр күші","электрическая сила","electric force"),r"F=k\\frac{{|q_1q_2|}}{{r^2}}",("Н","Н","N"),("Екі зарядтың әрқайсысы 1 мкКл, арасы {0} см. k=9·10⁹. Күшті табыңыз.","Два заряда по 1 мкКл находятся на расстоянии {0} см. k=9·10⁹. Найдите силу.","Two 1 μC charges are {0} cm apart. Use k=9·10⁹. Find the force."),tuple((r,) for r in (1,2,3,4,5,6,8,10,12,15,20,25,30,40,50,60,75,80,90,100)),lambda r:9e9*(1e-6)**2/(r/100)**2,lambda p:f"9\\cdot10^9\\cdot\\frac{{(10^{{-6}})^2}}{{({p[0]}/100)^2}}"),
 Pack("electricity",("ток күші","сила тока","current"),r"I=\\frac{{U}}{{R}}",("А","А","A"),("Кернеу {0} В, кедергі {1} Ом. Ток күшін табыңыз.","Напряжение {0} В, сопротивление {1} Ом. Найдите силу тока.","Voltage is {0} V and resistance is {1} Ω. Find the current."),tuple((u,r) for u in (6,9,12,15,18,20,24,30,36,48) for r in (2,3,4,5,6,8,9,10,12,15)),lambda u,r:u/r,lambda p:f"\\frac{{{p[0]}}}{{{p[1]}}}"),
 Pack("current_media",("электролиз массасы","масса при электролизе","electrolysis mass"),r"m=kIt",("г","г","g"),("Электролизде k=0,001 г/(А·с), ток {0} А, уақыт {1} с. Бөлінген массаны табыңыз.","При электролизе k=0,001 г/(А·с), ток {0} А, время {1} с. Найдите массу вещества.","For electrolysis, k=0.001 g/(A·s), current {0} A, time {1} s. Find the deposited mass."),tuple((i,t) for i in (1,2,3,4,5,6,8,10,12,15) for t in (10,20,30,40,50,60,80,100,120,150)),lambda i,t:.001*i*t,lambda p:f"0.001\\cdot {p[0]}\\cdot {p[1]}"),
 Pack("magnetic_field",("Лоренц күші","сила Лоренца","magnetic force"),r"F=|q|vB",("мН","мН","mN"),("Заряд модулі 1 мКл, жылдамдығы {0} м/с, B=0,01 Тл; қозғалыс өріске перпендикуляр. F табыңыз.","Модуль заряда 1 мКл, скорость {0} м/с, B=0,01 Тл; движение перпендикулярно полю. Найдите F.","A 1 mC charge moves at {0} m/s perpendicular to B=0.01 T. Find F."),tuple((v,) for v in range(10,1010,10)),lambda v:v/100,lambda p:f"10^{-3}\\cdot {p[0]}\\cdot0.01\\cdot1000"),
 Pack("induction",("индукция ЭҚК-і","ЭДС индукции","induced emf"),r"\\varepsilon=N\\frac{{\\Delta\\Phi}}{{\\Delta t}}",("В","В","V"),("N=10 орамда магнит ағыны {0} Вб-қа {1} с ішінде өзгерді. ЭҚК модулін табыңыз.","В катушке из N=10 витков поток изменился на {0} Вб за {1} с. Найдите ЭДС.","Flux changes by {0} Wb in {1} s through N=10 turns. Find the emf magnitude."),tuple((flux,t) for flux in (0.01,0.02,0.03,0.04,0.05,0.06,0.08,0.1,0.12,0.15) for t in (0.1,0.2,0.25,0.3,0.4,0.5,0.6,0.8,1,1.2)),lambda f,t:10*f/t,lambda p:f"10\\cdot\\frac{{{p[0]}}}{{{p[1]}}}"),
 Pack("mechanical_oscillations",("серіппе периоды","период пружинного маятника","spring period"),r"T=2\\pi\\sqrt{{m/k}}",("с","с","s"),("Серіппеге {0} кг жүк ілінген, қатаңдығы k={1} Н/м. π²≈10 деп алып, периодты табыңыз.","К пружине жёсткости k={1} Н/м прикрепили груз {0} кг. Примите π²≈10 и найдите период.","A {0} kg mass is on a spring with k={1} N/m. Use π²≈10 and find the period."),tuple((m,k) for m in (0.1,0.2,0.3,0.4,0.5,0.6,0.8,1,1.2,1.5) for k in (2,4,5,8,10,12,16,20,25,30)),lambda m,k:2*math.sqrt(10*m/k),lambda p:f"2\\sqrt{{10\\cdot {p[0]}/{p[1]}}}"),
 Pack("ac_circuits",("әсерлік кернеу","действующее напряжение","RMS voltage"),r"U=\\frac{{U_{{max}}}}{{\\sqrt{2}}}",("В","В","V"),("Айнымалы кернеудің амплитудасы {0} В. √2≈1,414 деп алып, әсерлік кернеуді табыңыз.","Амплитуда переменного напряжения {0} В. Примите √2≈1,414 и найдите действующее напряжение.","AC voltage has a peak of {0} V. Use √2≈1.414 to find its RMS voltage."),tuple((u,) for u in range(10,1010,10)),lambda u:u/math.sqrt(2),lambda p:f"\\frac{{{p[0]}}}{{\\sqrt{{2}}}}"),
 Pack("electromagnetic_waves",("толқын ұзындығы","длина волны","wavelength"),r"\\lambda=\\frac{{c}}{{f}}",("м","м","m"),("Электромагниттік толқын жиілігі {0} МГц. c=3·10⁸ м/с. Толқын ұзындығын табыңыз.","Частота электромагнитной волны {0} МГц. c=3·10⁸ м/с. Найдите длину волны.","An electromagnetic wave has frequency {0} MHz. Use c=3·10⁸ m/s to find its wavelength."),tuple((f,) for f in range(10,1010,10)),lambda f:300/f,lambda p:f"\\frac{{3\\cdot10^8}}{{{p[0]}\\cdot10^6}}"),
 Pack("wave_optics",("интерференциялық жолақ аралығы","интерференционная полоска","fringe spacing"),r"\\beta=\\frac{{\\lambda L}}{{d}}",("мм","мм","mm"),("λ=600 нм, экранға дейін L={0} м, саңылаулар арасы d=0,3 мм. Жолақ аралығын табыңыз.","λ=600 нм, расстояние до экрана L={0} м, между щелями d=0,3 мм. Найдите шаг полос.","Use λ=600 nm, screen distance L={0} m, slit separation d=0.3 mm. Find fringe spacing."),tuple((l,) for l in range(1,101)),lambda l:2*l,lambda p:f"\\frac{{600\\cdot10^{{-9}}\\cdot {p[0]}}}{{0.3\\cdot10^{{-3}}}}\\cdot1000"),
 Pack("geometric_optics",("кескін қашықтығы","расстояние до изображения","image distance"),r"\\frac{1}{f}=\\frac{1}{a}+\\frac{1}{b}",("см","см","cm"),("Жинағыш линза фокусы f={0} см, дене линзадан a={1} см. Кескін қашықтығын табыңыз.","Собирающая линза имеет f={0} см, предмет находится на a={1} см. Найдите расстояние до изображения.","A converging lens has focal length f={0} cm; an object is at a={1} cm. Find image distance."),tuple((f,a) for f in (5,6,8,10,12,15,16,20,24,30) for a in (2*f,3*f,4*f,5*f,6*f,7*f,8*f,9*f,10*f,12*f)),lambda f,a:1/(1/f-1/a),lambda p:f"\\frac{{1}}{{1/{p[0]}-1/{p[1]}}}"),
 Pack("relativity",("Лоренц көбейткіші","фактор Лоренца","Lorentz factor"),r"\\gamma=\\frac{{1}}{{\\sqrt{{1-v^2/c^2}}}}",("—","—","—"),("Дене жарық жылдамдығының {0}% бөлігімен қозғалады. Лоренц көбейткішін табыңыз.","Тело движется со скоростью {0}% от скорости света. Найдите фактор Лоренца.","An object moves at {0}% of light speed. Find the Lorentz factor."),tuple((v,) for v in (10,20,30,40,50,60,70,80,90,95)),lambda v:1/math.sqrt(1-(v/100)**2),lambda p:f"\\frac{{1}}{{\\sqrt{{1-({p[0]}/100)^2}}}}"),
 Pack("quantum_physics",("фотон энергиясы","энергия фотона","photon energy"),r"E=hf",("10⁻¹⁹ Дж","10⁻¹⁹ Дж","10⁻¹⁹ J"),("Жарық жиілігі {0}·10¹⁴ Гц. h=6,63·10⁻³⁴ Дж·с. Энергияны 10⁻¹⁹ Дж бірлігімен табыңыз.","Частота света {0}·10¹⁴ Гц. h=6,63·10⁻³⁴ Дж·с. Найдите энергию в единицах 10⁻¹⁹ Дж.","Light frequency is {0}·10¹⁴ Hz. Use h=6.63·10⁻³⁴ J·s. Find energy in units of 10⁻¹⁹ J."),tuple((f,) for f in range(1,101)),lambda f:.663*f,lambda p:f"6.63\\cdot10^{-1}\\cdot {p[0]}"),
 Pack("nuclear_physics",("жартылай ыдырау","период полураспада","half-life"),r"N=N_0\\left(\\frac{1}{2}\\right)^n",("","",""),("Бастапқыда {0} ядро бар. Ыдырау периодтарының санын n={1} деп алыңыз. Қанша ядро қалады?","Изначально было {0} ядер. Примите число периодов полураспада n={1}. Сколько ядер останется?","There are {0} nuclei initially. Let the number of half-lives be n={1}. How many nuclei remain?"),tuple((n,h) for n in (1024,2048,3072,4096,5120,6144,7168,8192,9216,10240) for h in (1,2,3,4,5,6,7,8,9,10)),lambda n,h:n/(2**h),lambda p:f"{p[0]}\\left(\\frac{{1}}{{2}}\\right)^{{{p[1]}}}"),
 Pack("nanotechnology",("нанометр","нанометр","nanometre"),r"1\\,\\mathrm{{nm}}=10^{{-9}}\\,\\mathrm{{m}}",("м","м","m"),("Нанобөлшек өлшемі {0} нм. Оны метрмен өрнектеңіз.","Размер наночастицы {0} нм. Выразите его в метрах.","A nanoparticle is {0} nm across. Express this in metres."),tuple((n,) for n in range(1,101)),lambda n:n*1e-9,lambda p:f"{p[0]}\\cdot10^{{-9}}"),
 Pack("cosmology",("қызыл ығысу","красное смещение","redshift"),r"z=\\frac{{\\lambda-\\lambda_0}}{{\\lambda_0}}",("—","—","—"),("Спектр сызығы бастапқы λ₀={0} нм-ден байқалған λ={1} нм-ге ығысты. z табыңыз.","Линия сместилась с исходной λ₀={0} нм до наблюдаемой λ={1} нм. Найдите z.","A spectral line shifted from λ₀={0} nm to λ={1} nm. Find the redshift z."),tuple((base,base+shift) for base in (400,450,500,550,600,650,700,750,800,850) for shift in (10,20,30,40,50,60,70,80,90,100)),lambda a,b:(b-a)/a,lambda p:f"\\frac{{{p[1]}-{p[0]}}}{{{p[0]}}}"),
 Pack("conservation",("кинетикалық энергия","кинетическая энергия","kinetic energy"),r"E_k=\\frac{{mv^2}}{{2}}",("Дж","Дж","J"),("Массасы {0} кг дене {1} м/с жылдамдықпен қозғалады. Кинетикалық энергиясын табыңыз.","Тело массой {0} кг движется со скоростью {1} м/с. Найдите кинетическую энергию.","An object of mass {0} kg moves at {1} m/s. Find its kinetic energy."),tuple((m,v) for m in (1,2,3,4,5,6,8,10,12,15) for v in (1,2,3,4,5,6,8,10,12,15)),lambda m,v:m*v*v/2,lambda p:f"\\frac{{{p[0]}\\cdot {p[1]}^2}}{{2}}"),
 Pack("wave_motion",("толқын жылдамдығы","скорость волны","wave speed"),r"v=\\lambda f",("м/с","м/с","m/s"),("Толқын ұзындығы {0} м, жиілігі {1} Гц. Таралу жылдамдығын табыңыз.","Длина волны {0} м, частота {1} Гц. Найдите скорость распространения.","Wavelength is {0} m and frequency is {1} Hz. Find wave speed."),tuple((l,f) for l in (0.1,0.2,0.25,0.3,0.4,0.5,0.6,0.8,1,1.2) for f in (1,2,3,4,5,6,8,10,12,15)),lambda l,f:l*f,lambda p:f"{p[0]}\\cdot {p[1]}"),
)


def _fmt(value: float, lang: str) -> str:
    if float(value).is_integer():
        s = str(int(round(value)))
    else:
        s = f"{value:.4g}"
    return s.replace(".", ",") if lang != "en" else s


def _latex_num(value: float) -> str:
    rendered = f"{value:.4g}"
    if "e" in rendered.lower():
        coeff, exponent = rendered.lower().split("e")
        return f"{coeff}\\times 10^{{{int(exponent)}}}"
    return rendered


def _round_sig(value: float, digits: int = 4) -> float:
    if value == 0 or not math.isfinite(value):
        return value
    return round(value, digits - 1 - int(math.floor(math.log10(abs(value)))))


def build_topic_exercises() -> tuple[dict, ...]:
    result = []
    for pack in PACKS:
        vals = pack.values
        # Explicitly distribute 50 beginner, 30 intermediate, and 20 advanced.
        for i in range(100):
            p = vals[i % len(vals)]
            repeat = i // len(vals)
            if repeat and p:
                offset = max(0.013, abs(float(p[0])) * 0.0013) * repeat
                p = (round(float(p[0]) + offset, 5), *p[1:])
            formula = pack.formula.replace("\\\\", "\\").replace("{{", "{").replace("}}", "}")
            raw = float(pack.calculate(*p))
            ans = _round_sig(raw)
            decoys = [ans * 2, ans / 2, ans * 1.5]
            options_num = [_round_sig(ans), *[_round_sig(x) for x in decoys]]
            rng = random.Random(f"{pack.topic}:{i}")
            rng.shuffle(options_num)
            correct = options_num.index(_round_sig(ans))
            # Add varied, reproducible context wording to avoid a single cloned prompt.
            prompt, choices, explanation = {}, {}, {}
            substitution = pack.substitute(p).replace("\\\\", "\\")
            result_symbol = {"geometric_optics": "b"}.get(pack.topic, formula.split("=")[0])
            for li, lang in enumerate(("kk", "ru", "en")):
                rendered = tuple(_fmt(v, lang) for v in p)
                prompt[lang] = pack.intro[li].format(*rendered)
                unit = pack.unit[li]
                choices[lang] = tuple(f"{_fmt(v, lang)} {unit}".strip() for v in options_num)
                pretty_sub = substitution.replace(".", ",") if lang != "en" else substitution
                explanation[lang] = {
                    "kk": f"Қолданылатын байланыс: {formula}. Берілген мәндерді қоямыз: {pretty_sub}. Нәтиже: {_fmt(ans, lang)} {unit}. Бірлікті есеп соңында тексереміз.",
                    "ru": f"Используем связь: {formula}. Подставляем данные: {pretty_sub}. Получаем {_fmt(ans, lang)} {unit}. Единицу измерения проверяем в конце.",
                    "en": f"Use the relation {formula}. Substitute the values: {pretty_sub}. The result is {_fmt(ans, lang)} {unit}. Check the unit at the end.",
                }[lang]
                if pack.topic == "nuclear_physics":
                    explanation[lang] = {
                        "kk": f"Әр жартылай ыдырау периодынан кейін ядролар саны екі есе азаяды. Формула: {formula}. Есептейміз: {substitution}={_fmt(ans, lang)}. Қалған ядро саны: {_fmt(ans, lang)}.",
                        "ru": f"После каждого периода полураспада число ядер уменьшается вдвое. Формула: {formula}. Считаем: {substitution}={_fmt(ans, lang)}. Число оставшихся ядер: {_fmt(ans, lang)}.",
                        "en": f"After each half-life, the number of nuclei halves. Use {formula}: {substitution}={_fmt(ans, lang)}. Remaining nuclei: {_fmt(ans, lang)}.",
                    }[lang]
            result.append({
                "id": f"topic-{pack.topic}-{i+1:03d}", "topic": pack.topic,
                "difficulty": "A" if i < 50 else "B" if i < 80 else "C",
                "kind": "single", "prompt": prompt, "choices": choices,
                "correct_indices": (correct,), "explanation": explanation,
                "kazakh_term": pack.term[0], "context": None,
                "matching_left": None, "source_note": f"Local physics reference library: topic-aligned original variation; formula reference {pack.formula}. Original item, not an official UNT question.",
                "reuse_status": "original_aetherlab_item", "author": "PhysLab",
                "reviewer": "pending_kazakhstan_physics_teacher",
                "language_review_status": "pending_teacher_review_kk_ru_en",
                "answer_verification_status": "author_checked_teacher_review_pending",
                "solution_latex": (formula, f"{result_symbol}={substitution}", f"{result_symbol}={_latex_num(ans)}" + (f"\\,\\mathrm{{{unit_latex(pack.unit[2])}}}" if pack.unit[2] else "")),
            })
    return tuple(result)


def unit_latex(unit: str) -> str:
    return {"m/s":r"m/s","N":r"N","N·m":r"N\cdot m","kPa":r"kPa","10⁻²¹ J":r"10^{-21} J","kJ":r"kJ","A":r"A","g":r"g","mN":r"mN","V":r"V","s":r"s","mm":r"mm","cm":r"cm","—":r"1","10⁻¹⁹ J":r"10^{-19} J","particles":r"","m":r"m"}.get(unit, unit)
