"""List kk-/ru-/en-neural voices actually offered by edge-tts right now."""

import asyncio
import json

import edge_tts


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

async def main() -> None:
    voices = await edge_tts.list_voices()
    keep = [v for v in voices
            if v.get("Locale", "").startswith(("kk", "ru-RU", "en-US"))]
    rows = sorted((v["Locale"], v["Name"], v.get("Gender", "?")) for v in keep)
    print(json.dumps(rows, ensure_ascii=False, indent=1))


asyncio.run(main())
