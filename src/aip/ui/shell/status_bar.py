from __future__ import annotations

from PySide6.QtWidgets import QStatusBar


class StatusBar(QStatusBar):
    """Status bar used by the desktop shell."""

    def __init__(self) -> None:
        super().__init__()
        self.setVisible(False)

    def set_message(self, message: str) -> None:
        self.showMessage(message)
        self.setVisible(True)
