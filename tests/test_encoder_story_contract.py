"""The encoder command story must describe its actual configuration boundary."""
import build_feature_tracker as tracker


def test_encoder_story_uses_code_specific_preconditions_and_failure_modes():
    row = dict(zip(tracker.HEADERS, next(item for item in tracker.FEATURES if item[0] == "F253")))
    assert "AI-backed generation" not in row["Story"]
    assert "quality feedback must be visible" not in row["Story"]
    assert "can retry" not in row["Failure-mode expectation"]
    assert "malformed" in row["Failure-mode expectation"]
    assert "clamp" in row["Failure-mode expectation"]
