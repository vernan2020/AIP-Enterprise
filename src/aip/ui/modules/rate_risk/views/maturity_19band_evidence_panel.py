"""Passive 19-band observed-maturity evidence; never a certified RTILB GAP."""

from __future__ import annotations

from datetime import date
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
        horizontal.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
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
            )
        exclusions = result.get("excluded", [])
        for row in exclusions if isinstance(exclusions, list) else []:
            if not isinstance(row, dict):
                continue
            self._append(
                self._excluded,
                (
                    str(row["currency_code"]),
                    str(row["reason"]),
                    str(row["records"]),
                    str(row["source_principal"]),
                ),
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
        self._status.setText(f"XML {cutoff:%d/%m/%Y}: {message}. Sin datos reutilizados.")

    def _finish_worker(self) -> None:
        worker = self._worker
        if worker is not None and worker.isFinished():
            self._worker = None
            worker.deleteLater()
            self._button.setEnabled(True)

    @staticmethod
    def _append(table: QTableWidget, values: tuple[str, ...]) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for index, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            if index >= 2:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, index, item)
