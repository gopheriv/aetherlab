"""Stage K2: split speak.json into per-shot semantic fragments.

- Sentence split on [.?!] + space (assert expected counts per block/language).
- Clause splits: B3 s5 ("8" | "24") and B4 s2 ("in zero - two" | "after 4s -
  fourteen") at per-language markers (one key event per fragment).
- Shot assignment per the sync analysis; per-language fit estimate from
  calibrated chars/sec; writes fragments.json.
"""

import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
SPEAK = json.loads((ROOT / "output" / "stage_k_voice" / "speak.json").read_text(encoding="utf-8"))
TIMING = json.loads((ROOT / "output" / "stage_k_voice" / "timing.json").read_text(encoding="utf-8"))

NSENT = {"B0": 4, "B1": 7, "B2": 5, "B3": 6, "B4": 4, "B5": 5, "B6": 5, "B7": 7}
# clause split: (block, sentence idx, {lang: marker to split AFTER})
CLAUSES = {
    ("B3", 4): {"ru": "восемь, ", "kk": "сегіз, ", "en": "eight, "},
    ("B4", 1): {"ru": "два, ", "kk": "екі, ", "en": "zero, "},
}
# shot -> list of sentence indices (negative = clause part: (idx, part))
SHOTS = {
    "B0": {"j0a": [0], "j0b": [1], "j0c": [2, 3]},
    "B1": {"j1a": [0], "j1b": [1, 2, 3], "j1c": [4, 5], "j1d": [6]},
    "B2": {"j2a": [0, 1], "j2b": [2], "j2c": [3, 4]},
    "B3": {"j3a": [0, 1], "j3b": [2, 3], "j3c": [(4, 0), (4, 1), 5]},
    "B4": {"j4a": [0, (1, 0), (1, 1)], "j4b": [2], "j4c": [3]},
    "B5": {"j5a": [0, 1, 2], "j5b": [3, 4]},
    "B6": {"j6a": [0, 1, 2], "j6b": [3], "j6c": [4]},
    "B7": {"j7a": [0, 1, 2], "j7b": [3, 4], "j7c": [5, 6]},
}
SHOT_DUR = {"j0a": 6, "j0b": 8, "j0c": 6, "j1a": 10, "j1b": 12, "j1c": 12,
            "j1d": 16, "j2a": 12, "j2b": 16, "j2c": 12, "j3a": 12, "j3b": 14,
            "j3c": 24, "j4a": 14, "j4b": 14, "j4c": 12, "j5a": 16, "j5b": 14,
            "j6a": 10, "j6b": 12, "j6c": 8, "j7a": 14, "j7b": 12, "j7c": 14}


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?]) ", text)
    return [p for p in parts if p]


def main() -> None:
    # calibrate speech rate per language from Stage K whole-block clips
    rate: dict[str, float] = {}
    for lang in ("ru", "kk", "en"):
        chars = sum(len(SPEAK[b][lang]) for b in SPEAK)
        total = sum(v["seconds"] for k, v in TIMING["fragments"].items()
                    if k.endswith(f"_{lang}"))
        rate[lang] = chars / total
        print(f"{lang}: {chars} chars / {total:.2f}s = {rate[lang]:.2f} chars/s")
    fragments: dict[str, dict] = {}
    print(f"\n{'shot':6s} {'dur':>5s} | " +
          " | ".join(f"{lang}: est_s (fill%)" for lang in ("ru", "kk", "en")))
    for block, shots in SHOTS.items():
        per_lang: dict[str, list] = {}
        for lang in ("ru", "kk", "en"):
            sents = sentences(SPEAK[block][lang])
            assert len(sents) == NSENT[block], (block, lang, len(sents))
            per_lang[lang] = sents
        for (bkey, idx), marker in CLAUSES.items():
            if bkey != block:
                continue
            for lang in ("ru", "kk", "en"):
                m = marker[lang]
                assert m in per_lang[lang][idx], (block, lang, idx)
                a, b = per_lang[lang][idx].split(m, 1)
                per_lang[lang][idx] = [a + m.strip(), b]
        for shot, refs in shots.items():
            est: dict[str, float] = {}
            for lang in ("ru", "kk", "en"):
                units = per_lang[lang]
                texts = [units[r[(0)]][r[1]] if isinstance(r, tuple) else units[r]
                         for r in refs]
                est[lang] = sum(len(t) for t in texts) / rate[lang]
            fills = " | ".join(
                f"{l}: {est[l]:5.2f}s ({est[l] / SHOT_DUR[shot] * 100:5.1f}%)"
                for l in ("ru", "kk", "en"))
            flag = "" if all(est[l] < SHOT_DUR[shot] * 0.9 for l in est) else \
                "  <-- TIGHT/OVER" if any(est[l] > SHOT_DUR[shot] for l in est) \
                else "  <-- snug"
            print(f"{shot:6s} {SHOT_DUR[shot]:5.0f}s | {fills}{flag}")
            for n, r in enumerate(refs, start=1):
                fid = f"{block}{shot[1:]}f{n}"
                entry: dict = {"block": block, "shot": shot}
                for lang in ("ru", "kk", "en"):
                    units = per_lang[lang]
                    entry[lang] = units[r[0]][r[1]] if isinstance(r, tuple) else units[r]
                fragments[fid] = entry
    # lossless check: fragments concatenated per block == speak text
    for block in SHOTS:
        for lang in ("ru", "kk", "en"):
            got = " ".join(fragments[f][lang] for f in sorted(fragments)
                           if fragments[f]["block"] == block)
            # clause rejoins need ", " not " " fix-up: our split kept "X," + " Y"
            want = SPEAK[block][lang]
            assert got.replace(",  ", ", ") == want, (block, lang, got[:120])
    out = ROOT / "output" / "stage_k2_fragments" / "fragments.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(fragments, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {out} ({len(fragments)} fragments x 3 langs)")


if __name__ == "__main__":
    main()
