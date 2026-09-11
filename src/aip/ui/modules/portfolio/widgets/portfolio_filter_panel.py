from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QWidget


class PortfolioFilterPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.issuer = QComboBox()
        self.issuer.addItems(["Todos", "Banco Acme"])
        self.currency = QComboBox()
        self.currency.addItems(["Todas", "USD"])
        self.instrument = QLineEdit()
        self.classification = QLineEdit()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar posición...")
        layout.addRow("Emisor", self.issuer)
        layout.addRow("Moneda", self.currency)
        layout.addRow("Instrumento", self.instrument)
        layout.addRow("Clasificación", self.classification)
        layout.addRow("Buscar", self.search)
