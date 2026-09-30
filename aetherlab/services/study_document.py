"""Well-explained LaTeX study documents: a topic guide or a worked problem solution.

``write_study_document(request, solver, rag, settings, out_dir)`` produces a
typeset PDF in one of two modes, chosen from the prompt:

* topic: overview, core theory with step-by-step derivations, boxed key
  results, a worked example, common mistakes, summary and references;
* problem: the problem restated, Given / Find, the theory it rests on, a
  solution plan, numbered solution steps (each explained in words, then the
  math), a boxed final answer, checks (units, limits, and an independent
  numerical simulation where AetherLab has one), common mistakes, summary and
  references.

The model writes structured JSON; this module does the typesetting. Prose is
escaped, and math travels in dedicated fields, so model LaTeX can only break
a single equation, never the document. The compile heals itself: when
pdflatex reports an error, the offending block is replaced by a safe rendering
and the document recompiles. A document is always produced: without a model
(or when authoring fails), a deterministic document is built from the
solver's own derivation, and a matplotlib PDF is the last resort.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

_MAX_COMPILE_ATTEMPTS = 12

# ── result ─────────────────────────────────────────────────────────────────


@dataclass
class StudyDocResult:
    mode: str                       # "topic" | "problem"
    tex_path: Path
    pdf_path: Path | None
    backend: str                    # "pdflatex" | "matplotlib" | "tex-only"
    authored_by: str                # model name, or "deterministic"
    repaired_blocks: int = 0        # equations replaced by a safe rendering
    checks: list[str] = field(default_factory=list)
    note: str = ""


# ── mode ───────────────────────────────────────────────────────────────────

_QUESTION_RE = re.compile(
    r"\?|\b(find|calculate|compute|determine|how (far|long|fast|high|much|many)|what is the|"
    r"solve|show that|prove|estimate)\b", re.I)


def classify(prompt: str) -> str:
    """"problem" for a concrete question with numbers or an explicit task, else "topic"."""
    text = prompt or ""
    has_number = bool(re.search(r"\d", text))
    asks = bool(_QUESTION_RE.search(text))
    if asks and (has_number or re.search(r"\b(show that|prove|derive an expression)\b", text, re.I)):
        return "problem"
    return "topic"


# ── authoring ──────────────────────────────────────────────────────────────

_RULES = """Formatting rules (strict):
- Return ONLY one JSON object. No markdown fences, no commentary.
- Prose fields are plain text. Put inline math between single dollar signs, e.g. "the period $T = 2\\pi\\sqrt{L/g}$".
- EVERY symbol in prose goes inside $...$, even a single variable: write "$v_{0x}$", "$a_y$", "$R_{\\max}$",
  never "v0x", "a_y" or "R_max" as plain text. Never use unicode symbols (use $\\checkmark$, $\\theta$, $\\le$).
- Every list (summary, checks, common_mistakes, plan, find) is a JSON array with ONE item per string.
- Headings and step titles are short phrases with NO leading number ("Resolve the velocity", not "1. Resolve...").
- Every field named "latex" is the BODY of a display equation: no surrounding $ or \\[ \\].
  Use amsmath/amssymb only. For multi-line derivations use \\begin{aligned} ... \\end{aligned} with & and \\\\.
- Write units in math as \\,\\mathrm{m/s}, \\,\\mathrm{kg}, etc.
- Do not use \\label, \\ref, \\cite, \\eqref, custom macros, tables or figures.
- Keep numbers to 3 significant figures and show substitutions explicitly.
- Write in clear English for a university student. Explain WHY each step is taken, not only what."""

_TOPIC_PROMPT = """You are AetherLab's physics author. Write a well-explained study guide on the topic below.
It should read like an excellent textbook section: build intuition first, then derive the key results step by step.

JSON shape:
{
  "title": "...",
  "abstract": "3-4 sentences: what this is, why it matters, what the reader will be able to do.",
  "sections": [
    {"heading": "...", "paragraphs": ["..."], "equations": [{"latex": "...", "note": "what this equation says, in words"}]}
  ],
  "key_results": [{"latex": "...", "meaning": "..."}],
  "worked_example": {"statement": "...", "steps": [{"explanation": "...", "latex": "..."}], "answer": "..."},
  "common_mistakes": ["..."],
  "summary": ["..."]
}
Use 4 to 6 sections: intuition and physical picture, the governing law(s), a full derivation with every algebra step,
consequences and limiting cases, and applications. 2 to 5 key results. 4 to 7 worked-example steps.
""" + _RULES

_PROBLEM_PROMPT = """You are AetherLab's physics tutor. Solve the problem below completely and explain it so a student
could solve the next one alone. First teach the theory the problem needs, then solve it step by step.

