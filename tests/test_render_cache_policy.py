"""Pixel-affecting policy changes must invalidate every derived media cache."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from aetherlab.core.render_profile import adapt_profile_for_cost, get_effective_profile


@pytest.fixture(autouse=True)
def owned_render_environment(monkeypatch):
    import os
    for key in tuple(os.environ):
        if key.startswith(("AETHERLAB_", "MANIM_", "RENDER_")):
            monkeypatch.delenv(key, raising=False)


def settings(adaptive):
    return SimpleNamespace(render_preset="cinematic", adaptive_quality=adaptive,
                           render_mode="cloud", narration_enabled=False)


def test_adaptive_policy_that_changes_actual_fps_has_distinct_cache_identity():
    fixed = get_effective_profile(settings(False), quality="h")
    adaptive = get_effective_profile(settings(True), quality="h")
    assert adapt_profile_for_cost(fixed, 4.0)[0].fps == 60
    assert adapt_profile_for_cost(adaptive, 4.0)[0].fps == 30
    assert fixed.identity_key() != adaptive.identity_key()


def test_voiceover_cache_identity_separates_adaptive_policy():
    from aetherlab.services.voiceover import render_profile_key
    assert render_profile_key(settings(False), "h") != render_profile_key(settings(True), "h")


def test_lesson_chapter_cache_identity_separates_adaptive_policy():
    from aetherlab.core.models import LessonChapter, LessonPlan
    from aetherlab.services.lesson_pipeline import _chapter_key
    chapter = LessonChapter.from_json({"title": "Acceleration", "content": "A changing speed"})
    plan = LessonPlan.from_json({"topic": "Acceleration", "language": "kk", "chapters": []})
    assert _chapter_key(chapter, plan, settings(False), "h") != _chapter_key(chapter, plan, settings(True), "h")


def test_segment_manifest_fingerprint_separates_adaptive_policy():
    from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
    from aetherlab.services.segmented_pipeline import _request_fingerprint
    request = ProblemRequest("Acceleration", duration_target_s=120)
    solver = SolverResult("Changing speed", [], [], {}, "owned")
    rag = RagResult([], [], "owned")
    assert _request_fingerprint(request, solver, rag, settings(False), "h") != _request_fingerprint(request, solver, rag, settings(True), "h")


def test_machine_resource_limits_do_not_invalidate_pixel_identity():
    from aetherlab.core.render_profile import ResourceLimits
    profile = get_effective_profile(settings(False), quality="h")
    limited = replace(profile, resource_limits=ResourceLimits(max_local_renders=1))
    assert limited.identity_key() == profile.identity_key()


def test_inherited_and_explicit_equivalent_policy_reuse_identity():
    inherited = get_effective_profile(settings(None), quality="h")
    explicit = get_effective_profile(settings(False), quality="h")
    assert inherited.identity_key() == explicit.identity_key()
