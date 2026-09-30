"""Topic → structured lesson plan (the top of the topic-explainer pipeline).

This is the analogue of SceneGenerator.storyboard(), one level up: instead of
directing a single ~20s scene, it turns a *topic* into a multi-chapter teaching
curriculum. A hot LLM pass (temperature ~0.8) returns strict JSON; the result
is grounded in the RAG textbook library. Everything is fail-soft: no API key,
a bad reply, or any error yields a deterministic template lesson keyed to the
problem domain, so the topic explainer always produces *something* coherent.

Reuses: services/rag (grounding), services/scene_templates.detect_domain +
services/llm.extract_keywords/FALLBACK_EQUATIONS (the keyless template).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from aetherlab.core.models import LessonChapter, LessonPlan, LessonQuestion, RagResult
from aetherlab.services.model_policy import request_temperature

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

VALID_AUDIENCES = ("high_school", "ap", "undergrad")
_RENDERED_CHAPTER_KINDS = {"scene", "equation_card", "recap"}

LESSON_PLANNER_SYSTEM_PROMPT = """You are AetherLab's lesson designer — a physicist
and a gifted teacher in the
3Blue1Brown / Khan Academy tradition. Turn ONE topic into a structured video
lesson a student genuinely learns from. Design the curriculum only — no code.

Return STRICT JSON only (no markdown, no prose) with exactly these keys:
{
  "title": "the lesson title",
  "audience": "high_school" | "ap" | "undergrad",
  "prerequisites": ["what the student should already know"],
  "objectives": ["by the end, the student can ..."],
  "misconception": "the single most common wrong idea to pre-empt",
  "chapters": [
    {
      "id": "ch1",
      "title": "short chapter title",
      "goal": "what the student should get from this chapter",
      "kind": "scene" | "equation_card" | "interactive" | "recap",
      "beats": ["what happens, beat by beat"],
      "narration": "the spoken script for this chapter (2-5 sentences, warm, plain)",
      "key_equations": ["LaTeX, inline subset only, governing form first"],
      "key_symbols": ["symbol: plain-language meaning"],
      "prediction": {"q": "...", "choices": ["A", "B", "C", "D"], "answer": "the exact choice text or its letter", "why": "..."} | null,
      "retrieval": {"q": "...", "choices": ["A", "B", "C", "D"], "answer": "the exact choice text or its letter", "why": "..."} | null,
      "citation_query": "a few words to retrieve the textbook passage for this chapter"
    }
  ],
  "questions": [
    {"q": "...", "choices": ["A", "B", "C", "D"], "answer": "B", "why": "one line"},
    {"q": "an open question", "answer": "a model answer", "why": ""}
  ]
}

