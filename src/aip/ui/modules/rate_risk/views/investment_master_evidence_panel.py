"""On-demand institutional investment-master inspection, not an IRRBB calculation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from aip.product.configured.irrbb.investment_master_cutoff_audit import (
    inspect_investment_master_cutoff,
)
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


class _InvestmentMasterWorker(QThread):
    completed = Signal(object)
    blocked = Signal(str)

    def __init__(self, cutoff: date) -> None:
        super().__init__()
        self._cutoff = cutoff

    def run(self) -> None:
        try:
            folder = EnvironmentLoader().load_source_config().folder_watch
            evidence = inspect_investment_master_cutoff(cutoff=self._cutoff, folder=folder)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            self.blocked.emit(f"Lectura del Maestro bloqueada ({type(exc).__name__})")
            return
        self.completed.emit(evidence)


class InvestmentMasterEvidencePanel(QWidget):
    """Do not convert source positions directly into cashflow or GAP bands."""

    _HEADERS = (
        "Moneda nativa",
        "Posiciones",
        "Principal informado",
        "Con principal válido",
        "Sin principal / moneda",
        "Con vencimiento",
        "Sin vencimiento válido",
    )

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("rateRiskInvestmentMasterEvidencePanel")
        self._cutoff: date | None = None
        self._worker: _InvestmentMasterWorker | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        top = QHBoxLayout()
        self._status = QLabel("Maestro de Inversiones: corte pendiente")
        self._status.setObjectName("rateRiskInvestmentMasterEvidenceStatus")
        self._status.setWordWrap(True)
        top.addWidget(self._status, 1)
        self._button = QPushButton("Auditar Maestro del corte")
        self._button.setObjectName("rateRiskInvestmentMasterEvidenceRun")
        self._button.clicked.connect(self.run_audit)
        top.addWidget(self._button)
        layout.addLayout(top)

        note = QLabel(
            "Fuente exclusiva: Maestro institucional de inversiones con fecha exacta. "
            "No se usa el XML de inversiones para sustituir posiciones. "
            "Se muestran importes originales sin convertir moneda. "
            "La fecha del archivo, los saldos y los vencimientos NO certifican "
            "cronogramas de cupones ni GAP RTILB de 19 bandas. Los importes "
            "sin moneda nativa son valores numéricos sin unidad atribuible."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self._certification = QLabel("Certificación de origen: sin evaluar")
        self._certification.setObjectName("rateRiskInvestmentMasterCertification")
        self._certification.setWordWrap(True)
        layout.addWidget(self._certification)
        self._currency_mapping = QLabel("Monedas del Maestro: pendientes de revisar")
        self._currency_mapping.setObjectName("rateRiskInvestmentSourceCurrencyMapping")
        self._currency_mapping.setWordWrap(True)
        layout.addWidget(self._currency_mapping)

        self._table = QTableWidget(0, len(self._HEADERS))
        self._table.setObjectName("rateRiskInvestmentMasterEvidenceTable")
        self._table.setHorizontalHeaderLabels(self._HEADERS)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tabs = QTabWidget()
        self._tabs.setObjectName("rateRiskInvestmentEvidenceTabs")
        self._tabs.addTab(self._table, "Posiciones por moneda")
        self._bands = self._create_table(
            ("Moneda", "Banda de vencimiento", "Posiciones", "Principal fuente"),
            "rateRiskInvestmentObservedBandsTable",
        )
        self._excluded = self._create_table(
            ("Moneda", "Motivo sin asignación", "Posiciones", "Principal fuente válido"),
            "rateRiskInvestmentMaturityExclusionsTable",
        )
        self._reconciliation = self._create_table(
            (
                "Moneda de origen",
                "Principal numérico original",
                "Asignado a bandas",
                "Excluido",
                "Diferencia",
                "Estado",
            ),
            "rateRiskInvestmentNativeCurrencyReconciliationTable",
        )
        self._tabs.addTab(self._bands, "19 bandas · vencimiento")
        self._tabs.addTab(self._excluded, "Sin bandeo · motivo")
        self._tabs.addTab(self._reconciliation, "Conciliación por moneda")
        layout.addWidget(self._tabs, 1)

    @staticmethod
    def _create_table(headers: tuple[str, ...], object_name: str) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setObjectName(object_name)
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def _add_group(
        self,
        table: QTableWidget,
        values: tuple[str, ...],
        *,
        numeric_columns: tuple[int, ...] = (2, 3),
    ) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for index, value in enumerate(values):
            item = QTableWidgetItem(
                self._format_number(value) if index in numeric_columns else value
            )
            item.setToolTip(f"Valor de origen: {value}")
            if index in numeric_columns:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, index, item)

    def set_cutoff(self, cutoff: date) -> None:
        if self._cutoff == cutoff:
            return
        self._cutoff = cutoff
        self._table.setRowCount(0)
        self._bands.setRowCount(0)
        self._excluded.setRowCount(0)
        self._reconciliation.setRowCount(0)
        self._status.setText(f"Maestro {cutoff:%d/%m/%Y} · auditoría pendiente")
        self._certification.setText("Certificación de origen: pendiente")
        self._currency_mapping.setText("Monedas del Maestro: pendientes de revisar")

    def run_audit(self) -> None:
        if self._cutoff is None or self._worker is not None:
            return
        cutoff = self._cutoff
        worker = _InvestmentMasterWorker(cutoff)
        self._worker = worker
        self._button.setEnabled(False)
        self._status.setText(f"Leyendo Maestro del {cutoff:%d/%m/%Y}…")
        worker.completed.connect(lambda report: self._receive_result(cutoff, report))
        worker.blocked.connect(lambda message: self._receive_error(cutoff, message))
        worker.finished.connect(self._finish_worker)
        worker.start()

    def _receive_result(self, cutoff: date, report: dict[str, object]) -> None:
        if cutoff != self._cutoff:
            return
        self._table.setRowCount(0)
        self._bands.setRowCount(0)
        self._excluded.setRowCount(0)
        self._reconciliation.setRowCount(0)
        status = str(report.get("status", "UNAVAILABLE"))
        if status != "INVESTMENT_MASTER_SOURCE_INSPECTED_NOT_CERTIFIED":
            self._status.setText(f"Maestro {cutoff:%d/%m/%Y}: {status}. Sin datos reemplazados.")
            self._certification.setText("Certificación: no disponible")
            self._currency_mapping.setText("Monedas del Maestro: no verificadas")
            return

        self._status.setText(
            f"Maestro {cutoff:%d/%m/%Y} · {report['accepted_positions']} posiciones "
            f"· {report['rejected_rows']} filas rechazadas · "
            f"{report['warning_count']} advertencias"
        )
        blocking_data = report.get("blocking_requirements", [])
        pending_data = report.get("not_assessed_requirements", [])
        blocking = blocking_data if isinstance(blocking_data, list) else []
        pending = pending_data if isinstance(pending_data, list) else []
        self._certification.setText(
            f"Certificación: {report['certification_status']} · "
            f"{len(blocking)} requisitos bloqueados · "
            f"{len(pending)} pendientes. Sin GAP ni ΔEVE/ΔNII."
        )
        mappings = report.get("source_currency_mappings", [])
        aliases = (
            [
                f'{item["source_currency"]} → {item["normalized_currency"]}: '
                f'{item["positions"]} posiciones, sin conversión cambiaria'
                for item in mappings
                if isinstance(item, dict) and item.get("mapping_status") == "EXPLICIT_ALIAS"
            ]
            if isinstance(mappings, list)
            else []
        )
        self._currency_mapping.setText(
            "Equivalencias explícitas del Maestro: " + "; ".join(aliases)
            if aliases
            else "Monedas del Maestro: sin equivalencias explícitas aplicadas"
        )
        groups = report.get("currencies", [])
        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict):
                continue
            values = (
                str(group["source_currency"]),
                str(group["positions"]),
                str(group["source_principal"]),
                str(group["principal_records"]),
                str(group["principal_missing"]),
                str(group["maturity_present"]),
                str(group["maturity_missing_or_past"]),
            )
            row = self._table.rowCount()
            self._table.insertRow(row)
            for col, value in enumerate(values):
                display = self._format_number(value) if col in (1, 2, 3, 4, 5, 6) else value
                item = QTableWidgetItem(display)
                item.setToolTip(f"Valor de origen: {value}")
                if col:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(row, col, item)

        bands = report.get("maturity_bands", [])
        for record in bands if isinstance(bands, list) else []:
            if not isinstance(record, dict):
                continue
            self._add_group(
                self._bands,
                (
                    str(record["source_currency"]),
                    f'{record["ordinal"]}. {record["band"]}',
                    str(record["positions"]),
                    str(record["source_principal"]),
                ),
            )
        exclusions = report.get("maturity_exclusions", [])
        explanations = {
            "MISSING_NATIVE_CURRENCY": "Falta moneda original",
            "UNSUPPORTED_CURRENCY": "Moneda sin catálogo confirmado",
            "INVALID_OR_MISSING_SOURCE_PRINCIPAL": "Falta principal válido",
            "MISSING_OR_PAST_MATURITY": "Sin vencimiento vigente",
            "MISSING_OR_INVALID_MATURITY": "Vencimiento ausente o inválido",
            "PAST_MATURITY": "Vencimiento anterior al corte",
        }
        for record in exclusions if isinstance(exclusions, list) else []:
            if not isinstance(record, dict):
                continue
            code = str(record["reason"])
            self._add_group(
                self._excluded,
                (
                    str(record["source_currency"]),
                    explanations.get(code, code),
                    str(record["positions"]),
                    str(record["valid_source_principal"]),
                ),
            )

        reconciliation = report.get("maturity_reconciliation", [])
        for record in reconciliation if isinstance(reconciliation, list) else []:
            if not isinstance(record, dict):
                continue
            status_code = str(record.get("status", "UNCONFIRMED"))
            display_status = (
                "Bloqueada: moneda sin equivalencia confirmada"
                if status_code == "BLOCKED_NATIVE_CURRENCY"
                else (
                    "Principal original conciliado"
                    if status_code == "RECONCILED_SOURCE_CURRENCY"
                    else status_code
                )
            )
            self._add_group(
                self._reconciliation,
                (
                    str(record["source_currency"]),
                    str(record["eligible_source_principal"]),
                    str(record["observed_principal"]),
                    str(record["excluded_valid_principal"]),
                    str(record["difference"]),
                    display_status,
                ),
                numeric_columns=(1, 2, 3, 4),
            )

    def _receive_error(self, cutoff: date, message: str) -> None:
        if cutoff != self._cutoff:
            return
        self._table.setRowCount(0)
        self._bands.setRowCount(0)
        self._excluded.setRowCount(0)
        self._reconciliation.setRowCount(0)
        self._status.setText(message)
        self._certification.setText("Certificación: bloqueada")
        self._currency_mapping.setText("Monedas del Maestro: sin verificar")

    def _finish_worker(self) -> None:
        worker = self._worker
        if worker is not None and worker.isFinished():
            self._worker = None
            worker.deleteLater()
            self._button.setEnabled(True)

    @staticmethod
    def _format_number(raw: str) -> str:
        try:
            value = Decimal(raw)
        except (InvalidOperation, ValueError):
            return raw
        if not value.is_finite():
            return raw
        formatted = format(value, ",f")
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
