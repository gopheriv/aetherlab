"""Modern dark-mode QSS stylesheet for AetherLab."""

from __future__ import annotations

AETHERLAB_QSS = """
/* ── Main Window Backdrop ── */
QMainWindow, QWidget#MainWindow {
    background-color: #0A0A0F;
    color: #F1F5F9;
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
}

/* ── Panel / Card Containers ── */
QFrame#CardFrame {
    background-color: #13131A;
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 14px;
}

QFrame#CardFrame:hover {
    border-color: #334155;
}

QFrame#SectionFrame {
    background-color: #0F0F17;
    border: 1px solid #1E293B;
    border-radius: 8px;
    padding: 10px;
}

/* ── Typography ── */
QLabel#PanelTitle {
    color: #F8FAFC;
    font-size: 14pt;
    font-weight: 700;
    letter-spacing: 0.3px;
    padding: 8px 0 10px 4px;
}

QLabel#SectionTitle {
    color: #64748B;
    font-size: 9pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    padding: 6px 0 4px 0;
}

QLabel {
    color: #CBD5E1;
    font-size: 13px;
}

/* ── Sidebar Navigation ── */
QWidget#Sidebar {
    background-color: #0D0D14;
    border-right: 1px solid #1E293B;
}

QPushButton#SidebarItem {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: #64748B;
    padding: 12px 16px;
    font-weight: 500;
    font-size: 13px;
    text-align: left;
}

QPushButton#SidebarItem:hover {
    background-color: #1E293B;
    color: #CBD5E1;
}

QPushButton#SidebarItem:checked {
    background-color: #164E63;
    color: #06B6D4;
    font-weight: 600;
}

/* ── Splitter Handle ── */
QSplitter::handle {
    background-color: #1E293B;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #06B6D4;
}

/* ── Tab Widget ── */
QTabWidget::pane {
    background-color: #0A0A0F;
    border: none;
    top: -1px;
}

QTabBar::tab {
    background-color: #0D0D14;
    color: #64748B;
    border: 1px solid #1E293B;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 20px;
    margin-right: 2px;
    font-weight: 500;
    font-size: 12px;
}

QTabBar::tab:selected {
    background-color: #13131A;
    color: #06B6D4;
    border-color: #1E293B;
}

QTabBar::tab:hover:!selected {
    background-color: #1A1A24;
    color: #94A3B8;
}

/* ── Text Edits & List Widgets ── */
QPlainTextEdit, QListWidget {
    background-color: #0F0F17;
    border: 1px solid #1E293B;
    border-radius: 8px;
    color: #E2E8F0;
    selection-background-color: #06B6D4;
    selection-color: #FFFFFF;
    padding: 6px;
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
}

QPlainTextEdit:hover, QListWidget:hover {
    border-color: #334155;
}

QPlainTextEdit:focus, QListWidget:focus {
    border-color: #06B6D4;
}

/* ── Command Bar Input ── */
QTextEdit {
    background-color: #0D0D14;
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 14px 16px;
    color: #F8FAFC;
    font-size: 12pt;
}

QTextEdit:focus {
    border: 1px solid #06B6D4;
    background-color: #0F1520;
}

QTextEdit:hover {
    border-color: #334155;
}

QTextEdit#CommandInput {
    background-color: #0D0D14;
    border: 2px solid #1E293B;
    border-radius: 12px;
    padding: 16px 20px;
    color: #F8FAFC;
    font-size: 12pt;
    line-height: 1.5;
}

QTextEdit#CommandInput:focus {
    border-color: #06B6D4;
    background-color: #0F1520;
}

QTextEdit#CommandInput:hover {
    border-color: #334155;
}

/* ── Single-line command bar ── */
QLineEdit#CommandBar {
    background-color: #0D0D14;
    border: 2px solid #1E293B;
    border-radius: 12px;
    padding: 14px 20px;
    color: #F8FAFC;
    font-size: 13pt;
    font-weight: 400;
}

QLineEdit#CommandBar:focus {
    border-color: #06B6D4;
    background-color: #0F1520;
}

QLineEdit#CommandBar:hover {
    border-color: #334155;
}

/* ── Buttons ── */
QPushButton {
    background-color: #0E7490;
    border: 1px solid #06B6D4;
    border-radius: 8px;
    color: #FFFFFF;
    padding: 10px 24px;
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 0.3px;
}

QPushButton:hover {
    background-color: #06B6D4;
    border-color: #22D3EE;
}

QPushButton:pressed {
    background-color: #0891B2;
    border-color: #06B6D4;
}

QPushButton:disabled {
    background-color: #1E293B;
    border-color: #1E293B;
    color: #475569;
}

QPushButton#RunButton {
    background-color: #0E7490;
    border: 2px solid #06B6D4;
    border-radius: 12px;
    color: #FFFFFF;
    padding: 14px 32px;
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.5px;
}

QPushButton#RunButton:hover {
    background-color: #06B6D4;
    border-color: #22D3EE;
}

QPushButton#RunButton:pressed {
    background-color: #0891B2;
}

QPushButton#RunButton:disabled {
    background-color: #1E293B;
    border-color: #1E293B;
    color: #475569;
}

QPushButton#PillTab {
    background-color: transparent;
    border: 1px solid #334155;
    border-radius: 16px;
    color: #94A3B8;
    padding: 6px 16px;
    font-weight: 500;
    font-size: 12px;
}

QPushButton#PillTab:checked {
    background-color: #164E63;
    border-color: #06B6D4;
    color: #06B6D4;
}

QPushButton#PillTab:hover:!checked {
    background-color: #1E293B;
    color: #CBD5E1;
}

/* ── Sliders ── */
QSlider::groove:horizontal {
    height: 4px;
    background: #1E293B;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    height: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0E7490, stop:1 #06B6D4);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #E2E8F0;
    border: 2px solid #06B6D4;
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #FFFFFF;
    border-color: #22D3EE;
    width: 16px;
    margin: -7px 0;
    border-radius: 8px;
}

/* ── Status Bar ── */
QStatusBar {
    background-color: #0A0A0F;
    color: #64748B;
    font-size: 12px;
    border-top: 1px solid #1E293B;
    padding: 4px 12px;
}

QStatusBar QLabel {
    color: #64748B;
}

/* ── Progress Bar ── */
QProgressBar {
    background-color: #1E293B;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #FFFFFF;
    font-size: 11px;
    font-weight: 600;
    height: 6px;
    max-height: 6px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0E7490, stop:0.5 #06B6D4, stop:1 #10B981);
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
    background-color: #334155;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #475569;
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
    background-color: #334155;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #475569;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    width: 0;
    background: none;
}

/* ── Form Labels ── */
QFormLayout QLabel {
    color: #94A3B8;
    font-size: 12px;
    font-weight: 500;
}

/* ── List Items ── */
QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #1E293B;
    border-radius: 4px;
    margin: 2px 0;
}

QListWidget::item:hover {
    background-color: #1E293B;
}

QListWidget::item:selected {
    background-color: #164E63;
    color: #06B6D4;
}

/* ── Pipeline Stepper ── */
QWidget#PipelineStepper {
    background-color: #0D0D14;
    border: 1px solid #1E293B;
    border-radius: 10px;
}

QLabel#StepActive {
    color: #06B6D4;
    font-weight: 700;
}

QLabel#StepComplete {
    color: #10B981;
    font-weight: 600;
}

QLabel#StepPending {
    color: #475569;
    font-weight: 500;
}

QLabel#StepError {
    color: #F43F5E;
    font-weight: 600;
}

/* ── Loading Overlay ── */
QWidget#BlueprintOverlay {
    background-color: #0A0A0F;
    border: 1px solid #1E293B;
    border-radius: 10px;
}

/* ── Status Labels ── */
QLabel#StatusIdle {
    color: #64748B;
}

QLabel#StatusWorking {
    color: #06B6D4;
}

QLabel#StatusReady {
    color: #10B981;
}

QLabel#StatusError {
    color: #F43F5E;
}

/* ── Video Player Controls ── */
QPushButton#VideoControlBtn {
    background-color: #13131A;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #E2E8F0;
    padding: 6px;
    font-size: 14px;
}

QPushButton#VideoControlBtn:hover {
    background-color: #1E293B;
    border-color: #06B6D4;
}

QPushButton#VideoControlBtn:pressed {
    background-color: #0E7490;
}

QLabel#VideoTimeLabel {
    color: #64748B;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
}

/* ── Menu Bar ── */
QMenuBar {
    background-color: #0A0A0F;
    color: #94A3B8;
    border-bottom: 1px solid #1E293B;
}

QMenuBar::item:selected {
    background-color: #1E293B;
    color: #06B6D4;
}

QMenu {
    background-color: #13131A;
    border: 1px solid #1E293B;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #1E293B;
    color: #06B6D4;
}

QMenu::separator {
    height: 1px;
    background: #1E293B;
    margin: 4px 8px;
}
"""
