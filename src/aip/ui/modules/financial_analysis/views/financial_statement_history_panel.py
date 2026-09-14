from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QValueAxis
from PySide6.QtCore import QDateTime, QMargins, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialMetricHistorySeriesView,
)


class FinancialStatementHistoryPanel(QWidget):
    """Interactive historical chart for every SUGEF account and indicator."""

    def __init__(self) -> None:
        super().__init__()
        self._series: tuple[FinancialMetricHistorySeriesView, ...] = ()
        self._chart_view: QChartView | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Histórico de la cuenta / indicador seleccionado")
        title.setStyleSheet("font-size:11px; font-weight:700; color:#142E46;")
        header.addWidget(title)
        header.addStretch(1)
        self._coverage = QLabel("Sin histórico")
        self._coverage.setStyleSheet("color:#667788; font-size:9px;")
        header.addWidget(self._coverage)
        root.addLayout(header)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Serie:"))
        self._selector = QComboBox()
        self._selector.setMinimumWidth(420)
        self._selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._selector.setMinimumContentsLength(55)
        self._selector.currentIndexChanged.connect(self._selection_changed)
        selector_row.addWidget(self._selector, 1)
        root.addLayout(selector_row)

        self._latest = QLabel("Seleccione una cuenta o indicador para ver su evolución.")
        self._latest.setStyleSheet("color:#52687A; font-size:9px;")
        root.addWidget(self._latest)

        self._chart_host = QVBoxLayout()
        root.addLayout(self._chart_host, 1)

    def bind_history(self, series: tuple[FinancialMetricHistorySeriesView, ...]) -> None:
        current_code = self._selector.currentData()
        self._series = series
        self._selector.blockSignals(True)
        try:
            self._selector.clear()
            for item in series:
                self._selector.addItem(item.label, item.code)
            if current_code:
                index = self._selector.findData(current_code)
                if index >= 0:
                    self._selector.setCurrentIndex(index)
        finally:
            self._selector.blockSignals(False)
        self._render_current()

    def select_series(self, code: str) -> None:
        if not code:
            return
        index = self._selector.findData(code)
        if index >= 0:
            self._selector.setCurrentIndex(index)

    def _selection_changed(self, _index: int) -> None:
        self._render_current()

    def _render_current(self) -> None:
        self._clear_chart()
        index = self._selector.currentIndex()
        if index < 0 or index >= len(self._series):
            self._coverage.setText("Sin histórico")
            self._latest.setText("No hay series históricas SUGEF disponibles para este corte.")
            return
        item = self._series[index]
        self._coverage.setText(f"{item.available_points}/{item.total_points} cortes")
        self._latest.setText(
            f"Último: {item.latest_value} · {item.period_change} · Fuente: {item.source_account}"
        )
        self._chart_view = self._build_chart(item)
        self._chart_host.addWidget(self._chart_view)

    def _clear_chart(self) -> None:
        if self._chart_view is not None:
            self._chart_host.removeWidget(self._chart_view)
            self._chart_view.deleteLater()
            self._chart_view = None

    @staticmethod
    def _build_chart(item: FinancialMetricHistorySeriesView) -> QChartView:
        chart = QChart()
        chart.legend().hide()
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(2, 2, 2, 2))

        dates = tuple(
            QDateTime.fromString(point.iso_date, Qt.DateFormat.ISODate) for point in item.points
        )
        values = tuple(point.value for point in item.points if point.value is not None)

        axis_x = QDateTimeAxis()
        axis_x.setFormat("MMM-yy")
        axis_x.setLabelsAngle(-35)
        axis_x.setTickCount(min(7, max(2, len(item.points))))
        axis_x.setGridLineVisible(False)
        if dates:
            start = dates[0]
            end = dates[-1]
            if start == end:
                start = start.addDays(-15)
                end = end.addDays(15)
            axis_x.setRange(start, end)

        axis_y = QValueAxis()
        axis_y.setTitleText(item.unit)
        axis_y.setLabelFormat("%.2f" if item.unit in {"%", "Valor"} else "%.0f")
        axis_y.setTickCount(6)
        if values:
            minimum = min(values)
            maximum = max(values)
            spread = maximum - minimum
            baseline = max(abs(minimum), abs(maximum), 1.0)
            padding = max(spread * 0.12, baseline * 0.03, 0.25)
            axis_y.setRange(minimum - padding, maximum + padding)
        else:
            axis_y.setRange(0.0, 1.0)

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

        segment: QLineSeries | None = None
        tooltip: list[str] = []
        for point, point_date in zip(item.points, dates, strict=True):
            tooltip.append(f"{point.date_label}: {point.display_value}")
            if point.value is None:
                segment = None
                continue
            if segment is None:
                segment = QLineSeries()
                segment.setPen(QPen(QColor("#005EB8"), 2.2))
                segment.setPointsVisible(True)
                segment.setMarkerSize(5.0)
                chart.addSeries(segment)
                segment.attachAxis(axis_x)
                segment.attachAxis(axis_y)
            segment.append(float(point_date.toMSecsSinceEpoch()), point.value)

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(230)
        view.setToolTip("\n".join(tooltip))
        return view
