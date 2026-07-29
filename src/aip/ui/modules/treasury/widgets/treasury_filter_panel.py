from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLineEdit, QWidget


class TreasuryFilterPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.currency = QLineEdit()
        self.issuer = QLineEdit()
        self.scenario = QLineEdit()
        self.search = QLineEdit()
        layout.addRow("Currency", self.currency)
        layout.addRow("Issuer", self.issuer)
        layout.addRow("Scenario", self.scenario)
        layout.addRow("Search", self.search)
