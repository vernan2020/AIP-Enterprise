"""CSV exports for Qt financial tables, compatible with Spanish-language Excel."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidget, QWidget

_NUMERIC_CELL = re.compile(r"[+-]?\d[\d\s.,]*%?")
_RATE_SHOCK_CELL = re.compile(r"[+-]\d+(?:[.,]\d+)?\s+pb", re.IGNORECASE)


def _excel_safe_cell(value: str) -> str:
    """Prevent spreadsheet formulas from executing while retaining signed numerics."""
    stripped = value.lstrip()
    starts_like_formula = stripped.startswith(("=", "+", "-", "@"))
    if starts_like_formula and not (
        _NUMERIC_CELL.fullmatch(stripped) or _RATE_SHOCK_CELL.fullmatch(stripped)
    ):
        return "'" + value
    return value


def export_table_csv(
    table: QTableWidget, destination: str | Path, *, visible_rows_only: bool = False
) -> int:
    """Export visible columns and optionally filtered rows without changing their data."""
    columns = [col for col in range(table.columnCount()) if not table.isColumnHidden(col)]
    count = 0
    with Path(destination).open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
        header_values = []
        for col in columns:
            header = table.horizontalHeaderItem(col)
            header_values.append(_excel_safe_cell(header.text() if header is not None else ""))
        writer.writerow(header_values)
        for row in range(table.rowCount()):
            if visible_rows_only and table.isRowHidden(row):
                continue
            values = []
            for col in columns:
                item = table.item(row, col)
                values.append(_excel_safe_cell(item.text() if item is not None else ""))
            writer.writerow(values)
            count += 1
    return count


def save_table_csv_dialog(
    parent: QWidget,
    table: QTableWidget,
    suggested_filename: str,
    *,
    visible_rows_only: bool = False,
) -> None:
    """Use a user-selected destination and report errors without modifying the table."""
    path, _selected_filter = QFileDialog.getSaveFileName(
        parent,
        "Exportar tabla para Excel",
        suggested_filename,
        "CSV para Excel (*.csv)",
    )
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path += ".csv"
    try:
        exported = export_table_csv(table, path, visible_rows_only=visible_rows_only)
    except OSError as exc:
        QMessageBox.warning(parent, "Error de exportación", f"No se pudo guardar el CSV: {exc}")
        return
    QMessageBox.information(
        parent, "Exportación completada", f"Se exportaron {exported} registros a CSV."
    )
