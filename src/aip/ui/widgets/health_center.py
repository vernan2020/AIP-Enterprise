from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class HealthCenterWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Component", "State", "Uptime", "Last Execution", "Response Time", "Warnings/Errors"]
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        self._build_rows()

    def _build_rows(self) -> None:
        self._table.setRowCount(len(self.component_rows()))
        for row_index, row in enumerate(self.component_rows()):
            for column_index, value in enumerate(row):
                self._table.setItem(row_index, column_index, QTableWidgetItem(str(value)))

    def component_rows(self) -> list[tuple[str, str, str, str, str, str]]:
        return [
            ("Application", "Healthy", "00:10:00", "now", "12ms", "0/0"),
            ("Integration Hub", "Healthy", "00:12:00", "now", "15ms", "0/0"),
            ("Scheduler", "Healthy", "00:08:00", "now", "8ms", "0/0"),
            ("Notifications", "Healthy", "00:09:00", "now", "6ms", "0/0"),
            ("Observability", "Healthy", "00:07:00", "now", "9ms", "0/0"),
            ("Reporting", "Healthy", "00:06:00", "now", "7ms", "0/0"),
            ("SQL", "Healthy", "00:05:00", "now", "11ms", "0/0"),
            ("Folder Watch", "Healthy", "00:04:00", "now", "5ms", "0/0"),
            ("BCCR", "Healthy", "00:03:00", "now", "4ms", "0/0"),
            ("Data Quality", "Healthy", "00:02:00", "now", "3ms", "0/0"),
        ]
