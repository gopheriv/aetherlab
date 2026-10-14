"""Simulation player, storyboard, scene critique, and code diagnostics."""

from __future__ import annotations

from pathlib import Path

from aetherlab.core.models import SceneBundle, SolverResult
from aetherlab.ui import icons
from aetherlab.ui.live_canvas import LiveCanvas, build_canvas_state
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt
from aetherlab.ui.shared_widgets import BlueprintLoadingOverlay, _copy_to_clipboard

require_qt()


_SIM_COPY = {
    "kk": {
        "details": "Толығырақ", "close": "Жабу", "waiting": "Күтілуде…",
        "repair_tip": "Жүйе рендер қателерін автоматты түрде түзетті", "revision_tip": "Көрнекі тексеруден кейін безендіру түзетілді",
        "phase": "Фазалық портрет", "phase_tip": "Фазалық портретті көрсету не жасыру", "tabs": ("Көрініс", "Бейне", "Код"),
        "code_title": "Жасалған сахна коды", "copy": "Көшіру", "copy_tip": "Сахна кодын алмасу буферіне көшіру", "export_scene": "scene.py экспорттау",
        "previous": "Алдыңғы кадр", "play": "Ойнату", "pause": "Кідірту", "stop": "Тоқтату", "next": "Келесі кадр",
        "seek": "Бейне бойынша өту: күлгін белгі — бөлім басы, сары белгі — негізгі кадр", "speed": "Ойнату жылдамдығы",
        "save": "Сақтау", "save_tip": "Дайын MP4 бейнесін сақтау", "gif": "GIF", "gif_tip": "GIF анимациясы ретінде экспорттау (ffmpeg қажет)",
        "waiting_status": "Күтілуде…", "computing": "Есептеу және талдау жүріп жатыр…", "rendering": "Интерактивті график дайын · бейне рендерленуде…",
        "phase_on": "Фазалық портрет қосылды", "phase_off": "Фазалық портрет өшірілді", "no_animation": "Анимация қажет емес — зерттеу PDF файлын «Талдау» бөлімінен экспорттаңыз.",
        "engine": "Қозғалтқыш: {engine} · күйі: {status}", "loading_video": "Жүктелуде: {name}", "missing_video": "Бейне файлы табылмады: {path}",
        "not_rendered": "Бейне рендерленбеді. Күйі: {status}", "playing": "Ойнатылып жатыр", "parameter": "Параметр: {name} = {value}",
        "failed": "{stage} кезеңі сәтсіз аяқталды: {message}", "traceback_title": "Pipeline қатесі", "diagnostics": "Диагностика", "issues": "Мәселелер",
        "ready": "Дайын", "revise": "Түзету ұсынылады", "no_storyboard": "Бұл сахнада жоспар-көрініс жоқ.",
        "video_empty": "Бейне әлі жасалмады. Алдымен есепті шешіп, рендерлеңіз.",
        "repair_count": "түзетілді ×{n}", "revision_count": "қайта қаралды ×{n}",
    },
    "ru": {
        "details": "Подробнее", "close": "Закрыть", "waiting": "Ожидание…",
        "repair_tip": "Ошибки рендера автоматически исправлены", "revision_tip": "Визуальные правки после проверки оформления",
        "phase": "Фазовый портрет", "phase_tip": "Показать или скрыть фазовый портрет", "tabs": ("Холст", "Видео", "Код"),
        "code_title": "Код сцены", "copy": "Копировать", "copy_tip": "Скопировать код сцены", "export_scene": "Экспорт scene.py",
        "previous": "Предыдущий кадр", "play": "Воспроизвести", "pause": "Пауза", "stop": "Остановить", "next": "Следующий кадр",
        "seek": "Позиция: фиолетовый — начало главы, янтарный — ключевой кадр", "speed": "Скорость воспроизведения",
        "save": "Сохранить", "save_tip": "Сохранить готовое видео MP4", "gif": "GIF", "gif_tip": "Экспортировать как анимированный GIF (нужен ffmpeg)",
        "waiting_status": "Ожидание…", "computing": "Вычисление и анализ…", "rendering": "Интерактивный график готов · рендер видео…",
        "phase_on": "Фазовый портрет включён", "phase_off": "Фазовый портрет выключен", "no_animation": "Анимация не нужна — экспортируйте исследовательский PDF из раздела «Анализ».",
        "engine": "Движок: {engine} · статус: {status}", "loading_video": "Загрузка: {name}", "missing_video": "Файл видео не найден: {path}",
        "not_rendered": "Видео не отрендерено. Статус: {status}", "playing": "Воспроизведение", "parameter": "Параметр: {name} = {value}",
        "failed": "Ошибка на этапе {stage}: {message}", "traceback_title": "Ошибка конвейера", "diagnostics": "Диагностика", "issues": "Замечания",
        "ready": "Готово", "revise": "Нужна правка", "no_storyboard": "Для этой сцены нет раскадровки.",
        "video_empty": "Видео ещё не создано. Сначала решите задачу и запустите рендер.",
        "repair_count": "исправлено ×{n}", "revision_count": "изменено ×{n}",
    },
    "en": {
        "details": "Details", "close": "Close", "waiting": "Waiting for pipeline…",
        "repair_tip": "Render errors automatically fixed by the pipeline", "revision_tip": "Visual revisions applied after critique",
        "phase": "Phase portrait", "phase_tip": "Toggle the phase portrait overlay", "tabs": ("Canvas", "Video", "Code"),
        "code_title": "Generated Scene Code", "copy": "Copy code", "copy_tip": "Copy scene code to the clipboard", "export_scene": "Export scene.py",
        "previous": "Previous frame", "play": "Play", "pause": "Pause", "stop": "Stop", "next": "Next frame",
        "seek": "Seek: violet marks act starts; amber marks the key frame", "speed": "Playback speed",
        "save": "Save", "save_tip": "Save the rendered MP4", "gif": "GIF", "gif_tip": "Export as animated GIF (requires ffmpeg)",
        "waiting_status": "Waiting for pipeline…", "computing": "Computing analytical pipeline…", "rendering": "Live canvas active — rendering video…",
        "phase_on": "Phase portrait overlay on", "phase_off": "Phase portrait overlay off", "no_animation": "No animation needed — export the research PDF from Analysis.",
        "engine": "Engine: {engine} | Status: {status}", "loading_video": "Loading: {name}", "missing_video": "Video file not found: {path}",
        "not_rendered": "Video not rendered. Status: {status}", "playing": "Playing", "parameter": "Parameter: {name} = {value}",
        "failed": "{stage} failed: {message}", "traceback_title": "Pipeline Traceback", "diagnostics": "Diagnostics", "issues": "Issues",
        "ready": "Ready to ship", "revise": "Revision suggested", "no_storyboard": "No storyboard for this scene.",
        "video_empty": "No video yet. Solve a problem and render it first.",
        "repair_count": "repaired ×{n}", "revision_count": "revised ×{n}",
    },
}

