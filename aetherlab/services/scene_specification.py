"""Versioned evidence and timing payload shared by renders and lesson scenes."""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from typing import Any

SCENE_SPEC_SCHEMA = "aetherlab.scene_spec.v1"


def build_scene_spec(
    request: Any,
    solver: Any,
    rag: Any = None,
    storyboard: dict[str, Any] | None = None,
    *,
    narration: str = "",
    citations: list[str] | None = None,
    assessment: list[dict[str, Any]] | None = None,
    scene: Any = None,
) -> dict[str, Any]:
    """Build a JSON-safe spec without asserting more than the checkers know."""
    from aetherlab.services.derivation_verify import verify_derivation_records, verify_ode_units
    from aetherlab.services.parameters import apply_request_parameters
    from aetherlab.services.verify import verify_solution

    solver = apply_request_parameters(request, solver)
    board = storyboard if isinstance(storyboard, dict) else {}
    refs = _references(rag, citations)
    numeric = verify_solution(solver, request)
    numeric_status = "not_checked" if not getattr(solver, "numeric_spec", None) else (
        "passed" if numeric.ok and all(item.passed for item in numeric.checks) else "failed"
    )
    units = verify_ode_units(solver)
    derivations = verify_derivation_records(solver)
    variables = getattr(solver, "variables", {}) or {}
    variable_units = getattr(solver, "variable_units", {}) or {}
    timeline = [dict(item) for item in board.get("timeline", []) if isinstance(item, dict)]
    if not timeline:
        timeline = _flatten_storyboard(board)
    acts = [item for item in board.get("acts", []) if isinstance(item, dict)]
    creative = {
        "concept": str(board.get("concept", "")),
        "staging": str(board.get("staging", "")),
        "palette": dict(board.get("palette", {})) if isinstance(board.get("palette"), dict) else {},
        "hero_frame": str(board.get("hero_frame", "")),
        "idle_loop": str(board.get("idle_loop", "")),
        "acts": [
            {
                "name": str(act.get("name", "")),
                "start_s": act.get("start_s"),
                "end_s": act.get("end_s"),
                "beat_ids": [
                    str(item.get("id", ""))
                    for item in timeline
                    if isinstance(item, dict)
                    and str(item.get("act", "")) == str(act.get("name", ""))
                    and item.get("id")
                ],
            }
            for act in acts
        ],
    }
    duration = _positive_float(
        board.get("timeline_duration_s") or getattr(request, "duration_target_s", 0.0)
    )
    code = str(getattr(scene, "code", "") or "")
    scene_ref = {
        "class_name": str(getattr(scene, "class_name", "") or ""),
        "engine": str(getattr(scene, "engine", "") or ""),
        "status": str(getattr(scene, "status", "") or ""),
        "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest() if code else "",
        "video_path": str(getattr(scene, "video_path", "") or ""),
    }
    checks = derivations.get("items", [])
    check_by_index = {
        int(check.get("index", 0)): check
        for check in checks
        if isinstance(check, dict) and str(check.get("index", "")).isdigit()
    }
    records = []
    for index, raw_record in enumerate(getattr(solver, "derivation_records", []) or [], start=1):
        if not isinstance(raw_record, dict):
            continue
        record = dict(raw_record)
        check = check_by_index.get(index, {})
        record["check_status"] = check.get("status", "not_checked")
        record["substitution_status"] = check.get("substitution_status", "not_checked")
        record["substitution_detail"] = check.get("substitution_detail", "")
        record["provenance_ids"] = _match_references(str(record.get("source_ref", "")), refs)
        records.append(record)
    return {
        "schema": SCENE_SPEC_SCHEMA,
        "subject": str(getattr(request, "prompt", "") or getattr(request, "topic", "")),
        "request": {
            "parameters": {
                str(name): _json_number(value)
                for name, value in (getattr(request, "parameters", {}) or {}).items()
            },
            "target_duration_s": duration,
        },
        "creative": creative,
        "physics": {
            "summary": str(getattr(solver, "summary", "")),
            "key_equations": [str(x) for x in getattr(solver, "key_equations", []) or []],
            "derivation_steps": [str(x) for x in getattr(solver, "derivation_steps", []) or []],
            "derivation_records": records,
            "variables": {
                str(name): {"value": _json_number(value), "unit": str(variable_units.get(name, ""))}
                for name, value in variables.items()
            },
            "assumptions": [str(x) for x in getattr(solver, "assumptions", []) or []],
            "numeric_model": getattr(solver, "numeric_spec", None),
            "plot": getattr(solver, "plot", None),
        },
        "evidence": refs,
        "verification": {
            "numeric_model": {
                "status": numeric_status,
                "summary": numeric.summary,
                "checks": [
                    {"name": c.name, "status": "passed" if c.passed else "failed", "detail": c.detail}
                    for c in numeric.checks
                ],
            },
            "derivations": derivations,
            "units": units,
        },
        "timeline": {"target_duration_s": duration, "beats": timeline},
        "narration": {
            "text": str(narration or ""),
            "beat_cues": [
                {
                    "beat_id": str(item.get("id", "")),
                    "start_s": item.get("start_s"),
                    "end_s": item.get("end_s"),
                    "text": str(item.get("narration_cue", "")),
                    "subtitle_text": str(item.get("subtitle_cue") or item.get("narration_cue", "")),
                    "target_object": str(item.get("target_object", "")),
                    "target_equation": str(item.get("target_equation", "")),
                    "anchor_cell": str(item.get("anchor_cell", "")),
                }
                for item in timeline if str(item.get("narration_cue", "")).strip()
            ],
        },
        "assessment": [dict(x) for x in (assessment or []) if isinstance(x, dict)],
        "scene": scene_ref,
    }


