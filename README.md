# AetherLab — Physics Desktop Workbench

AetherLab turns a natural-language physics or math prompt into:

1. **An analytical derivation** (summary, step-by-step derivation, keywords, and
   simulation variables) produced by an OpenAI-compatible LLM, with a
   deterministic offline fallback.
2. **Textbook references** retrieved from a local library via ChromaDB vector
   search, with a filesystem keyword-search fallback.
3. **A custom Manim scene** generated to visualize the problem, compiled,
   validated, and rendered to an MP4.
4. **A live interactive canvas** with parameter sliders that update parametric
   curves in real time.

Everything runs in a single PyQt6 desktop window with a dashboard layout
(Solve · Refs · Scene · Params · History) and a 4-stage pipeline progress bar.

## Install

```bash
python -m pip install -e .            # core (PyQt6, numpy, openai)
python -m pip install -e ".[rag]"     # optional: ChromaDB + PyMuPDF for RAG
python -m pip install -e ".[dev]"     # optional: pytest, black, ruff
```

Requires Python **3.11+**. Manim Community (`manim`) must be installed and on
the path for video rendering.

## Configure the model provider

AetherLab reads provider settings in this order of precedence:

| Setting   | Environment variables                                   | Fallback |
|-----------|---------------------------------------------------------|----------|
| API key   | `AETHERLAB_OPENAI_API_KEY`, `OPENAI_API_KEY`            | `~/.qwen/settings.json` |
| Base URL  | `AETHERLAB_OPENAI_BASE_URL`, `OPENAI_BASE_URL`          | `~/.qwen/settings.json` |
| Model     | `AETHERLAB_LLM_MODEL`                                    | `~/.qwen/settings.json`, else `gpt-5.5` |

Without an API key, AetherLab still runs using its deterministic solver and a
static fallback scene.

Other paths (all optional): `AETHERLAB_DATA_DIR`, `AETHERLAB_CACHE_PATH`,
`AETHERLAB_CHROMA_PATH`, `AETHERLAB_LIBRARY_DIR`, `AETHERLAB_LLM_TIMEOUT`.
By default, data lives under `%LOCALAPPDATA%\AetherLab` (or `~/.aetherlab`).

## Run

```bash
python -m aetherlab                 # launch the desktop app
python -m aetherlab --smoke         # headless end-to-end pipeline smoke test
python -m aetherlab --smoke "Solve the simple pendulum for large angles."
```

On Windows you can use `start.bat`, which launches the app under a watchdog that
auto-restarts it on a crash (a clean quit stops the watchdog).

## Library / RAG

Drop `.txt`, `.md`, `.tex`, or `.pdf` files into the library directory
(`%LOCALAPPDATA%\AetherLab\library` by default). They are auto-ingested into
ChromaDB on the first run; if ChromaDB is unavailable, a filesystem keyword
search is used instead.

## License

MIT