class SimulationPanel(QtWidgets.QWidget):
    parameter_changed = QtCore.pyqtSignal(str, float)
    phase_toggled = QtCore.pyqtSignal(bool)
    save_video_requested = QtCore.pyqtSignal()
    export_gif_requested = QtCore.pyqtSignal()
    export_scene_requested = QtCore.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._language = "kk"
        self._text_widgets: dict[str, QtWidgets.QWidget] = {}
        self._frame_step_ms = 33
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Error banner (hidden by default) ──
        self._error_banner = QtWidgets.QFrame()
        self._error_banner.setObjectName("ErrorBanner")
        self._error_banner.setStyleSheet(
            "QFrame#ErrorBanner {"
            "  background-color: #1C0A0A; border-bottom: 2px solid #AC4055;"
            "  padding: 0;"
            "}"
        )
        err_layout = QtWidgets.QHBoxLayout(self._error_banner)
        err_layout.setContentsMargins(16, 8, 16, 8)
        err_layout.setSpacing(12)

        self._error_icon = QtWidgets.QLabel("\u26a0\ufe0f")
        self._error_icon.setStyleSheet("font-size: 14px; color: #AC4055;")
        err_layout.addWidget(self._error_icon)

        self._error_text = QtWidgets.QLabel("")
        self._error_text.setStyleSheet("color: #8E3147; font-size: 12px;")
        self._error_text.setWordWrap(True)
        err_layout.addWidget(self._error_text, 1)

        self._error_detail_btn = QtWidgets.QPushButton()
        self._error_detail_btn.setFixedWidth(72)
        self._error_detail_btn.setStyleSheet(
            "background: transparent; border: 1px solid #AC4055; border-radius: 6px;"
            " color: #8E3147; font-size: 11px; padding: 4px 8px;"
        )
        self._error_detail_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._error_detail_btn.clicked.connect(self._show_error_details)
        err_layout.addWidget(self._error_detail_btn)

        self._dismiss_error_btn = QtWidgets.QPushButton("\u2715")
        self._dismiss_error_btn.setFixedWidth(28)
        self._dismiss_error_btn.setStyleSheet(
            "background: transparent; border: none; color: #65758A; font-size: 14px;"
        )
        self._dismiss_error_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._dismiss_error_btn.clicked.connect(self._error_banner.hide)
        err_layout.addWidget(self._dismiss_error_btn)

        self._error_banner.hide()
        self._error_traceback = ""
        layout.addWidget(self._error_banner)

        # Top bar with pill tabs for view switching + phase portrait toggle
        top_bar = QtWidgets.QWidget()
        top_bar.setObjectName("SceneToolbar")
        top_bar.setFixedHeight(48)
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 6, 16, 6)
        top_layout.setSpacing(8)

        self.status = QtWidgets.QLabel()
        self.status.setObjectName("StatusIdle")
        self.status.setStyleSheet("font-size: 12px;")
        top_layout.addWidget(self.status, 1)

        # Self-heal / revision pills (design v2 \u00a74) \u2014 hidden until they apply
        self._repaired_pill = _Pill("", "#8A5A24")
        self._repaired_pill.hide()
        top_layout.addWidget(self._repaired_pill)
        self._revised_pill = _Pill("", "#536F90")
        self._revised_pill.hide()
        top_layout.addWidget(self._revised_pill)

        # Phase portrait toggle checkbox
        self._phase_check = QtWidgets.QCheckBox()
        self._phase_check.setStyleSheet(
            "QCheckBox { color: #65758A; font-size: 11px; font-weight: 600; spacing: 6px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px;"
            "  border: 1px solid #A5B6CB; background: #FFFFFF; }"
            "QCheckBox::indicator:checked { background: #486A91; border-color: #486A91; }"
        )
        self._phase_check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._phase_check.toggled.connect(self.phase_toggled.emit)
        top_layout.addWidget(self._phase_check)

        # View pill tabs
        self._pill_group = QtWidgets.QButtonGroup(self)
        self._pill_group.setExclusive(True)
        self._view_buttons: list[QtWidgets.QPushButton] = []
        for i, label in enumerate(["Canvas", "Video", "Code"]):
            pill = QtWidgets.QPushButton(label)
            pill.setObjectName("PillTab")
            pill.setCheckable(True)
            pill.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self._pill_group.addButton(pill, i)
            pill.clicked.connect(lambda checked, idx=i: self._switch_view(idx))
            self._view_buttons.append(pill)
            top_layout.addWidget(pill)

        layout.addWidget(top_bar)

        # Stacked widget: loading + live canvas + video + code
        self._stack = QtWidgets.QStackedWidget()

        # Index 0: loading overlay
        self._loading = BlueprintLoadingOverlay()

        # Index 1: live interactive canvas
        self._live_canvas = LiveCanvas()

        # Index 2: video player
        self._video_frame = self._build_video_player()

        # Index 3: code viewer with copy button (#3)
        self._code_frame = QtWidgets.QFrame()
        self._code_frame.setObjectName("CardFrame")
        code_layout = QtWidgets.QVBoxLayout(self._code_frame)
        code_layout.setContentsMargins(14, 10, 14, 10)

        code_header = QtWidgets.QWidget()
        ch_layout = QtWidgets.QHBoxLayout(code_header)
        ch_layout.setContentsMargins(0, 0, 0, 0)
        self._code_title = QtWidgets.QLabel()
        self._code_title.setStyleSheet(
            "color: #65758A; font-size: 9pt; font-weight: 700; "
            "text-transform: uppercase; letter-spacing: 1.2px;"
        )
        ch_layout.addWidget(self._code_title)
        ch_layout.addStretch()
        self._copy_code_btn = QtWidgets.QPushButton()
        self._copy_code_btn.setIcon(icons.icon("copy", 12, "#65758A"))
        self._copy_code_btn.setFixedHeight(26)
        self._copy_code_btn.setStyleSheet(
            "background: transparent; border: 1px solid #A5B6CB; border-radius: 4px; "
            "color: #65758A; font-size: 11px; padding: 2px 10px;"
        )
        self._copy_code_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._copy_code_btn.clicked.connect(lambda: _copy_to_clipboard(self.code.toPlainText()))
        ch_layout.addWidget(self._copy_code_btn)

        self._export_code_btn = QtWidgets.QPushButton()
        self._export_code_btn.setObjectName("SecondaryButton")
        self._export_code_btn.setIcon(icons.icon("download", 13, "#65758A"))
        self._export_code_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._export_code_btn.clicked.connect(self.export_scene_requested.emit)
        ch_layout.addWidget(self._export_code_btn)
        # Engine / status / duration chips (design v2 §6: code view is an artifact)
        self._code_chips = QtWidgets.QWidget()
        chips_layout = QtWidgets.QHBoxLayout(self._code_chips)
        chips_layout.setContentsMargins(0, 2, 0, 2)
        chips_layout.setSpacing(6)
        self._engine_chip = _Pill("engine", "#65758A")
        self._status_chip = _Pill("status", "#65758A")
        self._backend_chip = _Pill("local", "#65758A")
        self._duration_chip = _Pill("duration", "#65758A")
        for chip in (self._engine_chip, self._status_chip, self._backend_chip, self._duration_chip):
            chip.hide()
            chips_layout.addWidget(chip)
        chips_layout.addStretch()
        code_layout.addWidget(code_header)
        code_layout.addWidget(self._code_chips)

        self.code = CodeArtifactView()
        code_layout.addWidget(self.code, 1)

        # Diagnostics drawer (design v2 §4: repaired/critique surfaced, not dumped)
        self._diag_drawer = _DiagnosticsDrawer()
        code_layout.addWidget(self._diag_drawer)

        self._stack.addWidget(self._loading)
        self._stack.addWidget(self._live_canvas)
        self._stack.addWidget(self._video_frame)
        self._stack.addWidget(self._code_frame)
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, 1)

        self._solver: SolverResult | None = None

        # Set first pill checked
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)
        self.set_language(self._language)

    def _t(self, key: str, **values) -> str:
        return _SIM_COPY[self._language][key].format(**values)

    def set_language(self, language: str) -> None:
        self._language = language if language in _SIM_COPY else "kk"
        text = _SIM_COPY[self._language]
        self._error_detail_btn.setText(text["details"])
        self._dismiss_error_btn.setToolTip(text["close"])
        self._repaired_pill.setToolTip(text["repair_tip"])
        self._revised_pill.setToolTip(text["revision_tip"])
        self._phase_check.setText(text["phase"])
        self._phase_check.setToolTip(text["phase_tip"])
        for button, label in zip(self._view_buttons, text["tabs"]):
            button.setText(label)
        self._code_title.setText(text["code_title"])
        self._copy_code_btn.setText(text["copy"])
        self._copy_code_btn.setToolTip(text["copy_tip"])
        self._export_code_btn.setText(text["export_scene"])
        for button, label in (
            (self._prev_frame_btn, text["previous"]),
            (self._play_btn, text["play"]),
            (self._pause_btn, text["pause"]),
            (self._stop_btn, text["stop"]),
            (self._next_frame_btn, text["next"]),
        ):
            button.setToolTip(label)
            button.setAccessibleName(label)
        self._seek_slider.setToolTip(text["seek"])
        self._speed_slider.setToolTip(text["speed"])
        self._save_video_btn.setText(text["save"])
        self._save_video_btn.setToolTip(text["save_tip"])
        self._export_gif_btn.setText(text["gif"])
        self._export_gif_btn.setToolTip(text["gif_tip"])
        self._video_empty_hint.setText(text["video_empty"])
        if not self._solver:
            self.status.setText(text["waiting_status"])
        self._storyboard_strip.set_language(self._language)
        self._critique_badge.set_language(self._language)
        self._diag_drawer.set_language(self._language)
        if getattr(self, "_scene_meta", None):
            self._critique_badge.set_critique(self._scene_meta.get("critique"))
            if self._scene_meta.get("repaired"):
                self._repaired_pill.setText(text["repair_count"].format(n=self._scene_meta["repaired"]))
            if self._scene_meta.get("revised"):
                self._revised_pill.setText(text["revision_count"].format(n=self._scene_meta["revised"]))

    def _switch_view(self, index: int) -> None:
        # Map pill index to stack index: 0->Canvas(1), 1->Video(2), 2->Code(3)
        stack_map = {0: 1, 1: 2, 2: 3}
        target = stack_map.get(index, 1)
        if self._stack.count() > target:
            self._stack.setCurrentIndex(target)

    def apply_plan(self, plan) -> None:
        """Show only the view pills the planner enabled for this problem.

        Canvas is shown when a 2-D or 3-D graphic is warranted; Video only when
        an animation is planned; Code is always available. If the active pill
        gets hidden, fall back to the first visible one.
        """
        self._plan = plan
        want = {
            0: bool(getattr(plan, "needs_2d", True) or getattr(plan, "needs_3d", False)),
            1: bool(getattr(plan, "needs_animation", True)),
            2: True,
        }
        for btn in self._pill_group.buttons():
            btn.setVisible(want.get(self._pill_group.id(btn), True))
        checked = self._pill_group.checkedButton()
        if checked is None or not checked.isVisible():
            for btn in self._pill_group.buttons():
                if btn.isVisible():
                    btn.setChecked(True)
                    self._switch_view(self._pill_group.id(btn))
                    break

    def _build_video_player(self) -> QtWidgets.QWidget:
        from PyQt6.QtMultimedia import QMediaPlayer
        from PyQt6.QtMultimediaWidgets import QVideoWidget

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(12, 8, 12, 8)
        container_layout.setSpacing(8)

        # Screening room: true-black letterbox stage (design v2 §6)
        stage = QtWidgets.QWidget()
        stage.setObjectName("VideoStage")
        stage.setStyleSheet("QWidget#VideoStage { background-color: #000000; border-radius: 8px; }")
        stage_layout = QtWidgets.QGridLayout(stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumSize(280, 158)
        self._video_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._video_widget.setStyleSheet("background-color: #000000;")
        stage_layout.addWidget(self._video_widget, 0, 0)
        self._video_empty_hint = QtWidgets.QLabel()
        self._video_empty_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._video_empty_hint.setWordWrap(True)
        self._video_empty_hint.setStyleSheet(
            "color:#D7DEE8; background:rgba(0,0,0,150); padding:10px 16px; "
            "border-radius:8px; font-size:12px;"
        )
        self._video_empty_hint.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        stage_layout.addWidget(
            self._video_empty_hint, 0, 0, QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self._manim_badge = ManimBadge(small=True)
        badge_wrap = QtWidgets.QWidget()
        bw = QtWidgets.QHBoxLayout(badge_wrap)
        bw.setContentsMargins(0, 0, 12, 12)
        bw.addStretch()
        bw.addWidget(self._manim_badge, 0, QtCore.Qt.AlignmentFlag.AlignBottom)
        badge_wrap.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        stage_layout.addWidget(badge_wrap, 0, 0)
        container_layout.addWidget(stage, 1)

        # Docked critique badge + storyboard strip (design v2 §4/§6)
        self._critique_badge = CritiqueBadge()
        container_layout.addWidget(self._critique_badge)
        self._storyboard_strip = StoryboardStrip()
        self._storyboard_strip.act_seek_requested.connect(self._seek_fraction)
        container_layout.addWidget(self._storyboard_strip)

        # Controls bar (design: components/media/VideoControls.jsx)
        controls = QtWidgets.QFrame()
        controls.setObjectName("VideoControlsBar")
        controls.setMaximumHeight(52)
        controls_layout = QtWidgets.QHBoxLayout(controls)
        controls_layout.setContentsMargins(14, 8, 14, 8)
        controls_layout.setSpacing(10)

        # Frame step buttons (#14)
        self._prev_frame_btn = QtWidgets.QPushButton()
        self._prev_frame_btn.setIcon(icons.icon("skip-back", 14, "#65758A"))
        self._prev_frame_btn.setFixedSize(28, 28)
        self._prev_frame_btn.setObjectName("VideoControlBtn")

        # Round cyan primary play button (design)
        self._play_btn = QtWidgets.QPushButton()
        self._play_btn.setIcon(icons.icon("play", 15, "#F4F7FB"))
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setObjectName("VideoPlayBtn")

        self._pause_btn = QtWidgets.QPushButton()
        self._pause_btn.setIcon(icons.icon("pause", 14, "#65758A"))
        self._pause_btn.setFixedSize(28, 28)
        self._pause_btn.setObjectName("VideoControlBtn")

        self._stop_btn = QtWidgets.QPushButton()
        self._stop_btn.setIcon(icons.icon("square", 13, "#65758A"))
        self._stop_btn.setFixedSize(28, 28)
        self._stop_btn.setObjectName("VideoControlBtn")

        self._next_frame_btn = QtWidgets.QPushButton()
        self._next_frame_btn.setIcon(icons.icon("skip-forward", 14, "#65758A"))
        self._next_frame_btn.setFixedSize(28, 28)
        self._next_frame_btn.setObjectName("VideoControlBtn")

        self._seek_slider = ActSeekSlider()
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setObjectName("VideoSeekSlider")
        self._seeking = False

        self._time_label = QtWidgets.QLabel("0:00 / 0:00")
        self._time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._time_label.setObjectName("VideoTimeLabel")
        self._time_label.setMinimumWidth(90)

        self._speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._speed_slider.setRange(25, 200)
        self._speed_slider.setValue(100)
        self._speed_slider.setFixedWidth(72)
        self._speed_label = QtWidgets.QLabel("1.0x")
        self._speed_label.setObjectName("VideoTimeLabel")

        # Save / GIF export (design: Save affordance on the controls bar)
        self._save_video_btn = QtWidgets.QPushButton()
        self._save_video_btn.setObjectName("SecondaryButton")
        self._save_video_btn.setIcon(icons.icon("save", 13, "#65758A"))
        self._save_video_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._save_video_btn.clicked.connect(self.save_video_requested.emit)

        self._export_gif_btn = QtWidgets.QPushButton("GIF")
        self._export_gif_btn.setObjectName("SecondaryButton")
        self._export_gif_btn.setIcon(icons.icon("film", 13, "#65758A"))
        self._export_gif_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._export_gif_btn.clicked.connect(self.export_gif_requested.emit)

        controls_layout.addWidget(self._play_btn)
        controls_layout.addWidget(self._pause_btn)
        controls_layout.addWidget(self._stop_btn)
        controls_layout.addWidget(self._prev_frame_btn)  # #14
        controls_layout.addWidget(self._next_frame_btn)  # #14
        controls_layout.addWidget(self._seek_slider, 1)
        controls_layout.addWidget(self._time_label)
        controls_layout.addWidget(self._speed_slider)
        controls_layout.addWidget(self._speed_label)
        controls_layout.addWidget(self._save_video_btn)
        controls_layout.addWidget(self._export_gif_btn)

        container_layout.addWidget(controls)

        self._player = QMediaPlayer()
        self._player.setVideoOutput(self._video_widget)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.positionChanged.connect(self._on_position_changed)

        # Seek slider: track drags, seek on release, ignore feedback while dragging.
        self._seek_slider.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self._seek_slider.sliderReleased.connect(self._on_seek_released)

        self._prev_frame_btn.clicked.connect(lambda: self._step_frame(-self._frame_step_ms))
        self._next_frame_btn.clicked.connect(lambda: self._step_frame(self._frame_step_ms))

        self._play_btn.clicked.connect(self._player.play)
        self._pause_btn.clicked.connect(self._player.pause)
        self._stop_btn.clicked.connect(self._player.stop)
        self._speed_slider.valueChanged.connect(
            lambda v: (
                self._player.setPlaybackRate(v / 100.0),
                self._speed_label.setText(f"{v / 100:.1f}x"),
            )
        )

        return container

    def _on_duration_changed(self, duration: int) -> None:
        self._seek_slider.setRange(0, max(duration, 0))
        total = duration // 1000
        self._time_label.setText(f"0:00 / {total // 60}:{total % 60:02d}")

    def _on_position_changed(self, position: int) -> None:
        if not self._seeking:
            self._seek_slider.blockSignals(True)
            self._seek_slider.setValue(position)
            self._seek_slider.blockSignals(False)
        duration = self._player.duration()
        if duration > 0:
            current = position // 1000
            total = duration // 1000
            self._time_label.setText(
                f"{current // 60}:{current % 60:02d} / {total // 60}:{total % 60:02d}"
            )

    def _on_seek_released(self) -> None:
        self._player.setPosition(self._seek_slider.value())
        self._seeking = False

    def _step_frame(self, delta_ms: int) -> None:
        """Step forward/backward by one decoded frame."""
        self._player.pause()
        new_pos = max(0, self._player.position() + delta_ms)
        self._player.setPosition(new_pos)

    def set_solver(
        self, solver: SolverResult, scene_spec: dict | None = None,
    ) -> None:
        self._solver = solver
        self._scene_spec = scene_spec if isinstance(scene_spec, dict) else None
        self._rebuild_canvas()

    def _rebuild_canvas(self) -> None:
        if not self._solver:
            return
        # Preserve any live slider adjustments instead of resetting to defaults.
        params = dict(self._solver.variables)
        raw_title = self._solver.summary or "Simulation"
        plot = getattr(self._solver, "plot", None)
        numeric_spec = getattr(self._solver, "numeric_spec", None)
        try:
            from aetherlab.services.scene_specification import canvas_inputs_from_scene_spec

            projected = canvas_inputs_from_scene_spec(getattr(self, "_scene_spec", None))
            if projected is not None:
                raw_title = projected["title"] or raw_title
                params = projected["params"] or params
                plot = projected["plot"]
                numeric_spec = projected["numeric_spec"]
        except Exception:  # noqa: BLE001 - the solver path remains a safe fallback
            pass
        current = getattr(self._live_canvas, "_state", None)
        if current and current.params:
            params.update(current.params)
        from aetherlab.services.mathtext import plain_math

        title = plain_math(raw_title)[:70]
        state = build_canvas_state(
            title=title,
            params=params,
            phase_portrait=self._phase_check.isChecked(),
            plot=plot,
            numeric_spec=numeric_spec,
        )
        self._live_canvas.set_state(state)

    def toggle_phase(self, enabled: bool) -> None:
        """Rebuild the canvas with/without the phase-portrait overlay curve."""
        self._rebuild_canvas()
        self.status.setText(self._t("phase_on" if enabled else "phase_off"))

    def show_loading(self) -> None:
        self._stack.setCurrentIndex(0)
        self.status.setText(self._t("computing"))
        self.status.setObjectName("StatusWorking")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def hide_loading(self) -> None:
        self._stack.setCurrentIndex(1)
        self.status.setText(self._t("rendering"))
        self.status.setObjectName("StatusWorking")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        # Select Canvas pill
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)

    def show_code(self) -> None:
        self._stack.setCurrentIndex(3)
        pills = self._pill_group.buttons()
        if len(pills) > 2:
            pills[2].setChecked(True)

    def show_canvas(self) -> None:
        self._stack.setCurrentIndex(1)
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)

    def _apply_scene_meta(self, scene: SceneBundle) -> None:
        """Populate v2 code chips, diagnostics drawer, storyboard, critique."""
        meta = parse_scene_meta(scene)
        self._scene_meta = meta

        self._engine_chip.setText(scene.engine)
        self._engine_chip.show()
        self._status_chip.setText(scene.status)
        self._status_chip.show()
        if any("Rendered via GitHub Actions" in d or "Cloud render cache hit" in d for d in scene.diagnostics):
            self._backend_chip.setText("Cloud")
            self._backend_chip.setStyleSheet("background: rgba(52,211,153,0.12); color: #26725C; border-radius: 8px; padding: 2px 8px;")
        elif any("Cloud render unavailable; rendered locally." in d for d in scene.diagnostics):
            self._backend_chip.setText("Local fallback")
            self._backend_chip.setStyleSheet("background: rgba(251,191,36,0.12); color: #8A5A24; border-radius: 8px; padding: 2px 8px;")
        else:
            self._backend_chip.setText("Local")
            self._backend_chip.setStyleSheet("background: rgba(119,116,123,0.10); color: #65758A; border-radius: 8px; padding: 2px 8px;")
        self._backend_chip.show()
        if meta["duration"]:
            self._duration_chip.setText(meta["duration"])
            self._duration_chip.show()
        else:
            self._duration_chip.hide()

        self._diag_drawer.set_diagnostics(scene.diagnostics)

        storyboard = getattr(scene, "storyboard", None)
        self._storyboard_strip.set_storyboard(storyboard)
        acts = _storyboard_acts(storyboard)
        self._seek_slider.set_acts(acts)

        self._critique_badge.set_critique(meta["critique"])

        # Repaired / revised pills in the top bar
        self._repaired_pill.setVisible(meta["repaired"] > 0)
        if meta["repaired"]:
            self._repaired_pill.setText(self._t("repair_count", n=meta["repaired"]))
        self._revised_pill.setVisible(meta["revised"] > 0)
        if meta["revised"]:
            self._revised_pill.setText(self._t("revision_count", n=meta["revised"]))

    def set_scene_bundle(self, scene: SceneBundle) -> None:
        self._stack.setCurrentIndex(1)
        if scene.status == "skipped":
            # Planner decided this problem doesn't need an animation — present it
            # as an intentional state, not an error, and point at the PDF.
            self.status.setText(self._t("no_animation"))
            self.status.setObjectName("StatusReady")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.code.setPlainText(
                "# No Manim animation was generated for this problem.\r\n"
                "# The planner judged an animation unnecessary here.\r\n"
                "# Use 'Export PDF' in the Analysis panel for the written result."
            )
            return
        self.status.setText(self._t("engine", engine=scene.engine, status=scene.status))
        if scene.status == "compiled":
            self.status.setObjectName("StatusReady")
        else:
            self.status.setObjectName("StatusError")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.code.setPlainText(scene.code)  # diagnostics now live in the drawer
        self._apply_scene_meta(scene)
        pills = self._pill_group.buttons()
        if pills:
            pills[0].setChecked(True)

    def set_video(self, scene: SceneBundle) -> None:
        from PyQt6.QtCore import QUrl

        if scene.video_path and Path(scene.video_path).exists():
            self._stack.setCurrentIndex(2)
            self._video_empty_hint.hide()
            self._frame_step_ms = _frame_step_ms_for_video(Path(scene.video_path))
            self._player.setSource(QUrl.fromLocalFile(scene.video_path))
            # Play when media is loaded (async loading)
            try:
                self._player.mediaStatusChanged.disconnect(self._auto_play)
            except (TypeError, RuntimeError):
                pass
            self._player.mediaStatusChanged.connect(self._auto_play)
            self.status.setText(self._t("loading_video", name=Path(scene.video_path).name))
            self.status.setObjectName("StatusReady")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self._apply_scene_meta(scene)
            pills = self._pill_group.buttons()
            if len(pills) > 1:
                pills[1].setChecked(True)
        else:
            self._video_empty_hint.show()
            self.code.setPlainText(scene.code)  # diagnostics live in the drawer (v2 §4)
            self.show_code()
            if scene.video_path:
                self.status.setText(self._t("missing_video", path=scene.video_path))
            else:
                self.status.setText(self._t("not_rendered", status=scene.status))
            self.status.setObjectName("StatusError")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self._apply_scene_meta(scene)

    def _seek_fraction(self, frac: float) -> None:
        """Seek the video to a fraction of its duration (storyboard act click)."""
        dur = self._player.duration()
        if dur > 0:
            self._player.setPosition(int(frac * dur))
            self._player.play()

    def _auto_play(self, media_status) -> None:
        """Play video once media is loaded."""
        from PyQt6.QtMultimedia import QMediaPlayer
        if media_status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._player.play()
            try:
                self._player.mediaStatusChanged.disconnect(self._auto_play)
            except (TypeError, RuntimeError):
                pass
            self.status.setText(self._t("playing"))

    def apply_parameter_update(self, name: str, value: float) -> None:
        self.status.setText(self._t("parameter", name=name, value=f"{value:g}"))
        self._live_canvas.update_params({name: value})
        self.parameter_changed.emit(name, value)

    def show_error_banner(self, stage: str, message: str, traceback: str = "") -> None:
        """Show an inline error banner instead of a modal popup."""
        stage_labels = {
            "kk": {"solve": "Шешу", "rag": "Іздеу", "scene": "Сахна", "render": "Рендер"},
            "ru": {"solve": "Решение", "rag": "Поиск", "scene": "Сцена", "render": "Рендер"},
            "en": {"solve": "Solve", "rag": "RAG", "scene": "Scene", "render": "Render"},
        }
        stage_label = stage_labels[self._language].get(stage.lower(), stage)
        self._error_text.setText(self._t("failed", stage=stage_label, message=message))
        self._error_traceback = traceback or message
        self._error_banner.show()

    def clear_error_banner(self) -> None:
        """Dismiss the error banner."""
        self._error_banner.hide()
        self._error_traceback = ""

    def _show_error_details(self) -> None:
        """Open the full traceback in a non-modal window."""
        if not self._error_traceback:
            return
        # Prevent duplicate windows
        if hasattr(self, "_detail_window") and self._detail_window is not None:
            self._detail_window.setPlainText(self._error_traceback)
            self._detail_window.raise_()
            return
        detail = QtWidgets.QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(self._error_traceback)
        detail.setWindowTitle(self._t("traceback_title"))
        detail.resize(900, 500)
        detail.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        detail.destroyed.connect(lambda: setattr(self, "_detail_window", None))
        self._detail_window = detail
        detail.show()

