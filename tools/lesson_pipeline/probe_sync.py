"""Probe Stage L preview mp4s for timing/sync defects.

1. Motion-profile check: decode each video, compute mean abs frame diff at
   2 samples/s; compare against planned motion/still intervals derived from
   the template's run_times. A motion window with no motion (or a still
   window with motion) = sync bug.
2. Caption-band steps: bright-pixel fraction in top 15% of frame; prints
   times of big changes vs planned caption fades.
3. Seek-accuracy check: `-ss` before -i (used for review frames) vs `-ss`
   after -i at the key-frame times; differing hashes = mistimed review frames.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import av
import imageio_ffmpeg
import numpy as np

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
PREVIEW = ROOT / "output" / "stage_l_preview"

# (start, end, kind) block-local seconds from lesson_template.py run_times.
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
KEY_T = {"BlockB0": 14, "BlockB1": 16, "BlockB2": 20, "BlockB3": 38,
         "BlockB4": 21, "BlockB5": 12, "BlockB6": 16, "BlockB7": 20}


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

def motion_profile(path: Path) -> tuple[list, list, float]:
    """Return (diffs, captions, fps): per-0.5s mean-abs-diff and top-band
    bright fraction."""
    diffs, caps = [], []
    with av.open(str(path)) as container:
        video = next(s for s in container.streams if s.type == "video")
        fps = float(video.average_rate)
        step = round(fps / 2)
        prev = None
        for i, frame in enumerate(container.decode(video)):
            if i % step:
                continue
            arr = frame.to_ndarray(format="gray")
            small = np.asarray(bytearray(arr.tobytes())).reshape(arr.shape)
            small = small[::8, ::8].astype(np.float32) / 255.0
            if prev is not None:
                diffs.append(float(np.mean(np.abs(small - prev))))
            prev = small
            top = arr[: arr.shape[0] * 15 // 100, :]
            caps.append(float(np.mean(top > 128)))
    return diffs, caps, fps


def check_block(name: str) -> list[str]:
    problems: list[str] = []
    diffs, caps, fps = motion_profile(PREVIEW / f"{name}.mp4")
    print(f"{name}: {len(diffs)} samples, fps={fps:.2f}", flush=True)
    # noise floor = median diff inside planned still windows
    still_d, motion_d = [], []
    for k, d in enumerate(diffs):
        t = (k + 1) * 0.5
        kinds = {kind for (a, b, kind) in PLAN[name] if a < t <= b}
        if kinds == {"s"}:
            still_d.append(d)
        elif kinds == {"m"}:
            motion_d.append(d)
    floor = float(np.median(still_d)) if still_d else 0.0
    thr = max(floor * 5, 0.0015)
    print(f"  still: n={len(still_d)} median={floor:.5f} max={max(still_d or [0]):.5f} "
          f"| motion: n={len(motion_d)} median={np.median(motion_d) if motion_d else 0:.5f} "
          f"min={min(motion_d) if motion_d else 0:.5f} | thr={thr:.5f}")
    for k, d in enumerate(diffs):
        t = (k + 1) * 0.5
        kinds = {kind for (a, b, kind) in PLAN[name] if a < t <= b}
        if kinds == {"m"} and d < thr:
            problems.append(f"{name} t={t:4.1f}s: NO MOTION in planned animation window (diff={d:.5f})")
        elif kinds == {"s"} and d > thr * 4:
            problems.append(f"{name} t={t:4.1f}s: MOTION in planned still window (diff={d:.5f})")
    # caption-band steps
    prev_c = caps[0]
    steps = []
    for k, c in enumerate(caps[1:], start=1):
        if abs(c - prev_c) > 0.004:
            steps.append((k * 0.5, prev_c, c))
            prev_c = c
    print(f"  caption-band steps (>0.004): " +
          ", ".join(f"t={t:.1f} {a:.3f}->{b:.3f}" for t, a, b in steps))
    return problems


def seek_check(name: str) -> str:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video = str(PREVIEW / f"{name}.mp4")
    t = KEY_T[name]
    tmp = ROOT / ".qwen" / "tmp" / "probe_frames"
    tmp.mkdir(exist_ok=True)
    p1, p2 = tmp / f"{name}_fast.png", tmp / f"{name}_acc.png"
    r1 = subprocess.run([ffmpeg, "-y", "-ss", str(t), "-i", video,
                         "-frames:v", "1", str(p1)],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=120)
    r2 = subprocess.run([ffmpeg, "-y", "-i", video, "-ss", str(t),
                         "-frames:v", "1", str(p2)],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=180)
    assert r1.returncode == 0 and r2.returncode == 0, (r1.stderr[-300:], r2.stderr[-300:])
    h1 = hashlib.md5(p1.read_bytes()).hexdigest()[:12]
    h2 = hashlib.md5(p2.read_bytes()).hexdigest()[:12]
    verdict = "SAME" if h1 == h2 else "DIFFERENT <-- review frames mistimed?"
    return f"{name} t={t}: input-seek vs accurate-seek: {verdict} ({h1} vs {h2})"


def main() -> None:
    all_problems: list[str] = []
    for name in PLAN:
        all_problems.extend(check_block(name))
    print("\n--- motion/still verdict ---")
    if all_problems:
        print(f"{len(all_problems)} anomalies:")
        for p in all_problems:
            print(" ", p)
    else:
        print("no motion/still anomalies: animation runs exactly in planned windows")
    print("\n--- seek accuracy ---")
    for name in PLAN:
        print(seek_check(name))


if __name__ == "__main__":
    main()
