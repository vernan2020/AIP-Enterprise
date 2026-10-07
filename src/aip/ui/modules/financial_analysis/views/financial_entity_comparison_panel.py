from __future__ import annotations

from calendar import monthrange
from datetime import date

from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QValueAxis
from PySide6.QtCore import QDateTime, QMargins, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
    FinancialEntityComparisonSeriesView,
    FinancialEntityComparisonViewModel,
)


class FinancialEntityComparisonPanel(QWidget):
    """Compare one financial series across one to five SUGEF entities."""

    compareRequested = Signal(object, str, str, object, object)
    _MAX_ENTITIES = 5

    def __init__(self) -> None:
        super().__init__()
        self._chart_view: QChartView | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("COMPARATIVO GRÁFICO MULTIENTIDAD")
        title.setStyleSheet("font-size:13px; font-weight:700; color:#142E46;")
        subtitle = QLabel(
            "Seleccione entre 1 y 5 entidades y una misma serie para compararlas "
            "sobre un eje temporal común."
        )
        subtitle.setStyleSheet("color:#667788; font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        heading.addLayout(title_box)
        heading.addStretch(1)
        self._selection_summary = QLabel("0/5 entidades")
        self._selection_summary.setStyleSheet(
            "padding:5px 9px; background:#F3F8FB; border:1px solid #CFE0EC; "
            "border-radius:6px; color:#314A5E; font-weight:600;"
        )
        heading.addWidget(self._selection_summary)
        root.addLayout(heading)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        controls.addWidget(QLabel("Serie:"))
        self._series_selector = QComboBox()
        self._series_selector.setMinimumWidth(420)
        self._series_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._series_selector.setMinimumContentsLength(48)
        controls.addWidget(self._series_selector, 1)
        controls.addWidget(QLabel("Horizonte:"))
        self._horizon_selector = QComboBox()
        self._horizon_selector.addItem("12 meses", "12M")
        self._horizon_selector.addItem("24 meses", "24M")
        self._horizon_selector.addItem("36 meses", "36M")
        self._horizon_selector.addItem("5 años", "5Y")
        self._horizon_selector.addItem("Toda la historia disponible", "ALL")
        self._horizon_selector.addItem("Personalizado", "CUSTOM")
        self._horizon_selector.setCurrentIndex(2)
        self._horizon_selector.currentIndexChanged.connect(self._horizon_changed)
        controls.addWidget(self._horizon_selector)
        self._compare_button = QPushButton("Graficar comparación")
        self._compare_button.clicked.connect(self._request_comparison)
        controls.addWidget(self._compare_button)
        root.addLayout(controls)

        self._custom_range = QWidget()
        custom_controls = QHBoxLayout(self._custom_range)
        custom_controls.setContentsMargins(0, 0, 0, 0)
        custom_controls.setSpacing(6)
        custom_controls.addWidget(QLabel("Desde:"))
        self._custom_from = QLineEdit()
        self._custom_from.setPlaceholderText("MM/AAAA")
        self._custom_from.setMaximumWidth(90)
        custom_controls.addWidget(self._custom_from)
        custom_controls.addWidget(QLabel("Hasta:"))
        self._custom_to = QLineEdit()
        self._custom_to.setPlaceholderText("MM/AAAA")
        self._custom_to.setMaximumWidth(90)
        custom_controls.addWidget(self._custom_to)
        custom_controls.addStretch(1)
        self._custom_range.setVisible(False)
        root.addWidget(self._custom_range)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        selector_host = QWidget()
        selector_layout = QVBoxLayout(selector_host)
        selector_layout.setContentsMargins(0, 0, 4, 0)
        selector_layout.setSpacing(5)
        selector_layout.addWidget(QLabel("Entidades SUGEF · máximo 5"))
        self._entity_search = QLineEdit()
        self._entity_search.setPlaceholderText("Buscar entidad…")
        self._entity_search.textChanged.connect(self._apply_entity_filter)
        selector_layout.addWidget(self._entity_search)
        self._entity_list = QListWidget()
        self._entity_list.itemChanged.connect(self._entity_checked)
        selector_layout.addWidget(self._entity_list, 1)
        splitter.addWidget(selector_host)

        chart_host = QWidget()
        self._chart_layout = QVBoxLayout(chart_host)
        self._chart_layout.setContentsMargins(4, 0, 0, 0)
        self._chart_layout.setSpacing(4)
        self._status = QLabel(
            "Seleccione las entidades, escoja una serie y presione “Graficar comparación”."
        )
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color:#52687A; font-size:9px;")
        self._chart_layout.addWidget(self._status)
        splitter.addWidget(chart_host)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 7)
        splitter.setSizes([280, 950])
        root.addWidget(splitter, 1)

    def bind_context(self, view_model: FinancialAnalysisViewModel) -> None:
        current_series = self._series_selector.currentData()
        checked = set(self.selected_entity_ids())
        if not checked and view_model.selected_entity_id:
            checked.add(view_model.selected_entity_id)

        self._entity_list.blockSignals(True)
        try:
            self._entity_list.clear()
            for entity_id, entity_name in view_model.entities:
                item = QListWidgetItem(entity_name)
                item.setData(Qt.ItemDataRole.UserRole, entity_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if entity_id in checked else Qt.CheckState.Unchecked
                )
                self._entity_list.addItem(item)
        finally:
            self._entity_list.blockSignals(False)

        self._series_selector.blockSignals(True)
        try:
            self._series_selector.clear()
            seen: set[str] = set()
            for prefix, series in (
                ("KPI", view_model.metric_history),
                ("Cuenta", view_model.statement_history),
            ):
                for item in series:
                    if not item.code or item.code in seen:
                        continue
                    seen.add(item.code)
                    self._series_selector.addItem(f"{prefix} · {item.label}", item.code)
            if current_series:
                index = self._series_selector.findData(current_series)
                if index >= 0:
                    self._series_selector.setCurrentIndex(index)
        finally:
            self._series_selector.blockSignals(False)

        self._apply_entity_filter()
        self._update_selection_summary()

    def selected_entity_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        for index in range(self._entity_list.count()):
            item = self._entity_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                entity_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if entity_id:
                    selected.append(entity_id)
        return tuple(selected)

    def _entity_checked(self, changed: QListWidgetItem) -> None:
        selected = self.selected_entity_ids()
        if len(selected) > self._MAX_ENTITIES:
            self._entity_list.blockSignals(True)
            try:
                changed.setCheckState(Qt.CheckState.Unchecked)
            finally:
                self._entity_list.blockSignals(False)
            self._status.setText("Máximo permitido: 5 entidades por gráfico.")
        self._update_selection_summary()

    def _update_selection_summary(self) -> None:
        count = len(self.selected_entity_ids())
        self._selection_summary.setText(f"{count}/5 entidades")

    def _apply_entity_filter(self, *_args: object) -> None:
        search = self._entity_search.text().strip().casefold()
        for index in range(self._entity_list.count()):
            item = self._entity_list.item(index)
            item.setHidden(bool(search) and search not in item.text().casefold())

    def _horizon_changed(self, *_args: object) -> None:
        self._custom_range.setVisible(str(self._horizon_selector.currentData() or "") == "CUSTOM")

    @staticmethod
    def _parse_month(value: str, *, month_end: bool) -> date:
        parts = value.strip().split("/")
        if len(parts) != 2:
            raise ValueError("Use el formato MM/AAAA.")
        month, year = (int(item) for item in parts)
        if month < 1 or month > 12 or year < 1900:
            raise ValueError("Mes o año inválido.")
        day = monthrange(year, month)[1] if month_end else 1
        return date(year, month, day)

    def set_loading(self, loading: bool) -> None:
        self._compare_button.setEnabled(not loading)
        self._horizon_selector.setEnabled(not loading)
        self._series_selector.setEnabled(not loading)
        self._entity_list.setEnabled(not loading)
        self._status.setText("Cargando comparación…" if loading else self._status.text())

    def _request_comparison(self) -> None:
        entity_ids = self.selected_entity_ids()
        if not entity_ids:
            self._status.setText("Seleccione al menos una entidad.")
            return
        series_code = str(self._series_selector.currentData() or "")
        if not series_code:
            self._status.setText("No hay una serie disponible para comparar.")
            return
        horizon = str(self._horizon_selector.currentData() or "36M")
        custom_from = None
        custom_to = None
        if horizon == "CUSTOM":
            try:
                custom_from = self._parse_month(self._custom_from.text(), month_end=False)
                custom_to = self._parse_month(self._custom_to.text(), month_end=True)
            except (TypeError, ValueError) as exc:
                self._status.setText(f"Rango personalizado inválido: {exc}")
                return
            if custom_from > custom_to:
                self._status.setText("Rango personalizado inválido: Desde es posterior a Hasta.")
                return
        self.set_loading(True)
        self.compareRequested.emit(entity_ids, series_code, horizon, custom_from, custom_to)

    def bind_comparison(self, view_model: FinancialEntityComparisonViewModel) -> None:
        self.set_loading(False)
        self._clear_chart()
        if not view_model.entities:
            message = " · ".join(view_model.diagnostics) or "No hay series comparables disponibles."
            self._status.setText(message)
            return

        entity_count = len(view_model.entities)
        self._status.setText(
            f"{view_model.label} · {entity_count} entidad"
            f"{'es' if entity_count != 1 else ''} · {view_model.unit}"
        )
        if view_model.diagnostics:
            self._status.setToolTip("\n".join(view_model.diagnostics))
        else:
            self._status.setToolTip("")

        self._chart_view = self._build_chart(view_model)
        self._chart_layout.addWidget(self._chart_view, 1)

    def _clear_chart(self) -> None:
        if self._chart_view is not None:
            self._chart_layout.removeWidget(self._chart_view)
            self._chart_view.deleteLater()
            self._chart_view = None

    @staticmethod
    def _build_chart(view_model: FinancialEntityComparisonViewModel) -> QChartView:
        chart = QChart()
        chart.setTitle(view_model.label)
        chart.setBackgroundVisible(False)
        chart.setMargins(QMargins(4, 4, 4, 4))
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignTop)

        all_dates: list[QDateTime] = []
        all_values: list[float] = []
        prepared: list[tuple[FinancialEntityComparisonSeriesView, tuple[QDateTime, ...]]] = []
        for entity in view_model.entities:
            dates = tuple(
                QDateTime.fromString(point.iso_date, Qt.DateFormat.ISODate)
                for point in entity.points
            )
            prepared.append((entity, dates))
            all_dates.extend(dates)
            all_values.extend(point.value for point in entity.points if point.value is not None)

        axis_x = QDateTimeAxis()
        axis_x.setFormat("MMM-yy")
        axis_x.setLabelsAngle(-30)
        axis_x.setGridLineVisible(False)
        axis_x.setTickCount(min(8, max(2, len({date.toMSecsSinceEpoch() for date in all_dates}))))
        if all_dates:
            start = min(all_dates, key=lambda item: item.toMSecsSinceEpoch())
            end = max(all_dates, key=lambda item: item.toMSecsSinceEpoch())
            if start == end:
                start = start.addDays(-15)
                end = end.addDays(15)
            axis_x.setRange(start, end)

        axis_y = QValueAxis()
        axis_y.setTitleText(view_model.unit)
        axis_y.setLabelFormat("%.2f" if view_model.unit in {"%", "Valor"} else "%.0f")
        axis_y.setTickCount(6)
        if all_values:
            minimum = min(all_values)
            maximum = max(all_values)
            spread = maximum - minimum
            baseline = max(abs(minimum), abs(maximum), 1.0)
            padding = max(spread * 0.12, baseline * 0.03, 0.25)
            axis_y.setRange(minimum - padding, maximum + padding)
        else:
            axis_y.setRange(0.0, 1.0)

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

        tooltip_lines: list[str] = []
        palette = ("#005EB8", "#00A9E0", "#40C1AC", "#FF8200", "#7A6FD0")
        for entity_index, (entity, dates) in enumerate(prepared):
            segment: QLineSeries | None = None
            segment_index = 0
            for point, point_date in zip(entity.points, dates, strict=True):
                tooltip_lines.append(
                    f"{entity.entity_name} · {point.date_label}: {point.display_value}"
                )
                if point.value is None:
                    segment = None
                    continue
                if segment is None:
                    segment = QLineSeries()
                    segment.setName(entity.entity_name if segment_index == 0 else "")
                    segment.setPointsVisible(True)
                    segment.setMarkerSize(6.0)
                    pen = QPen(QColor(palette[entity_index % len(palette)]), 2.6)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    segment.setPen(pen)
                    chart.addSeries(segment)
                    segment.attachAxis(axis_x)
                    segment.attachAxis(axis_y)
                    if segment_index > 0:
                        for marker in chart.legend().markers(segment):
                            marker.setVisible(False)
                    segment_index += 1
                segment.append(float(point_date.toMSecsSinceEpoch()), point.value)

        chart.setPlotAreaBackgroundVisible(True)
        chart.setPlotAreaBackgroundBrush(QColor("#F8FBFD"))
        chart.setPlotAreaBackgroundPen(QPen(QColor("#E1EAF0"), 1))
        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(430)
        view.setToolTip("\n".join(tooltip_lines))
        return view
