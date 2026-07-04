"""Theme-driven QSS stylesheet for AetherLab.

The stylesheet is a ``string.Template`` over the semantic roles of
:class:`aetherlab.ui.theme.Theme` (``$accent``, ``$surface``, ...). Widgets
opt into shared component styles via ``setObjectName`` — the former ~50
inline ``setStyleSheet`` copies of the palette now live here once, which is
what makes live theme switching a single ``setStyleSheet`` on the main
window.
"""AetherLab QSS — generated from the design system tokens.

Source of truth: design/tokens/{colors,spacing,typography}.css and
design/readme.md (Visual foundations). Palette: "engineering blueprint /
dark lab". Fonts per the design's substitution note: Segoe UI (UI) and
Cascadia Code (mono) are the native-Windows targets.
"""

from __future__ import annotations

from string import Template

from aetherlab.ui.theme import Theme

_QSS_TEMPLATE = Template("""
/* ── Main Window Backdrop ── */
QMainWindow, QWidget#MainWindow {
    background-color: $bg;
    color: $text_bright;
    font-family: "$font_ui", "Inter", system-ui, sans-serif;
    font-size: 13px;
}

/* ── Panel / Card Containers ── */
QFrame#CardFrame {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 14px;
}

QFrame#CardFrame:hover {
    border-color: $border_strong;
}

QFrame#SectionFrame {
    background-color: $surface_input;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 10px;
}

/* ── Typography ── */
QLabel#PanelTitle {
    color: $text_bright;
    font-size: 14pt;
    font-weight: 700;
    letter-spacing: 0.3px;
    padding: 8px 0 10px 4px;
}

QLabel#SectionTitle {
    color: $text_muted;
    font-size: 9pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    padding: 6px 0 4px 0;
}

QLabel {
    color: $text_soft;
# ── Color tokens (design/tokens/colors.css) ──
BG_DEEPEST = "#0A0A0F"
BG_PANEL_1 = "#0D0D14"
BG_PANEL_2 = "#13131A"
BG_CANVAS_TOP = "#0F1520"
SURFACE_INPUT = "#0B0B12"
SURFACE_INPUT_FOCUS = "#0E0E17"

BORDER_HAIRLINE = "#1E293B"
BORDER_STRONG = "#334155"

TEXT_HIGH = "#F8FAFC"
TEXT_MID = "#94A3B8"
TEXT_LOW = "#64748B"
TEXT_ON_ACCENT = "#04141A"

CYAN = "#06B6D4"
CYAN_HOVER = "#22D3EE"
CYAN_ACTIVE = "#0891B2"
CYAN_TINT_10 = "rgba(6, 182, 212, 0.10)"
CYAN_TINT_20 = "rgba(6, 182, 212, 0.20)"

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
QToolButton#TitleIconButton:hover {{ background-color: {BG_PANEL_2}; }}

QLabel#MutedLabel {
    color: $text_muted;
    font-size: 11px;
}

QLabel#DimLabel {
    color: $text_dim;
    font-size: 11px;
}

QLabel#EmptyStateLabel {
    color: $text_faint;
    font-size: 12px;
    padding: 24px;
}

QLabel#SourceLabel {
    color: $accent;
    font-size: 11px;
    font-weight: 600;
    font-family: "$font_mono", monospace;
}

QLabel#ExcerptLabel {
    color: $text_soft;
    font-size: 11px;
}

QLabel#StepNumLabel {
    color: $accent;
    font-size: 11px;
    font-weight: 700;
    font-family: "$font_mono", monospace;
}

QLabel#StepBody {
    color: $text;
    font-size: 12px;
    padding: 8px 8px 8px 28px;
    background-color: $surface_input;
    border-radius: 6px;
    margin-top: 4px;
}

/* ── Sidebar Navigation ── */
QWidget#Sidebar {
    background-color: $surface_alt;
    border-right: 1px solid $border;
}

QLabel#SidebarLogo {
    color: $accent;
    font-size: 16pt;
    font-weight: 800;
    letter-spacing: -0.5px;
    padding: 12px 0 16px 0;
}

QFrame#SidebarSep, QFrame#StepConnector {
    background-color: $border;
}
/* ═══════════════ Nav rail ═══════════════ */

QWidget#NavRail {{
    background-color: {BG_PANEL_1};
    border-right: 1px solid {BORDER_HAIRLINE};
}}

