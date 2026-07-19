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
- per-question prompt, concept, last choice, correctness, and timestamp;
- miss counts for questions answered incorrectly.

The file does not include provider settings, API keys, environment variables,
cache paths, raw videos, or generated render artifacts.

## User Flow

1. Build or open a lesson.
2. Answer a multiple-choice question in the **Questions** tab.
3. AetherLab saves the result immediately.
4. The course status strip updates with the current score and a recommended
   next topic.

Wrong answers recommend reviewing the mapped objective for that question.
Clean scores recommend a next physics topic from the lesson domain, for example
Kepler orbit -> orbital energy and escape velocity.

## Scope

This first pass is intentionally small and durable:

- no account system;
- no cloud sync;
- no grading of open-response questions;
- no changes to generated lesson content.

It gives future course mode work a stable local progress model to build on.
