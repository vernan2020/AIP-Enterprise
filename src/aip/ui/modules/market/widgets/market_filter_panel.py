from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QWidget


class MarketFilterPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.issuer = QComboBox()
        self.issuer.addItems(["All", "Acme Bank"])
        self.currency = QComboBox()
        self.currency.addItems(["All", "USD"])
        self.instrument = QLineEdit()
        self.recommendation = QLineEdit()
        self.confidence = QLineEdit()
        self.search = QLineEdit()
        layout.addRow("Issuer", self.issuer)
        layout.addRow("Currency", self.currency)
        layout.addRow("Instrument", self.instrument)
        layout.addRow("Recommendation", self.recommendation)
        layout.addRow("Confidence", self.confidence)
        layout.addRow("Search", self.search)
