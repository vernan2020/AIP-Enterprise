from __future__ import annotations

from PySide6.QtWidgets import QLabel


class TreasuryStatusBadge(QLabel):
    def __init__(self, text: str = "Ready") -> None:
        super().__init__(text)
        self.setStyleSheet("border: 1px solid #4b5563; padding: 4px; border-radius: 4px;")
