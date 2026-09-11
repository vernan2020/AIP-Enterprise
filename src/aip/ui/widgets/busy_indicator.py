from __future__ import annotations

from PySide6.QtWidgets import QLabel


class BusyIndicator(QLabel):
    def __init__(self, text: str = "Procesando") -> None:
        super().__init__(text)
