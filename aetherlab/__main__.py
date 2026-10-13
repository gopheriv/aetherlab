"""Command-line entry point for PhysLab (module-compatible with AetherLab)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler

from aetherlab import __version__
from aetherlab.core.console import configure_utf8_stdio
from aetherlab.core.models import ProblemRequest
from aetherlab.core.settings import load_settings
from aetherlab.services.pipeline import AetherLabPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="physlab",
        description="Launch or smoke-test the PhysLab physics learning workbench.",
    )
    parser.add_argument(
        "--smoke",
        nargs="?",
        const="Derive the damped harmonic oscillator and visualize phase space.",
        help="Run the headless analytical/RAG/scene-generation pipeline.",
    )
    parser.add_argument(
        "--pdf",
        metavar="PROMPT",
        help="Write a well-explained LaTeX PDF: a study guide for a topic, or theory "
             "plus a step-by-step solution for a problem.",
    )
    parser.add_argument(
        "--out", default="aetherlab_document.pdf",
        help="Where to save the --pdf document (default: %(default)s).",
    )
    parser.add_argument(
        "--version", action="version", version=f"PhysLab {__version__}"
    )
    return parser


async def _run_pdf(prompt: str, out: str) -> int:
    import shutil
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from aetherlab.services.llm import AsyncLLMCoordinator
    from aetherlab.services.pipeline import _merge_web_references
    from aetherlab.services.rag import LocalVectorRag
    from aetherlab.services.study_document import write_study_document

    settings = load_settings()
    request = ProblemRequest(prompt=prompt)
    print("Solving…", flush=True)
    solver = await AsyncLLMCoordinator(settings).solve(request)
    rag = await LocalVectorRag(settings).search(solver.keywords)
    rag = await _merge_web_references(rag, solver.keywords, settings)
    with TemporaryDirectory(prefix="aetherlab_pdf_") as tmp:
        doc = await write_study_document(
            request, solver, rag, settings, Path(tmp), progress=lambda m: print(m, flush=True))
        target = Path(out)
        content = Path(tmp) / "content.json"
        if content.exists():  # the model's structured content, to rebuild the PDF without a new call
            shutil.copyfile(content, target.with_suffix(".json"))
        if doc.pdf_path and doc.pdf_path.exists():
            shutil.copyfile(doc.pdf_path, target)
            shutil.copyfile(doc.tex_path, target.with_suffix(".tex"))
            print(f"{doc.mode} document ({doc.backend}, written by {doc.authored_by}): {target}")
            if doc.note:
                print(f"note: {doc.note}")
            return 0
        shutil.copyfile(doc.tex_path, target.with_suffix(".tex"))
        print(f"No PDF produced ({doc.note}); LaTeX saved: {target.with_suffix('.tex')}")
        return 1


def _setup_logging() -> None:
    """Rotating file log under the data dir — what students attach to bug
    reports. Best-effort: a read-only disk must not stop the app."""
    try:
        settings = load_settings()
        log_dir = settings.data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "aetherlab.log", maxBytes=1_000_000, backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root = logging.getLogger()
        root.addHandler(handler)
        if root.level > logging.INFO or root.level == logging.NOTSET:
            root.setLevel(logging.INFO)
        logging.getLogger(__name__).info("PhysLab %s starting", __version__)
    except Exception:  # noqa: BLE001 — logging must never block launch
        pass


async def _run_smoke(prompt: str) -> int:
    settings = load_settings()
    pipeline = AetherLabPipeline(settings=settings)
    result = await pipeline.run(ProblemRequest(prompt=prompt))

    print("PhysLab smoke pipeline complete")
    print(f"Cache key: {result.cache_key}")
    print(f"Plan ({result.plan.model_name}): {', '.join(result.plan.enabled()) or 'none'}")
    print(f"Solver model: {result.solver.model_name}")
    print(f"Keywords: {', '.join(result.solver.keywords) or 'none'}")
    print(f"RAG hits: {len(result.rag.hits)}")
    print(f"Scene engine: {result.scene.engine}")
    print(f"Scene status: {result.scene.status}")
    try:
        from aetherlab.services.verify import verify_solution

        report = verify_solution(result.solver, result.request)
        print(f"Verification: {report.summary}")
        for line in report.as_lines():
            print(f"  {line}")
    except Exception:
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    raw = list(sys.argv[1:] if argv is None else argv)
    # Frozen-bundle relay: inside a PyInstaller dist there is no `python -m
    # manim`, so the renderer re-invokes THIS exe as `aetherlab --manim render
    # ...` and we hand argv to Manim's own CLI (subprocess isolation + render
    # timeouts keep working exactly as in dev).
    if raw and raw[0] == "--manim":
        sys.argv = ["manim", *raw[1:]]
        from manim.__main__ import main as manim_main

        manim_main()  # click exits via SystemExit with the proper code
        return 0

    args = build_parser().parse_args(argv)
    _setup_logging()
    if args.smoke is not None:
        return asyncio.run(_run_smoke(args.smoke))
    if args.pdf:
        return asyncio.run(_run_pdf(args.pdf, args.out))

    try:
        from aetherlab.ui.app import run_app
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        return run_app()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
