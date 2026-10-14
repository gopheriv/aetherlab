"""One-off: which BlockB2 event exceeds its literal run_time?"""

if __package__:
    from ._console import configure_utf8_stdio
else:
    from _console import configure_utf8_stdio

configure_utf8_stdio()

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
sys.path.insert(0, str(ROOT))
from aetherlab.services.scene_preflight import preflight_scene  # noqa: E402

code = (ROOT / "output" / "stage_l_scenes" / "lesson_ru.py").read_text(encoding="utf-8")
lines = code.splitlines()
rep = preflight_scene(code, "BlockB2")
print(f"ran={rep.ran} ok={rep.ok} total={rep.duration_s}")
for line, s, e in rep.events:
    src = lines[line - 1].strip() if 0 < line <= len(lines) else "?"
    print(f"L{line}: {e - s:.3f}s  {src[:90]}")
