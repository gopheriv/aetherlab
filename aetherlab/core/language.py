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


# ── Dubbing extensions (Agent 3): voice validation + spoken normalization ──

import re as _re

SUPPORTED_LANGUAGES = tuple(LANGUAGE_NAMES)
VOICE_PREFIXES = {"kk": "kk-", "ru": "ru-", "en": "en-"}

# Kazakh-specific Cyrillic letters (upper + lower). edge-tts kk voices handle
# these; the normalizer must never strip or transliterate them away.
KAZAKH_CHARS = frozenset("ӘәҒғҚқҢңӨөҰұҮүҺһІі")
_KAZAKH_RE = _re.compile("[ӘәҒғҚқҢңӨөҰұҮүҺһІі]")


def contains_kazakh_chars(text: str) -> bool:
    """True when *text* carries Kazakh-specific Cyrillic letters."""
    return bool(text and _KAZAKH_RE.search(text))


def infer_language_from_voice(voice: str | None, default: str = "en") -> str:
    """Guess the narration language from an edge-tts voice tag (kk-/ru-/en-)."""
    tag = str(voice or "").strip().lower()
    for lang, prefix in VOICE_PREFIXES.items():
        if tag.startswith(prefix):
            return lang
    return normalize_language(None, default)


def resolve_tts_voice(
    configured_voice: str | None, language: str
) -> tuple[str, bool, str]:
    """Resolve the effective voice and report substitution visibly.

    Returns ``(voice, substituted, note)`` where ``substituted`` is True when
    the configured voice did not match *language* and the language default was
    used instead. Callers must surface ``note`` (already localized) instead of
    silently dubbing in the wrong language. This never falls back to English
    for ru/kk requests: a mismatched voice yields the ru/kk default voice.
    """
    lang = normalize_language(language)
    configured = str(configured_voice or "").strip()
    effective = tts_voice_for_language(configured, lang)
    if configured and effective.lower() == configured.lower():
        return effective, False, ""
    if not configured:
        note = {
            "kk": f"Дауыс таңдалмаған; {effective} қолданылады.",
            "ru": f"Голос не выбран; используется {effective}.",
            "en": f"No voice configured; using {effective}.",
        }[lang]
        return effective, True, note
    note = {
        "kk": f"«{configured}» дауысы қазақшаға сай емес; {effective} қолданылады.",
        "ru": f"Голос «{configured}» не подходит для русского; используется {effective}.",
        "en": f"Voice «{configured}» does not match {lang}; using {effective}.",
    }[lang]
    return effective, True, note


# Provider voice validation (edge-tts list_voices). Cached per process so the
# Solve/Learn paths validate without hammering the network. None = unknown
# (edge-tts missing or offline); callers must treat None as "unverified", not
# as a failure, and must never silently swap in an English voice.
_VOICE_LIST_CACHE: dict[str, bool] | None = None


async def list_available_voices() -> dict[str, bool] | None:
    """Return the set of ShortNames edge-tts currently offers, or None."""
    global _VOICE_LIST_CACHE
    if _VOICE_LIST_CACHE is not None:
        return _VOICE_LIST_CACHE
    try:
        import edge_tts  # type: ignore
    except Exception:
        return None
    try:
        voices = await edge_tts.list_voices()
    except Exception:
        return None
    try:
        names = {
            str(item.get("ShortName", "")).strip().lower()
            for item in voices
            if isinstance(item, dict) and str(item.get("ShortName", "")).strip()
        }
    except Exception:
        return None
    _VOICE_LIST_CACHE = {name: True for name in names}
    return _VOICE_LIST_CACHE


async def is_voice_available(voice: str) -> bool | None:
    """True/False when the provider list is reachable, else None (unknown)."""
    available = await list_available_voices()
    if available is None:
        return None
    return str(voice or "").strip().lower() in available


def voice_validation_message(voice: str, language: str, available: bool | None) -> str:
    """Localized, actionable note for a voice that failed provider validation."""
    lang = normalize_language(language)
    if available is True:
        return ""
    if available is None:
        return {
            "kk": f"«{voice}» дауысын тексеру мүмкін болмады (желі жоқ); синтез жалғасады.",
            "ru": f"Не удалось проверить голос «{voice}» (нет сети); синтез продолжается.",
            "en": f"Could not verify voice «{voice}» (offline); continuing anyway.",
        }[lang]
    fallback = DEFAULT_TTS_VOICES[lang]
    return {
        "kk": f"«{voice}» дауысы провайдерде жоқ; {fallback} қолданылады. Баптаулардан дауысты түзетіңіз.",
        "ru": f"Голоса «{voice}» нет у провайдера; используется {fallback}. Исправьте голос в настройках.",
        "en": f"Voice «{voice}» is not offered by the provider; using {fallback}. Fix the voice in settings.",
    }[lang]


