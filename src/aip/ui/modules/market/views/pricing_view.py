from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget


class PricingView(QWidget):
    def __init__(self, row: object | None = None) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self._fields = {
            "Market Value": QLabel(getattr(row, "market_value", "")),
            "Book Value": QLabel(getattr(row, "book_value", "")),
            "Clean Price": QLabel(getattr(row, "clean_price", "")),
            "Dirty Price": QLabel(getattr(row, "dirty_price", "")),
            "Accrued Interest": QLabel(getattr(row, "accrued_interest", "")),
            "Duration": QLabel(getattr(row, "duration", "")),
            "Modified Duration": QLabel(getattr(row, "modified_duration", "")),
            "Convexity": QLabel(getattr(row, "convexity", "")),
            "DV01": QLabel(getattr(row, "dv01", "")),
            "PVBP": QLabel(getattr(row, "pvbp", "")),
        }
        for title, widget in self._fields.items():
            layout.addRow(title, widget)
