from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationComparisonDisplay,
    PortfolioValuationComparisonDisplayRow,
    PortfolioValuationKpi,
)
from aip.ui.modules.portfolio.widgets.portfolio_gain_loss_chart import (
    PortfolioGainLossBarChart,
)


class PortfolioValuationComparisonView(QWidget):
    """Passive dashboard of authoritative accumulated valuation from the Master."""

    _GAIN = QColor("#16794B")
    _LOSS = QColor("#B42318")
    _NEUTRAL = QColor("#22384C")

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("portfolioValuationComparison")
        self._model = PortfolioValuationComparisonDisplay()
        self._show_all = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(8)

        self._note = QLabel(
            "La ganancia / pérdida parte directamente de la ‘Valuación acumulada’ del "
            "Maestro de Inversiones. Las posiciones USD se convierten a CRC con el "
            "tipo de cambio de venta BCCR del cierre del corte."
        )
        self._note.setObjectName("portfolioValuationMethodology")
        self._note.setWordWrap(True)
        self._note.setStyleSheet(
            "background:#EEF5FA; color:#355269; border:1px solid #D6E4EE; "
            "border-radius:7px; padding:8px 10px;"
        )
        layout.addWidget(self._note)

        self._kpi_grid = QGridLayout()
        self._kpi_grid.setHorizontalSpacing(8)
        self._kpi_grid.setVerticalSpacing(6)
        self._kpi_values: dict[str, QLabel] = {}
        layout.addLayout(self._kpi_grid)

        charts = QGridLayout()
        charts.setHorizontalSpacing(8)
        charts.setVerticalSpacing(8)

        self._top_gains = PortfolioGainLossBarChart()
        self._top_losses = PortfolioGainLossBarChart()
        self._currency = PortfolioGainLossBarChart(mode="diverging")
        self._issuers = PortfolioGainLossBarChart(mode="diverging")

        charts.addWidget(self._chart_group("Top 5 ganancias", self._top_gains), 0, 0)
        charts.addWidget(self._chart_group("Top 5 pérdidas", self._top_losses), 0, 1)
        charts.addWidget(
            self._chart_group("Ganancia / pérdida por moneda", self._currency),
            1,
            0,
        )
        charts.addWidget(
            self._chart_group("Ganancia / pérdida por emisor · Top 5", self._issuers),
            1,
            1,
        )
        charts.setColumnStretch(0, 1)
        charts.setColumnStretch(1, 1)
        layout.addLayout(charts, 2)

        detail_header = QGridLayout()
        detail_title = QLabel("Detalle por posición · Top 10 por magnitud absoluta")
        detail_title.setStyleSheet("font-weight:700; color:#17324D;")
        detail_header.addWidget(detail_title, 0, 0)
        self._toggle = QPushButton("Ver todas las posiciones")
        self._toggle.setObjectName("portfolioValuationShowAll")
        self._toggle.setStyleSheet(
            "QPushButton {padding:5px 10px; border:1px solid #C9D6E0; "
            "border-radius:6px; color:#174E78; background:#FFFFFF;}"
            "QPushButton:hover {background:#F3F7FA;}"
        )
        self._toggle.clicked.connect(self._toggle_positions)
        detail_header.addWidget(self._toggle, 0, 1)
        detail_header.setColumnStretch(0, 1)
        layout.addLayout(detail_header)

        self._positions = self._table(
            [
                "#",
                "Posición / ISIN",
                "Emisor",
                "Moneda",
                "Valuación acum. original",
                "G/P consolidada CRC",
            ]
        )
        self._positions.setObjectName("portfolioValuationPositions")
        self._positions.setMinimumHeight(180)
        layout.addWidget(self._positions, 1)

    @staticmethod
    def _chart_group(title: str, chart: QWidget) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(
            "QGroupBox {font-weight:700; color:#17324D; background:#FFFFFF; "
            "border:1px solid #DCE5EC; border-radius:8px; margin-top:7px;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 4px;}"
        )
        inner = QVBoxLayout(group)
        inner.setContentsMargins(8, 14, 8, 6)
        inner.addWidget(chart)
        return group

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
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return table

    def bind(self, model: PortfolioValuationComparisonDisplay, valuation_date: str) -> None:
        self._model = model
        self._show_all = False
        self._toggle.setText("Ver todas las posiciones")
        self._note.setText(
            f"Corte {valuation_date} · Ganancia / pérdida basada en la ‘Valuación acumulada’ "
            "del Maestro de Inversiones. CRC se mantiene en moneda original; USD se convierte "
            f"a CRC con TC venta BCCR {model.fx_sell_rate} del {model.fx_rate_date}. "
            "Si el TC exacto del corte no está disponible, la posición USD queda N/D para "
            "consolidación y no se sustituye por cero."
        )
        self._bind_kpis(model.kpis)
        self._top_gains.set_data(model.top_gains)
        self._top_losses.set_data(model.top_losses)
        self._currency.set_data(model.currency_points)
        self._issuers.set_data(model.issuer_points)
        self._populate_detail(model.positions)

    def _bind_kpis(self, kpis: tuple[PortfolioValuationKpi, ...]) -> None:
        while self._kpi_grid.count():
            item = self._kpi_grid.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._kpi_values.clear()

        for index, kpi in enumerate(kpis):
            card = QFrame()
            card.setObjectName(f"portfolioValuationKpi_{kpi.key}")
            card.setStyleSheet(
                "QFrame {background:#FFFFFF; border:1px solid #DCE5EC; " "border-radius:8px;}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 7, 10, 7)
            title = QLabel(kpi.title)
            title.setStyleSheet("color:#66788A; font-size:10px; border:0;")
            value = QLabel(kpi.value)
            value.setObjectName(f"portfolioValuationKpiValue_{kpi.key}")
            value.setStyleSheet(
                f"color:{self._tone_color(kpi.tone).name()}; "
                "font-size:16px; font-weight:700; border:0;"
            )
            card_layout.addWidget(title)
            card_layout.addWidget(value)
            self._kpi_values[kpi.key] = value
            self._kpi_grid.addWidget(card, 0, index)

    def _toggle_positions(self) -> None:
        self._show_all = not self._show_all
        self._toggle.setText("Ver Top 10" if self._show_all else "Ver todas las posiciones")
        rows = self._model.all_positions if self._show_all else self._model.positions
        self._populate_detail(rows)

    def _populate_detail(
        self,
        rows: tuple[PortfolioValuationComparisonDisplayRow, ...],
    ) -> None:
        self._positions.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            identity, issuer, currency, original, consolidated, *_ = row.cells
            values = (
                str(row_index + 1),
                identity,
                issuer,
                currency,
                original,
                consolidated,
            )
            color = self._tone_color(row.tone)
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 5:
                    item.setForeground(color)
                self._positions.setItem(row_index, column, item)

    def _tone_color(self, tone: str) -> QColor:
        if tone == "gain":
            return self._GAIN
        if tone == "loss":
            return self._LOSS
        return self._NEUTRAL
