# PhysLab ЕНТ physics MVP

## Product decision

Start with Kazakhstan school students preparing for the physics profile subject
of the ЕНТ/ҰБТ. This is the clearest audience for the requested exam pivot and
fits the existing high-school lesson path. Keep a Kazakhstan physics-teacher
review step for terminology and answer keys.

The current MVP is a three-language physics learning slice for high-school
students: Kazakh, Russian, and English lesson planning; a plain-language
Kazakh-term glossary; optional speech; and a 100-question practice pool with a
fixed answer key and worked explanations. Its separate 40-question UNT-format
mock is worth 50 points: 25 single-answer items (25 points), five context items (5 points),
five multiple-answer items (10 points), and five matching items (10 points).
The configured PhysLab timer is 90 minutes per the product requirement; verify
current official timing before calling that the official exam duration. The
questions are original study items, not an official mock variant. The app
links to official preparation materials and the free mock test.

## Work list

### P0 — needed for a dependable first demo

- [x] Choose high-school ЕНТ candidates as the first audience.
- [x] Add a language selector to Learn and Practice for kk/ru/en.
- [x] Ask the lesson planner for beginner-friendly explanations in the selected
  language and retain Kazakh terms with plain definitions.
- [x] Select a matching voice for Kazakh, Russian, or English narration.
- [x] Add a 100-question practice mode and a separate timed 40-question mock
  with explicit answer keys and explanations in all three languages.
- [x] Configure the full mock for 90 minutes and save unfinished answers
  locally so the student can resume after an app restart.
- [x] Add an opt-in camera shadow pilot that processes face presence locally,
  saves only event metadata, and never blocks or changes a score.
- [x] Apply ЕНТ 0/1/2-point scoring and display question count separately
  from the 50-point maximum.
- [x] Keep lesson-plan, chapter, and render caches language-specific so one
  language cannot reuse another language's narration or labels.
- [x] Add links to the official NCT preparation catalog and free mock test.
- [x] Document official source URLs and distinguish original practice items
  from official samples.
- [x] Match the 40-question physics structure: 25 single-answer questions, a
  five-question context set, five one-or-multiple-answer questions, and five
  matching tasks; follow the 50/30/20 difficulty split.
- [ ] Have a Kazakhstan physics teacher review every answer, calculation,
  Kazakh term, and translation before presenting the bank as exam-ready.
- [x] Make the no-API lesson fallback clearly explain in Kazakh or Russian
  that only the offline practice bank is available; never show English lesson
  text as if it were translated.
- [ ] Manually review generated video labels, captions, voice language, and
  audio/video timing for all three languages. Keep the existing whole-clip
  voiceover fit and unique per-render media directory that prevents the prior
  Manim cache/synchronization collision.

### P1 — next after the first demo

- [x] Add topic filters and local progress by the 25 official physics topics.
- [x] Add searchable PDF export with correct Kazakh/Cyrillic font support,
  worked solutions, terms, topic history, and source attribution.
- [x] Store per-question teacher-review status. All review fields start as
  pending and must be cleared by a Kazakhstan physics teacher before release.

### P2 — scale the content safely

- [x] Track source, originality/reuse status, author, reviewer, difficulty,
  language review, and answer verification for each question.
- [x] Add a 100-item topic-practice pool and a fixed 40-question timed mock.
- [x] Review missed questions locally and offer a mixed timed mock session.
- [x] Add a local screen for same-school full mock results and camera review
  signals, with a clear notice that the screen is not role-protected.
- [ ] Add more subjects only when the source catalog and reviewers are ready.

## MVP acceptance checklist

1. A student can choose kk, ru, or en and see practice prompts, choices,
   explanations, and Kazakh-term meanings in that language.
2. All 100 practice exercises are graded from version-controlled keys, never from a
   model response. Topic timed practice allows about two minutes per question.
   The full mock uses the configured 90-minute timer; verify official timing
   separately. Only the fixed 40 questions are scored as the full 50-point mock.
3. Learn sends the selected language and high-school audience through the
   planning, rendering, voice, and cache layers.
4. The app offers direct links to official NCT specifications/materials and
   its free mock test. PhysLab's 40-item set is labeled as original study
   material, not an official test variant. The question count and 50-point
   maximum are shown separately.
5. The attached competition rules are bank/finance-oriented, while this MVP is
   education-focused. Before submission, confirm the pivot fits the rubric and
   prepare a concrete financial-sector use case if the contest still requires it.
6. Goals and completed practice history are stored locally; history keeps topic
   counts, score totals, and missed question IDs, but not selected answers or
   identifying account data. A separate local active-attempt file stores
   in-progress answers for crash recovery and is deleted when the attempt ends.
   A student can export the current attempt and answer explanations as a PDF.

The optional camera pilot detects face presence and app focus only. It does not
track gaze, save video, lock the desktop, or infer cheating. Events are local
review flags and have no score impact. A local review screen lists complete
mock scores and allowlisted camera events for profiles with the same school ID
on this device. Anyone using the device can open it; it is not a teacher-auth
system, and camera events are not a cheating verdict. No event data is sent to
the leaderboard server. School-wide review across devices needs an authenticated
service with an explicit data-access policy.
Students can select one weekly mock day in their local study plan. The dashboard
shows the next day and offers a timed-mock shortcut on that day. This is a local
per-profile reminder; it does not distribute a schedule by school ID or enforce
attendance. School-wide scheduling needs a shared school service. AI help has a
local allowance of 10 explicitly started learner requests per profile and local
calendar day. The counter is visible in the AI command bar and stored beside
that profile's data. Background model work and practice/exam actions do not
consume it. The desktop counter is a local product limit, not secure
cross-device quota enforcement.

## Source notes

The official NCT catalog and the 2026 physics specifications are listed in
[`ENT_PHYSICS_SOURCES.md`](ENT_PHYSICS_SOURCES.md). The current specification
defines 40 questions across 25 topics, four item formats, a 50/30/20 difficulty
split, and about two minutes per question. The 90-minute setting above is a
PhysLab product choice, not an assertion about official timing. See that source note before extending
the bank; do not copy public or paid questions without checking reuse terms.
