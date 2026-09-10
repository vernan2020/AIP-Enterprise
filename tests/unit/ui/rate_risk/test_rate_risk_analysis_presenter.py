from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb import (
    IRRBBAnalysisRequest,
    IRRBBAnalysisResult,
    IRRBBAnalysisStatus,
    IRRBBGapCoverageIssue,
    IRRBBGapCoverageIssueCode,
    IRRBBGapCurrencyResult,
    IRRBBGapMatrixCell,
    IRRBBPositionSourceRecord,
    IRRBBSourceLoadResult,
    IRRBBSourceLoadStatus,
    IRRBBSourceSnapshot,
)
from aip.domain.irrbb.data_quality import (
    IRRBBDataIssueCode,
    IRRBBDataQualityIssue,
    IRRBBDataQualitySeverity,
    IRRBBDataQualityStatus,
    IRRBBPositionAssessment,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    DeltaEVEResult,
    EconomicValueResult,
    IRRBBInstrumentClass,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    IRRBBTimeBucket,
    PaymentStructure,
    RateType,
    ScenarioAssessment,
)
from aip.domain.irrbb.scenario_evaluation import IRRBBScenarioEvaluationResult
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapBucketTotal,
    SugefGapReportLine,
    SugefGapRowClassification,
    SugefGapRowClassificationStatus,
)
from aip.shared.money import Currency, Money
from aip.ui.modules.rate_risk.presenters import RateRiskPresenter

CUTOFF = date(2026, 8, 31)


def _methodology() -> IRRBBMethodologyProfile:
    return IRRBBMethodologyProfile(
        code="RTILB-SUGEF",
        version="2026.1",
        status=IRRBBMethodologyStatus.EFFECTIVE,
        source_reference="TEST:METHODOLOGY",
        effective_from=date(2026, 1, 1),
    )


def _request() -> IRRBBAnalysisRequest:
    return IRRBBAnalysisRequest(
        cutoff_date=CUTOFF,
        reporting_currency=Currency.CRC,
        methodology=_methodology(),
        required_scenarios=(IRRBBScenario.PARALLEL_UP,),
    )


def _position(position_id: str, currency: Currency) -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="BOND",
        side=BankingBookSide.ASSET,
        currency=currency,
        principal=Money(Decimal("1000"), currency),
        rate_type=RateType.FIXED,
        maturity_date=date(2028, 8, 31),
        source_reference=f"TEST:{position_id}",
        contractual_rate=Decimal("0.05"),
        payment_frequency_months=6,
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        payment_structure=PaymentStructure.BULLET,
    )


def _ready_assessment(position_id: str) -> IRRBBPositionAssessment:
    return IRRBBPositionAssessment(
        position_id=position_id,
        status=IRRBBDataQualityStatus.READY,
        issues=(),
    )


def _source_load(
    *,
    positions: tuple[BankingBookPosition, ...],
    assessments: tuple[IRRBBPositionAssessment, ...],
    status: IRRBBSourceLoadStatus,
) -> IRRBBSourceLoadResult:
    ready_ids = tuple(
        assessment.position_id
        for assessment in assessments
        if assessment.status is IRRBBDataQualityStatus.READY
    )
    incomplete_ids = tuple(
        assessment.position_id
        for assessment in assessments
        if assessment.status is IRRBBDataQualityStatus.INCOMPLETE
    )
    excluded_ids = tuple(
        assessment.position_id
        for assessment in assessments
        if assessment.status is IRRBBDataQualityStatus.EXCLUDED
    )
    return IRRBBSourceLoadResult(
        snapshot=IRRBBSourceSnapshot(
            cutoff_date=CUTOFF,
            position_records=tuple(
                IRRBBPositionSourceRecord(position=position) for position in positions
            ),
        ),
        assessments=assessments,
        status=status,
        ready_position_ids=ready_ids,
        incomplete_position_ids=incomplete_ids,
        excluded_position_ids=excluded_ids,
    )


