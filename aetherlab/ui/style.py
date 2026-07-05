"""AetherLab QSS — generated from the design system tokens.

Source of truth: design/tokens/{colors,spacing,typography}.css and
design/readme.md (Visual foundations). Palette: "engineering blueprint /
dark lab". Fonts per the design's substitution note: Segoe UI (UI) and
Cascadia Code (mono) are the native-Windows targets.
"""

from __future__ import annotations

# ── Color tokens (design/tokens/colors.css) ──
BG_DEEPEST = "#0A0A0F"
BG_PANEL_1 = "#0D0D14"
BG_PANEL_2 = "#13131A"
BG_CANVAS_TOP = "#0F1520"
STAGE = "#000000"        # v2: true-black screening-room letterbox
ELEV = "#181822"         # v2: elevated controls / segmented fills
HOVER_SURFACE = "#1C1C27"  # v2: hover surface
LINE_0 = "#141A24"       # v2: faintest divider
SURFACE_INPUT = "#0B0B12"
SURFACE_INPUT_FOCUS = "#0E0E17"

BORDER_HAIRLINE = "#1E293B"
BORDER_STRONG = "#334155"

TEXT_HIGH = "#F8FAFC"
TEXT_MID = "#94A3B8"
TEXT_LOW = "#64748B"
TEXT_ON_ACCENT = "#04141A"

CYAN = "#22D3EE"          # v2 primary (v1 #06B6D4 kept as CYAN_DEEP)
CYAN_DEEP = "#06B6D4"     # fills, spines, pressed states
CYAN_HOVER = "#67E8F9"
CYAN_ACTIVE = "#06B6D4"
CYAN_TINT_10 = "rgba(34, 211, 238, 0.10)"
CYAN_TINT_20 = "rgba(34, 211, 238, 0.20)"

EMERALD = "#10B981"
EMERALD_TINT_10 = "rgba(16, 185, 129, 0.10)"
VIOLET = "#8B5CF6"
VIOLET_TINT_10 = "rgba(139, 92, 246, 0.10)"
AMBER = "#F59E0B"
AMBER_TINT_10 = "rgba(245, 158, 11, 0.10)"
ROSE = "#F43F5E"
ROSE_HOVER = "#FB7185"
ROSE_TINT_10 = "rgba(244, 63, 94, 0.10)"

FONT_UI = "'Segoe UI', 'Inter', sans-serif"
FONT_MONO = "'Cascadia Code', 'Consolas', monospace"


