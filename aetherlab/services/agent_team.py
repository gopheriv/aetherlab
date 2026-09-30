"""An M3 agent team that authors a scene: a main agent delegating to specialists.

    main agent ──▶ Researcher   physics, numbers, misconceptions, topic-specific visual ideas
               ──▶ Coder        knows only the Manim knowledge base (codegen rules, learned
                                pitfalls, render-proven exemplars, the typeset-math kit)
               ──▶ Reviewer     static gates + a fast local render, then looks at the frames
                                for physics and layout mistakes and says how to fix them

The main agent is the same model with four tools (ask_researcher, ask_coder,
ask_reviewer, finish); each specialist is a fresh call with its own context.
The team only replaces the *authoring* step: the code it returns goes through
the same gates, repairs and render as the single-agent pipeline, so the two can
be compared fairly. Experimental: it is opt-in (see .analysis/team_experiment.py)
and every step is logged in ``team_log`` so the difference can be watched.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from aetherlab.services.scene_generator import SceneGenerator

log = logging.getLogger(__name__)

MAX_TURNS = 12
MAX_CODER_CALLS = 3
MAX_REVIEWS = 3
PREVIEW_TIMEOUT_S = 420

MAIN_PROMPT = """You lead a small team that makes one physics animation (Manim) for a student.
Your team: a Researcher (physics facts, numbers, misconceptions, visual ideas), a Coder
(writes the Manim scene; knows Manim, not physics) and a Reviewer (checks the code, renders a
preview and looks at the frames for mistakes). You never write code yourself.

What the owner values most:
- Creativity: a visual device invented for THIS topic (a race, two clocks, a shadow, a
  before/after, a build-up...), never a generic "title, axes, one curve" template.
- Full working: the real equations with the numbers substituted and units, step by step,
  and the answer stated clearly. Do not drop details to save time.
- Correctness: every number on screen must match the physics.

Process: ask the Researcher first (you may ask one sharper follow-up). Then give the Coder a
concrete creative direction: the device, the beats in order, the equations and numbers to show,
and the ending. Then ask the Reviewer. If the Reviewer finds real problems, send the Coder a
revision with the exact fixes, then review again. Call finish when the Reviewer approves or
the budget is spent. Call exactly one tool per turn."""

RESEARCHER_PROMPT = """You are the Researcher on a physics animation team. Answer the lead's
question for the request below, concisely (under 450 words), as plain text with headings:
1. Core physics (laws and why they apply), 2. Equations, with the given numbers substituted and
the results computed to 3 significant figures, with units, 3. The answer, 4. Common
misconceptions, 5. Three creative visual devices specific to this topic (how the animation
could SHOW the idea, not just state it), 6. Numbers or claims the animation must not get wrong.
Compute carefully; the Coder will put your numbers on screen."""

CODER_PROMPT = """You are the Coder on a physics animation team. You know Manim Community
v0.21 and nothing else: take the physics and numbers from the brief exactly as given.
Write ONE complete scene class named {class_name}(Scene) with def construct(self).

Rules (the render pipeline rejects code that breaks them):
- Output ONLY Python code. `from manim import *`; `import numpy as np` / `import math` if used.
  Start the file with a 2-3 line module docstring describing the visual concept.
- No getattr/setattr/hasattr/eval/exec, dunder attributes, reflection, file access or other imports.
- At most 16 top-level self.play(...) calls in the whole scene (combine with AnimationGroup /
  LaggedStart; use self.wait for reading time) and at most 3 live updaters / always_redraw.
  Never write self.play inside a loop. Never rebuild a curve (axes.plot, ParametricFunction)
  inside always_redraw.
- Total length within 20% of the target duration: give every equation a readable hold.
- Keep everything inside the frame (14.2 x 8 units, 0.45 margin). Long text: split into lines
  or fit: `if m.width > 13: m.scale_to_fit_width(13)`. Cloud fonts run wider than local ones.
