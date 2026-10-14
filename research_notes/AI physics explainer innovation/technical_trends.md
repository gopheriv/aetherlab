# Technical Trends and Enabling Technologies for AetherLab (2025–2026)

Scope: technologies, libraries and techniques that an LLM-driven physics explanation and animation desktop app (PyQt6, Manim CE, Qwen/DashScope, Ollama, ChromaDB RAG, vision critic, TTS, live canvas) could adopt. Research date: September 2026. Every claim has a source link; claims taken only from secondary or aggregator sites are marked as such.

---

## 1. Manim ecosystem and programmatic-video alternatives

### Takeaway
Manim CE is still very much alive. v0.21.0 (Aug 2026) adds **Typst text/math rendering, so no TeX install is needed**, plus a roughly 2.2x faster Cairo renderer and parallel partial-movie encoding. Those three changes go straight at AetherLab's two worst pain points: fragile Windows LaTeX installs and render time. The plugins around it (manim-slides, manim-voiceover) are maintained. The JS-side alternatives differ a lot in licensing: Motion Canvas is MIT, while Remotion needs a paid company license at 4+ employees.

### Cited Findings
- **Manim CE v0.21.0, released 10 Aug 2026**:
  - Adds **Typst support**, which compiles markup and math straight to SVG with no TeX needed.
  - Makes the **Cairo renderer ~2.2x faster** through vectorized operations.
  - Adds **parallel partial movie encoding**.
  - Improves NumPy array hashing to prevent stale cache hits.
  - Fixes OpenGL crashes.
  - Breaking changes: `Code` coloring now goes through Pygments (`formatter_style`), and `Camera.convert_pixel_array()` loses `convert_from_floats`.
  - [Manim v0.21.0 changelog](https://docs.manim.community/en/stable/changelog/0.21.0-changelog.html)
- **Manim CE v0.20.0, released 20 Feb 2026**. Breaking changes: ImageMobject 3D rotation/flip fixes, and some image resampling algorithms (lanczos, antialias, box, hamming) removed. — [v0.20.0 changelog](https://docs.manim.community/en/stable/changelog/0.20.0-changelog.html); [Changelog index](https://docs.manim.community/en/stable/changelog.html); [GitHub releases](https://github.com/ManimCommunity/manim/releases)
- **manim-slides**: latest release 5.6.0, 15 Apr 2026. It turns Manim scenes into presentation slides; the project also has HTML/reveal.js export, which I did not re-verify for this version. — [PyPI manim-slides](https://pypi.org/project/manim-slides/); [Releases](https://github.com/jeertmans/manim-slides/releases)
- **manim-voiceover**: current docs version is v0.3.7, under the ManimCommunity org. It syncs animation timing to TTS or recorded narration. — [manim-voiceover docs](https://voiceover.manim.community/en/stable/index.html); [GitHub](https://github.com/ManimCommunity/manim-voiceover); [Manim guide: Adding voiceovers](https://docs.manim.community/en/stable/guides/add_voiceovers.html)
- **Remotion** (React/TS video) uses its own source-available license, not OSS:
  - Free for individuals, non-profits, and for-profits with up to 3 employees.
  - 4+ employees need a Company License: $25/seat/month (Creators), or $0.01/render with a $100/month minimum (Automators). Enterprise starts at $500/month.
  - [Remotion pricing](https://www.remotion.dev/docs/license/pricing); [Remotion LICENSE](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md); [remotion.pro license](https://www.remotion.pro/license)
- **Motion Canvas** is MIT-licensed and free for any use. Revideo is a related fork. (Secondary comparison sources.) — [PkgPulse comparison](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026); [RenderComp comparison](https://rendercomp.com/blog/remotion-vs-motion-canvas-comparison/)
- **Manim in the browser**:
  - "Academa Studio" runs a Rust/wgpu engine in WebAssembly under Pyodide via PyO3 and claims 1:1 Manim CE API compatibility. It is **proprietary and closed-source**, and HN commenters objected to its use of the Manim name. — [Hacker News thread](https://news.ycombinator.com/item?id=49091703)
  - Open community experiments exist: `manim-web` on PyPI, loaded with micropip in Pyodide ([PyPI manim-web](https://pypi.org/project/manim-web/); [MathItYT demo repo](https://github.com/MathItYT/manim-web-demo)), and a Transcrypt-based port ([hugo-s29/manim-web-transcrypt](https://github.com/hugo-s29/manim-web-transcrypt)).

### Inferences
- **Typst math in v0.21 is the most important Manim change for AetherLab.** A Windows desktop app that no longer needs MiKTeX/TeX Live has a much simpler installer and loses a whole class of render failures (missing LaTeX packages, `Tex("m_1")` text-mode errors, like the fix in commit 765a5ea). This needs a spike: check how many of the curated scene components still work with `Typst`/`MathTypst`-style mobjects. The class names were not checked in the changelog summary.
- Upgrading to 0.21 should give faster local renders (Cairo speedup plus parallel partial encoding) at no cost, but the pinned version and any `Code`-mobject usage need checking against the breaking changes.
- **manim-voiceover is the natural way to fix narration–animation sync.** It exposes `tracker.duration` and bookmarks, so a local TTS engine such as Kokoro can plug in as a custom SpeechService.
- manim-slides could give students and teachers a "present this derivation step by step" export with no new renderer.
- Remotion is a poor fit for a commercial product once the team grows (per-seat fees). Motion Canvas (MIT) is the permissive JS option if AetherLab ever wants a web-native animation layer. Either one means rewriting the code-generation target away from Manim.

### Gaps
- The **status of Manim CE's OpenGL renderer** (still experimental or not) in 0.20/0.21 was not stated in the changelog summaries. Only "OpenGL crash fixes" were mentioned.
- **ManimGL** (3b1b) release cadence in 2025–2026 and **Reanimate** status (believed dormant) were not verified.
- Current maintenance activity of Motion Canvas (releases in 2026) was not verified.
- The exact Typst mobject API names and how complete its LaTeX-to-Typst math coverage is were not verified.

---

## 2. LLM techniques for reliable Manim/physics code generation

### Takeaway
Research published in 2025–2026 confirms that zero-shot Manim generation is unreliable: the median model runs only about a third of the time on ManiBench. What works is agentic loops that plan first, use version-aware constraints, and add render and vision feedback, which is close to AetherLab's current design. The best published figure is TheoremExplainAgent's 93.8% success with o3-mini. VLM critics are still reported to misread visual content. DashScope's structured outputs and context caching give cheap, direct improvements.

### Cited Findings
- **ManiBench (arXiv 2603.13251, 2026)** is a benchmark for Manim CE generation. It measures:
  - Executability.
  - **Version-Conflict Error Rate** (mixing ManimGL and ManimCE APIs).
  - Alignment (whether the required visual events happen, and in the right order).
  - Pedagogical coverage.

  The pilot has 12 problems with 276 samples across 9 models. Results:
  - Best executability: **Kimi-K2.5 and Claude-Sonnet-4 at 66.7%**. The median was ~33%, and **Qwen-2.5-Coder scored 0%**.
  - Average coverage was only 0.17.
  - Common failures: ManimGL constructs such as `ShowCreation` in place of `Create`, invented classes (`MCircle`), missing animation steps, and wrong timing.
  - Mitigations: few-shot prompting (+11.1 pp on Gemma-3-27B) and **version-aware prompting that lists forbidden constructs, which "eliminates version conflicts entirely"**. The authors note that heuristic alignment scores saturate and call for vision-based checking.
  - [ManiBench](https://arxiv.org/html/2603.13251)
- **TheoremExplainAgent (ACL 2025)** uses a planner agent for story and narration plus a coding agent that writes Manim, producing 5+ minute videos. Its TheoremExplainBench covers 240 STEM theorems with 5 automated metrics. The o3-mini agent reached **93.8% success and an overall score of 0.77**, but most videos had minor layout problems. — [arXiv 2502.19400](https://arxiv.org/abs/2502.19400); [ACL Anthology](https://aclanthology.org/2025.acl-long.332/); [project page](https://tiger-ai-lab.github.io/TheoremExplainAgent/)
- **PhysicsSolutionAgent (arXiv 2601.13453, Jan 2026)** makes physics-problem explanation videos up to 6 minutes long with Manim. It uses automated checks on 15 quantitative parameters plus VLM feedback for iterative refinement.
  - Across 32 videos it reported a 100% completion rate and a 3.8/5 average automated score. The model was reported as "GPT-4-mini"; the exact model name was unclear in the abstract as fetched.
  - It still showed **visual layout inconsistencies and "errors in how visual content is interpreted during feedback"**, meaning the VLM critic was sometimes wrong.
  - [arXiv 2601.13453](https://www.arxiv.org/abs/2601.13453)
- **Manimator (arXiv 2507.14306)** turns research papers and math concepts into Manim explanations with LLMs. — [arXiv 2507.14306](https://arxiv.org/html/2507.14306v1)
- **DashScope structured outputs**: JSON Schema mode is supported on the Qwen3.7-Plus/Flash/Max and Qwen3.8-Max/Flash series, through the OpenAI SDK or DashScope SDK. — [Alibaba Cloud: structured output](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output); [QwenCloud structured output](https://docs.qwencloud.com/developer-guides/text-generation/structured-output)
- **DashScope context cache**:
  - *Implicit* cache: automatic; creation billed at normal price; **hits at ~20%** of the input price; no guaranteed TTL.
  - *Explicit* cache: creation at **125%**, **hits at ~10%**, fixed 5-minute TTL that resets on each hit.
  - Both need at least 1,024 tokens.
  - Some qwen3.8 models have different cached-token pricing.
  - [Alibaba Cloud context cache](https://www.alibabacloud.com/help/en/model-studio/context-cache); [QwenCloud context cache](https://docs.qwencloud.com/developer-guides/run-and-scale/context-cache)
- Base pricing seen on an aggregator: Qwen Plus from $0.115/1M input and $0.287/1M output; Qwen Max from $0.345/1M input and $1.38/1M output. This is secondary and the region is unclear. — [CloudPrice Qwen Plus](https://cloudprice.net/models/alibaba-qwen-plus); [CloudPrice Qwen Max](https://cloudprice.net/models/alibaba-qwen-max)
- **Local/offline models**:
  - Ollama hosts `qwen3-coder`, `qwen3-coder-next` and `qwen3`. — [ollama.com/library/qwen3-coder](https://ollama.com/library/qwen3-coder); [qwen3-coder-next](https://ollama.com/library/qwen3-coder-next); [qwen3](https://ollama.com/library/qwen3)
  - Secondary guides describe Qwen3-Coder 30B as a MoE with ~3.3B active parameters, ~19 GB at Q4_K_M and 256K context. Qwen3-Coder-Next has ~3B active of 80B total. They also say Qwen3-Coder has no tag under 10 GB, so 8 GB-VRAM users fall back to qwen2.5-coder:7b. These models are Apache 2.0.
  - [Morph: best Ollama models Aug 2026](https://www.morphllm.com/best-ollama-models); [Unsloth Qwen3-Coder guide](https://unsloth.ai/docs/models/tutorials/qwen3-coder-how-to-run-locally)

### Inferences
- **AetherLab's planner-first, self-healing and vision-critic design matches the best published systems.** What the literature says is missing:
  1. An explicit ManimCE-vs-ManimGL **forbidden-construct list** in the system prompt, since ManiBench shows this removes version conflicts.
  2. Few-shot examples taken from the curated `scene_components` library.
  3. A **deterministic, non-VLM layout check**, such as bounding-box overlap and off-frame detection on mobjects before render, because both TheoremExplainAgent and PhysicsSolutionAgent report layout as the main leftover defect and VLM critics misread frames.
- Use JSON Schema structured output for the planner and derivation stages, where schema-valid plans matter. Keep free-form code generation for the Manim script, checked by AST and dry-run.
- The long, stable system prompt (API rules, component catalog, few-shots) is a good candidate for **explicit context caching**: hits cost ~10% of the input price, and the 5-minute TTL resets inside a repair loop. That cuts the cost of repair iterations directly.
- ManiBench's 0% for Qwen-2.5-Coder warns against using small local coder models without heavy scaffolding. An offline mode should rely on the component library and templates more than free-form generation.
- ManiBench (12 problems) and TheoremExplainBench (240 theorems) could be adopted as external regression sets alongside the internal F-catalog.

### Gaps
- Fine-tuning on Manim code datasets: I found no specific public Manim fine-tuning dataset or model with licensing details in this session.
- ManiBench did not test Qwen3.x-Plus executability rates.
- Comparable DashScope pricing for Qwen3.7-plus specifically, as opposed to the generic "Qwen Plus", was not confirmed.

---

## 3. Interactive and real-time physics simulation

### Takeaway
2025–2026 made browser GPU compute mainstream: WebGPU now ships in Chrome, Edge, Firefox and Safari. MuJoCo has an **official** DeepMind WebAssembly build on npm, and Genesis reached 1.0 (Apache 2.0). For a Python desktop app, NVIDIA Warp and Qt Quick 3D Physics are the lowest-friction ways to add real-time, possibly differentiable, simulation next to Manim's pre-rendered output.

### Cited Findings
- **WebGPU is on by default in all major browsers since Nov 2025**:
  - Chrome/Edge on Windows, macOS and ChromeOS, plus Chrome on Android.
  - Firefox 141+ on Windows, and Firefox 145 on macOS ARM.
  - Safari 26 on macOS, iOS, iPadOS and visionOS.
  - Firefox on Linux and Android is still in progress.
  - [web.dev](https://web.dev/blog/webgpu-supported-major-browsers); [gpuweb Implementation Status](https://github.com/gpuweb/gpuweb/wiki/Implementation-Status)
- **MuJoCo WebAssembly**: DeepMind maintains an official WASM build of the MuJoCo API, shipped as an npm package (`mujoco-js` / `@mujoco/mujoco`) with TS types.
  - It has a single-threaded build and a multi-threaded `/mt` build that uses Web Workers and SharedArrayBuffer.
  - The bindings are "still a work in progress", and **Windows support was experimental as of 13 Nov 2025**.
  - Community predecessor: zalo/mujoco_wasm.
  - [google-deepmind/mujoco wasm README](https://github.com/google-deepmind/mujoco/blob/main/wasm/README.md); [npm mujoco-js](https://www.npmjs.com/package/mujoco-js); [zalo/mujoco_wasm](https://github.com/zalo/mujoco_wasm/)
  - Google has published a Gemini-powered browser robotics simulator built on MuJoCo WASM. — [DEV/Google AI](https://dev.to/googleai/building-a-gemini-powered-robotics-simulator-in-the-browser-with-mujoco-wasm-hjj)
- **Genesis**:
  - Licensed Apache 2.0.
  - **Genesis World 1.0 was released in May 2026**, and the project is now officially supported by Genesis AI.
  - Requires Python 3.10–3.13 and supports Linux and Windows x86 with NVIDIA GPUs. Its compiler, "Quadrants", targets CUDA, ROCm, Metal, Vulkan, x86 and ARM64.
  - Renderers: Nyx (proprietary), Luisa ray tracer and Pyrender, with PBR and Gaussian splats.
  - The README does not mention any released generative ("prompt-to-4D-world") features.
  - [Genesis README](https://github.com/Genesis-Embodied-AI/Genesis/blob/main/README.md)
  - The original Dec 2024 announcement claimed 10–80x speedups over GPU-accelerated stacks. — [Zhou Xian on X](https://x.com/zhou_xian_/status/1869511650782658846)
- **NVIDIA Warp**: Apache 2.0. It JIT-compiles Python kernels to CUDA or CPU. Kernels are **differentiable** and work with PyTorch, JAX and Paddle. It is related to Taichi and Numba, but uses C++/CUDA as its intermediate representation. — [NVIDIA/warp README](https://github.com/NVIDIA/warp/blob/main/README.md); [NVIDIA Developer: Warp](https://developer.nvidia.com/warp-python)
- **Qt Quick 3D Physics** is a high-level, **pure-QML** physics API for rigid bodies, static meshes and trigger bodies, with no C++ API. It went from tech preview in Qt 6.4 to a stable API in current Qt 6.11. QtQuick3D is included in PySide6-Addons. — [Qt Quick 3D Physics 6.11](https://doc.qt.io/qt-6/qtquick3dphysics-index.html); [PySide6.QtQuick3D](https://doc.qt.io/qtforpython-6/PySide6/QtQuick3D/index.html); [Qt blog 6.4](https://www.qt.io/blog/qt-quick-3d-physics-in-qt-6.4)
- **Pyodide** runs CPython plus NumPy and SciPy in the browser through WASM. It underpins the browser-Manim experiments in Section 1. — [Pyodide](https://cnseniorious000.github.io/pyodide/)

### Inferences
- **The cheapest upgrade for the "live parametric canvas" is a QML scene inside the PyQt/PySide window** (Qt Quick 3D plus Qt Quick 3D Physics), driven by parameters from the LLM planner. It is real-time and GPU-accelerated and needs no browser.
  - Caveat: AetherLab uses **PyQt6**. Qt Quick 3D bindings ship with PySide6-Addons; PyQt6 has a separate PyQt6-3D/QtQuick3D story that was not verified. This could push toward a PySide6 migration.
- **Pair Manim output with a live simulation.** Manim is the "explanation" view and a numeric sim (Warp/NumPy/MuJoCo) is the "play with it" view, both fed by the same numeric ground truth that the planner and physics verifier already compute.
- Warp's differentiability allows "solve for the launch angle that hits the target" interactions: inverse problems done by gradient descent, which is a new kind of pedagogy.
- Genesis and MuJoCo are robotics-oriented and heavy (Genesis needs an NVIDIA GPU in practice). They are overkill for intro mechanics and useful mainly for advanced rigid-body or soft-body demos.
- A web companion built on three.js/WebGPU plus MuJoCo WASM or Rapier could host shareable interactive versions of generated scenes.

### Gaps
- Licensing and current versions for **Three.js (MIT), p5.js (LGPL), Matter.js (MIT), Rapier (Apache-2.0), Taichi (Apache-2.0) and MJX** were not re-verified in this session. The values in parentheses are from background knowledge only; check them at [three.js](https://github.com/mrdoob/three.js), [p5.js](https://github.com/processing/p5.js), [Matter.js](https://github.com/liabru/matter-js), [Rapier](https://github.com/dimforge/rapier), [Taichi](https://github.com/taichi-dev/taichi), [MJX docs](https://mujoco.readthedocs.io/en/stable/mjx.html).
- Taichi's 2025–2026 maintenance activity was not verified. Reports of slowed development are unconfirmed.
- Whether PyQt6 has bindings for Qt Quick 3D Physics was not verified.

---

## 4. Symbolic/numeric verification and formal methods

### Takeaway
Formal physics in Lean 4 is maturing: PhysLean/HepLean has merged into **PhysLib**, and Lean4PHYS was published at ICLR 2026. It is still research-grade and mainly covers advanced theory, so it is not a practical checker for intro homework. For AetherLab, SymPy plus unit-aware numerics is the pragmatic verification layer, with Lean as a long-horizon experiment.

### Cited Findings
- **PhysLean** (formerly HepLean) formalizes physics definitions, theorems and calculations in Lean 4. It is open-source and community-run, and strongest in advanced theory (HEP, QFT, index notation). — [PhysLean GitHub](https://github.com/HEPLean/PhysLean); [physlean.com](https://physlean.com/GettingStarted)
- Tooby-Smith, "HepLean: Digitalising high energy physics", *Computer Physics Communications* 308 (2025). There is also a formally verified index-notation implementation. — [arXiv 2411.07667](https://arxiv.org/abs/2411.07667)
- **Lean4PHYS (ICLR 2026)** is a reasoning framework for **college-level** general physics in Lean 4. It launched **PhysLib** by merging PhysLean with Lean-QuantumInfo, and the repo is now under leanprover-community. — [ICLR 2026 paper](https://proceedings.iclr.cc/paper_files/paper/2026/file/2821de2dc3501f55732e59d053e9e0cb-Paper-Conference.pdf); [arXiv 2510.26094](https://arxiv.org/abs/2510.26094); [leanprover-community/physlib](https://github.com/leanprover-community/physlib)

### Inferences
- Lean4PHYS aiming at *college-level* physics is the first sign that formal checks could reach AetherLab's content level. A realistic near-term use is an offline research track, such as spot-checking a small set of canonical derivations, not per-request checking.
- The practical stack for AetherLab:
  1. SymPy to re-derive or simplify the LLM's closed-form result and compare it symbolically.
  2. `sympy.physics.units` or `pint` for dimensional consistency of every displayed equation.
  3. The existing numeric solver as ground truth.
  4. Cross-checking that animation parameters match the numeric solution. This fits the existing "physics verifier" (F101–F113).

### Gaps
- The versions, licenses (believed BSD for SymPy and pint) and current features of SymPy and pint were not re-verified in this session. See [SymPy units docs](https://docs.sympy.org/latest/modules/physics/units/index.html) and [pint](https://github.com/hgrecco/pint).
- No published system was found that pairs LLM physics explanations with automatic dimensional-analysis checks, so I have no benchmark evidence of how much it helps.

---

## 5. Voice and media: TTS, speech input, captions, AI video

### Takeaway
There are now permissively licensed local TTS models good enough for narration: **Kokoro-82M** (Apache 2.0, CPU-fast, 8 languages, no cloning) and **Chatterbox** (MIT, 0.5B, 5-second voice cloning). Whisper large-v3-turbo (MIT) covers offline speech input and captions. AI video generators remain physically unreliable: the best Physics-IQ score in the original study was 29.5%. Sora 2's API is shutting down on 24 Sep 2026, so it should not be a dependency.

### Cited Findings
- **Kokoro-82M**:
  - 82M parameters, StyleTTS 2 architecture with an ISTFTNet vocoder, 24 kHz output.
  - v1.0 has **8 languages and 54 voices**; v0.19 was English-only.
  - Official and community **ONNX exports** allow CPU and browser inference without PyTorch.
  - [onnx-community/Kokoro-82M-v1.0-ONNX](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX); [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases); [hexgrad/Kokoro-82M ONNX file](https://huggingface.co/hexgrad/Kokoro-82M/blob/e9d173129d407bf1378c402aba163de4dde2615e/kokoro-v0_19.onnx)
- Licenses and positioning (secondary comparison sites):
  - Kokoro is Apache 2.0, runs "faster than real time on CPU", and **cannot clone voices**.
  - **Chatterbox** (Resemble AI) is MIT, 0.5B, clones from ~5 s of audio, and has an emotion-exaggeration control. Resemble's *own* blind study had listeners prefer it over ElevenLabs 65.3% to 24.5%; this is vendor-run.
  - **F5-TTS weights are CC-BY-NC**, so non-commercial only.
  - [ocdevel TTS comparison](https://ocdevel.com/blog/20250720-tts); [FindSkill.ai](https://findskill.ai/blog/best-open-source-tts-2026/); [tryspeakeasy](https://www.tryspeakeasy.io/blog/open-source-text-to-speech-2026)
- **Whisper large-v3-turbo**:
  - The decoder is pruned from 32 to 4 layers, giving about 809M parameters, and it is much faster with minor quality loss.
  - Whisper code is MIT and weights are permissive. faster-whisper (CTranslate2) conversions exist for efficient local inference.
  - [openai/whisper-large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo); [openai/whisper](https://github.com/openai/whisper); [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3)
- **Physics-IQ** (DeepMind/INSAIT) tests video models on physical prediction with 396 real videos.
  - The **best model scored 29.5%** relative to a physical-variance upper bound. Models tested: Sora, Runway Gen 3, Pika 1.0, Lumiere, SVD and VideoPoet.
  - The finding: "visually compelling" does not mean physically accurate.
  - [arXiv 2501.09038](https://arxiv.org/html/2501.09038); [INSAIT](https://insait.ai/new-benchmark-physics-iq-challenges-ai-video-models-understanding-of-the-physical-world/)
  - A 2026 follow-up, "Physics-IQ Verified", reports that **Sora-2 and Veo-3**, the top two models, still struggle on a scenario text models infer easily. — [arXiv 2606.18943](https://arxiv.org/html/2606.18943v1)
  - VideoScience-Bench benchmarks scientific reasoning in video generation. — [arXiv 2512.02942](https://arxiv.org/pdf/2512.02942)
- **Sora 2 API deprecation**: OpenAI notified developers on 24 Mar 2026 that the Videos API and all Sora 2 model IDs will be removed on **24 Sep 2026**, with no successor named. The consumer app closed 26 Apr 2026 (secondary). — [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations); [OpenAI community thread](https://community.openai.com/t/is-the-sora2-api-still-working/1379946); [Spheron](https://www.spheron.network/blog/sora-2-api-shutdown-2026-self-hosted-video-alternatives/)
- **Veo 3.1 pricing** (secondary aggregator): Lite $0.03/s at 720p and $0.05/s at 1080p; Fast ~$0.15/s; Standard ~$0.75/s with native audio. — [BuildMVPFast July 2026](https://www.buildmvpfast.com/api-costs/ai-video); [ModelsLab comparison](https://modelslab.com/blog/api/veo-3-1-vs-kling-3-sora-2-ai-video-api-cost-2026)

### Inferences
- **Recommended default narration: Kokoro (ONNX, CPU) wired in through a manim-voiceover SpeechService.**
  - It is fully offline, free, Apache 2.0 and multilingual (8 languages), and small enough to bundle.
  - Chatterbox can be an optional "your own voice" feature (MIT), with consent and ethics guardrails for cloning.
  - Avoid F5-TTS and XTTS in a commercial build because of their licenses.
- Whisper-turbo enables **spoken questions** ("explain why the pendulum period doesn't depend on mass") and **auto-captions/SRT** for rendered MP4s. Because the narration script is already known, captions can also come straight from the TTS text and timing with no ASR at all.
- AI video models are unsuitable as the *core* engine for a physics tutor: Physics-IQ scores are low and Sora's API is going away. At most they could make cosmetic B-roll ("real-world footage of a bridge oscillating") clearly labeled as illustrative. Deterministic Manim plus numeric sims is a real accuracy advantage that marketing can use.

### Gaps
- Piper, XTTS (Coqui CPML license; Coqui the company closed), Fish Audio and cloud TTS (Azure, Google, ElevenLabs) pricing were not verified in this session.
- Kokoro's exact language list, including whether it covers languages needed for target markets such as Russian or Kazakh, was not confirmed.
- Kling 3.0 pricing and physics evaluations were not verified from primary sources.

---

## 6. Vision/handwriting input (photo-of-homework to LaTeX)

### Takeaway
Open, small document VLMs now rival commercial OCR on formulas. **PaddleOCR-VL** (0.9B) handles printed and handwritten math to LaTeX, and version 1.6 (May 2026) is SOTA on OmniDocBench. Together with the vision-capable Qwen model AetherLab already uses, this makes a "snap your homework" input path feasible offline or cheaply.

### Cited Findings
- **PaddleOCR-VL** is an ultra-compact 0.9B vision-language model for multilingual document parsing. It covers text, tables and **printed/handwritten/vertical formulas to LaTeX**. Formula CDM on OmniDocBench v1.5 is 91.43.
  - PaddleOCR-VL-1.5 was open-sourced 29 Jan 2026.
  - **PaddleOCR-VL-1.6 was open-sourced 28 May 2026** with 96.3% on OmniDocBench v1.6.
  - [arXiv 2510.14528](https://arxiv.org/html/2510.14528v1); [HF PaddlePaddle/PaddleOCR-VL](https://huggingface.co/PaddlePaddle/PaddleOCR-VL); [PaddleOCR docs](http://www.paddleocr.ai/main/en/index.html)
- OmniDocBench (CVPR 2025) is the standard document-parsing benchmark. — [OmniDocBench](https://github.com/opendatalab/OmniDocBench)
- **Pix2Text** is an open-source Python alternative to Mathpix covering layout, tables and formulas, with an improved handwritten-formula model and 80+ languages. — [breezedeus/Pix2Text](https://github.com/breezedeus/Pix2Text)

### Inferences
- The simplest option is to route the photo to the configured **Qwen vision model** (already present for the critic) with a "transcribe to LaTeX plus a structured problem statement" JSON-schema prompt.
- PaddleOCR-VL makes a good local/offline fallback and a cross-check. When two OCR paths disagree, ask the user to confirm the equation before planning.
- Sketch-to-diagram (a free-body diagram drawn on a tablet, turned into a scene spec) is a natural extension using the same VLM with a constrained schema. No specific production tool was found.

### Gaps
- PaddleOCR-VL's license (believed Apache 2.0, like PaddleOCR) was not confirmed on the model card in this session.
- Mathpix's current API pricing and terms were not verified.
- I found no published accuracy figures specifically for photographed handwritten *physics* homework, as opposed to document benchmarks.
- No mature open-source sketch-to-physics-diagram tool was identified.

---

## 7. AR/VR/3D

### Takeaway
WebXR is the low-cost route into headsets. Safari on visionOS 2+ supports immersive-VR sessions by default, but not the AR module yet, and Quest Browser supports passthrough AR, hand tracking and anchors. A WebXR viewer for generated 3D scenes would reach both headsets without native apps.

### Cited Findings
- Safari on visionOS 2 enables WebXR `immersive-vr` by default with gaze-and-pinch input. The **WebXR AR Module is not yet enabled** on Vision Pro. — [Brown VR wiki](https://www.vrwiki.cs.brown.edu/hardware/vr-hardware/apple-vision-pro/development-approaches-for-visionos/webxr-on-visionos); [Apple WWDC24 WebXR session](https://developer.apple.com/videos/play/wwdc2024/10066/); [UploadVR](https://www.uploadvr.com/webxr-vision-pro-cross-compatible-quest/)
- Meta Quest Browser supports WebXR passthrough AR, plane detection, anchors and hand tracking. Chrome, Edge, Samsung Internet, Opera, Quest Browser and visionOS Safari all implement the core spec, with varying feature coverage. — [TestMu WebXR browser support 2026](https://www.testmuai.com/learning-hub/webxr-compatible-browsers/); [abratabia WebXR support](https://www.abratabia.com/webxr-games/webxr-device-support.php)
- A claim that "WebXR adoption grew 40% in 2026" comes from an unattributed trade article and should not be quoted as fact. — [VR.org](https://vr.org/articles/webxr-adoption-surge-2026-browsers-vs-apps)

### Inferences
- Manim's 3D scenes are pre-rendered video, so they cannot become XR directly. XR requires a scene description (e.g., glTF plus a parameter/timeline JSON) rendered by three.js/WebXR. This is another argument for a **structured scene spec produced by the planner**, from which both Manim code and web/XR views can be generated.

### Gaps
- No specific high-quality Vision Pro or Quest physics-education apps were catalogued, and there is no market data on classroom headset use.

---

## 8. Distribution and infrastructure

### Takeaway
For a PyQt6 desktop app, Nuitka is the recommended packager for fewer antivirus false positives and smaller binaries. GitHub-hosted runner prices fell on 1 Jan 2026 (Linux $0.006/min), which keeps GitHub-Actions cloud rendering cheap. Typst in Manim 0.21 could remove the biggest installer dependency (TeX).

### Cited Findings
- **Packaging**:
  - PyInstaller's self-extracting bootloader triggers antivirus heuristics.
  - Nuitka compiles Python to C to a native binary and usually gets fewer false positives. One developer reported going from 11/61 to 1/60 VirusTotal detections, which is anecdotal.
  - Qt recommends Nuitka or PyInstaller for PySide6 deployment. Nuitka makes smaller binaries and PyInstaller builds faster.
  - [pythonguis FAQ](https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/); [DEV: PyInstaller to Nuitka](https://dev.to/weisshufer/from-pyinstaller-to-nuitka-convert-python-to-exe-without-false-positives-19jf); [DEV: Nuitka vs PyInstaller](https://dev.to/il3ven/nuitka-vs-pyinstaller-distributing-a-python-application-3ah7)
- **GitHub Actions pricing**:
  - From 1 Jan 2026, hosted-runner prices dropped up to 39%: Linux x86 $0.008 to **$0.006/min**, Windows $0.016 to $0.010, macOS $0.080 to $0.062.
  - A proposed $0.002/min self-hosted platform fee was postponed indefinitely after backlash.
  - **Public-repo runner usage remains free**, and free-minute quotas are unchanged.
  - [GitHub changelog](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/); [Northflank](https://northflank.com/blog/github-pricing-change-self-hosted-alternatives-github-actions); [WarpBuild](https://www.warpbuild.com/blog/github-actions-price-change)
- WebGPU in all major browsers and MuJoCo/Pyodide WASM (Section 3) make a browser companion feasible.

### Inferences
- Cloud render cost estimate: a 2-minute Manim render taking ~5 runner-minutes on Linux costs about $0.03. That is negligible next to LLM tokens, so cloud rendering can be the default on low-end student PCs. Note GitHub's ToS on using Actions as a general compute service; this needs review.
- Suggested distribution path:
  1. Nuitka-built Windows installer with Typst in place of TeX and bundled Kokoro ONNX. This makes the app self-contained and offline-capable when paired with Ollama.
  2. Later, a web companion (Pyodide or a server-side renderer, with WebGPU sims) for sharing and for Chromebook/iPad classrooms.
- Tauri or Electron would mean a UI rewrite away from PyQt, which only makes sense if a web-first product is chosen.

### Gaps
- Tauri vs Electron and mobile (Flutter/React Native) trade-offs were not researched.
- GitHub's acceptable-use terms for Actions-as-render-farm were not checked.
- Alternative GPU and cloud render pricing (Modal, RunPod, Lambda) was not collected.
