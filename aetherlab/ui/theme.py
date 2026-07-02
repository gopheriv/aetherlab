"""Theme system: semantic color roles, presets, and persistence.

Single source of truth for AetherLab's look. Every color the app paints —
QSS-styled widgets, the live canvas painter, the loading overlay, and the
Manim scene templates — resolves through a :class:`Theme` instance, so a
palette change in the Settings dialog restyles everything, including the
rendered videos.

Pure stdlib (dataclasses/json/re/pathlib): importable without Qt, so the
theme logic is unit-testable headless and the services layer can share the
persisted scene palette without importing ``aetherlab.ui``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

log = logging.getLogger(__name__)

PREFS_FILENAME = "ui_prefs.json"

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass
class Theme:
    """Semantic palette. Defaults are the classic "Aether Dark" look —
    every hex here matches the pre-theming hardcoded values exactly."""

    name: str = "Aether Dark"

    # ── surfaces ──
    bg: str = "#0A0A0F"             # window backdrop / canvas gradient edge
    bg_deep: str = "#0F1520"        # canvas gradient center, focused inputs
    surface: str = "#13131A"        # cards, menus
    surface_alt: str = "#0D0D14"    # sidebar, top bars, stepper
    surface_input: str = "#0F0F17"  # text edits, list widgets, spinboxes

    # ── lines ──
    border: str = "#1E293B"
    border_strong: str = "#334155"

    # ── text ramp (bright → faint) ──
    text_bright: str = "#F8FAFC"
    text: str = "#E2E8F0"
    text_soft: str = "#CBD5E1"
    text_dim: str = "#94A3B8"
    text_muted: str = "#64748B"
    text_faint: str = "#475569"

    # ── accent family ──
    accent: str = "#06B6D4"
    accent_hover: str = "#22D3EE"
    accent_deep: str = "#0E7490"
    accent_pressed: str = "#0891B2"
    accent_soft: str = "#164E63"    # checked/selected backgrounds

    # ── semantics ──
    success: str = "#10B981"
    warning: str = "#F59E0B"
    error: str = "#F43F5E"
    error_bg: str = "#1C0A0A"
    error_deep: str = "#7F1D1D"
    error_text: str = "#FDA4AF"

    # ── data-viz curves (canvas + manim) ──
    curve1: str = "#06B6D4"
    curve2: str = "#10B981"
    curve3: str = "#8B5CF6"
    curve4: str = "#F59E0B"

    # ── fonts ──
    font_ui: str = "Segoe UI"
    font_mono: str = "Cascadia Code"

    # ------------------------------------------------------------------
    def qss_vars(self) -> dict[str, str]:
        """All roles as a mapping for string.Template substitution."""
        data = asdict(self)
        data.pop("name")
        return data

    def scene_palette(self) -> dict[str, str]:
        """Colors handed to the Manim scene templates (and the LLM prompt)."""
        return {
            "background": self.bg,
            "curve": self.curve1,
            "accent": self.warning,   # bobs/planets — the old YELLOW slot
            "text": self.text_bright,
            "secondary": self.curve2,
        }

    def to_json(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_json(cls, payload: object) -> "Theme":
        """Tolerant loader: unknown keys ignored, invalid colors replaced by
        the default preset's value — a corrupt prefs file never breaks boot."""
        base = cls()
        if not isinstance(payload, dict):
            return base
        values: dict[str, str] = {}
        for f in fields(cls):
            raw = payload.get(f.name)
            if f.name == "name":
                if isinstance(raw, str) and raw.strip():
                    values[f.name] = raw.strip()[:60]
            elif f.name in FONT_ROLES:
                if isinstance(raw, str) and raw.strip():
                    values[f.name] = raw.strip()[:60]
            elif isinstance(raw, str) and _HEX_RE.match(raw.strip()):
                values[f.name] = raw.strip().upper()
        return replace(base, **values)


COLOR_ROLES: tuple[str, ...] = tuple(
    f.name for f in fields(Theme) if f.name not in ("name", "font_ui", "font_mono")
)
FONT_ROLES: tuple[str, ...] = ("font_ui", "font_mono")

