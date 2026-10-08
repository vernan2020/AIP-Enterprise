from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.portfolio.models.portfolio_dashboard_point import PortfolioDashboardPoint
from aip.ui.modules.portfolio.models.portfolio_history_point import PortfolioHistorySeries
from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel
from aip.ui.modules.portfolio.views.portfolio_details_view import PortfolioDetailsView
from aip.ui.modules.portfolio.views.portfolio_history_view import PortfolioHistoryView
from aip.ui.modules.portfolio.views.portfolio_positions_view import PortfolioPositionsView
from aip.ui.modules.portfolio.views.portfolio_summary_view import PortfolioSummaryView
from aip.ui.modules.portfolio.views.portfolio_toolbar import PortfolioToolbar
from aip.ui.modules.portfolio.views.portfolio_valuation_comparison_view import (
    PortfolioValuationComparisonView,
)
from aip.ui.modules.portfolio.widgets.portfolio_dashboard_chart import (
    PortfolioDashboardBarChart,
    PortfolioDashboardColumnChart,
    PortfolioDashboardDonutChart,
)
from aip.ui.modules.portfolio.widgets.portfolio_filter_panel import PortfolioFilterPanel
from aip.ui.modules.portfolio.widgets.portfolio_status_badge import PortfolioStatusBadge
from aip.ui.services.export_service import ExcelSheet, TableExportService


class _PortfolioHistoryWorker(QObject):
    result_ready = Signal(int, str, str, object)
    failed = Signal(int, str, str, str)

    def __init__(self, presenter: PortfolioPresenter) -> None:
        super().__init__()
        self._presenter = presenter

    @Slot(int, str, str)
    def load(self, request_id: int, cutoff: str, sampling: str) -> None:
        try:
            series = self._presenter.load_history(end_date=cutoff, sampling=sampling)
            self.result_ready.emit(request_id, cutoff, sampling, series)
        except Exception as exc:
            self.failed.emit(request_id, cutoff, sampling, str(exc))