_V2 = {
    "stage": "#000000", "panel": "#FFFFFF", "panel2": "#FFFFFF", "elev": "#EDF2F8",
    "line": "#D8E1EC", "line2": "#A5B6CB",
    "tx": "#18283D", "tx2": "#53647A", "tx3": "#65758A",
    "cyan": "#486A91", "cyan_deep": "#3B587A", "emerald": "#26725C",
    "violet": "#536F90", "amber": "#8A5A24", "rose": "#AC4055",
}

def parse_scene_meta(scene: "SceneBundle") -> dict:
    """Distill a SceneBundle's diagnostics into structured v2 UI state.

    Returns {repaired:int, revised:int, critique:{verdict,score,issues}|None,
    duration:str|None}. Pure — no Qt. Storyboard rides on scene.storyboard.
    """
    import re as _re

    diags = list(getattr(scene, "diagnostics", []) or [])
    repaired = sum(1 for d in diags if d.startswith("Applied render repair"))
    revised = sum(1 for d in diags if d.startswith("Applied visual revision"))

    critique = None
    for d in diags:
        m = _re.search(r"Visual critique round \d+: (\w+) \(score ([\d.]+)\)(?: — (.+))?", d)
        if m:
            verdict, score, issues = m.group(1), float(m.group(2)), m.group(3)
            critique = {
                "verdict": verdict,
                "score": score,
                "issues": [s.strip() for s in issues.split(";")] if issues else [],
            }
    duration = None
    for d in diags:
        m = _re.search(r"Estimated duration ~(\d+)s", d)
        if m:
            duration = f"~{m.group(1)}s"
    return {"repaired": repaired, "revised": revised,
            "critique": critique, "duration": duration}

