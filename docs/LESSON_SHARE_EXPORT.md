# Lesson Share Export

AetherLab lessons can be exported as a portable `.zip` bundle from the lesson
page with **Export bundle**.

The bundle is meant for handoff: a teacher can post it to a class drive, a
student can open it offline, and a reviewer can inspect the generated sources
without needing AetherLab installed.

## Bundle Layout

```text
<lesson-slug>/
  README.txt
  index.html
  metadata.json
  study_guide.tex
  media/
    lesson.mp4
    lesson.srt
    lesson.vtt
  scenes/
    chapter_01_*.py
    chapter_02_*.py
```

`index.html` is a static local player. It references `media/lesson.mp4`, uses
the WebVTT subtitle copy when subtitles exist, and includes chapter buttons
that seek to the exported chapter offsets.

`metadata.json` intentionally avoids secrets and local absolute paths. It
stores only share-safe lesson information: title, topic, audience, objectives,
chapter titles, narration, equations, citations, rendered flags, offsets, and
relative asset names.

## Notes

- The exporter requires a completed lesson MP4.
- If `lesson.srt` exists, the bundle includes both the original SRT and a
  browser-friendly `lesson.vtt`.
- Generated Manim code is included per rendered chapter so the lesson can be
  audited or reused later.
- API keys, provider settings, environment variables, app config, Chroma data,
  and raw render cache folders are never included.