def validate_scene_spec(spec: Any) -> dict[str, Any]:
    """Validate the versioned cross-output payload without checking physics twice."""
    errors: list[str] = []
    if not isinstance(spec, dict):
        return {"status": "failed", "errors": ["scene spec must be an object"]}
    if spec.get("schema") != SCENE_SPEC_SCHEMA:
        errors.append(f"unsupported schema {spec.get('schema')!r}")
    for section in (
        "request", "creative", "physics", "evidence", "verification",
        "timeline", "narration", "assessment", "scene",
    ):
        if section not in spec:
            errors.append(f"missing {section} section")
    for section in ("request", "creative", "physics", "verification", "scene"):
        if section in spec and not isinstance(spec[section], dict):
            errors.append(f"{section} must be an object")
    request = spec.get("request")
    if isinstance(request, dict):
        if not isinstance(request.get("parameters", {}), dict):
            errors.append("request.parameters must be an object")
        if _positive_float(request.get("target_duration_s")) <= 0:
            errors.append("request.target_duration_s must be positive")
    if "assessment" in spec and not isinstance(spec.get("assessment"), list):
        errors.append("assessment must be a list")
    physics = spec.get("physics")
    timeline = spec.get("timeline")
    narration = spec.get("narration")
    evidence = spec.get("evidence")
    if not isinstance(physics, dict):
        errors.append("physics must be an object")
        physics = {}
    if not isinstance(timeline, dict):
        errors.append("timeline must be an object")
        timeline = {}
    if not isinstance(narration, dict):
        errors.append("narration must be an object")
        narration = {}
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        evidence = []

    duration = _positive_float(timeline.get("target_duration_s"))
    beats = timeline.get("beats")
    if not isinstance(beats, list):
        errors.append("timeline.beats must be a list")
        beats = []
    previous_end = 0.0
    beat_ids: set[str] = set()
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            errors.append(f"timeline beat {index + 1} must be an object")
            continue
        beat_id = str(beat.get("id", "")).strip()
        if beat_id and beat_id in beat_ids:
            errors.append(f"duplicate beat id {beat_id}")
        if beat_id:
            beat_ids.add(beat_id)
        has_start, has_end = "start_s" in beat, "end_s" in beat
        if not has_start and not has_end:
            continue  # Legacy flat storyboards can have descriptive, untimed beats.
        if not beat_id:
            errors.append(f"timeline beat {index + 1} is missing its id")
        try:
            start, end = float(beat.get("start_s")), float(beat.get("end_s"))
        except (TypeError, ValueError):
            errors.append(f"timeline beat {beat_id or index + 1} has invalid bounds")
            continue
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            errors.append(f"timeline beat {beat_id or index + 1} has invalid bounds")
            continue
        if start + 1e-6 < previous_end:
            errors.append(f"timeline beat {beat_id or index + 1} overlaps its predecessor")
        if duration and end > duration + 0.05:
            errors.append(f"timeline beat {beat_id or index + 1} exceeds target duration")
        previous_end = max(previous_end, end)

    refs = {
        str(ref.get("id", ""))
        for ref in evidence if isinstance(ref, dict) and ref.get("id")
    }
    records = physics.get("derivation_records", [])
    if not isinstance(records, list):
        errors.append("physics.derivation_records must be a list")
        records = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"derivation record {index + 1} must be an object")
            continue
        if record.get("check_status", "not_checked") not in {"passed", "failed", "not_checked"}:
            errors.append(f"derivation record {index + 1} has an invalid check status")
        if record.get("substitution_status", "not_checked") not in {"passed", "failed", "not_checked"}:
            errors.append(f"derivation record {index + 1} has an invalid substitution status")
        provenance = record.get("provenance_ids", [])
        if not isinstance(provenance, list) or any(str(item) not in refs for item in provenance):
            errors.append(f"derivation record {index + 1} has an unknown provenance id")

    cues = narration.get("beat_cues", [])
    if not isinstance(cues, list):
        errors.append("narration.beat_cues must be a list")
        cues = []
    for cue in cues:
        if not isinstance(cue, dict):
            errors.append("narration cue must be an object")
            continue
        beat_id = str(cue.get("beat_id", "")).strip()
        if beat_id and beat_id not in beat_ids:
            errors.append(f"narration cue references unknown beat {beat_id}")
    return {"status": "failed" if errors else "passed", "errors": errors}