JSON shape:
{
  "title": "short descriptive title",
  "restatement": "the problem in your own words",
  "given": [{"symbol": "LaTeX symbol, e.g. v_0", "value": "LaTeX value with unit, e.g. 18\\\\,\\\\mathrm{m/s}", "meaning": "..."}],
  "find": ["..."],
  "theory": [{"heading": "...", "paragraphs": ["..."], "equations": [{"latex": "...", "note": "..."}]}],
  "plan": ["short step of the solution strategy"],
  "steps": [{"title": "...", "explanation": "why and what, in words", "latex": "the math of this step"}],
  "final_answer": {"statement": "the answer in words with units", "latex": "the key result, e.g. R = 32.5\\\\,\\\\mathrm{m}"},
  "checks": ["unit check / limiting case / order-of-magnitude check"],
  "common_mistakes": ["..."],
  "summary": ["..."]
}
2 to 4 theory sections. 5 to 10 solution steps: derive the formula symbolically first, then substitute numbers.
""" + _RULES


def _context(request: Any, solver: Any, rag: Any) -> str:
    lines = [f"Request: {request.normalized_prompt()}"]
    summary = (getattr(solver, "summary", "") or "").strip()
    if summary and getattr(solver, "model_name", "") != "deterministic-fallback":
        lines.append(f"Solver summary: {summary}")
        steps = getattr(solver, "derivation_steps", []) or []
        if steps:
            lines.append("Solver derivation (keep consistent with it):")
            lines += [f"  {i}. {s}" for i, s in enumerate(steps[:10], 1)]
        eqs = getattr(solver, "key_equations", []) or []
        if eqs:
            lines.append("Key equations: " + " ; ".join(eqs[:4]))
        variables = getattr(solver, "variables", {}) or {}
        if variables:
            lines.append("Values: " + ", ".join(f"{k} = {v:g}" for k, v in list(variables.items())[:10]))
    hits = list(getattr(rag, "hits", []) or [])[:3]
    for hit in hits:
        excerpt = " ".join(str(getattr(hit, "excerpt", "")).split())[:500]
        if excerpt:
            lines.append(f"Reference ({getattr(hit, 'source_name', 'source')}): {excerpt}")
    return "\n".join(lines)


_N_COMMANDS = r"(?:abla|eq|eg|e|u|ewline|ot|onumber|oindent|i|mid|leq|geq|parallel|exists|atural|earrow|warrow)(?![A-Za-z])"


def _parse_json(text: str) -> dict[str, Any] | None:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    blob = text[start:end + 1]
    # Models often write LaTeX in JSON with single backslashes. JSON would
    # silently read "\frac" as a form feed + "rac" and "\theta" as a tab +
    # "heta", so a backslash followed by two or more letters is LaTeX: double
    # it ("\uXXXX" is kept). A newline escape can also precede letters, as in
    # "first item.\nSecond item", so "\n" + letters is LaTeX only when it
    # starts a real \n... command (\nabla, \nu, \neq...).
    latex_safe = re.sub(r"(?<!\\)\\(?!u[0-9a-fA-F]{4})(?!n(?!" + _N_COMMANDS + r"))(?=[A-Za-z]{2,})",
                        r"\\\\", blob)
    for candidate in (latex_safe, re.sub(r"(?<!\\)\\(?![\\\"/bfnrtu])", r"\\\\", latex_safe)):
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except ValueError:
            continue
    return None


def _valid(doc: dict[str, Any] | None, mode: str) -> bool:
    if not isinstance(doc, dict) or not doc.get("title"):
        return False
    if mode == "problem":
        return bool(doc.get("steps")) and isinstance(doc.get("final_answer"), dict)
    return bool(doc.get("sections"))


_CONNECTION_RETRIES = 2


def _is_connection_drop(exc: BaseException) -> bool:
    names = {cls.__name__ for cls in type(exc).__mro__}
    return "APIConnectionError" in names and "APITimeoutError" not in names


async def author_document(request: Any, solver: Any, rag: Any, settings: Any, mode: str,
                          progress: Callable[[str], None] | None = None) -> tuple[dict[str, Any] | None, str]:
    """Ask the configured model for the document content. Returns (content, model) or (None, reason)."""
    if not getattr(settings, "openai_api_key", None):
        return None, "no model configured"
    from aetherlab.services.llm_client import make_client
    from aetherlab.services.model_policy import codegen_request_kwargs, request_temperature

    client = make_client(settings)
    system = _PROBLEM_PROMPT if mode == "problem" else _TOPIC_PROMPT
    user = _context(request, solver, rag)
    last = "no reply"
    # First with the model's own reasoning; if that exhausts the budget or
    # returns unusable JSON, retry once with thinking off (MiniMax spends its
    # whole budget thinking on long outputs).
    for attempt, thinking in enumerate((None, False), start=1):
        if progress:
            progress(f"Writing the {mode} document (attempt {attempt})…")
        response = None
        for drop in range(_CONNECTION_RETRIES + 1):
            try:
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    temperature=request_temperature(settings, 0.3),
                    max_tokens=32768,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    **codegen_request_kwargs(settings, minimax_thinking=thinking),
                )
                break
            except Exception as exc:  # noqa: BLE001 — fall back to the deterministic document
                last = f"{type(exc).__name__}: {exc}"
                # A dropped connection fails fast and is worth another try; a
                # timeout already spent the whole budget, so it is not retried.
                if not _is_connection_drop(exc) or drop == _CONNECTION_RETRIES:
                    break
                if progress:
                    progress(f"Connection dropped; retrying (attempt {attempt})…")
                await asyncio.sleep(5 * (drop + 1))
        if response is None:
            continue
        doc = _parse_json(response.choices[0].message.content or "")
        if _valid(doc, mode):
            return doc, str(getattr(client, "last_served_by", None) or settings.llm_model)
        last = f"unusable reply (finish_reason={getattr(response.choices[0], 'finish_reason', None)})"
    return None, last


def deterministic_document(request: Any, solver: Any, mode: str) -> dict[str, Any]:
    """A document built from the solver alone (no model, or authoring failed)."""
    prompt = request.normalized_prompt()
    title = prompt if len(prompt) <= 80 else prompt[:79].rstrip() + "…"
    summary = (getattr(solver, "summary", "") or "").strip()
    steps = [str(s) for s in getattr(solver, "derivation_steps", []) or []]
    eqs = [{"latex": e, "note": ""} for e in (getattr(solver, "key_equations", []) or [])[:4]]
    variables = getattr(solver, "variables", {}) or {}
    offline = getattr(solver, "model_name", "") == "deterministic-fallback"
    intro = ("Generated offline from AetherLab's deterministic solver: the derivation below is a "
             "generic scaffold, not a solution of this specific request." if offline else summary)
    if mode == "problem":
        return {
            "title": title, "restatement": prompt,
            "given": [{"symbol": k, "value": f"{v:g}", "meaning": ""} for k, v in variables.items()],
            "find": [prompt],
            "theory": [{"heading": "Governing relations", "paragraphs": [intro], "equations": eqs}],
            "plan": [],
            "steps": [{"title": f"Step {i}", "explanation": s, "latex": ""} for i, s in enumerate(steps, 1)],
            "final_answer": {"statement": summary or "See the steps above.", "latex": ""},
            "checks": [], "common_mistakes": [], "summary": [],
        }
    return {
        "title": title, "abstract": intro,
        "sections": [{"heading": "Derivation", "paragraphs": steps or [intro], "equations": eqs}],
        "key_results": [{"latex": e["latex"], "meaning": ""} for e in eqs[:2]],
        "worked_example": {}, "common_mistakes": [], "summary": [],
    }


# ── LaTeX assembly ─────────────────────────────────────────────────────────

_TEXT_MAP = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "$": r"\$", "<": r"\textless{}", ">": r"\textgreater{}",
}
# Unicode that pdflatex (T1 + Latin Modern) cannot set in text: map to math.
_UNICODE_MATH = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\varepsilon", "ζ": r"\zeta",
    "η": r"\eta", "θ": r"\theta", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu", "ν": r"\nu",
    "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau", "φ": r"\varphi",
    "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega", "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta",
    "Λ": r"\Lambda", "Σ": r"\Sigma", "Φ": r"\Phi", "Ψ": r"\Psi", "Ω": r"\Omega",
    "°": r"^\circ", "×": r"\times", "·": r"\cdot", "≈": r"\approx", "≤": r"\le", "≥": r"\ge",
    "≠": r"\neq", "±": r"\pm", "→": r"\to", "∞": r"\infty", "√": r"\surd", "∝": r"\propto",
    "∂": r"\partial", "∇": r"\nabla", "²": r"^2", "³": r"^3", "ħ": r"\hbar", "−": "-", "′": "'",
    "✓": r"\checkmark", "✔": r"\checkmark", "✗": r"\times", "✘": r"\times", "⇒": r"\Rightarrow",
    "⇔": r"\Leftrightarrow", "←": r"\leftarrow", "↔": r"\leftrightarrow", "≡": r"\equiv", "∼": r"\sim",
    "≪": r"\ll", "≫": r"\gg", "∫": r"\int", "∑": r"\sum", "∏": r"\prod", "∈": r"\in", "ℏ": r"\hbar",
    "⟨": r"\langle", "⟩": r"\rangle", "∆": r"\Delta", "µ": r"\mu", "½": r"\tfrac{1}{2}", "÷": r"\div",
    "⁰": "^0", "¹": "^1", "⁴": "^4", "⁵": "^5", "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9", "⁻": "^{-}",
    "₀": "_0", "₁": "_1", "₂": "_2", "₃": "_3", "₄": "_4", "ₓ": "_x",
}
_PLAIN = {"–": "--", "—": "---", "‘": "`", "’": "'", "“": "``", "”": "''", "…": r"\ldots{}", "\u00a0": "~"}


def _text(value: Any) -> str:
    """Escape prose for LaTeX; unicode symbols become inline math."""
    out = []
    for ch in str(value or ""):
        if ch in _TEXT_MAP:
            out.append(_TEXT_MAP[ch])
        elif ch in _UNICODE_MATH:
            out.append(f"${_UNICODE_MATH[ch]}$")
        elif ch in _PLAIN:
            out.append(_PLAIN[ch])
        elif ord(ch) < 128:
            out.append(ch)
        else:
            out.append("?")
    return "".join(out)


def _math(body: Any) -> str:
    """Clean a math body: strip stray delimiters and map unicode to commands."""
    s = str(body or "").strip()
    for a, b in (("\\[", "\\]"), ("$$", "$$"), ("\\(", "\\)"), ("$", "$")):
        if s.startswith(a) and s.endswith(b) and len(s) > len(a) + len(b):
            s = s[len(a):-len(b)].strip()
    s = re.sub(r"\\(label|tag)\{[^}]*\}", "", s)
    s = re.sub(r"\\-", "-", s)  # a text-mode discretionary hyphen overprints digits in math
    s = "".join(_UNICODE_MATH.get(ch, ch) if ord(ch) > 127 else ch for ch in s)
    return "".join(ch if ord(ch) < 128 else " " for ch in s)


# A bare identifier with a subscript or power in prose ("a_y", "R_max",
# "v_{0x}", "t^2") that the model forgot to put in $...$.
_SCRIPT = r"[_^](?:\{[^{}$]{1,12}\}|-?[A-Za-z0-9]{1,6})"
_BARE_SYMBOL_RE = re.compile(r"(?<![\w\\])([A-Za-z]{1,3})((?:" + _SCRIPT + r")+)(?![\w{])")


# Argument-less math symbols the model sometimes writes in prose without $...$
# ("consistent. \checkmark"): set them as math instead of printing the command.
_BARE_COMMANDS = sorted({c[1:] for c in _UNICODE_MATH.values() if re.fullmatch(r"\\[A-Za-z]+", c)}
                        | {"cdot", "ldots", "degree", "circ", "hbar", "infty"}, key=len, reverse=True)
_BARE_COMMAND_RE = re.compile(r"\\(" + "|".join(_BARE_COMMANDS) + r")(?![A-Za-z])")


def _bare_symbol(m: re.Match[str]) -> str:
    base = m.group(1)
    if base in ("sin", "cos", "tan", "log", "exp"):
        base = "\\" + base
    scripts = []
    for op, arg in re.findall(r"([_^])(\{[^{}$]*\}|-?[A-Za-z0-9]+)", m.group(2)):
        arg = arg[1:-1] if arg.startswith("{") else arg
        if op == "_" and len(arg) > 1 and arg.isalpha():
            arg = f"\\mathrm{{{arg}}}"
        scripts.append(f"{op}{{{arg}}}")
    return f"\x00{base}{''.join(scripts)}\x01"


def _prose(text: str) -> str:
    """Escape prose, turning bare subscripted/powered identifiers into math (URLs untouched)."""
    out = []
    for piece in re.split(r"(\S+://\S+|\S+\.(?:py|json|pdf|tex|csv)\b)", text):
        if "://" in piece or re.fullmatch(r"\S+\.(?:py|json|pdf|tex|csv)", piece):
            out.append(_text(piece))
            continue
        marked = _BARE_SYMBOL_RE.sub(_bare_symbol, piece)
        marked = _BARE_COMMAND_RE.sub(lambda m: "\x00" + ("^\\circ" if m.group(1) == "degree" else m.group(0)) + "\x01",
                                      marked)
        for chunk in re.split(r"(\x00[^\x01]*\x01)", marked):
            out.append(f"${chunk[1:-1]}$" if chunk.startswith("\x00") else _text(chunk))
    return "".join(out)


def _rich(value: Any) -> str:
    """Prose with $inline math$: escape the prose, keep the math."""
    parts = re.split(r"(?<!\\)\$(.+?)(?<!\\)\$", str(value or ""))
    out = []
    for i, part in enumerate(parts):
        out.append(f"${_math(part)}$" if i % 2 else _prose(part))
    return "".join(out)


def _items(values: Any) -> list[str]:
    """List items, one per bullet: a string packing several lines becomes several items."""
    if isinstance(values, str):
        values = [values]
    out = []
    for v in values or []:
        out += [line.strip(" •-\t") for line in str(v).splitlines() if line.strip(" •-\t")]
    return out


def _heading(value: Any) -> str:
    """Drop the model's own numbering ("1. ", "Step 2: ") — LaTeX numbers sections itself."""
    return re.sub(r"^\s*(?:step\s*)?\d+(?:\.\d+)*\s*[.):\-–]?\s+", "", str(value or ""), flags=re.I).strip()


