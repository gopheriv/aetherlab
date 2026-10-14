"""Full-scan glitch probe: decode EVERY frame of each preview mp4 and report:
- near-black frames (mean < 2.0) outside t<0.3 (fade-from-black heads)
- exact-duplicate runs >= 3 frames inside planned MOTION windows (freezes)
- singleton flash frames (diff spike vs both neighbours)
- max diff in +/-0.5 s of every shot boundary (pops/flashes/freezes)
"""

import hashlib
from pathlib import Path

import av
import numpy as np

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
PREVIEW = ROOT / "output" / "stage_l_preview"

PLAN = {
    "BlockB0": [(0, 2, "m"), (2, 6, "s"), (6, 14, "m"), (14, 16, "m"), (16, 20, "s")],
    "BlockB1": [(0, 2, "m"), (2, 3.5, "m"), (3.5, 4, "s"), (4, 5.5, "m"),
                (5.5, 6, "s"), (6, 7.5, "m"), (7.5, 8, "s"), (8, 9.5, "m"),
                (9.5, 10, "s"), (10, 12.5, "m"), (12.5, 13, "s"),
                (13, 15.5, "m"), (15.5, 16, "s"), (16, 18.5, "m"),
                (18.5, 19, "s"), (19, 21.5, "m"), (21.5, 22, "s"),
                (22, 31, "m"), (31, 34, "s"), (34, 44, "m"), (44, 50, "s")],
    "BlockB2": [(0, 12, "m"), (12, 19, "m"), (19, 28, "s"), (28, 35, "m"),
                (35, 40, "s")],
    "BlockB3": [(0, 8, "m"), (8, 12, "s"), (12, 23, "m"), (23, 26, "s"),
                (26, 48, "m"), (48, 50, "s")],
    "BlockB4": [(0, 14, "m"), (14, 26, "m"), (26, 28, "s"), (28, 32, "m"),
                (32, 40, "s")],
    "BlockB5": [(0, 16, "m"), (16, 21, "m"), (21, 30, "s")],
    "BlockB6": [(0, 4, "m"), (4, 10, "s"), (10, 19, "m"), (19, 22, "s"),
                (22, 26, "m"), (26, 30, "s")],
    "BlockB7": [(0, 12, "m"), (12, 14, "s"), (14, 24, "m"), (24, 26, "s"),
                (26, 36, "m"), (36, 40, "s")],
}


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

def kind_at(plan, t):
    kinds = {k for (a, b, k) in plan if a < t <= b + 1e-9}
    return kinds


def scan(name):
    means, diffs, hashes = [], [], []
    prev = None
    with av.open(str(PREVIEW / f"{name}.mp4")) as container:
        video = next(s for s in container.streams if s.type == "video")
        fps = float(video.average_rate)
        for frame in container.decode(video):
            a = frame.to_ndarray(format="gray")[::8, ::8].astype(np.float32)
            means.append(float(a.mean()))
            h = hashlib.md5(a.tobytes()).hexdigest()
            hashes.append(h)
            if prev is not None:
                diffs.append(float(np.mean(np.abs(a - prev))))
            prev = a
    n = len(means)
    print(f"{name}: {n} frames", flush=True)
    # black frames past the head fade
    blacks = [i for i, m in enumerate(means) if m < 2.0 and i / fps > 0.5]
    print(f"  near-black frames after t=0.5s: "
          f"{[round(i / fps, 2) for i in blacks][:20] or 'none'}")
    # duplicate runs in motion windows
    run_start, i = 0, 1
    froze = []
    while i < n:
        if hashes[i] == hashes[i - 1]:
            i += 1
            continue
        run = i - run_start
        if run >= 3:
            t0, t1 = run_start / fps, (i - 1) / fps
            mid = (t0 + t1) / 2
            if kind_at(PLAN[name], mid) == {"m"}:
                froze.append((round(t0, 2), round(t1, 2), run))
        run_start = i
        i += 1
    print(f"  duplicate runs>=3 in motion windows: {froze or 'none'}")
    # flash singletons
    med = float(np.median(diffs)) if diffs else 0.0
    flashes = [i for i in range(1, len(diffs) - 1)
               if diffs[i] > max(med * 15, 0.01)
               and diffs[i + 1] > max(med * 15, 0.01)]
    print(f"  flash singletons (med diff={med:.5f}): "
          f"{[round(i / fps, 2) for i in flashes][:20] or 'none'}")
    # boundaries
    bounds = sorted({a for (a, _, _) in PLAN[name][1:]} |
                    {b for (_, b, _) in PLAN[name][:-1]})
    for b in bounds:
        lo, hi = int((b - 0.5) * fps), int((b + 0.5) * fps)
        window = diffs[max(lo, 0):min(hi, len(diffs))]
        print(f"  boundary t={b:5.1f}: maxdiff={max(window):.5f} "
              f"meandiff={float(np.mean(window)):.5f}")


for name in PLAN:
    scan(name)