def _frame_step_ms_for_video(path: Path) -> int:
    """Best-effort one-frame seek step from the video's encoded frame rate."""
    try:
        import av

        with av.open(str(path)) as container:
            stream = container.streams.video[0] if container.streams.video else None
            rate = float(stream.average_rate) if stream and stream.average_rate else 0.0
            if rate > 0:
                return max(1, int(round(1000.0 / rate)))
    except Exception:  # noqa: BLE001
        pass
    return 33

def _storyboard_acts(storyboard: dict | None) -> list[dict]:
    """Normalized [{name, duration_s, beats, narration}] from a storyboard dict."""
    if not isinstance(storyboard, dict):
        return []
    acts = storyboard.get("acts")
    if not isinstance(acts, list):
        return []
    narration = storyboard.get("narration")
    out = []
    for i, act in enumerate(acts):
        if not isinstance(act, dict):
            continue
        line = ""
        if isinstance(narration, list) and i < len(narration):
            line = str(narration[i])
        try:
            dur = float(act.get("duration_s", 0) or 0)
        except (TypeError, ValueError):
            dur = 0.0
        out.append({
            "name": str(act.get("name", f"ACT {i + 1}")),
            "duration_s": dur,
            "beats": [str(b) for b in act.get("beats", []) if b],
            "narration": line,
        })
    return out

