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
    """Visor de registros operativos con filtros de presentación en español."""

    _LEVEL_LABELS = (
        ("Todos", "ALL"),
        ("Información", "INFO"),
        ("Advertencia", "WARNING"),
        ("Error", "ERROR"),
        ("Crítico", "CRITICAL"),
    )
    _COMPONENT_LABELS = (
        ("Todos", "ALL"),
        ("Interfaz", "ui"),
        ("Programador", "scheduler"),
        ("Observabilidad", "observability"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Visor de Registros")
        self._logs: list[dict[str, Any]] = []
        self._level_filter = QComboBox()
        for label, value in self._LEVEL_LABELS:
            self._level_filter.addItem(label, value)
        self._component_filter = QComboBox()
        for label, value in self._COMPONENT_LABELS:
            self._component_filter.addItem(label, value)
        self._execution_filter = QTextEdit()
        self._correlation_filter = QTextEdit()
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Nivel", "Componente", "Ejecución", "Correlación", "Mensaje"]
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Nivel", self._level_filter)
        form.addRow("Componente", self._component_filter)
        form.addRow("ID de Ejecución", self._execution_filter)
        form.addRow("ID de Correlación", self._correlation_filter)
        layout.addLayout(form)
        export_button = QPushButton("Exportar")
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
        target = level or "ALL"
        index = self._level_filter.findData(target)
        self._level_filter.setCurrentIndex(index if index >= 0 else 0)
        self._refresh_table()

    def visible_log_count(self) -> int:
        return len(self._filtered_logs())

    def _filtered_logs(self) -> list[dict[str, Any]]:
        level = str(self._level_filter.currentData() or "ALL")
        component = str(self._component_filter.currentData() or "ALL")
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

    @staticmethod
    def _display_level(level: str) -> str:
        return {
            "INFO": "Información",
            "WARNING": "Advertencia",
            "ERROR": "Error",
            "CRITICAL": "Crítico",
        }.get(level, level)

    @staticmethod
    def _display_component(component: str) -> str:
        return {
            "ui": "Interfaz",
            "scheduler": "Programador",
            "observability": "Observabilidad",
        }.get(component, component)

    def _refresh_table(self) -> None:
        rows = self._filtered_logs()
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                self._display_level(str(row["level"])),
                self._display_component(str(row["component"])),
                str(row["execution_id"]),
                str(row["correlation_id"]),
                str(row["message"]),
            )
            for column_index, value in enumerate(values):
                self._table.setItem(row_index, column_index, QTableWidgetItem(value))

    def export_logs(self, export_format: str) -> str:
        rows = self._filtered_logs()
        path = Path(f"/tmp/aip-logs.{export_format}")
        path.write_text(json.dumps(rows, indent=2))
        return str(path)
