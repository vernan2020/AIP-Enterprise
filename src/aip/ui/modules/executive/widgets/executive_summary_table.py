from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


class ExecutiveSummaryTable(QTableWidget):
    def __init__(self, rows: tuple[str, ...]) -> None:
        super().__init__(len(rows), 1)
        self.setHorizontalHeaderLabels(["Value"])
        for index, row in enumerate(rows):
            self.setItem(index, 0, QTableWidgetItem(row))
