"""Theme-driven QSS stylesheet for AetherLab.

The stylesheet is a ``string.Template`` over the semantic roles of
:class:`aetherlab.ui.theme.Theme` (``$accent``, ``$surface``, ...). Widgets
opt into shared component styles via ``setObjectName`` — the former ~50
inline ``setStyleSheet`` copies of the palette now live here once, which is
what makes live theme switching a single ``setStyleSheet`` on the main
window.
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
    font-size: 13px;
}

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

QPushButton#SidebarItem {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: $text_muted;
    padding: 12px 16px;
    font-weight: 500;
    font-size: 13px;
    text-align: left;
}

QPushButton#SidebarItem:hover {
    background-color: $border;
    color: $text_soft;
}

QPushButton#SidebarItem:checked {
    background-color: $accent_soft;
    color: $accent;
    font-weight: 600;
}

/* ── Splitter Handle ── */
QSplitter::handle {
    background-color: $border;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

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

/* ── Scroll Bars ── */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: $border_strong;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: $text_faint;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0;
    background: none;
}

QScrollBar:horizontal {
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

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    width: 0;
    background: none;
}

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