def _evaluation() -> IRRBBScenarioEvaluationResult:
    base = EconomicValueResult(
        scenario=IRRBBScenario.BASE,
        reporting_currency=Currency.CRC,
        pv_assets=Money(Decimal("1500"), Currency.CRC),
        pv_liabilities=Money(Decimal("500"), Currency.CRC),
        pv_off_balance_net=Money(Decimal("0"), Currency.CRC),
        eve=Money(Decimal("1000"), Currency.CRC),
        discounted_cashflows=(),
    )
    stressed = EconomicValueResult(
        scenario=IRRBBScenario.PARALLEL_UP,
        reporting_currency=Currency.CRC,
        pv_assets=Money(Decimal("1350"), Currency.CRC),
        pv_liabilities=Money(Decimal("500"), Currency.CRC),
        pv_off_balance_net=Money(Decimal("0"), Currency.CRC),
        eve=Money(Decimal("850"), Currency.CRC),
        discounted_cashflows=(),
    )
    assessment = ScenarioAssessment(
        scenario=IRRBBScenario.PARALLEL_UP,
        eve=stressed.eve,
        delta_eve=Money(Decimal("-150"), Currency.CRC),
        fall_from_base=Money(Decimal("150"), Currency.CRC),
    )
    exposure = DeltaEVEResult(
        reporting_currency=Currency.CRC,
        base_eve=base.eve,
        tier_one_capital=Money(Decimal("2000"), Currency.CRC),
        worst_scenario=IRRBBScenario.PARALLEL_UP,
        worst_loss=Money(Decimal("150"), Currency.CRC),
        exposure_ratio_to_tier1=Decimal("0.075"),
        assessments=(assessment,),
    )
    return IRRBBScenarioEvaluationResult(
        methodology=_methodology(),
        valuation_date=CUTOFF,
        reporting_currency=Currency.CRC,
        position_count=2,
        base=base,
        stressed=(stressed,),
        exposure=exposure,
    )


def _gap_result(currency: Currency, amount: str) -> IRRBBGapCurrencyResult:
    money = Money(Decimal(amount), currency)
    return IRRBBGapCurrencyResult(
        currency=currency,
        bucket_totals=(
            SugefGapBucketTotal(
                bucket=IRRBBTimeBucket.MONTH_1_TO_3,
                ordinal=3,
                label="1 a 3 meses",
                amount=money,
            ),
        ),
        matrix_cells=(
            IRRBBGapMatrixCell(
                report_line=SugefGapReportLine.INVESTMENT_FIXED,
                bucket=IRRBBTimeBucket.MONTH_1_TO_3,
                ordinal=3,
                bucket_label="1 a 3 meses",
                amount=money,
            ),
        ),
        included_position_ids=(f"INV-{currency.value}",),
    )


def test_no_data_result_preserves_request_context_and_does_not_invent_kpis() -> None:
    result = IRRBBAnalysisResult(
        status=IRRBBAnalysisStatus.NO_DATA,
        source_load=_source_load(
            positions=(),
            assessments=(),
            status=IRRBBSourceLoadStatus.EMPTY,
        ),
        evaluation=None,
        tier_one_capital=None,
        gap_classifications=(),
        gap_results=(),
        gap_issues=(),
        curve_points=(),
    )

    read_model = RateRiskPresenter.build_from_analysis(request=_request(), result=result)

    assert read_model.analysis_status == IRRBBAnalysisStatus.NO_DATA.value
    assert read_model.methodology.valuation_date == CUTOFF
    assert read_model.methodology.code == "RTILB-SUGEF"
    assert read_model.kpis == ()
    assert read_model.scenario_rows == ()
    assert read_model.gap_bucket_rows == ()
    assert "No hay posiciones RTILB" in read_model.warnings[0]


