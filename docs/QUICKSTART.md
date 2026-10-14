# AetherLab — Quickstart (for students)

AetherLab turns a physics or math question into a full derivation, textbook
references, an animated video, and a live interactive plot — on your own
computer.

## 1. Install

**Installer (recommended):** run `AetherLab-Setup-<version>.exe`, then launch
*AetherLab* from the Start menu.

**From source (Python 3.11+):**
```bash
pip install -e ".[rag,render]"
python -m aetherlab
```

The `render` extra pins Manim Community 0.21.0 to match the cloud worker.

## 2. Solve your first problem

1. Type a question into the bar at the bottom — try
   *"Solve the simple pendulum for large angles"* — or click **Examples**.
2. Press **Run** (or Ctrl+Enter) and watch the pipeline:
   **Solve → RAG → Scene → Render**.
3. Explore the result:
   - **Solve** — the derivation with typeset equations,
   - **Scene** — the animated video and the live canvas (drag the sliders!),
   - **Refs** — where in real textbooks this topic lives.

No AI configured? Everything still works — you get a built-in derivation
scaffold, a domain-matched animation, and full textbook references.

## 3. Add real textbooks (free)

Open **Refs → Get starter library**. AetherLab downloads free, openly-licensed
OpenStax physics textbooks (CC BY 4.0) and indexes them so every answer cites
real pages. Your own PDFs work too: **Refs → Add folder**.

## 4. Enable AI (optional, free with Ollama)

The AI writes custom derivations and animations for *your* exact question.

**Local (free, private, no account):**
1. Install [Ollama](https://ollama.com) and run `ollama pull qwen2.5:7b`.
2. Start AetherLab — it detects Ollama and shows **Use local AI (Ollama)**
   on the home screen. One click and you're done.

**Cloud (bring your own key):** open **Settings** (gear icon), pick
*Custom endpoint*, paste any OpenAI-compatible base URL + API key + model,
and press **Test connection**.

## 5. Useful shortcuts

| Keys | Action |
|---|---|
| Ctrl+Enter | Run the prompt |
| Escape | Cancel a running pipeline |
| Ctrl+1…5 | Switch sidebar views |
| Ctrl+Shift+C | Toggle the generated code view |
| Ctrl+0 | Reset canvas zoom |

## 6. Export your work

- **Derivation** → LaTeX or PDF (Solve view → Export)
- **Animation** → MP4 (Save) or GIF
- **Scene code** → a runnable Manim Community `.py` file

Problems? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
