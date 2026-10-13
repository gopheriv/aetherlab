"""PhysLab QSS — shared UNT student palette and component styles.

Source of truth: design/tokens/{colors,spacing,typography}.css and
design/readme.md. Palette: cool white, muted steel blue, mint, and apricot. Fonts:
Segoe UI (UI) and Cascadia Code (mono) on Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

from aetherlab.ui.theme import Theme

_UI_ASSETS = Path(__file__).resolve().parents[2] / "assets" / "ui"
_CHEVRON = (_UI_ASSETS / "chevron-down.svg").as_posix()
_CHECK = (_UI_ASSETS / "check.svg").as_posix()

# ── Color tokens (design/tokens/colors.css) ──
_STUDY = Theme()
BG_DEEPEST = _STUDY.bg
BG_PANEL_1 = _STUDY.surface
BG_PANEL_2 = _STUDY.surface_alt
BG_CANVAS_TOP = _STUDY.bg_deep
STAGE = _STUDY.bg
ELEV = _STUDY.bg_deep
HOVER_SURFACE = _STUDY.accent_soft
LINE_0 = _STUDY.border
SURFACE_INPUT = _STUDY.surface_input
SURFACE_INPUT_FOCUS = _STUDY.accent_soft

BORDER_HAIRLINE = _STUDY.border
BORDER_STRONG = _STUDY.border_strong

TEXT_HIGH = _STUDY.text_bright
TEXT_MID = _STUDY.text_soft
TEXT_LOW = _STUDY.text_dim
TEXT_ON_ACCENT = "#FFFFFF"

CYAN = _STUDY.accent
CYAN_DEEP = _STUDY.accent_deep
CYAN_HOVER = _STUDY.accent_hover
CYAN_ACTIVE = _STUDY.accent_pressed
CYAN_TINT_10 = "rgba(72, 106, 145, 0.12)"
CYAN_TINT_20 = "rgba(72, 106, 145, 0.20)"

EMERALD = _STUDY.success
EMERALD_TINT_10 = "rgba(38, 114, 92, 0.12)"
VIOLET = _STUDY.curve3
VIOLET_TINT_10 = "rgba(83, 111, 144, 0.12)"
AMBER = _STUDY.warning
AMBER_TINT_10 = "rgba(138, 90, 36, 0.12)"
ROSE = _STUDY.error
ROSE_HOVER = _STUDY.error_deep
ROSE_TINT_10 = "rgba(172, 64, 85, 0.12)"

FONT_UI = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
FONT_MONO = "Cascadia Code" if sys.platform == "win32" else "DejaVu Sans"


AETHERLAB_QSS = f"""
/* ═══════════════ Base ═══════════════ */

QMainWindow#MainWindow, QWidget#Root {{
    background-color: {BG_DEEPEST};
}}

QWidget {{
    font-family: {FONT_UI};
    font-size: 13px;
    color: {TEXT_HIGH};
}}

QToolTip {{
    background-color: {BG_PANEL_2};
    color: {TEXT_HIGH};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 7px 10px;
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
    background-color: {BG_PANEL_1};
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
    border-radius: 9px;
    padding: 7px;
}}
QToolButton#TitleIconButton:hover {{ background-color: {HOVER_SURFACE}; }}

/* ═══════════════ Student navigation ═══════════════ */

QWidget#NavRail {{
    background-color: {BG_PANEL_1};
    border-right: 1px solid {BORDER_HAIRLINE};
}}

QToolButton#NavRailItem {{
    background: transparent;
    border: none;
    border-radius: 14px;
    color: {TEXT_LOW};
    font-size: 10px;
    font-weight: 600;
    padding: 6px 2px;
    text-align: center;
}}
QToolButton#NavRailItem[expanded="true"] {{ font-size: 13px; text-align:left; padding: 7px 12px; }}
QToolButton#NavRailItem:hover {{ background-color: {HOVER_SURFACE}; color: {CYAN}; }}
QToolButton#NavRailItem:checked {{
    background-color: {HOVER_SURFACE};
    color: {CYAN_DEEP};
}}
QToolButton#NavRailItem:disabled {{ color: {TEXT_LOW}; }}
QToolButton#NavRailItem:focus {{ border: 2px solid #335F92; }}

/* ═══════════════ Workspace panels & cards ═══════════════ */

QFrame#CardFrame {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 16px;
}}

QFrame#CanvasFrame {{
    background-color: {BG_CANVAS_TOP};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 16px;
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
    color: #65758A;
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
    color: {TEXT_MID};
    border: 1px solid {BORDER_STRONG};
    border-radius: 9px;
    padding: 8px 14px;
    font-size: 12.5px;
}}
QPushButton#SecondaryButton:hover {{ background-color: {HOVER_SURFACE}; border-color: {CYAN}; }}

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
    border-radius: 14px;
    color: {TEXT_MID};
    font-size: 12.5px;
    font-weight: 400;
    padding: 17px 14px;
    text-align: left;
}}
QPushButton#ExampleChip:hover {{ background: {HOVER_SURFACE}; border-color: {CYAN}; color: {CYAN_DEEP}; }}
QPushButton#ExampleChip[compact="true"] {{ padding: 9px 12px; }}

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

