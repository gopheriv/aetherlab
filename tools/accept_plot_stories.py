"""Execute reviewed pure numeric F27–F29 contracts with retained evidence."""
from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from tools.accept_practice_bank import HOOK, LAUNCHER, sha
from tools.accept_practice_bank import runtime_fingerprint as base_runtime

ROOT = Path(__file__).resolve().parents[1]
MODULE = "tests/test_plot_contract.py"
CASE_REQUIREMENTS = {
    "F27": {
        "test_f27_all_unary_functions_match_independent_scalar_math": {"15_functions", "scalar_math_oracles", "grid_preserved"},
        "test_f27_operators_constants_caret_and_named_parameters": {"operators", "nested_calls", "constants", "unicode_parameters", "declared_constant_override"},
        "test_f27_function_arity_is_checked_before_numpy_can_use_an_out_array": {"all_function_arities", "no_out_write"},
        "test_f27_unsafe_syntax_and_bare_function_values_are_rejected": {"ast_whitelist", "bare_functions", "unsafe_calls"},
        "test_f27_runtime_namespace_cannot_replace_functions_or_inject_unused_values": {"namespace_isolation", "invalid_missing_parameters"},
        "test_f27_scalar_and_multidimensional_outputs_are_independent_copies": {"scalar_empty_2d_shapes", "result_isolation"},
        "test_f27_damped_physics_curve_keeps_grid_and_parameters_unchanged": {"physics_oracle", "parameter_grid_preservation"},
    },
    "F28": {
        "test_f28_character_and_ast_limits_include_exact_boundaries": {"512_char_boundary", "200_ast_boundary", "invalid_syntax"},
        "test_f28_overflow_zero_division_and_domains_are_controlled": {"overflow_inf", "zero_nan", "numpy_domains", "complex_rejected", "huge_literal"},
        "test_f28_range_span_clamps_and_unrepresentable_ranges_fail": {"10000_span", "float_resolution", "huge_ranges_markers"},
        "test_f28_pathological_power_finishes_in_an_actual_bounded_process": {"actual_process_deadline", "no_giant_integer"},
    },
    "F29": {
        "test_f29_legacy_explicit_and_parametric_payloads_preserve_their_curves": {"legacy_explicit", "parametric", "default_vs_zero_x", "axis_labels"},
        "test_f29_multicurve_primary_roles_styles_and_payload_isolation": {"primary_fallback", "styles", "default_names", "payload_isolation", "live_parameters", "fallback_payload"},
        "test_f29_malformed_payloads_and_curve_entries_raise_domain_errors": {"payload_shapes", "six_curve_limit", "curve_types", "parametric_invalid_x"},
        "test_f29_optional_ranges_and_invalid_finite_pairs": {"legacy_autorange", "range_validation", "huge_endpoint"},
        "test_f29_fill_markers_label_limits_and_six_curve_boundary": {"fill_math", "markers", "eight_marker_limit", "forty_char_labels", "endpoint_inclusion", "invalid_metadata"},
    },
}
COMMON_SOURCES = {"aetherlab/services/plotting.py", MODULE, "tools/accept_plot_stories.py",
    "tools/accept_practice_bank.py", "tools/feature_acceptance.py", "aetherlab/core/proc.py",
    "test_features.py", "build_feature_tracker.py"}
FEATURE_SOURCES = {feature: set(COMMON_SOURCES) for feature in CASE_REQUIREMENTS}
DETAILS = {feature: f"Complete pure numeric {feature} contract: {len(cases)} executed groups, independent math/structural/failure oracles; current NumPy/Python/source/contract and retained exact JUnit/log; no Qt/network or native canvas acceptance"
           for feature, cases in CASE_REQUIREMENTS.items()}
_POINTERS = None


def runtime_fingerprint():
    import numpy
    import numpy._core._multiarray_umath as extension
    binary = Path(extension.__file__).resolve()
    return {"base": base_runtime(), "numpy": numpy.__version__,
            "numpy_binary": {str(binary): sha(binary), str(Path(numpy.__file__).resolve()): sha(Path(numpy.__file__))}}


def _owned(root, name):
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to((root / "tmp").resolve()):
        raise ValueError("Plot evidence must stay under project tmp")
    return path


def _command(feature, report, hook):
    return [sys.executable, "-c", LAUNCHER, str(hook), MODULE, "-k", f"test_{feature.lower()}_",
        "-q", "-p", "no:cacheprovider", f"--basetemp={report.parent / 'cases'}", f"--junitxml={report}"]


