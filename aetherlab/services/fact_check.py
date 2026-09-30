"""Ground a lesson in real textbooks (Phase 4).

For each chapter, retrieve the most relevant textbook passages (RAG) and:
  1. attach human-readable citations (source + page) for on-screen / study-guide
     display, and
  2. run a light LLM fact-check of the chapter narration against those passages,
     recording a short note and — when a claim is clearly unsupported — a
     corrected narration.

Fail-soft at every step: no API key skips the LLM check (citations still
attach); no library / RAG error leaves the chapter untouched. A student must
never see a broken lesson because grounding was unavailable.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from aetherlab.core.models import LessonPlan
from aetherlab.services.model_policy import request_temperature

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

FACT_CHECK_SYSTEM_PROMPT = """You are AetherLab's fact-checker for a physics lesson. You are given a chapter's
spoken narration and a few textbook passages. Judge ONLY whether the narration
is supported by the passages and by standard physics; do not rewrite for style.

Return STRICT JSON only:
{"supported": true|false,
 "note": "one short sentence — what's right, or exactly what's off",
 "correction": "the corrected narration IF and only if a claim was wrong, else \"\""}

Be conservative: only mark unsupported for a real physics error or an
unsupported specific claim (a number/law that contradicts the passages). Vague
but correct phrasing is 'supported'."""


async def fact_check_lesson(
    plan: LessonPlan,
    settings: "AppSettings",
    *,
    per_chapter_passages: int = 3,
) -> LessonPlan:
    """Annotate every chapter with citations + a fact-check note (in place).

    Returns the same plan for chaining. Never raises.
    """
    try:
        from aetherlab.services.llm import extract_keywords
        from aetherlab.services.rag import LocalVectorRag

        rag = LocalVectorRag(settings)
    except Exception:  # noqa: BLE001
        return plan

    for chapter in plan.chapters:
        query = chapter.citation_query or f"{plan.topic} {chapter.title}"
        try:
            result = await rag.search(extract_keywords(query) or [plan.topic], limit=per_chapter_passages)
            hits = result.hits if result else []
        except Exception:  # noqa: BLE001
            hits = []
        if hits:
            chapter.citations = [_cite(hit) for hit in hits]
        # LLM fact-check only when a key AND passages exist.
        if settings.openai_api_key and hits and chapter.narration.strip():
            try:
                await _check_chapter(chapter, hits, settings)
            except Exception as exc:  # noqa: BLE001 — grounding is best-effort
                log.info("Fact-check skipped for '%s': %s", chapter.title, exc)
    return plan


def _cite(hit) -> str:
    """A short, displayable citation from a RagHit."""
    name = getattr(hit, "source_name", None) or "reference"
    page = getattr(hit, "page_number", None)
    return f"{name}, p.{page}" if page else str(name)


async def _check_chapter(chapter, hits, settings: "AppSettings") -> None:
    from aetherlab.services.llm_client import make_client


    client = make_client(settings)
    passages = "\n\n".join(f"[{_cite(h)}]\n{h.excerpt[:500]}" for h in hits[:3])
    user = (
        f"## Chapter narration\n{chapter.narration}\n\n"
        f"## Textbook passages\n{passages}\n\nFact-check the narration now."
    )
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": FACT_CHECK_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        temperature=request_temperature(settings, 0.0),
        max_tokens=1024,
    )
    from aetherlab.services.model_json import load_model_json

    raw = response.choices[0].message.content or ""
    payload = load_model_json(raw)
    supported = bool(payload.get("supported", True))
    note = str(payload.get("note", "")).strip()
    correction = str(payload.get("correction", "")).strip()
    chapter.fact_check = ("✓ " if supported else "⚠ ") + note if note else (
        "✓ grounded" if supported else "⚠ unsupported claim"
    )
    if not supported and correction:
        chapter.narration = correction
