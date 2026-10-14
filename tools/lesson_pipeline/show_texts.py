"""Print ru speak sentences + captions per block to map events to fragments."""
import json
import re

ROOT = "C:/Users/sunak/Projects/aetherlab"
canon = json.load(open(f"{ROOT}/output/stage_f_content/canonical.json", encoding="utf-8"))
speak = json.load(open(f"{ROOT}/output/stage_k_voice/speak.json", encoding="utf-8"))
frags = json.load(open(f"{ROOT}/output/stage_k2_fragments/fragments.json", encoding="utf-8"))

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

for b in canon["blocks"]:
    bid = b["id"]
    print(f"===== {bid} =====")
    print("caps:", b["captions"])
    sents = re.split(r"(?<=[.!?]) ", speak[bid]["ru"])
    for i, s in enumerate(sents):
        print(f"  s{i}: {s}")
    print("  frag->shot:", sorted({(v['shot'], k) for k, v in frags.items()
                                   if v['block'] == bid}))
