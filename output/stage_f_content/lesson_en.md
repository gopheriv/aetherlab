# Равноускоренное прямолинейное движение — canonical en-text (v2)

Цель: После видео ученик сможет по начальной скорости, ускорению и времени вычислять скорость и перемещение равноускоренно движущегося тела и проверять ответ площадью под графиком v(t).

## Условия применимости

- rectilinear: motion along a straight line
- a_const: acceleration magnitude and direction do not change
- same_direction: velocity keeps its sign, so displacement numerically equals distance travelled
- si_units: all quantities in SI (m, s, m/s, m/s^2)

Ось: Ox directed along the motion; forward projections take the + sign (ТҮҚ case). ТКҚ and direction reversal are out of lesson scope.

## Величины (inputs — истина; derived — проверить на этапе G)

- `D-v0`: v0 = 2 м/с — начальная скорость [input]
- `D-a`: a = 3 м/с² — ускорение [input]
- `D-t`: t = 4 с — время [input]
- `D-v`: v = 14 м/с — конечная скорость [derived ← F-vel (Stage G 2026-10-12)]
- `D-s`: s = 32 м — перемещение [derived ← F-disp (Stage G 2026-10-12)]
- `D2-v0` [B6]: v0 = 0 м/с — начальная скорость (пауза-задача) [input]
- `D2-a` [B6]: a = 2 м/с² —  [input]
- `D2-t` [B6]: t = 5 с —  [input]
- `D2-s` [B6]: s = 25 м —  [derived ← F-disp (Stage G 2026-10-12)]

## Формулы

- `F-accel-def`: определение ускорения: $a = \Delta v / \Delta t$ (`a = (v - v0) / t`)
- `F-vel`: скорость: $v = v_0 + at$ (`v = v0 + a*t`)
- `F-disp`: перемещение: $s = v_0 t + at^2/2$ (`s = v0*t + a*t**2 / 2`)
- `F-avg`: перемещение через среднюю скорость: $s = (v_0 + v)t/2$ (`s = (v0 + v) * t / 2`)

## Блоки

### B0 Крючок и цель (0–20 с)

Visual: Машина разгоняется; вопрос на экране; цель урока

Voiceover:

> A car travels at two metres per second and accelerates smoothly. After four seconds it already does fourteen. How many metres did it cover? By the end of the lesson you will find the answer two ways.

Captions:

- How far did the car go?
- Two ways to the answer

### B1 Что значит «равноускоренно» (20–70 с)

Visual: Спидометр: равные прибавки скорости за равные такты; вектор a; ось Ox

Voiceover:

> If speed never changes, motion is uniform: v equals s over t. Here speed grows — but grows by the same amount each second. Every second adds three metres per second — that is what an acceleration of three means. Such motion is called uniformly accelerated. Acceleration measures how fast velocity grows: a equals the change in velocity divided by time. Its unit is the metre per second squared. We point the x axis along the motion: everything forward takes the plus sign.

Captions:

- v = s / t — uniform
- a = Δv / Δt
- [a] = m/s²
- x axis →

### B2 Скорость v = v0 + at (70–110 с)

Visual: Формула собирается по частям: старт + прибавка; числовая подстановка

Voiceover:

> Velocity at any moment is the starting velocity plus the gain. The gain is acceleration times time: v equals v naught plus a t. Plug in our numbers: two plus three times four — fourteen metres per second. Check the units: metres per second squared times seconds gives metres per second. It all fits.

Captions:

- v = v₀ + at
- 2 + 3·4 = 14 m/s

### B3 Перемещение s = v0t + at²/2 (110–160 с)

Visual: Два слагаемых растут столбиками 8 + 24; итог 32 м

Voiceover:

> Displacement is how far the body shifted from the start. While direction stays the same, it equals the distance travelled. The formula: s equals v naught t plus a t squared over two. The first term is what we would cover without accelerating; the second is the boost from acceleration. Let's compute: two times four is eight, plus three times sixteen over two — twenty-four. Thirty-two metres in total.

Captions:

- s = v₀t + at²/2
- 8 + 24 = 32 m
- direction unchanged

### B4 График v(t) (160–200 с)

Visual: Построение прямой v = 2 + 3t, точка (4, 14); наклон подписан «a = 3»

Voiceover:

> Let's plot velocity against time: v equals two plus three t. It is a straight line: two at zero, fourteen after four seconds. The slope of the line is the acceleration: the steeper, the larger the a. Remember: the slope of the v–t graph equals the acceleration.

Captions:

- v = 2 + 3t
- slope = a

### B5 Проверка площадью (200–230 с)

Visual: Заливка трапеции под графиком; разбиение на прямоугольник и треугольник; штамп «сошлось»

Voiceover:

> Now the check. The area under the velocity graph numerically equals the displacement. We have a trapezoid with bases two and fourteen and height four: half the sum of the bases times the height — eight times four — thirty-two metres. It matches the formula. Two ways, one answer.

Captions:

- S = (2+14)/2 · 4 = 32 m
- area = displacement ✓

### B6 Пауза-задача (230–260 с)

Visual: Условие + значок паузы; затем короткое решение

Voiceover:

> Now you. A car starts from rest with an acceleration of two metres per second squared. How far does it go in five seconds? Pause the video and solve it. Answer: zero times five plus two times twenty-five over two — twenty-five metres.

Captions:

- v₀ = 0, a = 2, t = 5, s = ?
- Pause!
- s = 25 m

### B7 Ловушки и итог (260–300 с)

Visual: Зачёркнутые неверные ходы; шпаргалка из трёх формул; мостик к ENT-формату

Voiceover:

> Two traps. First: plugging the final speed into the uniform-motion formula: fourteen times four is fifty-six. Wrong: the speed was growing, you must take the average. Second: mixing up slope and area. Slope is acceleration; area is displacement. To sum up: v equals v naught plus a t; s equals v naught t plus a t squared over two; the area under the v–t graph is the displacement. Graph-area problems appear in UNT mocks — now you will recognise them.

Captions:

- ✗ 14·4 = 56
- slope = a; area = s
- v = v₀ + at; s = v₀t + at²/2

Итого: 300 с (норма 300±15 с).
