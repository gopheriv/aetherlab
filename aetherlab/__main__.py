"""Command-line entry point for AetherLab."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from aetherlab import __version__
from aetherlab.core.models import ProblemRequest
from aetherlab.core.settings import load_settings
from aetherlab.services.code_safety import validate_code_safety
from aetherlab.services.pipeline import AetherLabPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aetherlab",
        description="Launch or smoke-test the AetherLab workbench.",
    )
    parser.add_argument(
        "--smoke",
        nargs="?",
        const="Derive the damped harmonic oscillator and visualize phase space.",
        help="Run the headless analytical/RAG/scene-generation pipeline.",
    )
    parser.add_argument(
        "--check",
        metavar="FILE",
        help="Validate a scene file through the AST safety gate and compile check, "
        "then exit (no render). Exit code 0 = safe & compiles, 1 = rejected.",
        "--version", action="version", version=f"AetherLab {__version__}"
    )
    return parser


def _run_check(path_str: str) -> int:
    """Run the safety gate + compile check on a scene file. No render."""
    path = Path(path_str)
    if not path.is_file():
        print(f"check: no such file: {path}", file=sys.stderr)
        return 1
    code = path.read_text(encoding="utf-8")

    safe, issues = validate_code_safety(code)
    if not safe:
        print(f"UNSAFE: {path}")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    try:
        compile(code, str(path), "exec")
    except SyntaxError as exc:
        print(f"SYNTAX ERROR: {path}: {exc}")
        return 1

    print(f"OK: {path} passed the safety gate and compiles.")
    return 0
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
        logging.getLogger(__name__).info("AetherLab %s starting", __version__)
    except Exception:  # noqa: BLE001 — logging must never block launch
        pass


async def _run_smoke(prompt: str) -> int:
    settings = load_settings()
    pipeline = AetherLabPipeline(settings=settings)
    result = await pipeline.run(ProblemRequest(prompt=prompt))

    print("AetherLab smoke pipeline complete")
    print(f"Cache key: {result.cache_key}")
    print(f"Solver model: {result.solver.model_name}")
    print(f"Keywords: {', '.join(result.solver.keywords) or 'none'}")
    print(f"RAG hits: {len(result.rag.hits)}")
    print(f"Scene engine: {result.scene.engine}")
    print(f"Scene status: {result.scene.status}")
    return 0


def main(argv: list[str] | None = None) -> int:
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
    if args.check is not None:
        return _run_check(args.check)
    _setup_logging()
    if args.smoke is not None:
        return asyncio.run(_run_smoke(args.smoke))

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
