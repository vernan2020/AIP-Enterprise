from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class PortfolioPositionsView(QWidget):
    _DISPLAY_TRANSLATIONS = {
        "eligible": "Elegible",
        "not eligible": "No elegible",
        "ineligible": "No elegible",
        "available": "Disponible",
        "unavailable": "No disponible",
        "buy": "Comprar",
        "sell": "Vender",
        "hold": "Mantener",
        "government": "Gobierno",
        "govt": "Gobierno",
        "bank": "Banco",
        "private": "Privado",
    }

    def __init__(self, rows: tuple[object, ...] | None = None) -> None:
        super().__init__()
        self._table = QTableWidget()
        self._table.setColumnCount(13)
        self._table.setHorizontalHeaderLabels(
            [
                "ISIN",
                "Emisor",
                "Instrumento",
                "Moneda",
                "Nominal",
                "Valor de Mercado",
                "Valor en Libros",
                "TIR",
                "Duración Modificada",
                "Clasificación",
                "Estado HQLA",
                "Estado MIL",
                "Recomendación",
            ]
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        self.bind_rows(rows or ())

    @classmethod
    def _display(cls, value: object) -> str:
        text = str(value)
        return cls._DISPLAY_TRANSLATIONS.get(text.strip().casefold(), text)

    def bind_rows(self, rows: tuple[object, ...]) -> None:
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                getattr(row, "isin", ""),
                getattr(row, "issuer", ""),
                getattr(row, "instrument", ""),
                getattr(row, "currency", ""),
                getattr(row, "nominal", ""),
                getattr(row, "market_value", ""),
                getattr(row, "book_value", ""),
                getattr(row, "yield_value", ""),
                getattr(row, "modified_duration", ""),
                getattr(row, "classification", ""),
                getattr(row, "hqla_status", ""),
                getattr(row, "mil_status", ""),
                getattr(row, "recommendation", ""),
            ]
            for column_index, value in enumerate(values):
                self._table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(self._display(value)),
                )
