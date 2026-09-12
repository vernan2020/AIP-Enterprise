from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QApplication

from aip.ui.modules.rate_risk.models import (
    RateRiskDataIssueRow,
    RateRiskGapCoverageIssueRow,
    RateRiskMethodologyMetadata,
    RateRiskPositionQualityRow,
    RateRiskReadinessSummary,
    RateRiskReadModel,
)
from aip.ui.modules.rate_risk.views import RateRiskView


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _blocked_read_model() -> RateRiskReadModel:
    return RateRiskReadModel(
        methodology=RateRiskMethodologyMetadata(
            code="RTILB-SUGEF",
            version="2026.1",
            status="EFFECTIVE",
            source_reference="TEST:METHODOLOGY",
            effective_from=date(2026, 1, 1),
            valuation_date=date(2026, 8, 31),
            reporting_currency="CRC",
            calculated_position_count=0,
        ),
        readiness=RateRiskReadinessSummary(
            calculated_position_count=0,
            assessed_position_count=1,
            ready_position_count=0,
            incomplete_position_count=1,
            excluded_position_count=0,
            data_issue_count=1,
            mapping_pending_count=0,
            incomplete_mapping_count=0,
        ),
        kpis=(),
        scenario_rows=(),
        gap_bucket_rows=(),
        gap_matrix_cells=(),
        valuation_flow_rows=(),
        position_quality_rows=(
            RateRiskPositionQualityRow(
                position_id="INV-1",
                status="INCOMPLETE",
                issue_count=1,
                error_count=1,
                warning_count=0,
                info_count=0,
            ),
        ),
        data_issue_rows=(
            RateRiskDataIssueRow(
                position_id="INV-1",
                status="INCOMPLETE",
                code="CONTRACTUAL_RATE_MISSING",
                field_name="contractual_rate",
                severity="ERROR",
                message="Required field is unavailable.",
            ),
        ),
        mapping_rows=(),
        curve_rows=(),
        warnings=("Cálculo RTILB bloqueado.",),
        analysis_status="BLOCKED",
        gap_coverage_issue_rows=(
            RateRiskGapCoverageIssueRow(
                position_id="INV-1",
                code="SCHEDULE_MISSING",
                message="No explicit SUGEF GAP schedule.",
            ),
        ),
    )


def test_rate_risk_view_opens_safely_without_configured_source() -> None:
    _app()
    view = RateRiskView()

    assert view.objectName() == "rateRiskWorkspace"
    assert view._tabs.count() == 6
    assert view._tabs.tabText(0) == "Resumen RTILB"
    assert view._tabs.tabText(2) == "GAP SUGEF · 19 bandas"
    assert view._analysis_status_label.text() == "Estado: Sin cálculo"
    assert view._warning_label.isVisibleTo(view) is False or "Sin cálculo RTILB" in (
        view._warning_label.text()
    )
    assert all(label.text() == "N/D" for label in view._kpi_values.values())


def test_rate_risk_view_exposes_expected_audit_tabs() -> None:
    _app()
    view = RateRiskView()

    labels = [view._tabs.tabText(index) for index in range(view._tabs.count())]
    assert labels == [
        "Resumen RTILB",
        "Escenarios VEP",
        "GAP SUGEF · 19 bandas",
        "Curvas",
        "Drill-down",
        "Calidad de Datos",
    ]


def test_blocked_analysis_is_rendered_as_nd_with_quality_and_gap_coverage() -> None:
    _app()
    view = RateRiskView(_blocked_read_model())

    assert view._analysis_status_label.text() == "Estado: Bloqueado"
    assert view._cutoff_label.text() == "Corte: 31/08/2026"
    assert all(label.text() == "N/D" for label in view._kpi_values.values())
    assert view._readiness_labels["incomplete"].text() == "1"
    assert view._quality_table.rowCount() == 1
    assert view._issues_table.rowCount() == 1
    assert view._gap_coverage_table.rowCount() == 1
    assert view._gap_coverage_table.item(0, 0).text() == "INV-1"
    assert view._gap_coverage_table.item(0, 1).text() == "SCHEDULE_MISSING"
    assert "No explicit SUGEF GAP schedule" in view._gap_coverage_table.item(0, 2).text()
