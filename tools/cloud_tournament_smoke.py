"""Manual live smoke for Quality-Flywheel Phase 2 (parallel cloud fan-out).

Renders N byte-identical scenes CONCURRENTLY through the real GitHub Actions
render backend, each with a distinct per-candidate variant, and verifies that
every candidate gets a DISTINCT job id and downloads its OWN artifact — i.e. the
BUG-15 artifact-steal race cannot happen under concurrency.

This is a MANUAL script: it needs a configured render repo + token and real
GitHub Actions minutes, so it is not part of the headless harness (which stubs
GitHub in `test_features.t_f171`). It never prints secrets.

    python tools/cloud_tournament_smoke.py [--n 3]

Exit codes: 0 = all candidates rendered with isolated artifacts; 1 = a candidate
failed to render; 2 = cloud backend not configured.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SCENE = (
    "from manim import *\n\n"
    "class AetherLabScene(Scene):\n"
    "    def construct(self):\n"
    "        self.play(Create(Circle()))\n"
    "        self.wait(1)\n"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=3, help="number of concurrent identical candidates")
    args = parser.parse_args(argv)

    from aetherlab.core.models import SceneBundle
    from aetherlab.core.settings import load_settings
    from aetherlab.services.render_backend import (
        CloudRenderBackend,
        cloud_job_id,
        render_fps_for,
    )

    settings = load_settings()
    backend = CloudRenderBackend(settings)
    ok, reason = backend.available()
    if not ok:
        print(f"Cloud backend not available: {reason}")
        print("Configure a render repo + token (Settings -> Test cloud render), then retry.")
        return 2

    n = max(2, args.n)
    fps = render_fps_for(_SCENE, "l")
    variants = [f"cand{i}" for i in range(n)]

    # Distinct job ids for identical code — proven before spending any minutes.
    ids = {
        v: cloud_job_id(SceneBundle("AetherLabScene", _SCENE, "manim", "compiled"), quality="l", fps=fps, variant=v)
        for v in variants
    }
    print("job ids:", ids)
    if len(set(ids.values())) != n:
        print("FAIL: job ids collided for identical code — isolation is broken.")
        return 1

    async def render_one(variant: str) -> tuple[str, SceneBundle]:
        scene = SceneBundle("AetherLabScene", _SCENE, "manim", "compiled")
        out = await backend.render(
            scene,
            quality="l",
            settings=settings,
            timeout=int(getattr(settings, "cloud_render_timeout", 1800)),
            variant=variant,
            progress=lambda m, v=variant: print(f"[{v}] {m}"),
        )
        return variant, out

    async def run() -> list[tuple[str, SceneBundle]]:
        return await asyncio.gather(*(render_one(v) for v in variants))

    results = asyncio.run(run())

    all_ok = True
    paths: list[str] = []
    for variant, out in results:
        rendered = out.status == "rendered" and bool(out.video_path) and Path(out.video_path).exists()
        print(f"{variant}: status={out.status} video={out.video_path}")
        if out.video_path:
            paths.append(out.video_path)
        all_ok = all_ok and rendered

    if len(set(paths)) != len(paths):
        print("FAIL: two candidates shared a video path — artifact cross-wiring.")
        return 1

    print("PASS: every candidate rendered to its own isolated artifact." if all_ok
          else "FAIL: a candidate did not render.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