AETHERLAB_QSS = f"""
/* ═══════════════ Base ═══════════════ */

QMainWindow#MainWindow, QWidget#Root {{
    background-color: {BG_DEEPEST};
}}

QWidget {{
    font-family: {FONT_UI};
    font-size: 13px;
    color: {TEXT_MID};
}}

QToolTip {{
    background-color: {BG_PANEL_2};
    color: {TEXT_HIGH};
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 11px;
}}

QStatusBar {{
    background-color: {BG_PANEL_1};
    color: {TEXT_LOW};
    border-top: 1px solid {BORDER_HAIRLINE};
    font-size: 11px;
    font-family: {FONT_MONO};
}}

/* ═══════════════ Title bar ═══════════════ */

QWidget#TitleBar {{
    background-color: {BG_DEEPEST};
    border-bottom: 1px solid {BORDER_HAIRLINE};
}}

QLabel#TitleWordmark {{
    color: {TEXT_HIGH};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}

QToolButton#TitleIconButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px;
}}
QToolButton#TitleIconButton:hover {{ background-color: {HOVER_SURFACE}; }}

/* ═══════════════ Nav rail ═══════════════ */

QWidget#NavRail {{
    background-color: {BG_PANEL_1};
    border-right: 1px solid {BORDER_HAIRLINE};
}}

QToolButton#NavRailItem {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: {TEXT_MID};
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.3px;
    padding: 8px 2px;
}}
QToolButton#NavRailItem:hover {{ background-color: {HOVER_SURFACE}; }}
QToolButton#NavRailItem:checked {{
    background-color: {CYAN_TINT_10};
    color: {CYAN};
}}
QToolButton#NavRailItem:disabled {{ color: #3D4B5F; }}

/* ═══════════════ Workspace panels & cards ═══════════════ */

QFrame#CardFrame {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 12px;
}}

QFrame#CanvasFrame {{
    background-color: {BG_CANVAS_TOP};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 12px;
}}

QLabel#PanelTitle {{
    color: {TEXT_HIGH};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#SectionTitle {{
    color: {TEXT_MID};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.1px;
}}

QLabel#SettingsSection {{
    color: {CYAN};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.6px;
}}

QLabel#EquationBanner {{
    background-color: {BG_CANVAS_TOP};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 8px;
    color: {CYAN};
    font-family: {FONT_MONO};
    font-size: 17px;
    font-style: italic;
    padding: 16px 20px;
}}

QLabel#KeywordChip {{
    color: {VIOLET};
    background-color: {VIOLET_TINT_10};
    border: 1px solid {VIOLET};
    border-radius: 9px;
    font-size: 11px;
    padding: 2px 9px;
}}

QLabel#EmptyHint {{
    color: #475569;
    font-size: 12px;
    padding: 24px;
}}

/* ═══════════════ Buttons ═══════════════ */

QPushButton {{
    font-weight: 600;
    border-radius: 8px;
}}

QPushButton#PrimaryButton {{
    background-color: {CYAN};
    color: {TEXT_ON_ACCENT};
    border: 1px solid {CYAN};
    padding: 9px 16px;
    font-size: 13px;
}}
QPushButton#PrimaryButton:hover {{ background-color: {CYAN_HOVER}; }}
QPushButton#PrimaryButton:pressed {{ background-color: {CYAN_ACTIVE}; }}
QPushButton#PrimaryButton:disabled {{
    background-color: {BG_PANEL_2};
    color: {TEXT_LOW};
    border-color: {BORDER_HAIRLINE};
}}

QPushButton#DangerButton {{
    background: transparent;
    color: {ROSE};
    border: 1px solid {ROSE};
    padding: 9px 16px;
    font-size: 13px;
}}
QPushButton#DangerButton:hover {{ background-color: {ROSE_TINT_10}; }}

QPushButton#SecondaryButton {{
    background-color: {BG_PANEL_2};
    color: {TEXT_HIGH};
    border: 1px solid {BORDER_STRONG};
    padding: 8px 14px;
    font-size: 12.5px;
}}
QPushButton#SecondaryButton:hover {{ border-color: {CYAN}; }}

QPushButton#GhostButton {{
    background: transparent;
    color: {TEXT_MID};
    border: none;
    padding: 7px 12px;
    font-size: 12.5px;
}}
QPushButton#GhostButton:hover {{ color: {TEXT_HIGH}; }}

QPushButton#LinkButton {{
    background: transparent;
    color: {CYAN};
    border: none;
    font-size: 12.5px;
    font-weight: 500;
    padding: 2px 0;
    text-align: left;
}}
QPushButton#LinkButton:hover {{ color: {CYAN_HOVER}; }}

QPushButton#ExampleChip {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 12px;
    color: {TEXT_HIGH};
    font-size: 12.5px;
    font-weight: 400;
    padding: 10px 16px;
}}
QPushButton#ExampleChip:hover {{ border-color: {CYAN}; }}

/* Run / Cancel in the command bar */
QPushButton#RunButton {{
    background-color: {CYAN};
    color: {TEXT_ON_ACCENT};
    border: 1px solid {CYAN};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
}}
QPushButton#RunButton:hover {{ background-color: {CYAN_HOVER}; }}
QPushButton#RunButton:pressed {{ background-color: {CYAN_ACTIVE}; }}
QPushButton#RunButton:disabled {{
    background-color: {BG_PANEL_2};
    color: {TEXT_LOW};
    border-color: {BORDER_HAIRLINE};
}}

QPushButton#CancelButton {{
    background: transparent;
    color: {ROSE};
    border: 1px solid {ROSE};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
}}
QPushButton#CancelButton:hover {{ background-color: {ROSE_TINT_10}; border-color: {ROSE_HOVER}; }}

/* ═══════════════ Command bar ═══════════════ */

QWidget#CommandBarDock {{
    background-color: {BG_PANEL_1};
    border-top: 1px solid {BORDER_HAIRLINE};
}}

QFrame#CommandBarShell {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 12px;
}}

QLineEdit#CommandInput {{
    background: transparent;
    border: none;
    color: {TEXT_HIGH};
    font-size: 15px;
    padding: 6px 4px;
    selection-background-color: {CYAN_TINT_20};
}}

QPushButton#ExamplesButton {{
    background: transparent;
    border: none;
    color: {TEXT_MID};
    font-size: 12.5px;
    font-weight: 500;
    padding: 6px 8px;
}}
QPushButton#ExamplesButton:hover {{ color: {TEXT_HIGH}; }}

QFrame#VDivider {{ background-color: {BORDER_HAIRLINE}; }}

/* ═══════════════ Combo boxes ═══════════════ */

QComboBox {{
    background-color: {BG_PANEL_1};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 8px;
    color: {TEXT_MID};
    padding: 7px 10px;
    font-size: 12.5px;
}}
QComboBox:hover {{ border-color: {CYAN}; color: {TEXT_HIGH}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    color: {TEXT_HIGH};
    selection-background-color: {CYAN_TINT_20};
    outline: none;
    padding: 4px;
}}

/* ═══════════════ Menus (examples popup) ═══════════════ */

QMenu {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    color: {TEXT_HIGH};
    font-size: 12.5px;
    padding: 8px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{ background-color: {HOVER_SURFACE}; }}

/* ═══════════════ Inputs ═══════════════ */

QLineEdit {{
    background-color: {SURFACE_INPUT};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 8px;
    color: {TEXT_HIGH};
    padding: 8px 10px;
    font-size: 12.5px;
    selection-background-color: {CYAN_TINT_20};
}}
QLineEdit:focus {{ border-color: {CYAN}; background-color: {SURFACE_INPUT_FOCUS}; }}

QLineEdit#MonoField {{ font-family: {FONT_MONO}; font-size: 12px; }}

QPlainTextEdit, QTextEdit {{
    background-color: {SURFACE_INPUT};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 8px;
    color: {TEXT_HIGH};
    font-family: {FONT_MONO};
    font-size: 12px;
    padding: 6px;
    selection-background-color: {CYAN_TINT_20};
}}

QDoubleSpinBox {{
    background-color: {SURFACE_INPUT};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 4px;
    color: {TEXT_HIGH};
    font-family: {FONT_MONO};
    font-size: 11.5px;
    padding: 3px 6px;
}}
QDoubleSpinBox:focus {{ border-color: {CYAN}; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; }}

QCheckBox {{
    color: {TEXT_MID};
    font-size: 12px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border-radius: 3px;
    border: 1px solid {BORDER_STRONG};
    background: {BG_PANEL_2};
}}
QCheckBox::indicator:checked {{ background: {CYAN}; border-color: {CYAN}; }}

/* ═══════════════ Sliders ═══════════════ */

QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER_HAIRLINE};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {CYAN};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: {TEXT_HIGH};
    border: 2px solid {CYAN};
}}
QSlider::handle:horizontal:hover {{ background: {CYAN_HOVER}; }}

/* ═══════════════ Lists ═══════════════ */

QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: {BG_PANEL_2};
    border-bottom: 1px solid {LINE_0};
    color: {TEXT_HIGH};
    /* No padding: rows are embedded widgets (History/Library) that manage
       their own margins — QSS item padding offsets and clips them. */
    padding: 0;
}}
QListWidget::item:hover {{ background-color: {HOVER_SURFACE}; }}
QListWidget::item:selected {{
    background-color: {CYAN_TINT_10};
    color: {CYAN};
}}

QFrame#ListShell {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 12px;
}}

/* ═══════════════ Pill tabs ═══════════════ */

QPushButton#PillTab {{
    background: transparent;
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 14px;
    color: {TEXT_MID};
    font-size: 12.5px;
    font-weight: 600;
    padding: 6px 16px;
}}
QPushButton#PillTab:hover {{ border-color: {BORDER_STRONG}; color: {TEXT_HIGH}; }}
QPushButton#PillTab:checked {{
    background-color: {CYAN_TINT_10};
    border-color: {CYAN};
    color: {CYAN};
}}

/* ═══════════════ Status labels ═══════════════ */

QLabel#StatusIdle {{ color: {TEXT_LOW}; }}
QLabel#StatusWorking {{ color: {CYAN}; }}
QLabel#StatusReady {{ color: {EMERALD}; }}
QLabel#StatusError {{ color: {ROSE}; }}

/* ═══════════════ Video controls ═══════════════ */

QFrame#VideoControlsBar {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 12px;
}}

QPushButton#VideoControlBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px;
}}
QPushButton#VideoControlBtn:hover {{ background-color: {ELEV}; }}

QPushButton#VideoPlayBtn {{
    background-color: {CYAN};
    border: none;
    border-radius: 16px;
    padding: 0;
}}
QPushButton#VideoPlayBtn:hover {{ background-color: {CYAN_HOVER}; }}

QLabel#VideoTimeLabel {{
    color: {TEXT_LOW};
    font-family: {FONT_MONO};
    font-size: 11px;
}}

/* ═══════════════ Scrollbars ═══════════════ */

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_LOW}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ═══════════════ Dialogs ═══════════════ */

QDialog {{
    background-color: {BG_PANEL_2};
}}

/* ═══════════════ Splitters ═══════════════ */

QSplitter::handle {{ background-color: {BORDER_HAIRLINE}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ═══════════════ Focus rings (v2 §9: keyboard-first) ═══════════════ */
/* A visible 1.5px cyan outline on every focusable control. */
QComboBox:focus {{ border: 1.5px solid {CYAN}; }}
QCheckBox:focus {{ outline: none; }}
QCheckBox:focus::indicator {{ border: 1.5px solid {CYAN}; }}
QPushButton#SecondaryButton:focus,
QPushButton#GhostButton:focus,
QPushButton#RunButton:focus,
QPushButton#PrimaryButton:focus,
QPushButton#CancelButton:focus {{ border: 1.5px solid {CYAN_HOVER}; }}
QToolButton#NavRailItem:focus {{ background-color: {CYAN_TINT_10}; }}
QSlider:focus {{ background: transparent; }}
QSlider:focus::handle:horizontal {{ border: 2px solid {CYAN_HOVER}; }}

/* ═══════════════ Command-bar focus filament ═══════════════ */
/* The shell lifts to a cyan hairline while the prompt is focused. */
QFrame#CommandBarShell[focused="true"] {{
    border: 1px solid {CYAN};
    background-color: {ELEV};
}}
"""
