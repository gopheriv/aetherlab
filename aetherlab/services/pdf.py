"""PyMuPDF helpers for textbook viewing, extraction, and LaTeX/PDF export."""

from __future__ import annotations

import subprocess
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


def compile_latex_to_pdf(tex_path: Path) -> Path | None:
    """Compile a .tex file to PDF using pdflatex. Returns PDF path or None."""
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(tex_path.parent), str(tex_path)],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        pdf_path = tex_path.with_suffix(".pdf")
        if pdf_path.exists():
            return pdf_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def export_scene_code(code: str, output_path: Path) -> Path:
    """Save generated Manim scene code to a .py file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding="utf-8")
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
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result
