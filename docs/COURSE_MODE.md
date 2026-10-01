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
5. When questions are due, choose **Review due questions**, recall the answer,
   then self-rate whether you recalled it. AetherLab mixes due concepts and
   reschedules each prompt from the configured review streak.

The default successful-recall intervals are 1, 3, 7, and 14 days. Change these
in **Settings → Learning** using comma-separated values from 1 to 365 days; up
to eight distinct intervals are used in ascending order. Incorrect and
low-confidence answers return at the first interval. Progress stays in the
local data directory and is not synced to an account or cloud service.

Wrong answers recommend reviewing the mapped objective for that question.
Clean scores recommend a next physics topic from the lesson domain, for example
Kepler orbit -> orbital energy and escape velocity.

## Scope

This first pass is intentionally small and durable:

- no account system;
- no cloud sync;
- no grading of open-response questions;
- no changes to generated lesson content;
- no learning-efficacy claim from immediate scores. Delayed one- and seven-day
  recall plus transfer performance still need to be measured with learners.

It gives future course mode work a stable local progress model to build on.
