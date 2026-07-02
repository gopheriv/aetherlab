"""Modern dashboard-style PyQt6 desktop window for AetherLab."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aetherlab.core.models import (
    PipelineError,
    PipelineResult,
    ProblemRequest,
    RagResult,
    SceneBundle,
    SolverResult,
)
from aetherlab.core.settings import AppSettings
from aetherlab.services.pdf import (
    compile_latex_to_pdf,
    export_derivation_to_latex,
    export_scene_code,
)
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt
from aetherlab.ui.style import AETHERLAB_QSS, build_qss
from aetherlab.ui.theme import (
    PRESET_NAMES,
    ROLE_LABELS,
    Theme,
    current_theme,
    get_preset,
    load_theme,
    save_theme,
    set_current_theme,
)
from aetherlab.ui.widgets import (
    AnalysisPanel,
    CommandBar,
    HistoryPanel,
    ParameterDock,
    PipelineStepper,
    ReferencePanel,
    SidebarNav,
    SimulationPanel,
)
from aetherlab.ui.workers import PipelineWorker

require_qt()


class _SwatchButton(QtWidgets.QPushButton):
    """A color-role editor: shows the current hex, opens QColorDialog on click."""

    def __init__(self, role: str, value: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.role = role
        self.setFixedHeight(26)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.set_value(value)
        self.clicked.connect(self._pick)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value
        # Readable text on top of the swatch, whatever the color.
        text_color = "#000000" if _is_light(value) else "#FFFFFF"
        self.setText(value)
        self.setStyleSheet(
            f"background-color: {value}; color: {text_color}; border: 1px solid "
            f"{current_theme().border_strong}; border-radius: 4px; "
            "font-family: monospace; font-size: 10px; padding: 2px;"
        )

    def _pick(self) -> None:
        initial = QtGui.QColor(self._value)
        chosen = QtWidgets.QColorDialog.getColor(
            initial, self, f"Choose {ROLE_LABELS.get(self.role, self.role)}"
        )
        if chosen.isValid():
            self.set_value(chosen.name().upper())


class AppearanceEditor(QtWidgets.QWidget):
    """Full palette editor: preset picker, per-role swatches, font pickers."""

    def __init__(self, theme: Theme, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._swatches: dict[str, _SwatchButton] = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Preset row
        preset_row = QtWidgets.QHBoxLayout()
        preset_label = QtWidgets.QLabel("Preset")
        preset_label.setObjectName("SectionTitle")
        preset_row.addWidget(preset_label)
        self._preset_combo = QtWidgets.QComboBox()
        self._preset_combo.setObjectName("QualityCombo")
        self._preset_combo.addItems(PRESET_NAMES)
        self._preset_combo.setCurrentText(theme.name if theme.name in PRESET_NAMES else PRESET_NAMES[0])
        self._preset_combo.activated.connect(self._load_preset)
        preset_row.addWidget(self._preset_combo, 1)
        layout.addLayout(preset_row)

        # Color grid (scrollable — there are ~28 roles)
        grid_host = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        for i, role in enumerate(ROLE_LABELS):
            row, col = divmod(i, 2)
            label = QtWidgets.QLabel(ROLE_LABELS[role])
            label.setObjectName("DimLabel")
            swatch = _SwatchButton(role, getattr(theme, role))
            self._swatches[role] = swatch
            cell = QtWidgets.QHBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.addWidget(label, 1)
            cell.addWidget(swatch)
            wrapper = QtWidgets.QWidget()
            wrapper.setLayout(cell)
            grid.addWidget(wrapper, row, col)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_host)
        scroll.setMinimumHeight(200)
        scroll.setMaximumHeight(240)
        layout.addWidget(scroll)

        # Fonts
        font_row = QtWidgets.QHBoxLayout()
        self._ui_font = QtWidgets.QFontComboBox()
        self._ui_font.setCurrentFont(QtGui.QFont(theme.font_ui))
        self._mono_font = QtWidgets.QFontComboBox()
        self._mono_font.setFontFilters(QtWidgets.QFontComboBox.FontFilter.MonospacedFonts)
        self._mono_font.setCurrentFont(QtGui.QFont(theme.font_mono))
        ui_lbl = QtWidgets.QLabel("UI font")
        ui_lbl.setObjectName("DimLabel")
        mono_lbl = QtWidgets.QLabel("Mono font")
        mono_lbl.setObjectName("DimLabel")
        font_row.addWidget(ui_lbl)
        font_row.addWidget(self._ui_font, 1)
        font_row.addWidget(mono_lbl)
        font_row.addWidget(self._mono_font, 1)
        layout.addLayout(font_row)

    def _load_preset(self) -> None:
        self.set_theme(get_preset(self._preset_combo.currentText()))

    def set_theme(self, theme: Theme) -> None:
        for role, swatch in self._swatches.items():
            swatch.set_value(getattr(theme, role))
        self._ui_font.setCurrentFont(QtGui.QFont(theme.font_ui))
        self._mono_font.setCurrentFont(QtGui.QFont(theme.font_mono))

    def theme(self) -> Theme:
        values = {role: sw.value() for role, sw in self._swatches.items()}
        return Theme(
            name=self._preset_combo.currentText(),
            font_ui=self._ui_font.currentFont().family(),
            font_mono=self._mono_font.currentFont().family(),
            **values,
        )


def _is_light(hex_color: str) -> bool:
    """Perceived-luminance test to pick readable swatch text."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
    except (ValueError, IndexError):
        return False
    return (0.299 * r + 0.587 * g + 0.114 * b) > 150


