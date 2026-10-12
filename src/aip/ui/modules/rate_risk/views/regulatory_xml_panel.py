from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from aip.product.configured.irrbb.regulatory_financial_xml import RegulatoryXMLPairResult


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
                "Detalles",
                "Totales",
                "SHA-256 / incidencia",
            )
        )
        self._files.setObjectName("rateRiskRegulatoryXMLFileStatus")
        layout.addWidget(self._files)

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

    def set_snapshot(self, snapshot: RegulatoryXMLPairResult) -> None:
        self._files.setRowCount(len(snapshot.files))
        for index, item in enumerate(snapshot.files):
            issue = "; ".join(item.issues) if item.issues else item.source_sha256 or ""
            values = (
                item.filename,
                item.status,
                item.period.isoformat() if item.period else "—",
                item.entity_id or "—",
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
