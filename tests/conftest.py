"""Shared fixtures for the AetherLab test suite.

Nothing here touches the network or spawns a real Manim render — every test
mocks or monkeypatches those boundaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.core.settings import AppSettings


def make_settings(tmp_path: Path, *, api_key: str | None = None) -> AppSettings:
    """Build an AppSettings pointing entirely at a throwaway temp dir."""
    return AppSettings(
        data_dir=tmp_path,
        cache_path=tmp_path / "cache.sqlite3",
        chroma_path=tmp_path / "chroma",
        library_path=tmp_path / "library",
        openai_api_key=api_key,
        openai_base_url=None,
        llm_model="test-model",
        llm_timeout_seconds=5.0,
    )


@pytest.fixture
def settings_no_key(tmp_path: Path) -> AppSettings:
    return make_settings(tmp_path, api_key=None)


@pytest.fixture
def settings_with_key(tmp_path: Path) -> AppSettings:
    return make_settings(tmp_path, api_key="test-key")


@pytest.fixture
def sample_request() -> ProblemRequest:
    return ProblemRequest(prompt="Solve the simple pendulum for large angles.")


@pytest.fixture
def sample_solver() -> SolverResult:
    return SolverResult(
        summary="Large-angle pendulum via elliptic integrals.",
        derivation_steps=["Write the equation of motion.", "Integrate energy."],
        keywords=["pendulum", "nonlinear"],
        variables={"damping": 0.2, "stiffness": 1.0, "mass": 1.0},
        model_name="test-model",
    )


@pytest.fixture
def sample_rag() -> RagResult:
    return RagResult(keywords=["pendulum"], hits=[], backend="none")
