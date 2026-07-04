<p align="center">
  <img src="assets/aetherlab_icon_1080.png" width="96" alt="AetherLab" />
</p>

<h1 align="center">AetherLab</h1>

<p align="center"><b>Type a physics question. Get a derivation, textbook
references, an animated video, and a live interactive plot.</b></p>

---

AetherLab is a desktop physics workbench for students, educators, and the
curious. One prompt drives a four-stage pipeline:

| Stage | What you get |
|---|---|
| **Solve** | An analytical derivation with typeset equations (AI-written, or a built-in scaffold without AI) |
| **RAG** | Citations from *real* textbooks — free OpenStax books download & index in one click, your own PDFs too |
| **Scene** | A storyboarded animation, directed and coded by AI, rendered with [Manim Community](https://www.manim.community/) |
| **Render** | A self-healing MP4 render — crashes and timeouts are auto-repaired; a vision model can review and revise the result |

Plus a **live parametric canvas**: drag sliders (damping, stiffness, gravity…)
and watch the solution curves respond in real time.

## Install

**Students:** run `AetherLab-Setup-<version>.exe` → launch from the Start menu.
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
- **Local AI (free, private):** install [Ollama](https://ollama.com); AetherLab
  detects it and enables it in one click.
- **Cloud AI:** any OpenAI-compatible endpoint (Settings → paste base URL,
  key, model → Test connection).

Advanced configuration (env vars override everything):
`AETHERLAB_OPENAI_API_KEY`/`OPENAI_API_KEY`, `AETHERLAB_OPENAI_BASE_URL`,
`AETHERLAB_LLM_MODEL`, `AETHERLAB_VISION_MODEL`, `AETHERLAB_PROVIDER=ollama`,
`AETHERLAB_DATA_DIR`, `AETHERLAB_LIBRARY_DIR`, `AETHERLAB_LLM_TIMEOUT`.
Data lives under `%LOCALAPPDATA%\AetherLab` (or `~/.aetherlab`). Logs:
`%LOCALAPPDATA%\AetherLab\logs\aetherlab.log`.

## Highlights

- **Typeset math everywhere** — governing equations render as real math, from
  the hero banner to the parameter sliders (γ, ω, ℓ).
- **Storyboarded animations** — the AI first *directs* (3 acts, hero frame,
  narration script), then implements; a static safety/lint battery and a
  bounded self-repair loop keep renders reliable.
- **Real textbook grounding** — ChromaDB vector search over an OpenStax
  starter library with page-level citations; filesystem keyword fallback
  without ChromaDB.
- **Exports** — LaTeX/PDF derivations, MP4/GIF animations, runnable Manim
  scene code.

## Run

```bash
python -m aetherlab                 # launch the desktop app
python -m aetherlab --smoke         # headless end-to-end pipeline check
python -m aetherlab --version
```

On Windows, `start.bat` launches the app under a crash-restart watchdog.

## Development

```bash
python test_features.py            # behavioural suite (offscreen-safe)
python build_feature_tracker.py    # regenerate the canonical feature tracker
```

The feature catalog lives in `AetherLab_Feature_Tracker.xlsx` (generated —
edit `build_feature_tracker.py`). Architecture notes:
`MANIM_PIPELINE_QUALITY_ANALYSIS.md`, `PHYSICS_SOURCES.md`. Docs for users:
[`docs/QUICKSTART.md`](docs/QUICKSTART.md),
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## License & credits

MIT. Videos are rendered with [Manim Community](https://www.manim.community/).
Starter textbooks are [OpenStax](https://openstax.org) (CC BY 4.0) — download
for free at openstax.org. Icons are [Lucide](https://lucide.dev) (MIT).