# ── Spoken normalization: formulas / units / numbers / abbreviations ──────

_UNITS_RU: dict[str, str] = {
    "км/ч": "километров в час", "м/с²": "метров в секунду в квадрате",
    "м/с": "метров в секунду", "м/с2": "метров в секунду в квадрате",
    "рад/с": "радиан в секунду", "об/мин": "оборотов в минуту",
    "°C": "градусов Цельсия", "℃": "градусов Цельсия",
    "°F": "градусов Фаренгейта", "°": "градусов",
    "Гц": "герц", "кГц": "килогерц", "МГц": "мегагерц",
    " Н": " ньютонов", " Дж": " джоулей", " Вт": " ватт",
    " Па": " паскалей", " Кл": " кулонов", " В": " вольт",
    " Ом": " ом", " Тл": " тесла", " Гн": " генри",
    " кг": " килограммов", " г": " граммов", " т": " тонн",
    " км": " километров", " см": " сантиметров", " мм": " миллиметров",
    " м ": " метров ", " с ": " секунд ",
}
_UNITS_KK: dict[str, str] = {
    "км/сағ": "сағатына километр", "км/ч": "сағатына километр",
    "м/с²": "секунд квадратына метр", "м/с": "секундына метр",
    "рад/с": "секундына радиан", "об/мин": "минутына айналым",
    "°C": "Цельсий градусы", "℃": "Цельсий градусы", "°": "градус",
    "Гц": "герц", "кГц": "килогерц", "МГц": "мегагерц",
    " Н": " ньютон", " Дж": " джоуль", " Вт": " ватт",
    " Па": " паскаль", " Кл": " кулон", " В": " вольт",
    " кг": " килограмм", " г": " грамм", " ж": " жыл",
    " км": " километр", " см": " сантиметр", " мм": " миллиметр",
}
_UNITS_EN: dict[str, str] = {
    "km/h": "kilometers per hour", "m/s^2": "meters per second squared",
    "m/s²": "meters per second squared", "m/s": "meters per second",
    "rad/s": "radians per second", "rpm": "revolutions per minute",
    "°C": "degrees Celsius", "℃": "degrees Celsius", "°F": "degrees Fahrenheit",
    "°": "degrees", "Hz": "hertz", "kHz": "kilohertz", "MHz": "megahertz",
}

_ABBREV_RU: dict[str, str] = {
    "т.е.": "то есть", "т.д.": "так далее", "и т.д.": "и так далее",
    "и т.п.": "и тому подобное", "т.п.": "тому подобное",
    "напр.": "например", "см.": "смотри", "рис.": "рисунок",
}
_ABBREV_KK: dict[str, str] = {
    "т.б.": "тағы басқа", "және т.б.": "және тағы басқа",
    "мыc.": "мысалы", "мыс.": "мысалы", "сур.": "сурет",
}
_ABBREV_EN: dict[str, str] = {
    "e.g.": "for example", "i.e.": "that is", "etc.": "etcetera",
    "vs.": "versus", "fig.": "figure",
}

