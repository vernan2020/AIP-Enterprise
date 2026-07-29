from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PortfolioDetailsView(QWidget):
    def __init__(self, selected_row: object | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Instrument"))
        layout.addWidget(QLabel(getattr(selected_row, "instrument", "No selection")))
        layout.addWidget(QLabel("Pricing Summary"))
        layout.addWidget(QLabel("Application-layer summary only"))
        layout.addWidget(QLabel("Policy References"))
        layout.addWidget(QLabel("N/A"))
