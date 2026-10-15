from pathlib import Path

import pytest

from aetherlab.core import settings


@pytest.mark.parametrize("value", (" ", "relative-folder"))
def test_invalid_localappdata_uses_stable_home_instead_of_working_directory(value, tmp_path, monkeypatch):
    home = tmp_path / "owned-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("LOCALAPPDATA", value)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    first_data, first_chroma = settings._default_data_dir(), settings._default_chroma_path()
    monkeypatch.chdir(second)
    assert first_data == settings._default_data_dir() == home / ".aetherlab"
    assert first_chroma == settings._default_chroma_path() == home / ".aetherlab/chroma"
