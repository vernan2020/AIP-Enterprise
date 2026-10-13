from __future__ import annotations

import csv

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from aip.ui.widgets.table_csv_export import export_table_csv


def test_table_csv_export_keeps_utf8_headers_and_filtered_rows(qt_app, tmp_path) -> None:
    table = QTableWidget(3, 3)
    table.setHorizontalHeaderLabels(["Período", "Variación", "Fuente SUGEF"])
    try:
        values = (
            ("2026-09", "-12,50", "SUGEF · revisión"),
            ("2026-08", "1,25", "BCCR"),
            ("2026-07", "0,00", "SUGEF"),
        )
        for row, data in enumerate(values):
            for column, value in enumerate(data):
                table.setItem(row, column, QTableWidgetItem(value))
        table.setRowHidden(1, True)
        table.setColumnHidden(2, True)
        path = tmp_path / "indicadores.csv"
        assert export_table_csv(table, path, visible_rows_only=True) == 2
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            exported = list(csv.reader(stream, delimiter=";"))
        assert exported == [
            ["Período", "Variación"],
            ["2026-09", "-12,50"],
            ["2026-07", "0,00"],
        ]
    finally:
        table.close()
        qt_app.processEvents()


def test_table_csv_export_escapes_formulas_and_quotes(qt_app, tmp_path) -> None:
    table = QTableWidget(1, 4)
    table.setHorizontalHeaderLabels(["A", "B", "C", "D"])
    try:
        entries = ("=HYPERLINK(\"https://example.com\")", "+1+2", "@SUM(A1)", "-1,234.50")
        for index, value in enumerate(entries):
            table.setItem(0, index, QTableWidgetItem(value))
        path = tmp_path / "safe.csv"
        assert export_table_csv(table, path) == 1
        with path.open(encoding="utf-8-sig", newline="") as stream:
            data = list(csv.reader(stream, delimiter=";"))
        assert data[1] == [
            "'=HYPERLINK(\"https://example.com\")",
            "'+1+2",
            "'@SUM(A1)",
            "-1,234.50",
        ]
    finally:
        table.close()
        qt_app.processEvents()


def test_table_csv_export_preserves_multiline_text(qt_app, tmp_path) -> None:
    table = QTableWidget(1, 1)
    table.setHorizontalHeaderLabels(["Trazabilidad"])
    try:
        table.setItem(0, 0, QTableWidgetItem('Línea 1; "texto"\nLínea 2'))
        path = tmp_path / "trace.csv"
        assert export_table_csv(table, path) == 1
        with path.open(encoding="utf-8-sig", newline="") as stream:
            exported = list(csv.reader(stream, delimiter=";"))
        assert exported == [["Trazabilidad"], ['Línea 1; "texto"\nLínea 2']]
    finally:
        table.close()
        qt_app.processEvents()