# Human labels for the palette editor, grouped for a scannable grid.
ROLE_LABELS: dict[str, str] = {
    "bg": "Background", "bg_deep": "Background (deep)", "surface": "Surface",
    "surface_alt": "Surface (alt)", "surface_input": "Inputs",
    "border": "Border", "border_strong": "Border (strong)",
    "text_bright": "Text (bright)", "text": "Text", "text_soft": "Text (soft)",
    "text_dim": "Text (dim)", "text_muted": "Text (muted)", "text_faint": "Text (faint)",
    "accent": "Accent", "accent_hover": "Accent (hover)", "accent_deep": "Accent (deep)",
    "accent_pressed": "Accent (pressed)", "accent_soft": "Accent (selected bg)",
    "success": "Success", "warning": "Warning", "error": "Error",
    "error_bg": "Error (background)", "error_deep": "Error (deep)", "error_text": "Error (text)",
    "curve1": "Curve 1", "curve2": "Curve 2", "curve3": "Curve 3", "curve4": "Curve 4",
}


def _nebula() -> Theme:
    return Theme(
        name="Nebula",
        bg="#0B0A12", bg_deep="#151226", surface="#161226", surface_alt="#0F0D1C",
        surface_input="#120F20", border="#2A2440", border_strong="#3F3660",
        accent="#8B5CF6", accent_hover="#A78BFA", accent_deep="#6D28D9",
        accent_pressed="#7C3AED", accent_soft="#3B2A64",
        curve1="#8B5CF6", curve2="#22D3EE", curve3="#F472B6", curve4="#F59E0B",
    )


def _emerald() -> Theme:
    return Theme(
        name="Emerald",
        bg="#0A0F0C", bg_deep="#0F1A14", surface="#101A14", surface_alt="#0C1410",
        surface_input="#0D1711", border="#1E3B2C", border_strong="#2F5544",
        accent="#10B981", accent_hover="#34D399", accent_deep="#047857",
        accent_pressed="#059669", accent_soft="#064E3B",
        success="#38BDF8",
        curve1="#10B981", curve2="#38BDF8", curve3="#A3E635", curve4="#F59E0B",
    )


def _solar_light() -> Theme:
    return Theme(
        name="Solar Light",
        bg="#F8FAFC", bg_deep="#EEF2F7", surface="#FFFFFF", surface_alt="#F1F5F9",
        surface_input="#FFFFFF", border="#CBD5E1", border_strong="#94A3B8",
        text_bright="#0F172A", text="#1E293B", text_soft="#334155",
        text_dim="#475569", text_muted="#64748B", text_faint="#94A3B8",
        accent="#0284C7", accent_hover="#0EA5E9", accent_deep="#075985",
        accent_pressed="#0369A1", accent_soft="#BAE6FD",
        success="#059669", warning="#D97706", error="#E11D48",
        error_bg="#FEE2E2", error_deep="#FCA5A5", error_text="#9F1239",
        curve1="#0284C7", curve2="#059669", curve3="#7C3AED", curve4="#D97706",
    )


_PRESET_FACTORIES = {
    "Aether Dark": Theme,
    "Nebula": _nebula,
    "Emerald": _emerald,
    "Solar Light": _solar_light,
}

PRESET_NAMES: tuple[str, ...] = tuple(_PRESET_FACTORIES)
DEFAULT_PRESET = "Aether Dark"


def get_preset(name: str) -> Theme:
    """Fresh Theme instance for a preset (default preset if unknown)."""
    factory = _PRESET_FACTORIES.get(name, Theme)
    return factory()


# ── current theme (read by painters every frame) ─────────────────────────────

_current: Theme = Theme()


def current_theme() -> Theme:
    return _current


def set_current_theme(theme: Theme) -> None:
    global _current
    _current = theme


# ── persistence ───────────────────────────────────────────────────────────────


def load_theme(data_dir: Path) -> Theme:
    """Load the persisted theme; default preset when absent/corrupt."""
    path = Path(data_dir) / PREFS_FILENAME
    if not path.exists():
        return Theme()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — a broken prefs file must not break boot
        log.debug("ui prefs unreadable, using default theme: %s", exc)
        return Theme()
    return Theme.from_json(payload.get("theme") if isinstance(payload, dict) else None)


def save_theme(theme: Theme, data_dir: Path) -> None:
    """Persist the theme plus the derived scene palette (read by services)."""
    path = Path(data_dir) / PREFS_FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"theme": theme.to_json(), "scene_palette": theme.scene_palette()}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        log.debug("could not persist ui prefs: %s", exc)
