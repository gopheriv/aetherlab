"""K2 word-timing probe: capture edge-tts WordBoundary offsets for key fragments.

Streams (not synthesize_cached: boundaries come from Communicate.stream).
Dumps output/stage_k2_fragments/words.json: {frag: {lang: [(word, t0, t1)]}}.
Retries each stream (edge-tts 403 flap) with backoff; resumes by frag.
"""

import asyncio
import json
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
FRAGMENTS = json.loads((ROOT / "output" / "stage_k2_fragments" / "fragments.json").read_text(encoding="utf-8"))
OUT = ROOT / "output" / "stage_k2_fragments" / "words.json"

VOICES = {"kk": "kk-KZ-AigulNeural", "ru": "ru-RU-SvetlanaNeural", "en": "en-US-AndrewMultilingualNeural"}
KEY = ["B00bf1", "B11af1", "B22bf1", "B33bf1", "B33cf1", "B33cf2", "B33cf3",
       "B44af2", "B44af3", "B55af3", "B77af2", "B77cf1"]
LANGS = ("ru", "kk", "en")


async def stream_words(text: str, voice: str, tag: str):
    import edge_tts

    last_exc = None
    for attempt in range(10):
        try:
            words = []
            async for msg in edge_tts.Communicate(
                    text, voice, boundary="WordBoundary").stream():
                if msg.get("type") == "WordBoundary":
                    t0 = msg["offset"] / 10_000_000
                    words.append((msg["text"], round(t0, 2),
                                  round(t0 + msg["duration"] / 10_000_000, 2)))
            assert words, f"no boundaries: {tag}"
            return words
        except Exception as exc:  # noqa: BLE001 - 403 flap, retry
            last_exc = exc
            await asyncio.sleep(min(5.0 * (attempt + 1), 30.0))
    raise RuntimeError(f"stream failed: {tag}: {last_exc}")


async def main() -> None:
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    total = len(KEY) * len(LANGS)
    n = sum(len(v) for v in done.values())
    for fid in KEY:
        done.setdefault(fid, {})
        for lang in LANGS:
            if lang in done[fid]:
                continue
            done[fid][lang] = await stream_words(
                FRAGMENTS[fid][lang], VOICES[lang], f"{fid}/{lang}")
            await asyncio.sleep(1.5)
            n += 1
            if n % 6 == 0 or n == total:
                print(f"progress {n}/{total}", flush=True)
    OUT.write_text(json.dumps(done, ensure_ascii=False, indent=0), encoding="utf-8")
    print("words.json written", flush=True)


asyncio.run(main())
