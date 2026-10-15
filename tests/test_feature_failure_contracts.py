"""Failure descriptions must match the actual non-video feature boundary."""
import build_feature_tracker as tracker


def test_student_formula_story_describes_math_fallback_and_early_finish():
    row = dict(zip(tracker.HEADERS, next(item for item in tracker.FEATURES if item[0] == "F233")))
    assert "missing/corrupt video" not in row["Failure-mode expectation"]
    assert "render_math" in row["Expected behaviour"]
    assert "readable" in row["Failure-mode expectation"]
    assert "early" in row["Story"].lower()
    assert "unattempted" in row["Expected behaviour"]


def test_nonvideo_failure_stories_match_their_implementations():
    for feature, anchor, fallbacks in (
        ("F190", "build_research_pdf", ("matplotlib", "tex-only")),
        ("F220", "write_study_document", ("deterministic", "tex-only")),
        ("F247", "set_language", ("Kazakh", "source")),
    ):
        row = dict(zip(tracker.HEADERS, next(item for item in tracker.FEATURES if item[0] == feature)))
        assert "missing/corrupt video" not in row["Failure-mode expectation"], feature
        assert anchor in row["Expected behaviour"]
        assert all(word in row["Failure-mode expectation"] for word in fallbacks)


def test_settings_timeout_description_matches_actual_runtime_bounds(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings
    from aetherlab.services.model_policy import effective_llm_timeout

    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "0")
    for raw, expected in (("1", 5.0), ("1800", 1800.0), ("99999", 1800.0)):
        monkeypatch.setenv("AETHERLAB_LLM_TIMEOUT", raw)
        settings = load_settings()
        assert settings.llm_timeout_seconds == expected
        assert effective_llm_timeout(settings) == expected
    row = next(item for item in tracker.FEATURES if item[0] == "F06")
    assert "5–1800s" in row[4]
    assert "5–900s" not in tracker.DEFECTS["F06"]
