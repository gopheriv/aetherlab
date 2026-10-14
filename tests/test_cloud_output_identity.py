"""Execute the exact worker output-selection code, without contacting GitHub."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from aetherlab.core.proc import subprocess_kwargs
from aetherlab.services.render_backend import RENDER_WORKFLOW_YAML


def _select(tmp_path: Path) -> subprocess.CompletedProcess:
    marker = "          # Select exactly one final output for the requested scene."
    assert marker in RENDER_WORKFLOW_YAML, "The worker must require exact scene identity"
    block = RENDER_WORKFLOW_YAML.split(marker, 1)[1].split("python - <<'PY'", 1)[1]
    code = textwrap.dedent(block.split("\n          PY", 1)[0])
    environment = dict(os.environ, SCENE_CLASS="RequestedScene", RENDER_JOB_ID="test-job")
    return subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, env=environment,
        capture_output=True, text=True, timeout=15, **subprocess_kwargs(),
    )


def _rejection_case(tmp_path: Path, case: str) -> None:
    videos = tmp_path / "out" / "videos"
    videos.mkdir(parents=True)
    if case == "other-scene":
        (videos / "OtherScene.mp4").write_bytes(b"unrelated" * 1000)
    elif case == "partial-only":
        partial = videos / "partial_movie_files" / "RequestedScene"
        partial.mkdir(parents=True)
        (partial / "RequestedScene.mp4").write_bytes(b"fragment")
    elif case == "ambiguous":
        for directory in ("first", "second"):
            folder = videos / directory
            folder.mkdir()
            (folder / "RequestedScene.mp4").write_bytes(directory.encode())
    result = _select(tmp_path)
    assert result.returncode == 2, result.stderr
    assert "Expected one final MP4" in result.stderr
    assert not (tmp_path / "test-job.mp4").exists()


def test_worker_rejects_unproven_scene_output(tmp_path: Path) -> None:
    for case in ("missing", "other-scene", "partial-only", "ambiguous"):
        _rejection_case(tmp_path / case, case)


def test_worker_copies_exact_scene_and_preserves_other_outputs(tmp_path: Path) -> None:
    folder = tmp_path / "out" / "videos" / "job source with spaces" / "720p30"
    folder.mkdir(parents=True)
    exact = folder / "RequestedScene.mp4"
    exact.write_bytes(b"exact output")
    other = folder / "OtherScene.mp4"
    other.write_bytes(b"unrelated larger output" * 1000)
    result = _select(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "test-job.mp4").read_bytes() == exact.read_bytes()
    assert other.read_bytes() == b"unrelated larger output" * 1000


def test_bundled_worker_matches_shipped_workflow() -> None:
    shipped = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "render.yml"
    assert shipped.read_text(encoding="utf-8").strip() == RENDER_WORKFLOW_YAML.strip()
