"""Controls for adjusting parameters in the active physics simulation."""

from __future__ import annotations

from aetherlab.ui.qt_compat import QtCore, QtWidgets, require_qt

require_qt()

class ParameterDock(QtWidgets.QWidget):
    """Collapsible horizontal strip of parameter sliders with spin boxes and reset (#7, #8)."""

    parameter_changed = QtCore.pyqtSignal(str, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        # (slider, spinbox, value_label, original_value)
        self._sliders: dict[str, tuple[QtWidgets.QSlider, QtWidgets.QDoubleSpinBox, QtWidgets.QLabel, float]] = {}
        self._spans: dict[str, float] = {}
        self._collapsed = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(4)

        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._toggle_btn = QtWidgets.QPushButton("\u25bc  Parameters")
        self._toggle_btn.setStyleSheet(
            "background: transparent; border: none; color: #65758A; "
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
            "letter-spacing: 1px; padding: 4px 0;"
        )
        self._toggle_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self._toggle_btn)
        header_layout.addStretch()
        layout.addWidget(header)

        self._container = QtWidgets.QWidget()
        self._container_layout = QtWidgets.QFormLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(8)
        layout.addWidget(self._container)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._container.setVisible(not self._collapsed)
        self._toggle_btn.setText(
            "\u25b6  Parameters" if self._collapsed else "\u25bc  Parameters"
        )

    def expand(self) -> None:
        if self._collapsed:
            self._toggle()

    _SLIDER_TICKS = 1000

    def _span_for(self, value: float) -> float:
        return max(abs(float(value)) * 2.0, 1.0)

    def set_variables(self, variables: dict[str, float]) -> None:
        self._clear()
        for name, value in sorted(variables.items()):
            value = float(value)
            span = self._span_for(value)
            self._spans[name] = span

            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(0, self._SLIDER_TICKS)
            slider.setValue(self._value_to_tick(value, span))
            slider.valueChanged.connect(
                lambda raw, key=name: self._on_slider_change(key, raw)
            )

            # Spin box for precise numeric input (#7) — allow negative values
            spinbox = QtWidgets.QDoubleSpinBox()
            spinbox.setRange(-span, span)
            spinbox.setValue(value)
            spinbox.setDecimals(4)
            spinbox.setSingleStep(span / 100)
            spinbox.setFixedWidth(90)
            spinbox.setStyleSheet(
                "QDoubleSpinBox { background-color: #FFFFFF; border: 1px solid #D8E1EC; "
                "border-radius: 4px; color: #486A91; padding: 2px 4px; "
                "font-family: 'Cascadia Code', monospace; font-size: 11px; }"
                "QDoubleSpinBox:focus { border-color: #486A91; }"
            )
            spinbox.valueChanged.connect(
                lambda val, key=name: self._on_spinbox_change(key, val)
            )

            # Reset button (#8)
            reset_btn = QtWidgets.QPushButton("\u21ba")
            reset_btn.setFixedWidth(28)
            reset_btn.setToolTip(f"Reset {name} to {value:g}")
            reset_btn.setStyleSheet(
                "background: transparent; border: 1px solid #A5B6CB; border-radius: 4px; "
                "color: #65758A; font-size: 14px; padding: 2px;"
            )
            reset_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            reset_btn.clicked.connect(
                lambda checked, key=name, orig=value: self._reset_param(key, orig)
            )

            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(slider, 1)
            row_layout.addWidget(spinbox)
            row_layout.addWidget(reset_btn)

            self._sliders[name] = (slider, spinbox, QtWidgets.QLabel(), value)
            self._container_layout.addRow(self._symbol_label(name), row_widget)

    def _symbol_label(self, name: str) -> QtWidgets.QWidget:
        """Typeset parameter symbol (design v2 §5.5), text fallback."""
        from aetherlab.services.mathtext import render_param_symbol

        pixmap = render_param_symbol(name, px_size=13, color="#18283D")
        label = QtWidgets.QLabel()
        if pixmap is not None:
            label.setPixmap(pixmap)
        else:
            label.setText(name)
        label.setToolTip(name)
        label.setMinimumWidth(34)
        label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        return label

    def _on_slider_change(self, name: str, raw: int) -> None:
        span = self._spans.get(name, 1.0)
        value = (raw / self._SLIDER_TICKS) * 2 * span - span  # map [0,1000] to [-span, +span]
        if name in self._sliders:
            _, spinbox, _, _ = self._sliders[name]
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
        self.parameter_changed.emit(name, value)

    def _on_spinbox_change(self, name: str, value: float) -> None:
        if name in self._sliders:
            slider, _, _, _ = self._sliders[name]
            span = self._spans.get(name, self._span_for(value))
            if abs(value) > span:
                span = self._span_for(value)
                self._spans[name] = span
                spinbox = self._sliders[name][1]
                spinbox.setRange(-span, span)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(value, span))
            slider.blockSignals(False)
        self.parameter_changed.emit(name, value)

    def _reset_param(self, name: str, original_value: float) -> None:
        if name in self._sliders:
            slider, spinbox, _, _ = self._sliders[name]
            span = self._spans.get(name, self._span_for(original_value))
            spinbox.blockSignals(True)
            spinbox.setValue(original_value)
            spinbox.blockSignals(False)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(original_value, span))
            slider.blockSignals(False)
            self.parameter_changed.emit(name, original_value)

    def _value_to_tick(self, value: float, span: float) -> int:
        if span <= 0:
            return self._SLIDER_TICKS // 2  # center for zero span
        return max(0, min(self._SLIDER_TICKS, int((value + span) / (2 * span) * self._SLIDER_TICKS)))

    def update_variable(self, name: str, value: float) -> None:
        if name in self._sliders:
            slider, spinbox, _, _ = self._sliders[name]
            span = self._spans.get(name, self._span_for(value))
            if abs(value) > span:
                span = self._span_for(value)
                self._spans[name] = span
                spinbox.setRange(-span, span)  # keep negative range (matches set_variables)
            slider.blockSignals(True)
            slider.setValue(self._value_to_tick(value, span))
            slider.blockSignals(False)
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)

    def _clear(self) -> None:
        while self._container_layout.rowCount():
            self._container_layout.removeRow(0)
        self._sliders.clear()
        self._spans.clear()
