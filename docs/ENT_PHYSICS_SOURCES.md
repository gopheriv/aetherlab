# ENТ physics content sources

## MVP scope

The practice set is for Kazakhstan school students preparing for the physics
profile subject of the Unified National Testing (ЕНТ/ҰБТ). The practice pool
contains 100 distinct items in Kazakh, Russian, and English: the fixed 40-item
UNT-format set plus 60 parameterized calculation exercises across ten topic
families. The fixed set follows the official structure: 25 single-answer,
five context-based, five one-or-multiple-answer, and five matching items. It is
worth 50 points and is not an official test variant. The added exercises expand
practice and do not alter that mock.

## Official source catalog

Use the National Testing Center (NCT/НЦТ) as the source of truth for scope and
exam format. Its preparation page links the subject specifications, recommended
textbooks, sample variants in Russian and Kazakh, English-language sample
variants, context examples, and official free/paid practice tests.

- [NCT preparation page for the full-duration ЕНТ](https://new.testcenter.kz/?lang=ru&page_id=15094)
- [2026 physics test specification in Russian](https://new.testcenter.kz/wp-content/uploads/2025/10/12_%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0_%D1%80%D1%83%D1%81.pdf)
- [2026 physics test specification in Kazakh](https://new.testcenter.kz/wp-content/uploads/2025/10/11_%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0_%D0%BA%D0%B0%D0%B7.pdf)
- [NCT Russian-language physics sample variant](https://new.testcenter.kz/wp-content/uploads/2024/12/obr_var_test_02.pdf)
- [NCT English-language physics sample variant](https://new.testcenter.kz/wp-content/uploads/2025/06/PHYSICS.pdf)
- [NCT official free practice portal](https://prob-ent.testcenter.kz/)
- [NCT full-duration ЕНТ scoring format](https://new.testcenter.kz/?lang=ru&page_id=15074)
- [ЕНТ administration and scoring rules, paragraph 18 (Әділет)](https://adilet.zan.kz/rus/docs/V1700015173)

The 2026 physics specification lists 40 questions across 25 topics and three
difficulty levels (50% basic, 30% medium, 20% advanced). The full-duration
scoring format makes the physics profile test worth 50 points: 25 single-answer
items and five context items are worth one point each; five multiple-answer
items and five matching items are worth two points each. The app therefore
shows the question count and point total separately. Paragraph 18 of the ЕНТ
rules defines 0/1/2 partial scoring for multiple-answer and matching items.
The NCT gives an average of about two minutes per item; PhysLab's 80-minute
timed mode uses that as a study pace and does not claim it is an official
physics-only timer.

## Local reference folder

The user-provided `C:\Users\sunak\Projects\References` folder was reviewed.
The current bank uses these items only to check topic coverage and school-level
terminology; no textbook or test question is reproduced:

- `10_.pdf`: a local copy of an earlier NCT physics specification. It was used
  as a cross-check; the 2026 NCT specification remains the source of truth.
- `Физика Закирова 10 ЖМ.pdf` and `Физика Закирова 11 ЖМ.pdf`: Kazakhstan
  high-school textbooks used for concept and Kazakh-term cross-checking.
- The official NCT sample variants in the web list above are used to understand
  the format. Their tasks are not copied into PhysLab's bank.

Some local formula collections identify themselves as paid or prohibit
redistribution, and one file has unclear provenance. Those collections and
question sets were not used as item sources. Use the local textbooks for study
only; do not republish their passages, figures, or end-of-chapter exercises.

## Content and answer quality

For every question added to the bank:

1. Record its topic, difficulty, source URL, language review status, and whether
   it is an original item or an officially published item with reuse permission.
2. Keep the correct answer and worked solution in version-controlled data, not
   in a model-generated response.
3. Check units and arithmetic independently. Have a Kazakh-speaking physics
   teacher review Kazakh wording and terminology before calling it ready.
4. Do not scrape private or paid question banks. Use public NCT materials to
   understand the syllabus and structure; only reproduce source questions when
   their reuse terms allow it.

The version-controlled bank is in `aetherlab/services/ent_physics_bank.py`.
`tools/sync_ent_practice_bank.py` mirrors its 100 keyed items and translations
into the local SQLite table `ent_practice_questions`; the question bank stays
separate from the indexed `physics_pages` table. The desktop practice mode
offers all 100 items; timed mode without filters selects only the fixed
40-item, 50-point mock. Teacher verification and translation review remain
required before describing the bank as exam-ready.

The desktop practice screen filters by the 25 NCT physics topics and records
local per-topic correct/total counts, points, and unresolved missed question
IDs. The queue stores no selected answer. Its PDF export includes the current
answer sheet, fixed answer key, explanations, Kazakh-term definitions, topic
progress, and NCT links. It remains a PhysLab-generated study report, not an
official NCT document.
