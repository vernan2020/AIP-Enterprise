from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class RelativeValueView(QWidget):
    def __init__(self, rows: tuple[object, ...] | None = None) -> None:
        super().__init__()
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Issuer",
            "Instrument",
            "Recommendation",
            "Confidence",
            "Spread",
            "Z-Spread",
            "Benchmark Spread",
        ])
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        self.bind_rows(rows or ())

    def bind_rows(self, rows: tuple[object, ...]) -> None:
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                getattr(row, "issuer", ""),
                getattr(row, "instrument", ""),
                getattr(row, "recommendation", ""),
                getattr(row, "confidence", ""),
                getattr(row, "spread", ""),
                getattr(row, "z_spread", ""),
                getattr(row, "benchmark_spread", ""),
            ]
            for column_index, value in enumerate(values):
                self._table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
