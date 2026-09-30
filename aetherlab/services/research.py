"""Formal, cited research-PDF generation.

Assembles a structured LaTeX document — title, problem, abstract, derivation, a
figure rendered from the numeric ground truth, parameters, and a References
section drawn from the RAG hits — and compiles it to PDF. Compilation prefers
pdflatex; when that is unavailable it falls back to a matplotlib-rendered PDF so
a document is *always* produced. Fully deterministic (no LLM required), though
an optional LLM-authored narrative can be slotted into the abstract.
"""

from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aetherlab.services.model_policy import request_temperature
from aetherlab.services.pdf import _latex_escape, compile_latex_to_pdf

log = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    tex_path: Path
    pdf_path: Path | None
    figure_path: Path | None
    backend: str  # "pdflatex" | "matplotlib" | "tex-only"
    citations: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    note: str = ""


def build_citations(rag: Any) -> list[str]:
    """Human-readable citation strings from the RAG hits (source + page)."""
    citations: list[str] = []
    seen: set[str] = set()
    for hit in getattr(rag, "hits", [])[:8]:
        name = getattr(hit, "source_name", None) or "reference"
        page = getattr(hit, "page_number", None)
        label = f"{name}" + (f", p.{page}" if page else "")
        source = str(getattr(hit, "source_path", "") or "")
        if source.startswith(("http://", "https://")):
            site = "Wikibooks" if "wikibooks.org" in source.lower() else "Wikipedia"
            label = f"{name}, {site}: {source}"
        if label not in seen:
            seen.add(label)
            citations.append(label)
    return citations


def render_numeric_figure(solver: Any, out_path: Path) -> Path | None:
    """Render the numeric trajectory (or the analytic plot payload) to a PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return None

    t = y = None
    ylabel = "x"
    spec = getattr(solver, "numeric_spec", None)
    variables = getattr(solver, "variables", {}) or {}
    if spec:
        try:
            from aetherlab.services.numeric import solve_numeric

            sol = solve_numeric(spec, variables)
            if sol.ok and sol.t:
                t = np.asarray(sol.t, dtype=float)
                y = np.asarray(sol.series(), dtype=float)
                ylabel = sol.observe or "x"
        except Exception:
            t = y = None
    if t is None:
        plot = getattr(solver, "plot", None)
        if isinstance(plot, dict):
            try:
                from aetherlab.services.plotting import compile_plot

                compiled = compile_plot(plot, variables)
                t = np.linspace(compiled.t_range[0], compiled.t_range[1], 400)
                y = np.asarray(compiled.y_fn(t, variables), dtype=float)
                ylabel = compiled.y_label
            except Exception:
                return None
    if t is None or y is None or np.size(t) != np.size(y):
        return None

    try:
        fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=140)
        finite = np.isfinite(y)
        ax.plot(np.asarray(t)[finite], np.asarray(y)[finite], color="#0369a1", lw=2)
        ax.set_xlabel("t")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.set_title("Numerical solution")
        fig.tight_layout()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path)
        plt.close(fig)
        return out_path if out_path.exists() else None
    except Exception:
        return None


def build_latex(
    request: Any, solver: Any, rag: Any, figure_path: Path | None,
    narrative: str = "", verification: list[str] | None = None,
) -> str:
    esc = _latex_escape
    # The problem itself is the natural title of a research note. The solver's
    # summary must NOT be used here: on the keyless path it is an internal
    # diagnostic ("No API key configured; deterministic fallback used ...").
    raw_title = request.normalized_prompt().strip() or "AetherLab Derivation"
    title = esc(raw_title if len(raw_title) <= 90 else raw_title[:89].rstrip() + "...")
    prompt = esc(request.normalized_prompt())
    summary = (getattr(solver, "summary", "") or "").strip()
    if narrative.strip():
        abstract = esc(narrative.strip())
    elif getattr(solver, "model_name", "") == "deterministic-fallback":
        abstract = esc(
            "Generated offline with AetherLab's deterministic solver (no model configured). "
            "The derivation scaffold and parameters below are analytic; the figure and the "
            "verification checks are computed from the numerical ground truth."
        )
    else:
        abstract = esc(summary or "Analytical derivation and numerical solution.")
    steps = "\n".join(
        rf"  \item {esc(step)}" for step in getattr(solver, "derivation_steps", [])
    ) or r"  \item No derivation steps available."
    var_rows = "\n".join(
        rf"  {esc(name)} & = {value:g} \\" for name, value in sorted(getattr(solver, "variables", {}).items())
    ) or r"  \text{(no variables)} & \\"

    citations = build_citations(rag)
    if citations:
        items = "\n".join(rf"  \item {esc(c)}" for c in citations)
        refs_block = "\\section*{References}\n\\begin{enumerate}\n" + items + "\n\\end{enumerate}\n"
    else:
        refs_block = (
            "\\section*{References}\n"
            "No local references matched; results are derived from first principles.\n"
        )

    fig_block = ""
    if figure_path is not None:
        latex_path = str(figure_path).replace("\\", "/")
        fig_block = (
            "\\begin{figure}[h]\n\\centering\n"
            f"\\includegraphics[width=0.8\\textwidth]{{{latex_path}}}\n"
            "\\caption{Numerical solution (ground truth).}\n\\end{figure}\n"
        )

    verify_block = ""
    if verification:
        items = "\n".join(rf"  \item {esc(line)}" for line in verification)
        verify_block = "\\section*{Verification}\n\\begin{itemize}\n" + items + "\n\\end{itemize}\n\n"

    return rf"""\documentclass[11pt]{{article}}
