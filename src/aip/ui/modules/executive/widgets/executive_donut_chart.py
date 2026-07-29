from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExecutiveDonutChart(QWidget):
    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(label))
        layout.addWidget(QLabel(value))
