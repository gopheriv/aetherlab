"""Absolute regional brightness probe: are stamps/checks/plus glyphs present?

Reports mean/max gray values in small regions where B2/B5 stamps, B7 bridge
check, B1 plus must be visible, plus dark/bright controls. Presence = max>>30.
"""

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
FRAMES = ROOT / "output" / "stage_l_preview" / "frames"

# (frame, x0, x1, y0, y1, label)
REGIONS = [
    ("BlockB2_t39.png", 1020, 1140, 520, 600, "B2 stamp (4.9,-2.2)"),
    ("BlockB5_t29.png", 990, 1120, 465, 545, "B5 stamp (4.3,-1.6)"),
    ("BlockB7_t39.png", 580, 700, 520, 600, "B7 bridge (0,-2.2)"),
    ("BlockB1_t49.png", 1010, 1110, 465, 525, "B1 plus (4.6,-1.5)"),
    ("BlockB7_t39.png", 50, 200, 600, 700, "CONTROL dark corner"),
    ("BlockB7_t39.png", 300, 980, 115, 170, "CONTROL cap2 text row"),
    ("BlockB4_t21.png", 990, 1120, 270, 340, "B4 aval half-fade (4.3,0.6)"),
]


def main() -> None:
    for frame, x0, x1, y0, y1, label in REGIONS:
        a = np.asarray(Image.open(FRAMES / frame).convert("L"), dtype=np.float32)
        crop = a[y0:y1, x0:x1]
        print(f"{label:28s} mean={crop.mean():7.2f} max={crop.max():6.1f} "
              f"bright_px(>60)={int((crop > 60).sum())}")


if __name__ == "__main__":
    main()
