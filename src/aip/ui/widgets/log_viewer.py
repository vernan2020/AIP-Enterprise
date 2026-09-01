from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogViewerDialog(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Log Viewer")
        self._logs: list[dict[str, Any]] = []
        self._level_filter = QComboBox()
        self._level_filter.addItems(["ALL", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._component_filter = QComboBox()
        self._component_filter.addItems(["ALL", "ui", "scheduler", "observability"])
        self._execution_filter = QTextEdit()
        self._correlation_filter = QTextEdit()
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Level", "Component", "Execution", "Correlation", "Message"]
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Level", self._level_filter)
        form.addRow("Component", self._component_filter)
        form.addRow("Execution ID", self._execution_filter)
        form.addRow("Correlation ID", self._correlation_filter)
        layout.addLayout(form)
        export_button = QPushButton("Export")
        export_button.clicked.connect(lambda: self.export_logs("json"))
        layout.addWidget(export_button)
        layout.addWidget(self._table)

    def add_log(
        self, level: str, component: str, execution_id: str, correlation_id: str, message: str
    ) -> None:
        self._logs.append(
            {
                "level": level,
                "component": component,
                "execution_id": execution_id,
                "correlation_id": correlation_id,
                "message": message,
            }
        )
        self._refresh_table()

    def apply_filters(self, *, level: str | None = None) -> None:
        self._level_filter.setCurrentText(level or "ALL")
        self._refresh_table()

    def visible_log_count(self) -> int:
        return len(self._filtered_logs())

    def _filtered_logs(self) -> list[dict[str, Any]]:
        level = self._level_filter.currentText()
        component = self._component_filter.currentText()
        execution = self._execution_filter.toPlainText().strip()
        correlation = self._correlation_filter.toPlainText().strip()
        rows = self._logs
        if level != "ALL":
            rows = [row for row in rows if row["level"] == level]
        if component != "ALL":
            rows = [row for row in rows if row["component"] == component]
        if execution:
            rows = [row for row in rows if execution in row["execution_id"]]
        if correlation:
            rows = [row for row in rows if correlation in row["correlation_id"]]
        return rows

    def _refresh_table(self) -> None:
        rows = self._filtered_logs()
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, header in enumerate(
                ["level", "component", "execution_id", "correlation_id", "message"]
            ):
                self._table.setItem(row_index, column_index, QTableWidgetItem(str(row[header])))

    def export_logs(self, export_format: str) -> str:
        rows = self._filtered_logs()
        path = Path(f"/tmp/aip-logs.{export_format}")
        path.write_text(json.dumps(rows, indent=2))
        return str(path)
