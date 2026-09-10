from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.ui.modules.rate_risk.models import RateRiskKpi, RateRiskReadModel


class RateRiskView(QWidget):
    """Passive institutional workspace for IRRBB/RTILB results.

    The view never calculates EVE, Delta EVE, repricing GAP, scenarios, curves,
    optionality or data-quality classifications. It renders a RateRiskReadModel
    produced by the presenter/application layer and can therefore be opened before
    any physical source (SQL, XML, OneDrive, Excel, PostgreSQL) is configured.
    """

    _MONEY_SCALE = Decimal("1000000")
    _ANALYSIS_STATUS_PRESENTATION = {
        "CALCULATED": ("Estado: Calculado", "#EAF7EE", "#1F6D3D", "#9DD5AD"),
        "CALCULATED_WITH_DATA_GAPS": (
            "Estado: Calculado · brechas",
            "#FFF8E6",
            "#775A00",
            "#E6C85C",
        ),
        "BLOCKED": ("Estado: Bloqueado", "#FDEEEE", "#9B2C2C", "#E7A9A9"),
        "NO_DATA": ("Estado: Sin datos", "#F2F4F5", "#566D7C", "#C9D2D7"),
        "UNCONFIGURED": ("Estado: Sin cálculo", "#F2F4F5", "#566D7C", "#C9D2D7"),
    }

    def __init__(self, read_model: RateRiskReadModel | None = None) -> None:
        super().__init__()
        self.setObjectName("rateRiskWorkspace")
        self._read_model = read_model
        self._kpi_values: dict[str, QLabel] = {}
        self._build_ui()
        self.set_read_model(read_model)

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox {border:1px solid #D5DEE3; border-radius:8px; margin-top:8px; "
            "font-weight:700; color:#005EB8; background:#FFFFFF;}"
            "QGroupBox::title {subcontrol-origin:margin; left:10px; padding:0 5px;}"
        )

    @staticmethod
    def _table() -> QTableWidget:
        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setStyleSheet(
            "QTableWidget {background:#FFFFFF; alternate-background-color:#F7F9FA; "
            "border:1px solid #D5DEE3; gridline-color:#E6ECEF;}"
            "QHeaderView::section {background:#F0F8FC; color:#00345F; font-weight:700; "
            "padding:6px; border:none; border-bottom:1px solid #D5DEE3;}"
        )
        return table

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
        title = QLabel("RIESGO DE TASAS · LIBRO BANCARIO")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color:#00345F;")
        subtitle = QLabel(
            "RTILB / IRRBB · VEP y ΔVEP · GAP SUGEF 19 bandas · trazabilidad por flujo"
        )
        subtitle.setStyleSheet("color:#566D7C; font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        self._analysis_status_label = QLabel("Estado: Sin cálculo")
        self._analysis_status_label.setObjectName("rateRiskAnalysisStatus")
        header.addWidget(self._analysis_status_label)

        self._cutoff_label = QLabel("Corte: pendiente")
        self._cutoff_label.setObjectName("rateRiskCutoff")
        self._cutoff_label.setStyleSheet(
            "QLabel#rateRiskCutoff {padding:7px 11px; background:#F0F8FC; color:#005EB8; "
            "border:1px solid #73B3DD; border-radius:6px; font-weight:700;}"
        )
        header.addWidget(self._cutoff_label)
        root.addLayout(header)

        self._methodology_label = QLabel()
        self._methodology_label.setWordWrap(True)
        self._methodology_label.setStyleSheet(
            "padding:6px 9px; background:#F7F9FA; color:#566D7C; "
            "border:1px solid #D5DEE3; border-radius:6px; font-size:9px;"
        )
        root.addWidget(self._methodology_label)

        self._warning_label = QLabel()
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet(
            "padding:7px 9px; background:#FFF8E6; color:#775A00; "
            "border:1px solid #E6C85C; border-radius:6px; font-size:9px;"
        )
        root.addWidget(self._warning_label)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        root.addWidget(self._tabs, 1)

        self._summary_page = QWidget()
        self._scenario_page = QWidget()
        self._gap_page = QWidget()
        self._curve_page = QWidget()
        self._drilldown_page = QWidget()
        self._quality_page = QWidget()

        self._tabs.addTab(self._summary_page, "Resumen RTILB")
        self._tabs.addTab(self._scenario_page, "Escenarios VEP")
        self._tabs.addTab(self._gap_page, "GAP SUGEF · 19 bandas")
        self._tabs.addTab(self._curve_page, "Curvas")
        self._tabs.addTab(self._drilldown_page, "Drill-down")
        self._tabs.addTab(self._quality_page, "Calidad de Datos")

        self._build_summary_page()
        self._build_scenario_page()
        self._build_gap_page()
        self._build_curve_page()
        self._build_drilldown_page()
        self._build_quality_page()

    def _build_summary_page(self) -> None:
        layout = QVBoxLayout(self._summary_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        cards = QGridLayout()
        cards.setSpacing(7)
        definitions = (
            ("BASE_EVE", "VEP base", "Valor económico del patrimonio"),
            ("WORST_EVE_LOSS", "Peor pérdida ΔVEP", "Mayor caída frente al escenario base"),
            ("EVE_TIER1_RATIO", "ΔVEP / CN1", "Exposición sobre Capital Nivel 1"),
            ("TIER1_CAPITAL", "Capital Nivel 1", "Denominador de exposición RTILB"),
            ("CALCULATED_POSITIONS", "Posiciones calculadas", "Perímetro incluido en VEP"),
        )
        for index, (key, caption, helper) in enumerate(definitions):
            cards.addWidget(self._metric_card(key, caption, helper), index // 3, index % 3)
        layout.addLayout(cards)

        readiness = QGroupBox("Preparación del cálculo")
        readiness.setStyleSheet(self._group_style())
        readiness_layout = QGridLayout(readiness)
        self._readiness_labels: dict[str, QLabel] = {}
        readiness_items = (
            ("assessed", "Evaluadas"),
            ("ready", "Listas"),
            ("incomplete", "Incompletas"),
            ("excluded", "Excluidas"),
            ("issues", "Incidencias"),
            ("mapping_pending", "Mapeo pendiente"),
        )
        for index, (key, caption) in enumerate(readiness_items):
            caption_label = QLabel(caption)
            caption_label.setStyleSheet("color:#566D7C; font-size:9px;")
            value = QLabel("-")
            value.setStyleSheet("color:#00345F; font-weight:800; font-size:13px;")
            self._readiness_labels[key] = value
            row = index // 3
            col = (index % 3) * 2
            readiness_layout.addWidget(caption_label, row, col)
            readiness_layout.addWidget(value, row, col + 1)
        layout.addWidget(readiness)
        layout.addStretch(1)

    def _metric_card(self, key: str, caption: str, helper: str) -> QFrame:
        card = QFrame()
        card.setObjectName("rateRiskMetricCard")
        card.setMinimumHeight(82)
        card.setStyleSheet(
            "QFrame#rateRiskMetricCard {background:#FFFFFF; border:1px solid #D5DEE3; "
            "border-radius:8px;}"
            "QFrame#rateRiskMetricCard:hover {background:#F0F8FC; border-color:#73B3DD;}"
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
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#7B8D98; font-size:8px; border:none;")
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(hint)
        self._kpi_values[key] = value
        return card

    def _build_scenario_page(self) -> None:
        layout = QVBoxLayout(self._scenario_page)
        layout.setContentsMargins(8, 8, 8, 8)
        self._scenario_table = self._table()
        self._scenario_table.setColumnCount(8)
        self._scenario_table.setHorizontalHeaderLabels(
            [
                "Escenario",
                "VEP",
                "ΔVEP",
                "Caída vs Base",
                "VP Activos",
                "VP Pasivos",
                "VP Fuera Balance",
                "Peor",
            ]
        )
        layout.addWidget(self._scenario_table)

    def _build_gap_page(self) -> None:
        layout = QVBoxLayout(self._gap_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        bucket_box = QGroupBox("Totales por banda")
        bucket_box.setStyleSheet(self._group_style())
        bucket_layout = QVBoxLayout(bucket_box)
        self._gap_bucket_table = self._table()
        self._gap_bucket_table.setColumnCount(4)
        self._gap_bucket_table.setHorizontalHeaderLabels(["#", "Banda", "Monto", "Moneda"])
        bucket_layout.addWidget(self._gap_bucket_table)
        layout.addWidget(bucket_box)

        matrix_box = QGroupBox("Matriz por fila regulatoria y banda")
        matrix_box.setStyleSheet(self._group_style())
        matrix_layout = QVBoxLayout(matrix_box)
        self._gap_matrix_table = self._table()
        self._gap_matrix_table.setColumnCount(5)
        self._gap_matrix_table.setHorizontalHeaderLabels(
            ["Fila SUGEF", "Banda", "#", "Monto", "Moneda"]
        )
        matrix_layout.addWidget(self._gap_matrix_table)
        layout.addWidget(matrix_box)

    def _build_curve_page(self) -> None:
        layout = QVBoxLayout(self._curve_page)
        layout.setContentsMargins(8, 8, 8, 8)
        self._curve_table = self._table()
        self._curve_table.setColumnCount(7)
        self._curve_table.setHorizontalHeaderLabels(
            ["Curva", "Fecha", "Moneda", "Escenario", "Tenor (años)", "Tasa", "Fuente"]
        )
        layout.addWidget(self._curve_table)

    def _build_drilldown_page(self) -> None:
        layout = QVBoxLayout(self._drilldown_page)
        layout.setContentsMargins(8, 8, 8, 8)
        self._flow_table = self._table()
        self._flow_table.setColumnCount(13)
        self._flow_table.setHorizontalHeaderLabels(
            [
                "Escenario",
                "Posición",
                "Lado",
                "Tipo flujo",
                "Estado monto",
                "Fecha flujo",
                "Fecha riesgo",
                "Monto",
                "Moneda",
                "DF",
                "FX",
                "VP",
                "Contribución VEP",
            ]
        )
        layout.addWidget(self._flow_table)

    def _build_quality_page(self) -> None:
        layout = QVBoxLayout(self._quality_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        quality_box = QGroupBox("Estado por posición")
        quality_box.setStyleSheet(self._group_style())
        quality_layout = QVBoxLayout(quality_box)
        self._quality_table = self._table()
        self._quality_table.setColumnCount(6)
        self._quality_table.setHorizontalHeaderLabels(
            ["Posición", "Estado", "Incidencias", "Errores", "Advertencias", "Info"]
        )
        quality_layout.addWidget(self._quality_table)
        layout.addWidget(quality_box)

        issues_box = QGroupBox("Incidencias de calidad")
        issues_box.setStyleSheet(self._group_style())
        issues_layout = QVBoxLayout(issues_box)
        self._issues_table = self._table()
        self._issues_table.setColumnCount(6)
        self._issues_table.setHorizontalHeaderLabels(
            ["Posición", "Estado", "Código", "Campo", "Severidad", "Detalle"]
        )
        issues_layout.addWidget(self._issues_table)
        layout.addWidget(issues_box)

        gap_coverage_box = QGroupBox("Cobertura GAP SUGEF")
        gap_coverage_box.setStyleSheet(self._group_style())
        gap_coverage_layout = QVBoxLayout(gap_coverage_box)
        self._gap_coverage_table = self._table()
        self._gap_coverage_table.setColumnCount(3)
        self._gap_coverage_table.setHorizontalHeaderLabels(
            ["Posición", "Código", "Detalle"]
        )
        gap_coverage_layout.addWidget(self._gap_coverage_table)
        layout.addWidget(gap_coverage_box)

        mapping_box = QGroupBox("Mapeo SUGEF")
        mapping_box.setStyleSheet(self._group_style())
        mapping_layout = QVBoxLayout(mapping_box)
        self._mapping_table = self._table()
        self._mapping_table.setColumnCount(4)
        self._mapping_table.setHorizontalHeaderLabels(
            ["Posición", "Estado", "Fila SUGEF", "Motivo"]
        )
        mapping_layout.addWidget(self._mapping_table)
        layout.addWidget(mapping_box)

    def set_read_model(self, read_model: RateRiskReadModel | None) -> None:
        """Render a certified read-model or an explicit unconfigured state."""
        self._read_model = read_model
        self._clear_tables()
        if read_model is None:
            self._set_unconfigured_state()
            return

        metadata = read_model.methodology
        self._cutoff_label.setText(f"Corte: {metadata.valuation_date:%d/%m/%Y}")
        self._set_analysis_status(read_model.analysis_status)
        effective = (
            metadata.effective_from.strftime("%d/%m/%Y")
            if metadata.effective_from is not None
            else "sin fecha de vigencia"
        )
        self._methodology_label.setText(
            f"Metodología: {metadata.code} · versión {metadata.version} · {metadata.status} · "
            f"vigencia {effective} · fuente {metadata.source_reference}"
        )
        self._warning_label.setVisible(bool(read_model.warnings))
        self._warning_label.setText(" · ".join(read_model.warnings))

        kpis = {item.key: item for item in read_model.kpis}
        for key, label in self._kpi_values.items():
            label.setText(self._format_kpi(kpis.get(key)))

        readiness = read_model.readiness
        self._readiness_labels["assessed"].setText(str(readiness.assessed_position_count))
        self._readiness_labels["ready"].setText(str(readiness.ready_position_count))
        self._readiness_labels["incomplete"].setText(str(readiness.incomplete_position_count))
        self._readiness_labels["excluded"].setText(str(readiness.excluded_position_count))
        self._readiness_labels["issues"].setText(str(readiness.data_issue_count))
        self._readiness_labels["mapping_pending"].setText(str(readiness.mapping_pending_count))

        self._populate_scenarios(read_model)
        self._populate_gap(read_model)
        self._populate_curves(read_model)
        self._populate_flows(read_model)
        self._populate_quality(read_model)

    def _set_unconfigured_state(self) -> None:
        self._cutoff_label.setText("Corte: pendiente")
        self._set_analysis_status("UNCONFIGURED")
        self._methodology_label.setText(
            "Módulo estructurado y sin fuente física configurada. Los datos podrán provenir de "
            "SQL, XML, OneDrive/Excel, PostgreSQL u otro adaptador aprobado."
        )
        self._warning_label.setVisible(True)
        self._warning_label.setText(
            "Sin cálculo RTILB cargado. AIP no mostrará VEP, ΔVEP, GAP ni curvas hasta recibir "
            "un read-model certificado desde la capa de aplicación."
        )
        for label in self._kpi_values.values():
            label.setText("N/D")
        for label in self._readiness_labels.values():
            label.setText("-")

    def _set_analysis_status(self, status: str) -> None:
        presentation = self._ANALYSIS_STATUS_PRESENTATION.get(
            status,
            (f"Estado: {status}", "#F2F4F5", "#566D7C", "#C9D2D7"),
        )
        text, background, foreground, border = presentation
        self._analysis_status_label.setText(text)
        self._analysis_status_label.setStyleSheet(
            "QLabel#rateRiskAnalysisStatus {"
            f"padding:7px 11px; background:{background}; color:{foreground}; "
            f"border:1px solid {border}; border-radius:6px; font-weight:700;"
            "}"
        )

    def _clear_tables(self) -> None:
        for table in (
            self._scenario_table,
            self._gap_bucket_table,
            self._gap_matrix_table,
            self._curve_table,
            self._flow_table,
            self._quality_table,
            self._issues_table,
            self._gap_coverage_table,
            self._mapping_table,
        ):
            table.setRowCount(0)

    def _populate_scenarios(self, read_model: RateRiskReadModel) -> None:
        self._scenario_table.setRowCount(len(read_model.scenario_rows))
        for row_index, row in enumerate(read_model.scenario_rows):
            values = (
                row.label,
                self._format_money(row.eve, row.currency),
                self._format_money(row.delta_eve, row.currency),
                self._format_money(row.fall_from_base, row.currency),
                self._format_money(row.pv_assets, row.currency),
                self._format_money(row.pv_liabilities, row.currency),
                self._format_money(row.pv_off_balance_net, row.currency),
                "Sí" if row.is_worst else "",
            )
            self._set_row(self._scenario_table, row_index, values)

    def _populate_gap(self, read_model: RateRiskReadModel) -> None:
        self._gap_bucket_table.setRowCount(len(read_model.gap_bucket_rows))
        for row_index, row in enumerate(read_model.gap_bucket_rows):
            self._set_row(
                self._gap_bucket_table,
                row_index,
                (
                    str(row.ordinal),
                    row.label,
                    self._format_money(row.amount, row.currency),
                    row.currency,
                ),
            )

        self._gap_matrix_table.setRowCount(len(read_model.gap_matrix_cells))
        for row_index, row in enumerate(read_model.gap_matrix_cells):
            self._set_row(
                self._gap_matrix_table,
                row_index,
                (
                    row.report_line_label,
                    row.bucket_label,
                    str(row.ordinal),
                    self._format_money(row.amount, row.currency),
                    row.currency,
                ),
            )

    def _populate_curves(self, read_model: RateRiskReadModel) -> None:
        self._curve_table.setRowCount(len(read_model.curve_rows))
        for row_index, row in enumerate(read_model.curve_rows):
            self._set_row(
                self._curve_table,
                row_index,
                (
                    row.curve_id,
                    row.as_of_date.strftime("%d/%m/%Y"),
                    row.currency,
                    row.scenario,
                    f"{row.tenor_years:f}",
                    self._format_rate(row.rate),
                    row.source_reference,
                ),
            )

    def _populate_flows(self, read_model: RateRiskReadModel) -> None:
        self._flow_table.setRowCount(len(read_model.valuation_flow_rows))
        for row_index, row in enumerate(read_model.valuation_flow_rows):
            self._set_row(
                self._flow_table,
                row_index,
                (
                    row.scenario,
                    row.position_id,
                    row.side,
                    row.flow_type,
                    row.amount_status,
                    row.cashflow_date.strftime("%d/%m/%Y"),
                    row.risk_date.strftime("%d/%m/%Y"),
                    f"{row.amount:,.2f}",
                    row.amount_currency,
                    f"{row.discount_factor:.8f}",
                    f"{row.exchange_rate:.8f}",
                    self._format_money(row.present_value_reporting, row.reporting_currency),
                    self._format_money(row.signed_eve_contribution, row.reporting_currency),
                ),
            )

    def _populate_quality(self, read_model: RateRiskReadModel) -> None:
        self._quality_table.setRowCount(len(read_model.position_quality_rows))
        for row_index, row in enumerate(read_model.position_quality_rows):
            self._set_row(
                self._quality_table,
                row_index,
                (
                    row.position_id,
                    row.status,
                    str(row.issue_count),
                    str(row.error_count),
                    str(row.warning_count),
                    str(row.info_count),
                ),
            )

        self._issues_table.setRowCount(len(read_model.data_issue_rows))
        for row_index, row in enumerate(read_model.data_issue_rows):
            self._set_row(
                self._issues_table,
                row_index,
                (
                    row.position_id,
                    row.status,
                    row.code,
                    row.field_name or "",
                    row.severity,
                    row.message,
                ),
            )

        self._gap_coverage_table.setRowCount(len(read_model.gap_coverage_issue_rows))
        for row_index, row in enumerate(read_model.gap_coverage_issue_rows):
            self._set_row(
                self._gap_coverage_table,
                row_index,
                (row.position_id, row.code, row.message),
            )

        self._mapping_table.setRowCount(len(read_model.mapping_rows))
        for row_index, row in enumerate(read_model.mapping_rows):
            self._set_row(
                self._mapping_table,
                row_index,
                (
                    row.position_id,
                    row.status,
                    row.report_line_label or row.report_line or "",
                    row.reason,
                ),
            )

    @staticmethod
    def _set_row(table: QTableWidget, row: int, values: tuple[str, ...]) -> None:
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column > 0:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
            table.setItem(row, column, item)

    @classmethod
    def _format_money(cls, value: Decimal, currency: str) -> str:
        symbol = "₡" if currency == "CRC" else f"{currency} "
        return f"{symbol}{value / cls._MONEY_SCALE:,.2f} MM"

    @staticmethod
    def _format_rate(value: Decimal) -> str:
        return f"{value * Decimal('100'):.4f}%"

    @classmethod
    def _format_kpi(cls, kpi: RateRiskKpi | None) -> str:
        if kpi is None:
            return "N/D"
        if kpi.unit == "MONEY" and kpi.currency is not None:
            return cls._format_money(kpi.value, kpi.currency)
        if kpi.unit == "RATIO":
            return f"{kpi.value * Decimal('100'):.2f}%"
        if kpi.unit == "COUNT":
            return f"{kpi.value:,.0f}"
        return f"{kpi.value}"