def _safe_rich(value: Any) -> str:
    """Fallback for prose whose inline math failed: everything as escaped text."""
    return _text(str(value or "").replace("$", ""))


def _display(body: Any) -> str:
    m = _math(body)
    if not m:
        return ""
    # A bare "\\" line break is ignored inside \[ \] and the lines run together
    # into one overflowing row: give multi-line bodies an environment.
    if re.search(r"\\\\", m) and "\\begin{" not in m:
        m = m.rstrip().removesuffix("\\\\").rstrip()
        env = "aligned" if "&" in m else "gathered"
        m = f"\\begin{{{env}}}\n{m}\n\\end{{{env}}}"
    return f"\\[\n{m}\n\\]"


def _safe_display(body: Any) -> str:
    m = str(body or "").strip()
    return ("\\begin{center}\\small\\texttt{" + _text(m) + "}\\end{center}") if m else ""


@dataclass
class _Block:
    latex: str
    safe: str


class _Doc:
    """Ordered blocks, each with a safe fallback, so a failing one can be swapped."""

    def __init__(self) -> None:
        self.blocks: list[_Block] = []

    def raw(self, latex: str) -> None:
        self.blocks.append(_Block(latex, latex))

    def prose(self, text: Any, wrap: str = "{}\n") -> None:
        if str(text or "").strip():
            self.blocks.append(_Block(wrap.format(_rich(text)), wrap.format(_safe_rich(text))))

    def equation(self, body: Any) -> None:
        if str(body or "").strip():
            self.blocks.append(_Block(_display(body), _safe_display(body)))

    def render(self, use_safe: set[int]) -> tuple[str, list[tuple[int, int, int]]]:
        """Assemble the source and record each block's (first line, last line, index)."""
        lines: list[str] = []
        spans = []
        for i, block in enumerate(self.blocks):
            text = block.safe if i in use_safe else block.latex
            start = len(lines) + 1
            lines.extend(text.split("\n"))
            spans.append((start, len(lines), i))
        return "\n".join(lines), spans


