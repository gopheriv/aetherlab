"""Build a self-contained contact-sheet HTML fragment for Stage L frame review.

Reads output/stage_l_preview/frames/*.png, embeds them as data URIs
(full 1280x720, they are small), writes .qwen/tmp/contact_sheet.html
(body-only fragment for the Artifact tool).
"""

import base64
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
FRAMES = ROOT / "output" / "stage_l_preview" / "frames"
OUT = ROOT / ".qwen" / "tmp" / "contact_sheet.html"

BLOCKS = ["BlockB0", "BlockB1", "BlockB2", "BlockB3",
          "BlockB4", "BlockB5", "BlockB6", "BlockB7"]
TIMES = {"BlockB0": [2, 14, 19], "BlockB1": [2, 16, 49], "BlockB2": [2, 20, 39],
         "BlockB3": [2, 38, 49], "BlockB4": [2, 21, 39], "BlockB5": [2, 12, 29],
         "BlockB6": [2, 16, 29], "BlockB7": [2, 20, 39]}

parts = ["""<style>
.sheet{font-family:system-ui,sans-serif;max-width:1400px;margin:0 auto;padding:16px;
background:#111;color:#eee}
.sheet h2{margin:28px 0 8px;font-size:20px}
.sheet .row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.sheet figure{margin:0;background:#000;border:1px solid #333;border-radius:8px;overflow:hidden}
.sheet img{width:100%;display:block}
.sheet figcaption{padding:6px 10px;font-size:13px;color:#bbb}
.sheet .legend{font-size:14px;color:#ccc}
</style>
<div class="sheet">
<h1>Stage L — preview frames (ru, 720p), blocks B0–B2</h1>
<p class="legend">first / key-transformation / final per block. Check: overlaps,
readability of captions/formulas at 720p, disappearing objects, wrong numbers.</p>"""]

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

for block in BLOCKS:
    parts.append(f"<h2>{block}</h2><div class='row'>")
    for t in TIMES[block]:
        name = f"{block}_t{t:02d}.png"
        raw = (FRAMES / name).read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        parts.append(
            f"<figure><img src='data:image/png;base64,{b64}' alt='{name}'/>"
            f"<figcaption>{name} — t={t}s</figcaption></figure>")
    parts.append("</div>")

parts.append("</div>")
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