Teaching rules (obey all):
- HOOK FIRST: chapter 1 opens with a question or a surprise, never a definition.
- Put a multiple-choice prediction on the first rendered chapter, before its video plays.
- Add a short retrieval question to rendered chapters after the first so it can be asked before the next chapter.
- Keep prediction/retrieval questions focused on one observable concept; use null when a chapter has no useful check.
- CONCRETE BEFORE ABSTRACT: show the real object before the equation.
- Put a brief key-symbol card before the first governing equation; define every symbol in plain language.
- BUILD THE MATH term-by-term; name each symbol as it appears.
- NAME THE MISCONCEPTION explicitly just after the hook and correct it before the math.
- Use analogies and everyday referents.
- Include one WORKED EXAMPLE chapter with real numbers, and a RECAP chapter.
- Keep each chapter to about 1-2 minutes; spoken narration carries full sentences, on-screen text uses short labels and equation fragments, never full-sentence captions.
- AUDIENCE sets depth: high_school avoids calculus; undergrad uses it freely.
- 4-7 chapters. Give the interactive/"play with it" chapter kind "interactive".
- 2-4 questions, mostly multiple-choice, at least one open.
Ground every claim in the provided reference context; do not invent constants."""


async def plan_lesson(
    topic: str,
    settings: "AppSettings",
    rag: "RagResult | None" = None,
    audience: str = "undergrad",
) -> LessonPlan:
    """Plan a lesson for ``topic``. Never raises — falls back to a template."""
    topic = (topic or "").strip()
    if not topic:
        topic = "A physics concept"

    if not settings.openai_api_key:
        return _template_lesson(topic, audience)

    try:
        context = await _grounding_context(topic, settings, rag)
        plan = await _plan_remote(topic, settings, audience, context)
        if plan is not None and _has_learning_scaffolds(plan):
            return plan
    except Exception as exc:  # noqa: BLE001 — planning is best-effort
        log.info("Lesson planning failed (%s); using template lesson.", exc)
    return _template_lesson(topic, audience)


def _has_learning_scaffolds(plan: LessonPlan) -> bool:
    """Require the fields needed for prediction, symbol pretraining, and recall."""
    rendered = [chapter for chapter in plan.chapters if chapter.kind in _RENDERED_CHAPTER_KINDS]
    if not rendered:
        return False
    prediction = rendered[0].prediction
    has_prediction = (
        isinstance(prediction, dict)
        and bool(str(prediction.get("q", "")).strip())
        and isinstance(prediction.get("choices"), list)
        and len(prediction["choices"]) >= 2
        and bool(str(prediction.get("answer", "")).strip())
    )
    has_symbols = any(ch.key_symbols for ch in plan.chapters)
    has_retrieval = any(
        isinstance(ch.retrieval, dict)
        and bool(str(ch.retrieval.get("q", "")).strip())
        and isinstance(ch.retrieval.get("choices"), list)
        and len(ch.retrieval["choices"]) >= 2
        for ch in plan.chapters[1:]
    )
    return has_prediction and has_symbols and has_retrieval


async def _grounding_context(topic: str, settings: "AppSettings", rag: "RagResult | None") -> str:
    """Retrieve a few textbook excerpts to ground the plan (best-effort)."""
    try:
        if rag is None:
            from aetherlab.services.llm import extract_keywords
            from aetherlab.services.rag import LocalVectorRag

            rag = await LocalVectorRag(settings).search(extract_keywords(topic), limit=4)
        lines = []
        for hit in (rag.hits if rag else [])[:4]:
            lines.append(f"- {hit.source_name}: {hit.excerpt[:300]}")
        return "\n".join(lines) if lines else "No local references available."
    except Exception:  # noqa: BLE001
        return "No local references available."


async def _plan_remote(
    topic: str, settings: "AppSettings", audience: str, context: str
) -> "LessonPlan | None":
    from aetherlab.services.llm_client import make_client
    from aetherlab.services.model_policy import system_prompt_message

    client = make_client(settings)
    if audience not in VALID_AUDIENCES:
        audience = "undergrad"
    user = (
        f"## Topic\n{topic}\n\n"
        f"## Target audience\n{audience}\n\n"
        f"## Reference context (ground the lesson in this)\n{context}\n\n"
        "Design the lesson JSON now."
    )
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            system_prompt_message(settings, LESSON_PLANNER_SYSTEM_PROMPT),
            {"role": "user", "content": user},
        ],
        temperature=request_temperature(settings, 0.8),
        max_tokens=8192,
    )
    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise ValueError("Lesson plan reply truncated at the token limit.")
    from aetherlab.services.model_json import load_model_json

    content = choice.message.content or ""
    payload = load_model_json(content)
    if not isinstance(payload, dict) or "chapters" not in payload:
        return None
    payload.setdefault("topic", topic)
    plan = LessonPlan.from_json(payload)
    plan.topic = topic
    plan.model_name = settings.llm_model
    return plan


def _template_lesson(topic: str, audience: str = "undergrad") -> LessonPlan:
    """Deterministic keyless lesson keyed to the problem domain.

    Picks a canned 4-chapter outline per domain
    (oscillator/pendulum/orbit/em_field/wave)
    so the offline experience is still a coherent, domain-correct lesson.
    """
    from aetherlab.services.llm import FALLBACK_EQUATIONS, extract_keywords
    from aetherlab.services.scene_templates import detect_domain

    if audience not in VALID_AUDIENCES:
        audience = "undergrad"
    keywords = extract_keywords(topic) or [topic]
    domain = detect_domain(keywords, {})
    equations = FALLBACK_EQUATIONS.get(domain, FALLBACK_EQUATIONS["oscillator"])
    spec = _TEMPLATE_DOMAINS.get(domain, _TEMPLATE_DOMAINS["oscillator"])

    chapters = [
        LessonChapter(
            id="ch1",
            title="The question",
            goal="motivate the topic",
            kind="scene",
            beats=[spec["hook"]],
            narration=spec["hook"],
        ),
        LessonChapter(
            id="ch2",
            title="The idea",
            goal="build intuition",
            kind="scene",
            beats=[spec["intuition"], f"Common misconception: {spec['misconception']}"],
            narration=f"{spec['intuition']} {spec['misconception']}",
        ),
        LessonChapter(
            id="ch3",
            title="Key symbols",
            goal="learn each symbol before meeting the full equation",
            kind="equation_card",
            beats=list(spec["symbols"]),
            narration="First, learn the symbols we will use: " + "; ".join(spec["symbols"]) + ".",
            key_symbols=list(spec["symbols"]),
        ),
        LessonChapter(
            id="ch4",
            title="The math",
            goal="derive the governing law",
            kind="equation_card",
            beats=[spec["math"]],
            narration=spec["math"],
            key_equations=list(equations),
        ),
        LessonChapter(
            id="ch5",
            title="Play with it",
            goal="explore the parameters",
            kind="interactive",
            beats=[spec["interactive"]],
            narration=spec["interactive"],
        ),
        LessonChapter(
            id="ch6",
            title="Recap",
            goal="consolidate",
            kind="recap",
            beats=[spec["recap"]],
            narration=spec["recap"],
        ),
    ]
    chapters[0].prediction = spec["prediction"]
    chapters[3].retrieval = spec["retrieval"]
    return LessonPlan(
        title=f"{topic.strip().capitalize()} — a visual explainer",
        topic=topic,
        audience=audience,
        prerequisites=spec["prereqs"],
        objectives=spec["objectives"],
        misconception=spec["misconception"],
        chapters=chapters,
        questions=[LessonQuestion(**q) for q in spec["questions"]],
        model_name="deterministic-template",
    )


_TEMPLATE_DOMAINS: dict[str, dict] = {
    "oscillator": {
        "hook": "Why does a mass on a spring keep bouncing back — and why does it slow to a stop?",
        "intuition": (
            "The spring always pushes toward equilibrium, so the mass overshoots, "
            "comes back, and overshoots again — while friction quietly drains the energy."
        ),
        "math": (
            "Newton's second law gives m x'' + c x' + k x = 0; its solution is a "
            "cosine wrapped in a decaying exponential."
        ),
        "interactive": (
            "Drag the damping and stiffness sliders and watch the envelope tighten "
            "and the frequency shift."
        ),
        "recap": (
            "Restoring force makes it oscillate; damping makes it decay. One equation "
            "captures both."
        ),
        "prereqs": ["Newton's second law", "basic trigonometry"],
        "objectives": [
            "Explain why oscillation happens",
            "Read the roles of damping and stiffness",
            "Recognize the damped-oscillator solution",
        ],
        "misconception": (
            "Damping does not change the mass's natural push-back — it removes energy, "
            "not the restoring force."
        ),
        "symbols": ["m: mass", "c: damping coefficient", "k: spring stiffness", "x: displacement from equilibrium"],
        "prediction": {
            "q": "If damping increases while the spring stays the same, what changes most directly?",
            "choices": ["The oscillations fade faster", "The equilibrium moves", "The mass becomes lighter", "The spring stops restoring"],
            "answer": "The oscillations fade faster",
            "why": "Damping removes energy from the motion.",
        },
        "retrieval": {
            "q": "In a mass-spring oscillator, which effect pulls the mass toward equilibrium?",
            "choices": ["The spring's restoring force", "The damping force", "The mass itself", "The initial push"],
            "answer": "The spring's restoring force",
            "why": "The spring force points back toward equilibrium; damping removes energy.",
        },
        "questions": [
            {
                "q": "Increasing damping mainly changes...",
                "choices": ["the amplitude decay", "the spring constant", "the mass", "nothing"],
                "answer": "the amplitude decay",
                "why": "Damping drains energy, tightening the decay envelope.",
            },
            {
                "q": "In your own words, why does the mass overshoot equilibrium?",
                "answer": (
                    "It carries momentum, so it passes the rest point before the "
                    "restoring force turns it around."
                ),
                "why": "",
            },
        ],
    },
    "pendulum": {
        "hook": "Two pendulums, different weights — which one swings faster?",
        "intuition": (
            "Gravity pulls the bob back toward the bottom; the longer the string, "
            "the slower the swing — and the mass surprisingly doesn't matter."
        ),
        "math": (
            "For small angles, θ'' + (g/ℓ) sin θ = 0 becomes θ'' + (g/ℓ) θ = 0, "
            "giving a period T ≈ 2π√(ℓ/g)."
        ),
        "interactive": (
            "Change the length and gravity and watch the period respond — try "
            "changing the mass and see nothing happen."
        ),
        "recap": (
            "Period depends on length and gravity, not mass. Small-angle motion is "
            "simple harmonic."
        ),
        "prereqs": ["forces and gravity", "basic trigonometry"],
        "objectives": [
            "Explain what sets a pendulum's period",
            "Justify why mass drops out",
            "State the small-angle period",
        ],
        "misconception": (
            "A heavier bob does NOT swing faster — mass cancels out of the equation "
            "of motion."
        ),
        "symbols": ["theta: angular displacement", "L: pendulum length", "g: gravitational acceleration", "T: period"],
        "prediction": {
            "q": "For small swings, what happens to the period if the pendulum length is made four times longer?",
            "choices": ["It doubles", "It quadruples", "It halves", "It stays the same"],
            "answer": "It doubles",
            "why": "The period scales with the square root of length.",
        },
        "retrieval": {
            "q": "Which quantities set the small-angle restoring acceleration along the arc?",
            "choices": ["Gravity and angular displacement", "Bob mass alone", "String color", "Air pressure only"],
            "answer": "Gravity and angular displacement",
            "why": "For small angles, the tangential restoring acceleration is approximately proportional to g times theta.",
        },
        "questions": [
            {
                "q": "The period of a simple pendulum depends on...",
                "choices": ["length and gravity", "mass and length", "mass only", "amplitude only"],
                "answer": "length and gravity",
                "why": "T ≈ 2π√(ℓ/g); mass cancels.",
            },
            {
                "q": "Why does mass cancel out of the pendulum equation?",
                "answer": "Gravity's pull and inertia both scale with mass, so it divides out.",
                "why": "",
            },
        ],
    },
    "orbit": {
        "hook": "What keeps a planet from either flying away or falling into the star?",
        "intuition": (
            "Gravity constantly bends the planet's straight-line motion into a closed "
            "curve — a perpetual falling that never lands."
        ),
        "math": (
            "An inverse-square force F = -GMm/r² gives an ellipse r(φ) = p/(1 + e cos φ), "
            "with equal areas swept in equal times."
        ),
        "interactive": (
            "Change the eccentricity and watch the orbit stretch while the swept-area "
            "rate stays constant."
        ),
        "recap": (
            "Gravity plus sideways motion makes a stable ellipse; Kepler's laws "
            "describe its shape and timing."
        ),
        "prereqs": ["Newton's law of gravitation", "vectors"],
        "objectives": [
            "Explain why orbits are stable",
            "Relate the shape to eccentricity",
            "State Kepler's equal-area law",
        ],
        "misconception": (
            "Orbiting objects are not weightless because gravity is absent — they are "
            "in continuous free fall."
        ),
        "symbols": ["G: gravitational constant", "M: central mass", "r: distance from the center", "e: orbital eccentricity"],
        "prediction": {
            "q": "As a planet moves closer to its star along an elliptical orbit, how does its speed change?",
            "choices": ["It speeds up", "It slows down", "It becomes zero", "It stays exactly constant"],
            "answer": "It speeds up",
            "why": "The planet moves fastest near the star while conserving angular momentum and energy.",
        },
        "retrieval": {
            "q": "What does Kepler's equal-area rule say?",
            "choices": ["Equal areas are swept in equal times", "Equal distances are traveled in equal times", "Every orbit is circular", "Gravity is absent in orbit"],
            "answer": "Equal areas are swept in equal times",
            "why": "The rule expresses conservation of angular momentum.",
        },
        "questions": [
            {
                "q": "Kepler's second law says a planet sweeps out...",
                "choices": [
                    "equal areas in equal times",
                    "equal angles in equal times",
                    "equal distances in equal times",
                    "a perfect circle",
                ],
                "answer": "equal areas in equal times",
                "why": "Angular momentum is conserved.",
            },
            {
                "q": "Why doesn't an orbiting planet fall into its star?",
                "answer": (
                    "Its sideways velocity keeps carrying it past the star as gravity "
                    "bends its path."
                ),
                "why": "",
            },
        ],
    },
    "em_field": {
        "hook": "If you place a tiny positive test charge nearby, which way will it start to move?",
        "intuition": (
            "A positive charge pushes field arrows outward, a negative charge pulls "
            "them inward, and a dipole bends those arrows from source to sink."
        ),
        "math": (
            "Coulomb's law gives E = kq/r^2 for one charge; fields add vector by vector, "
            "so a dipole is the sum of a positive and a negative source."
        ),
        "interactive": (
            "Move the charges closer or farther apart and watch the field lines tighten "
            "between them."
        ),
        "recap": (
            "Electric field lines show direction and relative strength: out of positive "
            "charge, into negative charge, denser where the force is stronger."
        ),
        "prereqs": ["vectors", "Coulomb's law"],
        "objectives": [
            "Predict field direction from charge sign",
            "Explain field-line density",
            "Add fields from two charges",
        ],
        "misconception": (
            "Field lines are not physical wires; they are a map of the force a positive "
            "test charge would feel."
        ),
        "symbols": ["E: electric field", "q: source charge", "r: distance from the charge", "k: Coulomb constant"],
        "prediction": {
            "q": "Which way does the electric field point around an isolated positive charge?",
            "choices": ["Outward", "Inward", "In circles", "It has no direction"],
            "answer": "Outward",
            "why": "The field points in the direction a positive test charge would be pushed.",
        },
        "retrieval": {
            "q": "What does a denser set of electric field lines indicate?",
            "choices": ["A stronger electric field", "A larger test charge", "A slower clock", "A weaker field"],
            "answer": "A stronger electric field",
            "why": "Field-line density represents relative field strength.",
        },
        "questions": [
            {
                "q": "Electric field lines point...",
                "choices": [
                    "from positive to negative",
                    "from negative to positive",
                    "only in circles",
                    "only upward",
                ],
                "answer": "from positive to negative",
                "why": "They show the direction of force on a positive test charge.",
            },
            {
                "q": "What does a denser cluster of field lines mean?",
                "answer": "The electric field is stronger there.",
                "why": "",
            },
        ],
    },
    "wave": {
        "hook": "When you pluck a string, why do you hear one clear note?",
        "intuition": (
            "A disturbance travels along the medium and reflects, and only certain "
            "wavelengths fit — those standing patterns are the notes."
        ),
        "math": (
            "The wave equation ∂²y/∂t² = c² ∂²y/∂x² has travelling solutions "
            "y = A sin(kx - ωt) with speed c = ω/k."
        ),
        "interactive": (
            "Change frequency and wave speed and watch the wavelength and travelling "
            "pattern respond."
        ),
        "recap": (
            "Waves carry energy, not matter; speed, frequency, and wavelength are "
            "locked by c = fλ."
        ),
        "prereqs": ["oscillations", "basic trigonometry"],
        "objectives": [
            "Describe how a wave propagates",
            "Relate speed, frequency, wavelength",
            "Explain standing waves",
        ],
        "misconception": (
            "A wave transports energy and a pattern, not the medium itself — the string "
            "does not travel to your ear."
        ),
        "symbols": ["A: amplitude", "k: wavenumber", "omega: angular frequency", "c: wave speed"],
        "prediction": {
            "q": "At fixed wave speed, what happens to wavelength if frequency doubles?",
            "choices": ["It halves", "It doubles", "It stays the same", "It becomes zero"],
            "answer": "It halves",
            "why": "Wave speed is c = f times wavelength, so wavelength falls when frequency rises at fixed speed.",
        },
        "retrieval": {
            "q": "In a traveling wave, what moves through the medium?",
            "choices": ["The disturbance and its energy", "Each bit of matter permanently", "The medium's atoms to the source", "Nothing moves"],
            "answer": "The disturbance and its energy",
            "why": "The medium oscillates locally while the wave pattern carries energy.",
        },
        "questions": [
            {
                "q": "For a wave, speed equals...",
                "choices": [
                    "frequency × wavelength",
                    "frequency ÷ wavelength",
                    "amplitude × frequency",
                    "wavelength ÷ amplitude",
                ],
                "answer": "frequency × wavelength",
                "why": "c = fλ.",
            },
            {
                "q": "Does a wave carry the medium along with it? Explain.",
                "answer": (
                    "No — each bit of the medium oscillates in place; only the disturbance "
                    "and its energy move."
                ),
                "why": "",
            },
        ],
    },
}