def verify_execution(root, evidence):
    try:
        feature = evidence["feature_id"]
        if feature not in CASE_REQUIREMENTS or evidence.get("runtime") != runtime_fingerprint():
            return False, "Plot acceptance runtime changed"
        report, log, hook = (_owned(root, evidence[key]) for key in ("execution_report", "execution_log", "headless_hook"))
        if (sha(report) != evidence.get("execution_report_sha256") or sha(log) != evidence.get("execution_log_sha256")
                or hook.read_text(encoding="utf-8") != HOOK or sha(hook) != evidence.get("headless_hook_sha256")):
            return False, "Plot execution artifacts changed"
        if evidence.get("isolation") != {"qt_imports_forbidden": True, "network_forbidden": True}:
            return False, "Plot isolation is incomplete"
        cases = list(ET.parse(report).iter("testcase"))
        names = [case.attrib["name"] for case in cases]
        if len(names) != len(set(names)) or set(names) != set(CASE_REQUIREMENTS[feature]):
            return False, "Plot report omits reviewed groups"
        if any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
            return False, "Plot execution contains failed or skipped groups"
        if any(case.attrib.get("classname") != MODULE[:-3].replace("/", ".") for case in cases):
            return False, "Plot report belongs to another module"
        if evidence.get("command") != _command(feature, report, hook):
            return False, "Plot command did not execute the reviewed selector"
    except (KeyError, OSError, ValueError, TypeError, ET.ParseError):
        return False, "Plot execution evidence is invalid"
    return True, DETAILS[feature]


def run_acceptance(output_dir):
    global _POINTERS
    from aetherlab.core.proc import subprocess_kwargs
    from tools.feature_acceptance import contract_hash, verify_acceptance
    output_dir = Path(output_dir).resolve()
    if not output_dir.is_relative_to((ROOT / "tmp").resolve()):
        raise ValueError("Plot output must stay under project tmp")
    group_before = {name: sha(ROOT / name) for name in COMMON_SOURCES}
    # An earlier feature may already have imported the builder. Load a fresh
    # contract snapshot so in-process reuse cannot bind an old cached story.
    catalogue = runpy.run_path(str(ROOT / "build_feature_tracker.py"), run_name="plot_contract_catalogue")
    rows = {row[0]: dict(zip(catalogue["HEADERS"], row)) for row in catalogue["FEATURES"]}
    if group_before != {name: sha(ROOT / name) for name in COMMON_SOURCES}:
        raise RuntimeError("Plot contract sources changed while loading stories")
    def valid(pointers):
        return set(pointers) == set(CASE_REQUIREMENTS) and all(verify_acceptance(ROOT, rows[fid], {
            "status": "PASS", "phase4_status": "PASS", "behaviour_acceptance_evidence": pointer})[0]
            for fid, pointer in pointers.items())
    if _POINTERS and valid(_POINTERS):
        return dict(_POINTERS)
    _POINTERS = None
    output_dir.mkdir(parents=True, exist_ok=True)
    pointers = {}
    for feature, requirements in CASE_REQUIREMENTS.items():
        before = {name: sha(ROOT / name) for name in FEATURE_SOURCES[feature]}
        runtime = runtime_fingerprint()
        folder = ROOT / "tmp" / ("plot-accept-" + uuid.uuid4().hex)
        hook = folder / "hooks/sitecustomize.py"
        hook.parent.mkdir(parents=True)
        hook.write_text(HOOK, encoding="utf-8")
        report, log = folder / "tests.xml", folder / "execution.log"
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_"))
               and key not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS", "GITHUB_TOKEN", "GH_TOKEN"}}
        env.update({"PYTHONPATH": os.pathsep.join((str(hook.parent), str(ROOT))), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "QT_QPA_PLATFORM": "offscreen", "PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE": "0", "PHYSLAB_REQUIRE_NATIVE_QT": "0",
            "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "TEMP": str(folder), "TMP": str(folder)})
        command = _command(feature, report, hook)
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90, **subprocess_kwargs())
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError((result.stdout + result.stderr)[-4000:])
        after = {name: sha(ROOT / name) for name in FEATURE_SOURCES[feature]}
        if before != after or runtime != runtime_fingerprint():
            raise RuntimeError("Plot acceptance inputs changed during execution")
        evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": feature, "status": "PASS", "exit_code": 0,
            "completed_at": datetime.now(UTC).isoformat(), "contract_sha256": contract_hash(rows[feature]),
            "source_sha256": after, "runtime": runtime,
            "checks": [{"id": name, "status": "PASS", "covers": sorted(tags)} for name, tags in requirements.items()],
            "execution_report": report.relative_to(ROOT).as_posix(), "execution_report_sha256": sha(report),
            "execution_log": log.relative_to(ROOT).as_posix(), "execution_log_sha256": sha(log),
            "headless_hook": hook.relative_to(ROOT).as_posix(), "headless_hook_sha256": sha(hook),
            "command": command, "isolation": {"qt_imports_forbidden": True, "network_forbidden": True}}
        accepted, reason = verify_execution(ROOT, evidence)
        if not accepted:
            raise RuntimeError(reason)
        target = output_dir / f"{feature}-{uuid.uuid4().hex}.json"
        target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        pointers[feature] = {"path": target.relative_to(ROOT).as_posix(), "sha256": sha(target)}
    if not valid(pointers):
        raise RuntimeError("Plot acceptance became stale before publication")
    _POINTERS = dict(pointers)
    return pointers
