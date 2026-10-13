"""Dump word timings for key fragments to place numeric events."""
import json

W = json.load(open("output/stage_k2_fragments/words.json", encoding="utf-8"))

# fragment -> substrings of interest (per lang where needed)
SHOW = {
    "B00bf1": None,  # full: find fourteen
    "B11af1": None,  # full: formula recitation
    "B22bf1": None,  # fourteen
    "B33bf1": None,  # term names
    "B33cf1": None,  # eight
    "B33cf2": None,  # twenty four
    "B33cf3": None,  # thirty two
    "B44af2": None,  # two
    "B44af3": None,  # fourteen
    "B55af3": None,  # two/fourteen/four/eight/thirty two
    "B77af2": None,  # fifty six
    "B77cf1": None,  # formula names x3
}

for fid in SHOW:
    for lang in ("ru", "kk", "en"):
        words = " ".join(f"{w}[{t0}-{t1}]" for w, t0, t1 in W[fid][lang])
        print(f"{fid}/{lang}: {words}")
    print()
