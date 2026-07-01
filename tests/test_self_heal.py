"""WP2: the self-heal loop feeds real errors back and skips infra failures."""

from __future__ import annotations

from aetherlab.core.models import SceneBundle
from aetherlab.services.manim_runtime import ManimRuntime, classify_render_error
from aetherlab.services.scene_generator import SceneGenerator

GOOD_SCENE = (
    "from manim import *\n"
    "class AetherLabScene(Scene):\n"
    "    def construct(self):\n"
    "        self.add(Dot())\n"
)
BAD_SYNTAX_SCENE = (
    "from manim import *\n"
    "class AetherLabScene(Scene)\n"  # missing colon -> SyntaxError
    "    def construct(self):\n"
    "        self.add(Dot())\n"
)


async def test_compile_repair_feeds_error_and_recovers(
    settings_with_key, sample_request, sample_solver, sample_rag, monkeypatch
):
    """Generation fails to compile once, then succeeds — the error is fed back."""
    seen_feedback: list[str | None] = []

    async def fake_generate(
        self, request, solver, rag, class_name="AetherLabScene", *, feedback=None, previous_code=None
    ):
        seen_feedback.append(feedback)
        return BAD_SYNTAX_SCENE if len(seen_feedback) == 1 else GOOD_SCENE

    monkeypatch.setattr(SceneGenerator, "generate", fake_generate)

    runtime = ManimRuntime(settings_with_key)
    bundle = await runtime.generate_scene_async(
        sample_request, sample_solver, sample_rag, settings_with_key
    )

    assert bundle.status == "compiled"
    assert len(seen_feedback) == 2
    assert seen_feedback[0] is None  # first attempt has no feedback
    assert seen_feedback[1] is not None and "compile" in seen_feedback[1].lower()


async def test_render_code_error_is_repaired(
    settings_with_key, sample_request, sample_solver, sample_rag, monkeypatch
):
    """A CODE render failure feeds manim's stderr back and re-renders."""
    seen_feedback: list[str | None] = []
    render_codes: list[str] = []

    async def fake_generate(
        self, request, solver, rag, class_name="AetherLabScene", *, feedback=None, previous_code=None
    ):
        seen_feedback.append(feedback)
        return GOOD_SCENE

    def fake_render_once(self, bundle, quality="l"):
        render_codes.append(bundle.code)
        if len(render_codes) == 1:
            bundle.status = "render-error"
            return bundle, "Traceback (most recent call last):\nNameError: name 'foo' is not defined"
        bundle.status = "rendered"
        bundle.video_path = "video.mp4"
        return bundle, ""

    monkeypatch.setattr(SceneGenerator, "generate", fake_generate)
    monkeypatch.setattr(ManimRuntime, "_render_once", fake_render_once)

    runtime = ManimRuntime(settings_with_key)
    scene = SceneBundle(
        class_name="AetherLabScene", code=GOOD_SCENE, engine="manim-community", status="compiled"
    )
    result = await runtime.render_scene_with_repair(
        scene, sample_request, sample_solver, sample_rag, settings_with_key
    )

    assert result.status == "rendered"
    assert len(seen_feedback) == 1  # exactly one repair attempt
    assert seen_feedback[0] is not None and "NameError" in seen_feedback[0]


async def test_infra_error_does_not_trigger_llm_repair(
    settings_with_key, sample_request, sample_solver, sample_rag, monkeypatch
):
    """An INFRA render failure must NOT burn any LLM repair calls."""
    generate_calls: list[int] = []

    async def fake_generate(self, *args, **kwargs):
        generate_calls.append(1)
        return GOOD_SCENE

    def fake_render_once(self, bundle, quality="l"):
        bundle.status = "render-error"
        return bundle, "ModuleNotFoundError: No module named 'manim'"

    monkeypatch.setattr(SceneGenerator, "generate", fake_generate)
    monkeypatch.setattr(ManimRuntime, "_render_once", fake_render_once)

    runtime = ManimRuntime(settings_with_key)
    scene = SceneBundle(
        class_name="AetherLabScene", code=GOOD_SCENE, engine="manim-community", status="compiled"
    )
    result = await runtime.render_scene_with_repair(
        scene, sample_request, sample_solver, sample_rag, settings_with_key
    )

    assert generate_calls == []  # no LLM repair attempted for infra failures
    assert result.status == "render-error"


def test_classify_render_error_taxonomy() -> None:
    assert classify_render_error("ModuleNotFoundError: No module named 'manim'") == "infra"
    assert classify_render_error("FileNotFoundError: [WinError 2] latex.exe") == "infra"
    assert classify_render_error("subprocess timed out after 180s") == "infra"
    assert classify_render_error("ffmpeg returned non-zero exit status") == "infra"
    assert classify_render_error("Traceback...\nNameError: name 'x' is not defined") == "code"
    assert classify_render_error("AttributeError: 'Axes' object has no attribute 'pl; '") == "code"
    assert classify_render_error("! Undefined control sequence.\nLaTeX Error") == "code"
    # Unknown/empty -> conservatively infra (do not burn LLM calls).
    assert classify_render_error("") == "infra"
