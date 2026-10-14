"""K2 mux plan: per-language fragment offsets (block-absolute seconds).

Single source of truth for Stage M. Asserts per shot+language: fragments
ordered, inter-fragment gap >= 0.15 s, within shot bounds. Video events are
common across languages (see lesson_template.py); only audio offsets differ.
Writes output/stage_k2_fragments/mux_plan.json.
"""

import json
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
DUR = json.load(open(ROOT / "output/stage_k2_fragments/durations.json", encoding="utf-8"))["durations"]
FRAGMENTS = json.loads((ROOT / "output" / "stage_k2_fragments" / "fragments.json").read_text(encoding="utf-8"))

# shot -> (head, end) block-absolute, L2 budgets
BOUNDS = {
    "j0a": (0, 6), "j0b": (6, 14), "j0c": (14, 20),
    "j1a": (0, 10), "j1b": (10, 24), "j1c": (24, 36), "j1d": (36, 50),
    "j2a": (0, 12), "j2b": (12, 28), "j2c": (28, 40),
    "j3a": (0, 12), "j3b": (12, 26), "j3c": (26, 50),
    "j4a": (0, 14), "j4b": (14, 28), "j4c": (28, 40),
    "j5a": (0, 16), "j5b": (16, 30),
    "j6a": (0, 10), "j6b": (10, 22), "j6c": (22, 30),
    "j7a": (0, 14), "j7b": (14, 23), "j7c": (23, 40),
}

# fragment -> offset; scalar = all languages, dict = per-language
OFFSETS: dict[str, float | dict[str, float]] = {
    "B00af1": 0.3,
    "B00bf1": {"ru": 10.6, "kk": 10.7, "en": 10.5},
    "B00cf1": 14.3, "B00cf2": 16.3,
    "B11af1": 0.3,
    "B11bf1": 10.3, "B11bf2": 14.3, "B11bf3": 20.5,
    "B11cf1": 24.3, "B11cf2": 31.4,
    "B11df1": 36.3,
    "B22af1": 0.3, "B22af2": 4.9,
    "B22bf1": 12.3,
    "B22cf1": 28.3, "B22cf2": 33.7,
    "B33af1": 0.3, "B33af2": 4.2,
    "B33bf1": 12.3, "B33bf2": 17.3,
    "B33cf1": 26.3, "B33cf2": 29.6, "B33cf3": 33.1,
    "B44af1": 0.3, "B44af2": 5.4,
    "B44af3": {"ru": 8.4, "kk": 8.4, "en": 9.4},
    "B44bf1": 14.3, "B44cf1": 28.3,
    "B55af1": {"ru": 2.4, "kk": 0.3, "en": 0.3},
    "B55af2": {"ru": 3.73, "kk": 1.6, "en": 1.6},
    "B55af3": {"ru": 7.26, "kk": 5.9, "en": 5.9},
    "B55bf1": 16.3, "B55bf2": 18.0,
    "B66af1": 0.3, "B66af2": 1.3, "B66af3": 5.9,
    "B66bf1": 10.3, "B66cf1": 22.3,
    "B77af1": 0.3, "B77af2": 1.4, "B77af3": 8.5,
    "B77bf1": 14.3, "B77bf2": 17.3,
    "B77cf1": 23.3, "B77cf2": 34.1,
}

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

assert set(OFFSETS) == set(FRAGMENTS), "offset/fragment mismatch"


def off(fid: str, lang: str) -> float:
    o = OFFSETS[fid]
    return o if isinstance(o, float) else o[lang]


plan: dict[str, dict] = {}
for shot, (head, end) in BOUNDS.items():
    fids = sorted(f for f in FRAGMENTS if FRAGMENTS[f]["shot"] == shot)
    plan[shot] = {"bounds": [head, end], "offsets": {}}
    for lang in ("ru", "kk", "en"):
        prev_end = head
        for i, fid in enumerate(fids):
            o, d = off(fid, lang), DUR[fid][lang]
            assert o >= head, (shot, lang, fid)
            if i > 0:
                assert o - prev_end >= 0.149, (shot, lang, fid, o - prev_end)
            prev_end = o + d
        assert prev_end <= end + 1e-9, (shot, lang, prev_end, end)
        plan[shot]["offsets"][lang] = {f: off(f, lang) for f in fids}
        tail = end - prev_end
        print(f"{shot}: tail ru/kk/en = ", end="")
    tails = []
    for lang in ("ru", "kk", "en"):
        last = fids[-1]
        tails.append(f"{lang}:{end - (off(last, lang) + DUR[last][lang]):.2f}s")
    print(" ".join(tails))

out = ROOT / "output" / "stage_k2_fragments" / "mux_plan.json"
out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {out} (all fits verified)")
