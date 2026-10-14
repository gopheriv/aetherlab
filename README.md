<p align="center">
  <img src="assets/aetherlab_icon_1080.png" width="96" alt="PhysLab" />
</p>

<h1 align="center">PhysLab</h1>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+" /></a>
  <a href="https://www.manim.community/"><img src="https://img.shields.io/badge/manim-0.21.0-orange" alt="Manim 0.21.0" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT" /></a>
  <a href="docs/QUICKSTART.md"><img src="https://img.shields.io/badge/docs-quickstart-informational" alt="Quickstart" /></a>
  <img src="https://img.shields.io/badge/langs-ru_%7C_kk_%7C_en-lightgrey" alt="ru kk en" />
</p>

<p align="center"><b>Ask a physics question — or a whole topic — and get a
narrated, animated explanation you can actually learn from.</b></p>

---

PhysLab is a desktop physics learning workbench for Kazakhstan high-school
students preparing for ЕНТ/ҰБТ. It combines a multilingual practice set,
beginner-friendly lessons, interactive visual explanations, and a searchable
PDF library. The existing solver and animation pipeline remain available.

### Solve — one problem, visualized
Type a problem, press **Run**, and watch a four-stage pipeline:

| Stage | What you get |
|---|---|
| **Solve** | An analytical derivation with typeset equations (AI-written, or a built-in scaffold without AI) |
| **RAG** | Citations from *real* textbooks — free OpenStax books download & index in one click, your own PDFs too |
| **Scene** | A storyboarded animation, directed and coded by AI, rendered with [Manim Community](https://www.manim.community/) |
| **Render** | A self-healing MP4 — crashes and timeouts auto-repair; a vision model can review and revise the result |

Plus a **live parametric canvas**: drag sliders (damping, stiffness, gravity…)
and watch the solution curves respond in real time.

### Learn — a whole topic, taught
Type a *topic*, press **Learn**, and PhysLab builds a **narrated,
multi-chapter video lesson** — hook → intuition → the math, built up → worked
example → recap. The Lesson page is a self-contained classroom:

- an **inline narrated video** assembled from the chapters,
- a clickable **chapter outline** that seeks the video,
- a **transcript** with per-chapter fact-check notes,
- interactive **check-yourself questions** (multiple-choice with instant
  feedback + open questions with model answers),
- **textbook references**, and a **Play with it** tab — a live canvas seeded
  with the topic's parameters so you can experiment,
- one-click **study-guide PDF** export.

Lessons are grounded in real textbooks and fact-checked against them; without an
AI key you still get a coherent, domain-matched template lesson.

## Install

**Students:** run `PhysLab-Setup-<version>.exe` → launch from the Start menu.
Then read the [Quickstart](docs/QUICKSTART.md).

**From source** (Python 3.11+):
```bash
pip install -e .[rag]
pip install manim
python -m aetherlab
```

## AI is optional — and can be free

- **No AI:** built-in domain templates (pendulum, orbit, wave, oscillator) +
  full textbook references. Works offline.
- **Local AI (free, private):** install [Ollama](https://ollama.com); PhysLab
  detects it and enables it in one click.
- **Cloud AI:** any OpenAI-compatible endpoint (Settings → paste base URL,
  key, model → Test connection). A separate **vision model** (optional) lets the
  critic watch renders and revise them.

Advanced configuration (the existing `AETHERLAB_*` variable names remain as a
backward-compatible prefix):
`AETHERLAB_OPENAI_API_KEY`/`OPENAI_API_KEY`, `AETHERLAB_OPENAI_BASE_URL`,
`AETHERLAB_LLM_MODEL`, `AETHERLAB_VISION_MODEL`, `AETHERLAB_PROVIDER=ollama`,
`AETHERLAB_NARRATION=1`, `AETHERLAB_DATA_DIR`, `AETHERLAB_LIBRARY_DIR`,
`AETHERLAB_LLM_TIMEOUT`. User data remains under `%LOCALAPPDATA%\AetherLab` (or
`~/.aetherlab`) so existing settings, textbooks, and study history survive the
rebrand; logs remain in that data folder.

## Highlights

- **Two modes, one bar** — *Run* a single problem or *Learn* a whole topic.
- **Typeset math everywhere** — governing equations render as real math, from
  the hero banner to the parameter sliders (γ, ω, ℓ).
- **Storyboarded, self-healing animations** — the AI first *directs* (acts,
  hero frame, narration), then implements; a static safety/lint battery + a
  bounded repair loop keep renders reliable; an optional vision critic revises
  weak results.
- **Real textbook grounding** — ChromaDB vector search over an OpenStax starter
  library with page-level citations (filesystem keyword fallback without
  ChromaDB); lessons are fact-checked against the sources.
- **Optional narration** — edge-tts voiceover fit to the animation (`.srt`
  subtitles for lessons).
- **Exports** — LaTeX/PDF derivations, lesson study guides, MP4/GIF animations,
  runnable Manim scene code.

## Run

```bash
python -m aetherlab                 # launch the desktop app
python -m aetherlab --smoke         # headless end-to-end pipeline check
python -m aetherlab --version
```

On Windows, `start.bat` launches the app under a crash-restart watchdog.

## Development

```bash
python test_features.py            # canonical feature checks, 250 features
python build_feature_tracker.py    # regenerate the canonical feature tracker
python tools/tracker_integrity_audit.py --check
python tools/feature_surface_audit.py --check
python -m pytest -q                # focused legacy regression suite
```

The feature catalog lives in `AetherLab_Feature_Tracker.xlsx` (generated — edit
`build_feature_tracker.py`). The CSV/XLSX, result JSON, tests, and defect log
are guarded by the audit tools above. The workbook records software checks
separately from complete user-behaviour acceptance; native UI, hardware and live
cloud verification must be evidenced independently. Design & architecture notes:
`TOPIC_EXPLAINER_BRIEF.md`, `MANIM_PIPELINE_QUALITY_ANALYSIS.md`,
`RENDER_RELIABILITY_AND_CLOUD.md`, `PHYSICS_SOURCES.md`. User docs:
[`docs/QUICKSTART.md`](docs/QUICKSTART.md),
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## License & credits

[MIT](LICENSE). Videos are rendered with [Manim Community](https://www.manim.community/).
Starter textbooks are [OpenStax](https://openstax.org) (CC BY 4.0) — download
for free at openstax.org. Icons are [Lucide](https://lucide.dev) (MIT).
