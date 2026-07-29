from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget


class Toast(QWidget):
    def __init__(self, message: str) -> None:
        super().__init__()
        self._label = QLabel(message)
