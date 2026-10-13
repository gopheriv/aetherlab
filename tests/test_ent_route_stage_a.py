from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest


def test_vector_search_falls_back_when_chroma_returns_no_hits(tmp_path, monkeypatch):
    from aetherlab.core.models import RagHit, RagResult
    from aetherlab.services.rag import LocalVectorRag

    settings = SimpleNamespace(
        chroma_path=tmp_path / "chroma",
        library_path=tmp_path / "library",
        reference_sources_path=None,
    )
    search = LocalVectorRag(settings)
    empty = RagResult(keywords=["ускорение"], hits=[], backend="chromadb")
    fallback = RagResult(
        keywords=["ускорение"],
        hits=[
            RagHit(
                source_path="book.pdf",
                page_number=16,
                score=1.0,
                excerpt="Постоянное ускорение.",
            )
        ],
        backend="filesystem",
    )
    calls = []
    monkeypatch.setattr(search, "_try_chromadb", lambda keywords, limit: empty)
    monkeypatch.setattr(
        search,
        "_filesystem_search",
        lambda keywords, limit: calls.append((keywords, limit)) or fallback,
    )

    result = asyncio.run(search.search(["ускорение"], limit=4))

    assert result.backend == "filesystem"
    assert result.hits[0].page_number == 16
    assert calls == [(["ускорение"], 4)]


def test_grounding_context_keeps_evidence_ids_and_pdf_pages():
    from aetherlab.services.lesson_planner import _grounding_context

    rag = SimpleNamespace(
        hits=[
            SimpleNamespace(
                source_name="Физика Закирова 10 ЖМ.pdf",
                page_number=16,
                excerpt="Үдеу тұрақты болғандағы жылдамдық формуласы.",
            )
        ]
    )
    text = asyncio.run(
        _grounding_context("тұрақты үдеу", SimpleNamespace(), rag)
    )
    records = json.loads(text)
    assert records == [
        {
            "evidence_id": "R01",
            "source": "Физика Закирова 10 ЖМ.pdf",
            "pdf_page_1based": 16,
            "excerpt": "Үдеу тұрақты болғандағы жылдамдық формуласы.",
        }
    ]


def test_model_truncation_retries_once_with_compact_plan(monkeypatch):
    from aetherlab.services import lesson_planner, llm_client, model_policy

    calls = []
    first = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content=""))]
    )
    valid = {
        "title": "Кинематика",
        "chapters": [
            {"id": "one", "title": "Түсінік", "kind": "scene", "beats": ["Қозғалыс"]}
        ],
    }
    second = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=json.dumps(valid, ensure_ascii=False)),
            )
        ]
    )

    class Completions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return first if len(calls) == 1 else second

    monkeypatch.setattr(llm_client, "make_client", lambda settings: SimpleNamespace(chat=SimpleNamespace(completions=Completions())))
    monkeypatch.setattr(model_policy, "system_prompt_message", lambda settings, prompt: prompt)
    monkeypatch.setattr(lesson_planner, "request_temperature", lambda settings, value: value)

    plan = asyncio.run(
        lesson_planner._plan_remote(
            "үдеу",
            SimpleNamespace(llm_model="test-model"),
            "high_school",
            "kk",
            "R01, PDF page 16",
        )
    )

    assert len(calls) == 2
    assert calls[0]["max_tokens"] == calls[1]["max_tokens"] == 8192
    assert "COMPACT RETRY" in calls[1]["messages"][1]["content"]
    assert plan.title == "Кинематика"
    assert plan.language == "kk"


def test_second_truncation_has_a_distinct_error(monkeypatch):
    from aetherlab.services import lesson_planner, llm_client, model_policy

    class Completions:
        async def create(self, **kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="length", message=SimpleNamespace(content="")
                    )
                ]
            )

    monkeypatch.setattr(llm_client, "make_client", lambda settings: SimpleNamespace(chat=SimpleNamespace(completions=Completions())))
    monkeypatch.setattr(model_policy, "system_prompt_message", lambda settings, prompt: prompt)
    monkeypatch.setattr(lesson_planner, "request_temperature", lambda settings, value: value)

    with pytest.raises(lesson_planner.LessonPlanningError) as exc:
        asyncio.run(
            lesson_planner._plan_remote(
                "topic", SimpleNamespace(llm_model="test-model"), "high_school", "ru", "refs"
            )
        )

    assert exc.value.code == "truncated"


def test_planning_error_does_not_claim_that_model_is_disconnected(monkeypatch):
    from aetherlab.services import lesson_planner

    async def fail(*_args, **_kwargs):
        raise lesson_planner.LessonPlanningError("truncated")

    monkeypatch.setattr(lesson_planner, "_grounding_context", fail)
    plan = asyncio.run(
        lesson_planner.plan_lesson(
            "a topic", SimpleNamespace(openai_api_key="configured"), language="ru"
        )
    )

    assert plan.model_name == "localized-planning-error"
    assert "обрез" in plan.chapters[0].goal.casefold() or "не законч" in plan.chapters[0].goal.casefold()
    assert "не подключ" not in plan.chapters[0].goal.casefold()


def test_reference_folder_selection_is_persisted_and_validated(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings, save_reference_sources_path

    root = tmp_path / "References"
    root.mkdir()
    data_dir = tmp_path / "app-data"
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(data_dir))
    monkeypatch.delenv("AETHERLAB_REFERENCE_SOURCES", raising=False)

    save_reference_sources_path(root)

    assert load_settings().reference_sources_path == root.resolve()
    with pytest.raises((FileNotFoundError, NotADirectoryError)):
        save_reference_sources_path(tmp_path / "missing")


def test_accelerated_motion_route_is_shared_and_numbers_do_not_drift():
    from aetherlab.services.ent_lesson_catalog import curated_ent_lesson, route_content

    plans = [curated_ent_lesson("constant_acceleration", lang) for lang in ("kk", "ru", "en")]
    assert all(plan is not None for plan in plans)
    assert [plan.questions[0].answer[0] for plan in plans] == ["B", "B", "B"]
    for plan in plans:
        worked = next(chapter for chapter in plan.chapters if chapter.id == "worked-example")
        example = " ".join(worked.beats).replace("1.5", "1,5")
        assert all(value in example for value in ("2", "1,5", "4", "8", "20"))
        assert any("PDF с. 15–18" in cite for cite in plan.chapters[1].citations)
        assert any("PDF с. 2" in cite and "PDF с. 37" in cite for cite in plan.chapters[4].citations)
    assert [route_content(lang)["answer_key"]["choice_id"] for lang in ("kk", "ru", "en")] == ["B"] * 3
    visuals = [route_content(lang)["verified_question_visual"] for lang in ("kk", "ru", "en")]
    assert visuals[0] == visuals[1] == visuals[2]
    assert sum(visuals[0]["area_segments_m"]) == visuals[0]["answer_m"] == 12
    assert visuals[0]["graph_points_time_s_velocity_mps"] == [[0, 0], [1, 4], [3, 4], [4, 0]]
    assert curated_ent_lesson("равноускоренное движение", "ru") is not None
    assert curated_ent_lesson("кинематика", "ru") is None