_FORMULA_TOKENS: dict[str, dict[str, str]] = {
    "ru": {"->": " переходит в ", "→": " переходит в ", "<=": " не больше ",
           ">=": " не меньше ", "!=": " не равно ", "=": " равно ",
           "+": " плюс ", "-": " минус ", "*": " умножить на ", "/": " делить на ",
           "^2": " в квадрате ", "^3": " в кубе ", "sqrt": " квадратный корень из ",
           "×": " умножить на ", "÷": " делить на ", "±": " плюс-минус ",
           "∞": " бесконечность ", "≈": " примерно равно ", "≠": " не равно ",
           "≤": " не больше ", "≥": " не меньше ", "θ": " тэта ", "ω": " омега ",
           "λ": " лямбда ", "φ": " фи ", "π": " пи ", "Δ": " дельта ", "Σ": " сумма "},
    "kk": {"->": " ауысады ", "→": " ауысады ", "<=": " артық емес ",
           ">=": " кем емес ", "!=": " тең емес ", "=": " тең ",
           "+": " қосу ", "-": " алу ", "*": " көбейту ", "/": " бөлу ",
           "^2": " квадраты ", "^3": " кубы ", "sqrt": " квадрат түбірі ",
           "×": " көбейту ", "÷": " бөлу ", "±": " плюс-минус ",
           "∞": " шексіздік ", "≈": " жуықтап тең ", "≠": " тең емес ",
           "≤": " артық емес ", "≥": " кем емес ", "θ": " тэта ", "ω": " омега ",
           "λ": " лямбда ", "φ": " фи ", "π": " пи ", "Δ": " дельта ", "Σ": " қосынды "},
    "en": {"->": " goes to ", "→": " goes to ", "<=": " is at most ",
           ">=": " is at least ", "!=": " is not equal to ", "=": " equals ",
           "+": " plus ", "-": " minus ", "*": " times ", "/": " divided by ",
           "^2": " squared ", "^3": " cubed ", "sqrt": " square root of ",
           "×": " times ", "÷": " divided by ", "±": " plus or minus ",
           "∞": " infinity ", "≈": " is approximately ", "≠": " is not equal to ",
           "≤": " is at most ", "≥": " is at least "},
}