\usepackage[margin=2.5cm]{{geometry}}
\usepackage{{amsmath,amssymb}}
\usepackage{{graphicx}}
\title{{{title}}}
\date{{\today}}

\begin{{document}}
\maketitle

\section*{{Problem}}
{prompt}

\section*{{Abstract}}
{abstract}

\section*{{Derivation}}
\begin{{enumerate}}
{steps}
\end{{enumerate}}

\section*{{Parameters}}
\[
\begin{{array}}{{rl}}
{var_rows}
\end{{array}}
\]

{fig_block}{verify_block}{refs_block}\end{{document}}
"""


def build_research_pdf(
    request: Any, solver: Any, rag: Any, out_dir: Path, narrative: str = ""
) -> ResearchResult:
    """Produce a formal, cited PDF. Never raises; always writes at least a .tex."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figure_path = render_numeric_figure(solver, out_dir / "figure.png")
    citations = build_citations(rag)

    try:
        from aetherlab.services.verify import verify_solution

        verification = verify_solution(solver, request).as_lines()
    except Exception:  # noqa: BLE001 — verification is advisory, never fatal
        verification = []

    tex = build_latex(request, solver, rag, figure_path, narrative, verification)
    tex_path = out_dir / "research.tex"
    tex_path.write_text(tex, encoding="utf-8")

    pdf = compile_latex_to_pdf(tex_path)
    if pdf is not None:
        return ResearchResult(tex_path, pdf, figure_path, "pdflatex", citations, verification)

    pdf = _matplotlib_pdf(request, solver, citations, figure_path, out_dir / "research.pdf", verification)
    if pdf is not None:
        return ResearchResult(
            tex_path, pdf, figure_path, "matplotlib", citations, verification,
            note="pdflatex unavailable; rendered PDF via matplotlib.",
        )

    return ResearchResult(
        tex_path, None, figure_path, "tex-only", citations, verification,
        note="No PDF backend available; wrote LaTeX source only.",
    )


def _matplotlib_pdf(
    request: Any, solver: Any, citations: list[str], figure_path: Path | None, out_path: Path,
    verification: list[str] | None = None,
) -> Path | None:
    """pdflatex-free fallback: a two-page PDF (text + figure) via matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
    except Exception:
        return None

    try:
        lines: list[str] = ["Problem:"]
        lines += textwrap.wrap(request.normalized_prompt(), 92) or [""]
        lines += ["", "Summary:"]
        lines += textwrap.wrap(getattr(solver, "summary", "") or "", 92)
        lines += ["", "Derivation:"]
        for i, step in enumerate(getattr(solver, "derivation_steps", []), 1):
            lines += textwrap.wrap(f"{i}. {step}", 90)
        lines += ["", "Parameters: " + ", ".join(
            f"{k}={v:g}" for k, v in sorted(getattr(solver, "variables", {}).items())
        )]
        if verification:
            lines += ["", "Verification:"]
            lines += ["  " + line for line in verification]
        lines += ["", "References:"]
        lines += (["  - " + c for c in citations] or ["  (none)"])

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with PdfPages(str(out_path)) as pdf:
            fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
            fig.text(0.08, 0.95, "AetherLab — Research Note", fontsize=16, weight="bold")
            fig.text(0.08, 0.91, "\n".join(lines[:64]), fontsize=9, va="top", family="monospace")
            pdf.savefig(fig)
            plt.close(fig)
            if figure_path is not None and Path(figure_path).exists():
                img = plt.imread(str(figure_path))
                fig2 = plt.figure(figsize=(8.27, 11.69))
                fig2.text(0.1, 0.88, "Numerical solution", fontsize=13, weight="bold")
                ax = fig2.add_axes([0.1, 0.42, 0.8, 0.4])
                ax.imshow(img)
                ax.axis("off")
                pdf.savefig(fig2)
                plt.close(fig2)
        return out_path if out_path.exists() else None
    except Exception:
        return None


async def compose_narrative(request: Any, solver: Any, settings: Any) -> str:
    """Optional LLM-authored abstract (2-3 sentences). Returns '' on any failure."""
    if not getattr(settings, "openai_api_key", None):
        return ""
    try:
        from aetherlab.services.llm_client import make_client

        client = make_client(settings)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": (
                    "Write a concise 2-3 sentence abstract for a physics research note. "
                    "Plain prose, no markdown, no LaTeX commands."
                )},
                {"role": "user", "content": (
                    f"Problem: {request.normalized_prompt()}\nSummary: {getattr(solver, 'summary', '')}"
                )},
            ],
            temperature=request_temperature(settings, 0.3),
            max_tokens=220,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""
