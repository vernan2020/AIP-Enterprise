"""Fast, legible and selectable table of actual portfolio positions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class PortfolioPositionsView(QWidget):
    selection_changed = Signal(object)

    _DISPLAY_TRANSLATIONS = {
        "eligible": "Elegible",
        "not eligible": "No elegible",
        "ineligible": "No elegible",
        "available": "Disponible",
        "unavailable": "No disponible",
        "buy": "Comprar",
        "sell": "Vender",
        "hold": "Mantener",
        "government": "Gobierno",
        "govt": "Gobierno",
        "bank": "Banco",
        "private": "Privado",
    }
    HEADERS = (
        "ISIN",
        "Emisor",
        "Instrumento",
        "Moneda",
        "Nominal",
        "Valor de Mercado",
        "Valor en Libros",
        "TIR",
        "Duración Modificada",
        "Clasificación",
        "Estado HQLA",
        "Estado MIL",
        "Recomendación",
    )
    FIELDS = (
        "isin",
        "issuer",
        "instrument",
        "currency",
        "nominal",
        "market_value",
        "book_value",
        "yield_value",
        "modified_duration",
        "classification",
        "hqla_status",
        "mil_status",
        "recommendation",
    )

    def __init__(self, rows: tuple[object, ...] | None = None) -> None:
        super().__init__()
        self.setObjectName("portfolioPositionsView")
        self._rows: tuple[object, ...] = ()
        self._table = QTableWidget()
        self._table.setObjectName("portfolioPositionsTable")
        self._table.setColumnCount(len(self.HEADERS))
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        self._table.setShowGrid(False)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.verticalHeader().hide()
        self._table.verticalHeader().setDefaultSectionSize(31)
        self._table.horizontalHeader().setMinimumHeight(35)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(False)
        for index, width in enumerate(
            (170, 110, 130, 70, 130, 145, 145, 75, 115, 140, 110, 105, 110)
        ):
            self._table.setColumnWidth(index, width)
        self._table.setStyleSheet(
            "QTableWidget#portfolioPositionsTable {background:#FFFFFF;"
            "alternate-background-color:#F1F7FB; border:1px solid #CDDFEB;"
            "border-radius:8px; font-size:10pt; color:#17324D;}"
            "QTableWidget#portfolioPositionsTable::item {padding:4px 7px;}"
            "QTableWidget#portfolioPositionsTable::item:selected {"
            "background:#D8EDFC; color:#00345F;}"
            "QHeaderView::section {background:#00549F; color:#FFFFFF;"
            "font-size:9pt; font-weight:700; padding:7px 6px;"
            "border-right:1px solid #2B7ABC;}"
        )
        self._count_label = QLabel("0 posiciones")
        self._count_label.setObjectName("portfolioPositionsCount")
        self._count_label.setStyleSheet(
            "color:#174E78; font-weight:700; font-size:10pt;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._count_label)
        layout.addWidget(self._table, 1)
        self._table.itemSelectionChanged.connect(self._emit_selection)
        self.bind_rows(rows or ())

    @classmethod
    def _display(cls, value: object) -> str:
        text = str(value if value is not None else "")
        return cls._DISPLAY_TRANSLATIONS.get(text.strip().casefold(), text)

    def bind_rows(self, rows: tuple[object, ...]) -> None:
        self._rows = tuple(rows)
        self._table.blockSignals(True)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            for column_index, name in enumerate(self.FIELDS):
                text = self._display(getattr(row, name, ""))
                item = QTableWidgetItem(text)
                item.setToolTip(f"{self.HEADERS[column_index]}: {text}")
                if column_index in (4, 5, 6, 7, 8):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                    )
                if column_index == 0:
                    # Every row preserves its immutable, original record after sorting.
                    item.setData(Qt.ItemDataRole.UserRole, row)
                self._table.setItem(row_index, column_index, item)
        self._table.setSortingEnabled(True)
        if self._rows:
            self._table.selectRow(0)
        self._table.blockSignals(False)
        self._update_count()
        self._emit_selection()

    def selected_row(self) -> object | None:
        index = self._table.currentRow()
        if index < 0 or self._table.isRowHidden(index):
            return None
        item = self._table.item(index, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _emit_selection(self) -> None:
        self.selection_changed.emit(self.selected_row())

    def apply_filter(self, predicate) -> int:
        count = 0
        for index in range(self._table.rowCount()):
            item = self._table.item(index, 0)
            record = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            visible = record is not None and predicate(record)
            self._table.setRowHidden(index, not visible)
            count += int(visible)
        self._update_count(count)
        current = self.selected_row()
        if current is None and count:
            for index in range(self._table.rowCount()):
                if not self._table.isRowHidden(index):
                    self._table.selectRow(index)
                    break
        else:
            self._emit_selection()
        return count

    def _update_count(self, visible: int | None = None) -> None:
        if visible is None:
            visible = self._table.rowCount()
        self._count_label.setText(
            f"{visible:,} de {self._table.rowCount():,} posiciones"
        )

    def visible_rows(self) -> tuple[object, ...]:
        rows: list[object] = []
        for index in range(self._table.rowCount()):
            if self._table.isRowHidden(index):
                continue
            item = self._table.item(index, 0)
            if item is not None:
                rows.append(item.data(Qt.ItemDataRole.UserRole))
        return tuple(rows)