- Equations: use the eq() helper below (typeset MathTex, plain Text if LaTeX is missing).
  Plain Text may only use these non-ASCII glyphs: ° ² · ½ × ħ Δ Σ γ θ λ π ψ ω ₁ ₂ → ∂ √ ∝ ≈ ö.
- Clear finished groups (FadeOut) before unrelated content; never stack text on text.
- End on a clear answer card and keep something gently moving in the final seconds.

Helper you may paste and use:
def eq(tex, plain, size=34, color=WHITE, width=13.0):
    try:
        m = MathTex(tex, font_size=size, color=color)
    except Exception:
        m = Text(plain, font_size=int(size * 0.72), color=color)
    if m.width > width:
        m.scale_to_fit_width(width)
    return m
"""

REVIEWER_PROMPT = """You are the Reviewer on a physics animation team. You see an automatic
check report and one image: a 3x2 grid of frames from a fast preview render of the scene, in
time order. Check against the research brief: wrong physics or numbers, missing working steps,
text clipped at frame edges or too small to read, overlapping elements, empty or confusing
frames, and whether the visual idea actually shows the physics. Be concrete and constructive.
Reply with ONLY JSON:
{"verdict": "approve" | "revise",
 "issues": [{"severity": "major" | "minor", "problem": "...", "fix": "exact change for the Coder"}],
 "strengths": ["..."]}
