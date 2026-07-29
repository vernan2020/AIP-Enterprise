from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MarketMetricCard(QWidget):
    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        layout.addWidget(QLabel(value))

    def text(self) -> str:
        return self.findChildren(QLabel)[0].text()
