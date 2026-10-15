"""Russian/Kazakh dubbing: language routing, voices, spoken text, caching, subs.

Agent 3 ownership: narration language must be explicit end to end (Solve +
Learn), voices must be validated against the provider (never a silent English
substitution), spoken text must read formulas/units/numbers/abbreviations
naturally in ru/kk, endings must be complete, subtitles must align with the
final timeline, and audio/chapter cache identity must cover language, voice,
rate, synthesis settings, and pipeline version.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from aetherlab.core.language import (
    DEFAULT_TTS_VOICES,
    contains_kazakh_chars,
    ensure_complete_sentences,
    infer_language_from_voice,
    narration_message,
    normalize_language,
    normalize_spoken_text,
    resolve_tts_voice,
    voice_validation_message,
)
from aetherlab.core.models import LessonChapter, LessonPlan, ProblemRequest, SceneBundle
from aetherlab.services import voiceover
from aetherlab.services.voiceover import (
    VOICEOVER_PIPELINE_VERSION,
    build_srt,
    render_profile_key,
    speech_cache_path,
)


# ── language is explicit on Solve + Learn requests ─────────────────────────

def test_problem_request_defaults_to_english_but_carries_ru_kk():
    assert ProblemRequest("solve this").normalized_language() == "en"
    assert ProblemRequest("реши", language="ru").normalized_language() == "ru"
    assert ProblemRequest("шығар", language="kk").normalized_language() == "kk"
    assert ProblemRequest("x", language="RU-ru").normalized_language() == "ru"


def test_cache_key_separates_ru_kk_en():
    ru = ProblemRequest("реши задачу", language="ru").canonical_payload()
    kk = ProblemRequest("реши задачу", language="kk").canonical_payload()
    en = ProblemRequest("реши задачу", language="en").canonical_payload()
    assert ru["language"] == "ru" and kk["language"] == "kk" and en["language"] == "en"
    assert ru != kk != en


def test_lesson_plan_language_survives_a_cache_round_trip():
    plan = LessonPlan(title="T", topic="t", language="kk")
    assert LessonPlan.from_json(plan.to_json()).language == "kk"
    plan_ru = LessonPlan(title="T", topic="t", language="ru")
    assert LessonPlan.from_json(plan_ru.to_json()).language == "ru"


# ── voice resolution: compatible voice, never silent English ───────────────

def test_matching_voice_is_kept_quietly():
    voice, substituted, note = resolve_tts_voice("ru-RU-DmitryNeural", "ru")
    assert (voice, substituted, note) == ("ru-RU-DmitryNeural", False, "")


def test_mismatched_voice_falls_back_to_the_language_default_with_a_note():
    voice, substituted, note = resolve_tts_voice("en-US-AndrewMultilingualNeural", "ru")
    assert voice == DEFAULT_TTS_VOICES["ru"]
    assert voice.startswith("ru-") and substituted and note  # visibly reported


def test_kazakh_never_gets_an_english_voice_by_default():
    voice, substituted, note = resolve_tts_voice("en-US-AndrewMultilingualNeural", "kk")
    assert voice == DEFAULT_TTS_VOICES["kk"]
    assert voice.startswith("kk-") and substituted and note


def test_empty_voice_reports_the_default_it_picks():
    voice, substituted, note = resolve_tts_voice("", "kk")
    assert voice == DEFAULT_TTS_VOICES["kk"] and substituted and "Aigul" in note


def test_infer_language_from_voice_tag():
    assert infer_language_from_voice("kk-KZ-AigulNeural") == "kk"
    assert infer_language_from_voice("ru-RU-SvetlanaNeural") == "ru"
    assert infer_language_from_voice("en-US-AndrewMultilingualNeural") == "en"
    assert infer_language_from_voice(None) == "en"


def test_kazakh_specific_letters_are_detected():
    assert contains_kazakh_chars("Қазақша әріптер: Ғ Қ Ң Ө Ұ Ү Һ І") is True
    assert contains_kazakh_chars("Обычный русский текст") is False


def test_provider_validation_messages_are_localized_and_actionable():
    missing_ru = voice_validation_message("ru-RU-NopeNeural", "ru", False)
    assert "Svetlana" in missing_ru and "настройках" in missing_ru
    missing_kk = voice_validation_message("kk-KZ-NopeNeural", "kk", False)
    assert "Aigul" in missing_kk
    offline = voice_validation_message("kk-KZ-AigulNeural", "kk", None)
    assert offline  # unverified, not a failure — synthesis continues
    assert voice_validation_message("ru-RU-SvetlanaNeural", "ru", True) == ""


def test_resolve_and_validate_voice_never_silently_substitutes_english(monkeypatch):
    async def available(_voice: str):
        return True

    monkeypatch.setattr("aetherlab.core.language.is_voice_available", available)
    voice, notes = asyncio.run(
        voiceover.resolve_and_validate_voice("en-US-AndrewMultilingualNeural", "kk")
    )
    assert voice.startswith("kk-") and notes

    async def missing(_voice: str):
        return False

    monkeypatch.setattr("aetherlab.core.language.is_voice_available", missing)
    voice, notes = asyncio.run(
        voiceover.resolve_and_validate_voice("ru-RU-GhostNeural", "ru")
    )
    assert voice == DEFAULT_TTS_VOICES["ru"]
    assert any("Svetlana" in note for note in notes)


# ── spoken normalization: formulas / units / numbers / abbreviations ───────

def test_russian_units_formulas_and_abbreviations_are_speakable():
    spoken = normalize_spoken_text("Скорость 20 м/с при 36 км/ч и 25 °C, т.е. тепло", "ru")
    assert "м/с" not in spoken and "км/ч" not in spoken and "°C" not in spoken
    assert "метров в секунду" in spoken and "километров в час" in spoken
    assert "то есть" in spoken and "т.е." not in spoken


def test_kazakh_units_abbreviations_and_letters_survive():
    spoken = normalize_spoken_text("Жылдамдық 20 м/с, т.б. жағдайлар: ӘҢҒ", "kk")
    assert "м/с" not in spoken and "т.б." not in spoken
    assert "секундына метр" in spoken and "тағы басқа" in spoken
    assert contains_kazakh_chars(spoken)  # ӘҒҚҢӨҰҮҺІ must never be stripped


def test_formula_tokens_and_latex_are_spoken_in_each_language():
    assert "равно" in normalize_spoken_text("F = m*a", "ru")
    assert "тең" in normalize_spoken_text("F = m*a", "kk")
    assert "equals" in normalize_spoken_text("F = m*a", "en")
    frac_ru = normalize_spoken_text(r"$\frac{a}{b}$", "ru")
    assert "frac" not in frac_ru and "разделить на" in frac_ru
    assert "бөлінген" in normalize_spoken_text(r"$\frac{a}{b}$", "kk")


def test_decimal_comma_for_ru_kk_but_not_en():
    assert "3,14" in normalize_spoken_text("pi is 3.14", "ru")
    assert "3,14" in normalize_spoken_text("pi is 3.14", "kk")
    assert "3.14" in normalize_spoken_text("pi is 3.14", "en")


def test_english_abbreviations_still_expand():
    spoken = normalize_spoken_text("Planets, e.g. Mars, etc.", "en")
    assert "for example" in spoken and "etcetera" in spoken


# ── complete endings: no truncated narration ───────────────────────────────

def test_trailing_fragment_is_dropped_ru_kk():
    ru = ensure_complete_sentences("Скорость растёт. А потом мы видим как", "ru")
    assert ru == "Скорость растёт."
    kk = ensure_complete_sentences("Жылдамдық артады. Содан кейін біз", "kk")
    assert kk == "Жылдамдық артады."


def test_complete_text_is_kept_verbatim():
    text = "Қозғалыс бірқалыпты. Үдеу нөлге тең!"
    assert ensure_complete_sentences(text, "kk") == text
    assert ensure_complete_sentences("", "ru") == ""


def test_planner_trims_truncated_chapter_narration():
    from aetherlab.services.lesson_planner import _prepare_lesson_plan

    plan = LessonPlan(
        title="T", topic="t", language="ru",
        chapters=[LessonChapter(id="c1", title="Глава", kind="scene",
                                narration="Скорость растёт. А потом мы видим как")],
    )
    assert _prepare_lesson_plan(plan) is True
    assert plan.chapters[0].narration == "Скорость растёт."


# ── audio cache identity: language / voice / rate / settings / version ─────

def test_speech_cache_key_covers_language_voice_rate_settings(tmp_path):
    base = dict(cache_dir=tmp_path, text="Скорость растёт.", voice="ru-RU-SvetlanaNeural", rate="+0%")
    ru = speech_cache_path(**base, language="ru")
    kk = speech_cache_path(**base, language="kk")
    assert ru != kk  # same text, different dub — never share a clip
    assert speech_cache_path(**base, language="ru") == ru  # stable
    other_voice = speech_cache_path(**{**base, "voice": "ru-RU-DmitryNeural"}, language="ru")
    assert other_voice != ru
    other_rate = speech_cache_path(**{**base, "rate": "+10%"}, language="ru")
    assert other_rate != ru
    with_settings = speech_cache_path(**base, language="ru", synthesis_settings={"pitch": "+5Hz"})
    assert with_settings != ru


def test_legacy_callers_without_language_still_split_by_voice_prefix(tmp_path):
    # Solve-path callers pass no language; the kk-/ru-/en- voice prefix keeps
    # their cache entries separated.
    ru = speech_cache_path(tmp_path, "line", "ru-RU-SvetlanaNeural", "+0%")
    kk = speech_cache_path(tmp_path, "line", "kk-KZ-AigulNeural", "+0%")
    assert ru != kk


def test_pipeline_version_pins_the_cache_identity():
    assert VOICEOVER_PIPELINE_VERSION == "dub-v2"


def test_concurrent_synthesis_of_one_line_resolves_to_one_clip(tmp_path, monkeypatch):
    calls: list[str] = []

    async def fake_synthesize(text, out_path, voice, rate, language=None):
        calls.append(text)
        await asyncio.sleep(0.01)  # force the race
        Path(out_path).write_bytes(b"fake-audio-payload")
        return Path(out_path)

    async def no_trim(_source, _target):
        return False

    monkeypatch.setattr(voiceover, "synthesize", fake_synthesize)
    monkeypatch.setattr(voiceover, "_trim_edges", no_trim)

    async def _race():
        return await asyncio.gather(
            voiceover.synthesize_cached("Сәлем әлем", tmp_path, "kk-KZ-AigulNeural", "+0%", "kk"),
            voiceover.synthesize_cached("Сәлем әлем", tmp_path, "kk-KZ-AigulNeural", "+0%", "kk"),
        )

    first, second = asyncio.run(_race())
    assert first == second and first is not None and first.is_file()
    assert len(calls) == 1  # one synthesis, one clip — no duplicate work


def test_measure_speech_routes_language_and_keeps_blanks_at_zero(tmp_path, monkeypatch):
    seen: list[str | None] = []

    async def fake_cached(text, cache_dir, voice, rate, language=None, synthesis_settings=None):
        seen.append(language)
        clip = tmp_path / f"{len(seen)}.mp3"
        clip.write_bytes(b"x" * 64)
        return clip

    monkeypatch.setattr(voiceover, "synthesize_cached", fake_cached)
    monkeypatch.setattr(voiceover, "get_duration", lambda _path: asyncio.sleep(0, result=1.5))
    durations = asyncio.run(voiceover.measure_speech(
        ["Сәлем", "", "Әлем"], tmp_path, "kk-KZ-AigulNeural", "+0%", language="kk",
    ))
    assert durations == [1.5, 0.0, 1.5]
    assert seen == ["kk", "kk"]  # blanks never reach synthesis


# ── subtitles align with the final timeline, never overlap ─────────────────

def test_build_srt_clips_cue_ends_to_the_next_start():
    srt = build_srt(
        [("Первая глава", 5.0), ("Вторая глава", 5.0)],
        starts=[0.0, 4.0],  # crossfade overlap: cue 1 must end at 4 s
    )
    assert "00:00:00,000 --> 00:00:04,000" in srt.splitlines()[1]
    assert srt.count("-->") == 2


def test_build_srt_skips_blank_narration_and_keeps_kazakh_chars():
    srt = build_srt([("", 3.0), ("Қозғалыс заңы", 2.0)], starts=[0.0, 3.0])
    assert srt.count("-->") == 1 and "Қозғалыс заңы" in srt


# ── chapter cache: stale dubs are misses, replace-not-duplicate ────────────

def _chapter_settings(**overrides):
    values = {"tts_voice": "ru-RU-SvetlanaNeural", "tts_rate": "+0%", "narration_enabled": True}
    values.update(overrides)
    return SimpleNamespace(**values)


def _lesson(language: str) -> LessonPlan:
    return LessonPlan(
        title="T", topic="mechanics", audience="undergrad", language=language,
        chapters=[LessonChapter(id="c1", title="Глава", kind="scene", narration="Текст.")],
    )


def test_chapter_key_invalidates_across_language_voice_rate_profile():
    from aetherlab.services.lesson_pipeline import _chapter_key

    plan_ru, plan_kk = _lesson("ru"), _lesson("kk")
    settings = _chapter_settings()
    key_ru = _chapter_key(plan_ru.chapters[0], plan_ru, settings, "l")
    assert _chapter_key(plan_kk.chapters[0], plan_kk, settings, "l") != key_ru
    assert _chapter_key(plan_ru.chapters[0], plan_ru, _chapter_settings(tts_rate="+10%"), "l") != key_ru
    assert _chapter_key(plan_ru.chapters[0], plan_ru, _chapter_settings(tts_voice="ru-RU-DmitryNeural"), "l") != key_ru
    assert _chapter_key(plan_ru.chapters[0], plan_ru, settings, "h") != key_ru
    assert _chapter_key(plan_ru.chapters[0], plan_ru, settings, "l") == key_ru


def test_chapter_clip_match_rejects_unverifiable_narrated_clips(tmp_path):
    from aetherlab.services.lesson_pipeline import _chapter_clip_matches

    settings = _chapter_settings()
    silent = SceneBundle("S", "code", "manim-community", "rendered")
    assert _chapter_clip_matches(silent, "ru", settings) is True  # silent → dub once
    assert _chapter_clip_matches(silent, "ru", _chapter_settings(narration_enabled=False)) is True

    narrated = SceneBundle("S", "code", "manim-community", "rendered",
                           narration_text="Старая озвучка")
    assert _chapter_clip_matches(narrated, "ru", settings) is False  # no silent source → miss

    source = tmp_path / "silent.mp4"
    source.write_bytes(b"x" * 128)
    replaceable = SceneBundle("S", "code", "manim-community", "rendered",
                              narration_text="Старая озвучка", silent_video_path=str(source))
    assert _chapter_clip_matches(replaceable, "ru", settings) is True  # replace, not stack


def test_render_profile_key_is_quality_sensitive_with_fallback(monkeypatch):
    import sys

    key_l, key_h = render_profile_key(None, "l"), render_profile_key(None, "h")
    assert key_l and key_h and key_l != key_h
    import aetherlab.core

    # Simulate the module being absent: block both the submodule lookup and
    # the parent-package attribute fallback of `from ... import ...`.
    monkeypatch.setitem(sys.modules, "aetherlab.core.render_profile", None)
    monkeypatch.delattr(aetherlab.core, "render_profile", raising=False)
    assert render_profile_key(None, "h") == "quality:h"


# ── export: language-correct metadata, player, subtitles ───────────────────

def _bundle(language: str) -> SimpleNamespace:
    return SimpleNamespace(
        plan=_lesson(language),
        status="complete",
        chapter_offsets=[0.0],
        rendered_chapter_indexes=[0],
        chapter_scenes=[SimpleNamespace(code="x = 1", scene_spec=None)],
    )


def test_export_metadata_carries_language():
    from aetherlab.services.share_export import _metadata

    metadata = _metadata(_bundle("kk"))
    assert metadata["language"] == "kk" and metadata["language_name"] == "Қазақша"


def test_export_player_uses_lesson_language_for_track():
    from aetherlab.services.share_export import _html_player, _metadata

    html_kk = _html_player(_bundle("kk"), _metadata(_bundle("kk")), has_track=True)
    assert '<html lang="kk">' in html_kk
    assert 'srclang="kk"' in html_kk and "Қазақша" in html_kk
    html_ru = _html_player(_bundle("ru"), _metadata(_bundle("ru")), has_track=True)
    assert '<html lang="ru">' in html_ru and 'srclang="ru"' in html_ru


def test_export_readme_notes_narration_language():
    from aetherlab.services.share_export import _readme

    assert "(kk)" in _readme(_bundle("kk"), True)


def test_vtt_conversion_preserves_kazakh_chars():
    from aetherlab.services.share_export import _srt_to_vtt

    vtt = _srt_to_vtt("1\n00:00:00,000 --> 00:00:02,000\nҚозғалыс: ӘҢҒ\n")
    assert vtt.startswith("WEBVTT") and "Қозғалыс: ӘҢҒ" in vtt
    assert "00:00:00.000 --> 00:00:02.000" in vtt


# ── Mission 2: normalizer battery (fuzz + invariants + fixed bugs) ──────────

def test_hyphenated_latin_words_are_never_read_as_minus():
    spoken = normalize_spoken_text("напиши e-mail про x-ray и T-shirt от mother-in-law", "ru")
    for word in ("e-mail", "x-ray", "T-shirt", "mother-in-law"):
        assert word in spoken, spoken
    assert "минус" not in spoken
    # A genuine minus with digits still splits.
    assert "минус" in normalize_spoken_text("счёт x-2", "ru")


def test_year_vs_gram_disambiguation_ru_kk():
    assert "году" in normalize_spoken_text("в 1999 г. было", "ru")
    assert "году" in normalize_spoken_text("в 1999 г состоялось", "ru")
    assert "граммов" in normalize_spoken_text("масса 5 г.", "ru")
    assert "граммов" in normalize_spoken_text("доза 100 г.", "ru")  # 3-digit: grams
    assert "жылы" in normalize_spoken_text("1999 ж. болды", "kk")
    assert "жылы" in normalize_spoken_text("2001 ж шықты", "kk")
    assert "грамм" in normalize_spoken_text("салмағы 5 г.", "kk")


def test_unknown_latex_commands_never_leave_a_backslash():
    for lang in ("ru", "kk", "en"):
        spoken = normalize_spoken_text(r"$\unknowncmd{x} + \frac{1}{2}$", lang)
        assert "\\" not in spoken, (lang, spoken)
        assert "unknowncmd" in spoken  # the name is spoken, TTS-safe


def test_slash_words_and_prepositions_survive():
    assert normalize_spoken_text("вход и/или выход", "ru") == "вход и/или выход"
    spoken = normalize_spoken_text("шаг с периодом", "ru")
    assert " с " in f" {spoken} " and "секунд" not in spoken  # "с" is not seconds
    assert "вольт" not in normalize_spoken_text("В начале было слово", "ru")


_NORMALIZER_FUZZ_TOKENS = (
    "Скорость", "Жылдамдық", "speed", "20", "3.14", "1999", "5", "100",
    "м/с", "км/ч", "°C", "г.", "г", "ж.", "ж", "Гц", "км", "см",
    "т.е.", "т.д.", "и т.д.", "напр.", "т.б.", "мыс.", "e.g.", "etc.",
    "F", "=", "->", "+", "-", "*", "/", "^2", "^3", "sqrt", "×", "±", "∞",
    "≈", "θ", "ω", "π", "Δ", "a_b", "x-2", "e-mail", "и/или", "что-то",
    r"$\frac{a}{b}$", r"$\sqrt{x}$", r"$\alpha + \beta$", "ӘҢҒ", "Қазақша",
)


def test_normalizer_fuzz_never_crashes_and_stays_idempotent():
    import random

    rng = random.Random(20261015)
    kazakh_probe = "ӘҢҒҚӨҰҮҺІ"
    for trial in range(400):
        width = rng.randint(1, 6)
        text = " ".join(rng.choice(_NORMALIZER_FUZZ_TOKENS) for _ in range(width))
        lang = rng.choice(["ru", "kk", "en"])
        if trial % 3 == 0:
            text += " " + kazakh_probe
        once = normalize_spoken_text(text, lang)
        assert isinstance(once, str) and once == once.strip()
        assert "  " not in once
        assert normalize_spoken_text(once, lang) == once  # idempotent
        for char in set(text) & set("ӘәҒғҚқҢңӨөҰұҮүҺһІі"):  # Kazakh letters survive
            assert char in once, (text, lang, once)
        assert "\\" not in once


def test_normalizer_fuzz_never_cascades_units_into_formulas():
    import random

    rng = random.Random(77)
    for _ in range(200):
        text = " ".join(rng.choice(_NORMALIZER_FUZZ_TOKENS) for _ in range(rng.randint(1, 5)))
        for lang in ("ru", "kk", "en"):
            spoken = normalize_spoken_text(text, lang)
            # "м/с" expands as one unit; its "/" must never split the word.
            # (Skipped when a frac is present: its "разделить на" joiner
            # legitimately contains "делить на" as a substring.)
            if "м/с" in text and "frac" not in text and lang == "ru":
                assert "метров в секунду" in spoken, (text, spoken)
                assert "м делить на с" not in spoken, (text, spoken)
            # Expansions never re-expand: no unit/formula source token survives
            # inside its own expansion.
            assert "метров в секунду в секунду" not in spoken
            assert "секундына метр секундына" not in spoken


def test_complete_sentences_ellipsis_long_tail_and_boundaries():
    assert ensure_complete_sentences("Пауза… А дальше обрывок без", "ru") == "Пауза…"
    long_tail = "Начало. " + "слово " * 13
    assert ensure_complete_sentences(long_tail.strip(), "ru") == long_tail.strip()
    assert ensure_complete_sentences("Готово! Вопрос?", "kk") == "Готово! Вопрос?"
    assert ensure_complete_sentences("Без точки вообще", "ru") == "Без точки вообще"


def test_srt_running_sum_invalid_starts_and_time_format():
    from aetherlab.services.voiceover import _fmt_srt_time

    assert _fmt_srt_time(3723.456) == "01:02:03,456"
    assert _fmt_srt_time(-5) == "00:00:00,000"
    srt = build_srt([("Раз", 2.0), ("Два", 3.0)])  # no starts: running sum
    assert "00:00:00,000 --> 00:00:02,000" in srt
    assert "00:00:02,000 --> 00:00:05,000" in srt
    srt = build_srt([("Раз", 2.0), ("Два", 0.0), ("Три", 1.0)])  # zero clip skipped
    assert srt.count("-->") == 2 and "Три" in srt
    srt = build_srt([("Раз", 2.0)], starts=["bogus"])  # invalid start falls back
    assert "00:00:00,000 --> 00:00:02,000" in srt


def test_speech_cache_keys_spoken_form_not_display_form(tmp_path):
    base = dict(cache_dir=tmp_path, voice="ru-RU-SvetlanaNeural", rate="+0%", language="ru")
    formula = speech_cache_path(text="F = m*a", **base)
    spoken = speech_cache_path(text="F равно m умножить на a", **base)
    assert formula == spoken  # identical audio: one clip, not two
    assert speech_cache_path(text="F = m*b", **base) != formula


def test_speech_cache_survives_unserializable_settings(tmp_path):
    path = speech_cache_path(tmp_path, "line", "ru-RU-SvetlanaNeural", "+0%", "ru",
                             synthesis_settings={"opaque": object()})
    assert path.suffix == ".mp3"


def test_spoken_form_falls_back_to_collapsed_text_on_normalizer_crash(monkeypatch):
    def _boom(_text, _lang):
        raise RuntimeError("normalizer exploded")

    monkeypatch.setattr("aetherlab.core.language.normalize_spoken_text", _boom)
    spoken, lang = voiceover._spoken_form("  F  =  m*a  ", "ru-RU-SvetlanaNeural", "ru")
    assert (spoken, lang) == ("F = m*a", "ru")


def test_synthesize_returns_none_when_edge_tts_is_missing_or_fails(tmp_path, monkeypatch):
    import sys

    out = tmp_path / "line.mp3"
    monkeypatch.setitem(sys.modules, "edge_tts", None)  # `import edge_tts` raises
    assert asyncio.run(voiceover.synthesize("Привет", out, "ru-RU-SvetlanaNeural", "+0%")) is None

    class _Denied:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("403 handshake (probe-injected)")

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=_Denied))
    assert asyncio.run(voiceover.synthesize("Привет", out, "ru-RU-SvetlanaNeural", "+0%")) is None

    class _Empty:
        def __init__(self, *args, **kwargs):
            pass

        async def save(self, path):
            Path(path).write_bytes(b"")  # zero-byte clip is unusable

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=_Empty))
    assert asyncio.run(voiceover.synthesize("Привет", out, "ru-RU-SvetlanaNeural", "+0%")) is None


def test_add_voiceover_keeps_silent_video_when_synthesis_fails(tmp_path, monkeypatch):
    async def _no_audio(_text, _path, _voice, _rate, _language=None):
        return None

    monkeypatch.setattr(voiceover, "synthesize", _no_audio)
    silent = tmp_path / "silent.mp4"
    silent.write_bytes(b"x" * 128)
    assert asyncio.run(voiceover.add_voiceover(silent, "Текст.", tmp_path)) is None
    assert asyncio.run(voiceover.add_voiceover(tmp_path / "missing.mp4", "Текст.", tmp_path)) is None
    assert asyncio.run(voiceover.add_voiceover(silent, "   ", tmp_path)) is None


def test_merge_without_ffmpeg_keeps_silent_video(tmp_path, monkeypatch):
    monkeypatch.setattr(voiceover, "_ffmpeg_exe", lambda: None)
    merged = asyncio.run(voiceover.merge(tmp_path / "v.mp4", tmp_path / "a.mp3", tmp_path / "o.mp4"))
    assert merged is None


def test_measure_speech_returns_none_when_any_line_fails(tmp_path, monkeypatch):
    async def _fail(_text, *_args, **_kwargs):
        return None

    monkeypatch.setattr(voiceover, "synthesize_cached", _fail)
    assert asyncio.run(voiceover.measure_speech(
        ["Раз", "Два"], tmp_path, "ru-RU-SvetlanaNeural", "+0%", language="ru")) is None


# ── localized status copy ──────────────────────────────────────────────────

def test_narration_messages_cover_ru_kk_en():
    for key in ("synthesis_failed", "voice_missing", "voice_degraded",
                "mux_failed", "truncated_avoided", "cancelled"):
        ru = narration_message(key, "ru", detail="d", voice="v")
        kk = narration_message(key, "kk", detail="d", voice="v")
        en = narration_message(key, "en", detail="d", voice="v")
        assert ru and kk and en and len({ru, kk, en}) == 3
    assert normalize_language("kk") == "kk"
