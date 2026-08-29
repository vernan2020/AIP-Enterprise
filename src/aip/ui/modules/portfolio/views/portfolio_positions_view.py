from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class PortfolioPositionsView(QWidget):
    def __init__(self, rows: tuple[object, ...] | None = None) -> None:
        super().__init__()
        self._table = QTableWidget()
        self._table.setColumnCount(14)
        self._table.setHorizontalHeaderLabels(
            [
                "ISIN",
                "Issuer",
                "Instrument",
                "Currency",
                "Nominal",
                "Market Value",
                "Book Value",
                "Yield",
                "Modified Duration",
                "Classification",
                "HQLA Status",
                "MIL Status",
                "Recommendation",
            ]
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        self.bind_rows(rows or ())

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
                self._table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
