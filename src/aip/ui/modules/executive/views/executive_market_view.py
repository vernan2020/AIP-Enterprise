from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExecutiveMarketView(QWidget):
    def __init__(self, market: tuple[str, ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        for item in market:
            layout.addWidget(QLabel(item))