def storyboard_from_scene_spec(spec: Any) -> dict[str, Any] | None:
    """Project the canonical spec timeline into the renderer/voiceover interface."""
    if validate_scene_spec(spec)["status"] != "passed":
        return None
    timeline_section = spec.get("timeline", {})
    timeline = timeline_section.get("beats", [])
    narration = spec.get("narration", {})
    cues = {
        str(item.get("beat_id", "")): item
        for item in narration.get("beat_cues", [])
        if isinstance(item, dict)
    }
    projected = []
    for beat in timeline:
        item = dict(beat)
        cue = cues.get(str(item.get("id", "")), {})
        if cue:
            item["narration_cue"] = str(cue.get("text", ""))
            item["subtitle_cue"] = str(cue.get("subtitle_text", ""))
        projected.append(item)
    return {
        "timeline": projected,
        "timeline_duration_s": timeline_section.get("target_duration_s", 0.0),
    }


def canvas_inputs_from_scene_spec(spec: Any) -> dict[str, Any] | None:
    """Return canvas data projected from the same physics fields as the scene."""
    if validate_scene_spec(spec)["status"] != "passed":
        return None
    physics = spec.get("physics", {})
    variables = physics.get("variables", {})
    params = {
        str(name): float(item["value"])
        for name, item in variables.items()
        if isinstance(item, dict)
        and isinstance(item.get("value"), (int, float))
        and math.isfinite(float(item["value"]))
    }
    return {
        "title": str(physics.get("summary", "Simulation")),
        "params": params,
        "plot": physics.get("plot") if isinstance(physics.get("plot"), dict) else None,
        "numeric_spec": (
            physics.get("numeric_model")
            if isinstance(physics.get("numeric_model"), dict) else None
        ),
    }


