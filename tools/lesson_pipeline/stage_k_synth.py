"""Stage K: synthesize + measure narration fragments (kk/ru/en x B0-B7).

Uses aetherlab.services.voiceover (edge-tts + edge-silence trim + PyAV measure).
Writes output/stage_k_voice/speak.json, clips/<block>_<lang>.mp3,
samples/<lang>.mp3, timing.json. Fails loudly on missing voices/clips.
"""

import asyncio
import json
import re
import shutil
from pathlib import Path

from aetherlab.services import voiceover as vo

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
CANON = json.loads((ROOT / "output" / "stage_f_content" / "canonical.json").read_text(encoding="utf-8"))
OUT = ROOT / "output" / "stage_k_voice"
CLIPS = OUT / "clips"
CACHE = OUT / "cache"

VOICES = {"kk": "kk-KZ-AigulNeural", "ru": "ru-RU-SvetlanaNeural", "en": "en-US-AndrewMultilingualNeural"}
VO_KEY = {"ru": "voiceover_ru", "kk": "voiceover_kk", "en": "voiceover_en"}
RATE = "+0%"

# Pronunciation text: standalone Latin symbols -> Cyrillic letter names (kk/ru).
SPEAK_SUB = {"v": "вэ", "s": "эс", "t": "тэ", "a": "а"}
LATIN_LETTER = re.compile(r"\b([vsta])\b")

SAMPLES = {
    "ru": "Вэ равно эс делить на тэ. А равно трём. Метр на секунду в квадрате. Задачи ЕНТ.",
    "kk": "Вэ тең эс бөлінген тэ. А үшке тең. Метр секундына квадрат. ҰБТ сынақтары.",
    "en": "V equals s over t. A equals three. Metres per second squared. UNT mocks.",
}


def speak_text(lang: str, text: str) -> str:
    if lang == "en":
        return text
    out = LATIN_LETTER.sub(lambda m: SPEAK_SUB[m.group(1)], text)
    assert not re.search(r"[A-Za-z]", out), f"latin left in {lang}: {out!r}"
    return out


async def synth_retry(text: str, voice: str, tag: str):
    """synthesize_cached with retries: edge-tts websockets flap 403 often."""
    last = None
    for attempt in range(4):
        last = await vo.synthesize_cached(text, CACHE, voice, RATE)
        if last is not None:
            return last
        await asyncio.sleep(2.0 * (attempt + 1))
    assert last is not None, f"synth failed after retries: {tag}"
    return last


async def main() -> None:
    import edge_tts

    names = {v["ShortName"] for v in await edge_tts.list_voices()}
    for lang, voice in VOICES.items():
        assert voice in names, f"voice missing: {voice}"
    print("voices ok:", ", ".join(VOICES.values()))

    OUT.mkdir(exist_ok=True)
    (OUT / "samples").mkdir(exist_ok=True)
    CLIPS.mkdir(exist_ok=True)

    speak: dict[str, dict[str, str]] = {}
    for b in CANON["blocks"]:
        speak[b["id"]] = {lang: speak_text(lang, b[VO_KEY[lang]]) for lang in VOICES}
    (OUT / "speak.json").write_text(json.dumps(speak, ensure_ascii=False, indent=1), encoding="utf-8")

    timing: dict[str, dict] = {"rate": RATE, "voices": VOICES, "samples": {}, "fragments": {}}

    for lang, text in SAMPLES.items():
        path = await synth_retry(text, VOICES[lang], f"sample/{lang}")
        dst = OUT / "samples" / f"{lang}.mp3"
        shutil.copyfile(path, dst)
        dur = await vo.get_duration(dst)
        assert dur > 0.5, f"sample too short: {lang} {dur}"
        timing["samples"][lang] = {"file": dst.name, "seconds": round(dur, 2)}
        print(f"sample {lang}: {dur:.2f}s")

    for b in CANON["blocks"]:
        for lang in VOICES:
            path = await synth_retry(speak[b["id"]][lang], VOICES[lang], f"{b['id']}/{lang}")
            dst = CLIPS / f"{b['id']}_{lang}.mp3"
            shutil.copyfile(path, dst)
            dur = await vo.get_duration(dst)
            assert dur > 1.0, f"clip too short: {b['id']}/{lang} {dur}"
            timing["fragments"][f"{b['id']}_{lang}"] = {
                "file": dst.name, "seconds": round(dur, 2)}
            print(f"{b['id']}_{lang}: {dur:.2f}s")

    (OUT / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=1), encoding="utf-8")
    print("timing.json written")


asyncio.run(main())
