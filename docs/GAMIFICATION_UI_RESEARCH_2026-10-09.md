# PhysLab UI research: useful progression, not score farming

**Reviewed:** 9 October 2026. Product comparison is based on public pages and
the current local PhysLab implementation; the feature scores below are design
priorities, not results from a user study.

## What comparable products do

| Product | Observed pattern | What PhysLab already has | Gap worth addressing |
| --- | --- | --- | --- |
| Khan Academy | Shows per-skill states (Familiar, Proficient, Mastered), explains progress, and reports which skills rose or fell after an activity. It can recommend a lesson from the result. [Mastery system](https://support.khanacademy.org/hc/en-us/articles/115002552631-What-are-Course-and-Unit-Mastery) | Topic accuracy, topic practice, and recommendations | A raw percentage does not tell a learner whether a topic is new, still being practiced, or consistently strong. |
| Quizlet | Groups studied material into Not Studied, Still Learning, and Mastered, then lets learners target one group. Progress syncs across web and mobile. [Progress for targeted studying](https://help.quizlet.com/hc/en-us/articles/360048803491-Using-Progress-for-targeted-studying) | Search, topic filters, and accuracy counts | A status should be visible in the catalog and later become a usable filter. |
| Duolingo | Uses optional leagues, XP, streaks, and quests. Its own product write-up says XP-based monthly challenges were changed to quest-based after learners could game XP, and rankings could over-reward grinding. [Learning well metric](https://blog.duolingo.com/time-spent-learning-well/) · [Duolingo learning guide](https://blog.duolingo.com/duolingo-101-how-to-learn-a-language-on-duolingo/) | Weekly goals and a school mock-exam leaderboard | Tie rewards to real learning signals and keep competition secondary. Avoid raw XP as the main progress measure. |
| iTest.kz | Local UNT preparation is organized around subjects/topics and full practice testing; its main page describes subject resources and full UNT mocks with expanded statistics. [iTest.kz](https://itest.kz/kz) · [Physics practice](https://itest.kz/kz/testirovanieznaniy-9/fizika-2627) | 25 UNT physics topics, topic exercises, and mock history | Make the learner's topic-by-topic readiness easier to scan at a glance. |
| Daryn.online | The UNT physics course pairs topic video lessons with tests and advertises frequent mock tests and learning points/rewards. [UNT Physics course](https://daryn.online/ru/course/370-fizika-ubt-2025-2026-qosymsa) | Topic lessons, practice, full mocks, review of mistakes | Keep the companion independent of subjects and reward points earned across completed study sessions. |

## Evidence and design implications

An educational gamification meta-analysis covering 22 experimental studies
(3,144 learners) reported a positive pooled achievement effect, but also
substantial variation between studies. A separate meta-analysis of 35
interventions (2,500 participants) found a small positive effect on intrinsic
motivation and called out perceived competence and learner autonomy as design
challenges. So the evidence supports careful testing, not a promise that points
or a mascot will improve scores. [Achievement meta-analysis](https://doi.org/10.1111/bjet.13471) · [Motivation meta-analysis](https://doi.org/10.1007/s11423-023-10337-7)

The gap with the clearest fit is **interpretable progress per topic**. The
current catalog shows accuracy, but it has no stable label for a topic's
learning state. This is why the UI now labels topics **Not started / In
progress / Confident** and explains the rule. For this first version,
“Confident” means at least five answered questions and at least 80% accuracy.
That cutoff is an explicit product heuristic, not a validated mastery test; it
is intentionally not called “Mastered.”

Learners choose one of three physics companions: Quantum, Photon, or Lab Bot.
The chosen companion changes form at 50 and 150 lifetime points from completed
practice and mock sessions, regardless of which topic produced them. A
50-point full UNT mock is one clear reference point for the first evolution;
the second threshold requires continued practice. This matches the requested
collectible-companion idea while making the characters part of the physics
product identity. These thresholds are initial product settings and need
student feedback before being treated as optimal.

## Prioritization scores

Scale: 1 = weak fit / little learner value, 10 = exceptionally strong fit.
Each score is an estimate based equally on learning relevance, clarity,
curriculum fit, and practical feasibility. It is a comparative product
judgment, not an objective scientific measurement.

| Candidate | Score / 10 | Reason |
| --- | ---: | --- |
| Per-topic confidence state with a visible, explainable rule | **9.4** | Makes existing accuracy data actionable and maps closely to proven mastery/progress patterns. |
| Choice of three companions, each evolving with accumulated study points | **8.7** | Adds a concrete visual reward while keeping the learner in control of species; should remain optional if testing shows distraction. |
| Post-practice summary showing topic changes and the next suggested action | **8.9** | Strong fit with Khan Academy's feedback pattern; still missing and the best next addition. |
| One-click review of “in progress” or low-confidence topics | **8.5** | Turns a progress display into a useful study route; catalog filtering can be added next. |
| Personalized, learning-based weekly mission | **7.8** | Could help structure practice, but should wait until the confidence state and activity data have been validated. |
| School leaderboard based on full mock exams | **7.2** | Relevant to the requested peer competition, but secondary to learning feedback and dependent on reliable cross-device hosting. |
| Generic XP and streak counter | **4.9** | Easy to understand, but can reward grinding rather than understanding and may penalize healthy breaks. |

## What changed in this iteration

- Added confidence states to the topic catalog in Kazakh, Russian, and English.
- Added a selectable Quantum, Photon, or Lab Bot companion; the choice is saved
  with the learner profile and previewed at its current evolution form.
- Added lifetime points from completed practice and mock scores; companions grow at
  50 and 150 points. Companion identity and evolution do not depend on topic.
- Kept visible topic-readiness count and the “5 questions + 80%” rule as a
  separate study-progress signal, not as the companion's progression system.
- Kept the existing topic practice, lesson, mock, and profile actions intact.

The next high-value UI change is a post-practice feedback panel that names the
topics that improved, stayed uncertain, or slipped, then routes directly to a
short review. That should follow once the new confidence heuristic has been
checked with real learners.
