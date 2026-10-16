"""On-demand institutional XML exposure evidence, never an IRRBB calculation."""

from __future__ import annotations

from datetime import date
from xml.etree.ElementTree import ParseError

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
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
        "Códigos producto",
        "Registros",
        "Saldo principal fuente",
        "Sin fecha principal",
        "Saldo principal afectado",
        "Sin fecha intereses",
        "Saldo intereses afectado",
    )

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
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, 1)

    def set_cutoff(self, cutoff: date) -> None:
        if self._cutoff == cutoff:
            return
        self._cutoff = cutoff
        self._table.setRowCount(0)
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
                values = (
                    str(source.get("source", "")),
                    str(group.get("currency_code", "")),
                    " · ".join(f"{k}={v}" for k, v in category.items()),
                    str(group.get("records", "")),
                    str(group.get("principal_balance", "")),
                    str(p.get("records", "N/A")),
                    str(p.get("principal_balance", "N/A")),
                    str(i.get("records", "N/A")),
                    str(i.get("principal_balance", "N/A")),
                )
                row = self._table.rowCount()
                self._table.insertRow(row)
                for column, value in enumerate(values):
                    self._table.setItem(row, column, QTableWidgetItem(value))