def test_blocked_result_exposes_quality_issues_but_keeps_financial_values_nd() -> None:
    position = _position("INV-CRC", Currency.CRC)
    assessment = IRRBBPositionAssessment(
        position_id=position.position_id,
        status=IRRBBDataQualityStatus.INCOMPLETE,
        issues=(
            IRRBBDataQualityIssue(
                code=IRRBBDataIssueCode.CONTRACTUAL_RATE_MISSING,
                field_name="contractual_rate",
                message="Required field is unavailable.",
                severity=IRRBBDataQualitySeverity.ERROR,
            ),
        ),
    )
    classification = SugefGapRowClassification(
        position_id=position.position_id,
        status=SugefGapRowClassificationStatus.MAPPED,
        report_line=SugefGapReportLine.INVESTMENT_FIXED,
        reason="Mapped.",
    )
    result = IRRBBAnalysisResult(
        status=IRRBBAnalysisStatus.BLOCKED,
        source_load=_source_load(
            positions=(position,),
            assessments=(assessment,),
            status=IRRBBSourceLoadStatus.BLOCKED,
        ),
        evaluation=None,
        tier_one_capital=None,
        gap_classifications=(classification,),
        gap_results=(),
        gap_issues=(),
        curve_points=(),
    )

    read_model = RateRiskPresenter.build_from_analysis(request=_request(), result=result)

    assert read_model.analysis_status == IRRBBAnalysisStatus.BLOCKED.value
    assert read_model.kpis == ()
    assert read_model.readiness.incomplete_position_count == 1
    assert read_model.readiness.data_issue_count == 1
    assert read_model.data_issue_rows[0].position_id == "INV-CRC"
    assert "bloqueado" in read_model.warnings[0].lower()


def test_calculated_with_gaps_keeps_crc_usd_separate_and_surfaces_gap_issues() -> None:
    positions = (
        _position("INV-CRC", Currency.CRC),
        _position("INV-USD", Currency.USD),
    )
    assessments = tuple(_ready_assessment(item.position_id) for item in positions)
    source_load = _source_load(
        positions=positions,
        assessments=assessments,
        status=IRRBBSourceLoadStatus.READY,
    )
    classifications = tuple(
        SugefGapRowClassification(
            position_id=item.position_id,
            status=SugefGapRowClassificationStatus.MAPPED,
            report_line=SugefGapReportLine.INVESTMENT_FIXED,
            reason="Mapped.",
        )
        for item in positions
    )
    gap_issue = IRRBBGapCoverageIssue(
        position_id="INV-USD",
        code=IRRBBGapCoverageIssueCode.SCHEDULE_MISSING,
        message="No explicit SUGEF GAP schedule.",
    )
    evaluation = _evaluation()
    result = IRRBBAnalysisResult(
        status=IRRBBAnalysisStatus.CALCULATED_WITH_DATA_GAPS,
        source_load=source_load,
        evaluation=evaluation,
        tier_one_capital=evaluation.exposure.tier_one_capital,
        gap_classifications=classifications,
        gap_results=(
            _gap_result(Currency.CRC, "500"),
            _gap_result(Currency.USD, "20"),
        ),
        gap_issues=(gap_issue,),
        curve_points=(),
    )

    read_model = RateRiskPresenter.build_from_analysis(request=_request(), result=result)

    assert read_model.analysis_status == (IRRBBAnalysisStatus.CALCULATED_WITH_DATA_GAPS.value)
    assert {row.currency for row in read_model.gap_bucket_rows} == {"CRC", "USD"}
    assert {row.amount for row in read_model.gap_bucket_rows} == {
        Decimal("500"),
        Decimal("20"),
    }
    assert len(read_model.gap_coverage_issue_rows) == 1
    assert read_model.gap_coverage_issue_rows[0].code == (
        IRRBBGapCoverageIssueCode.SCHEDULE_MISSING.value
    )
    assert any("brechas de datos" in warning for warning in read_model.warnings)


def test_presenter_rejects_result_from_a_different_cutoff() -> None:
    result = IRRBBAnalysisResult(
        status=IRRBBAnalysisStatus.NO_DATA,
        source_load=IRRBBSourceLoadResult(
            snapshot=IRRBBSourceSnapshot(
                cutoff_date=date(2026, 7, 31),
                position_records=(),
            ),
            assessments=(),
            status=IRRBBSourceLoadStatus.EMPTY,
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

    with pytest.raises(ValueError, match="cutoff"):
        RateRiskPresenter.build_from_analysis(request=_request(), result=result)
