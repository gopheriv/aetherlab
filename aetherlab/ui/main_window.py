"""Modern dashboard-style PyQt6 desktop window for AetherLab."""

from __future__ import annotations

from pathlib import Path

from aetherlab.core.models import PipelineError, PipelineResult, ProblemRequest, RagResult, SceneBundle, SolverResult
from aetherlab.core.settings import AppSettings
from aetherlab.services.pdf import compile_latex_to_pdf, export_derivation_to_latex, export_scene_code
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt
from aetherlab.ui.style import AETHERLAB_QSS
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


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self.worker: PipelineWorker | None = None
        self._debug_windows: list[QtWidgets.QPlainTextEdit] = []
        self._last_result: PipelineResult | None = None

        self.setObjectName("MainWindow")
        self.setWindowTitle("AetherLab")
        self.resize(1500, 950)
        self.setStyleSheet(AETHERLAB_QSS)

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
        # Scene and Params act on the always-visible right panel

        # ── Right area: canvas + stepper + parameters ──
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_layout.addWidget(self.simulation_panel, 1)
        right_layout.addWidget(self.stepper)
        right_layout.addWidget(self.parameter_dock)

        # ── Horizontal splitter: sidebar | content | right ──
        h_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        h_splitter.addWidget(self.sidebar)
        h_splitter.addWidget(self._content_stack)
        h_splitter.addWidget(right_panel)
        h_splitter.setSizes([160, 440, 900])
        h_splitter.setCollapsible(0, False)
        h_splitter.setCollapsible(2, False)

        # ── Vertical splitter: main content | command bar ──
        v_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        v_splitter.addWidget(h_splitter)
        v_splitter.addWidget(self.command_bar)
        v_splitter.setSizes([860, 90])
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

    def _build_shortcuts(self) -> None:
        """Register global keyboard shortcuts."""
        sc_submit = QtGui.QShortcut("Ctrl+Return", self)
        sc_submit.activated.connect(self.command_bar._submit)

        sc_toggle_code = QtGui.QShortcut("Ctrl+Shift+C", self)
        sc_toggle_code.activated.connect(self._toggle_code_view)

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        export_tex = file_menu.addAction("Export Derivation as &LaTeX\u2026")
        export_tex.triggered.connect(self._export_latex)

        export_pdf = file_menu.addAction("Export Derivation as &PDF\u2026")
        export_pdf.triggered.connect(self._export_pdf)

        export_scene = file_menu.addAction("Export Scene &Code\u2026")
        export_scene.triggered.connect(self._export_scene)

        file_menu.addSeparator()
        toggle_code = file_menu.addAction("Toggle &Code View")
        toggle_code.triggered.connect(self._toggle_code_view)

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
        import tempfile
        tmp = Path(tempfile.gettempdir()) / "aetherlab_export" / "derivation.tex"
        solver = self._last_result.solver
        export_derivation_to_latex(
            solver.summary, solver.derivation_steps, solver.variables, tmp
        )
        pdf = compile_latex_to_pdf(tmp)
        if pdf and pdf.exists():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export PDF", "derivation.pdf", "PDF Files (*.pdf)"
            )
            if path:
                import shutil
                shutil.copy2(pdf, path)
                self.statusBar().showMessage(f"PDF exported: {path}")
        else:
            self.statusBar().showMessage(
                "pdflatex not found or compilation failed. LaTeX file saved instead."
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

    def _toggle_code_view(self) -> None:
        if self.simulation_panel._stack.currentIndex() == 3:
            self.simulation_panel.show_canvas()
        else:
            self.simulation_panel.show_code()

    def _connect_signals(self) -> None:
        # Sidebar nav: indices 0-1 switch content stack, 2-3 show right panel
        self.sidebar.item_selected.connect(self._on_sidebar_select)

        # Command bar submission starts pipeline
        self.command_bar.submitted.connect(self.start_pipeline)

        # History: double-clicking a past run re-runs it
        self.history_panel.prompt_selected.connect(self.start_pipeline)

        # Parameter changes propagate between dock, analysis, and simulation
        self.parameter_dock.parameter_changed.connect(
            self.simulation_panel.apply_parameter_update
        )
        self.parameter_dock.parameter_changed.connect(
            self.analysis_panel.update_variable
        )
        self.analysis_panel.token_selected.connect(
            self.simulation_panel.apply_parameter_update
        )
        self.simulation_panel.parameter_changed.connect(
            self.parameter_dock.update_variable
        )
        # Phase portrait checkbox now actually toggles the overlay.
        self.simulation_panel.phase_toggled.connect(
            self.simulation_panel.toggle_phase
        )

    def _on_sidebar_select(self, index: int) -> None:
        """Handle sidebar navigation.

        0 Solve / 1 Refs / 4 History switch the left content stack.
        2 Scene focuses the live canvas; 3 Params expands the parameter dock —
        both act on the always-visible right panel.
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
        # Auto-switch to Scene view
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
        # Show the inline, dismissible error banner with a "Details" view
        # instead of spawning a detached top-level popup window.
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
