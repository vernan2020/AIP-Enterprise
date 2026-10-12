from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

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
            "se mantienen en la unidad de reporte del XML, sin inferir moneda "
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

        self._detail_note = QLabel("Detalle XML: pendiente de validación")
        self._detail_note.setStyleSheet("color:#566D7C; font-weight:700;")
        layout.addWidget(self._detail_note)
        self._rows = self._table(("Fuente", "Cuenta SUGEF", "Catálogo", "Banda", "Monto reportado"))
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
        visible = [
            (item.key, row) for item in snapshot.files if item.is_valid for row in item.rows
        ][: self._MAX_VISIBLE_ROWS]
        self._rows.setRowCount(len(visible))
        for index, (source, row) in enumerate(visible):
            for column, value in enumerate(
                (source, row.account_code, row.catalog_code, row.bucket_code, str(row.amount))
            ):
                self._cell(self._rows, index, column, value)

        available = sum(len(item.rows) for item in snapshot.files if item.is_valid)
        self._detail_note.setText(
            f"Detalle de archivos válidos: {available} filas; "
            f"se muestran hasta {self._MAX_VISIBLE_ROWS}. "
            "No incorpora totales como registros adicionales."
        )
