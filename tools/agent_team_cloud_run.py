"""Live check: the 3-agent team authors a scene, previews and final render on the cloud.

Usage: python tools/agent_team_cloud_run.py <out_dir> "<prompt>"
Uses the saved settings as-is (render_mode=cloud).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
from aetherlab.core.models import ProblemRequest  # noqa: E402
from aetherlab.core.settings import load_settings  # noqa: E402
from aetherlab.services import manim_runtime  # noqa: E402
from aetherlab.services.agent_team import AgentTeamGenerator  # noqa: E402
from aetherlab.services.llm import AsyncLLMCoordinator  # noqa: E402
from aetherlab.services.pipeline import _merge_web_references  # noqa: E402
from aetherlab.services.rag import LocalVectorRag  # noqa: E402
from aetherlab.services.scene_critic import critique_video  # noqa: E402

configure_utf8_stdio()
OUT = Path(sys.argv[1])
PROMPT = sys.argv[2]
OUT.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(OUT / "run.log", encoding="utf-8")],
)
T0 = time.monotonic()


def say(msg: str) -> None:
    print(f"[{time.monotonic() - T0:7.1f}s] {msg}", flush=True)


class _LoggedTeam(AgentTeamGenerator):
    """Prints each team step as it happens."""

    def _note(self, role, started, summary, **extra):
        super()._note(role, started, summary, **extra)
        say(f"  team {role} ({time.monotonic() - started:.0f}s): {summary[:220]!r}")


async def main() -> int:
    s = load_settings()
    say(f"model={s.llm_model} render_mode={s.render_mode} repo={s.github_repo}")
    request = ProblemRequest(prompt=PROMPT)
    solver = await AsyncLLMCoordinator(s).solve(request)
    say(f"solved by {solver.model_name}: {solver.summary[:140]!r}")
    rag = await LocalVectorRag(s).search(solver.keywords)
    rag = await _merge_web_references(rag, solver.keywords, s)
    say(f"rag: {len(rag.hits)} hits")

    team_holder: dict[str, AgentTeamGenerator] = {}

    def make_generator(settings, **kwargs):
        team = _LoggedTeam(settings, **kwargs)
        team_holder.setdefault("team", team)
        return team

    manim_runtime.SceneGenerator = make_generator  # the team authors; gates/render unchanged
    runtime = manim_runtime.ManimRuntime(s)
    bundle = await runtime.generate_scene_async(request, solver, rag, s)
    team = team_holder.get("team")
    say(f"scene: used_fallback={bundle.used_fallback} code={len(bundle.code)} chars")
    if bundle.fallback_reason:
        say(f"FALLBACK REASON: {bundle.fallback_reason}")
    if team is not None:
        say(f"team stats: {team.team_stats}")
        (OUT / "team_log.json").write_text(json.dumps(team.team_log, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    (OUT / "scene.py").write_text(bundle.code, encoding="utf-8")

    rendered = await runtime.render_scene_with_repair(
        bundle, s, quality="l", max_repairs=2, max_revisions=0, brief=PROMPT,
        progress=lambda m: say(f"  progress: {m}"),
    )
    say(f"render: status={rendered.status} failure={rendered.failure_kind} video={rendered.video_path}")
    for d in rendered.diagnostics[-4:]:
        say(f"  diag: {d[:300]}")
    if rendered.status == "rendered" and rendered.video_path:
        board = rendered.storyboard if isinstance(rendered.storyboard, dict) else {}
        crit = await critique_video(rendered.video_path, PROMPT, s, frame_count=6,
                                    expected_physics=board.get("physics_expectations", []))
        say(f"critic: {crit.verdict} score={crit.score} issues={crit.issues[:3]}")
    (OUT / "bundle.json").write_text(json.dumps(rendered.to_json(), indent=2, default=str),
                                     encoding="utf-8")
    say("DONE")
    return 0 if rendered.status == "rendered" and not bundle.used_fallback else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