class _Pill(QtWidgets.QLabel):
    """Small status pill (repaired ×N / revised ×N / verdict)."""

    def __init__(self, text: str, color: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(
            f"color: {color}; border: 1px solid {color}; border-radius: 9px; "
            "padding: 1px 9px; font-size: 10.5px; font-weight: 600; "
            "font-family: 'Cascadia Code', monospace; background: transparent;"
        )

class ManimBadge(QtWidgets.QFrame):
    """"Rendered with Manim Community" attribution (design v2 §6)."""

    def __init__(self, small: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ManimBadge")
        self.setStyleSheet(
            "QFrame#ManimBadge { background: rgba(10,10,15,0.72); border: 1px solid "
            f"{_V2['line']}; border-radius: 6px; }}"
        )
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.setSpacing(6)
        glyph = icons.icon_label("aperture", 13 if small else 15, _V2["cyan"])
        lay.addWidget(glyph)
        text = QtWidgets.QLabel("Rendered with Manim Community")
        text.setStyleSheet(
            f"color: {_V2['tx2']}; font-size: {9 if small else 10.5}px; "
            "background: transparent; border: none;"
        )
        if small:
            text.setText("Manim CE")
        lay.addWidget(text)

class ActSeekSlider(QtWidgets.QSlider):
    """Seek slider that paints storyboard act ticks (violet) and an amber
    hero-frame bookmark over the groove (design v2 §6)."""

    hero_seek_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(QtCore.Qt.Orientation.Horizontal, parent)
        self._act_fracs: list[tuple[float, str]] = []   # (start_frac, name)
        self._hero_frac: float | None = None

    def set_acts(self, acts: list[dict]) -> None:
        total = sum(a["duration_s"] for a in acts) or 0.0
        self._act_fracs = []
        self._hero_frac = None
        if total <= 0:
            self.update()
            return
        cum = 0.0
        for act in acts:
            self._act_fracs.append((cum / total, act["name"]))
            # Hero frame lives in the REVEAL act (cinematic §5): bookmark its start.
            if act["name"].upper().startswith("REVEAL"):
                self._hero_frac = cum / total
            cum += act["duration_s"]
        if self._hero_frac is None and self._act_fracs:
            self._hero_frac = self._act_fracs[-1][0]
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self._act_fracs:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w = self.width()
        mid = self.height() / 2
        for frac, _name in self._act_fracs:
            x = frac * w
            pen = QtGui.QPen(QtGui.QColor(_V2["violet"]), 1.5)
            painter.setPen(pen)
            painter.drawLine(QtCore.QPointF(x, mid - 6), QtCore.QPointF(x, mid + 6))
        if self._hero_frac is not None:
            x = self._hero_frac * w
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(_V2["amber"]))
            painter.drawPolygon(QtGui.QPolygonF([
                QtCore.QPointF(x, mid - 7), QtCore.QPointF(x - 4, mid - 12),
                QtCore.QPointF(x + 4, mid - 12),
            ]))

class StoryboardStrip(QtWidgets.QWidget):
    """Docked act strip: ESTABLISH / EVOLVE / REVEAL cards. Clicking an act
    emits its start fraction so the video can seek there (design v2 §6)."""

    act_seek_requested = QtCore.pyqtSignal(float)

    _ACT_COLORS = {"ESTABLISH": _V2["cyan"], "EVOLVE": _V2["emerald"],
                   "REVEAL": _V2["amber"]}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = "kk"
        self._storyboard = None
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._empty = QtWidgets.QLabel(_SIM_COPY[self._language]["no_storyboard"])
        self._empty.setStyleSheet(f"color: {_V2['tx3']}; font-size: 11px;")
        self._layout.addWidget(self._empty)

    def set_storyboard(self, storyboard: dict | None) -> None:
        self._storyboard = storyboard
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        acts = _storyboard_acts(storyboard)
        if not acts:
            self._empty = QtWidgets.QLabel(_SIM_COPY[self._language]["no_storyboard"])
            self._empty.setStyleSheet(f"color: {_V2['tx3']}; font-size: 11px;")
            self._layout.addWidget(self._empty)
            return
        total = sum(a["duration_s"] for a in acts) or 1.0
        cum = 0.0
        for act in acts:
            frac = cum / total
            cum += act["duration_s"]
            self._layout.addWidget(self._make_card(act, frac), 1)

    def set_language(self, language: str) -> None:
        self._language = language if language in _SIM_COPY else "kk"
        self.set_storyboard(self._storyboard)

    def _make_card(self, act: dict, frac: float) -> QtWidgets.QWidget:
        name = act["name"].upper()
        color = self._ACT_COLORS.get(name.split()[0] if name else "", _V2["violet"])
        card = QtWidgets.QFrame()
        card.setObjectName("ActCard")
        card.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(
            f"QFrame#ActCard {{ background: {_V2['panel2']}; border: 1px solid {_V2['line']}; "
            f"border-left: 3px solid {color}; border-radius: 8px; }}"
            f"QFrame#ActCard:hover {{ background: {_V2['elev']}; }}"
        )
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(3)
        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        label = QtWidgets.QLabel(act["name"])
        label.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: 700; "
            "letter-spacing: 0.8px; background: transparent; border: none;"
        )
        head.addWidget(label)
        head.addStretch()
        dur = QtWidgets.QLabel(f"{act['duration_s']:g}s")
        dur.setStyleSheet(
            f"color: {_V2['tx3']}; font-size: 10px; font-family: 'Cascadia Code', "
            "monospace; background: transparent; border: none;"
        )
        head.addWidget(dur)
        lay.addLayout(head)
        if act["narration"]:
            script = QtWidgets.QLabel(act["narration"])
            script.setWordWrap(True)
            script.setStyleSheet(
                f"color: {_V2['tx2']}; font-size: 11px; font-style: italic; "
                "background: transparent; border: none;"
            )
            lay.addWidget(script)
        card.mousePressEvent = lambda e, f=frac: self.act_seek_requested.emit(f)
        return card

