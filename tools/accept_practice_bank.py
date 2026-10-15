"""Executed software contracts for the generated bank and its SQLite mirror.

Pedagogical/language approval remains explicitly pending in the data. These
matrices certify the declared generator/API and sync contracts on this host.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ("kinematics", "dynamics", "statics", "fluids", "molecular_kinetic_theory", "gas_laws",
          "thermodynamics", "liquids_solids", "electrostatics", "electricity", "current_media", "magnetic_field",
          "induction", "mechanical_oscillations", "ac_circuits", "electromagnetic_waves", "wave_optics",
          "geometric_optics", "relativity", "quantum_physics", "nuclear_physics", "nanotechnology",
          "cosmology", "conservation", "wave_motion")
CASE_REQUIREMENTS = {
    "F232": {
        "test_every_generated_topic_has_an_independent_oracle": {"all_25_topics", "2500_items"},
        **{f"test_key_matches_displayed_condition_and_unit[{topic}]":
           {"100_items", "independent_displayed_input_calculation", "three_languages", "units", "public_api", "latex_result"}
           for topic in TOPICS},
        **{f"test_substitution_uses_the_displayed_input_without_hidden_precision[{topic}]": {"visible_substitution"}
           for topic in ("electrostatics", "relativity")},
        "test_ac_substitution_uses_the_approximation_given_in_the_condition": {"stated_approximation"},
        "test_bank_generation_is_deterministic_without_consuming_global_random_state": {"determinism", "random_isolation"},
        "test_structure_difficulty_bands_and_review_status_are_explicit":
            {"unique_ids_prompts_choices", "difficulty_bands", "pending_teacher_language_review", "nonofficial_label"},
        **{f"test_public_topic_aliases_select_the_same_hundred_questions[{alias}]": {"topic_alias"}
           for alias in ("energy-conservation", "mechanics-dynamics")},
        "test_unknown_topic_is_an_empty_selection": {"unknown_topic"},
        **{f"test_public_locale_normalization_preserves_question_identity[{locale}]": {"locale_normalization"}
           for locale in ("kk-KZ-kk", "ru_RU-ru", "en-US-en", "unknown-en")},
        "test_mutating_a_public_result_cannot_change_the_shared_bank": {"result_isolation"},
        "test_internal_generation_error_propagates_instead_of_returning_a_partial_bank": {"generation_failure"},
    },
    "F254": {
        "test_sync_preserves_an_unmanaged_custom_question": {"unmanaged_question_preserved"},
        "test_sync_keeps_additional_annotations": {"custom_columns_preserved"},
        "test_sync_keeps_child_rows_instead_of_delete_insert": {"foreign_keys_preserved"},
        "test_sync_works_before_any_books_are_indexed": {"fresh_database", "optional_corpus"},
        "test_updates_keep_question_and_metadata_row_identity": {"row_identity", "metadata_links"},
        "test_foreign_question_collision_aborts_without_any_changes": {"foreign_collision", "rollback"},
        **{f"test_corrupt_manifest_is_not_guessed_or_overwritten[{case}]": {"invalid_manifest", "rollback"}
           for case in ("invalid-json", "object", "string", "null-id", "foreign-namespace", "duplicate-id", "null-value", "invalid-utf8")},
        **{f"test_invalid_versioned_bank_cannot_clear_existing_data[{case}]": {"invalid_source_bank", "rollback"}
           for case in ("empty", "duplicate", "foreign-id")},
        "test_previously_managed_removed_question_is_retired_with_its_notes": {"managed_retirement", "notes_retained"},
        **{f"test_unknown_or_repurposed_old_rows_remain_untouched[{case}]": {"legacy_ownership", "repurposed_row"}
           for case in ("False", "True")},
        "test_current_bank_can_reactivate_an_archived_record_without_losing_notes": {"reactivation", "notes_retained"},
        "test_legacy_schema_migrates_without_deleting_data": {"schema_migration"},
        "test_page_candidates_keep_source_identity_limits_and_unreviewed_status": {"source_identity", "candidate_limit", "unreviewed_pages"},
        "test_broken_existing_page_view_aborts_without_partial_changes": {"corpus_read_failure", "rollback"},
        "test_mid_write_database_failure_rolls_back_questions_and_metadata": {"mid_write_rollback"},
        "test_read_only_database_refuses_and_then_retries_without_data_loss": {"physical_readonly_failure", "retry"},
        "test_sync_works_with_a_low_sqlite_bind_variable_limit": {"sqlite_variable_limit"},
        "test_actual_cli_from_foreign_directory_mirrors_the_public_bank": {"actual_cli", "unicode_profile", "all_2500_payloads"},
        "test_process_crash_recovers_the_previous_committed_bank": {"actual_process_crash", "journal_recovery"},
    },
}
MODULES = {"F232": "tests/test_all_topic_answer_keys.py", "F254": "tests/test_bank_sync_preservation.py"}
COMMON_SOURCES = {"tools/accept_practice_bank.py", "tools/feature_acceptance.py", "test_features.py",
                  "aetherlab/services/ent_topic_bank.py", "aetherlab/services/ent_physics_bank.py",
                  "aetherlab/services/ent_mock_solutions.py", "aetherlab/core/language.py"}
FEATURE_SOURCES = {
    "F232": COMMON_SOURCES | {MODULES["F232"]},
    "F254": COMMON_SOURCES | {MODULES["F254"], "tools/sync_ent_practice_bank.py", "tools/index_reference_library.py",
                              "aetherlab/core/settings.py", "aetherlab/core/atomic_json.py",
                              "aetherlab/core/console.py", "aetherlab/core/proc.py"},
}
DETAILS = {
    "F232": "Complete generator/API software contract: 40 executed cases, all 2500 displayed-condition keys/units in kk/ru/en, public filters/aliases/isolation, deterministic IDs/difficulty bands and honest pending review; no Qt/network. Teacher/curriculum approval is not certified",
    "F254": "Complete SQLite-sync software contract: 29 executed cases, real CLI/full bank, fresh/legacy databases, ownership/annotation/FK preservation, unreviewed page identity, atomic failure/readonly retry and actual process-crash recovery; no Qt/network",
}
HOOK = '''import importlib.abc,socket,sys
class NoGui(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'PyQt6','PySide6'}:
            raise ModuleNotFoundError('Qt is forbidden in this headless contract',name=fullname)
sys.meta_path.insert(0,NoGui())
def no_network(*args,**kwargs):
    raise AssertionError('Network is forbidden in the bank contract')
socket.socket.connect=no_network
socket.create_connection=no_network
'''
LAUNCHER = '''import pathlib,sitecustomize,socket,sys
assert pathlib.Path(sitecustomize.__file__).resolve()==pathlib.Path(sys.argv[1]).resolve()
def guard_is_active():
    assert any(isinstance(finder,sitecustomize.NoGui) for finder in sys.meta_path)
    assert socket.socket.connect is sitecustomize.no_network
    assert socket.create_connection is sitecustomize.no_network
    assert not any(name.split('.')[0] in {'PyQt6','PySide6'} for name in sys.modules)
guard_is_active()
import pytest
code=pytest.main(sys.argv[2:])
guard_is_active()
raise SystemExit(code)
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_fingerprint() -> dict:
    import _sqlite3

    import pytest

    paths = [Path(sys.executable), Path(_sqlite3.__file__)]
    for optional in (Path(_sqlite3.__file__).parent / "sqlite3.dll",
                     Path(sys.base_prefix) / f"python{sys.version_info.major}{sys.version_info.minor}.dll"):
        if optional.is_file():
            paths.append(optional)
    with sqlite3.connect(":memory:") as db:
        options = sorted(row[0] for row in db.execute("PRAGMA compile_options"))
    return {"python": sys.version, "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
            "sqlite_options": options, "pytest": pytest.__version__,
            "binaries": {str(path.resolve()): sha(path) for path in paths}}


def _owned(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to((root / "tmp").resolve()):
        raise ValueError("Bank evidence must stay under the project tmp directory")
    return path


def verify_execution(root: Path, evidence: dict) -> tuple[bool, str]:
    try:
        feature = evidence["feature_id"]
        if feature not in CASE_REQUIREMENTS or evidence.get("runtime") != runtime_fingerprint():
            return False, "Bank acceptance runtime changed"
        expected = CASE_REQUIREMENTS[feature]
        report = _owned(root, evidence["execution_report"])
        log = _owned(root, evidence["execution_log"])
        hook = _owned(root, evidence["headless_hook"])
        if (sha(report) != evidence.get("execution_report_sha256") or sha(log) != evidence.get("execution_log_sha256")
                or hook.read_text(encoding="utf-8") != HOOK or sha(hook) != evidence.get("headless_hook_sha256")):
            return False, "Bank execution artifacts changed"
        if evidence.get("isolation") != {"qt_imports_forbidden": True, "network_forbidden": True}:
            return False, "Bank acceptance isolation is incomplete"
        cases = list(ET.parse(report).iter("testcase"))
        names = [case.attrib["name"] for case in cases]
        if len(names) != len(expected) or len(set(names)) != len(names) or set(names) != set(expected):
            return False, "Bank execution report omits reviewed cases"
        if any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
            return False, "Bank execution contains a failed or skipped case"
        expected_class = Path(MODULES[feature]).with_suffix("").as_posix().replace("/", ".")
        if any(case.attrib.get("classname") != expected_class for case in cases):
            return False, "Bank report belongs to another test module"
        folder = report.parent
        command = [sys.executable, "-c", LAUNCHER, str(hook), MODULES[feature], "-q", "-p", "no:cacheprovider",
                   f"--basetemp={folder / 'cases'}", f"--junitxml={report}"]
        if evidence.get("command") != command:
            return False, "Bank execution did not run the reviewed module"
    except (KeyError, OSError, TypeError, ValueError, ET.ParseError):
        return False, "Bank execution evidence is invalid"
    return True, DETAILS[feature]


def run_acceptance(output: Path, row: dict) -> dict:
    from aetherlab.core.proc import subprocess_kwargs
    from tools.feature_acceptance import contract_hash

    feature = row["ID"]
    if feature not in CASE_REQUIREMENTS:
        raise ValueError("Unsupported bank contract")
    output = output.resolve()
    if not output.is_relative_to((ROOT / "tmp").resolve()):
        raise ValueError("Bank acceptance output must stay under project tmp")
    before = {name: sha(ROOT / name) for name in FEATURE_SOURCES[feature]}
    runtime = runtime_fingerprint()
    folder = ROOT / "tmp" / ("bank-accept-" + uuid.uuid4().hex)
    hook = folder / "hooks/sitecustomize.py"
    hook.parent.mkdir(parents=True)
    hook.write_text(HOOK, encoding="utf-8")
    report, log = folder / "tests.xml", folder / "execution.log"
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_"))}
    environment.update({"PYTHONPATH": os.pathsep.join((str(hook.parent), str(ROOT))),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "QT_QPA_PLATFORM": "offscreen",
        "PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE": "0", "PHYSLAB_REQUIRE_NATIVE_QT": "0",
        "AETHERLAB_DATA_DIR": str(folder / "data"), "AETHERLAB_DISABLE_LEGACY_ENV": "1",
        "AETHERLAB_QWEN_AUTOLOAD": "0", "TEMP": str(folder), "TMP": str(folder)})
    command = [sys.executable, "-c", LAUNCHER, str(hook), MODULES[feature], "-q", "-p", "no:cacheprovider",
               f"--basetemp={folder / 'cases'}", f"--junitxml={report}"]
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=180, **subprocess_kwargs())
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError((result.stdout + result.stderr)[-4500:])
    after = {name: sha(ROOT / name) for name in FEATURE_SOURCES[feature]}
    if before != after or runtime != runtime_fingerprint():
        raise RuntimeError("Bank acceptance inputs changed during execution")
    cases = list(ET.parse(report).iter("testcase"))
    evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": feature, "status": "PASS",
        "exit_code": result.returncode, "completed_at": datetime.now(UTC).isoformat(),
        "contract_sha256": contract_hash(row), "source_sha256": after, "runtime": runtime,
        "checks": [{"id": case.attrib["name"], "status": "PASS", "covers": sorted(CASE_REQUIREMENTS[feature].get(case.attrib["name"], set()))} for case in cases],
        "execution_report": report.relative_to(ROOT).as_posix(), "execution_report_sha256": sha(report),
        "execution_log": log.relative_to(ROOT).as_posix(), "execution_log_sha256": sha(log),
        "headless_hook": hook.relative_to(ROOT).as_posix(), "headless_hook_sha256": sha(hook),
        "command": command, "isolation": {"qt_imports_forbidden": True, "network_forbidden": True}}
    valid, reason = verify_execution(ROOT, evidence)
    if not valid:
        raise RuntimeError(reason)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": output.relative_to(ROOT).as_posix(), "sha256": sha(output)}
