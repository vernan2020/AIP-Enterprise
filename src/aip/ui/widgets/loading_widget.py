from __future__ import annotations

from PySide6.QtWidgets import QLabel


class LoadingWidget(QLabel):
    def __init__(self, text: str = "Cargando") -> None:
        super().__init__(text)
