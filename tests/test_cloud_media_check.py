"""Downloaded-MP4 media gate: container, streams, duration, resolution (Stage B)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aetherlab.core.proc import subprocess_kwargs
from aetherlab.services.render_backend import (
    CloudRenderBackend,
    probe_mp4,
    validate_mp4,
)


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _make_mp4(path: Path, size: str, seconds: int = 1) -> Path:
    subprocess.run(
        [
            _ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={size}:rate=30:duration={seconds}",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        **subprocess_kwargs(),
    )
    return path


def test_validate_mp4_rejects_non_container(tmp_path: Path) -> None:
    bad = tmp_path / "note.mp4"
    bad.write_bytes(b"This is not a video file, only a note.")
    assert not validate_mp4(bad)
    missing = tmp_path / "absent.mp4"
    assert not validate_mp4(missing)


def test_container_gate_memory_does_not_scale_with_video_size(tmp_path: Path) -> None:
    import tracemalloc

    # Sparse file models a long download without encoding or storing 128 MiB of
    # frames. This checks memory use, not full decodability (a separate gate).
    large = tmp_path / "large.mp4"
    with large.open("wb") as output:
        output.write(b"\x00\x00\x00\x20ftypmp42")
        output.seek(128 * 1024 * 1024)
        output.write(b"\x00")
    tracemalloc.start()
    try:
        assert validate_mp4(large)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 1024 * 1024, f"Header gate allocated {peak} bytes for a sparse video"


def test_profile_matches_expected_quality_dims(tmp_path: Path) -> None:
    pytest.importorskip("av")
    clip = _make_mp4(tmp_path / "standard.mp4", "1280x720")
    assert validate_mp4(clip)
    facts = probe_mp4(clip)
    assert facts is not None
    assert facts["video_streams"] >= 1
    assert facts["duration_s"] > 0
    assert (facts["width"], facts["height"]) == (1280, 720)
    ok, reason = CloudRenderBackend._profile_matches(clip, "m")
    assert ok, reason


def test_profile_rejects_wrong_resolution(tmp_path: Path) -> None:
    pytest.importorskip("av")
    draft = _make_mp4(tmp_path / "draft.mp4", "854x480")
    ok, _ = CloudRenderBackend._profile_matches(draft, "l")
    assert ok
    ok, reason = CloudRenderBackend._profile_matches(draft, "m")
    assert not ok
    assert "854x480" in reason and "1280x720" in reason


def test_profile_rejects_undecodable_with_ftyp(tmp_path: Path) -> None:
    pytest.importorskip("av")
    # Valid magic but truncated payload: must not ship as a finished render.
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"\x00\x00\x00\x20ftypmp42" + b"\x00" * 512)
    assert validate_mp4(broken)
    ok, reason = CloudRenderBackend._profile_matches(broken, "m")
    assert not ok
    assert reason


def test_profile_refuses_unverified_video_when_decoder_is_missing(tmp_path: Path, monkeypatch) -> None:
    clip = tmp_path / "header-only.mp4"
    clip.write_bytes(b"\x00\x00\x00\x20ftypmp42" + b"\x00" * 512)
    monkeypatch.setitem(sys.modules, "av", None)
    assert validate_mp4(clip)
    ok, reason = CloudRenderBackend._profile_matches(clip, "m")
    assert not ok, "A container signature cannot certify cloud video playback"
    assert "PyAV" in reason


def test_profile_rejects_metadata_without_a_decodable_frame(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    stream = SimpleNamespace(duration=30, time_base=1 / 30, width=1280, height=720)

    class MetadataOnly:
        streams = SimpleNamespace(video=[stream])

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def decode(self, **_kwargs):
            return iter(())

    monkeypatch.setitem(sys.modules, "av", SimpleNamespace(open=lambda *_args: MetadataOnly()))
    ok, reason = CloudRenderBackend._profile_matches(tmp_path / "metadata-only.mp4", "m")
    assert not ok
    assert "decodable" in reason