_PREAMBLE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[margin=2.2cm,headheight=14pt]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{amsmath,amssymb,mathtools}
\usepackage{xcolor}
\usepackage[most]{tcolorbox}
\usepackage{enumitem}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage[colorlinks=true,linkcolor=aeblue,urlcolor=aeblue]{hyperref}
\definecolor{aeblue}{HTML}{1F4E79}
\definecolor{aeteal}{HTML}{0F766E}
\definecolor{aered}{HTML}{9F1239}
\definecolor{aegold}{HTML}{8A6D0B}
\titleformat{\section}{\Large\bfseries\color{aeblue}}{\thesection}{0.6em}{}
\titleformat{\subsection}{\large\bfseries\color{aeblue}}{\thesubsection}{0.5em}{}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.55em}
\setlist{itemsep=0.25em,topsep=0.3em}
\newtcolorbox{keybox}[1]{enhanced,breakable,colback=aeblue!4,colframe=aeblue!70,fonttitle=\bfseries,title={#1}}
\newtcolorbox{answerbox}{enhanced,colback=aeteal!6,colframe=aeteal!80!black,fonttitle=\bfseries,title={Final answer}}
\newtcolorbox{warnbox}{enhanced,breakable,colback=aered!4,colframe=aered!70,fonttitle=\bfseries,title={Common mistakes}}
\newtcolorbox{notebox}[1]{enhanced,breakable,colback=aegold!6,colframe=aegold!70,fonttitle=\bfseries,title={#1}}
\pagestyle{fancy}
\fancyhf{}
"""


def build_document(content: dict[str, Any], mode: str, request: Any, citations: list[str],
                   checks: list[str], figure_path: Path | None, authored_by: str) -> _Doc:
    d = _Doc()
    title = str(content.get("title") or request.normalized_prompt())
    kind = "Worked solution" if mode == "problem" else "Study guide"
    d.raw(_PREAMBLE)
    short = title if len(title) <= 55 else title[:54].rstrip() + "…"
    d.prose(short, "\\fancyhead[L]{{\\small\\color{{gray}}AetherLab \\textbullet{{}} " + kind + "}}\n"
            "\\fancyhead[R]{{\\small\\color{{gray}}{}}}\n\\fancyfoot[C]{{\\small\\thepage}}\n")
    d.raw("\\begin{document}")
    d.raw("\\begin{center}\n{\\small\\color{aeteal}\\textsc{AetherLab " + kind + "}}\\\\[0.3em]")
    d.prose(title, "{{\\LARGE\\bfseries\\color{{aeblue}} {}}}\\\\[0.4em]")
    d.raw("{\\small\\color{gray}" + date.today().strftime("%d %B %Y") + " \\textbullet{} written by "
          + _text(authored_by) + "}\n\\end{center}\n\\vspace{0.4em}")
    if mode == "problem":
        _problem_body(d, content, request)
    else:
        _topic_body(d, content)
    if figure_path is not None:
        path = str(figure_path).replace("\\", "/")
        d.raw("\\begin{figure}[h]\n\\centering\n\\includegraphics[width=0.78\\textwidth]{" + path + "}\n"
              "\\caption{Numerical solution computed by AetherLab (ground truth).}\n\\end{figure}")
    if checks:
        d.raw("\\begin{notebox}{Independent checks by AetherLab}\n\\begin{itemize}")
        for line in checks:
            d.prose(line, "\\item {}")
        d.raw("\\end{itemize}\n\\end{notebox}")
    summary = _items(content.get("summary"))
    if summary:
        d.raw("\\section*{Summary}\n\\begin{itemize}")
        for s in summary:
            d.prose(s, "\\item {}")
        d.raw("\\end{itemize}")
    d.raw("\\section*{References}")
    if citations:
        d.raw("\\begin{enumerate}")
        for c in citations:
            label, _, url = str(c).partition(": http")
            if url and re.fullmatch(r"s?://[^\s{}\\]+", url):
                d.blocks.append(_Block(f"\\item {_text(label)}: {{\\small\\url{{http{url}}}}}",
                                       f"\\item {_text(label)}"))
            else:
                d.prose(c, "\\item {}")
        d.raw("\\end{enumerate}")
    else:
        d.raw("No library references matched this request; the material is derived from first principles.")
    d.raw("\\end{document}")
    return d


def _sections(d: _Doc, sections: list[dict[str, Any]], numbered: bool = True) -> None:
    for sec in sections or []:
        if not isinstance(sec, dict):
            continue
        star = "" if numbered else "*"
        d.prose(_heading(sec.get("heading")), "\\section" + star + "{{{}}}")
        for para in sec.get("paragraphs", []) or []:
            d.prose(para, "{}\n")
        for eq in sec.get("equations", []) or []:
            if isinstance(eq, dict):
                d.equation(eq.get("latex"))
                d.prose(eq.get("note"), "{{\\small\\color{{gray}} {}}}\n")
            else:
                d.equation(eq)


def _topic_body(d: _Doc, c: dict[str, Any]) -> None:
    if c.get("abstract"):
        d.raw("\\begin{keybox}{Overview}")
        d.prose(c["abstract"])
        d.raw("\\end{keybox}")
    _sections(d, c.get("sections"))
    results = [r for r in c.get("key_results", []) or [] if isinstance(r, dict) and r.get("latex")]
    if results:
        d.raw("\\begin{keybox}{Key results}")
        for r in results:
            d.equation(r.get("latex"))
            d.prose(r.get("meaning"), "{{\\small {}}}\n")
        d.raw("\\end{keybox}")
    ex = c.get("worked_example") or {}
    if isinstance(ex, dict) and ex.get("steps"):
        d.raw("\\section{Worked example}")
        d.prose(ex.get("statement"), "\\textbf{{Problem.}} {}\n")
        d.raw("\\begin{enumerate}[label=\\textbf{\\arabic*.}]")
        for step in ex.get("steps") or []:
            if isinstance(step, dict):
                d.prose(step.get("explanation"), "\\item {}")
                d.equation(step.get("latex"))
        d.raw("\\end{enumerate}")
        d.prose(ex.get("answer"), "\\textbf{{Answer.}} {}\n")
    _mistakes(d, c)


def _problem_body(d: _Doc, c: dict[str, Any], request: Any) -> None:
    d.raw("\\begin{keybox}{Problem}")
    d.prose(request.normalized_prompt())
    d.raw("\\end{keybox}")
    d.prose(c.get("restatement"), "\\textit{{In other words:}} {}\n")
    given = [g for g in c.get("given", []) or [] if isinstance(g, dict)]
    if given:
        d.raw("\\section*{Given}\n\\begin{center}\n\\begin{tabular}{l l l}\n\\toprule\n"
              "\\textbf{Symbol} & \\textbf{Value} & \\textbf{Meaning}\\\\\n\\midrule")
        for g in given:
            sym, val = _math(g.get("symbol")), _math(g.get("value"))
            d.blocks.append(_Block(
                f"${sym}$ & ${val}$ & {_rich(g.get('meaning'))}\\\\",
                f"{_text(g.get('symbol'))} & {_text(g.get('value'))} & {_safe_rich(g.get('meaning'))}\\\\"))
        d.raw("\\bottomrule\n\\end{tabular}\n\\end{center}")
    find = _items(c.get("find"))
    if find:
        d.raw("\\section*{Find}\n\\begin{itemize}")
        for f in find:
            d.prose(f, "\\item {}")
        d.raw("\\end{itemize}")
    theory = c.get("theory") or []
    if theory:
        d.raw("\\section{Theory you need}")
        for sec in theory:
            if isinstance(sec, dict):
                d.prose(_heading(sec.get("heading")), "\\subsection{{{}}}")
                for para in sec.get("paragraphs", []) or []:
                    d.prose(para, "{}\n")
                for eq in sec.get("equations", []) or []:
                    if isinstance(eq, dict):
                        d.equation(eq.get("latex"))
                        d.prose(eq.get("note"), "{{\\small\\color{{gray}} {}}}\n")
    plan = _items(c.get("plan"))
    if plan:
        d.raw("\\section{Plan}\n\\begin{enumerate}")
        for p in plan:
            d.prose(p, "\\item {}")
        d.raw("\\end{enumerate}")
    d.raw("\\section{Solution}")
    for i, step in enumerate(c.get("steps") or [], 1):
        if not isinstance(step, dict):
            continue
        title = _heading(step.get("title"))
        if title:
            d.prose(title, "\\subsection*{{Step " + str(i) + ": {}}}")
        else:
            d.raw("\\subsection*{Step " + str(i) + "}")
        d.prose(step.get("explanation"), "{}\n")
        d.equation(step.get("latex"))
    answer = c.get("final_answer") or {}
    if isinstance(answer, dict) and (answer.get("statement") or answer.get("latex")):
        d.raw("\\begin{answerbox}")
        d.equation(answer.get("latex"))
        d.prose(answer.get("statement"), "{}\n")
        d.raw("\\end{answerbox}")
    checks = _items(c.get("checks"))
    if checks:
        d.raw("\\section*{Does the answer make sense?}\n\\begin{itemize}")
        for x in checks:
            d.prose(x, "\\item {}")
        d.raw("\\end{itemize}")
    _mistakes(d, c)


def _mistakes(d: _Doc, c: dict[str, Any]) -> None:
    mistakes = _items(c.get("common_mistakes"))
    if mistakes:
        d.raw("\\begin{warnbox}\n\\begin{itemize}")
        for m in mistakes:
            d.prose(m, "\\item {}")
        d.raw("\\end{itemize}\n\\end{warnbox}")


# ── compile ────────────────────────────────────────────────────────────────


def _run_pdflatex(tex_path: Path, cancel_check: Callable[[], bool] | None) -> tuple[bool, str]:
    from aetherlab.core.proc import run_process_tree, subprocess_kwargs

    pdf = tex_path.with_suffix(".pdf")
    pdf.unlink(missing_ok=True)
    try:
        result = run_process_tree(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
             "-output-directory", str(tex_path.parent), str(tex_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90, cancel_check=cancel_check, **subprocess_kwargs(),
        )
    except FileNotFoundError:
        return False, "pdflatex not installed"
    except Exception as exc:  # noqa: BLE001 — timeouts/cancellation surface as a failed compile
        if exc.__class__.__name__ == "ProcessCancelledError":
            raise
        return False, str(exc)
    log_path = tex_path.with_suffix(".log")
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else result.stdout
    return result.returncode == 0 and pdf.exists(), log_text


def _error_lines(log_text: str) -> list[int]:
    lines = []
    for m in re.finditer(r"^l\.(\d+)", log_text, re.M):
        lines.append(int(m.group(1)))
    return lines


def _compiles(doc: _Doc, tex_path: Path, use_safe: set[int],
              cancel_check: Callable[[], bool] | None) -> tuple[bool, str, list[tuple[int, int, int]]]:
    source, spans = doc.render(use_safe)
    tex_path.write_text(source, encoding="utf-8")
    ok, log_text = _run_pdflatex(tex_path, cancel_check)
    return ok, log_text, spans


def _bisect_culprit(doc: _Doc, tex_path: Path, use_safe: set[int],
                    cancel_check: Callable[[], bool] | None) -> int | None:
    """Find one failing block when the log's line number points elsewhere.

    pdflatex often reports an unbalanced brace lines after the real mistake.
    Making a growing prefix of the healable blocks safe and bisecting on "does
    it compile" finds the first culprit in about log2(n) compiles.
    """
    candidates = [i for i, b in enumerate(doc.blocks) if b.safe != b.latex and i not in use_safe]
    if not candidates or not _compiles(doc, tex_path, use_safe | set(candidates), cancel_check)[0]:
        return None
    lo, hi = 0, len(candidates)          # prefix lo fails, prefix hi compiles
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _compiles(doc, tex_path, use_safe | set(candidates[:mid]), cancel_check)[0]:
            hi = mid
        else:
            lo = mid
    return candidates[hi - 1]


def compile_healing(doc: _Doc, tex_path: Path,
                    cancel_check: Callable[[], bool] | None = None) -> tuple[Path | None, int, str]:
    """Compile; on error swap the failing block for its safe version and retry."""
    use_safe: set[int] = set()
    log_text = ""
    for _ in range(_MAX_COMPILE_ATTEMPTS):
        ok, log_text, spans = _compiles(doc, tex_path, use_safe, cancel_check)
        if ok:
            return tex_path.with_suffix(".pdf"), len(use_safe), ""
        if log_text == "pdflatex not installed":
            return None, len(use_safe), log_text
        bad = {i for line in _error_lines(log_text) for start, end, i in spans if start <= line <= end}
        bad = {i for i in bad - use_safe if doc.blocks[i].safe != doc.blocks[i].latex}
        if not bad:
            culprit = _bisect_culprit(doc, tex_path, use_safe, cancel_check)
            if culprit is None:
                break
            bad = {culprit}
        use_safe |= bad
    # Last resort: every block in its safe form.
    source, _ = doc.render(set(range(len(doc.blocks))))
    tex_path.write_text(source, encoding="utf-8")
    ok, log_text = _run_pdflatex(tex_path, cancel_check)
    if ok:
        return tex_path.with_suffix(".pdf"), len(doc.blocks), ""
    first_error = next((ln for ln in log_text.splitlines() if ln.startswith("!")), "unknown LaTeX error")
    return None, len(use_safe), first_error


# ── entry point ────────────────────────────────────────────────────────────


def independent_checks(request: Any, solver: Any) -> list[str]:
    """AetherLab's own verification lines: problem simulations and the numeric-model checks."""
    lines: list[str] = []
    try:
        from aetherlab.services.scene_components.problems import check_lines

        lines += check_lines(solver)
    except Exception:  # noqa: BLE001 — checks are advisory
        pass
    try:
        from aetherlab.services.verify import verify_solution

        # A problem simulation says more than the generic "finite / bounded"
        # sanity checks, so those only fill in when no simulation matched.
        if getattr(solver, "numeric_spec", None) and not lines:
            # Only checks that ran and passed belong in a study document; a
            # failed or unrunnable check ("initial values must be numbers") is
            # a tooling diagnostic, not a physics statement for the reader.
            lines += [f"{c.name}: {c.detail}" for c in verify_solution(solver, request).checks
                      if c.passed and str(c.detail).strip()]
    except Exception:  # noqa: BLE001
        pass
    return lines


def relevant_citations(citations: list[str], content: dict[str, Any], request: Any) -> list[str]:
    """Drop web articles the document never talks about.

    The web search matches loose keywords, so a football problem can pull in
    "Taekwondo" or "Knuckleball". A Wikipedia citation stays only when every
    significant word of its article title appears in the document itself.
    Library (textbook) citations are always kept.
    """
    def norm(text: str) -> str:
        return re.sub(r"['’]s\b", "", text.lower()).replace("-", "").replace("–", "")

    body = norm(request.normalized_prompt() + " " + json.dumps(content, ensure_ascii=False))
    kept = []
    for c in citations:
        web = re.match(r"(.*), (?:Wikipedia|Wikibooks): \S+$", str(c))
        title = web.group(1) if web else str(c)
        words = [w for w in re.findall(r"[a-z]+", norm(title)) if len(w) >= 4]
        if not web or (words and all(w in body for w in words)):
            kept.append(c)
    return kept


async def write_study_document(request: Any, solver: Any, rag: Any, settings: Any, out_dir: Path,
                               progress: Callable[[str], None] | None = None,
                               cancel_check: Callable[[], bool] | None = None) -> StudyDocResult:
    """Write the PDF (topic guide or worked solution). Never raises for content problems."""
    from aetherlab.services.research import build_citations, render_numeric_figure

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mode = classify(request.normalized_prompt())
    content, authored_by = await author_document(request, solver, rag, settings, mode, progress)
    note = ""
    if content is None:
        note = f"Model authoring unavailable ({authored_by}); built from the solver's derivation."
        content, authored_by = deterministic_document(request, solver, mode), "AetherLab (deterministic)"
    (out_dir / "content.json").write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    if progress:
        progress("Typesetting the PDF…")
    figure = render_numeric_figure(solver, out_dir / "figure.png") if getattr(solver, "numeric_spec", None) else None
    checks = independent_checks(request, solver)
    citations = relevant_citations(build_citations(rag), content, request)
    doc = build_document(content, mode, request, citations, checks, figure, authored_by)
    tex_path = out_dir / "document.tex"
    pdf, repaired, error = compile_healing(doc, tex_path, cancel_check)
    if pdf is not None:
        if repaired:
            note = (note + " " if note else "") + f"{repaired} equation(s) shown as plain text after a LaTeX error."
        return StudyDocResult(mode, tex_path, pdf, "pdflatex", authored_by, repaired, checks, note.strip())
    try:
        from aetherlab.services.research import _matplotlib_pdf

        fallback = _matplotlib_pdf(request, solver, citations, figure, out_dir / "document.pdf", checks)
    except Exception:  # noqa: BLE001
        fallback = None
    why = f"pdflatex failed ({error})"
    if fallback is not None:
        return StudyDocResult(mode, tex_path, fallback, "matplotlib", authored_by, repaired, checks,
                              f"{why}; rendered a simplified PDF instead.")
    return StudyDocResult(mode, tex_path, None, "tex-only", authored_by, repaired, checks,
                          f"{why}; wrote the LaTeX source only.")
