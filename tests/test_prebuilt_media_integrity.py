"""A lesson package must not silently serve replaced or unrelated files."""
from __future__ import annotations

import copy
import hashlib

import pytest


def _package(tmp_path, monkeypatch):
    from aetherlab.services import ent_lesson_catalog as catalog

    payload = copy.deepcopy(catalog._load_5min_content())
    for language in ("kk", "ru", "en"):
        folder = tmp_path / language
        folder.mkdir()
        for kind in ("video", "srt", "pdf"):
            data = f"synthetic {language} {kind} manifest fixture".encode()
            path = folder / kind
            path.write_bytes(data)
            payload["media"][language][kind] = {
                "path": f"{language}/{kind}", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
            }
    monkeypatch.setattr(catalog, "ACCELERATED_MOTION_5MIN_JSON", tmp_path / "manifest.json")
    monkeypatch.setattr(catalog, "_load_5min_content", lambda: payload)
    return catalog, payload


@pytest.mark.parametrize("kind", ("video", "srt", "pdf"))
def test_replaced_media_is_not_served_as_the_manifest_artifact(kind, tmp_path, monkeypatch):
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle

    catalog, payload = _package(tmp_path, monkeypatch)
    plan = catalog.accelerated_motion_5min_plan("kk")
    assert _prebuilt_5min_bundle(plan).status == "assembled"
    (tmp_path / "kk" / kind).write_bytes(b"replacement from another lesson")
    media = catalog.prebuilt_5min_media("kk")
    assert media[kind] == ""
    assert media["invalid"][kind] == "hash_mismatch"
    bundle = _prebuilt_5min_bundle(plan)
    assert bundle.status == "error"
    assert bundle.invalid_media[kind] == "hash_mismatch"
    assert len(bundle.plan.chapters) == 8


def test_media_path_cannot_resolve_outside_the_package(tmp_path, monkeypatch):
    catalog, payload = _package(tmp_path, monkeypatch)
    foreign = tmp_path.parent / "foreign-lesson-fixture.bin"
    foreign.write_bytes(b"other lesson")
    payload["media"]["ru"]["video"] = {
        "path": "../foreign-lesson-fixture.bin",
        "sha256": hashlib.sha256(foreign.read_bytes()).hexdigest(),
    }
    media = catalog.prebuilt_5min_media("ru")
    assert media["video"] == ""
    assert media["invalid"]["video"] == "outside_package"


def test_media_without_a_manifest_hash_is_not_certified(tmp_path, monkeypatch):
    catalog, payload = _package(tmp_path, monkeypatch)
    del payload["media"]["en"]["pdf"]["sha256"]
    media = catalog.prebuilt_5min_media("en")
    assert media["pdf"] == ""
    assert media["invalid"]["pdf"] == "missing_hash"


def test_unreadable_media_reports_access_failure_without_serving_it(tmp_path, monkeypatch):
    from pathlib import Path

    catalog, payload = _package(tmp_path, monkeypatch)
    target = tmp_path / "kk" / "video"
    original = Path.open

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError("Isolated media read refused")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    media = catalog.prebuilt_5min_media("kk")
    assert media["video"] == ""
    assert media["invalid"]["video"] == "file_unavailable"
    assert media["srt"] and media["pdf"]


def test_lesson_error_explains_missing_and_unverified_media_in_each_language():
    from types import SimpleNamespace

    from aetherlab.ui.main_window import MainWindow

    for language, phrase in (("kk", "растау мүмкін болмады"), ("ru", "Не удалось подтвердить"), ("en", "Could not verify")):
        messages, videos = [], []
        shell = SimpleNamespace(
            command_bar=SimpleNamespace(set_busy=lambda value: None, get_language=lambda: language),
            stepper=SimpleNamespace(set_cancellable=lambda value: None),
            lesson_view=SimpleNamespace(set_lesson=lambda value: None, set_video=videos.append, set_audio_enabled=lambda value: None),
            _restore_pending_lesson_answers=lambda: None,
            _refresh_course_summary=lambda value: None,
            _workspace=SimpleNamespace(setCurrentIndex=lambda value: None),
            statusBar=lambda: SimpleNamespace(showMessage=messages.append),
            toast=SimpleNamespace(show_message=lambda kind, message: messages.append(message)),
        )
        bundle = SimpleNamespace(status="error", video_path="", missing_media=["pdf"], invalid_media={"video": "hash_mismatch"})
        MainWindow.on_lesson_ready(shell, bundle)
        assert videos == [""]
        assert len(messages) == 2 and messages[0] == messages[1]
        assert phrase in messages[0] and "pdf" in messages[0] and "video" in messages[0]
