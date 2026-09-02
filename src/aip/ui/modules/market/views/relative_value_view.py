from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class RelativeValueView(QWidget):
    """Ranking compacto de Valor Relativo del portafolio."""

    COLUMN_HEADERS = (
        "Serie",
        "Moneda",
        "Clasificación",
        "Diferencial",
        "TIR Mdo.",
        "TIR NS",
        "Plazo",
        "Valor Mdo. CRC",
        "Pos.",
    )

    def __init__(self, rows: tuple[object, ...] | None = None) -> None:
        super().__init__()
        self.setObjectName("relativeValueView")
        self._rows: tuple[object, ...] = rows or ()
        self._table = QTableWidget()
        self._table.setObjectName("relativeValueTable")
        self._table.setColumnCount(len(self.COLUMN_HEADERS))
        self._table.setHorizontalHeaderLabels(list(self.COLUMN_HEADERS))
        self._configure_table()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._table)
        self.bind_rows(self._rows)

    def _configure_table(self) -> None:
        table = self._table
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(27)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setStyleSheet(
            """
            QTableWidget#relativeValueTable {
                background:#FFFFFF;
                alternate-background-color:#F7F9FA;
                border:1px solid #D5DEE3;
                border-radius:6px;
                selection-background-color:#DDEFFA;
                selection-color:#00345F;
            }
            QTableWidget#relativeValueTable::item {
                border-bottom:1px solid #E3E9EC;
                padding:3px 5px;
            }
            QHeaderView::section {
                background:#005EB8;
                color:#FFFFFF;
                border:none;
                border-right:1px solid #1675C5;
                padding:6px 5px;
                font-weight:700;
            }
            """
        )

        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(42)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        widths = (0, 62, 94, 78, 76, 76, 72, 118, 48)
        for column in range(1, len(self.COLUMN_HEADERS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(column, widths[column])

    @staticmethod
    def _number(value: object, decimals: int, suffix: str = "") -> str:
        if value in (None, ""):
            return "-"
        try:
            return f"{float(value):,.{decimals}f}{suffix}"
        except (TypeError, ValueError):
            return str(value)

    @classmethod
    def _format_value(cls, row: object, column: int) -> str:
        if column == 0:
            return str(getattr(row, "series", ""))
        if column == 1:
            return str(getattr(row, "currency", ""))
        if column == 2:
            return str(getattr(row, "classification", ""))
        if column == 3:
            return cls._number(getattr(row, "spread_bp", None), 1, " pb")
        if column == 4:
            return cls._number(getattr(row, "market_yield", None), 3, "%")
        if column == 5:
            return cls._number(getattr(row, "curve_yield", None), 3, "%")
        if column == 6:
            return cls._number(getattr(row, "tenor", None), 2, "a")
        if column == 7:
            value = getattr(row, "market_value_crc", None)
            if value is None:
                return "-"
            try:
                return f"₡{float(value) / 1_000_000:,.2f} MM"
            except (TypeError, ValueError):
                return str(value)
        return str(getattr(row, "position_count", ""))

    def bind_rows(self, rows: tuple[object, ...]) -> None:
        self._rows = rows
        table = self._table
        table.setSortingEnabled(False)
        table.clearContents()
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index in range(len(self.COLUMN_HEADERS)):
                item = QTableWidgetItem(self._format_value(row, column_index))
                item.setData(Qt.ItemDataRole.UserRole, row_index)
                if column_index >= 3:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if column_index == 2:
                    self._apply_classification_style(item, row)
                table.setItem(row_index, column_index, item)
        table.setSortingEnabled(True)
        if rows:
            table.selectRow(0)

    @staticmethod
    def _apply_classification_style(item: QTableWidgetItem, row: object) -> None:
        classification = str(getattr(row, "classification", "")).strip().upper()
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        if classification == "BARATO":
            item.setForeground(QColor("#167A68"))
        elif classification == "CARO":
            item.setForeground(QColor("#B42335"))
        else:
            item.setForeground(QColor("#566D7C"))

    def selected_source_index(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def table(self) -> QTableWidget:
        return self._table

    def rows(self) -> tuple[object, ...]:
        return self._rows
