"""Synthetic policy fixtures here never become live-cloud acceptance records."""
import hashlib
import json

import pytest

import build_feature_tracker as tracker


@pytest.fixture
def recorded_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "ROOT", tmp_path)
    output = tmp_path / "owned.mp4"
    output.write_bytes(b"synthetic policy fixture, not a decoded/live render")
    data = {"status": "PASS", "exit_code": 0, "workflow_version": "8", "head_before": "owned",
        "head_after": "owned", "completed_at": "owned fixture timestamp", "changed_during_run": [],
        "dispatch_count": 1, "first_status": "rendered", "cached_status": "rendered",
        "output": str(output), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "media": {"width": 960, "height": 540, "fps": 24, "frame_count": 48,
                  "all_frames_decoded": True, "moving_object": True}}
    path = tmp_path / "probe.json"
    def write():
        raw = json.dumps(data).encode()
        path.write_bytes(raw)
        return {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest()}
    return data, path, output, write


def test_valid_record_is_scoped_to_historical_technical_probe(recorded_probe):
    _, _, _, write = recorded_probe
    scope = tracker._recorded_profile_evidence_scope(write())
    assert "recorded real v8 technical scene" in scope
    assert "no educational/audio/native-player acceptance" in scope


@pytest.mark.parametrize("damage", ["evidence-bytes", "output-bytes", "failed", "boolean-exit",
    "changed-source", "changed-head", "missing-completion", "wrong-fps", "extra-dispatch", "undecoded"])
def test_damaged_or_incomplete_record_never_advertises_live_scope(recorded_probe, damage):
    data, path, output, write = recorded_probe
    if damage == "failed":
        data["status"] = "FAIL"
    elif damage == "boolean-exit":
        data["exit_code"] = False
    elif damage == "changed-source":
        data["changed_during_run"] = ["owned.py"]
    elif damage == "changed-head":
        data["head_after"] = "other"
    elif damage == "missing-completion":
        data["completed_at"] = ""
    elif damage == "wrong-fps":
        data["media"]["fps"] = 30
    elif damage == "extra-dispatch":
        data["dispatch_count"] = 2
    elif damage == "undecoded":
        data["media"]["all_frames_decoded"] = False
    pointer = write()
    if damage == "evidence-bytes":
        path.write_bytes(b"{}")
    elif damage == "output-bytes":
        output.write_bytes(b"other")
    assert tracker._recorded_profile_evidence_scope(pointer) == ""


def test_external_and_missing_evidence_is_not_followed(recorded_probe):
    assert tracker._recorded_profile_evidence_scope({"path": "../outside.json", "sha256": "owned"}) == ""
    assert tracker._recorded_profile_evidence_scope(None) == ""
