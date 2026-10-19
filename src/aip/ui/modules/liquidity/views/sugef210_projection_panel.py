"""Configured-only SUGEF 2-10 liquidity planning panel.

Reads institutional XML investment source on demand. It NEVER shows example
numbers and does not pretend incomplete source coverage is a complete forecast.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    sugef210_windows,
)
from aip.product.configured.liquidity.sugef210_source_audit_cli import (
    inspect_xml_investment_source,
)
from aip.product.configured.liquidity.financial_plan_source import (
    FinancialPlanSourceAudit,
    read_financial_plan_assumptions,
)


class _SUGEF210SourceWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, cutoff: date) -> None:
        super().__init__()
        self._cutoff = cutoff

    def run(self) -> None:
        try:
            report = inspect_xml_investment_source(self._cutoff)
        except Exception as exc:  # UI must fail closed and never leak paths/tokens
            self.failed.emit(type(exc).__name__)
            return
        self.completed.emit(report)


class _SUGEF210FinancialPlanWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, cutoff: date, source_path: str) -> None:
        super().__init__()
        self._cutoff = cutoff
        self._source_path = source_path

    def run(self) -> None:
        try:
            evidence = read_financial_plan_assumptions(
                self._source_path, cutoff=self._cutoff
            )
        except Exception as exc:
            self.failed.emit(type(exc).__name__)
            return
        self.completed.emit(evidence)


class SUGEF210ProjectionPanel(QWidget):
    """Liquidity horizon framework + REAL source coverage, no DEMO waterfall."""

    _PLAN_HEADERS = (
        "Mes", "Supuesto / Driver", "Valor 2026 (¢ millones ref.)",
        "Área", "Sentido", "Tratamiento", "Celda fuente",
    )
    _PLAN_PARAMETER_HEADERS = (
        "ID", "Parámetro / actividad", "Valor", "Unidad",
        "Periodicidad", "Tipo", "Ref. Plan", "Tratamiento Liquidez", "Celda fuente",
    )
    _WINDOW_HEADERS = (
        "Horizonte", "Desde", "Hasta", "Apertura", "CRC neto", "USD neto",
        "Estado", "Principal Maestro CRC*", "Principal Maestro USD*",
    )
    _DETAIL_HEADERS = (
        "Referencia XML", "ID original", "Cuenta", "Moneda origen",
        "Saldo principal", "Id instrumento", "ISIN", "Serie",
        "Conciliación con Maestro", "Clasificación",
    )
    _SOURCE_HEADERS = (
        "Cuenta XML",
        "Moneda XML",
        "Registros",
        "Principal XML",
        "Clasificación",
        "Coincide ISIN",
        "Sin conciliación",
    )

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sugef210LiquidityProjectionPanel")
        self._worker: _SUGEF210SourceWorker | None = None
        self._report: dict[str, object] | None = None
        self._plan_worker: _SUGEF210FinancialPlanWorker | None = None
        self._plan_audit: FinancialPlanSourceAudit | None = None
        self._cutoff = date.today()
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)

        heading = QLabel("FLUJO PROYECTADO DE FONDOS · SUGEF 2-10")
        heading.setStyleSheet("font-size:14pt; font-weight:700; color:#064F87;")
        main.addWidget(heading)
        explanation = QLabel(
            "Horizontes diarios 0–7, semanales 8–30, mensuales y trimestrales "
            "hasta un año. Activos, pasivos, fuera de balance y eventos de negocio; "
            "la proyección requiere flujos contractuales, saldos iniciales y "
            "supuestos institucionales aprobados. Sin datos DEMO."
        )
        explanation.setWordWrap(True)
        main.addWidget(explanation)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Corte institucional:"))
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd/MM/yyyy")
        self._date.setDate(QDate(self._cutoff.year, self._cutoff.month, self._cutoff.day))
        self._date.dateChanged.connect(self._on_date_changed)
        controls.addWidget(self._date)
        self._button = QPushButton("Inspeccionar XML de inversiones")
        self._button.clicked.connect(self.run_source_audit)
        controls.addWidget(self._button)
        self._export = QPushButton("Exportar conciliación a Excel")
        self._export.setEnabled(False)
        self._export.clicked.connect(self.export_reconciliation)
        controls.addWidget(self._export)
        self._plan_button = QPushButton("Cargar planificación financiera 2026")
        self._plan_button.clicked.connect(self.select_financial_plan)
        controls.addWidget(self._plan_button)
        controls.addStretch(1)
        main.addLayout(controls)

        self._status = QLabel(
            "Proyección integral no certificada. Seleccione corte y audite XML real."
        )
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "padding:8px; background:#EAF3FA; color:#174E78;"
            "border-radius:6px; font-weight:600;"
        )
        main.addWidget(self._status)
        self._plan_status = QLabel(
            "Plan financiero: archivo no cargado. Sus supuestos NO se activan automáticamente."
        )
        self._plan_status.setWordWrap(True)
        self._plan_status.setStyleSheet(
            "padding:7px; background:#EDF4FA; color:#064F87; border-radius:6px;"
        )
        main.addWidget(self._plan_status)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._windows = self._table(self._WINDOW_HEADERS, "sugef210LiquidityWindows")
        self._accounts = self._table(self._SOURCE_HEADERS, "sugef210InvestmentXMLAccounts")
        splitter.addWidget(self._windows)
        splitter.addWidget(self._accounts)
        self._records = self._table(self._DETAIL_HEADERS, "sugef210XMLRecordEvidence")
        splitter.addWidget(self._records)
        self._planning_tabs = QTabWidget()
        self._plan_months = self._table(
            self._PLAN_HEADERS, "sugef210FinancialPlanMonthlyEvidence"
        )
        self._plan_parameters = self._table(
            self._PLAN_PARAMETER_HEADERS, "sugef210FinancialPlanParameters"
        )
        self._planning_tabs.addTab(self._plan_months, "Plan financiero · calendario")
        self._planning_tabs.addTab(self._plan_parameters, "Plan financiero · supuestos")
        splitter.addWidget(self._planning_tabs)
        splitter.setSizes([235, 150, 210, 220])
        main.addWidget(splitter, 1)
        self._fill_windows()

        note = QLabel(
            "Importante: Crediticio_InversionesActivas.xml se utiliza para detectar "
            "inversiones en cuentas corrientes no incluidas en el Maestro. "
            "Sus saldos no son ingresos futuros ni caja disponible hasta "
            "confirmar cuenta contable, conciliación, restricciones y retiro efectivo. "
            "CRC y USD permanecen separados. Los eventos fuera de balance requieren fuente "
            "independiente y los supuestos deben estar documentados y aprobados."
        )
        note.setWordWrap(True)
        main.addWidget(note)

    @staticmethod
    def _table(headers: tuple[str, ...], name: str) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setObjectName(name)
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    @staticmethod
    def _append(table: QTableWidget, values: tuple[str, ...]) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            if col in (2, 3, 5, 6):
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            table.setItem(row, col, item)

    def _fill_windows(self) -> None:
        self._windows.setRowCount(0)
        for window in sugef210_windows(self._cutoff):
            self._append(
                self._windows,
                (
                    window.label,
                    window.start.strftime("%d/%m/%Y"),
                    window.end.strftime("%d/%m/%Y"),
                    window.frequency,
                    "N/D",
                    "N/D",
                    "Fuente incompleta",
                    "N/D",
                    "N/D",
                ),
            )


    def _fill_master_maturities(self, report: dict[str, object]) -> None:
        """Show dated original principal evidence, never mislabel it net cash."""
        maturity = report.get("master_maturity_evidence")
        if not isinstance(maturity, dict):
            return
        if maturity.get("status") != "MASTER_PRINCIPAL_ONLY_PARTIAL_LIQUIDITY_EVIDENCE":
            return
        amounts = {
            (str(row.get("key")), str(row.get("currency"))): str(
                row.get("principal_maturing", "N/D")
            )
            for row in maturity.get("maturity_windows", [])
            if isinstance(row, dict)
        }
        for index, window in enumerate(sugef210_windows(self._cutoff)):
            for column, currency in ((7, "CRC"), (8, "USD")):
                value = amounts.get((window.key, currency), "N/D")
                item = QTableWidgetItem(value)
                item.setToolTip(
                    "Principal con fecha de vencimiento verificable en Maestro. "
                    "NO representa una entrada líquida certificada ni incluye cupones."
                )
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._windows.setItem(index, column, item)

    def _on_date_changed(self, value: QDate) -> None:
        self._cutoff = value.toPython()
        self._accounts.setRowCount(0)
        self._records.setRowCount(0)
        self._report = None
        self._export.setEnabled(False)
        self._plan_audit = None
        self._plan_months.setRowCount(0)
        self._plan_parameters.setRowCount(0)
        self._plan_status.setText(
            "Plan del corte anterior invalidado. Volver a cargar para este corte."
        )
        self._status.setText(
            "Corte cambiado: auditoría pendiente. No se reutilizan cifras del corte anterior."
        )
        self._fill_windows()

    def run_source_audit(self) -> None:
        if self._worker is not None:
            return
        requested_cutoff = self._cutoff
        worker = _SUGEF210SourceWorker(requested_cutoff)
        self._worker = worker
        self._button.setEnabled(False)
        self._status.setText("Consultando XML institucional; no se calculan flujos sin evidencia…")
        worker.completed.connect(lambda report: self._receive(requested_cutoff, report))
        worker.failed.connect(lambda category: self._error(requested_cutoff, category))
        worker.finished.connect(self._release_worker)
        worker.start()

    def _receive(self, cutoff: date, report: dict[str, object]) -> None:
        if cutoff != self._cutoff:
            return
        self._accounts.setRowCount(0)
        self._records.setRowCount(0)
        self._report = None
        self._export.setEnabled(False)
        status = str(report.get("status", "BLOCKED"))
        if status != "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH":
            self._status.setText(
                f"Fuente de inversiones no utilizable para inspección: {status}"
            )
            return
        self._fill_master_maturities(report)
        for group in report.get("accounts", []):
            if not isinstance(group, dict):
                continue
            self._append(
                self._accounts,
                (
                    str(group["account_code"]),
                    str(group["currency_source_code"]),
                    str(group["record_count"]),
                    str(group["source_principal"]),
                    str(group["classification"]),
                    str(group["master_isin_matches"]),
                    str(group["unverified_master_overlap"]),
                ),
            )
        for record in report.get("record_evidence", []):
            if not isinstance(record, dict):
                continue
            self._append(
                self._records,
                (
                    str(record.get("source_reference") or ""),
                    str(record.get("raw_record_id") or ""),
                    str(record.get("account_code") or ""),
                    str(record.get("currency_source_code") or ""),
                    str(record.get("source_principal") or "N/D"),
                    str(record.get("instrument_id") or ""),
                    str(record.get("isin") or ""),
                    str(record.get("series") or ""),
                    str(record.get("master_reconciliation") or ""),
                    str(record.get("classification") or ""),
                ),
            )
        self._report = report
        self._export.setEnabled(True)
        self._status.setText(
            f"XML inversiones: {report.get('xml_records_read', 0)} registros; "
            f"{self._accounts.rowCount()} cuentas/monedas inspeccionadas; "
            f"{self._records.rowCount()} registros trazables. "
            f"Maestro: {report.get('master_review_status', 'N/D')}. "
            "Disponibilidad a la vista: NO CERTIFICADA. "
            "Flujo integral: pendiente de fuentes y supuestos institucionales."
        )

    def _error(self, cutoff: date, category: str) -> None:
        if cutoff == self._cutoff:
            self._accounts.setRowCount(0)
            self._records.setRowCount(0)
            self._report = None
            self._export.setEnabled(False)
            self._status.setText(
                f"BLOCKED_SOURCE_READ ({category}). Sin sustituir información ni mostrar flujos."
            )



    def select_financial_plan(self) -> None:
        """Read local institutional workbook without copying it into the Git repository."""
        if self._plan_worker is not None:
            return
        source_path, _file_filter = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Matriz de Supuestos del Flujo de Efectivo 2026",
            "",
            "Excel (*.xlsx)",
        )
        if not source_path:
            return
        cutoff = self._cutoff
        worker = _SUGEF210FinancialPlanWorker(cutoff, source_path)
        self._plan_worker = worker
        self._plan_button.setEnabled(False)
        self._plan_status.setText(
            "Leyendo la matriz institucional en modo seguro. "
            "No se registrarán importes como flujos contractuales."
        )
        worker.completed.connect(
            lambda evidence: self._receive_financial_plan(cutoff, evidence)
        )
        worker.failed.connect(lambda reason: self._financial_plan_error(cutoff, reason))
        worker.finished.connect(self._release_plan_worker)
        worker.start()

    def _receive_financial_plan(
        self, cutoff: date, evidence: FinancialPlanSourceAudit
    ) -> None:
        if cutoff != self._cutoff:
            return
        self._plan_audit = evidence
        self._plan_months.setRowCount(0)
        self._plan_parameters.setRowCount(0)
        for row in evidence.monthly_inputs:
            self._append(
                self._plan_months,
                (
                    f"{row.month:02d}/{row.year}",
                    row.driver,
                    str(row.reported_value),
                    str(row.area or "NO EFECTIVO / PARÁMETRO"),
                    str(row.side or "—"),
                    row.status,
                    row.source_cell,
                ),
            )
        for param in evidence.parameters:
            self._append(
                self._plan_parameters,
                (
                    str(param.plan_id), param.name,
                    param.value if param.value is not None else "N/D",
                    param.unit, param.periodicity, param.cashflow_type,
                    param.plan_reference, param.liquidity_role, param.source_cell,
                ),
            )
        next_months = sum(
            row.period_start > date(cutoff.year, cutoff.month, 1)
            and row.classification == "PLANNED_POTENTIAL_CASHFLOW"
            for row in evidence.monthly_inputs
        )
        self._plan_status.setText(
            f"Plan {evidence.plan_year}: {len(evidence.parameters)} supuestos, "
            f"{next_months} importes mensuales futuros identificados. "
            f"SHA256: {evidence.sha256[:16]}… "
            "Datos de referencia en ¢ millones; NO son CRC efectivo ni USD certificado. "
            "Pendientes: aprobación, fecha, moneda original y no duplicación."
        )

    def _financial_plan_error(self, cutoff: date, reason: str) -> None:
        if cutoff != self._cutoff:
            return
        self._plan_audit = None
        self._plan_months.setRowCount(0)
        self._plan_parameters.setRowCount(0)
        self._plan_status.setText(
            f"BLOCKED_FINANCIAL_PLAN_{reason}: no se incorporaron proyecciones."
        )

    def _release_plan_worker(self) -> None:
        worker = self._plan_worker
        if worker is not None and worker.isFinished():
            self._plan_worker = None
            worker.deleteLater()
            self._plan_button.setEnabled(True)

    def export_reconciliation(self) -> None:
        """Export real audit evidence; never classify a balance as cash."""
        if self._report is None:
            return
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            "Exportar auditoría XML–Maestro",
            f"SUGEF210_Conciliacion_{self._cutoff.isoformat()}.xlsx",
            "Excel (*.xlsx)",
        )
        if not selected:
            return
        from openpyxl import Workbook

        workbook = Workbook()
        metadata = workbook.active
        assert metadata is not None
        metadata.title = "Control"
        report = self._report
        for key in (
            "cutoff", "xml_month", "xml_source", "entity_id", "sha256",
            "master_review_status", "master_positions_read", "xml_records_read",
            "invalid_source_principal", "missing_account_codes",
            "repeated_source_record_ids",
        ):
            metadata.append((key, str(report.get(key, "N/D"))))
        metadata.append(("disponibilidad_certificada", "NO"))
        metadata.append(("flujo_integral_certificado", "NO"))
        metadata.append(("nota", "Identificadores no prueban titularidad ni retiro disponible"))

        def safe(value: object) -> str:
            content = "" if value is None else str(value)
            return "'" + content if content.startswith(("=", "+", "-", "@")) else content

        accounts = workbook.create_sheet("Cuentas XML")
        account_keys = (
            "account_code", "currency_source_code", "record_count",
            "source_principal", "classification", "master_isin_matches",
            "unverified_master_overlap",
        )
        accounts.append(account_keys)
        for row in report.get("accounts", []):
            if isinstance(row, dict):
                accounts.append(tuple(safe(row.get(field)) for field in account_keys))

        maturity = report.get("master_maturity_evidence")
        if isinstance(maturity, dict):
            schedule = workbook.create_sheet("Vencimientos Maestro")
            keys = ("key", "from", "to", "currency", "principal_maturing", "status")
            schedule.append(keys)
            for item in maturity.get("maturity_windows", []):
                if isinstance(item, dict):
                    schedule.append(tuple(safe(item.get(key)) for key in keys))

        records = workbook.create_sheet("Detalle conciliación")
        record_keys = (
            "source_reference", "raw_record_id", "record_ordinal", "action",
            "account_code", "currency_source_code", "source_principal_raw",
            "source_principal", "instrument_id", "isin", "series",
            "classification", "master_reconciliation", "withdrawable_amount",
        )
        records.append(record_keys)
        for row in report.get("record_evidence", []):
            if isinstance(row, dict):
                records.append(tuple(safe(row.get(field)) for field in record_keys))
        for sheet in workbook:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
        try:
            workbook.save(selected)
        except OSError as exc:
            self._status.setText(
                f"Exportación bloqueada: {type(exc).__name__}. XML y Maestro sin cambios."
            )
            return
        self._status.setText(
            "Conciliación exportada en Excel. Disponibilidad de caja y "
            "diferencias de portafolio pendientes de certificación."
        )

    def _release_worker(self) -> None:
        worker = self._worker
        if worker is not None and worker.isFinished():
            self._worker = None
            worker.deleteLater()
            self._button.setEnabled(True)
