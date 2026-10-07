from __future__ import annotations

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QChartView,
    QHorizontalBarSeries,
    QPieSeries,
    QPieSlice,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QCursor, QPainter
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QToolTip, QVBoxLayout, QWidget

from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    PeerChartPointView,
    PeerChartSeriesView,
)
from aip.ui.widgets.chart_tooltip import build_chart_tooltip


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
        bar_set.setColor(QColor("#005EB8"))
        bar_set.setBorderColor(QColor("#00345F"))
        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setBarWidth(0.68)
        chart.addSeries(series)

        categories = QBarCategoryAxis()
        categories.append([cls._short_name(point.entity_name) for point in points])
        category_font = categories.labelsFont()
        category_font.setPointSize(8)
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

        chart.addAxis(categories, Qt.AlignmentFlag.AlignLeft)
        chart.addAxis(value_axis, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(categories)
        series.attachAxis(value_axis)

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(285)

        def show_bar_tooltip(status: bool, index: int) -> None:
            if not status or not 0 <= index < len(points):
                QToolTip.hideText()
                return
            point = points[index]
            tooltip = build_chart_tooltip(
                point.entity_name,
                (
                    ("Indicador", item.label),
                    ("Valor", point.display_value),
                    ("Unidad", item.unit),
                    ("Entidad seleccionada", "Sí" if point.selected else "No"),
                ),
                note="Comparación relativa dentro del universo visible.",
            )
            QToolTip.showText(QCursor.pos(), tooltip, view)

        bar_set.hovered.connect(show_bar_tooltip)
        return view

    @classmethod
    def _pie_chart(cls, item: PeerChartSeriesView) -> QChartView:
        chart = QChart()
        chart.setTitle(item.label)
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(4, 2, 4, 2))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
        series = QPieSeries()
        palette = ("#005EB8", "#00A9E0", "#40C1AC", "#FF8200", "#73B3DD", "#2B9E8B")
        slice_points: list[tuple[QPieSlice, PeerChartPointView]] = []
        for index, point in enumerate(item.points):
            slice_ = series.append(cls._short_name(point.entity_name), point.value)
            slice_.setColor(QColor(palette[index % len(palette)]))
            slice_points.append((slice_, point))
            if index < 10 or point.selected:
                slice_.setLabel(f"{cls._short_name(point.entity_name)} {point.value:.1f}%")
                slice_.setLabelVisible(True)
            if point.selected:
                slice_.setExploded(True)
        chart.addSeries(series)
        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(245)

        for slice_, point in slice_points:
            tooltip = build_chart_tooltip(
                point.entity_name,
                (
                    ("Indicador", item.label),
                    ("Participación", point.display_value),
                    ("Entidad seleccionada", "Sí" if point.selected else "No"),
                ),
                note="Composición del total mostrado.",
            )
            slice_.hovered.connect(
                lambda state, text=tooltip: (
                    QToolTip.showText(QCursor.pos(), text, view)
                    if state
                    else QToolTip.hideText()
                )
            )
        return view

    @staticmethod
    def _short_name(value: str) -> str:
        cleaned = " ".join(value.split())
        return cleaned if len(cleaned) <= 18 else f"{cleaned[:16]}…"