def refresh_scene_bundle_spec(
    scene: Any,
    request: Any,
    solver: Any,
    rag: Any = None,
    *,
    citations: list[str] | None = None,
    assessment: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach a validated spec and refresh its render metadata after each stage."""
    previous = getattr(scene, "scene_spec", None)
    previous_narration = (
        previous.get("narration", {}) if isinstance(previous, dict) else {}
    )
    narration = str(
        getattr(scene, "narration_text", "")
        or (previous_narration.get("text", "") if isinstance(previous_narration, dict) else "")
    )
    spec = build_scene_spec(
        request,
        solver,
        rag,
        getattr(scene, "storyboard", None),
        narration=narration,
        citations=citations,
        assessment=assessment,
        scene=scene,
    )
    if isinstance(previous_narration, dict):
        for key in ("sync", "subtitle_path"):
            if key in previous_narration:
                spec["narration"][key] = previous_narration[key]
    if isinstance(previous, dict) and isinstance(previous.get("assessment"), list):
        if not assessment:
            spec["assessment"] = previous["assessment"]
    scene.scene_spec = spec
    validation = validate_scene_spec(spec)
    if validation["status"] != "passed":
        diagnostics = getattr(scene, "diagnostics", None)
        if isinstance(diagnostics, list):
            message = (
                "Scene specification has validation issues: "
                + "; ".join(validation["errors"][:4])
            )
            if message not in diagnostics:
                diagnostics.append(message)
    return spec


def public_scene_spec(spec: Any) -> dict[str, Any] | None:
    """Return a portable spec with machine-local paths removed."""
    if validate_scene_spec(spec)["status"] != "passed":
        return None
    public = deepcopy(spec)
    for reference in public.get("evidence", []):
        if isinstance(reference, dict):
            reference["source"] = ""
    scene = public.get("scene")
    if isinstance(scene, dict):
        scene.pop("video_path", None)
    narration = public.get("narration")
    if isinstance(narration, dict):
        narration.pop("subtitle_path", None)
    return public


def _references(rag: Any, citations: list[str] | None) -> list[dict[str, Any]]:
    refs = []
    for index, hit in enumerate(getattr(rag, "hits", []) or []):
        refs.append({
            "id": f"ref-{index + 1}",
            "title": str(getattr(hit, "source_name", "") or getattr(hit, "source_label", "") or "Reference"),
            "source": str(getattr(hit, "source_path", "") or ""),
            "page": getattr(hit, "page_number", None),
            "origin": str(getattr(hit, "origin", "library")),
        })
    if not refs:
        for index, citation in enumerate(citations or []):
            refs.append({"id": f"ref-{index + 1}", "title": str(citation), "source": "", "page": None, "origin": "lesson-plan"})
    return refs


def _match_references(value: str, refs: list[dict[str, Any]]) -> list[str]:
    needle = value.casefold().strip()
    if not needle:
        return []
    return [
        str(ref["id"]) for ref in refs
        if needle in str(ref.get("title", "")).casefold()
        or needle in str(ref.get("source", "")).casefold()
    ]


def _flatten_storyboard(board: dict[str, Any]) -> list[dict[str, Any]]:
    flattened = []
    for act in board.get("acts", []) or []:
        if not isinstance(act, dict):
            continue
        for beat in act.get("beats", []) or []:
            if isinstance(beat, dict):
                flattened.append({"act": str(act.get("name", "")), **beat})
            else:
                flattened.append({"act": str(act.get("name", "")), "detail": str(beat)})
    return flattened


def _positive_float(value: Any) -> float:
    try:
        value = float(value)
        return value if value > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _json_number(value: Any) -> float | str:
    try:
        number = float(value)
        return number if number == number and abs(number) != float("inf") else str(value)
    except (TypeError, ValueError):
        return str(value)