Approve when there are no major issues."""

TOOLS = [
    {"type": "function", "function": {
        "name": "ask_researcher",
        "description": "Ask the Researcher a physics question about the request (facts, numbers, misconceptions, visual ideas).",
        "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
    {"type": "function", "function": {
        "name": "ask_coder",
        "description": "Ask the Coder to write the scene, or to revise the latest scene. Give the creative direction "
                       "(device, beats, equations and numbers to show, ending) or the exact fixes.",
        "parameters": {"type": "object", "properties": {"direction": {"type": "string"}}, "required": ["direction"]}}},
    {"type": "function", "function": {
        "name": "ask_reviewer",
        "description": "Ask the Reviewer to check the latest scene (automatic gates, a preview render and a look at the frames).",
        "parameters": {"type": "object", "properties": {"focus": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Finish: the latest scene is the team's answer.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": []}}},
]


def _strip_think(text: str) -> str:
    import re

    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


class AgentTeamGenerator(SceneGenerator):
    """SceneGenerator whose authoring step is done by an M3 agent team."""

    def __init__(self, settings: Any, *, minimax_thinking: bool | None = None) -> None:
        super().__init__(settings, minimax_thinking=minimax_thinking)
        self.team_log: list[dict[str, Any]] = []
        self.team_stats: dict[str, Any] = {}

    # ── plumbing ──────────────────────────────────────────────────────────

    def _note(self, role: str, started: float, summary: str, **extra: Any) -> None:
        self.team_log.append({"role": role, "seconds": round(time.monotonic() - started, 1),
                              "summary": summary[:1500], **extra})
        log.info("team %s (%.0fs): %s", role, time.monotonic() - started, summary[:160])

    async def _call(self, messages: list[dict], *, temperature: float, max_tokens: int,
                    tools: list | None = None, thinking: bool | None = None) -> Any:
        from aetherlab.services.model_policy import codegen_request_kwargs, request_temperature

        client = self._ensure_client()
        kwargs: dict[str, Any] = dict(model=self.settings.llm_model, messages=messages, max_tokens=max_tokens,
                                      temperature=request_temperature(self.settings, temperature),
                                      **codegen_request_kwargs(self.settings, minimax_thinking=thinking))
        if tools:
            kwargs["tools"] = tools
        # dropped connections are retried inside the shared client, exactly as for the
        # single-agent pipeline, so the comparison is fair
        return await client.chat.completions.create(**kwargs)

    # ── the specialists ───────────────────────────────────────────────────

    def _context(self, request: Any, solver: Any, rag: Any) -> str:
        vars_text = ", ".join(f"{k} = {v:g}" for k, v in sorted((solver.variables or {}).items())) or "(none)"
        steps = "\n".join(f"  {i}. {s}" for i, s in enumerate((solver.derivation_steps or [])[:8], 1))
        refs = "\n".join(f"- {h.source_name}: {' '.join(str(h.excerpt).split())[:350]}" for h in (rag.hits or [])[:4])
        return (f"Request: {request.prompt}\nTarget length: {float(request.duration_target_s):g} s\n"
                f"Solver summary: {solver.summary}\nGiven values: {vars_text}\n"
                f"Solver steps:\n{steps or '  (none)'}\nReferences:\n{refs or '- (none)'}")

    async def _research(self, question: str, context: str) -> str:
        t0 = time.monotonic()
        r = await self._call([{"role": "system", "content": RESEARCHER_PROMPT},
                              {"role": "user", "content": f"{context}\n\nLead's question: {question}"}],
                             temperature=0.4, max_tokens=12000)
        text = _strip_think(r.choices[0].message.content or "") or "(no answer)"
        self.research.append(text)
        self._note("researcher", t0, text, question=question[:400])
        return text

    async def _code(self, direction: str, context: str, class_name: str) -> str:
        from aetherlab.services.error_learner import preventive_pitfalls_block
        from aetherlab.services.scene_exemplars import exemplar_block

        t0 = time.monotonic()
        system = CODER_PROMPT.replace("{class_name}", class_name)
        knowledge = preventive_pitfalls_block(None)
        exemplar = exemplar_block(self._solver.keywords, self._solver.variables, data_dir=self.settings.data_dir)
        if exemplar:
            knowledge += "\n\n" + exemplar
        user = f"{context}\n\n## Research brief\n" + "\n\n".join(self.research[-2:]) + f"\n\n## Lead's direction\n{direction}"
        if self.code:
            user += (f"\n\n## Your previous scene (revise it; keep what works)\n{self.code}"
                     f"\n\n## Latest review\n{self.last_review or '(none)'}")
        user += "\n\nOutput ONLY the complete Python file."
        r = await self._call([{"role": "system", "content": system}, {"role": "system", "content": knowledge},
                              {"role": "user", "content": user}],
                             temperature=0.4, max_tokens=32768, thinking=self._minimax_thinking)
        code = self._extract_code(r.choices[0].message.content or "", class_name)
        self.code = code
        self.versions.append(code)
        gates = self._gates(code)
        doc = code.split('"""')[1].strip() if code.count('"""') >= 2 else ""
        summary = f"scene v{len(self.versions)}: {len(code.splitlines())} lines. Concept: {doc[:300]}\nGates: {gates['text']}"
        self._note("coder", t0, summary, version=len(self.versions), gates_ok=gates["ok"])
        return summary

    def _gates(self, code: str) -> dict[str, Any]:
        from aetherlab.services.code_safety import validate_code_safety
        from aetherlab.services.manim_runtime import _estimate_render_cost
        from aetherlab.services.scene_validation import (
            count_construct_play_calls,
            estimate_duration,
            scene_hygiene_warnings,
            validate_scene,
        )

        problems: list[str] = []
        try:
            compile(code, "<team-scene>", "exec")
        except SyntaxError as exc:
            return {"ok": False, "renderable": False, "text": f"does not compile: {exc}", "problems": [str(exc)]}
        safe, safety = validate_code_safety(code)
        problems += safety if not safe else []
        ok, issues = validate_scene(code, require_motion=True)
        problems += issues if not ok else []
        problems += [w for w in scene_hygiene_warnings(code) if w.startswith("[HYGIENE:OVERLAP]")]
        target = float(self._request.duration_target_s)
        est = estimate_duration(code).total_seconds
        if not 0.8 * target <= est <= 1.2 * target:
            problems.append(f"[TIMING] estimated {est:.1f}s, target {target:g}s (±20%)")
        plays = count_construct_play_calls(code)
        if target >= 24 and plays > 16:
            problems.append(f"[BUDGET] {plays} top-level self.play calls (max 16)")
        cost = _estimate_render_cost(code)
        if cost > 3.5:
            problems.append(f"[BUDGET] render cost estimate {cost:.1f} (max 3.5)")
        text = "all automatic checks pass" if not problems else "; ".join(problems[:8])
        # only code that compiles and passes the safety gate is ever rendered locally
        return {"ok": not problems, "renderable": safe, "problems": problems,
                "text": f"{text} (estimated {est:.0f}s, {plays} play calls)"}

    def _preview(self, code: str, class_name: str) -> tuple[bytes | None, str]:
        """Fast low-quality local render; returns a 3x2 frame grid (PNG) or the error tail."""
        with tempfile.TemporaryDirectory(prefix="aetherlab_team_") as tmp:
            src = Path(tmp) / "scene.py"
            src.write_text(code, encoding="utf-8")
            try:
                r = subprocess.run([sys.executable, "-m", "manim", "render", "-ql", "--media_dir", tmp,
                                    "--disable_caching", str(src), class_name],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=PREVIEW_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                return None, f"preview render timed out after {PREVIEW_TIMEOUT_S}s"
            videos = list(Path(tmp).rglob(f"{class_name}.mp4"))
            if r.returncode != 0 or not videos:
                tail = (r.stderr or r.stdout or "")[-1800:]
                return None, f"preview render FAILED:\n{tail}"
            try:
                import av
                from PIL import Image

                with av.open(str(videos[0])) as c:
                    st = c.streams.video[0]
                    dur = float(st.duration * st.time_base)
                    want = [dur * k / 6 + 0.5 for k in range(5)] + [dur - 0.2]
                    shots, k = [], 0
                    for fr in c.decode(st):
                        t = float(fr.pts * st.time_base)
                        if k < len(want) and t >= want[k]:
                            shots.append(fr.to_image().resize((480, 270)))
                            k += 1
                sheet = Image.new("RGB", (1440, 540), "black")
                for i, im in enumerate(shots[:6]):
                    sheet.paste(im, ((i % 3) * 480, (i // 3) * 270))
                buf = io.BytesIO()
                sheet.save(buf, format="PNG")
                return buf.getvalue(), f"preview rendered ({dur:.0f}s)"
            except Exception as exc:  # noqa: BLE001
                return None, f"preview rendered but frames could not be read ({exc})"

    async def _review(self, focus: str, class_name: str) -> str:
        t0 = time.monotonic()
        if not self.code:
            return "There is no scene yet: ask the Coder first."
        gates = self._gates(self.code)
        report = f"Automatic checks: {gates['text']}"
        image, preview = (None, "preview skipped: the code does not compile or fails the safety gate")
        if gates["renderable"]:
            image, preview = await asyncio.to_thread(self._preview, self.code, class_name)
        report += f"\nPreview: {preview}"
        content: list[dict[str, Any]] = [{"type": "text", "text": (
            f"Research brief:\n{self.research[-1] if self.research else '(none)'}\n\n{report}\n\n"
            f"Lead's focus: {focus or 'general review'}\n\nScene code:\n{self.code}")}]
        if image:
            content.append({"type": "image_url",
                            "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode("ascii")}})
        verdict = "revise"
        try:
            r = await self._call([{"role": "system", "content": REVIEWER_PROMPT}, {"role": "user", "content": content}],
                                 temperature=0.2, max_tokens=8000)
            from aetherlab.services.model_json import load_model_json

            raw = _strip_think(r.choices[0].message.content or "")
            try:
                parsed = load_model_json(raw)
                verdict = str(parsed.get("verdict", "revise")).lower()
                issues = parsed.get("issues") or []
                review = f"Verdict: {verdict}\n" + "\n".join(
                    f"- [{i.get('severity', '?')}] {i.get('problem', '')} -> fix: {i.get('fix', '')}"
                    for i in issues if isinstance(i, dict))
                if parsed.get("strengths"):
                    review += "\nStrengths: " + "; ".join(map(str, parsed["strengths"]))[:500]
            except Exception:  # noqa: BLE001 - keep the prose review
                review = raw[:3000]
        except Exception as exc:  # noqa: BLE001 - the automatic report still helps
            review = f"(visual review unavailable: {type(exc).__name__})"
        if not gates["ok"]:
            verdict = "revise"
        full = f"{report}\n{review}"
        self.last_review = full
        self.reviews.append({"verdict": verdict, "gates_ok": gates["ok"], "had_frames": image is not None})
        self._note("reviewer", t0, full, verdict=verdict, gates_ok=gates["ok"], had_frames=image is not None)
        return full

    # ── the main agent ────────────────────────────────────────────────────

    async def generate(self, request: Any, solver: Any, rag: Any, class_name: str = "AetherLabScene") -> str:
        from aetherlab.services.parameters import apply_request_parameters

        solver = apply_request_parameters(request, solver)
        self._request, self._solver = request, solver
        self._last_fallback_reason = ""
        self._last_storyboard = None
        self._last_scene_spec = None
        self.team_log, self.research, self.versions, self.reviews = [], [], [], []
        self.code, self.last_review = "", ""
        if not self.settings.openai_api_key:
            return await super().generate(request, solver, rag, class_name)
        started = time.monotonic()
        try:
            await self._run(request, solver, rag, class_name)
        except Exception as exc:  # noqa: BLE001 - recorded; the pipeline falls back below
            self._note("main", started, f"team failed: {type(exc).__name__}: {exc}")
        self.team_stats = {
            "seconds": round(time.monotonic() - started, 1), "research_calls": len(self.research),
            "code_versions": len(self.versions), "reviews": len(self.reviews),
            "approved": bool(self.reviews and self.reviews[-1]["verdict"] == "approve"),
        }
        if not self.code:
            self._note("main", started, "no scene from the team; using the single-agent pipeline")
            self.team_stats["fell_back"] = True
            return await super().generate(request, solver, rag, class_name)
        best = next((c for c in reversed(self.versions) if self._gates(c)["ok"]), self.code)
        return best

    async def _run(self, request: Any, solver: Any, rag: Any, class_name: str) -> None:
        context = self._context(request, solver, rag)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": context + "\n\nLead the team to make this animation."},
        ]
        nudges = 0
        for _ in range(MAX_TURNS):
            t0 = time.monotonic()
            r = await self._call(messages, temperature=0.3, max_tokens=6000, tools=TOOLS)
            msg = r.choices[0].message
            calls = msg.tool_calls or []
            if not calls:
                self._note("main", t0, "answered without a tool call: " + _strip_think(msg.content or "")[:300])
                nudges += 1
                if nudges > 2:
                    return
                messages += [{"role": "assistant", "content": msg.content or ""},
                             {"role": "user", "content": "Call exactly one tool now."}]
                continue
            call = calls[0]
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except ValueError:
                args = {}
            self._note("main", t0, f"-> {name}: " + json.dumps(args, ensure_ascii=False)[:600])
            assistant = msg.model_dump(exclude_none=True)
            assistant["tool_calls"] = [c for c in assistant.get("tool_calls", [])[:1]]
            messages.append(assistant)
            if name == "finish":
                if self.code:
                    return
                result = "There is no scene yet: ask the Coder first."
            elif name == "ask_researcher":
                result = (await self._research(str(args.get("question") or request.prompt), context)
                          if len(self.research) < 3 else "Research budget used; direct the Coder.")
            elif name == "ask_coder":
                if len(self.versions) >= MAX_CODER_CALLS:
                    result = "Coder budget used; call ask_reviewer or finish."
                else:
                    if not self.research:
                        await self._research(request.prompt, context)
                    try:
                        result = await self._code(str(args.get("direction") or "Make the scene."), context, class_name)
                    except Exception as exc:  # noqa: BLE001 - the lead decides what to do next
                        result = f"The Coder's reply was unusable ({type(exc).__name__}: {str(exc)[:200]}). Ask again."
                        self._note("coder", time.monotonic(), result)
            elif name == "ask_reviewer":
                result = (await self._review(str(args.get("focus") or ""), class_name)
                          if len(self.reviews) < MAX_REVIEWS else "Review budget used; call finish.")
            else:
                result = f"Unknown tool {name}."
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result[:6000]})
