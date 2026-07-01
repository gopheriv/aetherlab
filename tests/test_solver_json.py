"""WP3: solver JSON parsing, response_format fallback, deterministic path."""

from __future__ import annotations

import types

import pytest

from aetherlab.services.llm import AsyncLLMCoordinator, _is_response_format_unsupported


def _make_response(content: str):
    message = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=message)
    return types.SimpleNamespace(choices=[choice])


class _FakeCompletions:
    """Records calls; raises on response_format to emulate a picky server."""

    def __init__(self, reject_response_format: bool, content: str) -> None:
        self.reject_response_format = reject_response_format
        self.content = content
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.reject_response_format and "response_format" in kwargs:
            raise Exception("Unknown parameter: 'response_format' is not supported")
        return _make_response(self.content)


def _install_fake_client(coord: AsyncLLMCoordinator, completions: _FakeCompletions) -> None:
    coord._client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=completions)
    )


def test_parse_strict_json(settings_with_key) -> None:
    coord = AsyncLLMCoordinator(settings_with_key)
    payload = coord._parse_json('{"summary": "ok", "variables": {"a": 1}}')
    assert payload["summary"] == "ok"
    assert payload["variables"] == {"a": 1}


def test_parse_embedded_json(settings_with_key) -> None:
    coord = AsyncLLMCoordinator(settings_with_key)
    noisy = "Sure! Here is the result:\n{\"summary\": \"embedded\"}\nHope that helps."
    payload = coord._parse_json(noisy)
    assert payload["summary"] == "embedded"


def test_parse_json_raises_on_garbage(settings_with_key) -> None:
    coord = AsyncLLMCoordinator(settings_with_key)
    with pytest.raises(Exception):
        coord._parse_json("no json anywhere here")


async def test_response_format_used_when_supported(settings_with_key) -> None:
    coord = AsyncLLMCoordinator(settings_with_key)
    completions = _FakeCompletions(reject_response_format=False, content='{"summary": "hi"}')
    _install_fake_client(coord, completions)
    await coord._create_completion([{"role": "user", "content": "hi"}])
    assert len(completions.calls) == 1
    assert completions.calls[0].get("response_format") == {"type": "json_object"}


async def test_response_format_fallback_when_rejected(settings_with_key) -> None:
    coord = AsyncLLMCoordinator(settings_with_key)
    completions = _FakeCompletions(reject_response_format=True, content='{"summary": "hi"}')
    _install_fake_client(coord, completions)
    resp = await coord._create_completion([{"role": "user", "content": "hi"}])
    # First call includes response_format (rejected); retry drops it and succeeds.
    assert len(completions.calls) == 2
    assert "response_format" in completions.calls[0]
    assert "response_format" not in completions.calls[1]
    assert resp.choices[0].message.content == '{"summary": "hi"}'


async def test_solve_remote_end_to_end(settings_with_key, sample_request) -> None:
    coord = AsyncLLMCoordinator(settings_with_key)
    content = '{"summary": "Solved", "derivation_steps": ["s1"], "keywords": ["k"], "variables": {"g": 9.8}}'
    completions = _FakeCompletions(reject_response_format=False, content=content)
    _install_fake_client(coord, completions)
    result = await coord._solve_remote(sample_request)
    assert result.summary == "Solved"
    assert result.derivation_steps == ["s1"]
    assert result.variables == {"g": 9.8}
    assert result.model_name == "test-model"


async def test_no_key_deterministic_fallback(settings_no_key, sample_request) -> None:
    coord = AsyncLLMCoordinator(settings_no_key)
    result = await coord.solve(sample_request)
    assert result.model_name == "deterministic-fallback"
    assert result.derivation_steps  # non-empty scaffold
    assert result.keywords


def test_is_response_format_unsupported() -> None:
    assert _is_response_format_unsupported(Exception("Unknown parameter: response_format"))
    assert _is_response_format_unsupported(Exception("invalid parameter provided"))
    assert not _is_response_format_unsupported(Exception("Incorrect API key provided"))
    assert not _is_response_format_unsupported(Exception("Connection timed out"))
