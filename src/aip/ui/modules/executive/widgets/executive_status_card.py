from __future__ import annotations

from PySide6.QtWidgets import QLabel

from aip.ui.services.display_localization import translate_status


class ExecutiveStatusCard(QLabel):
    def __init__(self, text: str = "LISTO") -> None:
        super().__init__(translate_status(text))
        self.setStyleSheet("border: 1px solid #4b5563; padding: 4px; border-radius: 4px;")

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(translate_status(text))