QToolButton#NavRailItem {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: $text_muted;
    padding: 12px 16px;
    color: {TEXT_MID};
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.3px;
    padding: 8px 2px;
}}
QToolButton#NavRailItem:hover {{ background-color: {BG_PANEL_2}; }}
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

QPushButton#SidebarItem:hover {
    background-color: $border;
    color: $text_soft;
}

QPushButton#SidebarItem:checked {
    background-color: $accent_soft;
    color: $accent;
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

/* ── Splitter Handle ── */
QSplitter::handle {
    background-color: $border;
}
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

QSplitter::handle:hover {
    background-color: $accent;
}

/* ── Tab Widget ── */
QTabWidget::pane {
    background-color: $bg;
    border: none;
    top: -1px;
}

QTabBar::tab {
    background-color: $surface_alt;
    color: $text_muted;
    border: 1px solid $border;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 20px;
    margin-right: 2px;
    font-weight: 500;
    font-size: 12px;
}

QTabBar::tab:selected {
    background-color: $surface;
    color: $accent;
    border-color: $border;
}

QTabBar::tab:hover:!selected {
    background-color: $surface;
    color: $text_dim;
}

/* ── Text Edits & List Widgets ── */
QPlainTextEdit, QListWidget {
    background-color: $surface_input;
    border: 1px solid $border;
    border-radius: 8px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $text_bright;
    padding: 6px;
    font-family: "$font_mono", "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
}

QPlainTextEdit:hover, QListWidget:hover {
    border-color: $border_strong;
}

QPlainTextEdit:focus, QListWidget:focus {
    border-color: $accent;
}

/* ── Scroll areas are chromeless ── */
QScrollArea {
    border: none;
    background: transparent;
}

/* ── Command Bar Input ── */
QTextEdit {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 14px 16px;
    color: $text_bright;
    font-size: 12pt;
}

QTextEdit:focus {
    border: 1px solid $accent;
    background-color: $bg_deep;
}

QTextEdit:hover {
    border-color: $border_strong;
}

/* ── Single-line command bar ── */
QLineEdit#CommandBar {
    background-color: $surface_alt;
    border: 2px solid $border;
    border-radius: 12px;
    padding: 14px 20px;
    color: $text_bright;
    font-size: 13pt;
    font-weight: 400;
}

QLineEdit#CommandBar:focus {
    border-color: $accent;
    background-color: $bg_deep;
}

QLineEdit#CommandBar:hover {
    border-color: $border_strong;
}

/* ── Themed dialog inputs ── */
QLineEdit#ThemedInput {
    background-color: $surface_input;
    border: 1px solid $border;
    border-radius: 6px;
    color: $text;
    padding: 8px;
    font-family: "$font_mono", monospace;
    font-size: 12px;
}

QLineEdit#ThemedInput:focus {
    border-color: $accent;
}

/* ── Buttons ── */
QPushButton {
    background-color: $accent_deep;
    border: 1px solid $accent;
    border-radius: 8px;
    color: $text_bright;
    padding: 10px 24px;
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 0.3px;
}

QPushButton:hover {
    background-color: $accent;
    border-color: $accent_hover;
}

QPushButton:pressed {
    background-color: $accent_pressed;
    border-color: $accent;
}

QPushButton:disabled {
    background-color: $border;
    border-color: $border;
    color: $text_faint;
}

QPushButton#RunButton {
    background-color: $accent_deep;
    border: 2px solid $accent;
    border-radius: 12px;
    color: $text_bright;
    padding: 14px 32px;
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.5px;
}

QPushButton#RunButton:hover {
    background-color: $accent;
    border-color: $accent_hover;
}

QPushButton#RunButton:pressed {
    background-color: $accent_pressed;
}

QPushButton#RunButton:disabled {
    background-color: $border;
    border-color: $border;
    color: $text_faint;
}

QPushButton#CancelButton {
    background-color: $error_deep;
    border: 1px solid $error;
    border-radius: 12px;
    color: $error_text;
    padding: 14px 20px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton#CancelButton:hover {
    background-color: $error_deep;
    border-color: $error_text;
}

QPushButton#CancelButton:disabled {
    background-color: $surface;
    border-color: $border_strong;
    color: $text_muted;
}

QPushButton#PillTab {
    background-color: transparent;
    border: 1px solid $border_strong;
    border-radius: 16px;
    color: $text_dim;
    padding: 6px 16px;
    font-weight: 500;
    font-size: 12px;
}

