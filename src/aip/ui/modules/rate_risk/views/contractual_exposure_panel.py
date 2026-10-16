"""On-demand institutional XML exposure evidence, never an IRRBB calculation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import ParseError

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.product.configured.configuration.institutional_paths import (
    expand_environment_path,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
from aip.product.configured.irrbb.xml_contractual_exposure_audit_cli import audit
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


class _ExposureAuditWorker(QThread):
    """Stream XML off the UI thread; avoid loading confidential rows in widgets."""

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
                self.blocked.emit("Fuente XML CONFÍA no configurada.")
                return
            results = audit(XMLConfiaMonthlySourceReader(root), self._cutoff)
        except (OSError, ValueError, KeyError, ParseError) as exc:
            # Never display source paths, personal identifiers or exception messages.
            self.blocked.emit(f"Diagnóstico bloqueado ({type(exc).__name__}).")
            return
        self.completed.emit(results)


class ContractualExposurePanel(QWidget):
    """Read-only inspection of source principal by currency and product codes."""

    _HEADERS = (
        "Fuente",
        "Moneda XML",
        "Códigos / categoría",
        "Registros",
        "Saldo principal",
        "Sin fecha ppal.",
        "Saldo ppal. afectado",
        "Sin fecha interés",
        "Saldo ppal. afectado (int.)",
    )
    _FULL_HEADERS = (
        "Fuente institucional de origen",
        "Código de moneda tal como aparece en el XML; no es una traducción ISO",
        "Códigos de clasificación XML, sin interpretar catálogos regulatorios",
        "Número de registros en este grupo",
        "Saldo principal informado en la moneda original, sin conversión",
        "Número de registros sin fecha de próximo pago de principal",
        "Saldo principal de registros sin fecha de próximo pago de principal",
        "Número de registros sin fecha de próximo pago de intereses",
        "Saldo principal de registros sin fecha de próximo pago de intereses; NO intereses devengados",
    )
    _COLUMN_WIDTHS = (105, 110, 330, 100, 220, 140, 220, 145, 245)
    _FIELD_LABELS = {
        "TipoOperacion": "Operación",
        "TipoEstadoOperacionCrediticia": "Estado",
        "TipoCuotaPrincipal": "Cuota",
        "TipoOperacionObligaciones": "Obligación",
        "TipoCuenta": "Cuenta",
        "TipoTasa": "Tasa",
    }

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("rateRiskContractualExposurePanel")
        self._cutoff: date | None = None
        self._worker: _ExposureAuditWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        header = QHBoxLayout()
        self._status = QLabel("Corte contractual pendiente.")
        self._status.setObjectName("rateRiskContractualExposureStatus")
        self._status.setWordWrap(True)
        header.addWidget(self._status, 1)
        self._run_button = QPushButton("Auditar XML del corte")
        self._run_button.setObjectName("rateRiskContractualExposureRun")
        self._run_button.clicked.connect(self.run_audit)
        header.addWidget(self._run_button)
        layout.addLayout(header)

        note = QLabel(
            "Evidencia agregada y de solo lectura. Los saldos se mantienen en "
            "la moneda indicada por el XML, sin tipo de cambio ni sumas entre "
            "monedas. Las fechas faltantes no se sustituyen por vencimientos "
            "supuestos. No son flujos, GAP de 19 bandas, ΔNII ni ΔVEP."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self._table = QTableWidget(0, len(self._HEADERS))
        self._table.setObjectName("rateRiskContractualExposureTable")
        self._table.setHorizontalHeaderLabels(self._HEADERS)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setWordWrap(False)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(30)
        horizontal = self._table.horizontalHeader()
        horizontal.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        horizontal.setStretchLastSection(False)
        horizontal.setMinimumSectionSize(90)
        for index, (width, description) in enumerate(
            zip(self._COLUMN_WIDTHS, self._FULL_HEADERS)
        ):
            self._table.setColumnWidth(index, width)
            header_item = self._table.horizontalHeaderItem(index)
            if header_item is not None:
                header_item.setToolTip(description)

        self._filter_input = QLineEdit()
        self._filter_input.setObjectName("rateRiskContractualExposureFilter")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.setPlaceholderText(
            "Filtrar por fuente, código de moneda o clasificación XML…"
        )
        self._filter_input.setToolTip(
            "Filtra grupos ya auditados. No cambia saldos, cálculos ni datos XML."
        )
        self._filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_input)
        layout.addWidget(self._table, 1)

    def set_cutoff(self, cutoff: date) -> None:
        if self._cutoff == cutoff:
            return
        self._cutoff = cutoff
        self._table.setRowCount(0)
        self._filter_input.clear()
        if self._worker is None:
            self._status.setText(
                f"Corte AIP {cutoff:%d/%m/%Y}. Seleccione Auditar XML del corte. "
                "No se carga un mes anterior de forma silenciosa."
            )
        else:
            self._status.setText(
                f"Corte AIP cambiado a {cutoff:%d/%m/%Y}. "
                "Se descartará el resultado del corte anterior."
            )

    def run_audit(self) -> None:
        if self._cutoff is None or self._worker is not None:
            return
        worker = _ExposureAuditWorker(self._cutoff)
        requested_cutoff = self._cutoff
        self._worker = worker
        self._run_button.setEnabled(False)
        self._status.setText(f"Leyendo XML reales del corte {requested_cutoff:%d/%m/%Y}…")
        worker.completed.connect(lambda result: self._receive_result(requested_cutoff, result))
        worker.blocked.connect(lambda message: self._receive_error(requested_cutoff, message))
        worker.finished.connect(self._finish_worker)
        worker.start()

    def _receive_result(self, cutoff: date, results: list[dict[str, object]]) -> None:
        if cutoff != self._cutoff:
            return
        self._populate(results)
        records = sum(int(str(result["records"])) for result in results)
        self._status.setText(
            f"Auditoría XML completada · Corte {cutoff:%d/%m/%Y} · "
            f"{records:,} registros · sin cálculo VEP/ΔNII ni certificación 19 bandas."
        )

    def _receive_error(self, cutoff: date, message: str) -> None:
        if cutoff == self._cutoff:
            self._table.setRowCount(0)
            self._status.setText(
                f"XML {cutoff:%d/%m/%Y}: {message} "
                "Revise ruta y disponibilidad del mes; no se reutilizan datos antiguos."
            )

    def _finish_worker(self) -> None:
        worker = self._worker
        if worker is not None and worker.isFinished():
            self._worker = None
            worker.deleteLater()
            self._run_button.setEnabled(True)

    @staticmethod
    def _grouped_number(raw: object) -> str:
        """Costa Rican numeric display, preserving XML amount scale and precision."""
        value = str(raw)
        try:
            amount = Decimal(value)
        except (InvalidOperation, ValueError):
            return value
        if not amount.is_finite():
            return value
        formatted = format(amount, ",f")
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @classmethod
    def _short_codes(cls, codes: dict[str, object]) -> str:
        return " · ".join(
            f"{cls._FIELD_LABELS.get(key, key)}={value}" for key, value in codes.items()
        )

    def _apply_filter(self, _text: str) -> None:
        needle = self._filter_input.text().casefold().strip()
        for row in range(self._table.rowCount()):
            haystack = " ".join(
                self._table.item(row, column).toolTip()
                + " "
                + self._table.item(row, column).text()
                for column in (0, 1, 2)
                if self._table.item(row, column) is not None
            ).casefold()
            self._table.setRowHidden(row, needle not in haystack)

    def _populate(self, results: list[dict[str, object]]) -> None:
        self._table.setRowCount(0)
        for source in results:
            groups = source.get("groups", [])
            if not isinstance(groups, list):
                continue
            for group in groups:
                if not isinstance(group, dict):
                    continue
                gaps = group.get("missing_by_field", {})
                if not isinstance(gaps, dict):
                    gaps = {}
                principal_field = "FechaProximoPagoPrincipal"
                interest_field = (
                    "FechaProximoPagoIntereses"
                    if source.get("source") == "CREDIT"
                    else "FechaProximoPagoInteres"
                )
                p = gaps.get(principal_field, {})
                i = gaps.get(interest_field, {})
                if not isinstance(p, dict):
                    p = {}
                if not isinstance(i, dict):
                    i = {}
                category = group.get("category_codes", {})
                if not isinstance(category, dict):
                    category = {}
                codes = self._short_codes(category)
                raw_codes = " | ".join(f"{key}={value}" for key, value in category.items())
                source_key = str(source.get("source", ""))
                sources = {
                    "CREDIT": "Cartera",
                    "BORROWING": "Obligaciones",
                    "CAPTACIONES": "Captaciones",
                }
                raw_values = (
                    source_key,
                    str(group.get("currency_code", "")),
                    raw_codes,
                    str(group.get("records", "")),
                    str(group.get("principal_balance", "")),
                    str(p.get("records", "N/A")),
                    str(p.get("principal_balance", "N/A")),
                    str(i.get("records", "N/A")),
                    str(i.get("principal_balance", "N/A")),
                )
                display_values = (
                    sources.get(source_key, source_key),
                    raw_values[1],
                    codes,
                    self._grouped_number(raw_values[3]),
                    self._grouped_number(raw_values[4]),
                    self._grouped_number(raw_values[5]),
                    self._grouped_number(raw_values[6]),
                    self._grouped_number(raw_values[7]),
                    self._grouped_number(raw_values[8]),
                )
                row = self._table.rowCount()
                self._table.insertRow(row)
                for column, value in enumerate(display_values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(
                        f"{self._FULL_HEADERS[column]}\\n"
                        f"Valor original: {raw_values[column]}"
                    )
                    if column >= 3:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                    self._table.setItem(row, column, item)
        self._apply_filter(self._filter_input.text())
