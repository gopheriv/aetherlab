# Course Mode Lite

AetherLab now keeps lightweight progress for lesson quiz answers. The goal is
not a full LMS; it is a learning loop that remembers what a student missed and
suggests a useful next topic.

## What Is Stored

Progress is stored as JSON at:

```text
<AetherLab data dir>/course_progress.json
```

Each lesson is keyed by audience and normalized topic. A record stores:

- lesson title, topic, and audience;
- total quiz attempts and correct attempts;
- per-question prompt, concept, last choice, correctness, confidence, and due date;
- miss counts and a bounded local history of quiz and recall-review events.

`CourseProgressStore.evaluation_events()` exposes the local history without
exporting prompt answers or selected choices. Review events label the response
method: multiple-choice reviews store objective correctness; open-response
reviews store only the learner's self-reported recall. These are different
measures and should not be merged when evaluating learning.

The file does not include provider settings, API keys, environment variables,
cache paths, raw videos, or generated render artifacts.

## User Flow

1. Build or open a lesson.
2. Answer a multiple-choice question in the **Questions** tab.
3. Before choosing, rate confidence as low, medium, or high. AetherLab saves
   the result immediately and schedules missed or low-confidence questions for
   retrieval practice.
4. The course status strip updates with the current score and a recommended
   next topic.
5. When questions are due, choose **Review due questions**. Multiple-choice
   questions require an answer before feedback and record correctness. Open
   questions still reveal a model answer and ask for a self-rating because
   free-text grading is not reliable. AetherLab mixes due concepts and
   reschedules each prompt from the configured review streak.

The default successful-recall intervals are 1, 3, 7, and 14 days. Change these
in **Settings → Learning** using comma-separated values from 1 to 365 days; up
to eight distinct intervals are used in ascending order. Incorrect and
low-confidence answers return at the first interval. Progress stays in the
local data directory and is not synced to an account or cloud service.

Wrong answers recommend reviewing the mapped objective for that question.
Clean scores recommend a next physics topic from the lesson domain, for example
Kepler orbit -> orbital energy and escape velocity.

## Study measurement

Due MCQ reviews produce objective correctness events. Open-response review
events keep the learner's self-rating and have no correctness score. To summarize
one or more local progress files without copying question text, answers, selected
choices, file paths, or participant names into the report, run:

```powershell
python tools/learner_study_analysis.py <progress-a.json> <progress-b.json> `
  --output study-summary.json
```

The report counts due-review returns and the closest review in the one-day and
seven-day windows (default tolerance: one day). It reports objective MCQ accuracy
separately from open-response self-ratings. Transfer problems are scored separately
from progress events. To include those results, add `--transfer-csv <file>` with
the columns `participant_slot,item_id,days_since_first_attempt,correct,novel`.
Participant slots are 1-based and follow the order of progress files on the
command line. Mark `novel` true only for a problem that tests transfer to a new
situation. The output is descriptive pilot evidence, not proof that spaced review
caused a learning gain.

## Scope

This first pass is intentionally small and durable:

- no account system;
- no cloud sync;
- no grading of open-response questions;
- no changes to generated lesson content;
- no learning-efficacy claim from immediate scores. Delayed one- and seven-day
  recall plus transfer performance still need to be measured with learners.

It gives future course mode work a stable local progress model to build on.

## Prepared lessons and storage recovery (October 2026)

The prepared five-minute lesson opens without spending AI allowance or indexing
textbooks. Its header language selects the matching packaged text/media. While
loading, the latest language choice wins; cancelled loads do not start queued
replacements or discard a previous valid lesson. Both Qt players own an audio
output; actual sound/perception still requires a playback/listening check.

Course storage remains bound to the active learner after general settings are
saved. Profile changes rebuild owned quiz cards/gates, keep old selections out
of the new learner's view and ignore retired-card signals. Cancel keeps current
state. Pending grades return only with their original profile/content.

V2 uses one progress identity across three languages. Existing confirmed language
aliases are projected without rewriting during reads. The next successful
mutation retains complete legacy snapshots and combines histories. Exact old
imports do not count twice; changed previously migrated aliases require review
instead of guessing an overlap. V1 and unrelated records keep their identities.

New generic Unicode topics use identities derived from their complete normalized
names. Earlier ASCII-stripped totals may mix different topics and cannot safely
be attributed. Such records are retained with explicit uncertainty and excluded
from current review/evaluation evidence. Fresh checks establish verified progress.

File IO refusal is not an empty store and must not overwrite history. A graded
answer keeps its response time, choice and confidence for explicit save retry.
Operation IDs make retry idempotent when a write may have succeeded before its
acknowledgment failed. Closing unconfirmed drafts defaults to staying; discard
is explicit. These drafts are held in memory. Forced termination/crash before a
successful write does not have a persistent outbox recovery guarantee.

Review callbacks report unavailable storage, use selected MCQ control language,
and distinguish saved responses from cancellation without a new response.