QSpinBox, QDateEdit {{
    background-color: {SURFACE_INPUT};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 8px;
    color: {TEXT_HIGH};
    padding: 7px 9px;
    font-size: 12.5px;
}}
QSpinBox:focus, QDateEdit:focus {{
    border-color: {CYAN};
    background-color: {SURFACE_INPUT_FOCUS};
}}
QSpinBox::up-button, QSpinBox::down-button, QDateEdit::drop-down {{
    width: 18px;
    border: none;
    background-color: {BG_PANEL_2};
}}

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
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
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
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* ═══════════════ Dialogs ═══════════════ */

QDialog {{
    background-color: {BG_PANEL_2};
}}

/* ═══════════════ Splitters ═══════════════ */

QSplitter::handle {{ background-color: {BORDER_HAIRLINE}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ═══════════════ Focus rings (v2 §9: keyboard-first) ═══════════════ */
/* A visible 1.5px blue focus outline on every focusable control. */
QComboBox:focus {{ border: 1.5px solid {CYAN}; }}
QCheckBox:focus {{ outline: none; }}
QCheckBox::indicator:focus {{ border: 1.5px solid {CYAN}; }}
QPushButton#SecondaryButton:focus,
QPushButton#GhostButton:focus,
QPushButton#RunButton:focus,
QPushButton#PrimaryButton:focus,
QPushButton#CancelButton:focus {{ border: 1.5px solid {CYAN_HOVER}; }}
QToolButton#NavRailItem:focus {{ background-color: {CYAN_TINT_10}; }}
QSlider:focus {{ background: transparent; }}
QSlider:focus::handle:horizontal {{ border: 2px solid {CYAN_HOVER}; }}

/* ═══════════════ Command-bar focus filament ═══════════════ */
/* The shell lifts to a blue hairline while the prompt is focused. */
QFrame#CommandBarShell[focused="true"] {{
    border: 1px solid {CYAN};
    background-color: {ELEV};
}}

/* ═════════════ Shared component refinements ═════════════ */

QFrame#CardFrame,
QFrame#AnalysisCard,
QFrame#CanvasFrame,
QFrame#ListShell,
QFrame#VideoControlsBar {{
    border-radius: 16px;
    background-color: {BG_PANEL_2};
    border: 1px solid {LINE_0};
}}

QFrame#CardFrame:hover,
QFrame#AnalysisCard:hover,
QFrame#ListShell:hover {{
    border-color: {BORDER_HAIRLINE};
}}

QFrame#AnalysisCard {{
    background-color: {BG_PANEL_2};
    border-top: 1px solid {CYAN_TINT_20};
}}

QWidget#SceneToolbar {{
    background-color: {BG_PANEL_1};
    border-bottom: 1px solid {LINE_0};
}}

QWidget#RunningStatusStrip {{
    background-color: {BG_DEEPEST};
    border-top: 1px solid {LINE_0};
}}

QLabel#EmptyStateHeadline {{
    color: {TEXT_HIGH};
    font-size: 27px;
    font-weight: 700;
}}
QLabel#EmptyStateSubtitle {{
    color: {TEXT_MID};
    font-size: 14px;
}}
QFrame#ENTLaunchCard {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_STRONG};
    border-radius: 15px;
}}
QLabel#ENTLaunchMark {{
    background-color: {CYAN_TINT_10};
    border: 1px solid {BORDER_STRONG};
    border-radius: 11px;
}}
QLabel#ENTLaunchTitle {{
    color: {TEXT_HIGH};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#ENTLaunchSubtitle {{
    color: {TEXT_MID};
    font-size: 11px;
}}
QPushButton#ENTPracticeButton {{
    background-color: {CYAN};
    color: {TEXT_ON_ACCENT};
    border: 1px solid {CYAN};
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 700;
}}
QPushButton#ENTPracticeButton:hover {{
    background-color: {CYAN_HOVER};
    border-color: {CYAN_HOVER};
}}
QPushButton#ENTPracticeButton:pressed {{
    background-color: {CYAN_DEEP};
    border-color: {CYAN_DEEP};
}}
QPushButton#ENTPracticeButton:focus {{
    border: 2px solid {CYAN_HOVER};
}}

QFrame#SetupStrip,
QFrame#LibraryEmptyState {{
    background-color: {BG_PANEL_1};
    border: 1px dashed {BORDER_STRONG};
    border-radius: 14px;
}}

QWidget#BlueprintBackdrop {{
    background-color: {BG_DEEPEST};
}}

QLabel#EquationBanner {{
    background-color: {STAGE};
    border: 1px solid {CYAN_TINT_20};
    border-bottom: 2px solid {CYAN_DEEP};
    border-radius: 12px;
    color: {CYAN};
    font-family: {FONT_MONO};
    font-size: 18px;
    padding: 18px 20px;
}}

