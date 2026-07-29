from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExecutivePortfolioView(QWidget):
    def __init__(self, portfolio: tuple[str, ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        for item in portfolio:
            layout.addWidget(QLabel(item))
