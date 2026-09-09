from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.data_quality import (
    IRRBBDataIssueCode,
    IRRBBDataQualityIssue,
    IRRBBDataQualitySeverity,
    IRRBBDataQualityStatus,
    IRRBBPositionAssessment,
)
from aip.domain.irrbb.models import (
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    DeltaEVEResult,
    DiscountedCashFlow,
    EconomicValueResult,
    IRRBBCashFlow,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    IRRBBTimeBucket,
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
from aip.ui.modules.rate_risk.models import (
    RateRiskCurvePointInput,
    RateRiskGapMatrixCellInput,
)
from aip.ui.modules.rate_risk.presenters import RateRiskPresenter

VALUATION_DATE = date(2026, 8, 31)
REPORTING_CURRENCY = Currency.CRC


def _methodology() -> IRRBBMethodologyProfile:
    return IRRBBMethodologyProfile(
        code="RTILB-SUGEF",
        version="2026.1",
        status=IRRBBMethodologyStatus.EFFECTIVE,
        source_reference="TEST:METHODOLOGY",
        effective_from=date(2026, 1, 1),
    )


def _cashflow(scenario: IRRBBScenario) -> DiscountedCashFlow:
    flow = IRRBBCashFlow(
        position_id="INV-1",
        side=BankingBookSide.ASSET,
        direction=CashFlowDirection.RECEIVABLE,
        amount=Money(Decimal("100"), Currency.CRC),
        cashflow_date=date(2027, 8, 31),
        risk_date=date(2027, 8, 31),
        flow_type="PRINCIPAL",
        source_reference=f"TEST:{scenario.value}",
        amount_status=CashFlowAmountStatus.CONTRACTUAL,
    )
    return DiscountedCashFlow(
        cashflow=flow,
        scenario=scenario,
        discount_factor=Decimal("0.95"),
        exchange_rate=Decimal("1"),
        present_value_reporting=Money(Decimal("95"), Currency.CRC),
        signed_eve_contribution=Money(Decimal("95"), Currency.CRC),
    )


def _economic_value(scenario: IRRBBScenario, eve: str) -> EconomicValueResult:
    value = Decimal(eve)
    return EconomicValueResult(
        scenario=scenario,
        reporting_currency=REPORTING_CURRENCY,
        pv_assets=Money(value + Decimal("40"), REPORTING_CURRENCY),
        pv_liabilities=Money(Decimal("40"), REPORTING_CURRENCY),
        pv_off_balance_net=Money(Decimal("0"), REPORTING_CURRENCY),
        eve=Money(value, REPORTING_CURRENCY),
        discounted_cashflows=(_cashflow(scenario),),
    )


def _evaluation() -> IRRBBScenarioEvaluationResult:
    base = _economic_value(IRRBBScenario.BASE, "1000")
    scenario_values = (
        (IRRBBScenario.PARALLEL_UP, "850"),
        (IRRBBScenario.PARALLEL_DOWN, "1100"),
        (IRRBBScenario.STEEPENER, "940"),
        (IRRBBScenario.FLATTENER, "970"),
        (IRRBBScenario.SHORT_UP, "900"),
        (IRRBBScenario.SHORT_DOWN, "1040"),
    )
    stressed = tuple(
        _economic_value(scenario, value) for scenario, value in scenario_values
    )
    assessments = tuple(
        ScenarioAssessment(
            scenario=result.scenario,
            eve=result.eve,
            delta_eve=Money(result.eve.amount - base.eve.amount, REPORTING_CURRENCY),
            fall_from_base=Money(
                max(base.eve.amount - result.eve.amount, Decimal("0")),
                REPORTING_CURRENCY,
            ),
        )
        for result in stressed
    )
    exposure = DeltaEVEResult(
        reporting_currency=REPORTING_CURRENCY,
        base_eve=base.eve,
        tier_one_capital=Money(Decimal("2000"), REPORTING_CURRENCY),
        worst_scenario=IRRBBScenario.PARALLEL_UP,
        worst_loss=Money(Decimal("150"), REPORTING_CURRENCY),
        exposure_ratio_to_tier1=Decimal("0.075"),
        assessments=assessments,
    )
    return IRRBBScenarioEvaluationResult(
        methodology=_methodology(),
        valuation_date=VALUATION_DATE,
        reporting_currency=REPORTING_CURRENCY,
        position_count=3,
        base=base,
        stressed=stressed,
        exposure=exposure,
    )


def test_presenter_builds_base_six_scenarios_kpis_and_flow_drilldown() -> None:
    read_model = RateRiskPresenter.build(evaluation=_evaluation())

    assert len(read_model.scenario_rows) == 7
    assert read_model.scenario_rows[0].scenario == IRRBBScenario.BASE.value
    assert sum(row.is_worst for row in read_model.scenario_rows) == 1
    assert next(row for row in read_model.scenario_rows if row.is_worst).scenario == (
        IRRBBScenario.PARALLEL_UP.value
    )

    kpis = {item.key: item for item in read_model.kpis}
    assert kpis["BASE_EVE"].value == Decimal("1000")
    assert kpis["WORST_EVE_LOSS"].value == Decimal("150")
    assert kpis["EVE_TIER1_RATIO"].value == Decimal("0.075")
    assert kpis["CALCULATED_POSITIONS"].value == Decimal("3")

    assert len(read_model.valuation_flow_rows) == 7
    assert {row.scenario for row in read_model.valuation_flow_rows} == {
        IRRBBScenario.BASE.value,
        IRRBBScenario.PARALLEL_UP.value,
        IRRBBScenario.PARALLEL_DOWN.value,
        IRRBBScenario.STEEPENER.value,
        IRRBBScenario.FLATTENER.value,
        IRRBBScenario.SHORT_UP.value,
        IRRBBScenario.SHORT_DOWN.value,
    }


def test_presenter_preserves_gap_quality_mapping_and_curve_inputs() -> None:
    quality = (
        IRRBBPositionAssessment(
            position_id="INV-1",
            status=IRRBBDataQualityStatus.READY,
            issues=(),
        ),
        IRRBBPositionAssessment(
            position_id="LOAN-1",
            status=IRRBBDataQualityStatus.INCOMPLETE,
            issues=(
                IRRBBDataQualityIssue(
                    code=IRRBBDataIssueCode.NEXT_REPRICING_MISSING,
                    field_name="next_repricing_date",
                    message="Missing next repricing date.",
                    severity=IRRBBDataQualitySeverity.ERROR,
                ),
            ),
        ),
    )
    classifications = (
        SugefGapRowClassification(
            position_id="INV-1",
            status=SugefGapRowClassificationStatus.MAPPED,
            report_line=SugefGapReportLine.INVESTMENT_FIXED,
            reason="Mapped.",
        ),
        SugefGapRowClassification(
            position_id="ACCOUNT-233",
            status=SugefGapRowClassificationStatus.MAPPING_PENDING,
            report_line=None,
            reason="Pending supervisory mapping.",
        ),
    )
    bucket_totals = (
        SugefGapBucketTotal(
            bucket=IRRBBTimeBucket.MONTH_1_TO_3,
            ordinal=3,
            label="1 a 3 meses",
            amount=Money(Decimal("500"), Currency.CRC),
        ),
    )
    matrix_cells = (
        RateRiskGapMatrixCellInput(
            report_line=SugefGapReportLine.INVESTMENT_FIXED,
            bucket=IRRBBTimeBucket.MONTH_1_TO_3,
            ordinal=3,
            bucket_label="1 a 3 meses",
            amount=Money(Decimal("500"), Currency.CRC),
        ),
    )
    curves = (
        RateRiskCurvePointInput(
            curve_id="CRC_BASE",
            as_of_date=VALUATION_DATE,
            currency=Currency.CRC,
            scenario=IRRBBScenario.BASE,
            tenor_years=Decimal("1"),
            rate=Decimal("0.055"),
            source_reference="TEST:CURVE",
        ),
    )

    read_model = RateRiskPresenter.build(
        evaluation=_evaluation(),
        gap_bucket_totals=bucket_totals,
        gap_matrix_cells=matrix_cells,
        quality_assessments=quality,
        gap_classifications=classifications,
        curve_points=curves,
    )

    assert read_model.readiness.assessed_position_count == 2
    assert read_model.readiness.ready_position_count == 1
    assert read_model.readiness.incomplete_position_count == 1
    assert read_model.readiness.data_issue_count == 1
    assert read_model.readiness.mapping_pending_count == 1

    assert read_model.gap_bucket_rows[0].amount == Decimal("500")
    assert read_model.gap_matrix_cells[0].report_line == (
        SugefGapReportLine.INVESTMENT_FIXED.value
    )
    assert read_model.data_issue_rows[0].code == (
        IRRBBDataIssueCode.NEXT_REPRICING_MISSING.value
    )
    assert read_model.mapping_rows[1].status == (
        SugefGapRowClassificationStatus.MAPPING_PENDING.value
    )
    assert read_model.curve_rows[0].rate == Decimal("0.055")
    assert read_model.warnings == ()


def test_presenter_rejects_stress_and_delta_scenario_coverage_mismatch() -> None:
    evaluation = _evaluation()
    malformed_exposure = DeltaEVEResult(
        reporting_currency=evaluation.exposure.reporting_currency,
        base_eve=evaluation.exposure.base_eve,
        tier_one_capital=evaluation.exposure.tier_one_capital,
        worst_scenario=evaluation.exposure.worst_scenario,
        worst_loss=evaluation.exposure.worst_loss,
        exposure_ratio_to_tier1=evaluation.exposure.exposure_ratio_to_tier1,
        assessments=evaluation.exposure.assessments[:-1],
    )
    malformed = IRRBBScenarioEvaluationResult(
        methodology=evaluation.methodology,
        valuation_date=evaluation.valuation_date,
        reporting_currency=evaluation.reporting_currency,
        position_count=evaluation.position_count,
        base=evaluation.base,
        stressed=evaluation.stressed,
        exposure=malformed_exposure,
    )

    with pytest.raises(ValueError, match="identical coverage"):
        RateRiskPresenter.build(evaluation=malformed)
