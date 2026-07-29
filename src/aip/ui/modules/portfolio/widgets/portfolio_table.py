from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


class PortfolioTable(QTableWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setColumnCount(13)
        self.setHorizontalHeaderLabels([
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
        ])
        self.setSortingEnabled(True)

    def bind_rows(self, rows: tuple[object, ...]) -> None:
        self.setRowCount(len(rows))
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
                self.setItem(row_index, column_index, QTableWidgetItem(str(value)))
