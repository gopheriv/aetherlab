"""Layout probe: what objects are visible in each review frame, and where.

For each first/key/final review PNG, prints:
 1. bright-blob bounding boxes on a 16x9 coarse grid (connected components),
 2. a compact ASCII brightness map (64x36).
Lets a vision-less reviewer verify layout vs the Stage J scenario.
"""

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
FRAMES = ROOT / "output" / "stage_l_preview" / "frames"
TIMES = {"BlockB0": [2, 14, 19], "BlockB1": [2, 16, 49],
         "BlockB2": [2, 20, 39], "BlockB3": [2, 38, 49],
         "BlockB4": [2, 21, 39], "BlockB5": [2, 12, 29],
         "BlockB6": [2, 16, 29], "BlockB7": [2, 20, 39]}
RAMP = " .:+#@"


def blobs(arr: np.ndarray) -> list[str]:
    mask = arr > 60
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            if not mask[y, x] or seen[y // 8 * (w // 8) + x // 8] if False else False:
                pass
    # flood fill on downsampled mask
    small = mask[::16, ::16]
    sh, sw = small.shape
    seen = np.zeros_like(small, dtype=bool)
    comps = []
    for y in range(sh):
        for x in range(sw):
            if small[y, x] and not seen[y, x]:
                stack = [(y, x)]
                seen[y, x] = True
                cells = []
                while stack:
                    cy, cx = stack.pop()
                    cells.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < sh and 0 <= nx < sw \
                                    and small[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True
                                stack.append((ny, nx))
                if len(cells) >= 3:
                    ys = [c[0] for c in cells]
                    xs = [c[1] for c in cells]
                    comps.append((min(ys), min(xs), max(ys), max(xs), len(cells)))
    # map to 16x9 grid labels
    for (y0, x0, y1, x1, n) in sorted(comps, key=lambda c: -c[4])[:12]:
        gx0, gx1 = x0 * 16 // sw, x1 * 16 // sw
        gy0, gy1 = y0 * 9 // sh, y1 * 9 // sh
        out.append(f"grid x[{gx0}-{gx1}] y[{gy0}-{gy1}] cells={n}")
    return out


def ascii_map(arr: np.ndarray) -> list[str]:
    img = Image.fromarray(arr).resize((64, 36), Image.BILINEAR)
    a = np.asarray(img, dtype=np.float32)
    lines = []
    for row in a:
        lines.append("".join(RAMP[min(int(v / 256 * len(RAMP)), len(RAMP) - 1)]
                             for v in row))
    return lines


report = []
for block, times in TIMES.items():
    for t in times:
        name = f"{block}_t{t:02d}.png"
        arr = np.asarray(Image.open(FRAMES / name).convert("L"))
        report.append(f"===== {name} =====")
        report.append("blobs:")
        report.extend("  " + b for b in blobs(arr))
        report.append("map:")
        report.extend(ascii_map(arr))
        report.append("")
out = ROOT / ".qwen" / "tmp" / "ascii_frames.txt"
out.write_text("\n".join(report), encoding="utf-8")
print(f"wrote {out} ({len(report)} lines)")
