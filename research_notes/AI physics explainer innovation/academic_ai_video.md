# Academic Literature (2023–2026): LLM/Agent-Generated Educational Animations & Videos (Math/Physics) and Their Evaluation

Scope note: research conducted 2026-09-23 via arXiv/OpenReview/GitHub. About 25 search/fetch calls. Numbers come from primary arXiv pages (HTML/abstract) unless noted. Where only a search snippet was available, that is flagged.

---

## Q1. Agent architectures for Manim/code-driven educational video: what works and what success/quality numbers were reported?

### Takeaway
The best systems all use a **planner/storyboard, then a coder, then a render-in-the-loop repair step, then a VLM visual critic**. The ablations agree on what matters most: **planning** (removing it costs about 40 points in Code2Video), then **grounding/asset or doc retrieval**, then **explicit spatial anchoring for the visual critic**, then the critic itself. Plain Manim-doc RAG has mixed results. **Memory of the system's own past failures and successes** (ManimAgent) cuts repair rounds roughly in half. Render success of about 94% is now reachable, even with a 30B open model plus render-loop plus doc retrieval.

### Cited Findings

**TheoremExplainAgent / TheoremExplainBench (TIGER-Lab, arXiv 2502.19400, ACL 2025 oral)**
- The architecture has two agents. A **planner agent** produces a multi-scene story plan and narration, with visual elements, animations and transitions specified per scene. A **coding agent** writes Manim scripts and gets **up to 5 error-correction retries**. A multifaceted **RAG over Manim documentation** uses dynamic queries at the storyboard, implementation and error-correction stages — [arXiv HTML 2502.19400v1](https://arxiv.org/html/2502.19400v1)
- The benchmark has **240 theorems** across STEM (math, physics, CS, chemistry), split by difficulty — [arXiv 2502.19400](https://arxiv.org/abs/2502.19400); [HF dataset](https://huggingface.co/datasets/TIGER-Lab/TheoremExplainBench)
- Success rates: **o3-mini 93.8%**, GPT-4o 55.0% (61.3% on easy, falling to 46.2% on hard), Gemini 2.0-Flash 14.6%, Claude 3.5-Sonnet 2.1% — [arXiv HTML](https://arxiv.org/html/2502.19400v1)
- Overall quality score: o3-mini 0.77, GPT-4o 0.77, GPT-4o+RAG 0.76. **Human-made videos also score 0.77**, so the automatic metric saturates and cannot tell agents from humans — [arXiv HTML](https://arxiv.org/html/2502.19400v1)
- RAG ablation: RAG **lowered** GPT-4o success from 55.0% to 45.8% but raised Claude from 2.1% to 14.6%. The authors blame generic, misaligned doc retrievals and a large increase in input tokens — [arXiv HTML](https://arxiv.org/html/2502.19400v1)
- Agentic planning made long videos possible: **up to about 10 minutes, against about 20 s without agents**. Most videos had "minor issues with visual element layout". Multimodal explanations exposed reasoning flaws that text explanations hid. Chemistry had the lowest success because apparatus is hard to visualize — [arXiv 2502.19400](https://arxiv.org/abs/2502.19400); [HTML](https://arxiv.org/html/2502.19400v1)
- Code: [GitHub TIGER-AI-Lab/TheoremExplainAgent](https://github.com/TIGER-AI-Lab/TheoremExplainAgent); project page [tiger-ai-lab.github.io/TheoremExplainAgent](https://tiger-ai-lab.github.io/TheoremExplainAgent/)

**Code2Video (Show Lab, arXiv 2510.01174; NeurIPS 2025 DL4C workshop; GitHub lists ICML 2026)**
- Three agents:
  - **Planner**: builds a temporally coherent lecture flow and prepares visual assets.
  - **Coder**: turns the plan into Python/Manim and uses **scope-guided auto-fix ("ScopeRefine")**.
  - **Critic**: a VLM that uses **visual anchor prompts** to refine layout.
  - [arXiv 2510.01174](https://arxiv.org/abs/2510.01174); [GitHub showlab/Code2Video](https://github.com/showlab/Code2Video)
- ScopeRefine is a 3-level hierarchical debug:
  1. **Line scope** (±1 line, up to K₁ fixes)
  2. **Block scope** (the lecture-line block, K₂ attempts)
  3. **Global** section regeneration as a fallback
  - Removing ScopeRefine made **time 2.5–5.6× longer and tokens 1.4–1.7× higher** — [arXiv HTML 2510.01174](https://arxiv.org/html/2510.01174)
- The visual anchor prompt puts a **6×6 grid of discrete anchor points** on the canvas and places elements at point level or region level (multi-cell boxes). A 6×6 grid worked best: 4×4 underperformed and 8×8 caused clutter — [arXiv HTML](https://arxiv.org/html/2510.01174)
- The MMMC benchmark has **456 videos** (117 full-length plus 339 segmented clips) across **13 disciplines**, including Calculus, Geometry, Probability, Neural Networks and Physics. Full videos average 1014 s and clips average 201 s — [arXiv HTML](https://arxiv.org/html/2510.01174)
- Main results (Aesthetics / TeachQuiz, 0–100):

  | Method | Aesthetics | TeachQuiz | Time |
  |---|---|---|---|
  | Human 3Blue1Brown | 99.7 | 97.1 | – |
  | Veo3 (pixel-space video model) | 9.0 | 2.5 | – |
  | Direct code generation (GPT-5) | 32.7 | 36.5 | 1.8 min |
  | Code2Video (GPT-4.1) | 79.0 | 82.0 | 15.4 min |
  | Code2Video (Claude Opus) | 87.9 | 86.0 | 13.8 min |

  — [arXiv HTML](https://arxiv.org/html/2510.01174)
- Ablations (drops in Aesthetics / TeachQuiz):
  - **Planner**: −40.9 / −41.5
  - **External asset database**: −10.9 / −30.0
  - **Visual anchors**: −9.8 / −26.8
  - **Critic**: −6.5 / −21.3
  - Removing parallel processing raised time from 15.4 to 86.6 min.
  - [arXiv HTML](https://arxiv.org/html/2510.01174)
- The abstract headline is "40% improvement over direct code generation", with some categories surpassing human tutorials — [arXiv 2510.01174](https://arxiv.org/abs/2510.01174)

**ManimAgent: Self-Evolving Multimodal Agents for Visual Education (arXiv 2606.30296, 2026)**
- It uses six roles: Storyboarder, Coder, text Reviewer, **VLM Reviewer**, Visual Reviser, and distillers (Rationale Writer, Lesson Distiller) — [arXiv HTML 2606.30296](https://arxiv.org/html/2606.30296)
- The VLM critic is GPT-5.5 as reported. It scores keyframes on **logical flow, layout/occlusion and accuracy**.
- The reflection loops are bounded: text reflection gets **2 retries** and short-circuits on repeated error categories; visual reflection gets **2 iterations** and auto-passes at score ≥90 — [arXiv HTML](https://arxiv.org/html/2606.30296)
- Its key idea is a **dual-channel Episodic Memory Bank**:
  - **ℳ+** stores success rationales from scenes scoring ≥85, used as soft "Reference Examples".
  - **ℳ−** stores validated failure patterns, from crash→success fixes or visual-score improvements, used as hard "Known Pitfalls".
  - Lessons are distilled by an LLM rather than stored as raw diffs.
  - [arXiv HTML](https://arxiv.org/html/2606.30296)
- Results (human Pass@1 / reflection rounds / human quality out of 5):
  - VLM reflection only: 68.5% / 12.2 / 3.41
  - **Manim-code RAG**: 83.3% / 11.4 / 3.65
  - Empty memory (EMB@0): 62.0% / 12.2 / 3.26
  - **EMB@200: 84.9% / 6.5 / 3.88**
  - [arXiv HTML](https://arxiv.org/html/2606.30296)
- Ablations:
  - Without ℳ+, Pass@1 falls to 70.0%.
  - Without ℳ−, Pass@1 is 79.9% but rounds rise to 11.6.
  - Ungated ℳ− gives 81.8%.
  - Top-1 retrieval gives 81.0%.
  - A weaker VLM reviewer gives 80.0% with quality 3.42.
  - [arXiv HTML](https://arxiv.org/html/2606.30296)
- The benchmark uses paper-section animation tasks: 39 memory-building, 33 fixed-probe, 40 cross-test and a 195-task quarantined holdout. The paper gives **no direct numeric comparison** with TheoremExplainAgent or Code2Video and calls them complementary — [arXiv HTML](https://arxiv.org/html/2606.30296)

**Training and Agentic Inference Strategies for LLM-based Manim Generation (Nottingham Trent, arXiv 2604.18364, 2026)**
- Training uses SFT with LoRA r=8 on **ManimBench** (417 human-reviewed code–description pairs, 100 for test). **GRPO** follows, with the reward 0.2·text + 0.8·visual:
  - text part = geometric mean of CodeBLEU and CodeBERT
  - visual part = geometric mean of SSIM and CLIP similarity, with DTW frame alignment
  - [arXiv HTML 2604.18364](https://arxiv.org/html/2604.18364)
- At inference, **Renderer-in-the-loop (RITL)** feeds render errors back for K rounds. **RITL-DOC** also retrieves API docs for the specific function calls extracted from the code — [arXiv HTML](https://arxiv.org/html/2604.18364)
- Best result: **Qwen3-Coder-30B with GRPO + RITL-DOC (3 loops) reached 94% render success and 85.7% visual similarity**, which is +2pp render success and +3.8pp visual similarity over a GPT-4.1 baseline. Vanilla Qwen3-Coder-30B reached 66% / 59.2%. With SFT + RITL it reached 90% / 82.2% — [arXiv HTML](https://arxiv.org/html/2604.18364)
- Inference-time strategies (RITL, RITL-DOC) gave larger gains than fine-tuning alone, and 3 loops beat 1. Code metrics correlate weakly with visual metrics, because different code can produce similar visuals. Small models (≤4B) hallucinated spatial-positioning API parameters and got overloaded by doc context — [arXiv HTML](https://arxiv.org/html/2604.18364)

**Other systems**
- **Manimator** (arXiv 2507.14306): paper or prompt → LLM scene description (concepts, formulas, visual elements) → a second LLM writes Manim code → render. The only reported adoption figure is usage (about 5000 uses in a week), with no formal quality benchmark — [arXiv 2507.14306](https://arxiv.org/abs/2507.14306); [GitHub](https://github.com/HyperCluster-Tech/manimator)
- **LASEV** ("Beyond End-to-End Video Models", arXiv 2602.11790, KDD 2026 ADS):
  - Agents: an Orchestrating agent, a **Solution agent** (step-by-step problem solving), an Illustration agent (visualization code) and a Narration agent.
  - Outputs are **structured executable video scripts**, assembled with templates.
  - Quality gates combine semantic critique, rule-based constraints and tool-based compilation checks.
  - Reported: over 1M videos/day and over 95% cost reduction. No acceptance-rate figure in the abstract.
  - [arXiv 2602.11790](https://arxiv.org/abs/2602.11790)
- **Paper2Video / PaperTalker** (Show Lab, arXiv 2510.05096):
  - Benchmark: 101 papers with author-made talks.
  - Pipeline: LaTeX (Beamer) slide generation, **Tree Search Visual Choice** for layout, personalized TTS, talking head, cursor grounding.
  - Best scores: Meta Similarity (0.646 speech / 1.97 content), PresentArena win rate 17.0%, **PresentQuiz 50.0%**, IP Memory 50.0%.
  - [arXiv 2510.05096](https://arxiv.org/abs/2510.05096); [project](https://showlab.github.io/Paper2Video/); [GitHub](https://github.com/showlab/Paper2Video)
- Other related works found but not read in detail:
  - **VideoAgent: Personalized Synthesis of Scientific Videos** ([arXiv 2509.11253](https://arxiv.org/pdf/2509.11253))
  - **ViviDoc** interactive documents ([arXiv 2603.27991](https://arxiv.org/pdf/2603.27991))
  - A Springer chapter, "LLM Approaches to Educational Video Generation Using Manim" ([Springer](https://link.springer.com/chapter/10.1007/978-3-032-07938-1_26))
  - ManimML ([arXiv 2306.17108](https://arxiv.org/abs/2306.17108))

### Inferences
- AetherLab already follows the consensus shape: storyboard, then coder, then lint/self-heal, then VLM critic. The measured gaps are elsewhere:
  - **(a) Explicit spatial anchoring for the critic.** Code2Video's 6×6 grid was worth about 27 TeachQuiz points; AetherLab's critic appears to lack it.
  - **(b) Hierarchical, scoped repair** (line → block → scene) instead of whole-scene regeneration. This gives 2.5–5.6× time savings.
  - **(c) Targeted retrieval.** Pull API docs **for the functions actually called in the failing code** (RITL-DOC), not a generic doc search. TheoremExplainAgent's generic RAG hurt GPT-4o.
  - **(d) A persistent pitfall/success memory**, distilled from AetherLab's own crash→fix history. ManimAgent reports this halves repair rounds at equal pass rate. It maps naturally onto the existing self-heal and lint logs.
  - **(e) A bounded critic loop** (2 text + 2 visual rounds, auto-pass threshold). More loops show diminishing returns.
- AetherLab's curated numeric-driven components play the role of Code2Video's "external asset database" (−30 TeachQuiz when removed) and of LASEV's templates. Expanding and preferring them is supported by evidence.
- LASEV's separate "Solution agent" feeding illustration and narration mirrors AetherLab's derivation → animation flow. It argues for passing verified numbers, not free text, into the storyboard.

### Gaps
- No benchmark named "MathVideo" or "PhysVideo" was found. Physics-specific explainer-video benchmarks seem not to exist; physics appears only as one category in TheoremExplainBench and MMMC.
- Paper2Poster numbers were not retrieved.
- ManimAgent's comparison to TheoremExplainAgent and Code2Video is qualitative only.
- There is no per-discipline (physics-only) breakdown for Code2Video in what was fetched.

---

## Q2. How is educational-video quality evaluated automatically?

### Takeaway
There are three families of automatic evaluation:
- **VLM/LLM-as-judge rubrics**: layout, visual relevance, logic flow, consistency, accuracy.
- **Knowledge-transfer quizzes**: a VLM or VideoLLM answers questions after "watching", as in TeachQuiz and PresentQuiz.
- **Reference-similarity metrics**: SSIM/CLIP/DTW, or slide/speech similarity.

Human correlation is **only strong for visual relevance (ρ≈0.72)**. It is weak for accuracy and logic (ρ≈0.14–0.17), so LLM judges do not reliably certify correctness.

### Cited Findings
- **TheoremExplainBench** scores 5 dimensions on 0–1, combined by geometric mean:
  - Accuracy & Depth: GPT-4o on the transcript
  - Visual Relevance: GPT-4o on keyframes
  - Logical Flow: GPT-4o on the transcript
  - Element Layout: GPT-4o on frames
  - Visual Consistency: Gemini 2.0-Flash on video chunks
  - [arXiv HTML 2502.19400](https://arxiv.org/html/2502.19400v1)
- Spearman correlation with humans: Visual Relevance **0.72**, Element Layout 0.42, Visual Consistency 0.17, Logical Flow 0.16, **Accuracy & Depth 0.14**. Human inter-rater Krippendorff α was 0.31–0.56 — [arXiv HTML](https://arxiv.org/html/2502.19400v1)
- **TeachQuiz** (Code2Video):
  - Step 1 "unlearns" the VLM's prior knowledge of the concept by selective prompting.
  - Step 2 has it watch the generated video and answer **10 MCQs per concept**.
  - Score = post-video accuracy − unlearned baseline.
  - Aesthetics uses 5 VLM-judge dimensions (0–100): Element Layout, Attractiveness, Logic Flow, Visual Consistency, Accuracy & Depth.
  - [arXiv HTML 2510.01174](https://arxiv.org/html/2510.01174)
- Code2Video's human study (8 participants, 20 topics):
  - Code2Video videos: 80.3 aesthetics, 64.0 quiz, **80% completion willingness**.
  - Human videos: 97.0 aesthetics, 78.8 quiz, **36% completion** (long videos reduce attention).
  - Aesthetics and TeachQuiz correlated at r=0.971 (p=0.0059).
  - [arXiv HTML](https://arxiv.org/html/2510.01174)
- **Paper2Video metrics**:
  - Meta Similarity: VLM 5-point slide/subtitle similarity plus speaker-embedding cosine for speech.
  - PresentArena: pairwise VideoLLM preference.
  - **PresentQuiz**: MCQs from the paper, answered by a VideoLLM after watching.
  - IP Memory: whether the audience remembers the authors and work.
  - [arXiv 2510.05096](https://arxiv.org/abs/2510.05096); [emergentmind summary](https://www.emergentmind.com/topics/paper2video-benchmark)
- **ManimAgent** uses human Pass@1 (usable on first delivery), the number of reflection rounds (a repair-cost metric), human quality on 1–5, and Cohen's/Fleiss' kappa for rater reliability — [arXiv HTML 2606.30296](https://arxiv.org/html/2606.30296)
- **ManimBench / 2604.18364** uses:
  - Render Success Rate
  - Visual Similarity: geometric mean of SSIM and CLIP similarity with DTW frame alignment
  - CodeBERTBLEU
  - AST metrics turned out not to correlate with anything.
  - [arXiv HTML 2604.18364](https://arxiv.org/html/2604.18364)

### Inferences
- For AetherLab's automated QA/regression (e.g., test_features.py-style gates), a cheap, robust stack would be:
  - render success
  - repair rounds per scene
  - a **deterministic layout-overlap metric** computed from Manim mobject bounding boxes. This is more reliable than a VLM judge, which reached only ρ=0.42 against humans.
  - a TeachQuiz-style check: generate 5–10 MCQs from the verified derivation, then have a VLM answer them from sampled frames plus the narration transcript, with and without the video.
- VLM "accuracy" scores should not be trusted as a correctness signal (ρ=0.14). Physics correctness should come from the numeric verifier or symbolic checks (see Q4).
- The completion-willingness result argues for **shorter chapters** in narrated multi-chapter lessons.

### Gaps
- Nothing found on standardized automatic metrics for **narration–visual timing sync** (e.g., alignment of spoken term to on-screen element).
- No published deterministic bounding-box overlap metric was found. Existing "Element Layout" scores are all VLM-judged.

---

## Q3. Known failure modes (layout overlap, LaTeX errors, wrong motion, hallucinated physics, pacing, sync)

### Takeaway
Crashes are dominated by **Manim API hallucination**, then **LaTeX errors**, then ordinary coding bugs. Among videos that render, the dominant defect is **layout overlap/overcrowding**. Pixel-space video generators additionally fail at text rendering and physical plausibility. Visualizing an explanation also exposes reasoning errors that text hides.

### Cited Findings
- TheoremExplainAgent failure taxonomy:
  1. **Manim code hallucinations** (the majority): nonexistent functions, invalid parameter types, wrong signatures.
  2. **LaTeX rendering errors**: syntax and special characters.
  3. General coding errors: missing imports, undefined variables, NumPy errors.
  - [arXiv HTML 2502.19400](https://arxiv.org/html/2502.19400v1)
- "Most of the videos produced exhibit minor issues with visual element layout", and "multimodal explanations expose deeper reasoning flaws that text-based explanations fail to reveal" — [arXiv 2502.19400](https://arxiv.org/abs/2502.19400)
- Code2Video: code generation suffers **asset hallucination and layout overcrowding**. Pixel-based models (Veo3) show poor text rendering, inconsistent styling and weak temporal coherence; Veo3 scored TeachQuiz 2.5 against 86.0 — [arXiv HTML 2510.01174](https://arxiv.org/html/2510.01174)
- Small models hallucinate **spatial positioning parameters** after GRPO, and doc context saturates them — [arXiv HTML 2604.18364](https://arxiv.org/html/2604.18364)
- ManimAgent's critic axes are explicitly logical flow, **layout/occlusion** and accuracy. It lists visually ambiguous animations for complex relationships as a residual failure — [arXiv HTML 2606.30296](https://arxiv.org/html/2606.30296)
- Physics-plausibility failures in generative video are covered in Q5 (VideoPhy-2, PhyGenBench, VisPhyWorld).

### Inferences
- AetherLab's recent commit "auto-repair text-mode math so Tex('m_1') can't kill a render" matches the literature's #2 failure class. A pre-render **LaTeX compile check of every string** would catch the rest of that class before Manim runs, e.g. batch-compiling all Tex/MathTex strings once.
- For API hallucination (#1), a static check of every called Manim symbol and kwarg against the installed Manim version's signatures should be run before rendering. This is the deterministic version of RITL-DOC.
- "Physically wrong motion" in Manim is a distinct risk from pixel-video physics failure. Motion is only as right as the numbers driving the updaters. AetherLab's numeric-driven components with a verifier address this directly; free-form LLM-written motion code does not.

### Gaps
- No paper quantified **pacing** or **narration–visual desynchronization** rates for Manim agents.
- No paper quantified the rate of **physically incorrect motion** in LLM-written Manim, as opposed to pixel video. This appears to be an open, unmeasured problem.

---

## Q4. LLM physics problem-solving accuracy and verification methods

### Takeaway
Frontier reasoning models remain well short of reliable on multi-step physics:
- **PhysReason** hard problems: about 30–32% answer-level.
- **UGPhysics**: best overall about 49.8% (o1-mini).

Step-level errors are dominated by **calculation errors and theorem misapplication**. Multi-agent review adds only about 2–3 points on average. **SymPy step verification** and **Pint unit checking** are the emerging tool-grounded verifiers.

### Cited Findings
- **PhysReason** (arXiv 2502.12054, ACL 2025):
  - 1,200 problems (300 knowledge, 900 reasoning split into easy/medium/hard); an average of **8.1 steps**, and **15.6 steps for hard**; **81% include diagrams**.
  - Answer-level / step-level averages: Deepseek-R1 **56.75% / 73.26%**, Gemini-2.0-Flash-Thinking 54.73% / 69.73%, o3-mini-high 53.32% / 69.34%.
  - Hard split: about 30–32% answer-level.
  - PSAS auto-scoring is about 98% accurate.
  - [arXiv HTML 2502.12054](https://arxiv.org/html/2502.12054v1)
- PhysReason errors come in 7 types. **Calculation Process Error** (algebra, arithmetic, unit conversion) and **Physics Theorem Application Error** are most frequent. Stronger reasoning models show relatively more Physics Process Understanding Errors. Other types are condition analysis, diagram analysis, variable relationships and boundary conditions — [arXiv HTML](https://arxiv.org/html/2502.12054v1)
- **UGPhysics** (arXiv 2502.00334): 5,520 undergraduate problems in EN/ZH across 13 subjects. Best overall: **o1-mini 49.8%**. QwQ-32B 37.3%; Qwen2.5-Math-72B 39.5% — [arXiv 2502.00334](https://arxiv.org/html/2502.00334v2) (figures from search snippet of the arXiv page)
- **PhysicsEval** (arXiv 2508.00079):
  - 19,609 textbook problems (1,962 test) across 19 domains.
  - Multi-agent review (3 verifiers plus a meta-verifier) raised the Physics Proficiency Score: easy **88.96 → 91.78**, medium 79.21 → 81.48, hard 66.20 → 68.23 (p<0.05).
  - Self-refine sometimes **hurt**. Phi-4 gained 7.5 on hard problems.
  - [arXiv HTML 2508.00079](https://arxiv.org/html/2508.00079)
- **PRiSM** (arXiv 2512.05930) grounds evaluation in Python. It uses **Pint to enforce unit/dimensional consistency** and **SymPy** for symbolic manipulation and equation solving — [arXiv HTML 2512.05930](https://arxiv.org/html/2512.05930)
- **TPBench test-time scaling** (arXiv 2506.20729) proposes a **symbolic weak-verifier**. A SymPy-augmented grading agent generates and executes a SymPy script per derivation step to independently check each calculation — [arXiv 2506.20729](https://arxiv.org/abs/2506.20729); [NeurIPS ML4PS 2025 PDF](https://ml4physicalsciences.github.io/2025/files/NeurIPS_ML4PS_2025_20.pdf)
- **CMPhysBench** (arXiv 2508.18124) recommends embedding physics-aware verification, including **dimension/unit checks**, into decoding. It also recommends coupling models with symbolic/numeric tools for propose–check–revise derivations — [arXiv 2508.18124](https://arxiv.org/pdf/2508.18124)
- "Physics simulation capabilities of LLMs" (arXiv 2312.02091): GPT-4 struggles on research-level computational physics. About 40% of solutions "could pass" but contain significant coding and physics errors — [arXiv 2312.02091](https://arxiv.org/abs/2312.02091) (from search snippet)

### Inferences
- Take a pessimistic prior on LLM derivation correctness: roughly 50–75% on multi-step problems. The derivation step should therefore be **verified, not trusted**.
- The literature's best verification tools are:
  - **(a) Per-step SymPy re-execution**: extract each equation step and check its algebra and numerics.
  - **(b) Pint unit propagation** on every numeric quantity.
  - **(c) Cross-model review**, which gives small but significant gains, mostly on hard problems.
- Since calculation errors are the top error class, deterministic SymPy/Pint checks should catch the largest share.
- AetherLab's physics verifier could be extended from checking final numbers to **step-level SymPy + dimensional checks**, reusing PhysReason's error taxonomy as its error labels.

### Gaps
- OlympiadBench-physics and SciBench numbers were not retrieved in this pass.
- No paper was found measuring how much SymPy/Pint verification raises end-to-end physics accuracy with a clean before/after number. TPBench's exact figures were not in the abstract.

---

## Q5. Physics simulation from language and physical-plausibility benchmarks: relevance to trustworthy animations

### Takeaway
Pixel-space text-to-video models are physically unreliable: the best reaches only **32.6% joint** on VideoPhy-2, and 21.9% on its hard split. The trend is toward **LLM-planned, simulation- or computation-grounded** generation (PhysGen, PhyT2V, NEWTON, VisPhyWorld). Even so, MLLMs "struggle to accurately infer physical parameters" when writing simulator code. That supports AetherLab's approach of **deterministic numeric simulation driving code-rendered animation**, with the LLM choosing parameters rather than producing the motion.

### Cited Findings
- **VideoPhy** (arXiv 2406.03520, ICML 2024) has 688 prompts on solid–solid, solid–fluid and fluid–fluid interactions — [arXiv 2406.03520](https://arxiv.org/abs/2406.03520)
- **VideoPhy-2** (arXiv 2503.06800): the best model, **Wan2.1-14B, reaches 32.6% joint** (semantic plus physical adherence) on the full set and **21.9% on hard**. The closed model Ray2 trailed open models — [arXiv 2503.06800](https://arxiv.org/abs/2503.06800)
- **PhyGenBench** (arXiv 2410.05363, ICML 2025):
  - 160 prompts over 27 physical laws in mechanics, optics, thermal and material properties.
  - PhyGenEval is a hierarchical VLM + GPT-4o evaluator.
  - 8 models were tested (1,280 videos). Current models struggle, and "simply scaling up models or employing prompt engineering techniques is insufficient".
  - [arXiv 2410.05363](https://arxiv.org/abs/2410.05363); [GitHub](https://github.com/OpenGVLab/PhyGenBench)
- **PhyT2V** (arXiv 2412.00596) loops: an LLM identifies the physical rules, a captioner describes the generated video, the LLM finds mismatches, then refines the prompt with step-back reasoning. On CogVideoX-5B:
  - VideoPhy physical commonsense: **0.26 → 0.42** (2.3×)
  - PhyGenBench physical commonsense: 0.28 → 0.42
  - [arXiv HTML 2412.00596](https://arxiv.org/html/2412.00596)
- **NEWTON** (arXiv 2605.18396) is an agentic planner using keyframes, **scientific computation** and prompt refinement, plus a verifier with re-planning. The planner is trained with Flow-GRPO. VideoPhy-2 joint accuracy: **LTX-Video 21.4% → 29.7%; Veo-3.1 30.7% → 37.4%**. The authors argue "text prompts are lossy compression of the physical world, omitting the parameters that fully determine dynamics" — [arXiv 2605.18396](https://arxiv.org/abs/2605.18396)
- **VisPhyWorld / VisPhyBench** (arXiv 2602.13294):
  - MLLMs must **write executable simulator code** reproducing observed physics videos (209 scenes, 108 templates).
  - The pipeline produced valid videos in 97.7% of runs, **but** models "struggle to accurately infer physical parameters and to simulate consistent physical dynamics".
  - Recognition-style benchmarks (VQA) mask these deficits.
  - [arXiv 2602.13294](https://arxiv.org/abs/2602.13294)
- **PhysGen** (arXiv 2409.18964, ECCV 2024) turns an image into video using **rigid-body simulation in image space**, then diffusion-based rendering. Model-based simulation and learned rendering are combined for physical plausibility — [arXiv 2409.18964](https://arxiv.org/abs/2409.18964)
- Related 2025–26 works found but only seen as titles or snippets:
  - PhysGym, interactive physics discovery ([arXiv 2507.15550](https://arxiv.org/abs/2507.15550))
  - PhysCodeBench, physics-aware symbolic 3D simulation with self-corrective multi-agent refinement ([arXiv 2604.23580](https://arxiv.org/pdf/2604.23580))
  - PhysAgent, trajectory-grounded multi-agent feedback for 4D synthesis ([pith 2606.08688](https://pith.science/paper/2606.08688))
  - PhyWorldBench ([arXiv 2507.13428](https://arxiv.org/pdf/2507.13428))

### Inferences
- The evidence favors keeping **motion determined by a solver** (ODE integration or closed form) and never by LLM-written easing curves. It also suggests a **trajectory-grounded check** for any LLM-written motion code: sample mobject positions per frame and compare them against the solver (energy, period, range). This mirrors PhysAgent's trajectory descriptors and VisPhyWorld's falsifiable-code principle.
- PhyT2V's "caption the output, compare with intended physics rules" loop could be adapted cheaply. The vision critic would be given the **verifier's expected physical facts**, e.g. "the pendulum period should be 2.0 s; the ball should peak at t=1.2 s", and asked to check them against frames, instead of judging only aesthetics.
- NEWTON's point that prompts are lossy compressions of physics argues for passing **explicit numeric parameters** from the derivation and verifier into the storyboard and components, not prose.

### Gaps
- Exact per-model PhyGenBench scores and the PhyGenEval–human correlation were not in the abstract, so they are not reported.
- No study was found that evaluates physical correctness specifically for **code-rendered educational animations** (Manim), as opposed to generative video. This looks like an open research gap AetherLab's verifier could fill.