_LATEX_FRAC_RE = _re.compile(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
_LATEX_CMD_RE = _re.compile(r"\\(sqrt|times|div|pm|infty|approx|neq|leq|geq|theta|omega|lambda|phi|pi|Delta|Sigma|alpha|beta|gamma)\b")


def _expand_latex(text: str, lang: str) -> str:
    """Rewrite a small LaTeX subset into speakable words (fail-soft)."""
    tokens = _FORMULA_TOKENS.get(lang, _FORMULA_TOKENS["en"])

    def _frac(match: _re.Match) -> str:
        num, den = match.group(1).strip(), match.group(2).strip()
        joiner = {"ru": " разделить на ", "kk": " бөлінген ", "en": " over "}.get(lang, " over ")
        return f" {num}{joiner}{den} "

    text = _LATEX_FRAC_RE.sub(_frac, text)

    def _cmd(match: _re.Match) -> str:
        name = match.group(1)
        spoken = {
            "sqrt": tokens.get("sqrt", " square root of "), "times": tokens.get("×", " times "),
            "div": tokens.get("÷", " divided by "), "pm": tokens.get("±", " plus-minus "),
            "infty": tokens.get("∞", " infinity "), "approx": tokens.get("≈", " approximately "),
            "neq": tokens.get("≠", " not equal "), "leq": tokens.get("≤", " at most "),
            "geq": tokens.get("≥", " at least "),
        }.get(name, f" {name} ")
        return spoken

    text = _LATEX_CMD_RE.sub(_cmd, text)
    # Unknown commands (\unknowncmd): speak the name rather than choking TTS
    # on a backslash; lone leftovers (line breaks, escaped punctuation) go.
    text = _re.sub(r"\\([A-Za-z]+)", r" \1 ", text)
    # Strip leftover math delimiters and braces; keep the inner words.
    text = text.replace("$", " ").replace("\\(", " ").replace("\\)", " ")
    text = text.replace("\\[", " ").replace("\\]", " ")
    text = text.replace("{", " ").replace("}", " ")
    text = text.replace("_", " ").replace("\\", " ")
    # Powers before the generic caret, in the narration language.
    text = text.replace("^2", tokens.get("^2", " squared ")).replace(
        "^3", tokens.get("^3", " cubed ")
    )
    power = {"ru": " в степени ", "kk": " дәрежесінде ", "en": " to the power of "}.get(
        lang, " to the power of "
    )
    text = text.replace("^", power)
    return text


# Word-level spoken matching. Whole-string substring replacement cascades:
# "/" inside "м/с" would become "делить на", and " г" would match inside the
# already-expanded "градусов". Matching whole whitespace-separated words (with
# longest-first units and single-letter units only after a number) avoids that.
_PUNCT_TAIL_RE = _re.compile(r"^(?P<stem>.*?)(?P<punct>[,.!?:;]+)$")
_NUMBER_RE = _re.compile(r"^\d+([.,]\d+)?$")
_FORMULA_WORD_RE = _re.compile(r"^[A-Za-z0-9+\-*/^_().=<>!×÷±∞≈≠≤≥θωλφπΔΣ→-]+$")
_FORMULA_SYMBOL_RE = _re.compile(r"[+\-*/^_()=<>!×÷±∞≈≠≤≥θωλφπΔΣ→]")
_WORD_HYPHEN_RE = _re.compile(r"^[A-Za-z]{1,}(?:-[A-Za-z]{1,})+$")  # e-mail, not a minus
_MATH_HINT_RE = _re.compile(r"[\d=+*^<>!]")

# "в 1999 г." / "1999 ж." is a year, not grams — a 4-digit number decides.
# ("5 г." is grams with a sentence period; 2-3 digit quantities are near
# always weights, so only a 4-digit year reads as one.)
_YEAR_NUM_RE = _re.compile(r"^\d{4}$")
_YEAR_WORD = {"ru": "году", "kk": "жылы"}
_YEAR_STEMS = {"ru": frozenset({"г"}), "kk": frozenset({"г", "ж"})}


def _strip_unit_keys(units: dict[str, str]) -> dict[str, str]:
    return {key.strip(): value for key, value in units.items()}


def _is_number(word: str) -> bool:
    return bool(word and _NUMBER_RE.match(word))


def normalize_spoken_text(text: str, language: str) -> str:
    """Rewrite display text into TTS-friendly spoken prose for ru/kk/en.

    Expands LaTeX fragments, formula symbols, physical units, and common
    abbreviations; collapses whitespace; preserves Kazakh-specific letters.
    Matching is word-level so expansions never cascade into each other
    ("м/с" stays one unit; the preposition "с" is not read as seconds).
    Display strings (subtitles, cards) keep the original text — only the
    synthesized line uses this form.
    """
    lang = normalize_language(language)
    spoken = str(text or "")
    if not spoken.strip():
        return ""
    spoken = _expand_latex(spoken, lang)
    # Separate attached units ("25°C" -> "25 °C") without touching "3.14".
    spoken = _re.sub(r"(\d)([^\d\s.,!?;:])", r"\1 \2", spoken)
    tokens = _FORMULA_TOKENS.get(lang, _FORMULA_TOKENS["en"])
    units = _strip_unit_keys({"ru": _UNITS_RU, "kk": _UNITS_KK, "en": _UNITS_EN}[lang])
    abbrev = {"ru": _ABBREV_RU, "kk": _ABBREV_KK, "en": _ABBREV_EN}[lang]
    # Multi-word abbreviations first ("и т.д." before "т.д.").
    for short in sorted((k for k in abbrev if " " in k), key=len, reverse=True):
        if short in spoken:
            spoken = spoken.replace(short, abbrev[short])

    words = spoken.split()
    out: list[str] = []
    for index, word in enumerate(words):
        prev = words[index - 1] if index else ""
        prev_stem = _PUNCT_TAIL_RE.sub(r"\g<stem>", prev) if prev else ""
        prev_is_number = _is_number(prev_stem or prev)
        prev_is_year = bool(_YEAR_NUM_RE.match(prev_stem or prev))
        nxt = words[index + 1] if index + 1 < len(words) else ""

        def _unit_ok(key: str) -> bool:
            # Single-letter units ("с", "г", "В", "°") expand only after a
            # number — otherwise the preposition "с" / sentence-start "В"
            # would be misread as seconds / volts.
            return len(key) > 1 or prev_is_number

        def _sentence_end() -> bool:
            return not nxt or nxt[:1].isupper()

        expansion: str | None = None
        punct = ""
        if word in abbrev:
            expansion = abbrev[word]
            if word.endswith(".") and _sentence_end():
                expansion += "."  # "т.е." also ends the sentence: keep the stop
        elif word in units and _unit_ok(word):
            if prev_is_year and word in _YEAR_STEMS.get(lang, frozenset()):
                expansion = _YEAR_WORD[lang]  # "в 1999 г" is a year
            else:
                expansion = units[word]
        else:
            tail = _PUNCT_TAIL_RE.match(word)
            stem, punct = (tail.group("stem"), tail.group("punct")) if tail else (word, "")
            if stem and stem in abbrev:
                expansion = abbrev[stem]
            elif stem and stem in units and _unit_ok(stem):
                if (
                    "." in punct
                    and prev_is_year
                    and stem in _YEAR_STEMS.get(lang, frozenset())
                ):
                    expansion = _YEAR_WORD[lang]  # "в 1999 г." is a year
                else:
                    expansion = units[stem]
            elif stem and stem in tokens and stem.strip():
                expansion = tokens[stem].strip()  # standalone symbol ("=", "+")
            elif stem and _FORMULA_WORD_RE.match(stem) and _FORMULA_SYMBOL_RE.search(stem):
                # Intra-word symbols only in Latin/digit formula tokens, so
                # hyphenated words ("что-то") and "и/или" are left alone.
                core = stem
                for symbol in sorted(tokens, key=len, reverse=True):
                    if not symbol.strip() or symbol not in core:
                        continue
                    if symbol == "-" and _WORD_HYPHEN_RE.match(core):
                        continue
                    if symbol == "/":
                        parts = core.split("/")
                        if not (
                            all(_re.fullmatch(r"[A-Za-z0-9]", p) for p in parts)
                            or _MATH_HINT_RE.search(core)
                        ):
                            continue
                    core = core.replace(symbol, tokens[symbol])
                out.append(" ".join((core + punct).split()))
                continue
            else:
                out.append(word)
                continue
        assert expansion is not None
        out.append(" ".join((expansion + punct).split()))

    spoken = " ".join(out)
    # Decimal comma reads naturally in ru/kk TTS ("3,14"); keep dots in en.
    if lang in {"ru", "kk"}:
        spoken = _re.sub(r"(?P<int>\d+)\.(?P<frac>\d+)", r"\g<int>,\g<frac>", spoken)
    spoken = _re.sub(r"\s+", " ", spoken).strip()
    return spoken


def ensure_complete_sentences(text: str, language: str = "en") -> str:
    """Drop a trailing fragment so narration never ends mid-sentence.

    Keeps whole sentences (ending in . ! ? …); when no sentence boundary
    exists the text is returned stripped (a single short cue is complete by
    construction). Used before synthesis so truncated planner lines cannot
    produce cut-off audio endings.
    """
    value = " ".join(str(text or "").split())
    if not value:
        return ""
    match = _re.search(r"^(?P<body>.*?[.!?…]+)(?P<tail>\s*[^.!?…]*)$", value, _re.DOTALL)
    if not match:
        return value
    body = match.group("body").strip()
    tail = match.group("tail").strip()
    if not tail:
        return value
    # A short trailing tail without closing punctuation is a fragment.
    if len(tail.split()) <= 12:
        return body
    return value


# Localized narration status / failure copy (ru/kk/en). Keys are stable;
# templates take {detail} / {voice} / {rate} placeholders.
NARRATION_MESSAGES: dict[str, dict[str, str]] = {
    "kk": {
        "synthesis_failed": "Дауыстау сәтсіз аяқталды ({detail}); дыбыссыз нұсқа сақталды.",
        "voice_missing": "«{voice}» дауысы табылмады; {detail} қолданылады.",
        "voice_degraded": "Дауыс нашарлатылды: {detail}.",
        "mux_failed": "Дыбысты біріктіру сәтсіз ({detail}); дыбыссыз нұсқа сақталды.",
        "truncated_avoided": "Соңы кесілмес үшін видео ұзартылды.",
        "cancelled": "Дауыстау тоқтатылды.",
    },
    "ru": {
        "synthesis_failed": "Озвучка не удалась ({detail}); оставлена немая версия.",
        "voice_missing": "Голос «{voice}» не найден; используется {detail}.",
        "voice_degraded": "Голос понижен: {detail}.",
        "mux_failed": "Не удалось соединить звук ({detail}); оставлена немая версия.",
        "truncated_avoided": "Видео удлинено, чтобы не обрезать концовку.",
        "cancelled": "Озвучка отменена.",
    },
    "en": {
        "synthesis_failed": "Narration failed ({detail}); kept the silent video.",
        "voice_missing": "Voice «{voice}» not found; using {detail}.",
        "voice_degraded": "Voice degraded: {detail}.",
        "mux_failed": "Audio mux failed ({detail}); kept the silent video.",
        "truncated_avoided": "Extended the video so the ending is not cut.",
        "cancelled": "Narration cancelled.",
    },
}


def narration_message(key: str, language: str, **values: object) -> str:
    """Localized narration copy; falls back to English for unknown keys."""
    lang = normalize_language(language)
    template = NARRATION_MESSAGES.get(lang, {}).get(key) or NARRATION_MESSAGES["en"].get(key, key)
    try:
        return template.format(**values)
    except Exception:
        return template
