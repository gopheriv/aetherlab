"""Validate complete story acceptance separately from narrow catalog probes.

Acceptance binds an executed scenario matrix to the current story contract,
implementation and runner. It never promotes a pending or failed retest.
"""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

CONTRACT_COLUMNS = (
    "ID", "Feature", "User Story", "Expected Behavior", "Source File(s)",
    "Story", "Persona", "Expected behaviour", "Failure-mode expectation", "Test method",
)
DEFAULT_PATH_MODES = ("absent", "empty", "whitespace", "relative", "absolute", "unicode")
DEFAULT_PATH_CASES = {f"{mode}-{cwd}" for mode in DEFAULT_PATH_MODES for cwd in ("first", "second")}
DEFAULT_PATH_REQUIREMENTS = {
    "per_user_data", "home_fallback", "chroma_path", "derived_cache_library",
    "working_directory_independence", "invalid_localappdata_fallback",
}
DEFAULT_PATH_SOURCES = {
    "aetherlab/core/settings.py", "aetherlab/core/atomic_json.py", "tools/accept_default_paths.py",
    "tools/feature_acceptance.py",
}
WATCHDOG_CASE_REQUIREMENTS = {
    "test_unwritable_log_directory_does_not_prevent_clean_launch": {"log_directory_refusal", "launch_command"},
    "test_log_file_refusal_does_not_prevent_recovery": {"log_file_refusal", "restart_nonzero"},
    "test_clean_exit_stops_and_launch_uses_the_expected_command": {"launch_command", "clean_exit"},
    "test_repeated_crashes_back_off_and_cap_at_sixty_seconds": {"backoff_growth", "backoff_cap"},
    "test_healthy_uptime_resets_backoff_at_the_boundary": {"healthy_reset", "uptime_logging"},
    "test_child_start_failure_is_logged_and_retried": {"spawn_failure", "error_logging"},
    "test_interrupt_while_child_runs_stops_without_relaunch": {"child_interrupt"},
    "test_interrupt_during_backoff_stops_without_traceback": {"backoff_interrupt"},
    "test_actual_child_process_is_restarted_then_clean_exit_stops": {"actual_process_restart", "exit_logging", "clean_exit"},
    "test_actual_batch_launcher_restarts_child_from_foreign_cwd": {"actual_batch_launcher", "unicode_spaced_cwd"},
}
WATCHDOG_SOURCES = {
    "aetherlab_watchdog.py", "start.bat", "aetherlab/core/console.py",
    "tests/test_watchdog_behaviour.py", "test_features.py", "tools/feature_acceptance.py",
}


def requirements_for_mode(mode: str) -> set[str]:
    requirements = {"chroma_path", "derived_cache_library", "working_directory_independence"}
    requirements.add("per_user_data" if mode in {"absolute", "unicode"} else "home_fallback")
    if mode in {"whitespace", "relative"}:
        requirements.add("invalid_localappdata_fallback")
    return requirements