# ────────────────────────────────────────────────────────────────────────────
# Settings Dialog (#6)
# ────────────────────────────────────────────────────────────────────────────


class SettingsDialog(QtWidgets.QDialog):
    """In-app settings dialog for API key, model, and library path (#6)."""

    def __init__(self, settings: AppSettings, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AetherLab Settings")
        self.setMinimumWidth(480)
        self.setStyleSheet(AETHERLAB_QSS)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("\u2699\ufe0f  Settings")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        # LLM section
        llm_group = QtWidgets.QFrame()
        llm_group.setObjectName("CardFrame")
        llm_layout = QtWidgets.QFormLayout(llm_group)
        llm_layout.setSpacing(10)

        llm_header = QtWidgets.QLabel("LLM Provider")
        llm_header.setObjectName("SectionTitle")
        llm_layout.addRow(llm_header)

        self._model_edit = QtWidgets.QLineEdit(settings.llm_model)
        self._model_edit.setObjectName("ThemedInput")
        llm_layout.addRow("Model", self._model_edit)

        self._api_key_edit = QtWidgets.QLineEdit(settings.openai_api_key or "")
        self._api_key_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._api_key_edit.setObjectName("ThemedInput")
        llm_layout.addRow("API Key", self._api_key_edit)

        self._base_url_edit = QtWidgets.QLineEdit(settings.openai_base_url or "")
        self._base_url_edit.setObjectName("ThemedInput")
        llm_layout.addRow("Base URL", self._base_url_edit)

        layout.addWidget(llm_group)

        # Paths section
        path_group = QtWidgets.QFrame()
        path_group.setObjectName("CardFrame")
        path_layout = QtWidgets.QFormLayout(path_group)
        path_layout.setSpacing(10)

        path_header = QtWidgets.QLabel("Paths")
        path_header.setObjectName("SectionTitle")
        path_layout.addRow(path_header)

        self._library_edit = QtWidgets.QLineEdit(str(settings.library_path))
        self._library_edit.setObjectName("ThemedInput")
        path_layout.addRow("Library", self._library_edit)

        self._data_edit = QtWidgets.QLineEdit(str(settings.data_dir))
        self._data_edit.setObjectName("ThemedInput")
        path_layout.addRow("Data Dir", self._data_edit)

        layout.addWidget(path_group)

        # Appearance section (#WP8 \u2014 full palette editor)
        appearance_group = QtWidgets.QFrame()
        appearance_group.setObjectName("CardFrame")
        appearance_layout = QtWidgets.QVBoxLayout(appearance_group)
        appearance_layout.setSpacing(10)
        appearance_header = QtWidgets.QLabel("Appearance")
        appearance_header.setObjectName("SectionTitle")
        appearance_layout.addWidget(appearance_header)
        self._appearance = AppearanceEditor(current_theme())
        appearance_layout.addWidget(self._appearance)
        layout.addWidget(appearance_group)

        # Info note
        info = QtWidgets.QLabel(
            "\u2139\ufe0f  Model/paths take effect on the next pipeline run; theme "
            "applies immediately and is saved. For permanent provider config, set "
            "environment variables."
        )
        info.setObjectName("MutedLabel")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("DialogGhostButton")
        cancel_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(apply_btn)

        layout.addLayout(btn_row)

    def get_settings(self) -> dict:
        return {
            "model": self._model_edit.text().strip(),
            "api_key": self._api_key_edit.text().strip() or None,
            "base_url": self._base_url_edit.text().strip() or None,
            "library_path": self._library_edit.text().strip(),
            "data_dir": self._data_edit.text().strip(),
            "theme": self._appearance.theme(),
        }


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self.worker: PipelineWorker | None = None
        self._debug_windows: list[QtWidgets.QPlainTextEdit] = []
        self._last_result: PipelineResult | None = None

        self.setObjectName("MainWindow")
        self.setWindowTitle("AetherLab")

        # Load the persisted theme BEFORE styling anything (#WP8).
        set_current_theme(load_theme(settings.data_dir))

        # Responsive sizing (#15) — adapt to available screen space
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w = min(1500, int(geo.width() * 0.92))
            h = min(950, int(geo.height() * 0.92))
        else:
            w, h = 1500, 950
        self.resize(w, h)
        self.setStyleSheet(build_qss(current_theme()))

        # ── Panels (created BEFORE shortcuts/menu) ──
        self.sidebar = SidebarNav()
        self.analysis_panel = AnalysisPanel()
        self.reference_panel = ReferencePanel()
        self.simulation_panel = SimulationPanel()
        self.parameter_dock = ParameterDock()
        self.command_bar = CommandBar()
        self.stepper = PipelineStepper()
        self.history_panel = HistoryPanel()

        # ── Left content area (switched by sidebar nav) ──
        self._content_stack = QtWidgets.QStackedWidget()
        self._content_stack.addWidget(self.analysis_panel)    # 0: Solve
        self._content_stack.addWidget(self.reference_panel)    # 1: Refs
        self._content_stack.addWidget(self.history_panel)      # 2: History

        # ── Right area: canvas + stepper + parameters ──
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.simulation_panel, 1)
        right_layout.addWidget(self.stepper)
        right_layout.addWidget(self.parameter_dock)

        # ── Horizontal splitter: sidebar | content | right (#15 adaptive) ──
        h_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        h_splitter.addWidget(self.sidebar)
        h_splitter.addWidget(self._content_stack)
        h_splitter.addWidget(right_panel)

        # Adaptive splitter ratios based on window width (#15)
        sidebar_w = 160
        content_w = max(300, int((w - sidebar_w) * 0.33))
        right_w = w - sidebar_w - content_w
        h_splitter.setSizes([sidebar_w, content_w, right_w])
        h_splitter.setCollapsible(0, False)
        h_splitter.setCollapsible(2, False)

        # ── Vertical splitter: main content | command bar ──
        v_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        v_splitter.addWidget(h_splitter)
        v_splitter.addWidget(self.command_bar)
        main_h = int(h * 0.9)
        v_splitter.setSizes([main_h, h - main_h])
        v_splitter.setCollapsible(1, False)

        # Root
        root = QtWidgets.QWidget()
        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(v_splitter)

        self.setCentralWidget(root)

        # ── Menu bar & shortcuts (after panels exist) ──
        self._build_menu_bar()
        self._build_shortcuts()

        provider_note = (
            f" {settings.llm_model}" if settings.openai_api_key else " No API key"
        )
        self.statusBar().showMessage(f"AetherLab ready.{provider_note}")
        self._connect_signals()

        # Initialize history persistence (#5)
        self.history_panel.init_persistence(settings.data_dir / "history.sqlite3")

    def _build_shortcuts(self) -> None:
        """Register global keyboard shortcuts (#13 keyboard nav)."""
        sc_submit = QtGui.QShortcut("Ctrl+Return", self)
        sc_submit.activated.connect(self.command_bar._submit)

        sc_toggle_code = QtGui.QShortcut("Ctrl+Shift+C", self)
        sc_toggle_code.activated.connect(self._toggle_code_view)

        # Ctrl+1..5 for sidebar tabs (#13)
        for i in range(5):
            sc = QtGui.QShortcut(f"Ctrl+{i + 1}", self)
            sc.activated.connect(lambda idx=i: self.sidebar.select(idx))

        # Escape to cancel pipeline (#2)
        sc_cancel = QtGui.QShortcut("Escape", self)
        sc_cancel.activated.connect(self._cancel_pipeline)

        # Ctrl+0 to reset canvas zoom (#11)
        sc_reset = QtGui.QShortcut("Ctrl+0", self)
        sc_reset.activated.connect(self.simulation_panel._live_canvas.reset_view)

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        export_tex = file_menu.addAction("Export Derivation as &LaTeX\u2026")
        export_tex.triggered.connect(self._export_latex)

        export_pdf = file_menu.addAction("Export Derivation as &PDF\u2026")
        export_pdf.triggered.connect(self._export_pdf)

        export_scene = file_menu.addAction("Export Scene &Code\u2026")
        export_scene.triggered.connect(self._export_scene)

        export_gif = file_menu.addAction("Export Animation as &GIF\u2026")  # #17
        export_gif.triggered.connect(self._export_gif)

        file_menu.addSeparator()
        toggle_code = file_menu.addAction("Toggle &Code View")
        toggle_code.triggered.connect(self._toggle_code_view)

        # Settings menu (#6)
        edit_menu = menu.addMenu("&Edit")
        settings_action = edit_menu.addAction("&Settings\u2026")
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)

    def _export_latex(self) -> None:
        if not self._last_result:
            self.statusBar().showMessage("No pipeline result to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export LaTeX", "derivation.tex", "LaTeX Files (*.tex)"
        )
        if not path:
            return
        solver = self._last_result.solver
        export_derivation_to_latex(
            solver.summary, solver.derivation_steps, solver.variables, Path(path)
        )
        self.statusBar().showMessage(f"LaTeX exported: {path}")

    def _export_pdf(self) -> None:
        if not self._last_result:
            self.statusBar().showMessage("No pipeline result to export.")
            return
        # Ask for the destination BEFORE compiling — no wasted pdflatex run
        # when the user cancels the dialog (#F72).
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export PDF", "derivation.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        import tempfile
        tmp = Path(tempfile.gettempdir()) / "aetherlab_export" / "derivation.tex"
        solver = self._last_result.solver
        export_derivation_to_latex(
            solver.summary, solver.derivation_steps, solver.variables, tmp
        )
        self.statusBar().showMessage("Compiling PDF…")
        pdf = compile_latex_to_pdf(tmp)
        if pdf and pdf.exists():
            import shutil
            shutil.copy2(pdf, path)
            self.statusBar().showMessage(f"PDF exported: {path}")
        else:
            self.statusBar().showMessage(
                "pdflatex not found or compilation failed. Use 'Export as LaTeX' instead."
            )

    def _export_scene(self) -> None:
        if not self._last_result:
            self.statusBar().showMessage("No pipeline result to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Scene Code", "scene.py", "Python Files (*.py)"
        )
        if not path:
            return
        export_scene_code(self._last_result.scene.code, Path(path))
        self.statusBar().showMessage(f"Scene code exported: {path}")

    def _export_gif(self) -> None:
        """Export the last rendered video as an animated GIF via ffmpeg (#17)."""
        if not self._last_result or not self._last_result.scene.video_path:
            self.statusBar().showMessage("No rendered video to export.")
            return
        video_path = Path(self._last_result.scene.video_path)
        if not video_path.exists():
            self.statusBar().showMessage("Video file not found.")
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export GIF", "animation.gif", "GIF Files (*.gif)"
        )
        if not path:
            return

        self.statusBar().showMessage("Converting video to GIF\u2026")
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(video_path),
                    "-vf", "fps=15,scale=480:-1:flags=lanczos",
                    "-loop", "0", str(path),
                ],
                capture_output=True, text=True, timeout=120,
                creationflags=0x08000000,  # CREATE_NO_WINDOW on Windows
            )
            if result.returncode == 0 and Path(path).exists():
                size_mb = Path(path).stat().st_size / 1e6
                self.statusBar().showMessage(f"GIF exported: {path} ({size_mb:.1f} MB)")
            else:
                self.statusBar().showMessage("GIF conversion failed. Is ffmpeg installed?")
        except FileNotFoundError:
            self.statusBar().showMessage("ffmpeg not found. Install ffmpeg to export GIFs.")
        except subprocess.TimeoutExpired:
            self.statusBar().showMessage("GIF conversion timed out.")

    def _open_settings(self) -> None:
        """Open the settings dialog (#6)."""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._apply_settings(dialog.get_settings())

    def _apply_settings(self, vals: dict) -> None:
        """Apply dialog values to the live settings used by the next run (#F71).

        AppSettings is frozen, so build a replacement. Environment variables are
        untouched; this is an in-memory override for the current session.
        """
        from dataclasses import replace

        self.settings = replace(
            self.settings,
            llm_model=vals["model"] or self.settings.llm_model,
            openai_api_key=vals["api_key"],
            openai_base_url=vals["base_url"],
            library_path=Path(vals["library_path"]) if vals["library_path"] else self.settings.library_path,
            data_dir=Path(vals["data_dir"]) if vals["data_dir"] else self.settings.data_dir,
        )
        if vals.get("theme") is not None:
            self._apply_theme(vals["theme"])
        provider_note = (
            f" {self.settings.llm_model}" if self.settings.openai_api_key else " No API key"
        )
        self.statusBar().showMessage(
            f"Settings applied for the next pipeline run.{provider_note}"
        )

    def _apply_theme(self, theme: Theme) -> None:
        """Restyle the whole app live and persist the choice (#WP8).

        One setStyleSheet on the window cascades to every child; the canvas
        painter reads colors from the module-level current theme, so it just
        needs its cached fonts rebuilt and a repaint.
        """
        set_current_theme(theme)
        self.setStyleSheet(build_qss(theme))
        self.simulation_panel._live_canvas.refresh_theme()
        # Repolish so QSS objectName rules re-evaluate immediately.
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        save_theme(theme, self.settings.data_dir)

    def _toggle_code_view(self) -> None:
        if self.simulation_panel._stack.currentIndex() == 3:
            self.simulation_panel.show_canvas()
        else:
            self.simulation_panel.show_code()

    def _cancel_pipeline(self) -> None:
        """Cancel the running pipeline (#2).

        Run stays disabled until the worker thread actually finishes (its
        finished signal calls set_busy(False)); re-enabling it here would
        mislead while the current stage is still winding down (#F73).
        """
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.statusBar().showMessage("Cancelling pipeline\u2026")
            self.command_bar.set_cancelling()

    def _connect_signals(self) -> None:
        self.sidebar.item_selected.connect(self._on_sidebar_select)
        self.command_bar.submitted.connect(self.start_pipeline)
        self.command_bar.cancel_requested.connect(self._cancel_pipeline)  # #2
        self.history_panel.prompt_selected.connect(self.start_pipeline)

        self.parameter_dock.parameter_changed.connect(
            self.simulation_panel.apply_parameter_update
        )
        # analysis_panel.update_variable connection removed (#F63 — was a no-op)
        # token_selected signal removed (#4 — was dead wiring)
        self.simulation_panel.parameter_changed.connect(
            self.parameter_dock.update_variable
        )
        self.simulation_panel.phase_toggled.connect(
            self.simulation_panel.toggle_phase
        )

    def _on_sidebar_select(self, index: int) -> None:
        """Handle sidebar navigation.

        0 Solve / 1 Refs / 4 History switch the left content stack.
        2 Scene focuses the live canvas; 3 Params expands the parameter dock.
        """
        if index == 0:
            self._content_stack.setCurrentIndex(0)
        elif index == 1:
            self._content_stack.setCurrentIndex(1)
        elif index == 2:
            self.simulation_panel.show_canvas()
        elif index == 3:
            self.parameter_dock.expand()
        elif index == 4:
            self._content_stack.setCurrentIndex(2)

    def start_pipeline(self, prompt: str) -> None:
        if self.worker and self.worker.isRunning():
            self.statusBar().showMessage("Pipeline is already running.")
            return

        request = ProblemRequest(prompt=prompt)
        render_quality = self.command_bar.get_render_quality()
        self.worker = PipelineWorker(
            request=request, settings=self.settings, render_quality=render_quality
        )
        self.worker.status.connect(self.statusBar().showMessage)
        self.worker.solver_ready.connect(self.on_solver_ready)
        self.worker.rag_ready.connect(self.on_rag_ready)
        self.worker.scene_ready.connect(self.on_scene_ready)
        self.worker.render_ready.connect(self.on_render_ready)
        self.worker.failure.connect(self.on_failure)
        self.worker.pipeline_finished.connect(self.on_pipeline_finished)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(lambda: self.command_bar.set_busy(False))
        self.command_bar.set_busy(True)
        self.simulation_panel.clear_error_banner()
        self.simulation_panel.show_loading()
        self.stepper.reset()
        self.stepper.set_stage(0)
        self.statusBar().showMessage("Launching pipeline\u2026")
        self.worker.start()

    def _on_progress(self, value: int, text: str = "") -> None:
        if value <= 30:
            self.stepper.set_stage(0, "complete" if value >= 30 else "active")
        elif value <= 50:
            self.stepper.set_stage(1, "complete" if value >= 50 else "active")
        elif value <= 70:
            self.stepper.set_stage(2, "complete" if value >= 70 else "active")
        elif value <= 95:
            self.stepper.set_stage(3, "complete" if value >= 95 else "active")
        if value >= 100:
            self.stepper.set_stage(3, "complete")

    def on_solver_ready(self, solver: SolverResult) -> None:
        self.analysis_panel.set_solver_result(solver)
        self.parameter_dock.set_variables(solver.variables)
        self.simulation_panel.set_solver(solver)
        self.stepper.set_stage(0, "complete")
        self.sidebar.select(2)

    def on_rag_ready(self, rag: RagResult) -> None:
        self.reference_panel.set_rag_result(rag)
        self.stepper.set_stage(1, "complete")

    def on_scene_ready(self, scene: SceneBundle) -> None:
        self.simulation_panel.hide_loading()
        self.simulation_panel.set_scene_bundle(scene)
        self.stepper.set_stage(2, "complete")

    def on_render_ready(self, scene: SceneBundle) -> None:
        self.simulation_panel.set_video(scene)
        self.stepper.set_stage(3, "complete")

    def on_failure(self, error: PipelineError) -> None:
        self.simulation_panel.hide_loading()
        self.stepper.set_stage(self.stepper._current_stage, "error")
        self.statusBar().showMessage(f"{error.stage} failed: {error.message}")
        self.simulation_panel.show_error_banner(
            error.stage, error.message, error.traceback or error.message
        )

    def on_pipeline_finished(self, result: PipelineResult) -> None:
        self._last_result = result
        self.history_panel.add_entry(
            result.request.prompt,
            result.cache_key[:12],
            result.scene.status,
            len(result.rag.hits),
        )
        self.statusBar().showMessage(
            f"Pipeline complete. Cache {result.cache_key[:12]} | scene {result.scene.status}."
        )
