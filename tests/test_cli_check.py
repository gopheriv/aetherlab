"""WP6: the `--check FILE` CLI runs the safety gate + compile, no render."""

from __future__ import annotations

from aetherlab.__main__ import main

SAFE_SCENE = (
    "from manim import *\n"
    "import numpy as np\n"
    "class AetherLabScene(Scene):\n"
    "    def construct(self):\n"
    "        self.add(always_redraw(lambda: Dot()))\n"
)
UNSAFE_SCENE = (
    "from manim import *\n"
    "import os\n"
    "class AetherLabScene(Scene):\n"
    "    def construct(self):\n"
    "        os.system('echo hi')\n"
)
SYNTAX_ERROR_SCENE = "from manim import *\nclass AetherLabScene(Scene)\n    pass\n"


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_check_accepts_safe_scene(tmp_path, capsys) -> None:
    rc = main(["--check", _write(tmp_path, "ok.py", SAFE_SCENE)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK" in out


def test_check_rejects_unsafe_scene(tmp_path, capsys) -> None:
    rc = main(["--check", _write(tmp_path, "bad.py", UNSAFE_SCENE)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "UNSAFE" in out
    assert "os" in out


def test_check_rejects_syntax_error(tmp_path, capsys) -> None:
    rc = main(["--check", _write(tmp_path, "syn.py", SYNTAX_ERROR_SCENE)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "SYNTAX ERROR" in out


def test_check_missing_file(tmp_path) -> None:
    rc = main(["--check", str(tmp_path / "nope.py")])
    assert rc == 1
