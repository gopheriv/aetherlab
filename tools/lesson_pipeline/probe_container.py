"""Container-level sync probe: exact frame counts, PTS start/monotonicity/gaps,
keyframe interval, stream params. Any deviation = real render sync defect."""

if __package__:
    from ._console import configure_utf8_stdio
else:
    from _console import configure_utf8_stdio

configure_utf8_stdio()


from pathlib import Path

import av

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
PREVIEW = ROOT / "output" / "stage_l_preview"
BUDGETS = {"BlockB0": 20, "BlockB1": 50, "BlockB2": 40, "BlockB3": 50,
           "BlockB4": 40, "BlockB5": 30, "BlockB6": 30, "BlockB7": 40}


def probe(name: str) -> None:
    path = PREVIEW / f"{name}.mp4"
    expected = BUDGETS[name] * 30
    with av.open(str(path)) as container:
        video = next(s for s in container.streams if s.type == "video")
        n, first_pts, prev_pts, gaps, non_key_first = 0, None, None, 0, 0
        key_idx = []
        for frame in container.decode(video):
            pts_s = float(frame.pts * video.time_base) if frame.pts is not None else None
            if first_pts is None:
                first_pts = pts_s
                first_key = frame.key_frame
            if pts_s is not None and prev_pts is not None and pts_s - prev_pts > 1.5 / 30:
                gaps += 1
            prev_pts = pts_s
            if frame.key_frame:
                key_idx.append(n)
            n += 1
    last_pts = prev_pts
    status = "OK" if n == expected else f"MISMATCH (expected {expected})"
    print(f"{name}: frames={n} {status} first_pts={first_pts} last_pts={last_pts} "
          f"gaps={gaps} first_is_key={first_key} keyframes={len(key_idx)} "
          f"key_every~{key_idx[1]-key_idx[0] if len(key_idx) > 1 else '?'}")
    if n != expected:
        print(f"  <-- FRAME COUNT OFF BY {n - expected}")


for name in BUDGETS:
    probe(name)
