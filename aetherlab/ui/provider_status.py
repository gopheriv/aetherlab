"""Provider identity and shadow/model warnings for the Settings dialog."""

from __future__ import annotations

from aetherlab.core.settings import AppSettings
from aetherlab.services.model_policy import active_provider_name, model_codegen_warning
from aetherlab.ui.qt_compat import QtWidgets


class ProviderStatusPanel(QtWidgets.QWidget):
    """Read-only active provider summary; never displays credential values."""

    def __init__(
        self, settings: AppSettings, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(3)

        self.active_label = QtWidgets.QLabel()
        self.active_label.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 600;")
        self.active_label.setWordWrap(True)
        layout.addWidget(self.active_label)

        self.source_label = QtWidgets.QLabel()
        self.source_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)

        self.warning_label = QtWidgets.QLabel()
        self.warning_label.setStyleSheet("color: #F59E0B; font-size: 11px;")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)
        self.set_model(settings.llm_model)

    def set_model(self, model: str) -> None:
        model = str(model or "offline").strip() or "offline"
        self.active_label.setText(
            f"Active: {active_provider_name(self._settings)} · {model}"
        )
        self.source_label.setText(
            f"API key source: {getattr(self._settings, 'api_key_source', 'none')}"
        )
        warnings = [
            str(getattr(self._settings, "provider_warning", "") or "").strip(),
            model_codegen_warning(model, self._settings.llm_timeout_seconds),
        ]
        message = "\n".join(item for item in warnings if item)
        self.warning_label.setText(message)
        self.warning_label.setVisible(bool(message))
