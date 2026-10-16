"""Passive 19-band observed-maturity evidence; never a certified RTILB GAP."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import ParseError

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

from aip.product.configured.configuration.institutional_paths import (
    expand_environment_path,
)
from aip.product.configured.irrbb.captaciones_maturity_19band_audit import (
    inspect_fixed_term_maturities,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


class _MaturityAuditWorker(QThread):
    completed = Signal(object)
    blocked = Signal(str)

    def __init__(self, cutoff: date) -> None:
        super().__init__()
        self._cutoff = cutoff

    def run(self) -> None:
        try:
            config = EnvironmentLoader().load_source_config().xml_confia
            root = expand_environment_path(config.root)
            if not config.enabled or not root:
                self.blocked.emit("XML CONFÍA no configurado")
                return
            result = inspect_fixed_term_maturities(XMLConfiaMonthlySourceReader(root), self._cutoff)
        except (OSError, ValueError, KeyError, ParseError) as exc:
            self.blocked.emit(f"Auditoría bloqueada ({type(exc).__name__})")
            return
        self.completed.emit(result)


class Maturity19BandEvidencePanel(QWidget):
    """On-demand source maturity buckets; not interest-repricing or payments."""

    _REASONS = {
        "SIGHT_NMD_BEHAVIORAL_PROFILE_REQUIRED": "A la vista · requiere perfil comportamental",
        "MATURED_TERM_POLICY_REQUIRED": "Plazo vencido · requiere tratamiento aprobado",
        "TERM_NOT_FIXED_REPRICING_REQUIRED": "TipoTasa distinto de F · revisar código/reprecio",
        "TERM_MISSING_MATURITY": "Plazo · falta fecha de vencimiento",
        "TERM_INVALID_MATURITY": "Plazo · fecha de vencimiento inválida",
        "TERM_PAST_MATURITY": "Plazo · vencimiento anterior al corte",
        "INVALID_PRINCIPAL": "Importe principal inválido",
        "MISSING_CURRENCY": "Código de moneda faltante",
        "UNSUPPORTED_ACCOUNT": "Cuenta contable sin clasificación aprobada",
    }

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("rateRiskMaturity19BandEvidencePanel")
        self._cutoff: date | None = None
        self._worker: _MaturityAuditWorker | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        top = QHBoxLayout()
        self._status = QLabel("Corte de evidencia pendiente")
        self._status.setObjectName("rateRiskMaturity19BandEvidenceStatus")
        self._status.setWordWrap(True)
        top.addWidget(self._status, 1)
        self._button = QPushButton("Auditar vencimientos XML")
        self._button.setObjectName("rateRiskMaturity19BandEvidenceRun")
        self._button.clicked.connect(self.run_audit)
        top.addWidget(self._button)
        layout.addLayout(top)

        note = QLabel(
            "Solo captaciones a plazo con tasa fija y fecha de vencimiento XML "
            "verificable. Usa el calendario canónico de 19 bandas, pero NO es "
            "GAP SUGEF, cronograma de cupones, repricing ni ΔEVE/ΔNII. "
            "Falta conciliar certificados CAPF. Moneda = código XML original. "
            "Cuentas a la vista y operaciones no aptas quedan excluidas."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self._tabs = QTabWidget()
        self._bands = self._table(
            ("Moneda XML", "Banda", "Registros", "Saldo principal fuente"),
            (120, 260, 130, 250),
        )
        self._bands.setObjectName("rateRiskMaturity19BandEvidenceTable")
        self._excluded = self._table(
            ("Moneda XML", "Motivo sin asignación", "Registros", "Saldo principal fuente"),
            (120, 370, 130, 250),
        )
        self._excluded.setObjectName("rateRiskMaturity19BandExclusionTable")
        self._tabs.addTab(self._bands, "Vencimientos observados")
        self._tabs.addTab(self._excluded, "Sin asignar · con motivo")
        self._reconciliation = self._table(
            (
                "Moneda XML",
                "Principal válido de origen",
                "Principal en bandas",
                "Principal excluido",
                "Registros con principal inválido",
                "Estado",
            ),
            (120, 230, 230, 230, 220, 270),
        )
        self._reconciliation.setObjectName("rateRiskMaturity19BandReconciliationTable")
        self._tabs.addTab(self._reconciliation, "Conciliación por moneda")
        self._rate_review = self._table(
            (
                "Moneda XML",
                "TipoTasa original",
                "Fecha de vencimiento",
                "Registros",
                "Principal válido en XML",
            ),
            (120, 170, 280, 120, 260),
        )
        self._rate_review.setObjectName("rateRiskMaturity19BandRateReviewTable")
        self._tabs.addTab(self._rate_review, "Revisión tipos de tasa")
        layout.addWidget(self._tabs, 1)

    @staticmethod
    def _table(headers: tuple[str, ...], widths: tuple[int, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.verticalHeader().setVisible(False)
        horizontal = table.horizontalHeader()
        horizontal.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        horizontal.setStretchLastSection(False)
        for col, width in enumerate(widths):
            table.setColumnWidth(col, width)
        return table

    def set_cutoff(self, cutoff: date) -> None:
        if self._cutoff == cutoff:
            return
        self._cutoff = cutoff
        self._bands.setRowCount(0)
        self._excluded.setRowCount(0)
        self._reconciliation.setRowCount(0)
        self._rate_review.setRowCount(0)
        self._status.setText(
            f"Corte {cutoff:%d/%m/%Y} · Ejecutar auditoría. " "No se cargan datos de otro período."
        )

    def run_audit(self) -> None:
        if self._cutoff is None or self._worker is not None:
            return
        cutoff = self._cutoff
        worker = _MaturityAuditWorker(cutoff)
        self._worker = worker
        self._button.setEnabled(False)
        self._status.setText(f"Leyendo captaciones del {cutoff:%d/%m/%Y}…")
        worker.completed.connect(lambda result: self._receive_result(cutoff, result))
        worker.blocked.connect(lambda message: self._receive_error(cutoff, message))
        worker.finished.connect(self._finish_worker)
        worker.start()

    def _receive_result(self, cutoff: date, result: dict[str, object]) -> None:
        if cutoff != self._cutoff:
            return
        self._bands.setRowCount(0)
        self._excluded.setRowCount(0)
        self._reconciliation.setRowCount(0)
        self._rate_review.setRowCount(0)
        bands = result.get("bands", [])
        for row in bands if isinstance(bands, list) else []:
            if not isinstance(row, dict):
                continue
            self._append(
                self._bands,
                (
                    str(row["currency_code"]),
                    f'{row["ordinal"]}. {row["band"]}',
                    str(row["records"]),
                    str(row["source_principal"]),
                ),
                numeric_columns=(2, 3),
            )
        exclusions = result.get("excluded", [])
        for row in exclusions if isinstance(exclusions, list) else []:
            if not isinstance(row, dict):
                continue
            self._append(
                self._excluded,
                (
                    str(row["currency_code"]),
                    self._REASONS.get(str(row["reason"]), str(row["reason"])),
                    str(row["records"]),
                    str(row["source_principal"]),
                ),
                numeric_columns=(2, 3),
                raw_details=str(row["reason"]),
            )
        reconciliations = result.get("currency_reconciliation", [])
        for entry in reconciliations if isinstance(reconciliations, list) else []:
            if not isinstance(entry, dict):
                continue
            self._append(
                self._reconciliation,
                (
                    str(entry["currency_code"]),
                    str(entry["source_valid_principal"]),
                    str(entry["assigned_principal"]),
                    str(entry["excluded_valid_principal"]),
                    str(entry["invalid_principal_records"]),
                    (
                        "Principal válido conciliado"
                        if entry["status"] == "RECONCILED_VALID_PRINCIPAL"
                        else str(entry["status"])
                    ),
                ),
                numeric_columns=(1, 2, 3, 4),
                raw_details=str(entry["status"]),
            )
        reviews = result.get("term_rate_review", [])
        for row in reviews if isinstance(reviews, list) else []:
            if not isinstance(row, dict):
                continue
            date_quality = {
                "MISSING_MATURITY": "Sin fecha",
                "INVALID_MATURITY": "Fecha inválida",
                "PAST_MATURITY": "Anterior al corte",
                "CURRENT_OR_FUTURE_MATURITY": "Igual o posterior al corte",
            }.get(str(row["maturity_quality"]), str(row["maturity_quality"]))
            self._append(
                self._rate_review,
                (
                    str(row["currency_code"]),
                    str(row["rate_type_source_code"]),
                    date_quality,
                    str(row["records"]),
                    str(row["valid_source_principal"]),
                ),
                numeric_columns=(3, 4),
            )
        self._status.setText(
            f"Evidencia XML {cutoff:%d/%m/%Y} · {result['source_records']} registros: "
            f"{result['observed_records']} con vencimiento clasificable y "
            f"{result['excluded_records']} excluidos · NO certificado RTILB."
        )

    def _receive_error(self, cutoff: date, message: str) -> None:
        if cutoff != self._cutoff:
            return
        self._bands.setRowCount(0)
        self._excluded.setRowCount(0)
        self._reconciliation.setRowCount(0)
        self._rate_review.setRowCount(0)
        self._status.setText(f"XML {cutoff:%d/%m/%Y}: {message}. Sin datos reutilizados.")

    def _finish_worker(self) -> None:
        worker = self._worker
        if worker is not None and worker.isFinished():
            self._worker = None
            worker.deleteLater()
            self._button.setEnabled(True)

    @staticmethod
    def _formatted_number(value: str) -> str:
        try:
            amount = Decimal(value)
        except (InvalidOperation, ValueError):
            return value
        if not amount.is_finite():
            return value
        formatted = format(amount, ",f")
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @classmethod
    def _append(
        cls,
        table: QTableWidget,
        values: tuple[str, ...],
        *,
        numeric_columns: tuple[int, ...] = (),
        raw_details: str = "",
    ) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for index, value in enumerate(values):
            display = cls._formatted_number(value) if index in numeric_columns else value
            item = QTableWidgetItem(display)
            item.setToolTip(
                f"Valor XML: {value}"
                + (f"\\nCódigo original: {raw_details}" if raw_details else "")
            )
            if index in numeric_columns:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, index, item)
