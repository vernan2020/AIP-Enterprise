from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExecutiveTrendChart(QWidget):
    def __init__(self, label: str, points: tuple[str, ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(label))
        layout.addWidget(QLabel(" | ".join(points)))
