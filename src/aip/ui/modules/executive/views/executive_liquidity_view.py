from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExecutiveLiquidityView(QWidget):
    def __init__(self, liquidity: tuple[str, ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        for item in liquidity:
            layout.addWidget(QLabel(item))
