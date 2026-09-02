from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.price_risk.presenters.price_risk_presenter import PriceRiskPresenter
from aip.ui.modules.price_risk.viewmodels.price_risk_view_model import PriceRiskViewModel
from aip.ui.modules.price_risk.widgets.risk_charts import ParetoChartWidget, RiskBarChartWidget


class _PriceRiskWorker(QObject):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, presenter: PriceRiskPresenter) -> None:
        super().__init__()
        self._presenter = presenter

    @Slot()
    def load(self) -> None:
        try:
            self.result_ready.emit(self._presenter.build_view_model())
        except Exception as exc:
            self.failed.emit(str(exc))


class PriceRiskView(QWidget):
    """Espacio AIP Hybrid para VeR histórico y sensibilidad a tasas."""

    _STATUS_TRANSLATIONS = {
        "LOADING": "CARGANDO",
        "READY": "LISTO",
        "AVAILABLE": "DISPONIBLE",
        "UNAVAILABLE": "NO DISPONIBLE",
        "CALCULATED": "CALCULADO",
        "DATA_UNAVAILABLE": "DATOS NO DISPONIBLES",
        "POLICY_EXCLUDED": "EXCLUIDO POR POLÍTICA",
        "ERROR": "ERROR",
    }

    load_requested = Signal()

    def __init__(self, presenter: PriceRiskPresenter) -> None:
        super().__init__()
        self.setObjectName("priceRiskWorkspace")
        self._presenter = presenter
        self._view_model = PriceRiskViewModel(status="LOADING")
        self._loading = False
        self._refresh_pending = False
        self._closing = False
        self._kpi_labels: dict[str, QLabel] = {}
        self._bucket_labels: dict[str, QLabel] = {}
        self._build_ui()
        self._setup_worker()
        self._set_loading_state(initial=True)
        QTimer.singleShot(0, self._request_load)

    @classmethod
    def _translate_status(cls, value: str) -> str:
        return cls._STATUS_TRANSLATIONS.get(value.strip().upper(), value)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(8)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("RIESGO DE MERCADO")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QLabel("VeR histórico · sensibilidad DV01 · exposición del portafolio")
        subtitle.setStyleSheet("color:#667788; font-size:10px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self._date_label = QLabel("Corte: cargando...")
        self._date_label.setObjectName("priceRiskDate")
        self._date_label.setStyleSheet(
            "QLabel#priceRiskDate {padding:7px 11px; background:#F3F6F9; "
            "border:1px solid #D7E0E8; border-radius:6px; font-weight:600;}"
        )
        header.addWidget(self._date_label)
        root.addLayout(header)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab {padding:8px 18px; font-weight:600;}"
            "QTabBar::tab:selected {color:#174E78; border-bottom:2px solid #1F5A8A;}"
        )
        root.addWidget(self._tabs, 1)

        self._price_page = QWidget()
        self._rate_page = QWidget()
        self._tabs.addTab(self._price_page, "Riesgo de Precio")
        self._tabs.addTab(self._rate_page, "Riesgo de Tasa")
        self._build_price_page()
        self._build_rate_page()

    def _build_price_page(self) -> None:
        layout = QVBoxLayout(self._price_page)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(8)

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(7)
        kpi_grid.setVerticalSpacing(7)
        price_kpis = (
            ("var_crc", "VeR 95%", "Pérdida máxima estimada"),
            ("var_percent", "VeR %", "Sobre exposición calculada"),
            ("coverage", "Cobertura", "Universo elegible con historia"),
            ("titles", "Títulos", "Incorporados al cálculo"),
            ("eligible_vm", "Exposición", "Valor de mercado elegible"),
            ("scenarios", "Escenarios", "Simulaciones históricas"),
            ("horizon", "Horizonte", "Observaciones por escenario"),
            ("rank", "Posición Percentil", "Percentil regulatorio"),
        )
        for index, (key, caption, helper) in enumerate(price_kpis):
            kpi_grid.addWidget(self._metric_card(key, caption, helper), index // 4, index % 4)
        layout.addLayout(kpi_grid)

        scenario_group = QGroupBox("Escenario VeR seleccionado")
        scenario_group.setStyleSheet(self._group_style())
        scenario_layout = QGridLayout(scenario_group)
        self._scenario_label = QLabel("-")
        self._scenario_period = QLabel("-")
        self._status_label = QLabel("-")
        self._diagnostic_label = QLabel("")
        self._diagnostic_label.setWordWrap(True)
        self._diagnostic_label.setStyleSheet("color:#667788; font-size:9px;")
        scenario_layout.addWidget(QLabel("Escenario"), 0, 0)
        scenario_layout.addWidget(self._scenario_label, 0, 1)
        scenario_layout.addWidget(QLabel("Ventana"), 0, 2)
        scenario_layout.addWidget(self._scenario_period, 0, 3)
        scenario_layout.addWidget(QLabel("Estado"), 1, 0)
        scenario_layout.addWidget(self._status_label, 1, 1)
        scenario_layout.addWidget(self._diagnostic_label, 1, 2, 1, 2)
        layout.addWidget(scenario_group)

        charts = QHBoxLayout()
        charts.setSpacing(8)
        contribution_group = QGroupBox("10 principales · contribución al VeR")
        contribution_group.setStyleSheet(self._group_style())
        contribution_layout = QVBoxLayout(contribution_group)
        self._contribution_chart = RiskBarChartWidget(
            value_formatter=lambda value: f"{value:.2f}%"
        )
        contribution_layout.addWidget(self._contribution_chart)
        pareto_group = QGroupBox("Pareto · concentración de contribuyentes")
        pareto_group.setStyleSheet(self._group_style())
        pareto_layout = QVBoxLayout(pareto_group)
        self._pareto_chart = ParetoChartWidget()
        pareto_layout.addWidget(self._pareto_chart)
        charts.addWidget(contribution_group, 1)
        charts.addWidget(pareto_group, 1)
        layout.addLayout(charts)

        table_group = QGroupBox("Contribución por título al escenario VeR")
        table_group.setStyleSheet(self._group_style())
        table_layout = QVBoxLayout(table_group)
        self._table = QTableWidget()
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels(
            [
                "Serie",
                "Emisor",
                "Moneda",
                "Valor de Mercado",
                "Resultado del Escenario",
                "Contribución %",
                "VeR Individual %",
                "Obs. Reales",
                "Obs. Sintéticas",
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(26)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setMinimumHeight(260)
        table_layout.addWidget(self._table)
        layout.addWidget(table_group)

    def _build_rate_page(self) -> None:
        layout = QVBoxLayout(self._rate_page)
        layout.setContentsMargins(4, 8, 4, 4)
        layout.setSpacing(8)

        kpi_grid = QGridLayout()
        rate_kpis = (
            ("dv01_total", "DV01 Total", "Cambio estimado por +1 pb"),
            ("dv01_crc", "DV01 CRC", "Sensibilidad posiciones CRC"),
            ("dv01_usd", "DV01 USD", "CRC-equivalente posiciones USD"),
            ("dv01_coverage", "Cobertura DV01", "VM con duración aplicable"),
        )
        for index, (key, caption, helper) in enumerate(rate_kpis):
            kpi_grid.addWidget(self._metric_card(key, caption, helper), 0, index)
        layout.addLayout(kpi_grid)

        charts = QHBoxLayout()
        charts.setSpacing(8)
        bucket_group = QGroupBox("DV01 por tramo · monto y participación")
        bucket_group.setStyleSheet(self._group_style())
        bucket_layout = QVBoxLayout(bucket_group)
        self._bucket_chart = RiskBarChartWidget(
            value_formatter=lambda value: self._format_mm(value),
            show_secondary=True,
        )
        bucket_layout.addWidget(self._bucket_chart)
        currency_group = QGroupBox("DV01 por moneda · CRC equivalente")
        currency_group.setStyleSheet(self._group_style())
        currency_layout = QVBoxLayout(currency_group)
        self._currency_chart = RiskBarChartWidget(
            value_formatter=lambda value: self._format_mm(value),
            show_secondary=True,
        )
        currency_layout.addWidget(self._currency_chart)
        charts.addWidget(bucket_group, 2)
        charts.addWidget(currency_group, 1)
        layout.addLayout(charts)

        bucket_detail = QGroupBox("Sensibilidad DV01 por tramo")
        bucket_detail.setStyleSheet(self._group_style())
        grid = QGridLayout(bucket_detail)
        headers = ("< 1 año", "1 a 5 años", "> 5 años")
        for column, text in enumerate(headers, start=1):
            item = QLabel(text)
            item.setStyleSheet("font-weight:700; color:#17324D;")
            grid.addWidget(item, 0, column)
        for row_index, label in enumerate(("DV01", "% DV01", "Valor de Mercado", "Posiciones"), 1):
            grid.addWidget(QLabel(label), row_index, 0)
        for column, key in enumerate(("lt1", "1to5", "gt5"), 1):
            for row_index, metric in enumerate(("value", "percent", "market_value", "positions"), 1):
                label = QLabel("-")
                if metric in {"value", "percent"}:
                    label.setStyleSheet("font-weight:600;")
                self._bucket_labels[f"{key}_{metric}"] = label
                grid.addWidget(label, row_index, column)
        layout.addWidget(bucket_detail)

        irrbb = QGroupBox("IRRBB · ΔEVE / ΔNII")
        irrbb.setStyleSheet(self._group_style())
        irrbb_layout = QVBoxLayout(irrbb)
        notice = QLabel(
            "Integración pendiente con el módulo IRRBB. Esta vista no aproxima ΔEVE/ΔNII "
            "a partir de DV01; mostrará resultados cuando el motor de riesgo de tasas esté conectado."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet("color:#5E6E7E; padding:12px; font-weight:600;")
        irrbb_layout.addWidget(notice)
        layout.addWidget(irrbb)
        layout.addStretch(1)

    @staticmethod
    def _format_mm(value: Decimal) -> str:
        return f"₡{value / Decimal('1000000'):,.2f} MM"

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D7E0E8; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#22384C; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    def _metric_card(self, key: str, caption: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("riskMetricCard")
        card.setMinimumHeight(76)
        card.setStyleSheet(
            "QFrame#riskMetricCard {background:#FFFFFF; border:1px solid #D7E0E8; "
            "border-radius:8px;} QFrame#riskMetricCard:hover {border-color:#8DB0CB;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        title = QLabel(caption)
        title.setStyleSheet("color:#667788; font-size:9px; border:none;")
        value = QLabel("-")
        value_font = QFont()
        value_font.setPointSize(12)
        value_font.setBold(True)
        value.setFont(value_font)
        value.setStyleSheet("color:#142E46; border:none;")
        hint = QLabel(helper)
        hint.setStyleSheet("color:#8A98A6; font-size:8px; border:none;")
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(hint)
        self._kpi_labels[key] = value
        return card

    def _setup_worker(self) -> None:
        self._worker_thread = QThread(self)
        self._worker_thread.setObjectName("priceRiskWorkerThread")
        self._worker = _PriceRiskWorker(self._presenter)
        self._worker.moveToThread(self._worker_thread)
        self.load_requested.connect(self._worker.load, Qt.ConnectionType.QueuedConnection)
        self._worker.result_ready.connect(
            self._on_load_completed,
            Qt.ConnectionType.QueuedConnection,
        )
        self._worker.failed.connect(self._on_load_failed, Qt.ConnectionType.QueuedConnection)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.start()

    def _request_load(self) -> None:
        if self._closing:
            return
        if self._loading:
            self._refresh_pending = True
            return
        self._loading = True
        self._set_loading_state(initial=False)
        self.load_requested.emit()

    def _set_loading_state(self, *, initial: bool) -> None:
        self._date_label.setText("Corte: cargando..." if initial else "Corte: actualizando...")
        self._status_label.setText("Calculando VeR...")
        self._status_label.setStyleSheet("color:#506273; font-weight:600;")
        if initial:
            for label in self._kpi_labels.values():
                label.setText("-")
            self._table.setRowCount(0)
        self._table.setEnabled(False)

    @Slot(object)
    def _on_load_completed(self, view_model: object) -> None:
        if self._closing:
            return
        self._loading = False
        if self._refresh_pending:
            self._refresh_pending = False
            self._request_load()
            return
        if not isinstance(view_model, PriceRiskViewModel):
            self._on_load_failed("El proceso devolvió un modelo de vista inválido")
            return
        self._bind_view_model(view_model)
        self._table.setEnabled(True)

    @Slot(str)
    def _on_load_failed(self, message: str) -> None:
        if self._closing:
            return
        self._loading = False
        self._bind_view_model(PriceRiskViewModel(status="ERROR", diagnostic=message))
        self._status_label.setStyleSheet("color:#A33A3A; font-weight:700;")
        self._table.setEnabled(True)

    def _bind_view_model(self, vm: PriceRiskViewModel) -> None:
        self._view_model = vm
        self._date_label.setText(f"Corte: {vm.valuation_date}")
        mapping = {
            "var_crc": vm.var_crc,
            "var_percent": vm.var_percent,
            "coverage": vm.coverage_percent,
            "titles": str(vm.calculated_titles),
            "eligible_vm": vm.eligible_market_value,
            "scenarios": str(vm.scenario_count),
            "horizon": str(vm.horizon_observations),
            "rank": str(vm.var_rank),
            "dv01_total": vm.dv01_total,
            "dv01_crc": vm.dv01_crc,
            "dv01_usd": vm.dv01_usd,
            "dv01_coverage": vm.dv01_coverage_percent,
        }
        for key, value in mapping.items():
            self._kpi_labels[key].setText(value)

        bucket_mapping = {
            "lt1_value": vm.dv01_bucket_lt1_value,
            "lt1_percent": vm.dv01_bucket_lt1_percent,
            "lt1_market_value": vm.dv01_bucket_lt1_market_value,
            "lt1_positions": str(vm.dv01_bucket_lt1_positions),
            "1to5_value": vm.dv01_bucket_1to5_value,
            "1to5_percent": vm.dv01_bucket_1to5_percent,
            "1to5_market_value": vm.dv01_bucket_1to5_market_value,
            "1to5_positions": str(vm.dv01_bucket_1to5_positions),
            "gt5_value": vm.dv01_bucket_gt5_value,
            "gt5_percent": vm.dv01_bucket_gt5_percent,
            "gt5_market_value": vm.dv01_bucket_gt5_market_value,
            "gt5_positions": str(vm.dv01_bucket_gt5_positions),
        }
        for key, value in bucket_mapping.items():
            self._bucket_labels[key].setText(value)

        self._scenario_label.setText(f"#{vm.scenario_number}" if vm.scenario_number else "-")
        self._scenario_period.setText(
            f"{vm.scenario_start_date} → {vm.scenario_end_date}"
            if vm.scenario_start_date != "-"
            else "-"
        )
        self._status_label.setText(self._translate_status(vm.status))
        self._diagnostic_label.setText(vm.diagnostic or "")
        self._contribution_chart.set_data(vm.var_contribution_points)
        self._pareto_chart.set_data(vm.var_pareto_points)
        self._bucket_chart.set_data(vm.dv01_bucket_points)
        self._currency_chart.set_data(vm.dv01_currency_points)

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(vm.rows))
        for row_index, row in enumerate(vm.rows):
            values = (
                row.series,
                row.issuer,
                row.currency,
                row.market_value,
                row.pnl_scenario,
                row.contribution_percent,
                row.individual_var_percent,
                str(row.real_observations),
                str(row.synthetic_observations),
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index >= 3:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if row_index < 3 and column_index == 5:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self._table.setItem(row_index, column_index, item)
        self._table.setSortingEnabled(True)

    def refresh(self) -> None:
        self._request_load()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._closing = True
        thread = getattr(self, "_worker_thread", None)
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            thread.wait(30000)
        super().closeEvent(event)

    @property
    def table(self) -> QTableWidget:
        return self._table

    @property
    def view_model(self) -> PriceRiskViewModel:
        return self._view_model
