"""Stage C cloud probe: dispatch a tiny trilingual scene via CloudRenderBackend.

Usage (from project root):
  python .qwen/tmp/stage_c_probe.py preflight   # local dry-run only
  python .qwen/tmp/stage_c_probe.py cloud       # real cloud render -> output/stage_c_probe/
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

SCENE_CODE = '''from manim import *


class StageCProbe(Scene):
    def construct(self):
        formula = MathTex(r"v = v_0 + at").scale(1.2)
        formula.to_edge(UP)
        ax = Axes(
            x_range=[0, 4, 1],
            y_range=[0, 14, 2],
            x_length=5,
            y_length=3,
            x_axis_config={"include_tip": True},
            y_axis_config={"include_tip": True},
        )
        line = ax.plot(lambda t: 2 + 3 * t, color=BLUE)
        label = ax.get_graph_label(line, MathTex(r"v(t)=2+3t"))
        lines = VGroup(
            Text("Скорость растёт линейно", font_size=26),
            Text("Жылдамдық сызықты өседі: ә ғ қ ң ө ұ ү һ і", font_size=26),
            Text("Velocity grows linearly", font_size=26),
        ).arrange(DOWN, aligned_edge=LEFT).to_edge(DOWN)
        self.play(Write(formula), run_time=1)
        self.play(Create(ax), run_time=1)
        self.play(Create(line), FadeIn(label), run_time=1.5)
        self.play(FadeIn(lines), run_time=1)
        self.wait(0.5)
'''

CLASS_NAME = "StageCProbe"
QUALITY = "m"


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

def cmd_preflight() -> int:
    from aetherlab.services.scene_preflight import preflight_scene

    t0 = time.monotonic()
    report = preflight_scene(SCENE_CODE, CLASS_NAME)
    print(f"ran={report.ran} ok={report.ok} duration_s={report.duration_s} "
          f"seconds={report.seconds} wall={time.monotonic() - t0:.1f}s")
    if report.error:
        print("error:", report.error[:2000])
    if report.note:
        print("note:", report.note[:2000])
    if report.off_frame:
        print("off_frame:", json.dumps(report.off_frame, ensure_ascii=False)[:2000])
    return 0 if report.ok else 1


def _stream_facts(path: Path) -> dict:
    import av

    facts: dict = {"path": str(path), "bytes": path.stat().st_size}
    with av.open(str(path)) as container:
        video = next((s for s in container.streams if s.type == "video"), None)
        assert video is not None, "no video stream"
        facts["video_streams"] = sum(1 for s in container.streams if s.type == "video")
        facts["width"] = video.width
        facts["height"] = video.height
        rate = video.average_rate
        facts["fps"] = float(rate) if rate else 0.0
        dur = None
        if video.duration and video.time_base:
            dur = float(video.duration * video.time_base)
        elif container.duration:
            dur = float(container.duration) / 1_000_000
        facts["duration_s"] = dur or 0.0
        facts["codec"] = video.codec_context.name if video.codec_context else ""
    return facts


def cmd_cloud() -> int:
    from aetherlab.core.models import SceneBundle
    from aetherlab.core.settings import load_settings
    from aetherlab.services.render_backend import (
        CloudRenderBackend,
        probe_mp4,
        render_timeout_for,
        validate_mp4,
    )

    settings = load_settings()
    assert str(getattr(settings, "render_mode", "")).lower() == "cloud", "render_mode must be cloud"
    assert getattr(settings, "github_repo", ""), "github_repo not configured"
    backend = CloudRenderBackend(settings)
    ok, reason = backend.available()
    print(f"backend available={ok} ({reason})", flush=True)
    assert ok, reason

    timeout = render_timeout_for(SCENE_CODE, QUALITY, settings)
    print(f"quality={QUALITY} timeout={timeout}s data_dir={settings.data_dir}", flush=True)

    scene = SceneBundle(class_name=CLASS_NAME, code=SCENE_CODE,
                        engine="manim", status="compiled")

    def say(message: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)

    t0 = time.monotonic()
    result = asyncio.run(backend.render(
        scene, quality=QUALITY, settings=settings, timeout=timeout, progress=say))
    wall = time.monotonic() - t0
    print(f"status={result.status} failure_kind={result.failure_kind} wall={wall:.0f}s",
          flush=True)
    for diag in result.diagnostics[-8:]:
        print("diag:", diag[:500], flush=True)
    if result.status != "rendered" or not result.video_path:
        print("CLOUD PROBE FAILED", flush=True)
        return 1

    video = Path(result.video_path)
    print(f"container_ok={validate_mp4(video)} gate={probe_mp4(video)}", flush=True)
    facts = _stream_facts(video)
    facts.update({"status": result.status, "wall_s": round(wall, 1),
                  "requested": {"quality": QUALITY}})
    print("stream:", json.dumps(facts, ensure_ascii=False), flush=True)

    out = Path("output/stage_c_probe")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, out / "probe.mp4")
    (out / "params.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    (out / "scene.py").write_text(SCENE_CODE, encoding="utf-8")
    print(f"evidence -> {out.resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "preflight"
    sys.exit(cmd_cloud() if mode == "cloud" else cmd_preflight())
