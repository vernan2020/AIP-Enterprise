from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
    """Espacio institucional de VeR histórico, DV01 y sensibilidad de tasas."""

    _STATUS_TRANSLATIONS = {
        "LOADING": "CARGANDO",
        "READY": "LISTO",
        "AVAILABLE": "DISPONIBLE",
        "UNAVAILABLE": "NO DISPONIBLE",
        "CALCULATED": "CALCULADO",
        "CALCULATED_WITH_DATA_GAPS": "CALCULADO CON BRECHAS DE DATOS",
        "CALCULATED_WITH_MINOR_HISTORY_EXCLUSIONS": "CALCULADO CON EXCLUSIONES MENORES",
        "PARTIAL_HISTORY_COVERAGE": "COBERTURA HISTÓRICA PARCIAL",
        "INSUFFICIENT_MARKET_HISTORY": "HISTORIA DE MERCADO INSUFICIENTE",
        "NO_ELIGIBLE_TITLES_WITH_HISTORY": "SIN TÍTULOS ELEGIBLES CON HISTORIA",
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
        self._quality_labels: dict[str, QLabel] = {}
        self._bucket_labels: dict[str, QLabel] = {}
        self._build_ui()
        self._setup_worker()
        self._set_loading_state(initial=True)
        QTimer.singleShot(0, self._request_load)

    @classmethod
    def _translate_status(cls, value: str) -> str:
        return cls._STATUS_TRANSLATIONS.get(value.strip().upper(), value)

    @staticmethod
    def _format_mm(value: Decimal) -> str:
        return f"₡{value / Decimal('1000000'):,.2f} MM"

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D5DEE3; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#005EB8; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(7)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("RIESGO DE PRECIO · VeR 95%")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color:#00345F;")
        subtitle = QLabel(
            "Simulación histórica institucional · 521 precios · horizonte 21 observaciones · 500 escenarios"
        )
        subtitle.setStyleSheet("color:#566D7C; font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self._date_label = QLabel("Corte: cargando...")
        self._date_label.setObjectName("priceRiskDate")
        self._date_label.setStyleSheet(
            "QLabel#priceRiskDate {padding:7px 11px; background:#F0F8FC; color:#005EB8; "
            "border:1px solid #73B3DD; border-radius:6px; font-weight:700;}"
        )
        header.addWidget(self._date_label)
        root.addLayout(header)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        root.addWidget(self._tabs, 1)

        self._price_page = QWidget()
        self._rate_page = QWidget()
        self._tabs.addTab(self._price_page, "Riesgo de Precio · VeR")
        self._tabs.addTab(self._rate_page, "Riesgo de Tasa · DV01")
        self._build_price_page()
        self._build_rate_page()

    def _metric_card(self, key: str, caption: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("riskMetricCard")
        card.setMinimumHeight(76)
        card.setStyleSheet(
            "QFrame#riskMetricCard {background:#FFFFFF; border:1px solid #D5DEE3; border-radius:8px;}"
            "QFrame#riskMetricCard:hover {background:#F0F8FC; border-color:#73B3DD;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        title = QLabel(caption)
        title.setStyleSheet("color:#566D7C; font-size:8px; border:none;")
        value = QLabel("-")
        value_font = QFont()
        value_font.setPointSize(12)
        value_font.setBold(True)
        value.setFont(value_font)
        value.setStyleSheet("color:#00345F; border:none;")
        hint = QLabel(helper)
        hint.setStyleSheet("color:#7B8D98; font-size:8px; border:none;")
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(hint)
        self._kpi_labels[key] = value
        return card

    def _build_price_page(self) -> None:
        layout = QVBoxLayout(self._price_page)
        layout.setContentsMargins(3, 6, 3, 3)
        layout.setSpacing(7)

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(7)
        kpi_grid.setVerticalSpacing(7)
        definitions = (
            ("var_crc", "VeR 95%", "Pérdida del percentil 5%"),
            ("var_percent", "VeR %", "Sobre exposición calculada"),
            ("calculated_vm", "Exposición VeR", "VM incorporado al cálculo"),
            ("coverage", "Cobertura histórica", "Sobre universo elegible"),
            ("titles", "Títulos calculados", "Series incorporadas"),
            ("scenarios", "Escenarios", "Simulaciones históricas"),
            ("horizon", "Horizonte", "Observaciones por escenario"),
            ("reconciliation", "Reconciliación", "Suma de contribuciones"),
        )
        for index, definition in enumerate(definitions):
            kpi_grid.addWidget(self._metric_card(*definition), index // 4, index % 4)
        layout.addLayout(kpi_grid)

        quality = QFrame()
        quality.setObjectName("varQualityStrip")
        quality.setStyleSheet(
            "QFrame#varQualityStrip {background:#F7F9FA; border:1px solid #D5DEE3; border-radius:7px;}"
        )
        quality_layout = QHBoxLayout(quality)
        quality_layout.setContentsMargins(10, 6, 10, 6)
        quality_layout.setSpacing(18)
        for key, caption in (
            ("eligible_vm", "Universo elegible"),
            ("policy_excluded_vm", "Excluido por política"),
            ("history_excluded_vm", "Sin historia utilizable"),
            ("eligible_positions", "Posiciones elegibles"),
            ("policy_excluded_positions", "Posiciones fuera de política"),
            ("history_excluded_titles", "Títulos sin historia"),
        ):
            block = QVBoxLayout()
            label = QLabel(caption)
            label.setStyleSheet("color:#7B8D98; font-size:8px;")
            value = QLabel("-")
            value.setStyleSheet("color:#183247; font-weight:700; font-size:9px;")
            self._quality_labels[key] = value
            block.addWidget(label)
            block.addWidget(value)
            quality_layout.addLayout(block)
        quality_layout.addStretch(1)
        layout.addWidget(quality)

        scenario_group = QGroupBox("Escenario VeR seleccionado")
        scenario_group.setStyleSheet(self._group_style())
        scenario_layout = QGridLayout(scenario_group)
        self._scenario_label = QLabel("-")
        self._scenario_period = QLabel("-")
        self._status_label = QLabel("-")
        self._diagnostic_label = QLabel("")
        self._diagnostic_label.setWordWrap(True)
        self._diagnostic_label.setStyleSheet("color:#566D7C; font-size:8px;")
        scenario_layout.addWidget(QLabel("Escenario"), 0, 0)
        scenario_layout.addWidget(self._scenario_label, 0, 1)
        scenario_layout.addWidget(QLabel("Ventana histórica"), 0, 2)
        scenario_layout.addWidget(self._scenario_period, 0, 3)
        scenario_layout.addWidget(QLabel("Estado"), 1, 0)
        scenario_layout.addWidget(self._status_label, 1, 1)
        scenario_layout.addWidget(self._diagnostic_label, 1, 2, 1, 2)
        layout.addWidget(scenario_group)

        analytics = QGridLayout()
        analytics.setHorizontalSpacing(7)
        analytics.setVerticalSpacing(7)

        top_group = QGroupBox("10 principales · contribución al VeR")
        top_group.setStyleSheet(self._group_style())
        top_layout = QVBoxLayout(top_group)
        self._contribution_chart = RiskBarChartWidget(
            value_formatter=lambda value: f"{value:+.2f}%"
        )
        top_layout.addWidget(self._contribution_chart)
        analytics.addWidget(top_group, 0, 0)

        pareto_group = QGroupBox("Contribución acumulada · reconciliación al 100%")
        pareto_group.setStyleSheet(self._group_style())
        pareto_layout = QVBoxLayout(pareto_group)
        self._pareto_chart = ParetoChartWidget()
        pareto_layout.addWidget(self._pareto_chart)
        analytics.addWidget(pareto_group, 0, 1)

        issuer_group = QGroupBox("Contribución al VeR por emisor")
        issuer_group.setStyleSheet(self._group_style())
        issuer_layout = QVBoxLayout(issuer_group)
        self._issuer_chart = RiskBarChartWidget(
            value_formatter=lambda value: f"{value:+.2f}%"
        )
        issuer_layout.addWidget(self._issuer_chart)
        analytics.addWidget(issuer_group, 1, 0)

        currency_group = QGroupBox("Distribución por moneda · Valor de Mercado VeR")
        currency_group.setStyleSheet(self._group_style())
        currency_layout = QVBoxLayout(currency_group)
        self._var_currency_chart = RiskBarChartWidget(
            value_formatter=lambda value: self._format_mm(value),
            show_secondary=True,
        )
        currency_layout.addWidget(self._var_currency_chart)
        analytics.addWidget(currency_group, 1, 1)
        analytics.setColumnStretch(0, 1)
        analytics.setColumnStretch(1, 1)
        layout.addLayout(analytics)

        table_group = QGroupBox("Contribución por título al escenario VeR")
        table_group.setStyleSheet(self._group_style())
        table_layout = QVBoxLayout(table_group)
        table_header = QHBoxLayout()
        self._table_search = QLineEdit()
        self._table_search.setPlaceholderText("Buscar serie, emisor o moneda...")
        self._table_search.setMaximumWidth(360)
        self._table_search.textChanged.connect(self._filter_table)
        table_header.addWidget(self._table_search)
        table_header.addStretch(1)
        table_layout.addLayout(table_header)

        self._table = QTableWidget()
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels(
            [
                "Serie",
                "Emisor",
                "Moneda",
                "Valor de Mercado",
                "P&L Escenario",
                "Contribución %",
                "VeR Individual %",
                "Obs. Reales",
                "Backfill",
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(25)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setMinimumHeight(280)
        table_layout.addWidget(self._table)
        layout.addWidget(table_group)

    def _build_rate_page(self) -> None:
        layout = QVBoxLayout(self._rate_page)
        layout.setContentsMargins(3, 6, 3, 3)
        layout.setSpacing(7)

        kpi_grid = QGridLayout()
        definitions = (
            ("dv01_total", "DV01 Total", "Variación estimada por +1 pb"),
            ("dv01_crc", "DV01 CRC", "Sensibilidad posiciones CRC"),
            ("dv01_usd", "DV01 USD", "Equivalente CRC de posiciones USD"),
            ("dv01_coverage", "Cobertura DV01", "VM con duración aplicable"),
            ("shock_coverage", "Cobertura shocks", "VM sensible a tasas"),
            ("worst_shock", "Shock más adverso", "Escenario de menor ΔEVE"),
            ("worst_eve", "Peor ΔEVE aprox.", "Aproximación por duración"),
            ("shock_status", "Estado sensibilidad", "Cálculo paralelo ±100/±200 pb"),
        )
        for index, definition in enumerate(definitions):
            kpi_grid.addWidget(self._metric_card(*definition), index // 4, index % 4)
        layout.addLayout(kpi_grid)

        charts = QGridLayout()
        charts.setHorizontalSpacing(7)
        charts.setVerticalSpacing(7)

        bucket_group = QGroupBox("DV01 por tramo · monto y participación")
        bucket_group.setStyleSheet(self._group_style())
        bucket_layout = QVBoxLayout(bucket_group)
        self._bucket_chart = RiskBarChartWidget(
            value_formatter=lambda value: self._format_mm(value),
            show_secondary=True,
        )
        bucket_layout.addWidget(self._bucket_chart)
        charts.addWidget(bucket_group, 0, 0)

        currency_group = QGroupBox("DV01 por moneda · CRC equivalente")
        currency_group.setStyleSheet(self._group_style())
        currency_layout = QVBoxLayout(currency_group)
        self._currency_chart = RiskBarChartWidget(
            value_formatter=lambda value: self._format_mm(value),
            show_secondary=True,
        )
        currency_layout.addWidget(self._currency_chart)
        charts.addWidget(currency_group, 0, 1)

        shock_group = QGroupBox("Sensibilidad a shocks paralelos de tasas · ΔEVE aproximado")
        shock_group.setStyleSheet(self._group_style())
        shock_layout = QVBoxLayout(shock_group)
        self._shock_chart = RiskBarChartWidget(
            value_formatter=lambda value: self._format_mm(value)
        )
        shock_layout.addWidget(self._shock_chart)
        charts.addWidget(shock_group, 1, 0)

        shock_table_group = QGroupBox("Detalle de escenarios de sensibilidad")
        shock_table_group.setStyleSheet(self._group_style())
        shock_table_layout = QVBoxLayout(shock_table_group)
        self._shock_table = QTableWidget(0, 3)
        self._shock_table.setHorizontalHeaderLabels(
            ["Shock", "ΔEVE aproximado", "Valor de Mercado sensibilizado"]
        )
        self._shock_table.verticalHeader().setVisible(False)
        self._shock_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._shock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        shock_table_layout.addWidget(self._shock_table)
        charts.addWidget(shock_table_group, 1, 1)
        layout.addLayout(charts)

        bucket_detail = QGroupBox("Sensibilidad DV01 por tramo")
        bucket_detail.setStyleSheet(self._group_style())
        grid = QGridLayout(bucket_detail)
        headers = ("< 1 año", "1 a 5 años", "> 5 años")
        for column, text in enumerate(headers, start=1):
            item = QLabel(text)
            item.setStyleSheet("font-weight:700; color:#00345F;")
            grid.addWidget(item, 0, column)
        for row_index, label in enumerate(
            ("DV01", "% DV01", "Valor de Mercado", "Posiciones"),
            1,
        ):
            grid.addWidget(QLabel(label), row_index, 0)
        for column, key in enumerate(("lt1", "1to5", "gt5"), 1):
            for row_index, metric in enumerate(
                ("value", "percent", "market_value", "positions"),
                1,
            ):
                label = QLabel("-")
                if metric in {"value", "percent"}:
                    label.setStyleSheet("font-weight:600;")
                self._bucket_labels[f"{key}_{metric}"] = label
                grid.addWidget(label, row_index, column)
        layout.addWidget(bucket_detail)

        irrbb = QGroupBox("Alcance metodológico")
        irrbb.setStyleSheet(self._group_style())
        irrbb_layout = QVBoxLayout(irrbb)
        notice = QLabel(
            "Los shocks mostrados son una sensibilidad aproximada del valor económico basada en duración "
            "modificada. No sustituyen el cálculo regulatorio IRRBB de ΔEVE/ΔNII; ese motor se integra "
            "de forma independiente para evitar mezclar metodologías."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet("color:#566D7C; padding:8px; font-weight:600;")
        irrbb_layout.addWidget(notice)
        layout.addWidget(irrbb)

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
        self._status_label.setStyleSheet("color:#566D7C; font-weight:600;")
        if initial:
            for label in self._kpi_labels.values():
                label.setText("-")
            for label in self._quality_labels.values():
                label.setText("-")
            self._table.setRowCount(0)
            self._shock_table.setRowCount(0)
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
        self._status_label.setStyleSheet("color:#E4002B; font-weight:700;")
        self._table.setEnabled(True)

    def _bind_view_model(self, vm: PriceRiskViewModel) -> None:
        self._view_model = vm
        self._date_label.setText(f"Corte: {vm.valuation_date}")

        mapping = {
            "var_crc": vm.var_crc,
            "var_percent": vm.var_percent,
            "calculated_vm": vm.calculated_market_value,
            "coverage": vm.coverage_percent,
            "titles": str(vm.calculated_titles),
            "scenarios": str(vm.scenario_count),
            "horizon": str(vm.horizon_observations),
            "reconciliation": vm.contribution_reconciliation_percent,
            "dv01_total": vm.dv01_total,
            "dv01_crc": vm.dv01_crc,
            "dv01_usd": vm.dv01_usd,
            "dv01_coverage": vm.dv01_coverage_percent,
            "shock_coverage": vm.rate_shock_coverage_percent,
            "worst_shock": vm.worst_shock,
            "worst_eve": vm.worst_delta_eve,
            "shock_status": self._translate_status(vm.rate_shock_status),
        }
        for key, value in mapping.items():
            self._kpi_labels[key].setText(value)

        quality_mapping = {
            "eligible_vm": vm.eligible_market_value,
            "policy_excluded_vm": vm.policy_excluded_market_value,
            "history_excluded_vm": vm.history_excluded_market_value,
            "eligible_positions": str(vm.eligible_positions),
            "policy_excluded_positions": str(vm.policy_excluded_positions),
            "history_excluded_titles": str(vm.history_excluded_titles),
        }
        for key, value in quality_mapping.items():
            self._quality_labels[key].setText(value)

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
        self._status_label.setStyleSheet(
            "color:#167A68; font-weight:700;"
            if vm.status.startswith("CALCULATED")
            else "color:#A95B00; font-weight:700;"
        )
        self._diagnostic_label.setText(vm.diagnostic or "")

        self._contribution_chart.set_data(vm.var_contribution_points)
        self._pareto_chart.set_data(vm.var_pareto_points)
        self._issuer_chart.set_data(vm.issuer_contribution_points)
        self._var_currency_chart.set_data(vm.currency_market_value_points)
        self._bucket_chart.set_data(vm.dv01_bucket_points)
        self._currency_chart.set_data(vm.dv01_currency_points)
        self._shock_chart.set_data(vm.rate_shock_points)

        self._populate_var_table(vm)
        self._populate_shock_table(vm)
        self._filter_table(self._table_search.text())

    def _populate_var_table(self, vm: PriceRiskViewModel) -> None:
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
                if column_index == 4:
                    raw = value.replace("₡", "").replace(",", "").strip()
                    try:
                        negative = Decimal(raw) < 0
                    except Exception:
                        negative = False
                    if negative:
                        item.setForeground(QColor("#E4002B"))
                if row_index < 3 and column_index == 5:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor("#005EB8"))
                self._table.setItem(row_index, column_index, item)
        self._table.setSortingEnabled(True)

    def _populate_shock_table(self, vm: PriceRiskViewModel) -> None:
        self._shock_table.setRowCount(len(vm.rate_shock_rows))
        for row_index, row in enumerate(vm.rate_shock_rows):
            values = (row.shock_label, row.delta_eve, row.shocked_market_value)
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column_index == 1:
                    item.setForeground(
                        QColor("#E4002B") if row.delta_eve_crc < 0 else QColor("#167A68")
                    )
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self._shock_table.setItem(row_index, column_index, item)

    @Slot(str)
    def _filter_table(self, text: str) -> None:
        needle = text.strip().casefold()
        for row in range(self._table.rowCount()):
            haystack = " ".join(
                self._table.item(row, column).text()
                for column in range(min(3, self._table.columnCount()))
                if self._table.item(row, column) is not None
            ).casefold()
            self._table.setRowHidden(row, bool(needle) and needle not in haystack)

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
