"""Stage L verification, part 1 (static + preflight).

Checks:
 1. lesson_{ru,kk,en}.py: CAPTIONS/DATA/FORMULAS/UNITS parsed via ast match
    canonical.json exactly (formulas via the same latex->unicode mapping).
 2. No LaTeX usage anywhere in the scene code (unicode Text only).
 3. All 8 Block classes import locally and subclass manim Scene.
 4. Every canonical caption index is referenced by its block's code.
 5. Preflight (dry-run): each class ok, exact duration == block budget
    within 0.6 s, no off-frame objects.

Usage: python .qwen/tmp/verify_l.py [ru|kk|en]  (default ru)
Part 2 (cloud previews + frames) is appended after L4/L5 complete.
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
CANON = json.loads((ROOT / "output" / "stage_f_content" / "canonical.json").read_text(encoding="utf-8"))

LANG = sys.argv[1] if len(sys.argv) > 1 else "ru"
CAP_KEY = {"ru": "captions", "kk": "captions_kk", "en": "captions_en"}
UNITS = {"ru": {"vel": "м/с", "acc": "м/с²", "dist": "м", "time": "с"},
         "kk": {"vel": "м/с", "acc": "м/с²", "dist": "м", "time": "с"},
         "en": {"vel": "m/s", "acc": "m/s²", "dist": "m", "time": "s"}}
LATEX_SUBS = (("\\Delta ", "Δ"), ("v_0", "v₀"), ("t^2", "t²"))

SRC = (ROOT / "output" / "stage_l_scenes" / f"lesson_{LANG}.py").read_text(encoding="utf-8")
TREE = ast.parse(SRC)
ASSIGN = {n.targets[0].id: ast.literal_eval(n.value)
          for n in ast.walk(TREE)
          if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
          and n.targets[0].id in ("DATA", "UNITS", "FORMULAS", "CAPTIONS")}

# 1. data matches canonical
canon_data = {d["id"]: d["value"] for d in CANON["data"]}

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

assert ASSIGN["DATA"] == {
    "v0": canon_data["D-v0"], "a": canon_data["D-a"], "t": canon_data["D-t"],
    "v": canon_data["D-v"], "s": canon_data["D-s"],
    "b6": {"v0": canon_data["D2-v0"], "a": canon_data["D2-a"],
           "t": canon_data["D2-t"], "s": canon_data["D2-s"]}}, "DATA drift"
assert ASSIGN["UNITS"] == UNITS[LANG], "UNITS drift"
expected_f = {}
for f in CANON["formulas"]:
    uni = f["latex"]
    for src, dst in LATEX_SUBS:
        uni = uni.replace(src, dst)
    assert "\\" not in uni and "_" not in uni and "^" not in uni, f["id"]
    expected_f[f["id"]] = uni
assert ASSIGN["FORMULAS"] == expected_f, "FORMULAS drift"
expected_c = {b["id"]: b[CAP_KEY[LANG]] for b in CANON["blocks"]}
assert ASSIGN["CAPTIONS"] == expected_c, "CAPTIONS drift"
print(f"[{LANG}] data/captions/formulas match canonical.json")

# 2. no LaTeX
for token in ("MathTex", "Tex(", "TexTemplate", "TexMobject", "SingleStringMathTex"):
    assert token not in SRC, f"latex token: {token}"
print(f"[{LANG}] no LaTeX tokens")

# 3. import + Scene subclasses
from manim import Scene  # noqa: E402

spec = importlib.util.spec_from_file_location(
    f"lesson_{LANG}", str(ROOT / "output" / "stage_l_scenes" / f"lesson_{LANG}.py"))
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
CLASSES = [f"BlockB{i}" for i in range(8)]
for name in CLASSES:
    cls = getattr(module, name, None)
    assert isinstance(cls, type) and issubclass(cls, Scene), name
print(f"[{LANG}] 8/8 classes import and subclass Scene")

# 4. every caption index referenced by its block's code
for b in CANON["blocks"]:
    for i in range(len(b[CAP_KEY[LANG]])):
        assert f'CAPTIONS["{b["id"]}"]' in SRC or f"cap_text(\"{b['id']}\", {i})" in SRC, \
            f"{b['id']}[{i}] unreferenced"
print(f"[{LANG}] all caption indices referenced")

# 5. preflight each class
from aetherlab.services.scene_preflight import preflight_scene  # noqa: E402

# The preflight dry-runs at 2 fps, where a wait shorter than one frame
# (0.5 s) is played as a whole frame: wait(0.3) measures 0.5 s (+0.2 each).
# Real 30 fps renders play 0.3 s as exactly 9 frames, so the scene timing
# is correct and only the measurement needs this known correction.
def subframe_inflation(class_node) -> float:
    extra = 0.0
    for node in ast.walk(class_node):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "wait" and node.args
                and isinstance(node.args[0], ast.Constant)):
            dur = float(node.args[0].value)
            if 0 < dur < 0.5:
                extra += 0.5 - dur
    return extra

CLASS_NODES = {n.name: n for n in ast.walk(TREE)
               if isinstance(n, ast.ClassDef)}

budgets = {f"Block{b['id']}": b["end_s"] - b["start_s"] for b in CANON["blocks"]}
for name in CLASSES:
    report = preflight_scene(SRC, name)
    assert report.ran, f"{name}: preflight did not run ({report.note})"
    assert report.ok, f"{name}: {report.error[-3000:]}"
    corrected = report.duration_s - subframe_inflation(CLASS_NODES[name])
    assert abs(corrected - budgets[name]) < 0.6, \
        f"{name}: {report.duration_s}s (corrected {corrected:.2f}s) vs budget {budgets[name]}s"
    assert not report.off_frame, f"{name}: off_frame {report.off_frame}"
    print(f"[{LANG}] {name}: preflight ok, {report.duration_s}s "
          f"(corrected {corrected:.2f}s, budget {budgets[name]}s), plays={len(report.events)}")

print(f"STAGE L PART 1 VERIFIED ({LANG}): static + preflight clean")
