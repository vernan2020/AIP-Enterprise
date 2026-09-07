from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.macro_intelligence.presenters.macro_intelligence_presenter import (
    MacroIntelligencePresenter,
)
from aip.ui.modules.macro_intelligence.viewmodels.macro_intelligence_view_model import (
    MacroForecastLabViewModel,
)


class _ForecastLabSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class _ForecastLabWorker(QRunnable):
    def __init__(
        self,
        presenter: MacroIntelligencePresenter,
        indicator_code: str,
        force_refresh: bool,
    ) -> None:
        super().__init__()
        self._presenter = presenter
        self._indicator_code = indicator_code
        self._force_refresh = force_refresh
        self.signals = _ForecastLabSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            result = self._presenter.build_forecast_lab(
                self._indicator_code,
                force_refresh=self._force_refresh,
            )
            self.signals.completed.emit(result)
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


class _ForecastPathChart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._view_model = MacroForecastLabViewModel()
        self.setMinimumHeight(280)

    def set_view_model(self, view_model: MacroForecastLabViewModel) -> None:
        self._view_model = view_model
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        points = self._view_model.points
        if not points:
            painter.setPen(QColor("#718096"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Ejecute los modelos para generar la trayectoria ensemble",
            )
            return

        all_values = [item.forecast for item in points]
        all_values.extend(item.lower_95 for item in points if item.lower_95 is not None)
        all_values.extend(item.upper_95 for item in points if item.upper_95 is not None)
        minimum = min(all_values)
        maximum = max(all_values)
        span = max(maximum - minimum, max(abs(maximum), 1.0) * 0.02)
        minimum -= span * 0.10
        maximum += span * 0.10
        span = maximum - minimum

        left, right, top, bottom = 64.0, 24.0, 25.0, 46.0
        width = max(40.0, self.width() - left - right)
        height = max(40.0, self.height() - top - bottom)

        painter.setPen(QPen(QColor("#E1E7EC"), 1))
        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)
        for index in range(5):
            fraction = index / 4
            y = top + height * fraction
            painter.drawLine(QPointF(left, y), QPointF(left + width, y))
            value = maximum - span * fraction
            painter.setPen(QColor("#637587"))
            suffix = "" if self._view_model.indicator_code == "FX_SELL" else "%"
            prefix = "₡" if self._view_model.indicator_code == "FX_SELL" else ""
            painter.drawText(
                QRectF(4, y - 9, left - 10, 18),
                Qt.AlignmentFlag.AlignRight,
                f"{prefix}{value:.2f}{suffix}",
            )
            painter.setPen(QPen(QColor("#E1E7EC"), 1))

        def coordinates(value: float, index: int) -> QPointF:
            x = left + width * index / max(1, len(points) - 1)
            y = top + height - ((value - minimum) / span) * height
            return QPointF(x, y)

        lower_95 = [
            coordinates(item.lower_95, index)
            for index, item in enumerate(points)
            if item.lower_95 is not None
        ]
        upper_95 = [
            coordinates(item.upper_95, index)
            for index, item in enumerate(points)
            if item.upper_95 is not None
        ]
        if len(lower_95) == len(points) and len(upper_95) == len(points):
            polygon = QPolygonF(upper_95 + list(reversed(lower_95)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(31, 90, 138, 26))
            painter.drawPolygon(polygon)

        lower_80 = [
            coordinates(item.lower_80, index)
            for index, item in enumerate(points)
            if item.lower_80 is not None
        ]
        upper_80 = [
            coordinates(item.upper_80, index)
            for index, item in enumerate(points)
            if item.upper_80 is not None
        ]
        if len(lower_80) == len(points) and len(upper_80) == len(points):
            polygon = QPolygonF(upper_80 + list(reversed(lower_80)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(31, 90, 138, 48))
            painter.drawPolygon(polygon)

        forecast_points = [coordinates(item.forecast, index) for index, item in enumerate(points)]
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#005EB8"), 2.5))
        painter.drawPolyline(QPolygonF(forecast_points))
        painter.setBrush(QColor("#005EB8"))
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        for point in forecast_points:
            painter.drawEllipse(point, 3.5, 3.5)

        painter.setPen(QColor("#53697C"))
        label_indexes = sorted({0, len(points) - 1, 2, 5, 8})
        for index in label_indexes:
            if not 0 <= index < len(points):
                continue
            x = left + width * index / max(1, len(points) - 1)
            painter.drawText(
                QRectF(x - 34, top + height + 8, 68, 18),
                Qt.AlignmentFlag.AlignCenter,
                points[index].period.strftime("%m/%y"),
            )

        title_font = QFont(self.font())
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#17324D"))
        painter.drawText(
            QRectF(left, 2, width, 20),
            Qt.AlignmentFlag.AlignLeft,
            f"Ensemble · {self._view_model.indicator_label} · bandas 80% / 95%",
        )


class MacroForecastLabPanel(QWidget):
    """Lazy, background-loaded multimodel macro forecasting workspace."""

    _INDICATORS = (
        ("TPM", "TPM"),
        ("TBP", "TBP"),
        ("TRI_CRC_12M", "TRI CRC 12M"),
        ("TRI_USD_12M", "TRI USD 12M"),
        ("INFLATION", "Inflación"),
        ("IMAE", "IMAE"),
        ("FX_SELL", "USD / CRC"),
    )

    def __init__(
        self,
        presenter: MacroIntelligencePresenter,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._presenter = presenter
        self._thread_pool = QThreadPool.globalInstance()
        self._worker: _ForecastLabWorker | None = None
        self._loading = False
        self._pending_force = False
        self._view_model = MacroForecastLabViewModel()
        self._kpi_values: dict[str, QLabel] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 8, 4, 4)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("AIP FORECAST LAB · MULTIMODELO")
        title.setStyleSheet("font-size:12px; font-weight:700; color:#17324D;")
        subtitle = QLabel(
            "Backtesting rolling 1/3/6/12M · selección fuera de muestra · ensemble. "
            "No sustituye el escenario institucional aprobado."
        )
        subtitle.setStyleSheet("color:#667788; font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(QLabel("Indicador:"))
        self._indicator_combo = QComboBox()
        for code, label in self._INDICATORS:
            self._indicator_combo.addItem(label, code)
        self._indicator_combo.currentIndexChanged.connect(self._indicator_changed)
        header.addWidget(self._indicator_combo)
        self._run_button = QPushButton("EJECUTAR MODELOS")
        self._run_button.clicked.connect(lambda: self.refresh(force_refresh=True))
        header.addWidget(self._run_button)
        root.addLayout(header)

        kpis = QGridLayout()
        definitions = (
            ("champion", "Champion", "Mejor modelo gobernado"),
            ("confidence", "Confianza", "Score técnico 0-100"),
            ("p1", "Proyección 1M", "Ensemble"),
            ("p3", "Proyección 3M", "Ensemble"),
            ("p6", "Proyección 6M", "Ensemble"),
            ("p12", "Proyección 12M", "Ensemble"),
        )
        for index, definition in enumerate(definitions):
            kpis.addWidget(self._metric_card(*definition), index // 3, index % 3)
        root.addLayout(kpis)

        self._status = QLabel("Seleccione un indicador y ejecute los modelos.")
        self._status.setStyleSheet(
            "padding:6px 9px; background:#F3F8FB; border:1px solid #CFE0EC; "
            "border-radius:6px; color:#53697C;"
        )
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        root.addWidget(tabs, 1)

        trajectory = QWidget()
        trajectory_layout = QVBoxLayout(trajectory)
        self._chart = _ForecastPathChart()
        trajectory_layout.addWidget(self._chart, 1)
        self._forecast_table = self._table(
            ["Horizonte", "Periodo", "Forecast", "Banda 80%", "Banda 95%"]
        )
        self._forecast_table.setMaximumHeight(220)
        trajectory_layout.addWidget(self._forecast_table)
        tabs.addTab(trajectory, "Ensemble · Trayectoria")

        comparison = QWidget()
        comparison_layout = QVBoxLayout(comparison)
        self._model_table = self._table(
            [
                "Rank",
                "Modelo",
                "Familia",
                "Estado",
                "Score",
                "Mejora vs Naive",
                "RMSE 1M",
                "RMSE 3M",
                "RMSE 6M",
                "RMSE 12M",
                "DA 12M",
            ]
        )
        comparison_layout.addWidget(self._model_table)
        tabs.addTab(comparison, "Comparador de modelos")

        ensemble = QWidget()
        ensemble_layout = QHBoxLayout(ensemble)
        self._ensemble_table = self._table(["Modelo", "Familia", "Peso"])
        ensemble_layout.addWidget(self._table_group("Pesos del ensemble", self._ensemble_table), 1)
        explanation = QLabel(
            "Los pesos se derivan del desempeño multi-horizonte fuera de muestra. "
            "NAIVE permanece como benchmark y puede formar parte del ensemble. "
            "Ridge y ElasticNet usan únicamente información observable al origen. "
            "Gradient Boosting se habilita solo si scikit-learn está disponible en el runtime."
        )
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignTop)
        explanation.setStyleSheet("color:#53697C; padding:12px; font-size:10px;")
        group = QGroupBox("Gobierno metodológico")
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(explanation)
        ensemble_layout.addWidget(group, 1)
        tabs.addTab(ensemble, "Ensemble y gobierno")

    def _metric_card(self, key: str, caption: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("forecastLabMetricCard")
        card.setStyleSheet(
            "QFrame#forecastLabMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 7, 10, 7)
        title = QLabel(caption)
        title.setStyleSheet("color:#667788; font-size:8px; border:none;")
        value = QLabel("-")
        value.setStyleSheet("color:#17324D; font-size:13px; font-weight:700; border:none;")
        hint = QLabel(helper)
        hint.setStyleSheet("color:#93A0AC; font-size:8px; border:none;")
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(hint)
        self._kpi_values[key] = value
        return card

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return table

    @staticmethod
    def _table_group(title: str, table: QTableWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(table)
        return group

    @Slot(int)
    def _indicator_changed(self, _index: int) -> None:
        self.refresh(force_refresh=False)

    def ensure_loaded(self) -> None:
        if not self._view_model.points and not self._loading:
            self.refresh(force_refresh=False)

    def refresh(self, *, force_refresh: bool = False) -> None:
        if self._loading:
            self._pending_force = self._pending_force or force_refresh
            return
        code = str(self._indicator_combo.currentData() or "TPM")
        self._loading = True
        self._run_button.setEnabled(False)
        self._run_button.setText("CALCULANDO...")
        self._status.setText(
            f"Ejecutando backtesting multimodelo para {self._indicator_combo.currentText()}..."
        )
        worker = _ForecastLabWorker(self._presenter, code, force_refresh)
        worker.signals.completed.connect(self._completed)
        worker.signals.failed.connect(self._failed)
        self._worker = worker
        self._thread_pool.start(worker)

    @Slot(object)
    def _completed(self, result: object) -> None:
        if not isinstance(result, MacroForecastLabViewModel):
            self._failed("Resultado inesperado del Forecast Lab")
            return
        self._view_model = result
        self._bind(result)
        self._finish()

    @Slot(str)
    def _failed(self, message: str) -> None:
        self._status.setText(f"Forecast Lab no disponible · {message}")
        self._finish()

    def _finish(self) -> None:
        self._loading = False
        self._worker = None
        self._run_button.setEnabled(True)
        self._run_button.setText("EJECUTAR MODELOS")
        if self._pending_force:
            self._pending_force = False
            self.refresh(force_refresh=True)

    def _bind(self, view_model: MacroForecastLabViewModel) -> None:
        self._kpi_values["champion"].setText(
            f"{view_model.champion_model} · {view_model.champion_family}"
        )
        self._kpi_values["confidence"].setText(view_model.confidence_score)
        self._kpi_values["p1"].setText(view_model.projection_1m)
        self._kpi_values["p3"].setText(view_model.projection_3m)
        self._kpi_values["p6"].setText(view_model.projection_6m)
        self._kpi_values["p12"].setText(view_model.projection_12m)
        origin = (
            view_model.forecast_origin.strftime("%d/%m/%Y") if view_model.forecast_origin else "-"
        )
        self._status.setText(
            f"Estado {view_model.status} · origen {origin} · "
            f"{view_model.historical_observations} observaciones · "
            f"{view_model.diagnostic or 'sin diagnósticos'}"
        )
        self._chart.set_view_model(view_model)
        self._bind_forecast_table(view_model)
        self._bind_model_table(view_model)
        self._bind_ensemble_table(view_model)

    def _bind_forecast_table(self, view_model: MacroForecastLabViewModel) -> None:
        self._forecast_table.setRowCount(len(view_model.points))
        for row, point in enumerate(view_model.points):
            values = (
                f"{point.horizon}M",
                point.period.strftime("%m/%Y"),
                self._value(view_model.indicator_code, point.forecast),
                self._interval(view_model.indicator_code, point.lower_80, point.upper_80),
                self._interval(view_model.indicator_code, point.lower_95, point.upper_95),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column >= 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._forecast_table.setItem(row, column, item)

    def _bind_model_table(self, view_model: MacroForecastLabViewModel) -> None:
        self._model_table.setRowCount(len(view_model.models))
        for row, model in enumerate(view_model.models):
            metrics = {item.horizon: item for item in model.metrics}
            values = (
                model.rank,
                model.model_name,
                model.family,
                model.status,
                model.weighted_score,
                model.improvement_vs_naive,
                metrics.get("1M").rmse if metrics.get("1M") else "-",
                metrics.get("3M").rmse if metrics.get("3M") else "-",
                metrics.get("6M").rmse if metrics.get("6M") else "-",
                metrics.get("12M").rmse if metrics.get("12M") else "-",
                metrics.get("12M").directional_accuracy if metrics.get("12M") else "-",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {0, 4, 5, 6, 7, 8, 9, 10}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if model.rank == "1":
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self._model_table.setItem(row, column, item)

    def _bind_ensemble_table(self, view_model: MacroForecastLabViewModel) -> None:
        self._ensemble_table.setRowCount(len(view_model.ensemble))
        for row, model in enumerate(view_model.ensemble):
            for column, value in enumerate((model.model_name, model.family, model.weight)):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._ensemble_table.setItem(row, column, item)

    @staticmethod
    def _value(code: str, value: float) -> str:
        return f"₡{value:,.2f}" if code == "FX_SELL" else f"{value:,.2f}%"

    @classmethod
    def _interval(
        cls,
        code: str,
        lower: float | None,
        upper: float | None,
    ) -> str:
        if lower is None or upper is None:
            return "-"
        return f"{cls._value(code, lower)} – {cls._value(code, upper)}"
