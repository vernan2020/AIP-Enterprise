from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget


class PortfolioPropertyGrid(QWidget):
    def __init__(self, row: object | None = None) -> None:
        super().__init__()
        layout = QFormLayout(self)
        layout.addRow("ISIN", QLabel(getattr(row, "isin", "")))
        layout.addRow("Issuer", QLabel(getattr(row, "issuer", "")))
        layout.addRow("Instrument", QLabel(getattr(row, "instrument", "")))
        layout.addRow("Currency", QLabel(getattr(row, "currency", "")))
        layout.addRow("Recommendation", QLabel(getattr(row, "recommendation", "")))
