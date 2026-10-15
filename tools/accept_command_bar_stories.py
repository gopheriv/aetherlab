"""Reviewed native Qt acceptance matrices at the command-bar/worker boundary.

The actual widget tests run in an owned Windows Qt subprocess. Controlled
pipeline values and a real QThread cancellation barrier exercise UI behaviour;
these matrices do not certify a provider, solver or cloud rendering service.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("kk", "ru", "en")


def _cases(name, values, *covers):
    return {f"{name}[{value}]": set(covers) for value in values}


PROMPT_CASES = _cases("test_prompt_input_routes_once_and_preserves_unicode",
    (f"{route}-{language}" for route in ("return", "run", "ctrl-return") for language in LANGUAGES),
    "single_submission", "trimmed_unicode", "cleared_disabled_input", "worker_request_boundary")
QUOTA_CASES = _cases("test_quota_storage_failure_keeps_draft_and_retry_starts_once", LANGUAGES,
    "quota_failure_exact_draft", "retry_once")
THREAD_CASES = _cases("test_real_qthread_cancel_waits_for_cleanup_and_preserves_draft",
    (f"{route}-{language}" for route in ("button", "escape", "stepper") for language in LANGUAGES),
    "real_qthread_finished", "busy_during_cleanup", "localized_cancelling_cancelled",
    "restored_exact_draft_and_focus", "loading_cleared", "terminal_not_cancellable")
DETAIL_CASES = _cases("test_failure_details_and_retry_use_recoverable_page",
    (f"{state}-{language}" for state in ("False", "True") for language in LANGUAGES),
    "existing_or_empty_page", "actual_details_window", "original_traceback",
    "loading_cleared", "retry_clears_error", "idle_after_finished")
DUPLICATE_CASES = _cases("test_duplicate_start_preserves_worker_and_does_not_charge_again", LANGUAGES,
    "localized_duplicate", "single_worker", "no_second_quota_charge", "unchanged_progress_and_connections")
FAILURE_CASES = _cases("test_failure_context_is_localized_and_preserves_original_diagnostics",
    (f"{stage}-{language}" for stage in ("pipeline", "solver", "rag", "scene", "render", "planner", "lesson", "owned-unknown-stage")
     for language in LANGUAGES),
    "all_known_stages_localized", "unknown_stage_preserved", "original_diagnostics",
    "status_and_toast", "recoverable_draft", "idle_after_finished")
PROGRESS = {"test_progress_stages_complete_and_next_run_resets_timing": {
    "all_stage_boundaries", "completed_stages", "terminal_pulse_stopped", "next_run_timing_reset"}}
LATE_ERROR = {"test_terminal_error_ignores_late_worker_events": {"late_error_events_rejected"}}
NEW_DRAFT = {"test_recovery_keeps_a_newer_draft_instead_of_replacing_it": {"newer_draft_preserved"}}
DELETED = {"test_deleted_previous_qthread_does_not_block_a_new_run": {"deleted_qobject_restart"}}
QUEUED = {"test_queued_previous_worker_signals_cannot_change_a_new_run": {"queued_old_thread_events_rejected"}}

CASE_REQUIREMENTS = {
    "F12": {**PROMPT_CASES, **QUOTA_CASES, **PROGRESS, **NEW_DRAFT,
        "test_blank_busy_and_exhausted_quota_do_not_submit": {"blank_busy_zero_and_unknown_quota_guard"},
        "test_cancel_restores_question_for_editing": {"cancel_restores_exact_draft"},
        "test_failure_restores_question_and_stops_active_timeline": {"failure_restores_exact_draft"}},
    "F13": {"test_examples_menu_selects_full_prompt_and_escape_preserves_input": {
        "actual_menu_event_loop", "all_ten_choices", "truncated_labels_full_values", "above_button_anchor",
        "keyboard_focus", "no_run", "escape_preserves_draft"},
        **_cases("test_examples_follow_selected_language_and_keep_identical_physics_data", LANGUAGES,
                 "ten_school_physics_examples", "localized_prompts", "identical_numerical_data",
                 "language_switch_updates_menu", "full_prompt_focus_no_run", "dismiss_keeps_draft")},
    "F14": {**_cases("test_quality_flags_and_missing_selection_reach_actual_worker", LANGUAGES,
        "l_m_h_worker_arguments", "invalid_label_flag_preserve_selection", "unselected_draft_fallback"),
        **_cases("test_saved_default_quality_reaches_next_window_and_worker", ("l", "m", "h"),
                 "saved_default_window_and_worker"),
        **_cases("test_quality_labels_fit_the_styled_edit_field", LANGUAGES, "all_localized_labels_fit")},
    "F15": {**THREAD_CASES, **PROGRESS, **DETAIL_CASES,
        "test_cancel_remains_busy_until_worker_finished": {"run_learn_practice_swap", "input_disabled",
            "cancel_disabled_during_cleanup", "idle_buttons_after_finished"},
        **_cases("test_cancel_returns_to_existing_result_page", LANGUAGES,
                 "cancel_returns_existing_result", "loading_cleared", "draft_recovered"),
        **_cases("test_lesson_terminal_keeps_controls_busy_until_finished",
                 (f"{terminal}-{language}" for terminal in (
                     "planned", "rendered", "planning_error", "offline_practice_available",
                     "cancelled_empty", "cancelled_video", "failure") for language in LANGUAGES),
                 "lesson_terminal_waits_for_finished", "new_submissions_disabled", "terminal_cancel_disabled",
                 "allowance_unchanged", "next_lesson_cancel_usable"),
        **_cases("test_lesson_cancel_is_requested_once_and_controls_wait_for_cleanup", LANGUAGES,
                 "single_lesson_cancel", "cleanup_remains_busy"),
        **_cases("test_real_lesson_qthread_keeps_busy_after_result_until_cleanup_finishes", LANGUAGES,
                 "real_lesson_qthread_cleanup_barrier")},
    "F17": {**PROGRESS, **LATE_ERROR,
        "test_finished_cancellation_has_no_active_stage": {"neutral_cancelled_terminal", "pulse_stopped"},
        "test_late_progress_does_not_overwrite_cancelling_state": {"late_progress_rejected"},
        **_cases("test_terminal_stepper_freezes_elapsed_and_reset_clears_it", ("complete", "error", "cancelled"),
                 "terminal_elapsed_frozen", "reset_clears_timing"),
        **_cases("test_running_progress_labels_follow_selected_language", LANGUAGES, "localized_running_stages"),
        **THREAD_CASES},
    "F19": {**DUPLICATE_CASES, **DELETED, **QUEUED,
        **_cases("test_solve_during_lesson_cleanup_does_not_charge_or_start", LANGUAGES,
                 "no_solve_during_lesson_cleanup", "no_extra_allowance")},
    "F20": {**DELETED, **QUEUED, **LATE_ERROR,
        "test_cleanup_disconnects_all_signals_after_one_was_already_disconnected": {
            "all_signals_disconnected_independently", "delete_later_requested"},
        "test_all_worker_data_signals_route_once_and_stop_after_cancel": {
            "all_six_data_signals_once", "cancelled_and_finished_events_rejected"}},
    "F84": {**FAILURE_CASES, **DETAIL_CASES, **LATE_ERROR, **NEW_DRAFT,
        **_cases("test_lesson_failure_recovers_its_topic_after_a_previous_solve", LANGUAGES,
                 "lesson_failure_uses_its_own_draft", "failure_cleanup_focus"),
        **_cases("test_lesson_recovery_preserves_a_newer_draft",
                 (f"{terminal}-{language}" for terminal in ("failure", "cancelled") for language in LANGUAGES),
                 "lesson_recovery_keeps_newer_draft"),
        **_cases("test_failed_lesson_rejects_late_progress_and_ready", LANGUAGES,
                 "late_lesson_progress_and_result_rejected")},
}
REQUIRED_SOURCES = {
    "aetherlab/ui/main_window.py", "aetherlab/ui/command_bar.py", "aetherlab/ui/navigation.py",
    "aetherlab/ui/widgets.py", "aetherlab/ui/workers.py", "aetherlab/ui/qt_compat.py",
    "aetherlab/ui/shared_widgets.py", "aetherlab/ui/simulation_panel.py", "aetherlab/ui/lesson_view.py",
    "aetherlab/core/settings.py", "aetherlab/core/models.py", "aetherlab/core/atomic_json.py",
    "aetherlab/services/ai_help_quota.py", "aetherlab/services/student_profiles.py",
    "tests/test_command_bar_behaviour.py", "tests/test_lesson_submission_behaviour.py",
    "tests/test_examples_localization.py", "tests/test_lesson_completion_feedback.py", "tools/accept_command_bar_stories.py",
    "tools/feature_acceptance.py", "test_features.py",
}
FEATURE_SOURCES = {feature: REQUIRED_SOURCES for feature in CASE_REQUIREMENTS}
DETAILS = {feature: (
    f"Complete {feature} UI contract: {len(cases)} reviewed executed native Windows Qt cases; "
    "owned profiles and actual controls, menu/details where applicable; controlled pipeline data "
    "and real QThread cleanup barrier. Worker handoff and UI lifecycle only, no solver/provider/cloud acceptance"
) for feature, cases in CASE_REQUIREMENTS.items()}
_CACHE = {}
_FAILURES = {}


def _snapshot():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(REQUIRED_SOURCES)}


def run_acceptance(rows: dict[str, dict]) -> dict[str, dict]:
    """Explicitly run visible UI tests once per current source/contracts."""
    if os.environ.get("PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE") != "1":
        raise RuntimeError(
            "Visible Windows UI tests require PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE=1; "
            "ordinary catalog checks must not open desktop windows"
        )
    from aetherlab.core.proc import subprocess_kwargs
    from tools.feature_acceptance import contract_hash

    before = _snapshot()
    contracts = {feature: contract_hash(rows[feature]) for feature in CASE_REQUIREMENTS}
    signature = json.dumps([before, contracts], sort_keys=True)
    if signature in _CACHE:
        return _CACHE[signature]
    if signature in _FAILURES:
        raise AssertionError(_FAILURES[signature])
    folder = ROOT / "tmp" / "feature-acceptance" / ("commandbar-" + uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith(
        ("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_"))}
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "VISION_MODEL", "VOICEOVER_ENABLED", "TTS_ENABLED"):
        env.pop(key, None)
    env.update({"AETHERLAB_DATA_DIR": str(folder / "data"),
        "AETHERLAB_DISABLE_LEGACY_ENV": "1", "AETHERLAB_QWEN_AUTOLOAD": "0",
        "QT_QPA_PLATFORM": "windows", "PHYSLAB_REQUIRE_NATIVE_QT": "1", "TEMP": str(folder), "TMP": str(folder)})
    report = folder / "tests.xml"
    command = [sys.executable, "-m", "pytest", "tests/test_command_bar_behaviour.py",
        "tests/test_lesson_submission_behaviour.py", "tests/test_examples_localization.py",
        "tests/test_lesson_completion_feedback.py", "-q",
        "-o", "faulthandler_timeout=45", f"--basetemp={folder / 'cases'}", f"--junitxml={report}"]
    with (folder / "pytest.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, **subprocess_kwargs())
        (folder / "started.json").write_text(json.dumps({"pid": process.pid, "command": command,
            "started_at": datetime.now(UTC).isoformat(), "source_sha256": before}), encoding="utf-8")
        try:
            code = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            message = f"Native UI acceptance exceeded 600 seconds; see {folder / 'pytest.log'}"
            _FAILURES[signature] = message
            raise AssertionError(message)
    after = _snapshot()
    summary = {"exit_code": code, "completed_at": datetime.now(UTC).isoformat(),
        "source_sha256_before": before, "source_sha256_after": after,
        "log": (folder / "pytest.log").relative_to(ROOT).as_posix(), "qt_platform": "windows"}
    (folder / "execution.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    assert before == after, "UI acceptance sources changed during execution"
    if code != 0:
        message = f"Native UI acceptance failed; see {folder / 'pytest.log'}"
        _FAILURES[signature] = message
        raise AssertionError(message)
    tests = list(ET.parse(report).iter("testcase"))
    names = [test.attrib["name"] for test in tests]
    assert len(set(names)) == len(names), "Duplicate native test identifiers"
    observed = {test.attrib["name"]: test for test in tests}
    required = set().union(*(set(cases) for cases in CASE_REQUIREMENTS.values()))
    assert required <= set(observed), "The native report omits a reviewed scenario"
    assert all(not any(test.find(tag) is not None for tag in ("failure", "error", "skipped"))
               for test in tests), "Skipped, failed or otherwise unaccepted native scenario"
    pointers = {}
    report_hash = hashlib.sha256(report.read_bytes()).hexdigest()
    for feature, cases in CASE_REQUIREMENTS.items():
        evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": feature,
            "status": "PASS", "exit_code": code, "completed_at": summary["completed_at"],
            "contract_sha256": contracts[feature], "source_sha256": after, "scope": DETAILS[feature],
            "qt_platform": "windows", "execution_report": report.relative_to(ROOT).as_posix(),
            "execution_report_sha256": report_hash,
            "checks": [{"id": case, "status": "PASS", "covers": sorted(coverage)} for case, coverage in cases.items()]}
        target = folder / (feature + ".json")
        target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        pointers[feature] = {"path": target.relative_to(ROOT).as_posix(),
                             "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    _CACHE[signature] = pointers
    return pointers
