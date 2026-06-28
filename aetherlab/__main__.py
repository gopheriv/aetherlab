"""Command-line entry point for AetherLab."""

from __future__ import annotations

import argparse
import asyncio
import sys

from aetherlab.core.models import ProblemRequest
from aetherlab.core.settings import load_settings
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
    return parser


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
    args = build_parser().parse_args(argv)
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
