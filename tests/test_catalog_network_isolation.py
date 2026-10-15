"""Catalog fixtures must not enter provider/preflight paths while stubbing media."""
import ast
from pathlib import Path

from aetherlab.core.settings import AppSettings


def test_candidate_fanout_probe_controls_full_render_boundary(tmp_path, monkeypatch):
    import httpx
    from aetherlab.services.manim_runtime import ManimRuntime
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "test_features.py").read_text(encoding="utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "t_f171")
    owned = AppSettings(data_dir=tmp_path, cache_path=tmp_path / "cache.sqlite3", chroma_path=tmp_path / "chroma",
        library_path=tmp_path / "library", openai_api_key=None, openai_base_url=None, llm_model="owned")
    scope = {"_settings": lambda: owned, "Path": Path}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "test_features.py", "exec"), scope)
    calls = []
    async def forbidden_preflight(self, bundle, *args, **kwargs):
        calls.append("preflight")
        return bundle
    def forbidden_send(*args, **kwargs):
        calls.append("network")
        raise AssertionError("Catalog probe attempted external traffic")
    async def forbidden_async_send(*args, **kwargs):
        return forbidden_send(*args, **kwargs)
    monkeypatch.setattr(ManimRuntime, "_preflight_and_repair", forbidden_preflight)
    monkeypatch.setattr(httpx.Client, "send", forbidden_send)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden_async_send)
    monkeypatch.chdir(root)
    note = scope["t_f171"]()
    assert "fan-out" in note
    assert calls == [], f"Controlled media probe entered uncontrolled work: {calls}"
