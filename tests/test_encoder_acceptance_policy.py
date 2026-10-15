"""Synthetic schema/policy fixtures only; never production acceptance evidence."""
import copy
import hashlib
import json

import pytest

from tools import accept_encoder_budget as encoder
from tools.feature_acceptance import CONTRACT_COLUMNS, contract_hash, verify_acceptance


@pytest.fixture
def policy_record(tmp_path, monkeypatch):
    row = {key: "F253" if key == "ID" else "Synthetic policy contract" for key in CONTRACT_COLUMNS}
    runtime = {"synthetic-policy-runtime": True}
    monkeypatch.setattr(encoder, "runtime_fingerprint", lambda: runtime)
    media = {"width": 320, "height": 240, "fps": 24, "frames": 27,
             "frame_sha256": [f"synthetic-frame-{i}" for i in range(27)]}
    monkeypatch.setattr(encoder, "media_summary", lambda _: copy.deepcopy(media))
    def bind(path):
        return {"path": path.relative_to(tmp_path).as_posix(), "sha256": encoder.digest(path)}
    sources = {}
    for name in encoder.FEATURE_SOURCES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source for policy, not an app execution", encoding="utf-8")
        sources[name] = encoder.digest(path)
    records = {}
    for name, (raw, expected) in encoder.REAL_CASES.items():
        folder = tmp_path / "tmp" / name
        (folder / "media").mkdir(parents=True)
        trace, scene, log, video = folder / "queue.json", folder / "scene.py", folder / "process.log", folder / "media" / "OwnedEncoderBudget.mp4"
        scene.write_text("TRACE_PATH = " + repr(str(trace)) + "\n" + encoder.CHILD_SOURCE, encoding="utf-8")
        observed = {"drained": True, "observations": [
            {"configured": expected, "pending_before": min(i, expected), "live_before": min(i, expected),
             "pending_after": min(i, expected - 1)} for i in range(1, 10)]}
        trace.write_text(json.dumps(observed), encoding="utf-8")
        log.write_text("synthetic policy log; no subprocess was run", encoding="utf-8")
        video.write_bytes(b"synthetic policy video, deliberately not decodable")
        records[name] = {"input": raw, "expected": expected, "exit_code": 0,
            "command": encoder.command_for(folder, raw),
            "files": {role: bind(path) for role, path in (("scene", scene), ("trace", trace), ("log", log), ("video", video))},
            "media": copy.deepcopy(media)}
    evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": "F253", "status": "PASS", "exit_code": 0,
        "completed_at": "2026-10-15T00:00:00+00:00", "contract_sha256": contract_hash(row),
        "source_sha256": sources, "runtime_fingerprint": runtime, "execution_records": records,
        "checks": [{"id": name, "status": "PASS", "covers": sorted(covers)} for name, covers in encoder.CASE_REQUIREMENTS.items()]}
    def save():
        path = tmp_path / "synthetic-policy-evidence.json"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        return {"status": "PASS", "phase4_status": "PASS", "behaviour_acceptance_evidence": bind(path)}
    return tmp_path, row, evidence, save


def test_complete_encoder_schema_requires_bound_execution_records(policy_record):
    root, row, _, save = policy_record
    assert verify_acceptance(root, row, save())[0]


@pytest.mark.parametrize("damage", ["missing-case", "missing-condition", "stale-source", "runtime", "missing-record",
    "video-bytes", "missing-log", "queue-cap", "live-cap", "undrained", "boolean-limit", "wrong-input",
    "wrong-frames", "changed-frames", "preview-command", "outside-path", "absolute-path", "reused-output",
    "scene-bytes", "boolean-exit"])
def test_encoder_acceptance_rejects_incomplete_or_changed_execution(policy_record, monkeypatch, damage):
    root, row, evidence, save = policy_record
    record = evidence["execution_records"]["real-serial"]
    def rebind(role):
        pointer = record["files"][role]
        pointer["sha256"] = encoder.digest(root / pointer["path"])
    if damage == "missing-case":
        evidence["checks"].pop()
    elif damage == "missing-condition":
        evidence["checks"][0]["covers"] = []
    elif damage == "stale-source":
        (root / "aetherlab/services/manim_runtime.py").write_text("changed", encoding="utf-8")
    elif damage == "runtime":
        monkeypatch.setattr(encoder, "runtime_fingerprint", lambda: {"different": True})
    elif damage == "missing-record":
        evidence["execution_records"].pop("real-serial")
    elif damage == "video-bytes":
        (root / record["files"]["video"]["path"]).write_bytes(b"changed video")
    elif damage == "missing-log":
        (root / record["files"]["log"]["path"]).unlink()
    elif damage in {"queue-cap", "live-cap", "undrained", "boolean-limit"}:
        path = root / record["files"]["trace"]["path"]
        trace = json.loads(path.read_text(encoding="utf-8"))
        if damage == "queue-cap": trace["observations"][0]["pending_before"] = 2
        elif damage == "live-cap": trace["observations"][0]["live_before"] = 2
        elif damage == "undrained": trace["drained"] = False
        else: trace["observations"][0]["configured"] = True
        path.write_text(json.dumps(trace), encoding="utf-8")
        rebind("trace")
    elif damage == "wrong-input":
        record["input"] = "8"
    elif damage == "wrong-frames":
        record["media"]["frames"] = 26
    elif damage == "changed-frames":
        record["media"]["frame_sha256"][1] = "different"
        media = copy.deepcopy(evidence["execution_records"]["real-default"]["media"])
        changed = copy.deepcopy(record["media"])
        monkeypatch.setattr(encoder, "media_summary", lambda path: changed if "real-serial" in path.parts else media)
    elif damage == "preview-command":
        record["command"].insert(3, "--preview")
    elif damage == "outside-path":
        record["files"]["video"]["path"] = "../outside.mp4"
    elif damage == "absolute-path":
        record["files"]["video"]["path"] = str(root / record["files"]["video"]["path"])
    elif damage == "reused-output":
        record["files"]["video"] = copy.deepcopy(evidence["execution_records"]["real-default"]["files"]["video"])
    elif damage == "scene-bytes":
        (root / record["files"]["scene"]["path"]).write_text("changed scene", encoding="utf-8")
        rebind("scene")
    elif damage == "boolean-exit":
        record["exit_code"] = False
    assert not verify_acceptance(root, row, save())[0]


def test_budget_context_restores_environment_after_error(monkeypatch):
    import os
    monkeypatch.setenv("AETHERLAB_MAX_INFLIGHT_ENCODERS", "7")
    with pytest.raises(RuntimeError):
        with encoder.budget("1"):
            assert os.environ["AETHERLAB_MAX_INFLIGHT_ENCODERS"] == "1"
            raise RuntimeError("owned failure")
    assert os.environ["AETHERLAB_MAX_INFLIGHT_ENCODERS"] == "7"


def test_visible_render_flags_are_rejected_before_process_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(encoder, "command_for", lambda *a, **k: ["python", "render", "--preview"])
    def forbidden(*args, **kwargs):
        pytest.fail("Visible render command reached subprocess launch")
    monkeypatch.setattr(encoder.subprocess, "run", forbidden)
    with pytest.raises(AssertionError, match="Visible output"):
        encoder.render_case("real-default", tmp_path / "case")


def test_acceptance_rejects_output_outside_its_temporary_area(tmp_path, monkeypatch):
    monkeypatch.setattr(encoder, "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="temporary area"):
        encoder.run_acceptance(tmp_path / "outside.json", {"ID": "F253"})
    assert not (tmp_path / "outside.json").exists()
