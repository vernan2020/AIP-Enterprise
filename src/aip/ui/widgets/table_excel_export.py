"""Download visible Qt tables as a genuine Excel workbook without recalculating risk."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidget, QWidget

from aip.ui.services.export_service import ExcelSheet, TableExportService


def export_table_excel(
    table: QTableWidget,
    destination: str | Path,
    *,
    visible_rows_only: bool = False,
    title: str = "Datos",
) -> int:
    """Export exactly the visible columns and selected rows in displayed order."""
    columns = [index for index in range(table.columnCount()) if not table.isColumnHidden(index)]
    headers = tuple(
        table.horizontalHeaderItem(index).text()
        if table.horizontalHeaderItem(index) is not None
        else ""
        for index in columns
    )
    if not headers:
        raise ValueError("No hay columnas visibles que exportar")
    rows = []
    for row_index in range(table.rowCount()):
        if visible_rows_only and table.isRowHidden(row_index):
            continue
        values = []
        for column_index in columns:
            item = table.item(row_index, column_index)
            if item is None:
                values.append(None)
                continue
            raw_value = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(raw_value, (int, float, bool, Decimal, date, datetime)):
                values.append(raw_value)
            else:
                values.append(item.text())
        rows.append(tuple(values))
    TableExportService().export_workbook(
        destination,
        sheets=(ExcelSheet(title=title, headers=headers, rows=tuple(rows)),),
        metadata={
            "Fuente": "AIP Enterprise · pantalla institucional",
            "Alcance": "Columnas visibles; filas filtradas según selección",
            "Observación": "Mismos valores presentados en pantalla; sin recálculo de VeR ni tasas",
        },
    )
    return len(rows)


def save_table_excel_dialog(
    parent: QWidget,
    table: QTableWidget,
    suggested_filename: str,
    *,
    visible_rows_only: bool = False,
    title: str = "Datos",
) -> None:
    """User-selected destination; a failed export never changes financial data."""
    destination, _filter = QFileDialog.getSaveFileName(
        parent, "Exportar Excel (.xlsx)", suggested_filename, "Excel (*.xlsx)"
    )
    if not destination:
        return
    try:
        count = export_table_excel(
            table, destination, visible_rows_only=visible_rows_only, title=title
        )
    except (OSError, ValueError) as exc:
        QMessageBox.warning(parent, "Error de exportación", f"No se pudo guardar XLSX: {exc}")
        return
    QMessageBox.information(
        parent, "Exportación completada", f"Se exportaron {count} registros a Excel."
    )
