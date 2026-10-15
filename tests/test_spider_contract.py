"""Spider probes use owned screenshots, fake providers and temporary source only."""
import json
import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from aetherlab.core.settings import AppSettings
from aetherlab.services import spider


def owned_settings(tmp_path, **kwargs):
    return AppSettings(data_dir=tmp_path, cache_path=tmp_path / "cache", chroma_path=tmp_path / "chroma",
        library_path=tmp_path / "library", openai_api_key="owned-unused-key", openai_base_url="https://owned.invalid/v1",
        llm_model="k3-agent", **kwargs)


def reply(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason="stop")])


def provider(monkeypatch, responses):
    from aetherlab.services import llm_client
    calls = []
    async def create(**kwargs):
        calls.append(kwargs)
        return reply(responses.pop(0))
    monkeypatch.setattr(llm_client, "make_client", lambda *args, **kwargs:
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
                        _primary=SimpleNamespace(close=AsyncMock()), _fallback=None))
    return calls


def test_actual_async_client_is_awaited_and_model_temperature_is_resolved(tmp_path, monkeypatch):
    calls = provider(monkeypatch, [json.dumps({"has_error": False, "description": "Owned clean view"})])
    result = spider.inspect_and_repair(owned_settings(tmp_path), b"owned-png", tmp_path, tmp_path / "backups")
    assert len(calls) == 1 and calls[0]["temperature"] == 1.0
    assert result.summary == "Owned clean view" and not result.repaired


@pytest.mark.parametrize("response", ["", "not JSON", "{}", '{"has_error":"false"}', '[]', '{"description":"unknown"}'])
def test_invalid_diagnosis_never_claims_a_clean_screen(tmp_path, monkeypatch, response):
    provider(monkeypatch, [response])
    with pytest.raises(ValueError, match="diagnosis"):
        spider.inspect_and_repair(owned_settings(tmp_path), b"owned-png", tmp_path, tmp_path / "backups")


def patch_for(path, old="value = 1", new="value = 2"):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-{old}\n+{new}\n"


@pytest.mark.parametrize("extra", [
    "diff --git a/private.txt b/private.txt\ndeleted file mode 100644\n--- a/private.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-secret\n",
    "diff --git a/private.txt b/private.txt\nold mode 100644\nnew mode 100755\n",
    "diff --git a/private.bin b/private.bin\nGIT binary patch\nliteral 1\nx\n",
    "diff --git a/aetherlab/old.py b/aetherlab/new.py\nsimilarity index 99%\nrename from aetherlab/old.py\nrename to aetherlab/new.py\n--- a/aetherlab/old.py\n+++ b/aetherlab/new.py\n@@ -1 +1 @@\n-x=1\n+x=2\n",
], ids=["deletion", "mode", "binary", "rename"])
def test_every_patch_section_is_validated_before_git_can_mutate(extra):
    with pytest.raises(ValueError):
        spider._patch_paths(patch_for("aetherlab/owned.py") + extra)
    if "+++ /dev/null" in extra:
        with pytest.raises(ValueError):
            spider._patch_paths(patch_for("aetherlab/owned.py") + extra.split("\n", 1)[1])


def test_cancelled_scan_never_calls_provider_or_changes_source(tmp_path, monkeypatch):
    calls = provider(monkeypatch, [])
    cancelled = threading.Event()
    cancelled.set()
    result = spider.inspect_and_repair(owned_settings(tmp_path), b"owned-png", tmp_path, tmp_path / "backups",
                                      cancel_event=cancelled)
    assert calls == [] and not result.repaired and "cancel" in result.summary.lower()


def test_cancel_after_diagnosis_prevents_source_lookup_and_repair(tmp_path, monkeypatch):
    from aetherlab.services import llm_client
    cancelled = threading.Event()
    async def create(**kwargs):
        cancelled.set()
        return reply('{"has_error":true,"description":"owned error"}')
    monkeypatch.setattr(llm_client, "make_client", lambda *a, **k:
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
                        _primary=SimpleNamespace(close=AsyncMock()), _fallback=None))
    monkeypatch.setattr(spider, "_find_source", lambda *a: pytest.fail("Source read after cancellation"))
    result = spider.inspect_and_repair(owned_settings(tmp_path), b"owned-png", tmp_path, tmp_path / "backups",
                                      cancel_event=cancelled)
    assert not result.repaired and "cancel" in result.summary.lower()


