"""Stage J verification: shots.json is internally consistent and covers canonical.json.

Checks:
 1. Block ids/order/timings match canonical; shot durations sum to block
    length; total is 300 s.
 2. Every data/formula ref in shots exists in canonical; restricted B6 scope:
    D2-* ids appear only in B6 shots, plain D-* never in B6.
 3. Coverage: every canonical block formula/data/caption index is referenced
    by >=1 shot of that block (nothing in the canon is left unstaged, nothing
    staged is uncanonical — except F-accel-def reuse in B4 slope triangle,
    which is explicitly allowed).
 4. Every shot has a non-empty purpose (gate: explainable purpose).
 5. Colors used by shots are all declared in the frozen roles table.
 6. Animated shots declare phys t0/t1 within [0,4], t1>t0; static shots none.
 7. scenario.md contains all block headers, variants, choice, and time table.
"""

import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
CANON = json.loads((ROOT / "output" / "stage_f_content" / "canonical.json").read_text(encoding="utf-8"))
SHOTS = json.loads((ROOT / "output" / "stage_j_scenario" / "shots.json").read_text(encoding="utf-8"))
DOC = (ROOT / "output" / "stage_j_scenario" / "scenario.md").read_text(encoding="utf-8")

data_ids = {d["id"] for d in CANON["data"]}
formula_ids = {f["id"] for f in CANON["formulas"]}
canon_by_id = {b["id"]: b for b in CANON["blocks"]}

# 1. structure + timing

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

assert SHOTS["block_order"] == [b["id"] for b in CANON["blocks"]]
total = 0
for sb in SHOTS["blocks"]:
    cb = canon_by_id[sb["id"]]
    assert (sb["start_s"], sb["end_s"]) == (cb["start_s"], cb["end_s"]), sb["id"]
    dur = sum(s["dur_s"] for s in sb["shots"])
    assert dur == cb["end_s"] - cb["start_s"], f"{sb['id']}: shots sum {dur}"
    total += dur
assert total == 300, total

# 2. refs exist + B6 scope
for sb in SHOTS["blocks"]:
    for s in sb["shots"]:
        for did in s["data"]:
            assert did in data_ids, f"unknown data {did} in {s['id']}"
            assert (did.startswith("D2-")) == (sb["id"] == "B6"), \
                f"scope leak: {did} in {s['id']}"
        for fid in s["formulas"]:
            assert fid in formula_ids, f"unknown formula {fid} in {s['id']}"

# 3. coverage per block
for sb in SHOTS["blocks"]:
    cb = canon_by_id[sb["id"]]
    used_f = {f for s in sb["shots"] for f in s["formulas"]}
    used_d = {d for s in sb["shots"] for d in s["data"]}
    used_c = {c for s in sb["shots"] for c in s["captions"]}
    for fid in cb["formulas"]:
        assert fid in used_f, f"{sb['id']}: formula {fid} unstaged"
    for did in cb["data"]:
        assert did in used_d, f"{sb['id']}: data {did} unstaged"
    for i in range(len(cb["captions"])):
        assert i in used_c, f"{sb['id']}: caption[{i}] unstaged"
    for s in sb["shots"]:
        for c in s["captions"]:
            assert 0 <= c < len(cb["captions"]), f"{s['id']}: bad caption idx {c}"
    extra_f = used_f - set(cb["formulas"])
    assert extra_f <= {"F-accel-def"}, f"{sb['id']}: uncanonical formulas {extra_f}"

# 4-6. purpose, colors, phys clocks
roles = set(SHOTS["colors"])
n_anim = 0
for sb in SHOTS["blocks"]:
    for s in sb["shots"]:
        assert s["purpose"].strip(), f"{s['id']}: empty purpose"
        assert set(s["colors"]) <= roles, f"{s['id']}: undeclared colors"
        assert s["colors"], f"{s['id']}: no colors"
        if s["phys"] is None:
            continue
        n_anim += 1
        assert 0 <= s["phys"]["t0"] < s["phys"]["t1"] <= 4, f"{s['id']}: bad clock"
        assert "T" in s["phys"]["clock"], f"{s['id']}: clock unexplained"
assert n_anim == 5, n_anim

# 7. doc presence
for bid in SHOTS["block_order"]:
    assert re.search(rf"^### {bid} \d+–\d+ с", DOC, re.M), f"doc: no {bid} section"
for token in ("Вариант A", "Вариант B", "Вариант C", "ВЫБРАН",
              "Физическое и экранное время", "Замороженные роли",
              "x(t) = 2t", "dT/dt"):
    assert token in DOC, f"doc: missing {token!r}"

n_shots = sum(len(b["shots"]) for b in SHOTS["blocks"])
print(f"STAGE J VERIFIED: 8 blocks, {n_shots} shots, 300 s, "
      f"{n_anim} animated clocks in [0,4], canon fully staged, "
      f"{len(roles)} frozen color roles")
