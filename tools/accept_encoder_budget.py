"""Full local encoder-budget contract: arguments, real queue and unchanged video."""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_CASES = {
    "default": (None, 4), "empty": ("", 4), "whitespace": ("  ", 4),
    "malformed": ("bogus", 4), "decimal": ("2.5", 4), "negative": ("-2", 1),
    "zero": ("0", 1), "minimum": ("1", 1), "trimmed": (" 2 ", 2),
    "maximum": ("8", 8), "clamped": ("99", 8),
}
REAL_CASES = {"real-default": (None, 4), "real-serial": ("1", 1),
              "real-clamped": ("99", 8), "real-invalid": ("oops", 4)}
CASE_REQUIREMENTS = {
    **{name: {"parsed_budget", "one_queue_argument"} for name in INPUT_CASES},
    "profile": {"quality", "fps", "canvas", "seed", "scene", "media", "cache_disabled"},
    "partial": {"cache_enabled", "partial_range", "queue_argument"},
    "opengl": {"renderer", "movie_output", "queue_argument"},
    **{name: {"actual_cli", "configured_budget", "queue_bound", "queue_drained",
              "complete_video", "unchanged_frame_sequence"} for name in REAL_CASES},
}
FEATURE_SOURCES = {
    "aetherlab/services/manim_runtime.py", "aetherlab/core/render_profile.py", "aetherlab/core/proc.py",
    "tools/accept_encoder_budget.py", "tools/feature_acceptance.py", "tests/test_encoder_budget_contract.py",
}
DETAIL = ("Complete local encoder-budget contract: 11 input classes and profile/cache/renderer arguments; "
          "four real CLI renders observe limits 1/4/8/fallback-4, drained queues and identical 27-frame video; runtime bound")

CHILD_SOURCE = '''from manim import *
from manim.scene.scene_file_writer import SceneFileWriter
import atexit, json
from pathlib import Path
config.preview = False
config.show_in_file_browser = False
config.write_to_movie = True
config.save_last_frame = False
config.format = "mp4"
config.transparent = False
config.background_color = BLACK
config.frame_height = 8
config.frame_width = 32 / 3
_observations = []
_writer = None
_original_close = SceneFileWriter.close_partial_movie_stream
def _observed_close(self):
    global _writer
    _writer = self
    jobs = list(self._inflight_encode_jobs)
    if self._current_encode_job is not None:
        jobs.append(self._current_encode_job)
    item = {"configured": int(config.max_inflight_encoders), "pending_before": len(jobs),
            "live_before": sum(job.thread.is_alive() for job in jobs)}
    _original_close(self)
    item["pending_after"] = len(self._inflight_encode_jobs)
    _observations.append(item)
SceneFileWriter.close_partial_movie_stream = _observed_close
def _report():
    Path(TRACE_PATH).write_text(json.dumps({"observations": _observations,
        "drained": _writer is not None and not _writer._inflight_encode_jobs and _writer._current_encode_job is None}), encoding="utf-8")
atexit.register(_report)
class OwnedEncoderBudget(Scene):
    def construct(self):
        dot = Dot(radius=0.2, color=BLUE).shift(LEFT * 2)
        self.add(dot)
        for _ in range(8):
            self.play(dot.animate.shift(RIGHT * 0.5), run_time=0.125, rate_func=linear)
        self.wait(0.125)
'''


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def runtime_fingerprint() -> dict:
    import av
    spec = importlib.util.find_spec("manim")
    if spec is None or spec.origin is None:
        raise RuntimeError("Manim runtime unavailable")
    base = Path(spec.origin).parent
    return {"python": platform.python_version(), "manim": importlib.metadata.version("manim"),
        "av": importlib.metadata.version("av"), "numpy": importlib.metadata.version("numpy"),
        "codec_versions": {key: list(value) for key, value in av.library_versions.items()},
        "source_sha256": {name: digest(base / name) for name in
            ("scene/scene_file_writer.py", "cli/render/commands.py", "cli/render/render_options.py", "_config/utils.py")}}


@contextmanager
def budget(value):
    key = "AETHERLAB_MAX_INFLIGHT_ENCODERS"
    previous = os.environ.get(key)
    try:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def command_for(folder: Path, raw, **overrides) -> list[str]:
    from aetherlab.services.manim_runtime import _manim_render_command
    args = dict(quality="l", fps=24, seed=7, width=320, height=240, renderer="cairo",
                media_dir=folder / "media", scene_file=folder / "scene.py", class_name="OwnedEncoderBudget")
    args.update(overrides)
    with budget(raw):
        return _manim_render_command([sys.executable, "-m", "manim"], **args)