class CritiqueBadge(QtWidgets.QFrame):
    """Verdict + 0–10 score + expandable issues (design v2 §4/§6)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = "kk"
        self._critique: dict | None = None
        self.setObjectName("CritiqueBadge")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(4)

        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self._icon = QtWidgets.QLabel()
        self._icon.setFixedSize(16, 16)
        head.addWidget(self._icon)
        self._verdict = QtWidgets.QLabel("")
        self._verdict.setStyleSheet(
            f"color: {_V2['tx']}; font-size: 12px; font-weight: 600; "
            "background: transparent; border: none;"
        )
        head.addWidget(self._verdict)
        self._score = QtWidgets.QLabel("")
        self._score.setStyleSheet(
            f"color: {_V2['tx2']}; font-size: 11px; font-family: 'Cascadia Code', "
            "monospace; background: transparent; border: none;"
        )
        head.addWidget(self._score)
        head.addStretch()
        self._toggle = QtWidgets.QPushButton(_SIM_COPY[self._language]["issues"])
        self._toggle.setObjectName("GhostButton")
        self._toggle.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self._toggle_issues)
        head.addWidget(self._toggle)
        lay.addLayout(head)

        self._issues = QtWidgets.QLabel("")
        self._issues.setWordWrap(True)
        self._issues.setStyleSheet(
            f"color: {_V2['tx2']}; font-size: 11px; padding: 2px 0 2px 24px; "
            "background: transparent; border: none;"
        )
        self._issues.hide()
        lay.addWidget(self._issues)
        self.hide()

    def _toggle_issues(self) -> None:
        self._issues.setVisible(not self._issues.isVisible())

    def set_language(self, language: str) -> None:
        self._language = language if language in _SIM_COPY else "kk"
        self._toggle.setText(_SIM_COPY[self._language]["issues"])
        if self._critique is not None:
            self.set_critique(self._critique)

    def set_critique(self, critique: dict | None) -> None:
        self._critique = critique
        if not critique:
            self.hide()
            return
        verdict = critique["verdict"]
        color = {"ship": _V2["emerald"], "revise": _V2["amber"]}.get(verdict, _V2["tx3"])
        icon_name = {"ship": "check-circle", "revise": "alert-circle"}.get(verdict, "info")
        self._icon.setPixmap(icons.icon_pixmap(icon_name, 15, color))
        self._verdict.setText(
            _SIM_COPY[self._language]["ready"] if verdict == "ship"
            else _SIM_COPY[self._language]["revise"] if verdict == "revise"
            else verdict.title()
        )
        self._score.setText(f"{critique['score']:.1f}/10")
        issues = critique.get("issues") or []
        if issues:
            self._issues.setText("• " + "\r\n• ".join(issues))
            self._toggle.show()
        else:
            self._toggle.hide()
        self.setStyleSheet(
            f"QFrame#CritiqueBadge {{ background: {_V2['panel2']}; "
            f"border: 1px solid {color}; border-radius: 8px; }}"
        )
        self.show()

class _ManimHighlighter(QtGui.QSyntaxHighlighter):
    """Manim-aware syntax accents (design v2 syntax map)."""

    _KEYWORDS = {
        "import", "from", "as", "def", "class", "return", "for", "while", "if",
        "elif", "else", "with", "in", "and", "or", "not", "lambda", "self",
        "True", "False", "None", "yield", "pass", "break", "continue",
    }
    _PLAY_VERBS = {
        "Create", "Write", "Transform", "ReplacementTransform", "FadeIn",
        "FadeOut", "GrowFromCenter", "GrowArrow", "DrawBorderThenFill",
        "Indicate", "Flash", "Circumscribe", "MoveAlongPath", "Rotate",
        "Rotating", "TransformMatchingTex", "TransformMatchingShapes",
        "ApplyWave", "SpiralIn", "Wiggle", "FocusOn", "ShowPassingFlash",
        "always_redraw", "add_updater",
    }

    def __init__(self, document) -> None:
        super().__init__(document)
        import re as _re
        self._re = _re
        self._fmt = {}
        for key, color in (("kw", _V2["violet"]), ("cls", _V2["cyan"]),
                           ("verb", _V2["emerald"]), ("lit", _V2["amber"]),
                           ("cmt", _V2["tx3"])):
            f = QtGui.QTextCharFormat()
            f.setForeground(QtGui.QColor(color))
            self._fmt[key] = f
        self._fmt["cls"].setFontWeight(QtGui.QFont.Weight.DemiBold)

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        for m in self._re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text):
            word = m.group()
            if word in self._KEYWORDS:
                self.setFormat(m.start(), len(word), self._fmt["kw"])
            elif word in self._PLAY_VERBS:
                self.setFormat(m.start(), len(word), self._fmt["verb"])
            elif word[:1].isupper():
                self.setFormat(m.start(), len(word), self._fmt["cls"])
        for m in self._re.finditer(r"\b\d+\.?\d*\b", text):
            self.setFormat(m.start(), len(m.group()), self._fmt["lit"])
        for m in self._re.finditer(r"(['\"]).*?\1", text):
            self.setFormat(m.start(), len(m.group()), self._fmt["lit"])
        h = text.find("#")
        if h >= 0:
            self.setFormat(h, len(text) - h, self._fmt["cmt"])

class _LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor: "CodeArtifactView") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        self._editor.line_number_area_paint(event)

class CodeArtifactView(QtWidgets.QPlainTextEdit):
    """Editor pane with line numbers + Manim syntax accents (design v2 §6)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setObjectName("CodeArtifact")
        self.setStyleSheet(
            f"QPlainTextEdit#CodeArtifact {{ background: {_V2['stage']}; "
            f"border: 1px solid {_V2['line']}; border-radius: 8px; "
            f"color: {_V2['tx']}; font-family: 'Cascadia Code', monospace; "
            "font-size: 12px; padding: 4px; }"
        )
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self._numbers = _LineNumberArea(self)
        self._highlighter = _ManimHighlighter(self.document())
        self.blockCountChanged.connect(lambda _: self._update_margins())
        self.updateRequest.connect(self._update_numbers)
        self._update_margins()

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margins(self) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_numbers(self, rect, dy) -> None:
        if dy:
            self._numbers.scroll(0, dy)
        else:
            self._numbers.update(0, rect.y(), self._numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margins()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._numbers.setGeometry(
            QtCore.QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint(self, event) -> None:
        painter = QtGui.QPainter(self._numbers)
        painter.fillRect(event.rect(), QtGui.QColor(_V2["panel"]))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        painter.setFont(self.font())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QtGui.QColor(_V2["tx3"]))
                painter.drawText(
                    0, int(top), self._numbers.width() - 6, self.fontMetrics().height(),
                    QtCore.Qt.AlignmentFlag.AlignRight, str(num + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            num += 1

class _DiagnosticsDrawer(QtWidgets.QFrame):
    """Collapsible mono diagnostics with severity dots (design v2 §4)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = "kk"
        self._diagnostics: list[str] = []
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(4)
        self._toggle = QtWidgets.QPushButton(
            f"▸ {_SIM_COPY[self._language]['diagnostics']}"
        )
        self._toggle.setObjectName("GhostButton")
        self._toggle.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self._toggle_body)
        lay.addWidget(self._toggle, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self._body = QtWidgets.QPlainTextEdit()
        self._body.setReadOnly(True)
        self._body.setMaximumHeight(120)
        self._body.setStyleSheet(
            f"QPlainTextEdit {{ background: {_V2['panel']}; border: 1px solid {_V2['line']}; "
            f"border-radius: 6px; color: {_V2['tx2']}; font-family: 'Cascadia Code', "
            "monospace; font-size: 11px; }"
        )
        self._body.hide()
        lay.addWidget(self._body)
        self.hide()

    def _severity(self, line: str) -> str:
        low = line.lower()
        if any(k in low for k in ("fail", "error", "timed out", "unsafe")):
            return "●"  # rose
        if any(k in low for k in ("repair", "revis", "retry", "revise", "warn")):
            return "●"  # amber
        return "●"

    def set_diagnostics(self, diagnostics: list[str]) -> None:
        self._diagnostics = list(diagnostics)
        if not diagnostics:
            self.hide()
            return
        rows = []
        for d in diagnostics:
            low = d.lower()
            if any(k in low for k in ("fail", "error", "timed out", "unsafe")):
                dot = _V2["rose"]
            elif any(k in low for k in ("repair", "revis", "retry", "warn")):
                dot = _V2["amber"]
            else:
                dot = _V2["tx3"]
            rows.append((dot, d))
        # QPlainTextEdit can't color per-line easily; prefix with a unicode dot
        # and rely on the drawer being mono. Keep it simple + legible.
        self._body.setPlainText("\r\n".join(f"• {d}" for _c, d in rows))
        self._toggle.setText(
            f"▸ {_SIM_COPY[self._language]['diagnostics']} ({len(diagnostics)})"
        )
        self.show()

    def set_language(self, language: str) -> None:
        self._language = language if language in _SIM_COPY else "kk"
        if self._diagnostics:
            self.set_diagnostics(self._diagnostics)
        else:
            self._toggle.setText(f"▸ {_SIM_COPY[self._language]['diagnostics']}")

    def _toggle_body(self) -> None:
        vis = not self._body.isVisible()
        self._body.setVisible(vis)
        self._toggle.setText(
            self._toggle.text().replace("▸", "▾") if vis
            else self._toggle.text().replace("▾", "▸")
        )
