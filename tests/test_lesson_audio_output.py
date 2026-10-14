"""Inline lesson playback must route the existing audio stream to an output."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def test_inline_lesson_player_has_an_owned_unmuted_audio_output():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from aetherlab.ui.lesson_view import LessonView

    view = LessonView()
    try:
        assert view._player is not None, "Multimedia dependency is required for this playback acceptance"
        audio = view._player.audioOutput()
        assert audio is not None, "Lesson player has no audio destination despite voiced MP4s"
        assert audio.parent() is view
        assert not audio.isMuted() and audio.volume() > 0
        view.set_audio_enabled(False)
        assert audio.isMuted()
        view.set_audio_enabled(True)
        assert not audio.isMuted()
    finally:
        view.close()


def test_scene_video_player_has_an_owned_unmuted_audio_output():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from aetherlab.ui.simulation_panel import SimulationPanel

    panel = SimulationPanel()
    try:
        audio = panel._player.audioOutput()
        assert audio is not None, "Rendered scene player has no audio destination"
        assert audio.parent() is panel
        assert not audio.isMuted() and audio.volume() > 0
    finally:
        panel.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_real_lesson_audio_stream_loads_without_starting_playback(language):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from PyQt6.QtMultimedia import QMediaPlayer

    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle
    from aetherlab.ui.lesson_view import LessonView
    from aetherlab.ui.qt_compat import QtCore

    view = LessonView()
    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan(language))
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    elapsed = QtCore.QElapsedTimer()
    statuses = []
    view._player.mediaStatusChanged.connect(lambda status: statuses.append(str(status)))
    view._player.mediaStatusChanged.connect(
        lambda status: loop.quit() if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.InvalidMedia) else None
    )
    try:
        elapsed.start()
        view.set_video(bundle.video_path)
        timer.start(10000)
        loop.exec()
        assert view._player.mediaStatus() == QMediaPlayer.MediaStatus.LoadedMedia, {
            "language": language, "bundle_status": bundle.status,
            "has_path": bool(bundle.video_path), "elapsed_ms": elapsed.elapsed(),
            "statuses": statuses, "current": str(view._player.mediaStatus()),
            "player_error": view._player.errorString(),
        }
        assert view._player.hasAudio() and view._player.hasVideo()
        assert view._player.audioOutput() is view._audio_output
        assert view._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
        assert 285000 <= view._player.duration() <= 315000
    finally:
        timer.stop()
        view._player.stop()
        view._player.setSource(QtCore.QUrl())
        _APP.processEvents()
        view.close()
        _APP.processEvents()
