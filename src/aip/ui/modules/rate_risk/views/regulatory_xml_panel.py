from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aip.product.configured.irrbb.regulatory_financial_xml import RegulatoryXMLPairResult
from aip.product.configured.irrbb.regulatory_gap_six_band import build_regulatory_gap


class RegulatoryXMLPanel(QWidget):
    """Regulatory source evidence, not a substitute for contractual VEP/NII."""

    _MAX_VISIBLE_ROWS = 200

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("rateRiskRegulatoryXMLPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._headline = QLabel("XML regulatorios: sin leer")
        self._headline.setObjectName("rateRiskRegulatoryXMLStatus")
        self._headline.setStyleSheet("color:#00345F; font-size:13px; font-weight:800;")
        layout.addWidget(self._headline)
        self._period_label = QLabel("Último corte XML: pendiente")
        self._period_label.setObjectName("rateRiskRegulatoryXMLSelectedPeriod")
        self._period_label.setWordWrap(True)
        layout.addWidget(self._period_label)

        note = QLabel(
            "Brechas (catálogo 5) y Calce (catálogo 4): información por cuenta y "
            "banda según archivo SICVECA. Los totales se usan solo para conciliar; "
            "no son flujos contractuales ni resultados ΔNII/ΔVEP. Las cifras "
            "se reportan en colones equivalentes (CRC), sin inferir moneda "
            "contractual de cada posición."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#566D7C; font-size:10px;")
        layout.addWidget(note)

        self._files = self._table(
            (
                "Archivo",
                "Estado",
                "Período",
                "Entidad",
                "Tipo carga",
                "Detalles",
                "Totales",
                "SHA-256 / incidencia",
            )
        )
        self._files.setObjectName("rateRiskRegulatoryXMLFileStatus")
        layout.addWidget(self._files)

        self._gap_title = QLabel("GAP regulatorio · 6 bandas SICVECA (CRC)")
        self._gap_title.setStyleSheet("color:#00345F; font-weight:800;")
        layout.addWidget(self._gap_title)
        self._gap_notice = QLabel("GAP regulatorio no calculado")
        self._gap_notice.setWordWrap(True)
        layout.addWidget(self._gap_notice)
        self._gap_table = self._table(
            (
                "Banda",
                "Activos sensibles CRC",
                "Pasivos sensibles CRC",
                "GAP simple CRC",
                "GAP acumulado CRC",
            )
        )
        self._gap_table.setObjectName("rateRiskRegulatorySixBandGap")
        layout.addWidget(self._gap_table)

        self._snapshot: RegulatoryXMLPairResult | None = None
        self._account_selector = QComboBox()
        self._account_selector.setObjectName("rateRiskRegulatoryXMLAccountSelector")
        self._account_selector.setToolTip(
            "Filtre una cuenta regulatoria para no sumar categorías jerárquicas."
        )
        self._account_selector.currentIndexChanged.connect(self._populate_rows)
        layout.addWidget(self._account_selector)

        self._detail_note = QLabel("Detalle XML: pendiente de validación")
        self._detail_note.setStyleSheet("color:#566D7C; font-weight:700;")
        layout.addWidget(self._detail_note)
        self._rows = self._table(("Fuente", "Cuenta SUGEF", "Catálogo", "Banda", "Monto (CRC)"))
        self._rows.setObjectName("rateRiskRegulatoryXMLRows")
        layout.addWidget(self._rows, 1)

    @staticmethod
    def _table(headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _cell(table: QTableWidget, row: int, column: int, value: object) -> None:
        table.setItem(row, column, QTableWidgetItem(str(value)))

    def set_unconfigured(self) -> None:
        self._snapshot = None
        self._headline.setText("XML Brechas y Calce: fuente no configurada")
        self._period_label.setText("Último corte XML: no disponible")
        self._files.setRowCount(0)
        self._rows.setRowCount(0)
        self._account_selector.clear()
        self._gap_table.setRowCount(0)
        self._gap_notice.setText("No disponible: fuente XML no configurada.")
        self._detail_note.setText(
            "Revise la fuente XML CONFÍA ya documentada en AIP. "
            "No hay datos regulatorios cargados; no se asumen valores cero."
        )

    def set_snapshot(
        self,
        snapshot: RegulatoryXMLPairResult,
        *,
        valuation_cutoff: date | None = None,
    ) -> None:
        if not snapshot.source_month_found:
            self._period_label.setText(
                "No se encontró un mes con XML Brechas / Calce en la ruta configurada."
            )
        report_month = snapshot.cutoff_date.strftime("%m/%Y")
        target = valuation_cutoff or snapshot.cutoff_date
        target_month = target.strftime("%m/%Y")
        matches_cutoff = (snapshot.cutoff_date.year, snapshot.cutoff_date.month) == (
            target.year,
            target.month,
        )
        message = (
            f"Último mes con XML: {report_month}. Corte AIP: {target_month}."
            if matches_cutoff
            else f"Último mes con XML: {report_month}. Corte AIP: {target_month}. "
            "DESFASE: datos regulatorios de otro corte; no usar para el cálculo "
            "RTILB del corte AIP."
        )
        if snapshot.source_month_found:
            self._period_label.setText(message)
        self._files.setRowCount(len(snapshot.files))
        for index, item in enumerate(snapshot.files):
            issue = "; ".join(item.issues) if item.issues else item.source_sha256 or ""
            values = (
                item.filename,
                item.status,
                item.period.isoformat() if item.period else "—",
                item.entity_id or "—",
                item.load_type or "—",
                str(len(item.rows)) if item.is_valid else "—",
                str(len(item.account_totals)) if item.is_valid else "—",
                issue,
            )
            for column, value in enumerate(values):
                self._cell(self._files, index, column, value)

        self._headline.setText(
            "XML regulatorios conciliados"
            if snapshot.is_valid
            else "XML regulatorios pendientes o bloqueados"
        )
        self._snapshot = snapshot
        gap = build_regulatory_gap(snapshot)
        self._gap_table.setRowCount(len(gap.rows))
        for index, row in enumerate(gap.rows):
            for column, value in enumerate(
                (
                    row.bucket_label,
                    str(row.assets_crc),
                    str(row.liabilities_crc),
                    str(row.gap_crc),
                    str(row.cumulative_gap_crc),
                )
            ):
                self._cell(self._gap_table, index, column, value)
        self._gap_notice.setText(
            "Conciliado: 22310 = 22110 + 22210; 22320 = 22120 + 22220; "
            "22300 = 22310 - 22320. No es delta NII ni delta VEP."
            if gap.is_ready
            else "No disponible: " + " ".join(gap.issues[:4])
        )
        self._account_selector.blockSignals(True)
        self._account_selector.clear()
        self._account_selector.addItem("Todas las cuentas (sin consolidar)", None)
        for item in snapshot.files:
            if not item.is_valid:
                continue
            accounts = sorted({row.account_code for row in item.rows}, key=int)
            for account in accounts:
                self._account_selector.addItem(
                    f"{item.key} · cuenta {account}", (item.key, account)
                )
        self._account_selector.blockSignals(False)
        self._populate_rows()

    def _populate_rows(self, _index: int = -1) -> None:
        snapshot = self._snapshot
        if snapshot is None:
            return
        selected = self._account_selector.currentData()
        visible = [
            (item.key, row)
            for item in snapshot.files
            if item.is_valid
            for row in item.rows
            if selected is None or selected == (item.key, row.account_code)
        ][: self._MAX_VISIBLE_ROWS]
        self._rows.setRowCount(len(visible))
        for index, (source, row) in enumerate(visible):
            for column, value in enumerate(
                (source, row.account_code, row.catalog_code, row.bucket_code, str(row.amount))
            ):
                self._cell(self._rows, index, column, value)

        available = sum(
            1
            for item in snapshot.files
            if item.is_valid
            for row in item.rows
            if selected is None or selected == (item.key, row.account_code)
        )
        label = (
            f"Cuenta seleccionada: {selected[0]} / {selected[1]}."
            if selected is not None
            else "Sin consolidación entre cuentas jerárquicas."
        )
        self._detail_note.setText(
            f"Detalle: {available} filas; se muestran hasta {self._MAX_VISIBLE_ROWS}. "
            f"{label} Los registros totales no se duplican."
        )
