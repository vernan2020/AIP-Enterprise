from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExecutiveMetricCard(QWidget):
    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        layout.addWidget(QLabel(value))
