"""Stage K2: synthesize + measure per-shot speech fragments (45 x kk/ru/en).

Reuses Stage K machinery (edge-tts voices/rate, synthesize_cached, trim,
PyAV measure, 4-attempt retry). Reads output/stage_k2_fragments/fragments.json
(authored clause splits of speak.json; lossless join verified by the generator).
Writes clips/<frag>_<lang>.mp3 + durations.json (+ fit table vs shot durs).
Skips fragments whose clip already exists (resume by deleting files).
"""

import asyncio
import json
import shutil
from pathlib import Path

from aetherlab.services import voiceover as vo

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
OUT = ROOT / "output" / "stage_k2_fragments"
CLIPS = OUT / "clips"
CACHE = OUT / "cache"
FRAGMENTS = json.loads((OUT / "fragments.json").read_text(encoding="utf-8"))

VOICES = {"kk": "kk-KZ-AigulNeural", "ru": "ru-RU-SvetlanaNeural", "en": "en-US-AndrewMultilingualNeural"}
RATE = "+0%"
LANGS = ("ru", "kk", "en")
SHOT_DUR = {"j0a": 6, "j0b": 8, "j0c": 6, "j1a": 10, "j1b": 12, "j1c": 12,
            "j1d": 16, "j2a": 12, "j2b": 16, "j2c": 12, "j3a": 12, "j3b": 14,
            "j3c": 24, "j4a": 14, "j4b": 14, "j4c": 12, "j5a": 16, "j5b": 14,
            "j6a": 10, "j6b": 12, "j6c": 8, "j7a": 14, "j7b": 12, "j7c": 14}


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

async def synth_retry(text: str, voice: str, tag: str):
    last = None
    for attempt in range(10):
        last = await vo.synthesize_cached(text, CACHE, voice, RATE)
        if last is not None:
            return last
        await asyncio.sleep(min(5.0 * (attempt + 1), 30.0))
    assert last is not None, f"synth failed after retries: {tag}"
    return last


async def main() -> None:
    import edge_tts

    names = {v["ShortName"] for v in await edge_tts.list_voices()}
    for lang, voice in VOICES.items():
        assert voice in names, f"voice missing: {voice}"
    print("voices ok", flush=True)
    CLIPS.mkdir(exist_ok=True)

    durations: dict[str, dict[str, float]] = {}
    total = len(FRAGMENTS) * len(LANGS)
    done = 0
    for fid, entry in sorted(FRAGMENTS.items()):
        durations[fid] = {}
        for lang in LANGS:
            dst = CLIPS / f"{fid}_{lang}.mp3"
            if not dst.is_file():
                path = await synth_retry(entry[lang], VOICES[lang], f"{fid}/{lang}")
                shutil.copyfile(path, dst)
                await asyncio.sleep(1.5)  # pace requests: rapid-fire trips 403s
            dur = await vo.get_duration(dst)
            assert dur > 0.4, f"clip too short: {fid}/{lang} {dur}"
            durations[fid][lang] = round(dur, 2)
            done += 1
            if done % 10 == 0 or done == total:
                print(f"progress {done}/{total}", flush=True)
    (OUT / "durations.json").write_text(
        json.dumps({"rate": RATE, "voices": VOICES, "durations": durations},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'shot':6s} {'dur':>5s} | fit ru/kk/en (speech s vs shot)", flush=True)
    for shot in SHOT_DUR:
        fills = []
        for lang in LANGS:
            s = sum(durations[f][lang] for f in durations
                    if FRAGMENTS[f]["shot"] == shot)
            fills.append(f"{lang}:{s:5.2f}s/{s / SHOT_DUR[shot] * 100:5.1f}%")
        flag = "" if all(
            sum(durations[f][l] for f in durations if FRAGMENTS[f]["shot"] == shot)
            < SHOT_DUR[shot] for l in LANGS) else "  <-- OVERFLOW"
        print(f"{shot:6s} {SHOT_DUR[shot]:5.0f}s | {' '.join(fills)}{flag}", flush=True)
    print("durations.json written", flush=True)


asyncio.run(main())