def option(command, name):
    assert command.count(name) == 1, f"Missing/duplicate option {name}"
    return command[command.index(name) + 1]


def command_case(name: str, folder: Path) -> dict:
    if name in INPUT_CASES:
        raw, expected = INPUT_CASES[name]
        command = command_for(folder, raw)
        assert option(command, "--max-inflight-encoders") == str(expected)
    elif name == "profile":
        command = command_for(folder, "2", quality="p", fps=48, width=960, height=540)
        assert "-qp" in command and option(command, "--fps") == "48"
        assert option(command, "-r") == "960,540" and option(command, "--seed") == "7"
        assert command[-2:] == [str(folder / "scene.py"), "OwnedEncoderBudget"]
        assert option(command, "--media_dir") == str(folder / "media") and "--disable_caching" in command
    elif name == "partial":
        command = command_for(folder, "8", cache_enabled=True, partial_animation_range=(1, 3))
        assert option(command, "-n") == "1,3" and "--disable_caching" not in command
        assert option(command, "--max-inflight-encoders") == "8"
    elif name == "opengl":
        command = command_for(folder, "1", renderer="opengl")
        assert option(command, "--renderer") == "opengl" and "--write_to_movie" in command
        assert option(command, "--max-inflight-encoders") == "1"
    else:
        raise ValueError(name)
    return {"id": name, "status": "PASS", "covers": sorted(CASE_REQUIREMENTS[name]), "command": command}


def media_summary(path: Path) -> dict:
    import av
    import numpy as np
    hashes, centers = [], []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        assert (stream.width, stream.height, float(stream.average_rate)) == (320, 240, 24)
        for frame in container.decode(video=0):
            pixels = frame.to_ndarray(format="rgb24")
            hashes.append(hashlib.sha256(pixels.tobytes()).hexdigest())
            signed = pixels.astype(np.int16)
            _, xs = np.where((signed[:, :, 2] > signed[:, :, 0] + 40) & (signed[:, :, 2] > 100))
            assert len(xs) > 5, "Control object absent from a decoded frame"
            centers.append(float(xs.mean()))
    assert len(hashes) == 27 and centers[-1] - centers[0] > 60
    assert all(b >= a - 1 for a, b in zip(centers, centers[1:]))
    return {"width": 320, "height": 240, "fps": 24, "frames": 27, "frame_sha256": hashes}


def _bind(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}


def render_case(name: str, folder: Path) -> tuple[dict, dict]:
    from aetherlab.core.proc import subprocess_kwargs
    raw, expected = REAL_CASES[name]
    folder.mkdir(parents=True)
    scene, trace, log = folder / "scene.py", folder / "queue.json", folder / "process.log"
    scene.write_text("TRACE_PATH = " + repr(str(trace)) + "\n" + CHILD_SOURCE, encoding="utf-8")
    command = command_for(folder, raw)
    assert all(flag not in command for flag in ("-p", "--preview", "--show_in_file_browser")), "Visible output is not allowed in this acceptance run"
    environment = {key: value for key, value in os.environ.items() if not key.startswith(
        ("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_"))}
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "VISION_MODEL"):
        environment.pop(key, None)
    environment.update({"QT_QPA_PLATFORM": "offscreen", "PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE": "0",
        "PHYSLAB_REQUIRE_NATIVE_QT": "0", "AETHERLAB_DISABLE_LEGACY_ENV": "1", "AETHERLAB_QWEN_AUTOLOAD": "0",
        "AETHERLAB_DATA_DIR": str(folder / "data"), "TEMP": str(folder), "TMP": str(folder)})
    result = subprocess.run(command, cwd=folder, env=environment, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=90, **subprocess_kwargs())
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, f"{name}: Manim CLI exit {result.returncode}; {log}"
    observed = json.loads(trace.read_text(encoding="utf-8"))
    validate_queue(observed, expected)
    paths = [path for path in (folder / "media").rglob("OwnedEncoderBudget.mp4") if "partial_movie_files" not in path.parts]
    assert len(paths) == 1, "Ambiguous/missing encoder output"
    record = {"input": raw, "expected": expected, "command": command, "exit_code": result.returncode,
        "files": {role: _bind(path) for role, path in (("scene", scene), ("trace", trace), ("log", log), ("video", paths[0]))},
        "media": media_summary(paths[0])}
    check = {"id": name, "status": "PASS", "covers": sorted(CASE_REQUIREMENTS[name]), "exit_code": result.returncode}
    return check, record