QPushButton#PillTab:checked {
    background-color: $accent_soft;
    border-color: $accent;
    color: $accent;
}

QPushButton#PillTab:hover:!checked {
    background-color: $border;
    color: $text_soft;
}

/* Transparent bordered utility buttons (copy/clear/reset/expand). */
QPushButton#GhostButton {
    background: transparent;
    border: 1px solid $border_strong;
    border-radius: 4px;
    color: $text_muted;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#GhostButton:hover {
    border-color: $accent;
    color: $text_soft;
    background: transparent;
}

QPushButton#DialogGhostButton {
    background: transparent;
    border: 1px solid $border_strong;
    border-radius: 8px;
    color: $text_dim;
    padding: 10px 24px;
}

QPushButton#DialogGhostButton:hover {
    border-color: $accent;
    color: $text_soft;
    background: transparent;
}

/* Borderless icon-only buttons (copy/dismiss glyphs). */
QPushButton#MiniIconButton {
    background: transparent;
    border: none;
    font-size: 12px;
    padding: 2px;
    color: $text_muted;
}

QPushButton#MiniIconButton:hover {
    color: $text_soft;
    background: transparent;
}

/* Bordered icon button (parameter reset). */
QPushButton#IconGhostButton {
    background: transparent;
    border: 1px solid $border_strong;
    border-radius: 4px;
    color: $text_muted;
    font-size: 14px;
    padding: 2px;
}

QPushButton#IconGhostButton:hover {
    border-color: $accent;
    color: $text_soft;
    background: transparent;
}

QPushButton#DockToggle {
    background: transparent;
    border: none;
    color: $text_muted;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 4px 0;
}

QPushButton#DockToggle:hover {
    color: $text_soft;
    background: transparent;
}

QPushButton#ErrorGhostButton {
    background: transparent;
    border: 1px solid $error;
    border-radius: 6px;
    color: $error_text;
    font-size: 11px;
    padding: 4px 8px;
}

QPushButton#ErrorGhostButton:hover {
    border-color: $error_text;
    background: transparent;
}

/* ── Combo boxes (examples / quality) ── */
QComboBox#ExamplesCombo, QComboBox#QualityCombo {
    background-color: $surface;
    border: 1px solid $border_strong;
    border-radius: 8px;
    color: $text_dim;
    padding: 8px 12px;
    font-size: 12px;
}

QComboBox#QualityCombo {
    padding: 8px 8px;
    font-weight: 600;
}

QComboBox#ExamplesCombo:hover, QComboBox#QualityCombo:hover {
    border-color: $accent;
    color: $text_soft;
}

QComboBox#ExamplesCombo::drop-down, QComboBox#QualityCombo::drop-down {
    border: none;
}

QComboBox#ExamplesCombo QAbstractItemView, QComboBox#QualityCombo QAbstractItemView {
    background-color: $surface;
    border: 1px solid $border_strong;
    color: $text_soft;
    selection-background-color: $accent_soft;
}

/* ── Spin boxes ── */
QDoubleSpinBox#ThemedSpinBox {
    background-color: $surface_input;
    border: 1px solid $border;
    border-radius: 4px;
    color: $accent;
    padding: 2px 4px;
    font-family: "$font_mono", monospace;
    font-size: 11px;
}

QDoubleSpinBox#ThemedSpinBox:focus {
    border-color: $accent;
}

/* ── Checkboxes (phase toggle) ── */
QCheckBox#PhaseCheck {
    color: $text_dim;
    font-size: 11px;
    font-weight: 600;
    spacing: 6px;
}

QCheckBox#PhaseCheck::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid $border_strong;
    background: $surface;
}

QCheckBox#PhaseCheck::indicator:checked {
    background: $accent;
    border-color: $accent;
}

/* ── Sliders ── */
QSlider::groove:horizontal {
    height: 4px;
    background: $border;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    height: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent_deep, stop:1 $accent);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: $text;
    border: 2px solid $accent;
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: $text_bright;
    border-color: $accent_hover;
    width: 16px;
    margin: -7px 0;
    border-radius: 8px;
}

/* ── Status Bar ── */
QStatusBar {
    background-color: $bg;
    color: $text_muted;
    font-size: 12px;
    border-top: 1px solid $border;
    padding: 4px 12px;
}

QStatusBar QLabel {
    color: $text_muted;
}

