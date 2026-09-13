from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QValueAxis
from PySide6.QtCore import QDateTime, QMargins, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialMetricHistorySeriesView,
)


class FinancialHistoryPanel(QWidget):
    """Small-multiple charts for the monthly financial KPI history."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("financialHistoryPanel")
        self._grid = QGridLayout()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("EVOLUCIÓN HISTÓRICA DE KPIs")
        title.setStyleSheet("font-size:13px; font-weight:700; color:#142E46;")
        subtitle = QLabel(
            "Últimos 12 cortes mensuales oficiales disponibles para la entidad seleccionada"
        )
        subtitle.setStyleSheet("color:#667788; font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        heading.addLayout(title_box)
        heading.addStretch(1)
        source = QLabel("Fuente: SUGEF")
        source.setStyleSheet(
            "padding:5px 9px; background:#F3F8FB; border:1px solid #CFE0EC; "
            "border-radius:6px; color:#314A5E; font-weight:600;"
        )
        heading.addWidget(source)
        root.addLayout(heading)

        note = QLabel(
            "Los faltantes permanecen N/D y generan cortes en la línea. "
            "El Resultado neto corresponde al saldo acumulado reportado por SUGEF en cada corte."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "padding:6px 9px; background:#FFF9E8; border:1px solid #EAD9A2; "
            "border-radius:6px; color:#67572C; font-size:8px;"
        )
        root.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._grid = QGridLayout(content)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(10)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(1, 1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.setStyleSheet(
            "QFrame#historyMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:9px;}"
        )

    def bind_history(self, series: tuple[FinancialMetricHistorySeriesView, ...]) -> None:
        self._clear_grid()
        if not series:
            empty = QLabel(
                "No hay histórico mensual disponible para la entidad y el corte seleccionados."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color:#667788; padding:40px; font-size:10px;")
            self._grid.addWidget(empty, 0, 0, 1, 2)
            return

        for index, item in enumerate(series):
            self._grid.addWidget(self._history_card(item), index // 2, index % 2)

    def _clear_grid(self) -> None:
        while self._grid.count():
            child = self._grid.takeAt(0)
            if child is None:
                break
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _history_card(self, item: FinancialMetricHistorySeriesView) -> QFrame:
        card = QFrame()
        card.setObjectName("historyMetricCard")
        card.setMinimumHeight(285)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 9, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        title = QLabel(item.label)
        title.setStyleSheet("font-size:11px; font-weight:700; color:#142E46; border:none;")
        top.addWidget(title)
        top.addStretch(1)
        coverage = QLabel(f"{item.available_points}/{item.total_points} cortes")
        coverage.setStyleSheet("color:#667788; font-size:8px; border:none;")
        top.addWidget(coverage)
        layout.addLayout(top)

        metrics = QHBoxLayout()
        latest = QLabel(item.latest_value)
        latest.setStyleSheet("font-size:15px; font-weight:700; color:#005EB8; border:none;")
        metrics.addWidget(latest)
        metrics.addStretch(1)
        change = QLabel(item.period_change)
        change.setStyleSheet("font-size:8px; font-weight:600; color:#52687A; border:none;")
        metrics.addWidget(change)
        layout.addLayout(metrics)

        chart_view = self._chart_view(item)
        layout.addWidget(chart_view, 1)

        source = QLabel(f"Cuenta/fuente: {item.source_account}")
        source.setWordWrap(True)
        source.setStyleSheet("color:#8393A3; font-size:7px; border:none;")
        layout.addWidget(source)
        return card

    def _chart_view(self, item: FinancialMetricHistorySeriesView) -> QChartView:
        chart = QChart()
        chart.legend().hide()
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(2, 2, 2, 2))
        chart.setPlotAreaBackgroundVisible(False)

        point_dates = tuple(
            QDateTime.fromString(point.iso_date, Qt.DateFormat.ISODate) for point in item.points
        )
        available_values = tuple(point.value for point in item.points if point.value is not None)

        axis_x = QDateTimeAxis()
        axis_x.setFormat("MMM-yy")
        axis_x.setLabelsAngle(-35)
        axis_x.setTickCount(min(6, max(2, len(item.points))))
        axis_x.setGridLineVisible(False)

        if point_dates:
            start = point_dates[0]
            end = point_dates[-1]
            if start == end:
                start = start.addDays(-15)
                end = end.addDays(15)
            axis_x.setRange(start, end)

        axis_y = QValueAxis()
        axis_y.setTitleText(item.unit)
        axis_y.setLabelFormat("%.2f" if item.unit == "%" else "%.0f")
        axis_y.setTickCount(5)
        axis_y.setGridLineVisible(True)
        axis_y.setMinorGridLineVisible(False)

        if available_values:
            minimum = min(available_values)
            maximum = max(available_values)
            spread = maximum - minimum
            baseline = max(abs(minimum), abs(maximum), 1.0)
            padding = max(spread * 0.12, baseline * 0.03, 0.25 if item.unit == "%" else 1.0)
            axis_y.setRange(minimum - padding, maximum + padding)
        else:
            axis_y.setRange(0.0, 1.0)

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

        segment: QLineSeries | None = None
        tooltip_lines: list[str] = []
        for point, point_date in zip(item.points, point_dates, strict=True):
            tooltip_lines.append(f"{point.date_label}: {point.display_value}")
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
        view.setMinimumHeight(185)
        view.setToolTip("\n".join(tooltip_lines))
        return view
