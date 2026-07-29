from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SpreadTable(QWidget):
    """Minimal spread table widget for the market workspace."""

    def __init__(self, title: str = "Spread") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