QLabel#KeywordChip {{
    border-radius: 6px;
    border-color: {VIOLET};
    background-color: {VIOLET_TINT_10};
    padding: 3px 9px;
}}

QPushButton#ExampleChip {{
    border-radius: 8px;
    background-color: {ELEV};
    border: 1px solid {LINE_0};
    padding: 10px 14px;
}}
QPushButton#ExampleChip:hover {{
    border-color: {CYAN};
    background-color: {HOVER_SURFACE};
}}

QPushButton#PillTab {{
    border-radius: 12px;
    background-color: {BG_PANEL_1};
    padding: 7px 14px;
}}
QPushButton#PillTab:checked {{
    background-color: {CYAN_TINT_10};
    border-color: {CYAN};
    color: {CYAN};
}}

QFrame#CommandBarShell {{
    border-radius: 14px;
    background-color: {ELEV};
    border-color: {BORDER_HAIRLINE};
}}

QComboBox#QualityCombo {{
    font-family: {FONT_MONO};
    color: {TEXT_HIGH};
}}

QTabWidget::pane {{
    border: 1px solid {LINE_0};
    border-radius: 8px;
    background-color: {BG_PANEL_2};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {BG_PANEL_1};
    color: {TEXT_MID};
    border: 1px solid {LINE_0};
    border-bottom: none;
    padding: 8px 14px;
    margin-right: 4px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    font-size: 12px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    color: {CYAN};
    background-color: {BG_PANEL_2};
    border-color: {CYAN_TINT_20};
}}
QTabBar::tab:hover {{
    color: {TEXT_HIGH};
    background-color: {HOVER_SURFACE};
}}

QProgressBar {{
    background-color: {LINE_0};
    border: none;
    border-radius: 3px;
    height: 6px;
}}
QProgressBar::chunk {{
    background-color: {CYAN};
    border-radius: 3px;
}}

QRadioButton {{
    color: {TEXT_MID};
    font-size: 12.5px;
    spacing: 8px;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid {BORDER_STRONG};
    background: {BG_PANEL_2};
}}
QRadioButton::indicator:checked {{
    border: 4px solid {CYAN};
    background: {STAGE};
}}

QListWidget#HistoryList::item:selected,
QListWidget::item:selected {{
    border-left: 2px solid {CYAN};
}}

QToolButton#CanvasExportButton {{
    background-color: {BG_PANEL_1};
    border: 1px solid {BORDER_HAIRLINE};
    border-radius: 9px;
}}
QToolButton#CanvasExportButton:hover {{
    border-color: {CYAN};
    background-color: {HOVER_SURFACE};
}}

QFrame#ErrorBanner {{
    background-color: {ROSE_TINT_10};
    border-bottom: 2px solid {ROSE};
}}

/* Study studio shell */
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{_CHEVRON}"); width: 14px; height: 14px; }}
QCheckBox::indicator:checked {{ image: url("{_CHECK}"); }}
QPushButton#SecondaryButton:disabled {{ color: #8292A5; background: #F1EFF5; border-color: #D8E1EC; }}
QDialog#ENTPracticeDialog {{ background: #F4F7FB; }}
QLabel#EmptyStateHeadline {{ color: #18283D; font-size: 30px; font-weight: 700; }}
QLabel#EmptyStateHeadline[compact="true"] {{ font-size: 26px; }}
QLabel#EmptyStateSubtitle {{ color: #65758A; font-size: 14px; }}
QFrame#ENTLaunchCard {{ background: #E9EFF7; border: none; border-radius: 16px; }}
QLabel#ENTLaunchTitle {{ color: #304A69; font-size: 14px; font-weight: 700; }}
QLabel#ENTLaunchSubtitle {{ color: #53647A; font-size: 11px; }}
QLabel#ENTLaunchMark {{ background: #FFFFFF; border: none; border-radius: 12px; }}
QWidget#CommandBarDock {{ background: #F4F7FB; border: none; }}
QFrame#CommandBarShell {{ background: #FFFFFF; border: 1px solid #A5B6CB; border-radius: 18px; }}
QLineEdit#CommandInput {{ background: transparent; border: none; padding: 12px 6px; font-size: 14px; }}
QComboBox {{ background: #EDF2F8; border: 1px solid #D8E1EC; border-radius: 9px; padding: 7px 12px; }}
QLineEdit#TopicSearch {{ background: #FFFFFF; border: 1px solid #D8E1EC; border-radius: 12px;
    padding: 12px 16px; min-height: 20px; }}
QPushButton#PracticeMode {{ background: #FFFFFF; border: 1px solid #D8E1EC; border-radius: 12px;
    color: #53647A; padding: 16px; font-size: 14px; font-weight: 600; }}
QPushButton#PracticeMode:checked {{ background: #E9EFF7; color: #304A69; border: 2px solid #486A91; }}
QPushButton#PracticeMode:hover {{ border-color: #335F92; }}
QPushButton:disabled {{ color: #8292A5; background: #F1EFF5; border-color: #D8E1EC; }}
"""
