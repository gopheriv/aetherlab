# Stage I — agreed trilingual dictionary (kk / ru / en)

Date: 2026-10-12. Source of truth: output/stage_d_evidence/registry.md
terminology table. This file freezes the exact word forms used in
canonical.json v2 voiceovers/captions and practice.json, so later stages
(J scenes, K TTS, N subtitles, O PDF) cannot silently re-translate terms.

Legend: kk forms from zak9/zak10/fbs (page-cited in registry); ru/en grounded
in nct-ru/nct-en where present, else standard school term (†). Status of every
row: auto-checked, teacher review pending.

## Core lesson terms

| kk (used) | ru (used) | en (used) | registry grounding |
|-----------|-----------|-----------|--------------------|
| теңүдемелі қозғалыс | равноускоренное движение | uniformly accelerated motion | zak9 p.21 / † / nct-en Q26–30 |
| бірқалыпты (қозғалыс) | равномерное (движение) | uniform (motion) | prerequisite P1, standard |
| үдеу | ускорение | acceleration | zak9 p.20 / nct-ru Q1 / nct-en Q16 |
| жылдамдық | скорость | velocity (vector); speed (modulus) | zak9 p.19 / nct-ru Q1 / nct-en Q26–30, Q8 |
| бастапқы жылдамдық | начальная скорость | initial / starting velocity | fbs p.6 / † / † |
| соңғы жылдамдық | конечная скорость | final velocity | fbs p.6 / † / † |
| орын ауыстыру | перемещение | displacement | zak10 p.15 / nct-ru Q36 / † |
| жүрілген жол | пройденный путь | distance travelled | zak10 p.15 / † / nct-en Q28 |
| көлбеу | наклон | slope | zak10 p.17 graph rules |
| аудан | площадь | area | zak10 p.17; zak9 p.22 |
| уақыт | время | time | fbs p.6 |
| орташа(сын) | средн(яя/юю) | average | zak9 pp.23, 26 (орташа жылдамдық) |
| Ox осі | ось Ox / ось икс | x axis | lesson axis convention (Stage F) |
| ҰБТ (байқау сынақтары) | ЕНТ (пробники) | UNT (mocks) | tc3 collection header (adapted-only) |
| Закирова | Закирова | Zakirova | practice.json H3/H4 explanations |

## Units (spoken and written)

| kk | ru | en | note |
|----|----|----|------|
| м/с² | м/с² | m/s² | acceleration; zak9 p.21: [a] = 1 м/с² |
| м/с | м/с | m/s | velocity |
| м | м | m | displacement / distance |
| с | с | s | time (single letter: Latin s vs Cyrillic с — visually identical, kept per-language) |

Spoken forms: «метр секундына квадрат» / «метр на секунду в квадрате» /
«metre per second squared»; «секундына N метр» / «N метра в секунду» /
«N metres per second».

## Fixed lesson phrases (sense anchors, checked by verify_i.py)

- Constancy (B1): «әр секундта бірдей шамаға өседі» / «растёт одинаково за
  каждую секунду» / «grows by the same amount each second».
- Definition link (B1): «үдеудің үшке тең екенін» / «ускорение равно трём» /
  «an acceleration of three».
- Direction guard (B3): «Бағыт өзгермесе» / «направление не меняется» /
  «direction stays the same».
- Slope rule (B4): «көлбеуі — бұл үдеу» / «Наклон прямой — это ускорение» /
  «the slope of the line is the acceleration».
- Area rule (B5): «аудан сан жағынан орын ауыстыруға тең» / «Площадь под
  графиком скорости численно равна перемещению» / «the area under the
  velocity graph numerically equals the displacement».
- Trap verdict (B7): «Қате» / «Неверно» / «Wrong» + «орташасын алу керек» /
  «брать надо среднюю» / «take the average».
- Slope≠area (B7): «Көлбеу — бұл үдеу, аудан — орын ауыстыру» /
  «Наклон — это ускорение, площадь — перемещение» /
  «Slope is acceleration; area is displacement».

## Deliberate non-parities (recorded, not bugs)

- Single-letter time unit «с» (Cyrillic, ru/kk) vs «s» (Latin, en) — identical
  glyphs, correct per language; H5 prompt uses each in its own version.
- «Закирова» transliterated as «Zakirova» in en (added Stage I parity fix).
- Caption descriptors after «—» are translated, not copied
  («равномерное» / «бірқалыпты» / «uniform»); only the math skeleton before
  «—» is required identical (verify_i.py math_core).
