"""WP8: theme roles, presets, persistence, and QSS templating."""

from __future__ import annotations

import re

import pytest

from aetherlab.ui.style import build_qss
from aetherlab.ui.theme import (
    COLOR_ROLES,
    DEFAULT_PRESET,
    PRESET_NAMES,
    Theme,
    get_preset,
    load_theme,
    save_theme,
)

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_default_theme_is_all_valid_hex():
    theme = Theme()
    for role in COLOR_ROLES:
        assert _HEX.match(getattr(theme, role)), f"{role}={getattr(theme, role)!r}"


def test_default_preset_matches_legacy_accent():
    # Guards the "exact current look" contract for the default preset.
    assert DEFAULT_PRESET == "Aether Dark"
    assert Theme().accent == "#06B6D4"
    assert Theme().bg == "#0A0A0F"


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_presets_are_complete_and_valid(name):
    theme = get_preset(name)
    assert theme.name == name
    for role in COLOR_ROLES:
        assert _HEX.match(getattr(theme, role)), f"{name}.{role}"


def test_unknown_preset_falls_back_to_default():
    assert get_preset("does-not-exist").accent == Theme().accent


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_build_qss_leaves_no_tokens(name):
    qss = build_qss(get_preset(name))
    assert "$" not in qss, "unsubstituted template token remains"
    assert get_preset(name).accent in qss


def test_build_qss_reflects_custom_accent():
    theme = Theme(accent="#123456")
    assert "#123456" in build_qss(theme)


def test_theme_json_round_trip():
    theme = get_preset("Nebula")
    restored = Theme.from_json(theme.to_json())
    assert restored == theme


def test_from_json_rejects_bad_hex_and_keeps_default():
    theme = Theme.from_json({"accent": "not-a-color", "bg": "#abcdef"})
    assert theme.accent == Theme().accent  # invalid -> default
    assert theme.bg == "#ABCDEF"           # valid -> applied (normalized)


def test_from_json_tolerates_garbage():
    assert Theme.from_json(None) == Theme()
    assert Theme.from_json("nonsense") == Theme()
    assert Theme.from_json([1, 2, 3]) == Theme()


def test_scene_palette_shape():
    pal = get_preset("Emerald").scene_palette()
    assert set(pal) == {"background", "curve", "accent", "text", "secondary"}
    assert all(_HEX.match(v) for v in pal.values())


def test_persistence_round_trip(tmp_path):
    theme = get_preset("Solar Light")
    save_theme(theme, tmp_path)
    assert load_theme(tmp_path).name == "Solar Light"
    assert load_theme(tmp_path).accent == theme.accent


def test_load_theme_missing_dir_is_default(tmp_path):
    assert load_theme(tmp_path / "nope").accent == Theme().accent


def test_load_theme_corrupt_file_is_default(tmp_path):
    (tmp_path / "ui_prefs.json").write_text("{ broken", encoding="utf-8")
    assert load_theme(tmp_path) == Theme()


def test_saved_prefs_expose_scene_palette(tmp_path):
    import json
    save_theme(get_preset("Nebula"), tmp_path)
    payload = json.loads((tmp_path / "ui_prefs.json").read_text(encoding="utf-8"))
    assert payload["scene_palette"]["background"] == get_preset("Nebula").bg