/* ── Progress Bar ── */
QProgressBar {
    background-color: $border;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: $text_bright;
    font-size: 11px;
    font-weight: 600;
    height: 6px;
    max-height: 6px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 $accent_deep, stop:0.5 $accent, stop:1 $success);
    border-radius: 4px;
}
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
QMenu::item:selected {{ background-color: {BG_PANEL_1}; }}

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

QScrollBar::handle:vertical {
    background-color: $border_strong;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: $text_faint;
}
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
    height: 8px;
    border-radius: 4px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: $border_strong;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: $text_faint;
}
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: {BG_PANEL_2};
    border-bottom: 1px solid {BORDER_HAIRLINE};
    color: {TEXT_HIGH};
    /* No padding: rows are embedded widgets (History/Library) that manage
       their own margins — QSS item padding offsets and clips them. */
    padding: 0;
}}
QListWidget::item:hover {{ background-color: {BG_PANEL_1}; }}
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

/* ── Form Labels ── */
QFormLayout QLabel {
    color: $text_dim;
    font-size: 12px;
    font-weight: 500;
}

/* ── List Items ── */
QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid $border;
    border-radius: 4px;
    margin: 2px 0;
}

QListWidget::item:hover {
    background-color: $border;
}

QListWidget::item:selected {
    background-color: $accent_soft;
    color: $accent;
}

/* ── Pipeline Stepper ── */
QWidget#PipelineStepper {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: 10px;
}

QLabel#StepActive {
    color: $accent;
    font-weight: 700;
}

QLabel#StepComplete {
    color: $success;
    font-weight: 600;
}

QLabel#StepPending {
    color: $text_faint;
    font-weight: 500;
}

QLabel#StepError {
    color: $error;
    font-weight: 600;
}

/* ── Loading Overlay ── */
QWidget#BlueprintOverlay {
    background-color: $bg;
    border: 1px solid $border;
    border-radius: 10px;
}

/* ── Simulation top bar & error banner ── */
QWidget#SimTopBar {
    background-color: $surface_alt;
    border-bottom: 1px solid $border;
}

QFrame#ErrorBanner {
    background-color: $error_bg;
    border-bottom: 2px solid $error;
    padding: 0;
}

QLabel#ErrorIcon {
    font-size: 14px;
    color: $error;
}

QLabel#ErrorText {
    color: $error_text;
    font-size: 12px;
}

/* ── Status Labels ── */
QLabel#StatusIdle {
    color: $text_muted;
    font-size: 12px;
}

QLabel#StatusWorking {
    color: $accent;
    font-size: 12px;
}

QLabel#StatusReady {
    color: $success;
    font-size: 12px;
}

QLabel#StatusError {
    color: $error;
    font-size: 12px;
}

/* ── Video Player Controls ── */
QPushButton#VideoControlBtn {
    background-color: $surface;
    border: 1px solid $border_strong;
    border-radius: 6px;
    color: $text;
    padding: 6px;
    font-size: 14px;
}

QPushButton#VideoControlBtn:hover {
    background-color: $border;
    border-color: $accent;
}

QPushButton#VideoControlBtn:pressed {
    background-color: $accent_deep;
}

QLabel#VideoTimeLabel {
    color: $text_muted;
    font-family: "$font_mono", "Consolas", monospace;
    font-size: 11px;
}

QVideoWidget#VideoSurface {
    background-color: $bg;
    border-radius: 8px;
}

/* ── Menu Bar ── */
QMenuBar {
    background-color: $bg;
    color: $text_dim;
    border-bottom: 1px solid $border;
}

QMenuBar::item:selected {
    background-color: $border;
    color: $accent;
}

QMenu {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: $border;
    color: $accent;
}

QMenu::separator {
    height: 1px;
    background: $border;
    margin: 4px 8px;
}
""")


def build_qss(theme: Theme) -> str:
    """Render the stylesheet for a theme. Raises KeyError on a missing role,
    so a template/Theme drift is caught by tests, not silently shipped."""
    return _QSS_TEMPLATE.substitute(theme.qss_vars())


# Default-theme stylesheet, kept for backward compatibility with existing
# imports (main_window applies a themed build at runtime).
AETHERLAB_QSS = build_qss(Theme())
QPushButton#VideoControlBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px;
}}
QPushButton#VideoControlBtn:hover {{ background-color: {BG_PANEL_1}; }}

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
"""
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
