"""Language choices shared by lessons, exam practice, and narration."""

from __future__ import annotations

LANGUAGE_NAMES = {
    "kk": "Қазақша",
    "ru": "Русский",
    "en": "English",
}

LANGUAGE_PROMPT_NAMES = {
    "kk": "Kazakh (Kazakhstan), written in clear modern Kazakh",
    "ru": "Russian, written in clear modern Russian",
    "en": "English, written in clear plain English",
}

DEFAULT_TTS_VOICES = {
    "kk": "kk-KZ-AigulNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "en": "en-US-AndrewMultilingualNeural",
}


def normalize_language(value: str | None, default: str = "en") -> str:
    """Return a supported short language code; accept common locale tags too."""
    raw = str(value or "").strip().lower().replace("_", "-")
    code = raw.split("-", 1)[0]
    if code in LANGUAGE_NAMES:
        return code
    return default if default in LANGUAGE_NAMES else "en"


def tts_voice_for_language(configured_voice: str | None, language: str) -> str:
    """Use a configured voice only when it speaks the selected lesson language."""
    lang = normalize_language(language)
    voice = str(configured_voice or "").strip()
    if voice.lower().startswith({"kk": "kk-", "ru": "ru-", "en": "en-"}[lang]):
        return voice
    return DEFAULT_TTS_VOICES[lang]
