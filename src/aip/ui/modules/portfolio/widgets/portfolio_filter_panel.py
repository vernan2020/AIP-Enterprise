from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QWidget


class PortfolioFilterPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.issuer = QComboBox()
        self.issuer.addItems(["All", "Acme Bank"])
        self.currency = QComboBox()
        self.currency.addItems(["All", "USD"])
        self.instrument = QLineEdit()
        self.classification = QLineEdit()
        self.search = QLineEdit()
        layout.addRow("Issuer", self.issuer)
        layout.addRow("Currency", self.currency)
        layout.addRow("Instrument", self.instrument)
        layout.addRow("Classification", self.classification)
        layout.addRow("Search", self.search)
