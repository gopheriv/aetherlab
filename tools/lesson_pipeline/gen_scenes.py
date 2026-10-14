"""Stage L: emit output/stage_l_scenes/lesson_{ru,kk,en}.py from canonical.json.

The template (.qwen/tmp/lesson_template.py) holds staging/choreography; all
data (numbers, units, formula spellings, captions) is baked from the canon.
Fails loudly on unknown latex tokens or caption count drift.
"""

import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
CANON = json.loads((ROOT / "output" / "stage_f_content" / "canonical.json").read_text(encoding="utf-8"))
TEMPLATE = (ROOT / ".qwen" / "tmp" / "lesson_template.py").read_text(encoding="utf-8")
OUTDIR = ROOT / "output" / "stage_l_scenes"

CAP_KEY = {"ru": "captions", "kk": "captions_kk", "en": "captions_en"}
UNITS = {"ru": {"vel": "м/с", "acc": "м/с²", "dist": "м", "time": "с"},
         "kk": {"vel": "м/с", "acc": "м/с²", "dist": "м", "time": "с"},
         "en": {"vel": "m/s", "acc": "m/s²", "dist": "m", "time": "s"}}

LATEX_SUBS = (("\\Delta ", "Δ"), ("v_0", "v₀"), ("t^2", "t²"))


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

def latex_to_unicode(latex: str) -> str:
    out = latex
    for src, dst in LATEX_SUBS:
        out = out.replace(src, dst)
    assert "\\" not in out and "_" not in out and "^" not in out, latex
    return out


def build_block(lang: str) -> str:
    data = {d["id"]: d["value"] for d in CANON["data"]}
    payload = {"v0": data["D-v0"], "a": data["D-a"], "t": data["D-t"],
               "v": data["D-v"], "s": data["D-s"],
               "b6": {"v0": data["D2-v0"], "a": data["D2-a"],
                      "t": data["D2-t"], "s": data["D2-s"]}}
    data_src = f"DATA = {json.dumps(payload, ensure_ascii=False)}"
    units_src = f"UNITS = {json.dumps(UNITS[lang], ensure_ascii=False)}"
    formulas = {f["id"]: latex_to_unicode(f["latex"]) for f in CANON["formulas"]}
    formulas_src = f"FORMULAS = {json.dumps(formulas, ensure_ascii=False, indent=8)}"
    captions = {b["id"]: b[CAP_KEY[lang]] for b in CANON["blocks"]}
    for b in CANON["blocks"]:
        assert len(b[CAP_KEY[lang]]) == len(b["captions"]), (lang, b["id"])
    captions_src = f"CAPTIONS = {json.dumps(captions, ensure_ascii=False, indent=8)}"
    return "\n".join((data_src, units_src, formulas_src, captions_src))


pattern = re.compile(r"# == GEN:DATA BEGIN ==\n.*?\n# == GEN:DATA END ==",
                     re.DOTALL)
assert pattern.search(TEMPLATE), "GEN markers missing in template"

OUTDIR.mkdir(exist_ok=True)
for lang in ("ru", "kk", "en"):
    code = pattern.sub(
        f"# == GEN:DATA BEGIN ==\n{build_block(lang)}\n# == GEN:DATA END ==",
        TEMPLATE)
    code = code.replace("Language of on-screen captions: RU",
                        f"Language of on-screen captions: {lang.upper()}")
    dst = OUTDIR / f"lesson_{lang}.py"
    dst.write_text(code, encoding="utf-8")
    print(f"ok: {dst.name}")
