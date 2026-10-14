"""A damaged package must fail honestly and recover on the next request."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json

import pytest


def _package(tmp_path, monkeypatch):
    from aetherlab.services import ent_lesson_catalog as catalog

    payload = copy.deepcopy(catalog._load_5min_content())
    for language in ("kk", "ru", "en"):
        folder = tmp_path / language
        folder.mkdir()
        for kind in ("video", "srt", "pdf"):
            data = f"owned {language} {kind} content fixture".encode()
            (folder / kind).write_bytes(data)
            payload["media"][language][kind] = {"path": f"{language}/{kind}", "sha256": hashlib.sha256(data).hexdigest()}
    path = tmp_path / "lesson.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(catalog, "ACCELERATED_MOTION_5MIN_JSON", path)
    monkeypatch.setattr(catalog, "_5MIN_CACHE", None, raising=False)
    return catalog, path, payload


@pytest.mark.parametrize("failure", ("missing", "bad_json", "incomplete"))
def test_package_failure_returns_localized_error_and_recovers(failure, tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings
    from aetherlab.services import lesson_pipeline as pipeline

    catalog, path, payload = _package(tmp_path, monkeypatch)
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path / "data"))
    calls = []

    async def unexpected_planning(*args, **kwargs):
        calls.append(args)
        raise AssertionError("A missing explicit package must not start AI generation")

    monkeypatch.setattr(pipeline, "plan_lesson", unexpected_planning)
    if failure == "missing":
        path.unlink()
    elif failure == "bad_json":
        path.write_text("{broken", encoding="utf-8")
    else:
        path.write_text(json.dumps({"route_id": catalog.ACCELERATED_MOTION_5MIN_ID}), encoding="utf-8")
    service = pipeline.LessonPipeline(load_settings())
    for language in ("kk", "ru", "en"):
        bundle = asyncio.run(service.run(catalog.ACCELERATED_MOTION_5MIN_ID, language=language))
        assert bundle.status == "package_error"
        assert bundle.plan.language == language
        assert not bundle.video_path and not bundle.plan.questions
        assert bundle.plan.model_name == "localized-prebuilt-error"
        assert {"kk": "қалпына", "ru": "Восстановите", "en": "Restore"}[language] in bundle.package_error_message
        assert not calls
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert asyncio.run(service.run(catalog.ACCELERATED_MOTION_5MIN_ID, language="kk")).status == "assembled"


def test_package_path_changes_do_not_reuse_other_package_data(tmp_path, monkeypatch):
    catalog, path, payload = _package(tmp_path, monkeypatch)
    old = catalog._load_5min_content()
    payload["meta"]["ru"]["title"] = "Owned package title"
    second = tmp_path / "second-package.json"
    second.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(catalog, "ACCELERATED_MOTION_5MIN_JSON", second)
    assert catalog._load_5min_content()["meta"]["ru"]["title"] == "Owned package title"
    assert old["meta"]["ru"]["title"] != "Owned package title"


def test_manifest_refresh_and_readers_cannot_pollute_other_requests(tmp_path, monkeypatch):
    catalog, path, payload = _package(tmp_path, monkeypatch)
    first = catalog._load_5min_content()
    first["meta"]["kk"]["title"] = "Discarded reader mutation"
    assert catalog._load_5min_content()["meta"]["kk"]["title"] == payload["meta"]["kk"]["title"]
    payload["meta"]["kk"]["title"] = "Updated title"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert catalog._load_5min_content()["meta"]["kk"]["title"] == "Updated title"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        catalog._load_5min_content()


def test_prebuilt_snapshot_hash_survives_plan_roundtrip(tmp_path, monkeypatch):
    from aetherlab.core.models import LessonPlan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle

    catalog, path, payload = _package(tmp_path, monkeypatch)
    plan = catalog.accelerated_motion_5min_plan("en")
    restored = LessonPlan.from_json(plan.to_json())
    assert getattr(restored, "prebuilt_content_hash", "") == plan.prebuilt_content_hash
    payload["meta"]["en"]["title"] = "Changed after history save"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert _prebuilt_5min_bundle(restored).status == "error"


def test_unreadable_manifest_does_not_use_warm_content(tmp_path, monkeypatch):
    from pathlib import Path

    catalog, path, payload = _package(tmp_path, monkeypatch)
    catalog._load_5min_content()
    before = path.read_bytes()
    original = Path.read_text

    def denied(target, *args, **kwargs):
        if target == path:
            raise PermissionError("Isolated manifest is unreadable")
        return original(target, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", denied)
        with pytest.raises(catalog.PrebuiltLessonContentError) as error:
            catalog._load_5min_content()
        assert error.value.code == "unreadable_manifest"
    assert path.read_bytes() == before
    assert catalog._load_5min_content()["route_id"] == catalog.ACCELERATED_MOTION_5MIN_ID


def test_package_error_clears_video_without_touching_course_progress():
    from types import SimpleNamespace

    from aetherlab.ui.main_window import MainWindow

    videos, refreshed, notices = [], [], []
    shell = SimpleNamespace(
        command_bar=SimpleNamespace(set_busy=lambda value: None),
        stepper=SimpleNamespace(set_cancellable=lambda value: None),
        lesson_view=SimpleNamespace(set_lesson=lambda value: None, set_video=videos.append, set_audio_enabled=lambda value: None),
        _restore_pending_lesson_answers=lambda: None,
        _refresh_course_summary=refreshed.append,
        _workspace=SimpleNamespace(setCurrentIndex=lambda value: None),
        statusBar=lambda: SimpleNamespace(showMessage=notices.append),
        toast=SimpleNamespace(show_message=lambda kind, message: notices.append(message)),
    )
    bundle = SimpleNamespace(status="package_error", package_error_message="Restore the prepared package")
    MainWindow.on_lesson_ready(shell, bundle)
    assert videos == [""] and not refreshed
    assert notices == [bundle.package_error_message] * 2


def test_plan_and_media_must_use_one_content_snapshot(tmp_path, monkeypatch):
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle

    catalog, path, payload = _package(tmp_path, monkeypatch)
    plan = catalog.accelerated_motion_5min_plan("ru")
    assert _prebuilt_5min_bundle(plan).status == "assembled"
    payload["meta"]["ru"]["title"] = "Different version while loading"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    bundle = _prebuilt_5min_bundle(plan)
    assert bundle.status == "error"
    assert bundle.invalid_media["manifest"] == "content_changed"
    assert not bundle.video_path and bundle.plan.title == plan.title
    fresh = catalog.accelerated_motion_5min_plan("ru")
    assert _prebuilt_5min_bundle(fresh).status == "assembled"


@pytest.mark.parametrize("damage", ("root", "version", "offsets", "duration", "chapter_count", "question_key", "media_entry", "kind", "chapter_order", "question_count", "language_key"))
def test_manifest_contract_rejects_malformed_input(damage, tmp_path, monkeypatch):
    catalog, path, payload = _package(tmp_path, monkeypatch)
    if damage == "root":
        payload = []
    elif damage == "version":
        payload["version"] = "unknown-version"
    elif damage == "offsets":
        payload["chapter_offsets"][1] = float("inf")
    elif damage == "duration":
        payload["duration_seconds"] = -1
    elif damage == "chapter_count":
        payload["chapters"]["kk"].pop()
    elif damage == "question_key":
        payload["questions"]["en"][0]["answer"] = "not an available option"
    elif damage == "kind":
        payload["chapters"]["ru"][0]["kind"] = "unsupported kind"
    elif damage == "chapter_order":
        payload["chapters"]["en"][0], payload["chapters"]["en"][1] = payload["chapters"]["en"][1], payload["chapters"]["en"][0]
    elif damage == "question_count":
        payload["questions"]["en"].pop()
    elif damage == "language_key":
        question = payload["questions"]["en"][0]
        question["answer"] = next(choice for choice in question["choices"] if choice != question["answer"])
    else:
        payload["media"]["ru"]["video"] = None
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        catalog._load_5min_content()


def test_legacy_prebuilt_plan_without_snapshot_requires_reload(tmp_path, monkeypatch):
    from aetherlab.core.models import LessonPlan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle

    catalog, path, payload = _package(tmp_path, monkeypatch)
    plan = catalog.accelerated_motion_5min_plan("kk")
    legacy = plan.to_json()
    del legacy["prebuilt_content_hash"]
    restored = LessonPlan.from_json(legacy)
    bundle = _prebuilt_5min_bundle(restored)
    assert bundle.status == "error" and not bundle.video_path
    assert bundle.invalid_media == {"manifest": "missing_content_hash"}
    assert bundle.plan.questions == restored.questions
    assert _prebuilt_5min_bundle(catalog.accelerated_motion_5min_plan("kk")).status == "assembled"
