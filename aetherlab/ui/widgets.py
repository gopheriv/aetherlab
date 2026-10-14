"""Backward-compatible facade for AetherLab's Qt widgets.

Implementations live in focused modules; imports from ``aetherlab.ui.widgets``
remain supported for the application and existing integrations.
"""

from __future__ import annotations

from aetherlab.ui.analysis_panel import AnalysisPanel
from aetherlab.ui.command_bar import EXAMPLE_PROMPTS, CommandBar
from aetherlab.ui.lesson_view import LessonView, _LessonCheckDialog, _QuestionCard
from aetherlab.ui.library_panel import LibraryPanel, StarterLibraryDialog, _BookSpine
from aetherlab.ui.navigation import HistoryPanel, PipelineStepper, SidebarNav
from aetherlab.ui.parameter_dock import ParameterDock
from aetherlab.ui.reference_panel import ReferencePanel, _RagHitCard
from aetherlab.ui.shared_widgets import (
    BlueprintBackdrop,
    BlueprintLoadingOverlay,
    EmptyStateView,
    RunningView,
    TitleBar,
    Toast,
)
from aetherlab.ui.simulation_panel import (
    ActSeekSlider,
    CodeArtifactView,
    CritiqueBadge,
    ManimBadge,
    SimulationPanel,
    StoryboardStrip,
    _DiagnosticsDrawer,
    _frame_step_ms_for_video,
    _ManimHighlighter,
    _storyboard_acts,
    parse_scene_meta,
)

__all__ = [
    "ActSeekSlider",
    "AnalysisPanel",
    "BlueprintBackdrop",
    "BlueprintLoadingOverlay",
    "CodeArtifactView",
    "CommandBar",
    "CritiqueBadge",
    "EXAMPLE_PROMPTS",
    "EmptyStateView",
    "HistoryPanel",
    "LessonView",
    "LibraryPanel",
    "ManimBadge",
    "ParameterDock",
    "PipelineStepper",
    "ReferencePanel",
    "RunningView",
    "SidebarNav",
    "SimulationPanel",
    "StarterLibraryDialog",
    "StoryboardStrip",
    "TitleBar",
    "Toast",
    "_BookSpine",
    "_DiagnosticsDrawer",
    "_LessonCheckDialog",
    "_ManimHighlighter",
    "_QuestionCard",
    "_RagHitCard",
    "_frame_step_ms_for_video",
    "_storyboard_acts",
    "parse_scene_meta",
]
