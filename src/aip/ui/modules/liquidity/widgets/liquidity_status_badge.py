from __future__ import annotations

from PySide6.QtWidgets import QLabel


class LiquidityStatusBadge(QLabel):
    def __init__(self, text: str = "Ready") -> None:
        super().__init__(text)
