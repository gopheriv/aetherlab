"""PyMuPDF helpers for textbook viewing, extraction, and LaTeX/PDF export."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PdfPageImage:
    path: Path
    page_number: int
    width: int
    height: int


class PdfService:
    def __init__(self) -> None:
        try:
            import fitz
        except Exception as exc:
            self._fitz = None
            self._import_error = exc
        else:
            self._fitz = fitz
            self._import_error = None

    @property
    def available(self) -> bool:
        return self._fitz is not None

    @property
    def import_error(self) -> Exception | None:
        return self._import_error

    def extract_page_text(self, pdf_path: Path, page_number: int) -> str:
        if self._fitz is None:
            raise RuntimeError("PyMuPDF is not available") from self._import_error
        document = self._fitz.open(pdf_path)
        try:
            page = document.load_page(max(page_number - 1, 0))
            return page.get_text("text")
        finally:
            document.close()

    def render_page_png(self, pdf_path: Path, page_number: int, output_path: Path, zoom: float = 1.5) -> PdfPageImage:
        if self._fitz is None:
            raise RuntimeError("PyMuPDF is not available") from self._import_error
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document = self._fitz.open(pdf_path)
        try:
            page = document.load_page(max(page_number - 1, 0))
            matrix = self._fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(output_path)
            return PdfPageImage(
                path=output_path,
                page_number=page_number,
                width=pixmap.width,
                height=pixmap.height,
            )
        finally:
            document.close()


# ────────────────────────────────────────────────────────────────────────────
# Export: Derivation → LaTeX → PDF
# ────────────────────────────────────────────────────────────────────────────


def export_derivation_to_latex(
    summary: str,
    derivation_steps: list[str],
    variables: dict[str, float],
    output_path: Path,
    key_equations: list[str] | None = None,
) -> Path:
    """Write a standalone LaTeX document from solver results."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    var_rows = "\n".join(
        f"  {name} & = {value:g} \\\\"
        for name, value in sorted(variables.items())
    ) or r"  \text{(no variables)}"

    step_items = "\n".join(
        f"  \\item {_latex_escape(step)}"
        for step in derivation_steps
    ) or r"  \item No derivation steps available."

    # key_equations are already LaTeX — emitted verbatim in display math,
    # NOT escaped (escaping would destroy them).
    equations_block = ""
    if key_equations:
        rows = "\n".join(f"\\[ {eq} \\]" for eq in key_equations)
        equations_block = f"\n\\section*{{Key Equations}}\n{rows}\n"

    latex = rf"""\documentclass[11pt]{{article}}
\usepackage[margin=2.5cm]{{geometry}}
\usepackage{{amsmath,amssymb}}
\usepackage{{booktabs}}

\title{{AetherLab — Analytical Derivation}}
\date{{\today}}

\begin{{document}}
\maketitle

\section*{{Summary}}
{_latex_escape(summary)}
{equations_block}

\section*{{Derivation Steps}}
\begin{{enumerate}}
{step_items}
\end{{enumerate}}

\section*{{Simulation Variables}}
\[
\begin{{array}}{{rl}}
{var_rows}
\end{{array}}
\]

\end{{document}}
"""
    output_path.write_text(latex, encoding="utf-8")
    return output_path


