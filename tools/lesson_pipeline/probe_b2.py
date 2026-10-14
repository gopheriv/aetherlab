"""One-off: which BlockB2 event exceeds its literal run_time?"""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
sys.path.insert(0, str(ROOT))
from aetherlab.services.scene_preflight import preflight_scene  # noqa: E402

code = (ROOT / "output" / "stage_l_scenes" / "lesson_ru.py").read_text(encoding="utf-8")
lines = code.splitlines()
rep = preflight_scene(code, "BlockB2")

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

print(f"ran={rep.ran} ok={rep.ok} total={rep.duration_s}")
for line, s, e in rep.events:
    src = lines[line - 1].strip() if 0 < line <= len(lines) else "?"
    print(f"L{line}: {e - s:.3f}s  {src[:90]}")
