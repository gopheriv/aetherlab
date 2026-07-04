# AetherLab — Troubleshooting

**Where are my logs?** `%LOCALAPPDATA%\AetherLab\logs\aetherlab.log`
(attach this to any bug report).

## "No API key configured"
This is fine — AetherLab still works with built-in templates and textbook
references. To enable AI, see [QUICKSTART.md §4](QUICKSTART.md): local Ollama
(free) or any OpenAI-compatible key. Use **Settings → Test connection** to
verify the provider actually answers.

## The AI answers but is very slow
Cloud providers vary a lot; some free tiers queue for minutes. The pipeline
retries and falls back automatically, but the run will feel slow. Try a
faster model, or local Ollama with a small model (`qwen2.5:7b`).

## Videos don't render / "render-error"
- The render self-heals up to two times automatically — check the Code view's
  diagnostics for what happened.
- **LaTeX missing:** AI scenes that use typeset math (`MathTex`) need a LaTeX
  distribution ([MiKTeX](https://miktex.org) or TinyTeX). Without one,
  AetherLab automatically instructs the AI to use plain text — scenes still
  render, just without typeset math inside the video.
- **Manim missing (source installs):** `pip install manim`.

## GIF export says "ffmpeg not found"
GIF conversion needs the ffmpeg CLI: `winget install ffmpeg` (or
[ffmpeg.org](https://ffmpeg.org)). MP4 export ("Save") works without it.

## References are empty
Add books first: **Refs → Get starter library** (free OpenStax textbooks) or
**Add folder** for your own PDFs, then wait for indexing to finish. The
first index of a large book takes a few minutes.

## The library index seems corrupted
Delete `%LOCALAPPDATA%\AetherLab\chroma` and press **Re-index** (Ctrl+click
for a full rebuild). Your PDFs are untouched; only the search index rebuilds.

## Reset everything
Close AetherLab and delete `%LOCALAPPDATA%\AetherLab` (this removes settings,
cache, history, and the index — downloaded books in `library/` included, so
move those out first if you want to keep them).
