"""Compact, data-driven filters for the real institutional portfolio."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class PortfolioFilterPanel(QWidget):
    filters_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("portfolioFilterPanel")
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(7)
        self.setStyleSheet(
            "QWidget#portfolioFilterPanel {background:#F5FAFD;"
            "border:1px solid #CDDFEB; border-radius:10px;}"
            "QWidget#portfolioFilterPanel QLabel {color:#36566D; font-size:9pt;"
            "font-weight:600; border:none;}"
            "QWidget#portfolioFilterPanel QComboBox, "
            "QWidget#portfolioFilterPanel QLineEdit {background:#FFFFFF;"
            "border:1px solid #C9DCE8; border-radius:6px; padding:5px 8px;"
            "min-height:23px;}"
        )
        self.issuer = QComboBox()
        self.issuer.addItem("Todos")
        self.currency = QComboBox()
        self.currency.addItem("Todas")
        self.instrument = QLineEdit()
        self.instrument.setPlaceholderText("Tipo o serie...")
        self.classification = QLineEdit()
        self.classification.setPlaceholderText("Clasificación...")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar ISIN, emisor, título...")
        self.search.setClearButtonEnabled(True)
        self.reset_button = QPushButton("Limpiar")
        self.reset_button.setToolTip("Restablecer filtros del portafolio")
        self.reset_button.setMinimumHeight(32)
        fields = (
            ("Emisor", self.issuer),
            ("Moneda", self.currency),
            ("Instrumento", self.instrument),
            ("Clasificación", self.classification),
            ("Búsqueda", self.search),
        )
        for index, (label, widget) in enumerate(fields):
            column = index % 3
            row = (index // 3) * 2
            heading = QLabel(label)
            layout.addWidget(heading, row, column)
            layout.addWidget(widget, row + 1, column)
            widget.setAccessibleName(f"Filtro: {label}")
            layout.setColumnStretch(column, 1)
        layout.addWidget(self.reset_button, 3, 2)
        for combo in (self.issuer, self.currency):
            combo.currentIndexChanged.connect(self.filters_changed.emit)
        for edit in (self.instrument, self.classification, self.search):
            edit.textChanged.connect(self.filters_changed.emit)
        self.reset_button.clicked.connect(self.reset_filters)

    def set_rows(self, rows: tuple[object, ...]) -> None:
        """Replace obsolete sample options with actual values from the presenter."""
        previous_issuer = self.issuer.currentText()
        previous_currency = self.currency.currentText()
        for combo, key, default, previous in (
            (self.issuer, "issuer", "Todos", previous_issuer),
            (self.currency, "currency", "Todas", previous_currency),
        ):
            combo.blockSignals(True)
            options = sorted(
                {
                    str(getattr(row, key, "")).strip()
                    for row in rows
                    if str(getattr(row, key, "")).strip()
                },
                key=str.casefold,
            )
            combo.clear()
            combo.addItems((default, *options))
            index = combo.findText(previous)
            combo.setCurrentIndex(max(0, index))
            combo.blockSignals(False)
        self.filters_changed.emit()

    def reset_filters(self) -> None:
        self.issuer.setCurrentIndex(0)
        self.currency.setCurrentIndex(0)
        for edit in (self.instrument, self.classification, self.search):
            edit.clear()
        self.filters_changed.emit()

    def matches(self, row: object) -> bool:
        issuer = self.issuer.currentText()
        currency = self.currency.currentText()
        if issuer != "Todos" and str(getattr(row, "issuer", "")) != issuer:
            return False
        if currency != "Todas" and str(getattr(row, "currency", "")) != currency:
            return False
        for edit, name in (
            (self.instrument, "instrument"),
            (self.classification, "classification"),
        ):
            if edit.text().strip().casefold() not in str(getattr(row, name, "")).casefold():
                return False
        term = self.search.text().strip().casefold()
        return not term or any(
            term in str(getattr(row, field, "")).casefold()
            for field in ("isin", "issuer", "instrument", "classification", "currency")
        )
