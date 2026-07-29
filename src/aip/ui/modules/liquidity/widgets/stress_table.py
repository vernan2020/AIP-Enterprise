from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


class StressTable(QTableWidget):
    def __init__(self, rows: tuple[object, ...] = ()) -> None:
        super().__init__(len(rows), 2)
        self.setHorizontalHeaderLabels(["Label", "Value"])
        for index, row in enumerate(rows):
            label = getattr(row, "label", "")
            value = getattr(row, "value", "")
            self.setItem(index, 0, QTableWidgetItem(str(label)))
            self.setItem(index, 1, QTableWidgetItem(str(value)))