def validate_queue(observed: dict, expected: int) -> None:
    values = observed["observations"]
    assert len(values) == 9 and observed["drained"] is True
    assert all(type(value[key]) is int for value in values for key in
               ("configured", "pending_before", "live_before", "pending_after"))
    assert all(value["configured"] == expected and 1 <= value["pending_before"] <= expected
        and 0 <= value["live_before"] <= expected and 0 <= value["pending_after"] < expected for value in values)
    assert max(value["pending_before"] for value in values) == expected


def verify_execution(root: Path, evidence: dict) -> tuple[bool, str]:
    try:
        assert evidence["runtime_fingerprint"] == runtime_fingerprint(), "Encoder runtime changed"
        records = evidence["execution_records"]
        assert set(records) == set(REAL_CASES), "Real-render matrix incomplete"
        first_frames, outputs = None, set()
        for name, (raw, expected) in REAL_CASES.items():
            record = records[name]
            assert record["input"] == raw and type(record["expected"]) is int and record["expected"] == expected
            assert type(record["exit_code"]) is int and record["exit_code"] == 0
            paths = {}
            assert set(record["files"]) == {"scene", "trace", "log", "video"}
            for role, pointer in record["files"].items():
                assert not Path(pointer["path"]).is_absolute()
                path = (root / pointer["path"]).resolve()
                assert path.is_relative_to((root / "tmp").resolve()), "Encoder file outside owned temporary area"
                assert digest(path) == pointer["sha256"], "Encoder execution file changed"
                paths[role] = path
            expected_source = "TRACE_PATH = " + repr(str(paths["trace"])) + "\n" + CHILD_SOURCE
            assert paths["scene"].read_text(encoding="utf-8") == expected_source, "Encoder scene/instrumentation changed"
            validate_queue(json.loads(paths["trace"].read_text(encoding="utf-8")), expected)
            assert paths["video"] not in outputs, "Different runs share an output path"
            outputs.add(paths["video"])
            command = record["command"]
            assert all(flag not in command for flag in ("-p", "--preview", "--show_in_file_browser"))
            assert option(command, "--max-inflight-encoders") == str(expected)
            assert command[-2:] == [str(paths["scene"]), "OwnedEncoderBudget"]
            assert option(command, "--renderer") == "cairo" and "--disable_caching" in command
            assert option(command, "--fps") == "24" and option(command, "-r") == "320,240" and "-ql" in command
            assert paths["video"].is_relative_to(Path(option(command, "--media_dir")).resolve())
            media = media_summary(paths["video"])
            assert media == record["media"], "Decoded media differs from execution report"
            if first_frames is None:
                first_frames = media["frame_sha256"]
            assert media["frame_sha256"] == first_frames, "Encoder setting changed frame order/content"
    except Exception as exc:
        return False, f"Encoder acceptance execution unavailable/invalid: {type(exc).__name__}: {exc}"
    return True, DETAIL


def run_acceptance(output: Path, row: dict) -> dict:
    from tools.feature_acceptance import contract_hash
    assert row["ID"] == "F253"
    assert output.resolve().is_relative_to((ROOT / "tmp").resolve()), "Acceptance output must stay in the owned temporary area"
    before = {name: digest(ROOT / name) for name in FEATURE_SOURCES}
    runtime = runtime_fingerprint()
    folder = ROOT / "tmp" / ("encoder-accept-" + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    checks = [command_case(name, folder / name) for name in CASE_REQUIREMENTS if name not in REAL_CASES]
    records = {}
    for name in REAL_CASES:
        check, record = render_case(name, folder / name)
        checks.append(check)
        records[name] = record
    after = {name: digest(ROOT / name) for name in FEATURE_SOURCES}
    assert before == after and runtime == runtime_fingerprint(), "Encoder acceptance inputs changed during execution"
    evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": "F253", "status": "PASS", "exit_code": 0,
        "completed_at": datetime.now(UTC).isoformat(), "contract_sha256": contract_hash(row),
        "source_sha256": after, "checks": checks, "runtime_fingerprint": runtime,
        "execution_records": records, "scope": DETAIL}
    valid, detail = verify_execution(ROOT, evidence)
    assert valid, detail
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return _bind(output)
