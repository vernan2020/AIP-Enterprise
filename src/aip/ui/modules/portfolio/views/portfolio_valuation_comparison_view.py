from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationComparisonDisplay,
    PortfolioValuationComparisonDisplayRow,
)


class PortfolioValuationComparisonView(QWidget):
    """Passive view of same-cut market/book differences and coverage."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._note = QLabel()
        self._note.setWordWrap(True)
        layout.addWidget(self._note)
        self._totals = self._table(
            ["Moneda", "Mercado", "Libros", "Ganancia / pérdida", "% sobre libros", "Cobertura"]
        )
        self._totals.setMaximumHeight(180)
        layout.addWidget(self._totals)
        self._positions = self._table(
            [
                "ISIN / serie",
                "Emisor",
                "Moneda",
                "Mercado",
                "Libros",
                "Ganancia / pérdida",
                "% sobre libros",
                "Estado",
                "Fuente",
            ]
        )
        layout.addWidget(self._positions)

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _bind(
        table: QTableWidget,
        rows: tuple[PortfolioValuationComparisonDisplayRow, ...],
        difference_column: int,
    ) -> None:
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for column, value in enumerate(row.cells):
                item = QTableWidgetItem(value)
                if column in (difference_column, difference_column + 1):
                    color = {"gain": "#146C43", "loss": "#B42318"}.get(row.tone)
                    if color:
                        item.setForeground(QColor(color))
                        item.setBackground(QColor("#FFFFFF"))
                table.setItem(index, column, item)

    def bind(self, display: PortfolioValuationComparisonDisplay, cutoff: str) -> None:
        self._note.setText(
            f"Corte del Maestro: {cutoff}. Ganancia / pérdida no realizada = mercado − libros. "
            "Importes en moneda original; totales sobre posiciones con ambos valores disponibles. "
            "No incluye ajustes adicionales por cupones, comisiones o deterioro, ni representa "
            "rendimiento total o resultado realizado. N/D identifica información no disponible."
        )
        self._bind(self._totals, display.totals, 3)
        self._bind(self._positions, display.positions, 5)
