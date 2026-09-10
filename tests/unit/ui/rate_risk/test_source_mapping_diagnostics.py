from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QApplication

from aip.application.irrbb import (
    IRRBBAnalysisRequest,
    IRRBBAnalysisResult,
    IRRBBAnalysisStatus,
    IRRBBSourceLoadResult,
    IRRBBSourceLoadStatus,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
    IRRBBSourceSnapshot,
)
from aip.domain.irrbb.models import (
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
)
from aip.shared.money import Currency
from aip.ui.modules.rate_risk.presenters import RateRiskPresenter
from aip.ui.modules.rate_risk.views import RateRiskView

CUTOFF = date(2026, 8, 31)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _request() -> IRRBBAnalysisRequest:
    return IRRBBAnalysisRequest(
        cutoff_date=CUTOFF,
        reporting_currency=Currency.CRC,
        methodology=IRRBBMethodologyProfile(
            code="RTILB-SUGEF",
            version="2026.1",
            status=IRRBBMethodologyStatus.EFFECTIVE,
            source_reference="TEST:METHODOLOGY",
            effective_from=date(2026, 1, 1),
        ),
        required_scenarios=(IRRBBScenario.PARALLEL_UP,),
    )


def _blocked_result() -> IRRBBAnalysisResult:
    failure = IRRBBSourceMappingFailure(
        source_record_id="ROW-42",
        source_reference="SOURCE:BATCH-7:ROW-42",
        code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
        canonical_field="currency",
        message="Canonical currency is unavailable in the source record.",
    )
    return IRRBBAnalysisResult(
        status=IRRBBAnalysisStatus.BLOCKED,
        source_load=IRRBBSourceLoadResult(
            snapshot=IRRBBSourceSnapshot(
                cutoff_date=CUTOFF,
                position_records=(),
                mapping_failures=(failure,),
            ),
            assessments=(),
            status=IRRBBSourceLoadStatus.BLOCKED,
            ready_position_ids=(),
            incomplete_position_ids=(),
            excluded_position_ids=(),
        ),
        evaluation=None,
        tier_one_capital=None,
        gap_classifications=(),
        gap_results=(),
        gap_issues=(),
        curve_points=(),
    )


def test_source_mapping_failure_is_preserved_in_presenter_read_model() -> None:
    read_model = RateRiskPresenter.build_from_analysis(
        request=_request(),
        result=_blocked_result(),
    )

    assert read_model.analysis_status == IRRBBAnalysisStatus.BLOCKED.value
    assert read_model.kpis == ()
    assert read_model.readiness.assessed_position_count == 0
    assert read_model.readiness.data_issue_count == 0
    assert read_model.readiness.source_mapping_failure_count == 1
    assert len(read_model.source_mapping_failure_rows) == 1
    row = read_model.source_mapping_failure_rows[0]
    assert row.source_record_id == "ROW-42"
    assert row.source_reference == "SOURCE:BATCH-7:ROW-42"
    assert row.code == IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD.value
    assert row.canonical_field == "currency"
    assert "Canonical currency" in row.message
    assert any("no pudieron normalizarse" in warning for warning in read_model.warnings)


def test_passive_view_renders_source_mapping_failure_without_financial_values() -> None:
    _app()
    read_model = RateRiskPresenter.build_from_analysis(
        request=_request(),
        result=_blocked_result(),
    )
    view = RateRiskView(read_model)

    assert view._analysis_status_label.text() == "Estado: Bloqueado"
    assert all(label.text() == "N/D" for label in view._kpi_values.values())
    assert view._readiness_labels["source_mapping_failures"].text() == "1"
    assert view._source_mapping_failure_table.rowCount() == 1
    assert view._source_mapping_failure_table.item(0, 0).text() == "ROW-42"
    assert view._source_mapping_failure_table.item(0, 1).text() == "SOURCE:BATCH-7:ROW-42"
    assert view._source_mapping_failure_table.item(0, 2).text() == (
        IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD.value
    )
    assert view._source_mapping_failure_table.item(0, 3).text() == "currency"
    assert "Canonical currency" in view._source_mapping_failure_table.item(0, 4).text()