class PortfolioView(QWidget):
    """Panel institucional del portafolio y explorador de posiciones."""

    history_load_requested = Signal(int, str, str)

    def __init__(self, presenter: PortfolioPresenter | None = None) -> None:
        super().__init__()
        self.setObjectName("portfolioWorkspace")
        self._presenter = presenter or PortfolioPresenter()
        self._view_model = self._presenter.build_view_model()
        self._toolbar = PortfolioToolbar()
        self._summary = PortfolioSummaryView(self._view_model.summary)
        self._filter_panel = PortfolioFilterPanel()
        self._positions = PortfolioPositionsView(self._view_model.rows)
        self._details = PortfolioDetailsView(
            self._view_model.rows[0] if self._view_model.rows else None
        )
        self._history = PortfolioHistoryView()
        self._valuation_comparison = PortfolioValuationComparisonView()
        self._status_bar = PortfolioStatusBadge("Portafolio listo")
        self._content_splitter: QSplitter | None = None
        self._positions_page: QWidget | None = None
        self._history_loaded_for: tuple[str, str] | None = None
        self._history_worker_thread: QThread | None = None
        self._history_worker: _PortfolioHistoryWorker | None = None
        self._history_loading_request: tuple[int, str, str] | None = None
        self._history_pending_request: tuple[int, str, str] | None = None
        self._history_request_sequence = 0
        self._history_requested_sampling = "monthly"
        self._closing = False
        self._kpis: dict[str, QLabel] = {}
        self._build_ui()
        self._toolbar.actions()[0].triggered.connect(self.refresh)
        self._history.sampling_requested.connect(self._load_history)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._bind_dashboard(self._view_model)

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D7E6EF; border-radius:14px; margin-top:10px; "
            "font-weight:700; color:#173B6C; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:14px; padding:0 6px; "
            "background:#FFFFFF;}"
        )

    @staticmethod
    def _translate_status(value: str) -> str:
        return {
            "ready": "listo",
            "loaded": "cargado",
            "loading": "cargando",
            "error": "error",
            "available": "disponible",
            "unavailable": "no disponible",
        }.get(value.strip().casefold(), value)

    def _metric_card(self, key: str, title: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("portfolioMetricCard")
        card.setMinimumHeight(112)
        card.setStyleSheet(
            "QFrame#portfolioMetricCard {"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #073F84, stop:0.52 #0A6ED1, stop:1 #12B7E7); "
            "border:1px solid #2C8CE0; border-radius:14px;"
            "} QFrame#portfolioMetricCard:hover {border:1px solid #73B3DD;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        caption = QLabel(title)
        caption.setStyleSheet("color:#E8F6FF; font-size:10px; font-weight:700; border:none;")
        value = QLabel("-")
        value_font = QFont()
        value_font.setPointSize(16)
        value_font.setBold(True)
        value.setFont(value_font)
        value.setStyleSheet("color:#FFFFFF; border:none;")
        hint = QLabel(helper)
        hint.setStyleSheet("color:#D1ECFA; font-size:8px; border:none;")
        layout.addWidget(caption)
        layout.addWidget(value)
        layout.addWidget(hint)
        self._kpis[key] = value
        return card

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(
            "QWidget#portfolioWorkspace {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #F4FAFE,stop:1 #EEF5F9);}"
            "QTabWidget::pane {border:0; background:transparent;}"
            "QTabBar::tab {background:transparent; color:#506A84;}"
            "QTabBar::tab:selected {color:#0B57B7;}"
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 12, 18, 16)
        layout.setSpacing(10)
        scroll.setWidget(content)
        root.addWidget(scroll)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Portafolio")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QLabel("Resumen ejecutivo")
        subtitle.setStyleSheet("color:#244A7A; font-size:12px; font-weight:700;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        vision = QLabel("Visión integral del portafolio de inversiones")
        vision.setStyleSheet("color:#6B7F93; font-size:9px;")
        title_box.addWidget(vision)
        header.addLayout(title_box)
        header.addStretch(1)
        self._date_label = QLabel("-")
        self._date_label.setStyleSheet(
            "padding:7px 11px; background:#F3F6F9; border:1px solid #D7E0E8; "
            "border-radius:6px; font-weight:600;"
        )
        header.addWidget(self._date_label)
        layout.addLayout(header)

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(7)
        kpi_grid.setVerticalSpacing(7)
        definitions = (
            ("market_value", "Valor de mercado", "Valor de mercado CRC"),
            ("yield", "TIR ponderada", "Rendimiento ponderado"),
            ("duration", "Duración modificada", "Sensibilidad del portafolio"),
            ("hqla", "HQLA", "Capacidad líquida elegible"),
            ("issuer_count", "Emisores", "Activos en portafolio"),
            ("hhi", "Concentración por emisor", "Índice Herfindahl"),
        )
        for index, definition in enumerate(definitions):
            card = self._metric_card(*definition)
            kpi_grid.addWidget(card, 0, index)
        for column in range(6):
            kpi_grid.setColumnStretch(column, 1)
        layout.addLayout(kpi_grid)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab {padding:8px 18px; font-weight:600;}"
            "QTabBar::tab:selected {color:#174E78; border-bottom:2px solid #1F5A8A;}"
        )
        layout.addWidget(self._tabs, 1)
        self._build_dashboard_tab()
        self._tabs.addTab(self._history, "Histórico KPIs")
        self._tabs.addTab(self._valuation_comparison, "Ganancia / pérdida")
        self._build_positions_tab()

        layout.addWidget(self._status_bar)

    def _build_dashboard_tab(self) -> None:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        issuer_group = QGroupBox("Concentración por emisor · 10 principales")
        issuer_group.setStyleSheet(self._group_style())
        issuer_layout = QVBoxLayout(issuer_group)
        self._issuer_chart = PortfolioDashboardBarChart()
        issuer_layout.addWidget(self._issuer_chart)
        self._issuer_concentration = QLabel("Concentración Top 3 / Top 5: N/D")
        self._issuer_concentration.setStyleSheet(
            "color:#315468; font-size:10px; font-weight:600;"
        )
        issuer_layout.addWidget(self._issuer_concentration)
        self._add_excel_action(issuer_layout, "issuer", "Concentración por emisor")
        layout.addWidget(issuer_group, 0, 0)

        duration_group = QGroupBox("Distribución por duración")
        duration_group.setStyleSheet(self._group_style())
        duration_layout = QVBoxLayout(duration_group)
        self._duration_chart = PortfolioDashboardColumnChart()
        duration_layout.addWidget(self._duration_chart)
        self._add_excel_action(duration_layout, "duration", "Distribución por duración")
        layout.addWidget(duration_group, 0, 1)

        opportunity_group = QGroupBox("Radar de oportunidades · diferencial vs curva")
        opportunity_group.setStyleSheet(self._group_style())
        opportunity_layout = QVBoxLayout(opportunity_group)
        self._opportunity_chart = PortfolioDashboardBarChart(
            value_formatter=lambda value: f"{value:+.1f} pb"
        )
        opportunity_layout.addWidget(self._opportunity_chart)
        self._add_excel_action(opportunity_layout, "opportunity", "Diferencial frente a curva")
        layout.addWidget(opportunity_group, 1, 0)

        currency_group = QGroupBox("Distribución por moneda")
        currency_group.setStyleSheet(self._group_style())
        currency_layout = QVBoxLayout(currency_group)
        self._currency_chart = PortfolioDashboardDonutChart(center_label="Valor de mercado total")
        currency_layout.addWidget(self._currency_chart)
        self._add_excel_action(currency_layout, "currency", "Distribución por moneda")
        layout.addWidget(currency_group, 1, 1)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        self._dashboard_note = QLabel("")
        self._dashboard_note.setWordWrap(True)
        self._dashboard_note.setObjectName("portfolioInsightBanner")
        self._dashboard_note.setStyleSheet(
            "QLabel#portfolioInsightBanner {color:#315468; padding:8px 12px; "
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #E8F5FB, stop:0.65 #F7FBFD, stop:1 #EAF7F2); "
            "border:1px solid #BFDDEB; border-radius:8px; font-weight:600;}"
        )
        layout.addWidget(self._dashboard_note, 2, 0, 1, 2)
        self._tabs.addTab(page, "Resumen ejecutivo")

    def _add_excel_action(self, layout: QVBoxLayout, key: str, label: str) -> None:
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action = QPushButton("Exportar datos · Excel")
        action.setObjectName(f"portfolioExcel_{key}")
        action.setToolTip(f"Descargar los datos originales de {label}")
        action.clicked.connect(
            lambda _checked=False, metric=key, title=label: self._export_chart_data(metric, title)
        )
        action_row.addWidget(action)
        layout.addLayout(action_row)

    @staticmethod
    def _chart_data_sheet(
        title: str, points: tuple[PortfolioDashboardPoint, ...], unit: str
    ) -> ExcelSheet:
        return ExcelSheet(
            title=title,
            chart_title=title,
            chart_type="bar",
            unit=unit,
            headers=("Categoría / instrumento", f"Valor ({unit})", "Dato adicional", "Detalle"),
            rows=tuple(
                (item.label, item.value, item.secondary_value, item.detail)
                for item in points
            ),
        )

    def _export_chart_data(self, key: str, title: str) -> None:
        sources = {
            "issuer": (self._view_model.top_issuer_points, "%"),
            "duration": (self._view_model.duration_points, "%"),
            "opportunity": (self._view_model.opportunity_points, "pb"),
            "currency": (self._view_model.currency_points, "%"),
        }
        points, unit = sources[key]
        if not points:
            QMessageBox.information(self, "Sin datos", "Este gráfico no tiene datos disponibles.")
            return
        destination, _filter = QFileDialog.getSaveFileName(
            self, f"Exportar {title}", f"AIP_{key}.xlsx", "Excel (*.xlsx)"
        )
        if not destination:
            return
        try:
            TableExportService().export_workbook(
                destination,
                sheets=(self._chart_data_sheet(title, points, unit),),
                metadata={
                    "Módulo": "Portafolio · Resumen ejecutivo",
                    "Gráfico": title,
                    "Corte": str(self._view_model.summary.valuation_date),
                    "Fuente": "Maestro institucional de inversiones",
                    "Regla": "Los datos son valores de presentación, sin recálculo de metodología.",
                },
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Exportación fallida", str(exc))

    def _build_positions_tab(self) -> None:
        page = QWidget()
        self._positions_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(6)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._filter_panel)
        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.addWidget(self._positions)
        self._content_splitter.addWidget(self._details)
        self._content_splitter.setStretchFactor(0, 3)
        self._content_splitter.setStretchFactor(1, 1)
        layout.addWidget(self._content_splitter, 1)
        self._tabs.addTab(page, "Posiciones")

    @staticmethod
    def _market_value_mm(value: str) -> str:
        try:
            amount = Decimal(value.replace(",", ""))
        except Exception:
            return value
        return f"₡{amount / Decimal('1000000'):,.2f} MM"

    def _bind_dashboard(self, view_model: PortfolioViewModel) -> None:
        summary = view_model.summary
        self._date_label.setText(f"Corte: {summary.valuation_date}")
        issuer_count = len(
            {
                str(getattr(row, "issuer", "")).strip()
                for row in view_model.rows
                if str(getattr(row, "issuer", "")).strip()
            }
        )
        market_value_display = self._market_value_mm(summary.market_value)
        values = {
            "market_value": market_value_display,
            "yield": summary.weighted_yield,
            "duration": summary.modified_duration,
            "hqla": summary.hqla_percent,
            "issuer_count": str(issuer_count),
            "hhi": view_model.hhi,
        }
        for key, value in values.items():
            self._kpis[key].setText(value)
        self._issuer_chart.set_data(view_model.top_issuer_points)
        top_issuers = tuple(view_model.top_issuer_points)
        if top_issuers:
            top3 = sum((point.value for point in top_issuers[:3]), Decimal("0"))
            top5 = sum((point.value for point in top_issuers[:5]), Decimal("0"))
            self._issuer_concentration.setText(
                f"Concentración Top 3: {top3:,.1f}% · Top 5: {top5:,.1f}%"
            )
        else:
            self._issuer_concentration.setText("Concentración Top 3 / Top 5: N/D")
        self._duration_chart.set_data(view_model.duration_points)
        self._opportunity_chart.set_data(view_model.opportunity_points)
        self._currency_chart.set_data(view_model.currency_points)
        self._currency_chart.set_center_value(market_value_display)
        self._valuation_comparison.bind(view_model.valuation_comparison, summary.valuation_date)
        self._dashboard_note.setText(
            f"Vista ejecutiva · Calidad de datos: {view_model.data_quality_status} · "
            f"MIL elegible: {summary.mil_eligible_percent} · "
            f"DV01: {self._translate_status(view_model.dv01_status)}. "
            "El Indicador de Salud permanece N/D hasta certificar su metodología institucional."
        )

    def _ensure_history_worker(self) -> None:
        if self._history_worker_thread is not None:
            return
        thread = QThread(self)
        thread.setObjectName("portfolioHistoryWorkerThread")
        worker = _PortfolioHistoryWorker(self._presenter)
        worker.moveToThread(thread)
        self.history_load_requested.connect(worker.load, Qt.ConnectionType.QueuedConnection)
        worker.result_ready.connect(
            self._on_history_loaded,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(
            self._on_history_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(worker.deleteLater)
        self._history_worker_thread = thread
        self._history_worker = worker
        thread.start()

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.widget(index) is not self._history:
            return
        cutoff = self._view_model.summary.valuation_date
        if self._history_loaded_for is None or self._history_loaded_for[0] != cutoff:
            self._load_history(self._history_requested_sampling)

    def _load_history(self, sampling: str) -> None:
        if self._closing:
            return
        cutoff = self._view_model.summary.valuation_date
        self._history_request_sequence += 1
        self._history_requested_sampling = sampling
        request = (self._history_request_sequence, cutoff, sampling)
        self._history.set_loading(sampling)
        if self._history_loading_request is not None:
            self._history_pending_request = request
            return
        self._start_history_request(request)

    def _start_history_request(self, request: tuple[int, str, str]) -> None:
        if self._closing:
            return
        self._ensure_history_worker()
        self._history_loading_request = request
        request_id, cutoff, sampling = request
        self.history_load_requested.emit(request_id, cutoff, sampling)

    @Slot(int, str, str, object)
    def _on_history_loaded(
        self,
        request_id: int,
        cutoff: str,
        sampling: str,
        payload: object,
    ) -> None:
        if self._closing:
            return
        active = self._history_loading_request
        if active is None or active[0] != request_id:
            return
        self._history_loading_request = None

        pending = self._history_pending_request
        self._history_pending_request = None
        if pending is not None:
            self._history.set_loading(pending[2])
            self._start_history_request(pending)
            return

        if cutoff != self._view_model.summary.valuation_date:
            return
        if not isinstance(payload, PortfolioHistorySeries):
            self._history.set_error("El proceso devolvió una serie histórica inválida")
            return

        self._history.set_data(
            payload.points,
            status=payload.status,
            sampling=payload.sampling,
            warnings=payload.warnings,
        )
        self._history_loaded_for = (cutoff, sampling)

    @Slot(int, str, str, str)
    def _on_history_failed(
        self,
        request_id: int,
        cutoff: str,
        sampling: str,
        message: str,
    ) -> None:
        if self._closing:
            return
        active = self._history_loading_request
        if active is None or active[0] != request_id:
            return
        self._history_loading_request = None

        pending = self._history_pending_request
        self._history_pending_request = None
        if pending is not None:
            self._history.set_loading(pending[2])
            self._start_history_request(pending)
            return

        if cutoff == self._view_model.summary.valuation_date:
            self._history.set_error(message or f"No fue posible calcular la frecuencia {sampling}")

    def refresh(self) -> None:
        self._view_model = self._presenter.refresh()
        self._history_loaded_for = None
        self.bind_view_model(self._view_model)
        if self._tabs.currentWidget() is self._history:
            self._load_history(self._history_requested_sampling)

    def bind_view_model(self, view_model: PortfolioViewModel) -> None:
        previous_cutoff = self._view_model.summary.valuation_date
        self._view_model = view_model
        self._bind_dashboard(view_model)

        if view_model.summary.valuation_date != previous_cutoff:
            self._history_loaded_for = None

        positions_layout = (
            self._positions_page.layout() if self._positions_page is not None else None
        )
        if positions_layout is not None and self._content_splitter is not None:
            positions_layout.removeWidget(self._content_splitter)
            self._content_splitter.hide()

        self._summary = PortfolioSummaryView(view_model.summary)
        self._positions = PortfolioPositionsView(view_model.rows)
        self._details = PortfolioDetailsView(view_model.rows[0] if view_model.rows else None)
        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.addWidget(self._positions)
        self._content_splitter.addWidget(self._details)
        self._content_splitter.setStretchFactor(0, 3)
        self._content_splitter.setStretchFactor(1, 1)
        if positions_layout is not None:
            positions_layout.addWidget(self._content_splitter)

        self._status_bar.setText(self._translate_status(view_model.status))
        self._status_bar.setToolTip(view_model.error or "")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._closing = True
        thread = self._history_worker_thread
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            thread.wait(30000)
        super().closeEvent(event)

    def view_model(self) -> PortfolioViewModel:
        return self._view_model

    def selected_row(self) -> object | None:
        return self._view_model.rows[0] if self._view_model.rows else None