def contract_hash(row: dict) -> str:
    contract = {key: row[key] for key in CONTRACT_COLUMNS}
    return hashlib.sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _inside(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Evidence path is outside the project")
    return path


def verify_acceptance(root: Path, row: dict, result: dict) -> tuple[bool, str]:
    # Stories catalogued before the phase-4 field was introduced have no such
    # field. Their current retest plus source-bound acceptance matrix remains
    # sufficient; an explicit phase status is still binding and PENDING/FAIL
    # must never be promoted by old evidence.
    phase4_status = result.get("phase4_status")
    if result.get("status") != "PASS" or ("phase4_status" in result and phase4_status != "PASS"):
        return False, "Current catalog retest has not passed"
    feature = row.get("ID")
    from tools.accept_command_bar_stories import CASE_REQUIREMENTS as UI_CASES
    from tools.accept_command_bar_stories import DETAILS as UI_DETAILS
    from tools.accept_command_bar_stories import FEATURE_SOURCES as UI_SOURCES
    from tools.accept_settings_stories import CASE_REQUIREMENTS as SETTINGS_CASES
    from tools.accept_settings_stories import DETAILS as SETTINGS_DETAILS
    from tools.accept_settings_stories import FEATURE_SOURCES as SETTINGS_SOURCES
    from tools.accept_plot_stories import CASE_REQUIREMENTS as PLOT_CASES
    from tools.accept_plot_stories import FEATURE_SOURCES as PLOT_SOURCES

    if feature not in {"F06", "F07", "F08", "F11", "F04", "F03", "F05", "F09", "F253", "F232", "F254"} | set(UI_CASES) | set(PLOT_CASES):
        return False, "No reviewed complete acceptance matrix for this story"
    if feature == "F11":
        required_cases = DEFAULT_PATH_CASES
        required_sources = DEFAULT_PATH_SOURCES
        required_conditions = {case: requirements_for_mode(case.rsplit("-", 1)[0]) for case in required_cases}
    elif feature == "F04":
        required_cases = set(WATCHDOG_CASE_REQUIREMENTS)
        required_sources = WATCHDOG_SOURCES
        required_conditions = WATCHDOG_CASE_REQUIREMENTS
    elif feature == "F253":
        from tools.accept_encoder_budget import CASE_REQUIREMENTS, FEATURE_SOURCES
        required_conditions = CASE_REQUIREMENTS
        required_cases = set(required_conditions)
        required_sources = FEATURE_SOURCES
    elif feature in {"F232", "F254"}:
        from tools.accept_practice_bank import CASE_REQUIREMENTS, FEATURE_SOURCES

        required_conditions = CASE_REQUIREMENTS[feature]
        required_cases = set(required_conditions)
        required_sources = FEATURE_SOURCES[feature]
    elif feature in PLOT_CASES:
        required_conditions = PLOT_CASES[feature]
        required_cases = set(required_conditions)
        required_sources = PLOT_SOURCES[feature]
    elif feature in SETTINGS_CASES:
        required_conditions = SETTINGS_CASES[feature]
        required_cases = set(required_conditions)
        required_sources = SETTINGS_SOURCES[feature]
    elif feature in UI_CASES:
        required_conditions = UI_CASES[feature]
        required_cases = set(required_conditions)
        required_sources = UI_SOURCES[feature]
    else:
        try:
            from tools.accept_startup_stories import CASE_REQUIREMENTS, DETAILS, FEATURE_SOURCES
        except ImportError:
            return False, "The reviewed startup acceptance matrix is unavailable"
        required_conditions = CASE_REQUIREMENTS[feature]
        required_cases = set(required_conditions)
        required_sources = FEATURE_SOURCES[feature]
    pointer = result.get("behaviour_acceptance_evidence")
    if not isinstance(pointer, dict):
        return False, "Complete acceptance evidence is missing"
    try:
        data = _inside(root, pointer["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != pointer.get("sha256"):
            return False, "Acceptance evidence changed"
        evidence = json.loads(data)
        if not isinstance(evidence, dict):
            return False, "Acceptance evidence is not an object"
        if evidence.get("schema") != "physlab.story_acceptance.v1" or evidence.get("feature_id") != row["ID"]:
            return False, "Acceptance evidence belongs to another contract"
        if evidence.get("contract_sha256") != contract_hash(row):
            return False, "The story contract changed after acceptance"
        if (evidence.get("status") != "PASS" or type(evidence.get("exit_code")) is not int
                or evidence["exit_code"] != 0 or not evidence.get("completed_at")):
            return False, "The acceptance run did not finish successfully"
        checks = evidence.get("checks")
        if not isinstance(checks, list) or len(checks) != len(required_cases):
            return False, "Acceptance scenario coverage is incomplete"
        if any(not isinstance(check, dict) or check.get("status") != "PASS" for check in checks):
            return False, "An acceptance scenario failed"
        if {check.get("id") for check in checks} != required_cases:
            return False, "Acceptance scenario coverage is incomplete"
        if any(not required_conditions[check["id"]] <= set(check.get("covers", [])) for check in checks):
            return False, "A scenario omits its required acceptance conditions"
        coverage = set().union(*(set(check.get("covers", [])) for check in checks))
        if not set().union(*required_conditions.values()) <= coverage:
            return False, "Acceptance requirement coverage is incomplete"
        sources = evidence.get("source_sha256")
        if not isinstance(sources, dict) or not required_sources <= set(sources):
            return False, "Acceptance implementation coverage is incomplete"
        for name, digest in sources.items():
            if hashlib.sha256(_inside(root, name).read_bytes()).hexdigest() != digest:
                return False, "Acceptance is stale for the current implementation"
        if feature == "F253":
            from tools.accept_encoder_budget import verify_execution
            return verify_execution(root, evidence)
        if feature in {"F232", "F254"}:
            from tools.accept_practice_bank import verify_execution

            return verify_execution(root, evidence)
        if feature in SETTINGS_CASES:
            from tools.accept_settings_stories import verify_execution

            return verify_execution(root, evidence)
        if feature in PLOT_CASES:
            from tools.accept_plot_stories import verify_execution

            return verify_execution(root, evidence)
        if feature in UI_CASES:
            if evidence.get("qt_platform") != "windows":
                return False, "Native UI acceptance did not use the reviewed Windows platform"
            report = _inside(root, evidence["execution_report"]).read_bytes()
            if hashlib.sha256(report).hexdigest() != evidence.get("execution_report_sha256"):
                return False, "Native UI execution report changed"
            native_cases = list(ET.fromstring(report).iter("testcase"))
            names = [test.attrib["name"] for test in native_cases]
            if len(set(names)) != len(names) or not required_cases <= set(names):
                return False, "Native UI execution report omits reviewed scenarios"
            if any(test.find(tag) is not None for test in native_cases for tag in ("failure", "error", "skipped")):
                return False, "Native UI execution report contains an unsuccessful scenario"
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, ET.ParseError):
        return False, "Acceptance evidence is unavailable or invalid"
    detail = (
        "Complete defaults contract: 12 fresh-process cases; absent, empty, invalid and valid LOCALAPPDATA; two launch folders; current story and source hashes"
        if feature == "F11" else
        "Complete watchdog contract: 10 executed cases; real child and Windows batch restart/clean exit, backoff growth/cap/reset, spawn/logging failures and interrupts; current story and source hashes. Child fixtures exercise watchdog control, not native app acceptance"
    )
    if feature in {"F03", "F05", "F09"}:
        detail = DETAILS[feature]
    elif feature in UI_CASES:
        detail = UI_DETAILS[feature]
    elif feature in SETTINGS_CASES:
        detail = SETTINGS_DETAILS[feature]
    return True, detail
