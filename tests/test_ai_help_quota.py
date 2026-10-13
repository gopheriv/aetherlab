from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.ai_help_quota import (
    DAILY_AI_HELP_LIMIT,
    consume_ai_help,
    daily_ai_help_usage,
    remaining_ai_help,
)


def test_daily_allowance_counts_attempts_and_resets_by_local_date(tmp_path) -> None:
    path = tmp_path / "ai_help_quota.json"
    today = date(2026, 10, 12)

    assert remaining_ai_help(path, today=today) == DAILY_AI_HELP_LIMIT
    for expected_remaining in range(9, -1, -1):
        allowed, remaining = consume_ai_help(path, today=today)
        assert allowed is True
        assert remaining == expected_remaining

    assert consume_ai_help(path, today=today) == (False, 0)
    assert daily_ai_help_usage(path, today=today) == 10
    assert remaining_ai_help(path, today=today + timedelta(days=1)) == 10


def test_concurrent_help_requests_cannot_exceed_limit(tmp_path) -> None:
    path = tmp_path / "ai_help_quota.json"
    today = date(2026, 10, 12)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: consume_ai_help(path, today=today), range(24)))

    assert sum(1 for allowed, _remaining in results if allowed) == DAILY_AI_HELP_LIMIT
    assert daily_ai_help_usage(path, today=today) == DAILY_AI_HELP_LIMIT


def test_corrupt_counter_recovers_without_granting_negative_quota(tmp_path) -> None:
    path = tmp_path / "ai_help_quota.json"
    path.write_text("{broken", encoding="utf-8")

    assert remaining_ai_help(path, today=date(2026, 10, 12)) == DAILY_AI_HELP_LIMIT
    assert consume_ai_help(path, today=date(2026, 10, 12)) == (True, 9)


def test_command_bar_disables_only_ai_actions_at_zero_and_localizes_badge() -> None:
    from aetherlab.ui.command_bar import CommandBar
    from aetherlab.ui.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    command = CommandBar()
    command.set_ai_quota(0)
    assert not command.run_button.isEnabled()
    assert not command.learn_button.isEnabled()
    assert command.practice_button.isEnabled()
    assert "0/10" in command._ai_quota.text()

    command.set_language("ru")
    assert command._ai_quota.text().startswith("AI сегодня:")
    command.close()
    del app


def test_main_window_consumes_quota_for_active_student_profile(tmp_path) -> None:
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    settings = replace(
        load_settings(),
        data_dir=tmp_path,
        cache_path=tmp_path / "cache.sqlite3",
        chroma_path=tmp_path / "chroma",
        library_path=tmp_path / "library",
        openai_api_key="test-key",
        reference_sources_path=None,
    )
    window = MainWindow(settings)
    assert "10/10" in window.command_bar._ai_quota.text()
    for _ in range(10):
        assert window._try_consume_ai_help()
    assert not window._try_consume_ai_help()
    assert "0/10" in window.command_bar._ai_quota.text()
    assert not window.command_bar.run_button.isEnabled()
    window.close()
    del app
