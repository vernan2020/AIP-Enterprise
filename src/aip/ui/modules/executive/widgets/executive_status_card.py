from __future__ import annotations

from PySide6.QtWidgets import QLabel

from aip.ui.services.display_localization import translate_status


class ExecutiveStatusCard(QLabel):
    def __init__(self, text: str = "LISTO") -> None:
        super().__init__(translate_status(text))
        self.setStyleSheet(
            "background:#F5FAFD; color:#31566F; border:1px solid #CFE4F2; "
            "padding:5px 9px; border-radius:6px; font-size:9px; font-weight:700;"
        )

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(translate_status(text))
