from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout

from aip.ui.modules.rate_risk.models import RateRiskReadModel
from aip.ui.modules.rate_risk.views.rate_risk_view import RateRiskView as _BaseRateRiskView


class RateRiskView(_BaseRateRiskView):
    """Passive RTILB view extended with source-to-canonical mapping diagnostics."""

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
