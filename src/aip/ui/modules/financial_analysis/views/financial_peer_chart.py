from __future__ import annotations

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    PeerChartPointView,
    PeerChartSeriesView,
)


class FinancialPeerChartPanel(QWidget):
    """Comparative peer charts and additive market-composition views."""

    _MAX_BAR_ENTITIES = 15

    def __init__(self) -> None:
        super().__init__()
        self._series: tuple[PeerChartSeriesView, ...] = ()
        self._chart_view: QChartView | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("Comparación y composición del mercado")
        title.setStyleSheet("font-size:11px; font-weight:700; color:#142E46;")
        header.addWidget(title)
        header.addStretch(1)
        self._summary = QLabel("Sin datos")
        self._summary.setStyleSheet("color:#667788; font-size:9px;")
        header.addWidget(self._summary)
        root.addLayout(header)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(6)
        selector_row.addWidget(QLabel("Gráfico:"))
        self._selector = QComboBox()
        self._selector.setMinimumWidth(280)
        self._selector.currentIndexChanged.connect(self._selection_changed)
        selector_row.addWidget(self._selector)
        selector_row.addStretch(1)
        root.addLayout(selector_row)

        self._chart_host = QVBoxLayout()
        self._chart_host.setContentsMargins(0, 0, 0, 0)
        self._chart_host.setSpacing(0)
        root.addLayout(self._chart_host, 1)

    def bind_series(self, series: tuple[PeerChartSeriesView, ...]) -> None:
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

    def _selection_changed(self, _index: int) -> None:
        self._render_current()

    def _render_current(self) -> None:
        self._clear_chart()
        index = self._selector.currentIndex()
        if index < 0 or index >= len(self._series):
            self._summary.setText("Sin datos comparables")
            return
        item = self._series[index]
        self._summary.setText(f"{len(item.points)} entidades · {item.unit}")
        self._chart_view = (
            self._pie_chart(item) if item.chart_type == "PIE" else self._bar_chart(item)
        )
        self._chart_host.addWidget(self._chart_view)

    def _clear_chart(self) -> None:
        if self._chart_view is not None:
            self._chart_host.removeWidget(self._chart_view)
            self._chart_view.deleteLater()
            self._chart_view = None

    @classmethod
    def _bar_points(cls, item: PeerChartSeriesView) -> tuple[PeerChartPointView, ...]:
        ordered = sorted(item.points, key=lambda point: abs(point.value), reverse=True)
        selected = next((point for point in ordered if point.selected), None)
        visible = ordered[: cls._MAX_BAR_ENTITIES]
        if selected is not None and selected not in visible and visible:
            visible[-1] = selected
        return tuple(visible)

    @classmethod
    def _bar_chart(cls, item: PeerChartSeriesView) -> QChartView:
        points = cls._bar_points(item)
        chart = QChart()
        chart.setTitle(item.label)
        chart.legend().hide()
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(4, 2, 4, 2))
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        bar_set = QBarSet(item.label)
        bar_set.append([point.value for point in points])
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)

        categories = QBarCategoryAxis()
        categories.append([cls._short_name(point.entity_name) for point in points])
        categories.setLabelsAngle(-35)
        category_font = categories.labelsFont()
        category_font.setPointSize(7)
        categories.setLabelsFont(category_font)

        value_axis = QValueAxis()
        value_axis.setTitleText(item.unit)
        value_axis.setLabelFormat("%.2f" if item.unit == "%" else "%.0f")
        value_font = value_axis.labelsFont()
        value_font.setPointSize(8)
        value_axis.setLabelsFont(value_font)

        values = [point.value for point in points]
        if values:
            minimum = min(values)
            maximum = max(values)
            span = maximum - minimum
            padding = max(span * 0.08, max(abs(minimum), abs(maximum), 1.0) * 0.05)
            value_axis.setRange(min(0.0, minimum - padding), max(0.0, maximum + padding))

        chart.addAxis(categories, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(value_axis, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(categories)
        series.attachAxis(value_axis)

        tooltip = "\n".join(
            f"{point.entity_name}: {point.display_value}"
            + (" · seleccionada" if point.selected else "")
            for point in points
        )
        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(245)
        view.setToolTip(tooltip)
        return view

    @classmethod
    def _pie_chart(cls, item: PeerChartSeriesView) -> QChartView:
        chart = QChart()
        chart.setTitle(item.label)
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(4, 2, 4, 2))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
        series = QPieSeries()
        for index, point in enumerate(item.points):
            slice_ = series.append(cls._short_name(point.entity_name), point.value)
            if index < 10 or point.selected:
                slice_.setLabel(f"{cls._short_name(point.entity_name)} {point.value:.1f}%")
                slice_.setLabelVisible(True)
            if point.selected:
                slice_.setExploded(True)
        chart.addSeries(series)
        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(245)
        view.setToolTip(
            "\n".join(f"{point.entity_name}: {point.display_value}" for point in item.points)
        )
        return view

    @staticmethod
    def _short_name(value: str) -> str:
        cleaned = " ".join(value.split())
        return cleaned if len(cleaned) <= 18 else f"{cleaned[:16]}…"
