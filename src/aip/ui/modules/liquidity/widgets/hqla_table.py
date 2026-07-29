from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


class HQLATable(QTableWidget):
    def __init__(self, rows: tuple[object, ...] = ()) -> None:
        super().__init__(len(rows), 3)
        self.setHorizontalHeaderLabels(["Label", "Value", "Policy"])
        for index, row in enumerate(rows):
            label = getattr(row, "label", "")
            value = getattr(row, "value", "")
            policy_reference = getattr(row, "policy_reference", "")
            self.setItem(index, 0, QTableWidgetItem(str(label)))
            self.setItem(index, 1, QTableWidgetItem(str(value)))
            self.setItem(index, 2, QTableWidgetItem(str(policy_reference)))
