from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.portfolio.models.portfolio_history_point import PortfolioHistoryPoint
from aip.ui.modules.portfolio.widgets.portfolio_history_line_chart import (
    PortfolioHistoryLineChart,
)


class PortfolioHistoryView(QWidget):
    """Historical KPI workspace with horizon and source-cut sampling controls."""

    sampling_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: tuple[PortfolioHistoryPoint, ...] = ()
        self._sampling = "monthly"
        self._status = "UNAVAILABLE"
        self._warnings: tuple[str, ...] = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        controls = QHBoxLayout()
        title = QLabel("EVOLUCIÓN HISTÓRICA DE KPIs")
        title.setProperty("role", "sectionTitle")
        controls.addWidget(title)
        controls.addStretch(1)

        controls.addWidget(QLabel("Horizonte"))
        self._horizon = QComboBox()
        self._horizon.addItem("3 meses", "3M")
        self._horizon.addItem("6 meses", "6M")
        self._horizon.addItem("12 meses", "12M")
        self._horizon.addItem("Año en curso", "YTD")
        self._horizon.addItem("Todo", "ALL")
        self._horizon.setCurrentIndex(2)
        self._horizon.currentIndexChanged.connect(self._refresh_charts)
        controls.addWidget(self._horizon)

        controls.addWidget(QLabel("Frecuencia"))
        self._frequency = QComboBox()
        self._frequency.addItem("Mensual", "monthly")
        self._frequency.addItem("Cada corte", "daily")
        self._frequency.currentIndexChanged.connect(self._on_frequency_changed)
        controls.addWidget(self._frequency)
        root.addLayout(controls)

        subtitle = QLabel(
            "Cada punto se recalcula desde el maestro institucional del corte; "
            "no se interpolan datos faltantes."
        )
        subtitle.setProperty("role", "subtle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self._status_label = QLabel("Histórico no cargado")
        self._status_label.setProperty("role", "subtle")
        root.addWidget(self._status_label)

        self._charts: dict[str, PortfolioHistoryLineChart] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        definitions = (
            (
                "market_value",
                "Valor de mercado",
                "Evolución del valor total del portafolio en millones de colones.",
                lambda value: f"₡{value:,.0f} MM",
            ),
            (
                "weighted_yield",
                "TIR ponderada",
                "Rendimiento efectivo ponderado del portafolio.",
                lambda value: f"{value:,.2f}%",
            ),
            (
                "duration",
                "Duración modificada",
                "Sensibilidad agregada del portafolio a movimientos de tasas.",
                lambda value: f"{value:,.2f}",
            ),
            (
                "hqla",
                "HQLA",
                "Proporción del valor de mercado elegible como activo líquido de alta calidad.",
                lambda value: f"{value:,.1f}%",
            ),
            (
                "dv01",
                "DV01",
                "Variación estimada de valor ante un movimiento de 1 pb, en millones de colones.",
                lambda value: f"₡{value:,.2f} MM",
            ),
            (
                "hhi",
                "HHI por emisor",
                "Índice Herfindahl-Hirschman de concentración del portafolio por emisor.",
                lambda value: f"{value:,.0f}",
            ),
        )

        for index, (key, heading, detail, formatter) in enumerate(definitions):
            group = QGroupBox(heading)
            group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            box = QVBoxLayout(group)
            description = QLabel(detail)
            description.setProperty("role", "subtle")
            description.setWordWrap(True)
            box.addWidget(description)
            chart = PortfolioHistoryLineChart(value_formatter=formatter)
            box.addWidget(chart, 1)
            self._charts[key] = chart
            grid.addWidget(group, index // 2, index % 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        for row in range(3):
            grid.setRowStretch(row, 1)
        root.addLayout(grid, 1)

    def set_data(
        self,
        points: tuple[PortfolioHistoryPoint, ...],
        *,
        status: str,
        sampling: str = "monthly",
        warnings: tuple[str, ...] = (),
    ) -> None:
        self._points = tuple(sorted(points, key=lambda item: item.valuation_date))
        self._status = status
        self._warnings = warnings
        self._sampling = sampling

        index = self._frequency.findData(sampling)
        if index >= 0 and index != self._frequency.currentIndex():
            self._frequency.blockSignals(True)
            self._frequency.setCurrentIndex(index)
            self._frequency.blockSignals(False)
        self._refresh_charts()

    def _on_frequency_changed(self) -> None:
        requested = str(self._frequency.currentData() or "monthly")
        if requested == self._sampling:
            self._refresh_charts()
            return
        self._status_label.setText("Calculando cortes históricos…")
        self.sampling_requested.emit(requested)

    def _refresh_charts(self) -> None:
        points = self._filtered_points()
        self._charts["market_value"].set_data(
            tuple((point.valuation_date, point.market_value_mm) for point in points)
        )
        self._charts["weighted_yield"].set_data(
            tuple((point.valuation_date, point.weighted_yield_percent) for point in points)
        )
        self._charts["duration"].set_data(
            tuple((point.valuation_date, point.modified_duration) for point in points)
        )
        self._charts["hqla"].set_data(
            tuple((point.valuation_date, point.hqla_percent) for point in points)
        )
        self._charts["dv01"].set_data(
            tuple((point.valuation_date, point.dv01_mm) for point in points)
        )
        self._charts["hhi"].set_data(tuple((point.valuation_date, point.hhi) for point in points))

        frequency = "mensual" if self._sampling == "monthly" else "cada corte"
        warning_text = (
            f" · {len(self._warnings)} advertencia(s) de fuente" if self._warnings else ""
        )
        self._status_label.setText(
            f"{len(points)} cortes visibles · frecuencia {frequency} · "
            f"estado {self._status}{warning_text}"
        )

    def _filtered_points(self) -> tuple[PortfolioHistoryPoint, ...]:
        if not self._points:
            return ()
        horizon = str(self._horizon.currentData() or "12M")
        if horizon == "ALL":
            return self._points

        latest = self._points[-1].valuation_date
        if horizon == "YTD":
            threshold = date(latest.year, 1, 1)
        else:
            months = {"3M": 3, "6M": 6, "12M": 12}.get(horizon, 12)
            threshold = self._subtract_months(latest, months)
        return tuple(point for point in self._points if point.valuation_date >= threshold)

    @staticmethod
    def _subtract_months(value: date, months: int) -> date:
        month_index = value.year * 12 + value.month - 1 - months
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        days = (
            31,
            29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        )
        return date(year, month, min(value.day, days[month - 1]))
