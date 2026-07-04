"""WP3: _extract_code must rename any scene base, strip fences, inject imports."""

from __future__ import annotations

import pytest

from aetherlab.services.scene_generator import SceneGenerator

from .conftest import make_settings


@pytest.fixture
def generator(tmp_path):
    return SceneGenerator(make_settings(tmp_path))


@pytest.mark.parametrize(
    "base",
    ["Scene", "ThreeDScene", "MovingCameraScene", "ZoomedScene"],
)
def test_rename_preserves_any_base(generator, base: str) -> None:
    src = (
        "from manim import *\n"
        f"class MyCoolScene({base}):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
    )
    out = generator._extract_code(src, "AetherLabScene")
    assert f"class AetherLabScene({base}):" in out
    assert "MyCoolScene" not in out


def test_multiclass_prefers_scene_subclass(generator) -> None:
    src = (
        "from manim import *\n"
        "class Helper:\n"
        "    pass\n"
        "class Viz(MovingCameraScene):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
    )
    out = generator._extract_code(src, "AetherLabScene")
    # The Scene subclass is renamed; the plain helper class is left alone.
    assert "class AetherLabScene(MovingCameraScene):" in out
    assert "class Helper:" in out


def test_strips_markdown_fences(generator) -> None:
    src = (
        "```python\n"
        "from manim import *\n"
        "class AetherLabScene(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
        "```"
    )
    out = generator._extract_code(src, "AetherLabScene")
    assert "```" not in out
    assert out.strip().startswith("from manim import *")


def test_injects_missing_import(generator) -> None:
    src = (
        "class AetherLabScene(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
    )
    out = generator._extract_code(src, "AetherLabScene")
    assert "from manim import *" in out


def test_keeps_existing_correct_class(generator) -> None:
    src = (
        "from manim import *\n"
        "class AetherLabScene(ThreeDScene):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
    )
    out = generator._extract_code(src, "AetherLabScene")
    assert "class AetherLabScene(ThreeDScene):" in out