def test_valid_patch_is_backed_up_and_syntax_failure_restores_original(tmp_path, monkeypatch):
    from aetherlab.core.proc import subprocess_kwargs
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True, **subprocess_kwargs())
    monkeypatch.setattr(spider.time, "strftime", lambda *args: "frozen-second")
    target = tmp_path / "aetherlab/owned.py"
    target.parent.mkdir()
    target.write_text("value = 1\n", encoding="utf-8")
    backups = tmp_path / "backups"
    assert spider._apply_patch(tmp_path, backups, patch_for("aetherlab/owned.py")) == ("aetherlab/owned.py",)
    assert target.read_text() == "value = 2\n"
    with pytest.raises(SyntaxError):
        spider._apply_patch(tmp_path, backups, patch_for("aetherlab/owned.py", "value = 2", "value = ("))
    assert target.read_text() == "value = 2\n"
    copies = list(backups.glob("*/aetherlab/owned.py"))
    assert len(copies) == 2 and {p.read_text() for p in copies} == {"value = 1\n", "value = 2\n"}


def test_different_vision_model_gets_its_own_temperature_policy(tmp_path, monkeypatch):
    calls = provider(monkeypatch, ['{"has_error":false}'])
    spider.inspect_and_repair(owned_settings(tmp_path, vision_model="qwen3.7-plus"), b"owned-png", tmp_path, tmp_path / "backups")
    assert calls[0]["model"] == "qwen3.7-plus" and calls[0]["temperature"] == 0.1


def test_unsafe_extra_diff_cannot_delete_unrelated_owned_file(tmp_path):
    target = tmp_path / "private.txt"
    target.write_text("secret\n")
    malicious = patch_for("aetherlab/owned.py") + "diff --git a/private.txt b/private.txt\ndeleted file mode 100644\n--- a/private.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-secret\n"
    with pytest.raises(ValueError):
        spider._apply_patch(tmp_path, tmp_path / "backups", malicious)
    traditional = malicious.replace("diff --git a/private.txt b/private.txt\ndeleted file mode 100644\n", "")
    with pytest.raises(ValueError):
        spider._apply_patch(tmp_path, tmp_path / "backups", traditional)
    assert target.read_text() == "secret\n" and not (tmp_path / "backups").exists()


@pytest.mark.parametrize("language", ["kk", "ru", "en"])
def test_unrepaired_error_does_not_display_a_clean_screen_status(language):
    from aetherlab.ui.spider_panel import SpiderPanel
    status, output, watch = [], [], []
    panel = SimpleNamespace(_language=language, _COPY=SpiderPanel._COPY,
        status_label=SimpleNamespace(setText=status.append), output=SimpleNamespace(setPlainText=output.append),
        watch_button=SimpleNamespace(setChecked=watch.append))
    result = spider.SpiderResult("Visible error found; no safe patch", details="Owned diagnosis")
    SpiderPanel._on_success(panel, result)
    assert status == [result.summary] and result.summary in output[0]
    assert status[0] != SpiderPanel._COPY[language]["done"]
    assert watch == []
    SpiderPanel._on_success(panel, spider.SpiderResult("Updated source", repaired=True))
    assert watch == [False], "Watch must pause after a source repair; the live view still uses old code"
    assert {"en": "Restart", "ru": "перезапуск", "kk": "қайта"}[language] in status[-1]


def test_crawl_handles_empty_project_and_pre_cancel_without_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(spider.subprocess, "run", lambda *a, **k: pytest.fail("Unexpected static tool"))
    cancelled = threading.Event()
    assert "no Python" in spider.crawl_project(tmp_path, cancelled, lambda p: None).summary
    (tmp_path / "owned.py").write_text("x = 1\n")
    cancelled.set()
    assert "stopped" in spider.crawl_project(tmp_path, cancelled, lambda p: pytest.fail("Progress after cancel")).summary


def test_crawl_reports_owned_syntax_and_lint_findings_with_hidden_subprocess(tmp_path, monkeypatch):
    import sys
    (tmp_path / "owned.py").write_text("value = (\n")
    observed, progress = [], []
    def run(command, **kwargs):
        observed.append((command, kwargs))
        return SimpleNamespace(returncode=1, stdout="owned.py:1:1: E999 owned lint\n", stderr="")
    monkeypatch.setattr(spider.subprocess, "run", run)
    result = spider.crawl_project(tmp_path, threading.Event(), progress.append)
    assert len(progress) == 1 and "owned.py" in result.details and "E999" in result.details
    assert "static issues" in result.summary
    if sys.platform == "win32":
        assert observed[0][1]["creationflags"] & subprocess.CREATE_NO_WINDOW
    assert observed[0][1]["encoding"] == "utf-8" and observed[0][1]["errors"] == "replace"


def test_source_lookup_preserves_real_unicode_paths_and_literal_search_terms(tmp_path):
    root = tmp_path / "Қазақша папка"
    package = root / "aetherlab"
    package.mkdir(parents=True)
    target = package / "owned.py"
    target.write_text("message = 'Қазақша физика қатесі'\n", encoding="utf-8")
    sources = spider._find_source(root, {"search_terms": ["Қазақша физика"]})
    assert len(sources) == 1 and sources[0][0].as_posix() == "aetherlab/owned.py"
    assert "Қазақша физика" in sources[0][1]
    assert spider._find_source(root, {"search_terms": ["--files"]}) == []