def compile_latex_to_pdf(
    tex_path: Path,
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> Path | None:
    """Compile a .tex file to PDF using pdflatex. Returns PDF path or None."""
    from aetherlab.core.proc import (
        ProcessCancelledError,
        run_process_tree,
        subprocess_kwargs,
    )

    pdf_path = tex_path.with_suffix(".pdf")
    pdf_path.unlink(missing_ok=True)
    try:
        result = run_process_tree(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(tex_path.parent), str(tex_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cancel_check=cancel_check,
            **subprocess_kwargs(),
        )
        if result.returncode == 0 and pdf_path.exists():
            return pdf_path
    except ProcessCancelledError:
        raise
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def export_scene_code(code: str, output_path: Path) -> Path:
    """Save generated Manim scene code to a .py file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding="utf-8")
    return output_path


def export_lesson_study_guide(plan, output_path: Path) -> Path:
    """Write a printable LaTeX study guide from a LessonPlan (topic explainer).

    Sections: objectives, the misconception, per-chapter summaries with their
    typeset key equations and citations, and a self-check with answers. Returns
    the .tex path (compile with compile_latex_to_pdf, as the derivation export
    does). key_equations are emitted verbatim in display math (already LaTeX).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    from aetherlab.core.language import normalize_language

    language = normalize_language(getattr(plan, "language", "en"))
    labels = {
        "kk": {
            "date": "Оқу нұсқаулығы · AetherLab",
            "objectives": "Оқу мақсаттары", "prerequisites": "Алдын ала білу керек",
            "watch": "Есте сақтаңыз", "terms": "Қазақша физика терминдері",
            "chapters": "Сабақ бөлімдері", "check": "Өзіңізді тексеріңіз",
            "meaning": "Түсіндірме", "translation": "Аудармасы",
        },
        "ru": {
            "date": "Учебный конспект · AetherLab",
            "objectives": "Цели обучения", "prerequisites": "Что нужно знать заранее",
            "watch": "Важно помнить", "terms": "Казахские термины по физике",
            "chapters": "Разделы урока", "check": "Проверьте себя",
            "meaning": "Простое объяснение", "translation": "Перевод",
        },
        "en": {
            "date": "Study guide · AetherLab",
            "objectives": "Learning objectives", "prerequisites": "Prerequisites",
            "watch": "Keep in mind", "terms": "Kazakh physics terms",
            "chapters": "Lesson chapters", "check": "Check yourself",
            "meaning": "Plain-language meaning", "translation": "Translation",
        },
    }[language]

    def items(xs: list[str]) -> str:
        return "\n".join(f"  \\item {_latex_escape(str(x))}" for x in xs) or r"  \item —"

    objectives = items(plan.objectives)
    prereqs = items(plan.prerequisites)

    chapter_blocks = []
    for i, ch in enumerate(plan.chapters, 1):
        eqs = "\n".join(f"\\[ {eq} \\]" for eq in ch.key_equations)
        cites = ""
        if ch.citations:
            cites = "\n\\textit{Sources: " + _latex_escape("; ".join(ch.citations)) + "}\n"
        chapter_blocks.append(
            f"\\subsection*{{{i}. {_latex_escape(ch.title)}}}\n"
            f"{_latex_escape(ch.goal)}\n\n"
            f"{_latex_escape(ch.narration)}\n{eqs}\n{cites}"
        )
    chapters = "\n\n".join(chapter_blocks)

    q_blocks = []
    for i, q in enumerate(plan.questions, 1):
        choices = ""
        if q.choices:
            choices = "\n\\begin{itemize}\n" + "\n".join(
                f"  \\item {_latex_escape(c)}" for c in q.choices
            ) + "\n\\end{itemize}"
        why = f" — {_latex_escape(q.why)}" if q.why else ""
        q_blocks.append(
            f"\\item {_latex_escape(q.q)}{choices}\n\n"
            f"\\textbf{{Answer:}} {_latex_escape(q.answer)}{why}"
        )
    questions = "\n".join(q_blocks) or r"\item —"

    term_blocks = []
    for item in getattr(plan, "kazakh_terms", []) or []:
        if not isinstance(item, dict):
            continue
        term = _latex_escape(str(item.get("term_kk", "")).strip())
        translation = _latex_escape(str(item.get("translation", "")).strip())
        meaning = _latex_escape(str(item.get("meaning", "")).strip())
        if term:
            term_blocks.append(
                f"\\item \\textbf{{{term}}} — {translation}. {meaning}"
            )
    terms = "\n".join(term_blocks)
    terms_section = (
        f"\\section*{{{labels['terms']}}}\n\\begin{{itemize}}\n{terms}\n\\end{{itemize}}"
        if terms else ""
    )

    latex = rf"""\documentclass[11pt]{{article}}
\usepackage[margin=2.3cm]{{geometry}}
\usepackage[utf8]{{inputenc}}
\usepackage{{amsmath,amssymb}}

\title{{{_latex_escape(plan.title)}}}
\date{{{labels['date']}}}

\begin{{document}}
\maketitle

\section*{{{labels['objectives']}}}
\begin{{itemize}}
{objectives}
\end{{itemize}}

\section*{{{labels['prerequisites']}}}
\begin{{itemize}}
{prereqs}
\end{{itemize}}

\section*{{{labels['watch']}}}
{_latex_escape(plan.misconception) or "—"}

{terms_section}

\section*{{{labels['chapters']}}}
{chapters}

\section*{{{labels['check']}}}
\begin{{enumerate}}
{questions}
\end{{enumerate}}

\end{{document}}
"""
    output_path.write_text(latex, encoding="utf-8")
    return output_path


def _latex_escape(text: str) -> str:
    """Escape special LaTeX characters."""
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        # Must stay AFTER the brace entries: in text mode LaTeX renders a bare
        # "<"/">" as the inverted marks "¡"/"¿" (so "<=" printed as "¡=" and
        # "->" as "-¿"), and the braces introduced here must not be re-escaped.
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result
