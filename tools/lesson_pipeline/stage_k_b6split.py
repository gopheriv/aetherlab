"""Stage K fix: split B6 narration into condition (B6a) + answer (B6b).

The B6 pause card needs real think-time silence between prompt and answer,
so the two parts are synthesized separately and the mux gap is computed from
measured durations. Appends b6_split to timing.json.
"""

import asyncio
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"C:\Users\sunak\Projects\aetherlab\.qwen\tmp")))
from stage_k_synth import VOICES, RATE  # noqa: E402

from aetherlab.services import voiceover as vo

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
OUT = ROOT / "output" / "stage_k_voice"
CACHE = OUT / "cache"
CLIPS = OUT / "clips"

ANSWER_HEAD = {"kk": "Жауабы:", "ru": "Ответ:", "en": "Answer:"}
B6_BUDGET = 30.0
EDGE_BREATH = 1.0  # silence kept at both block edges


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

async def synth_retry(text: str, voice: str, tag: str):
    last = None
    for attempt in range(4):
        last = await vo.synthesize_cached(text, CACHE, voice, RATE)
        if last is not None:
            return last
        await asyncio.sleep(2.0 * (attempt + 1))
    raise AssertionError(f"synth failed after retries: {tag}")


async def main() -> None:
    speak = json.loads((OUT / "speak.json").read_text(encoding="utf-8"))
    timing = json.loads((OUT / "timing.json").read_text(encoding="utf-8"))
    split: dict[str, dict] = {}
    for lang in VOICES:
        head = ANSWER_HEAD[lang]
        assert head in speak["B6"][lang], f"no answer head in B6/{lang}"
        part1, part2 = re.split(re.escape(head), speak["B6"][lang], maxsplit=1)
        part1, part2 = part1.strip(), f"{head} {part2.strip()}"
        durs = {}
        for tag, text in (("a", part1), ("b", part2)):
            path = await synth_retry(text, VOICES[lang], f"B6{tag}/{lang}")
            dst = CLIPS / f"B6{tag}_{lang}.mp3"
            shutil.copyfile(path, dst)
            dur = await vo.get_duration(dst)
            assert dur > 1.0, f"clip too short: B6{tag}/{lang}"
            durs[tag] = round(dur, 2)
        gap = round(B6_BUDGET - 2 * EDGE_BREATH - durs["a"] - durs["b"], 2)
        assert gap >= 4.0, f"B6/{lang}: think gap only {gap}s"
        split[lang] = {"B6a_s": durs["a"], "gap_s": gap,
                       "B6b_s": durs["b"], "edge_breath_s": EDGE_BREATH}
        print(f"B6/{lang}: a={durs['a']}s gap={gap}s b={durs['b']}s")
    timing["b6_split"] = split
    (OUT / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=1), encoding="utf-8")
    print("timing.json updated with b6_split")


asyncio.run(main())
