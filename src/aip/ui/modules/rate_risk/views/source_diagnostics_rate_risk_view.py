from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout

from aip.product.configured.irrbb.source_integration_progress import (
    INSTITUTIONAL_IRRBB_SOURCE_PROGRESS,
)
from aip.ui.modules.rate_risk.models import RateRiskReadModel
from aip.ui.modules.rate_risk.views.rate_risk_view import RateRiskView as _BaseRateRiskView


class RateRiskView(_BaseRateRiskView):
    """Passive RTILB view extended with source-integration diagnostics."""

    def _build_summary_page(self) -> None:
        super()._build_summary_page()
        readiness_box = next(
            box
            for box in self._summary_page.findChildren(QGroupBox)
            if box.title() == "Preparación del cálculo"
        )
        readiness_layout = cast(QGridLayout, readiness_box.layout())
        caption = QLabel("Fallos normalización")
        caption.setStyleSheet("color:#566D7C; font-size:9px;")
        value = QLabel("-")
        value.setStyleSheet("color:#00345F; font-weight:800; font-size:13px;")
        self._readiness_labels["source_mapping_failures"] = value
        readiness_layout.addWidget(caption, 2, 0)
        readiness_layout.addWidget(value, 2, 1)

    def _build_quality_page(self) -> None:
        super()._build_quality_page()
        layout = cast(QVBoxLayout, self._quality_page.layout())

        source_status_box = QGroupBox("Estado de integración de fuentes")
        source_status_box.setStyleSheet(self._group_style())
        source_status_layout = QVBoxLayout(source_status_box)
        source_status_note = QLabel(
            "Cobertura real por segmento: distingue fuente primaria, complemento contractual, "
            "normalización, asignación a 19 bandas, componente GAP y preparación VEP. "
            "PARCIAL o BLOQUEADO nunca se interpreta como cero ni como cálculo productivo."
        )
        source_status_note.setWordWrap(True)
        source_status_note.setStyleSheet("color:#566D7C; font-size:9px;")
        source_status_layout.addWidget(source_status_note)
        self._source_integration_table = self._table()
        self._source_integration_table.setObjectName("rateRiskSourceIntegrationStatus")
        self._source_integration_table.setColumnCount(9)
        self._source_integration_table.setHorizontalHeaderLabels(
            [
                "Fuente primaria",
                "Segmento",
                "Tecnología",
                "Complemento",
                "Normalización",
                "19 bandas",
                "GAP",
                "VEP",
                "Gate pendiente",
            ]
        )
        source_status_layout.addWidget(self._source_integration_table)
        layout.insertWidget(0, source_status_box)
        self._populate_source_integration_status()

        source_mapping_box = QGroupBox("Normalización fuente → RTILB")
        source_mapping_box.setStyleSheet(self._group_style())
        source_mapping_layout = QVBoxLayout(source_mapping_box)
        self._source_mapping_failure_table = self._table()
        self._source_mapping_failure_table.setObjectName("rateRiskSourceMappingFailures")
        self._source_mapping_failure_table.setColumnCount(5)
        self._source_mapping_failure_table.setHorizontalHeaderLabels(
            ["Registro fuente", "Fuente", "Código", "Campo RTILB", "Detalle"]
        )
        source_mapping_layout.addWidget(self._source_mapping_failure_table)
        layout.addWidget(source_mapping_box)

    def set_read_model(self, read_model: RateRiskReadModel | None) -> None:
        super().set_read_model(read_model)
        if read_model is None:
            return
        self._readiness_labels["source_mapping_failures"].setText(
            str(read_model.readiness.source_mapping_failure_count)
        )

    def _clear_tables(self) -> None:
        super()._clear_tables()
        self._source_mapping_failure_table.setRowCount(0)

    def _populate_source_integration_status(self) -> None:
        rows = INSTITUTIONAL_IRRBB_SOURCE_PROGRESS
        self._source_integration_table.setRowCount(len(rows))
        for row_index, progress in enumerate(rows):
            self._set_row(
                self._source_integration_table,
                row_index,
                (
                    progress.primary_source,
                    progress.segment.value,
                    progress.technology,
                    progress.contractual_complement,
                    progress.normalization_status,
                    progress.bucket_status,
                    progress.gap_status,
                    progress.eve_status,
                    progress.pending_gate,
                ),
            )

    def _populate_quality(self, read_model: RateRiskReadModel) -> None:
        super()._populate_quality(read_model)
        rows = read_model.source_mapping_failure_rows
        self._source_mapping_failure_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self._set_row(
                self._source_mapping_failure_table,
                row_index,
                (
                    row.source_record_id,
                    row.source_reference,
                    row.code,
                    row.canonical_field or "",
                    row.message,
                ),
            )
