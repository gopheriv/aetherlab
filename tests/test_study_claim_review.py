"""Evidence-aware prose review for study-document exports."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aetherlab.core.models import ProblemRequest, RagHit, RagResult
from aetherlab.services import study_document as sd


def test_solar_irradiance_comparison_is_calculated_and_corrected():
    content = {
        "title": "Blackbody radiation",
        "worked_example": {
            "answer": (
                r"F=3.54\times 10^{7}\,\mathrm{W/m^2}, roughly half of the "
                "solar constant at Earth's orbit."
            )
        },
    }

    corrected, checks, citations = sd.audit_known_numeric_claims(content)

    answer = corrected["worked_example"]["answer"]
    assert "about 26,010 times the solar irradiance" in answer
    assert "blackbody surface" in answer and "Earth's orbit" in answer
    assert checks[0]["status"] == "corrected"
    assert checks[0]["ratio"] == 26010.2866
    assert any("nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html" in c for c in citations)


def test_solar_irradiance_comparison_that_matches_reference_is_preserved():
    content = {"abstract": "A flux of 680.5 W/m^2 is about half the solar constant."}

    revised, checks, _ = sd.audit_known_numeric_claims(content)

    assert revised == content
    assert checks[0]["status"] == "passed"
    assert checks[0]["ratio"] == 0.5


def test_source_review_corrects_only_an_exact_claim(monkeypatch):
    from aetherlab.services import llm_client

    raw = json.dumps({
        "status": "issues_found",
        "note": "One value conflicts with the supplied reference.",
        "issues": [{
            "original": "The wavelength is 580 nm.",
            "correction": "The wavelength is 520 nm.",
            "reason": "The cited table gives 520 nm for this condition.",
            "source": "Physics table, p. 12",
        }],
    })

    async def create(**kwargs):
        assert kwargs["max_tokens"] == 1800
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )
    monkeypatch.setattr(llm_client, "make_client", lambda _settings: fake_client)
    settings = SimpleNamespace(
        openai_api_key="test-key",
        openai_base_url="https://api.minimax.io/v1",
        llm_model="MiniMax-M3",
        llm_timeout_seconds=30,
    )
    rag = RagResult(
        keywords=["wavelength"],
        hits=[RagHit("physics.pdf", 12, 0.9, "The measured wavelength is 520 nm." , source_label="Physics table")],
        backend="test",
    )
    content = {"abstract": "The wavelength is 580 nm. The title remains unchanged."}

    revised, report = asyncio.run(sd.review_study_claims(content, rag, settings))

    assert revised["abstract"].startswith("The wavelength is 520 nm.")
    assert report["status"] == "corrected"
    assert report["source_review"]["issues"][0]["status"] == "corrected"
    assert report["source_review"]["sources"] == ["Physics table, p.12"]


def test_missing_sources_are_explicitly_not_checked_in_report_and_pdf():
    content = {"title": "Radiation", "abstract": "Radiation carries energy."}
    rag = RagResult(keywords=[], hits=[], backend="empty")

    revised, report = asyncio.run(
        sd.review_study_claims(content, rag, SimpleNamespace(openai_api_key=None))
    )
    document = sd.build_document(
        revised, "topic", ProblemRequest(prompt="Explain radiation"), [], [], None,
        "AetherLab", report,
    )
    source, _ = document.render(set())

    assert report["status"] == "not_checked"
    assert "not be treated as independently verified" in report["note"]
    assert "Prose claim review (advisory)" in source
    assert "not be treated as independently verified" in source
    assert "claimreviewbox" in source


def test_study_export_saves_corrected_content_and_review_sidecar(tmp_path, monkeypatch):
    content = {
        "title": "Blackbody radiation",
        "abstract": "A study guide.",
        "sections": [],
        "worked_example": {
            "answer": (
                r"F=3.54\times 10^{7}\,\mathrm{W/m^2}, roughly half of the "
                "solar constant at Earth's orbit."
            )
        },
    }

    async def author(*_args, **_kwargs):
        return content, "test-model"

    def compile_doc(doc, tex_path, _cancel):
        source, _ = doc.render(set())
        tex_path.write_text(source, encoding="utf-8")
        pdf_path = tex_path.with_suffix(".pdf")
        pdf_path.write_bytes(b"pdf-test")
        return pdf_path, len(doc.blocks), ""

    monkeypatch.setattr(sd, "author_document", author)
    monkeypatch.setattr(sd, "compile_healing", compile_doc)
    request = ProblemRequest(prompt="Explain blackbody radiation")
    rag = RagResult(keywords=[], hits=[], backend="empty")

    result = asyncio.run(sd.write_study_document(
        request, SimpleNamespace(summary="Blackbody radiation."), rag,
        SimpleNamespace(openai_api_key=None), Path(tmp_path),
    ))

    saved_content = json.loads((tmp_path / "content.json").read_text(encoding="utf-8"))
    saved_review = json.loads((tmp_path / "claim_review.json").read_text(encoding="utf-8"))
    tex = (tmp_path / "document.tex").read_text(encoding="utf-8")
    assert result.claim_review["status"] == "corrected"
    assert saved_content["worked_example"]["answer"].count("26,010 times") == 1
    assert saved_review["known_fact_checks"][0]["status"] == "corrected"
    assert "NASA Earth Fact Sheet" in tex
    assert "Prose claim review (advisory)" in tex
