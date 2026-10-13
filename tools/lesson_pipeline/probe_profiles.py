"""Profile probe: row/column brightness profiles + bright-mass bbox for each
review frame. Compact ground truth for layout-vs-scenario comparison."""

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
FRAMES = ROOT / "output" / "stage_l_preview" / "frames"
TIMES = {"BlockB0": [2, 14, 19], "BlockB1": [2, 16, 49],
         "BlockB2": [2, 20, 39], "BlockB3": [2, 38, 49],
         "BlockB4": [2, 21, 39], "BlockB5": [2, 12, 29],
         "BlockB6": [2, 16, 29], "BlockB7": [2, 20, 39]}


def prof(v: np.ndarray, n: int) -> str:
    b = np.array_split(v, n)
    m = np.array([x.mean() for x in b])
    scale = m.max() if m.max() > 0 else 1.0
    return "".join(str(min(int(x / scale * 9.999), 9)) for x in m)


lines = []
for block, times in TIMES.items():
    for t in times:
        name = f"{block}_t{t:02d}.png"
        a = np.asarray(Image.open(FRAMES / name).convert("L"), dtype=np.float32)
        bright = a > 60
        ys, xs = np.nonzero(bright)
        if len(ys):
            bbox = (f"x[{np.percentile(xs, 5):.0f}-{np.percentile(xs, 95):.0f}] "
                    f"y[{np.percentile(ys, 5):.0f}-{np.percentile(ys, 95):.0f}] "
                    f"n={len(ys)}")
        else:
            bbox = "EMPTY"
        lines.append(f"{name}: {bbox}")
        lines.append(f"  rows36: {prof(a.mean(axis=1), 36)}")
        lines.append(f"  cols64: {prof(a.mean(axis=0), 64)}")
out = ROOT / ".qwen" / "tmp" / "frame_profiles.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out}")
