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
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

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

        self._chart_context = QLabel("Seleccione un indicador para comparar entidades.")
        self._chart_context.setWordWrap(True)
        self._chart_context.setStyleSheet("color:#52687A; font-size:9px; padding:4px 0;")
        root.addWidget(self._chart_context)

        self._hover_detail = QLabel(
            "Detalle al pasar el cursor: seleccione una barra o un sector."
        )
        self._hover_detail.setObjectName("financialPeerHoverDetail")
        self._hover_detail.setTextFormat(Qt.TextFormat.PlainText)
        self._hover_detail.setWordWrap(True)
        self._hover_detail.setStyleSheet(
            "color:#17324D; background:#EAF4FC; border:1px solid #C7DDEB; "
            "border-radius:6px; padding:6px 9px; font-weight:600;"
        )
        root.addWidget(self._hover_detail)

        # Preserve legibility of up to 15 entity labels rather than compress
        # every chart into a fixed-height panel when the workspace is resized.
        self._chart_scroll = QScrollArea()
        self._chart_scroll.setWidgetResizable(True)
        self._chart_scroll.setFrameShape(QFrame.Shape.NoFrame)
        chart_container = QWidget()
        self._chart_host = QVBoxLayout(chart_container)
        self._chart_host.setContentsMargins(0, 0, 0, 0)
        self._chart_host.setSpacing(0)
        self._chart_scroll.setWidget(chart_container)
        root.addWidget(self._chart_scroll, 1)

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
        self._hover_detail.setText(
            "Detalle al pasar el cursor: seleccione una barra o un sector."
        )
        index = self._selector.currentIndex()
        if index < 0 or index >= len(self._series):
            self._summary.setText("Sin datos comparables")
            self._chart_context.setText("No hay información comparable para este corte.")
            return
        item = self._series[index]
        if item.chart_type == "PIE":
            self._summary.setText(f"{len(item.points)} entidades · {item.unit}")
            self._chart_context.setText(
                "Composición del universo publicado. Pase el cursor para ver "
                "la entidad y el valor completo sin abreviaturas."
            )
        else:
            visible = min(len(item.points), self._MAX_BAR_ENTITIES)
            self._summary.setText(f"{visible}/{len(item.points)} entidades · {item.unit}")
            sign_note = (
                " Los valores negativos mantienen su signo."
                if any(point.value < 0 for point in item.points)
                else ""
            )
            self._chart_context.setText(
                "Orden descendente por magnitud; máximo 15 entidades. "
                "La entidad seleccionada siempre se incluye y se identifica con ●."
                + sign_note
            )
        self._chart_view = (
            self._pie_chart(item, detail_label=self._hover_detail)
            if item.chart_type == "PIE"
            else self._bar_chart(item, detail_label=self._hover_detail)
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

    @staticmethod
    def _point_readout(point: PeerChartPointView, item: PeerChartSeriesView) -> str:
        selected = " · Entidad seleccionada" if point.selected else ""
        return f"{point.entity_name} · {item.label}: {point.display_value}{selected}"

    @classmethod
    def _bar_chart(
        cls, item: PeerChartSeriesView, *, detail_label: QLabel | None = None
    ) -> QChartView:
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
        categories.append(
            [
                ("● " if point.selected else "") + cls._short_name(point.entity_name)
                for point in points
            ]
        )
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
        view.setMinimumHeight(max(285, 75 + 32 * len(points)))

        def show_bar_tooltip(status: bool, index: int) -> None:
            if not status or not 0 <= index < len(points):
                QToolTip.hideText()
                return
            point = points[index]
            if detail_label is not None:
                detail_label.setText(cls._point_readout(point, item))
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
    def _pie_chart(
        cls, item: PeerChartSeriesView, *, detail_label: QLabel | None = None
    ) -> QChartView:
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
            def on_hover(
                state: bool,
                *,
                text: str = tooltip,
                source_point: PeerChartPointView = point,
            ) -> None:
                if not state:
                    QToolTip.hideText()
                    return
                if detail_label is not None:
                    detail_label.setText(cls._point_readout(source_point, item))
                QToolTip.showText(QCursor.pos(), text, view)

            slice_.hovered.connect(on_hover)
        return view

    @staticmethod
    def _short_name(value: str) -> str:
        cleaned = " ".join(value.split())
        return cleaned if len(cleaned) <= 18 else f"{cleaned[:16]}…"
