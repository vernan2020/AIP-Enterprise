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
)


class PortfolioValuationComparisonView(QWidget):
    """Passive market-versus-book valuation view."""

    _GAIN = QColor("#16794B")
    _LOSS = QColor("#B42318")
    _NEUTRAL = QColor("#22384C")

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("portfolioValuationComparison")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(8)

        self._note = QLabel(
            "Ganancia / pérdida no realizada = valor de mercado − valor contable. "
            "Los totales se presentan por moneda; posiciones incompletas no se convierten a cero."
        )
        self._note.setWordWrap(True)
        self._note.setStyleSheet("color:#617386; padding:4px 2px;")
        layout.addWidget(self._note)

        self._totals = self._table(
            ["Moneda", "Mercado", "Contable", "G/P", "G/P %", "Cobertura"]
        )
        self._totals.setObjectName("portfolioValuationTotals")
        self._totals.setMaximumHeight(180)
        layout.addWidget(self._totals)

        self._positions = self._table(
            [
                "Posición",
                "Emisor",
                "Moneda",
                "Mercado",
                "Contable",
                "G/P",
                "G/P %",
                "Estado",
                "Fuente",
            ]
        )
        self._positions.setObjectName("portfolioValuationPositions")
        layout.addWidget(self._positions, 1)

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def bind(self, model: PortfolioValuationComparisonDisplay, valuation_date: str) -> None:
        self._note.setText(
            f"Corte {valuation_date} · Ganancia / pérdida no realizada = valor de mercado − "
            "valor contable. Totales separados por moneda; faltantes quedan como N/D."
        )
        self._populate(self._totals, model.totals)
        self._populate(self._positions, model.positions)

    def _populate(self, table: QTableWidget, rows) -> None:
        table.setRowCount(len(rows))
        tone_column = 3 if table is self._totals else 5
        for row_index, row in enumerate(rows):
            color = self._tone_color(row.tone)
            for column, value in enumerate(row.cells):
                item = QTableWidgetItem(value)
                if column == tone_column:
                    item.setForeground(color)
                table.setItem(row_index, column, item)

    def _tone_color(self, tone: str) -> QColor:
        if tone == "gain":
            return self._GAIN
        if tone == "loss":
            return self._LOSS
        return self._NEUTRAL
