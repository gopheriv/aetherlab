"""Run complete source-bound acceptance matrices for the F06-F08 settings stories."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from tools.accept_practice_bank import HOOK, LAUNCHER, runtime_fingerprint, sha

ROOT = Path(__file__).resolve().parents[1]
CASE_REQUIREMENTS = {
    "F06": {
        "test_f06_explicit_environment_paths_and_provider_fields": {"environment_paths", "provider_fields"},
        "test_f06_compatible_environment_aliases_feed_the_same_client_policy": {"migration_aliases", "bounded_client_policy"},
        "test_f06_timeout_and_retry_bounds_are_explicit_and_authoritative": {"timeout_minimum", "timeout_maximum", "retry_bounds"},
        **{f"test_f06_every_provider_alias_and_first_nonblank_winner[{kind}]": {"all_aliases", "blank_alias", "alias_order"}
           for kind in ("model", "key", "url")},
        "test_f06_legacy_cloud_aliases_and_visual_controls": {"legacy_file", "cloud_aliases", "visual_controls", "unchanged_input"},
        "test_f06_client_factory_passes_bounded_policy_to_primary_and_backup": {"actual_client_factory", "primary_backup_policy"},
        "test_f06_ollama_fills_only_missing_provider_fields": {"preset_defaults", "explicit_winner"},
    },
    "F07": {
        "test_f07_settings_round_trip_drops_empty_values_and_survives_reload": {"save_reload", "empty_value_cleanup"},
        "test_f07_concurrent_saves_merge_without_partial_temporary_files": {"concurrent_updates", "atomic_cleanup"},
        "test_f07_unreadable_config_refuses_overwrite_and_preserves_saved_bytes": {"read_failure", "preserve_existing_bytes"},
        "test_missing_profile_read_creates_no_files": {"missing_profile", "no_write_on_read"},
        **{f"test_corrupt_config_is_read_without_rewriting[{kind}]": {"corrupt_input", "no_write_on_read"}
           for kind in ("json", "utf8", "list", "null", "number", "boolean", "string")},
        "test_scalar_filter_preserves_zero_false_and_unicode": {"scalar_shape", "zero_false_unicode"},
        "test_save_merges_trims_and_removes_only_requested_empty_fields": {"merge", "trim", "selective_removal"},
        "test_saved_data_and_library_paths_flow_into_settings_without_config_recursion": {"saved_paths", "stable_config_location"},
        "test_read_refusal_uses_startup_defaults_but_cannot_be_overwritten": {"read_failure", "startup_fallback", "strict_save"},
        **{f"test_write_failure_preserves_committed_bytes_and_cleans_stage[{stage}]": {"write_failure", "atomic_cleanup", "preserve_existing_bytes"}
           for stage in ("create", "encode", "fsync", "replace")},
        **{f"test_windows_sharing_refusal_retries_without_deleting_target[{kind}]": {"bounded_retry", "preserve_existing_bytes"}
           for kind in ("transient", "permanent")},
        "test_real_read_only_config_refuses_then_retries": {"physical_readonly", "retry"},
        "test_real_shared_read_handle_recovers_after_owner_releases_it": {"physical_sharing_handle", "retry"},
        "test_concurrent_writers_keep_every_field": {"thread_concurrency", "merge"},
        "test_real_restart_from_a_foreign_directory_reads_saved_values": {"actual_restart", "unicode_foreign_cwd"},
        "test_real_process_crash_cannot_publish_a_partial_configuration": {"actual_process_crash", "committed_data_survives", "retry"},
    },
    "F08": {
        "test_f08_environment_wins_over_saved_and_opted_in_qwen_sources": {"environment_precedence", "provider_source", "key_source"},
        "test_f08_saved_config_wins_over_opted_in_qwen_and_reports_its_source": {"saved_precedence", "provider_source"},
        "test_f08_blank_environment_values_fall_through_to_saved_provider": {"blank_fallback"},
        "test_f08_provider_warnings_never_echo_environment_or_saved_secrets": {"secret_redaction", "shadow_warning"},
        "test_f08_legacy_tier_and_per_field_fallback": {"legacy_precedence", "per_field_fallback", "exact_key_source"},
        **{f"test_f08_bad_lower_files_are_skipped_without_rewriting[{kind}]": {"bad_lower_source", "no_rewrite", "no_environment_mutation"}
           for kind in ("missing", "utf8", "shape", "json")},
        "test_f08_url_only_environment_and_saved_fields_name_the_highest_used_tier": {"url_only_origin", "preset_priority", "mixed_key_origin"},
    },
}
FEATURE_SOURCES = {
    "F06": {
        "aetherlab/core/settings.py", "aetherlab/services/model_policy.py",
        "aetherlab/services/llm_client.py", "tests/test_settings_story_acceptance.py",
        "tools/accept_settings_stories.py", "tools/feature_acceptance.py", "test_features.py",
    },
    "F07": {
        "aetherlab/core/settings.py", "aetherlab/core/atomic_json.py",
        "tests/test_settings_story_acceptance.py", "tools/accept_settings_stories.py",
        "tools/feature_acceptance.py", "test_features.py",
    },
    "F08": {
        "aetherlab/core/settings.py", "tests/test_settings_story_acceptance.py",
        "tools/accept_settings_stories.py", "tools/feature_acceptance.py", "test_features.py",
    },
}
PERSISTENCE_MODULE = "tests/test_settings_persistence_contract.py"
SETTINGS_MODULE = "tests/test_settings_story_acceptance.py"
CASE_MODULES = {fid: {name: PERSISTENCE_MODULE if fid == "F07" and not name.startswith("test_f07_")
                     else SETTINGS_MODULE for name in cases} for fid, cases in CASE_REQUIREMENTS.items()}
# The environment and precedence stories promise safe startup on corrupt config
# too. Execute these existing physical persistence cases in each relevant matrix.
for _feature in ("F06", "F08"):
    for _name in CASE_REQUIREMENTS["F07"]:
        if _name == "test_missing_profile_read_creates_no_files" or _name.startswith("test_corrupt_config_is_read_without_rewriting["):
            CASE_REQUIREMENTS[_feature][_name] = CASE_REQUIREMENTS["F07"][_name]
            CASE_MODULES[_feature][_name] = PERSISTENCE_MODULE
    FEATURE_SOURCES[_feature].update({PERSISTENCE_MODULE, "aetherlab/core/atomic_json.py"})
for _sources in FEATURE_SOURCES.values():
    _sources.update({"tools/accept_practice_bank.py", "aetherlab/core/proc.py"})
FEATURE_SOURCES["F07"].add(PERSISTENCE_MODULE)
DETAILS = {
    "F06": "Complete settings-input contract: 17 cases for explicit paths, every provider alias/order, actual legacy/cloud/critic settings, preset fallback, bounded primary/backup client construction and corrupt/missing app config; no provider calls",
    "F07": "Complete backend persistence contract: 26 cases including actual restart/crash, Windows read-only/share handle refusals, staged-write failures, bounded retry, thread merge, saved paths and corrupt/missing input; Settings dialog interaction remains F10",
    "F08": "Complete provider precedence contract: 18 cases for independent env > config > legacy > opted-in Qwen fields, blank/corrupt fallback, highest-used-tier summary, exact key origin and secret-free diagnostics",
}
_POINTERS: dict[str, dict] | None = None


def _owned(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to((root / "tmp").resolve()):
        raise ValueError("Settings evidence must stay under project tmp")
    return path


def _command(feature: str, report: Path, hook: Path) -> list[str]:
    nodes = [f"{CASE_MODULES[feature][name]}::{name}" for name in CASE_REQUIREMENTS[feature]]
    return [sys.executable, "-c", LAUNCHER, str(hook), *nodes, "-q", "-p", "no:cacheprovider",
            f"--basetemp={report.parent / 'cases'}", f"--junitxml={report}"]


def verify_execution(root: Path, evidence: dict) -> tuple[bool, str]:
    try:
        feature = evidence["feature_id"]
        if feature not in CASE_REQUIREMENTS or evidence.get("runtime") != runtime_fingerprint():
            return False, "Settings acceptance runtime changed"
        report = _owned(root, evidence["execution_report"])
        log = _owned(root, evidence["execution_log"])
        hook = _owned(root, evidence["headless_hook"])
        if (sha(report) != evidence.get("execution_report_sha256") or sha(log) != evidence.get("execution_log_sha256")
                or hook.read_text(encoding="utf-8") != HOOK or sha(hook) != evidence.get("headless_hook_sha256")):
            return False, "Settings execution artifacts changed"
        if evidence.get("isolation") != {"qt_imports_forbidden": True, "network_forbidden": True}:
            return False, "Settings acceptance isolation is incomplete"
        cases = list(ET.parse(report).iter("testcase"))
        names = [case.attrib["name"] for case in cases]
        if len(names) != len(set(names)) or set(names) != set(CASE_REQUIREMENTS[feature]):
            return False, "Settings execution report omits reviewed cases"
        if any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
            return False, "Settings execution contains a failed or skipped case"
        if any(case.attrib.get("classname") != CASE_MODULES[feature][case.attrib["name"]][:-3].replace("/", ".") for case in cases):
            return False, "Settings report belongs to another test module"
        if evidence.get("command") != _command(feature, report, hook):
            return False, "Settings execution did not run the reviewed nodes"
    except (KeyError, OSError, TypeError, ValueError, ET.ParseError):
        return False, "Settings execution evidence is invalid"
    return True, DETAILS[feature]


def _current_rows() -> dict[str, dict]:
    # Contracts come from current code, never a possibly stale generated CSV.
    import build_feature_tracker as tracker
    return {row[0]: dict(zip(tracker.HEADERS, row)) for row in tracker.FEATURES}


def run_acceptance(output_dir: Path) -> dict[str, dict]:
    """Execute the three reviewed backend matrices, persisting raw evidence."""
    global _POINTERS
    from aetherlab.core.proc import subprocess_kwargs
    from tools.feature_acceptance import contract_hash, verify_acceptance

    output_dir = output_dir.resolve()
    if not output_dir.is_relative_to((ROOT / "tmp").resolve()):
        raise ValueError("Settings acceptance output must stay under project tmp")
    rows = _current_rows()
    if _POINTERS and set(_POINTERS) == set(CASE_REQUIREMENTS) and all(
        verify_acceptance(ROOT, rows[fid], {"status": "PASS", "phase4_status": "PASS",
                          "behaviour_acceptance_evidence": pointer})[0]
        for fid, pointer in _POINTERS.items()
    ):
        return dict(_POINTERS)
    _POINTERS = None
    output_dir.mkdir(parents=True, exist_ok=True)
    pointers = {}
    for feature, requirements in CASE_REQUIREMENTS.items():
        before = {name: sha(ROOT / name) for name in FEATURE_SOURCES[feature]}
        runtime = runtime_fingerprint()
        contract = contract_hash(rows[feature])
        folder = ROOT / "tmp" / ("settings-accept-" + uuid.uuid4().hex)
        hook = folder / "hooks/sitecustomize.py"
        hook.parent.mkdir(parents=True)
        hook.write_text(HOOK, encoding="utf-8")
        report, log = folder / "tests.xml", folder / "execution.log"
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_", "CLOUD_", "VISION_", "VISUAL_CRITIC_", "TTS_"))
               and key not in {"PYTEST_ADDOPTS", "GITHUB_TOKEN", "GH_TOKEN", "VOICEOVER_ENABLED"}}
        env.update({"PYTHONPATH": os.pathsep.join((str(hook.parent), str(ROOT))),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "QT_QPA_PLATFORM": "offscreen",
            "PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE": "0", "PHYSLAB_REQUIRE_NATIVE_QT": "0",
            "AETHERLAB_DATA_DIR": str(folder / "data"), "AETHERLAB_DISABLE_LEGACY_ENV": "1",
            "AETHERLAB_QWEN_AUTOLOAD": "0", "TEMP": str(folder), "TMP": str(folder),
            "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
        command = _command(feature, report, hook)
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=180, **subprocess_kwargs())
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError((result.stdout + result.stderr)[-4500:])
        after = {name: sha(ROOT / name) for name in FEATURE_SOURCES[feature]}
        if before != after or runtime != runtime_fingerprint() or contract != contract_hash(_current_rows()[feature]):
            raise RuntimeError("Settings acceptance inputs changed during execution")
        evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": feature, "status": "PASS",
            "exit_code": result.returncode, "completed_at": datetime.now(UTC).isoformat(),
            "contract_sha256": contract, "source_sha256": after, "runtime": runtime,
            "checks": [{"id": name, "status": "PASS", "covers": sorted(tags)} for name, tags in requirements.items()],
            "execution_report": report.relative_to(ROOT).as_posix(), "execution_report_sha256": sha(report),
            "execution_log": log.relative_to(ROOT).as_posix(), "execution_log_sha256": sha(log),
            "headless_hook": hook.relative_to(ROOT).as_posix(), "headless_hook_sha256": sha(hook),
            "command": command, "isolation": {"qt_imports_forbidden": True, "network_forbidden": True}}
        valid, reason = verify_execution(ROOT, evidence)
        if not valid:
            raise RuntimeError(reason)
        target = output_dir / f"{feature}-{uuid.uuid4().hex}.json"
        target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        pointers[feature] = {"path": target.relative_to(ROOT).as_posix(), "sha256": sha(target)}
    # Recheck early matrices too: a later scenario must not stale an earlier run.
    if not all(verify_acceptance(ROOT, rows[fid], {"status": "PASS", "phase4_status": "PASS",
               "behaviour_acceptance_evidence": pointer})[0] for fid, pointer in pointers.items()):
        raise RuntimeError("Settings acceptance became stale before publication")
    _POINTERS = dict(pointers)
    return pointers
