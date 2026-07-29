from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from aip.domain.analytics.enums.score_direction import ScoreDirection
from aip.domain.analytics.exceptions import InvalidWeightError
from aip.domain.analytics.scoring.score_band import ScoreBand
from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.issuers.credit_rating import CreditRating
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule
from aip.domain.relative_value.calculators.benchmark_spread import BenchmarkSpreadCalculator
from aip.domain.relative_value.calculators.interpolated_curve_spread import (
    InterpolatedCurveSpreadCalculator,
)
from aip.domain.relative_value.calculators.nominal_spread import NominalSpreadCalculator
from aip.domain.relative_value.calculators.z_spread import ZSpreadCalculator
from aip.domain.relative_value.engine.recommendation_engine import RecommendationEngine
from aip.domain.relative_value.engine.relative_value_engine import RelativeValueEngine
from aip.domain.relative_value.engine.spread_engine import SpreadEngine
from aip.domain.relative_value.enums.confidence_level import ConfidenceLevel
from aip.domain.relative_value.enums.recommendation_type import RecommendationType
from aip.domain.relative_value.enums.valuation_status import ValuationStatus
from aip.domain.relative_value.exceptions import (
    BenchmarkNotAvailableError,
    CurveNotAvailableError,
    RecommendationError,
    RelativeValueError,
    SpreadCalculationError,
    UnsupportedSpreadTypeError,
)
from aip.domain.relative_value.explainability.decision_matrix import DecisionMatrix
from aip.domain.relative_value.explainability.recommendation_explanation import (
    RecommendationExplanation,
)
from aip.domain.relative_value.models.investment_opportunity import InvestmentOpportunity
from aip.domain.relative_value.models.recommendation import Recommendation
from aip.domain.relative_value.models.relative_value_request import RelativeValueRequest
from aip.domain.relative_value.models.relative_value_result import RelativeValueResult
from aip.domain.relative_value.ranking.investment_ranking import InvestmentRanking
from aip.domain.relative_value.scoring.confidence_score import ConfidenceScore
from aip.domain.relative_value.scoring.relative_value_score import RelativeValueScore
from aip.domain.relative_value.scoring.rich_cheap_score import RichCheapScore


def _build_instrument() -> GovernmentBond:
    issuer = Issuer(
        code="CRGOV",
        name="Costa Rica Government",
        issuer_type=IssuerType.GOVERNMENT,
        credit_rating=CreditRating("BBB", "S&P"),
    )
    return GovernmentBond(
        isin="CR1234567890",
        name="Costa Rica 10Y Bond",
        issuer=issuer,
        currency="CRC",
        settlement_calendar="CR",
        business_day_convention="Following",
        day_count_convention="ACTUAL_365",
        issue_date=date(2020, 1, 1),
        settlement_date=date(2024, 1, 1),
        maturity_date=date(2030, 1, 1),
        coupon_schedule=CouponSchedule(),
        nominal_value=Decimal("1000000"),
        book_value=Decimal("1000000"),
        market_value=Decimal("1000000"),
        face_value=Decimal("1000000"),
        outstanding_amount=Decimal("1000000"),
        yield_rate=Decimal("0.045"),
        duration=Decimal("6.0"),
        modified_duration=Decimal("5.8"),
        convexity=Decimal("42.0"),
        dirty_price=Decimal("100.0"),
        clean_price=Decimal("100.0"),
        accrued_interest=Decimal("0.0"),
        coupon_rate=Decimal("0.05"),
        payment_frequency=PaymentFrequency.SEMIANNUAL,
    )


def _build_curve() -> YieldCurve:
    return YieldCurve(
        valuation_date=date(2024, 1, 1),
        currency="CRC",
        points=(
            CurvePoint(Decimal("1"), Decimal("0.03")),
            CurvePoint(Decimal("5"), Decimal("0.04")),
            CurvePoint(Decimal("10"), Decimal("0.05")),
        ),
    )


def test_nominal_spread() -> None:
    calculator = NominalSpreadCalculator()
    result = calculator.calculate(Decimal("0.045"), Decimal("0.050"))
    assert result == Decimal("-0.005")


def test_benchmark_spread() -> None:
    calculator = BenchmarkSpreadCalculator()
    result = calculator.calculate(Decimal("0.045"), Decimal("0.050"))
    assert result == Decimal("-0.005")


def test_exact_curve_tenor() -> None:
    calculator = InterpolatedCurveSpreadCalculator()
    curve = _build_curve()
    result = calculator.calculate(Decimal("0.045"), curve, Decimal("5"))
    assert result == Decimal("0.005")


def test_interpolated_curve_tenor() -> None:
    calculator = InterpolatedCurveSpreadCalculator()
    curve = _build_curve()
    result = calculator.calculate(Decimal("0.045"), curve, Decimal("7"))
    assert result == Decimal("0.005")


def test_unavailable_curve() -> None:
    calculator = InterpolatedCurveSpreadCalculator()
    with pytest.raises(CurveNotAvailableError):
        calculator.calculate(Decimal("0.045"), None, Decimal("5"))


def test_unavailable_benchmark() -> None:
    calculator = BenchmarkSpreadCalculator()
    with pytest.raises(BenchmarkNotAvailableError):
        calculator.calculate(Decimal("0.045"), None)


def test_unsupported_curve_extrapolation() -> None:
    calculator = InterpolatedCurveSpreadCalculator()
    curve = _build_curve()
    with pytest.raises(SpreadCalculationError):
        calculator.calculate(Decimal("0.045"), curve, Decimal("12"))


def test_z_spread_convergence() -> None:
    calculator = ZSpreadCalculator()
    instrument = _build_instrument()
    curve = _build_curve()
    result = calculator.calculate(Decimal("0.045"), curve, instrument, Decimal("0.01"), Decimal("0.001"))
    assert result > Decimal("0")


def test_z_spread_unavailable_for_unsupported_instruments() -> None:
    calculator = ZSpreadCalculator()
    with pytest.raises(SpreadCalculationError):
        calculator.calculate(Decimal("0.045"), _build_curve(), object(), Decimal("0.01"), Decimal("0.001"))


def test_z_spread_non_convergence_raises() -> None:
    calculator = ZSpreadCalculator()
    instrument = SimpleNamespace(coupon_schedule=SimpleNamespace(coupons=[]), face_value=Decimal("100"))
    with pytest.raises(SpreadCalculationError):
        calculator.calculate(Decimal("0.045"), _build_curve(), instrument, Decimal("0.01"), Decimal("0.001"))


def test_decimal_precision() -> None:
    calculator = NominalSpreadCalculator()
    result = calculator.calculate(Decimal("0.1000"), Decimal("0.1001"))
    assert result == Decimal("-0.0001")


def test_theoretical_vs_market_price_differences() -> None:
    engine = RelativeValueEngine()
    request = RelativeValueRequest(
        valuation_date=date(2024, 1, 1),
        instrument=_build_instrument(),
        observed_market_price=Decimal("980000"),
        observed_market_yield=Decimal("0.046"),
        reference_curve=_build_curve(),
        pricing_configuration={},
    )
    result = engine.evaluate(request)
    assert result.theoretical_price > Decimal("0")
    assert result.absolute_price_difference > Decimal("0")
    assert result.percentage_price_difference > Decimal("0")


def test_configurable_weights() -> None:
    score = RelativeValueScore(
        raw_values={"spread": Decimal("0.1"), "liquidity": Decimal("0.9")},
        weights={"spread": Decimal("0.3"), "liquidity": Decimal("0.7")},
        directions={"spread": ScoreDirection.LOWER_IS_BETTER, "liquidity": ScoreDirection.HIGHER_IS_BETTER},
        bands={"spread": (ScoreBand("spread", "spread", Decimal("0"), Decimal("1")),)},
    )
    assert score.final_score > Decimal("0")


def test_missing_score_components() -> None:
    with pytest.raises(InvalidWeightError):
        RelativeValueScore(raw_values={"spread": Decimal("0.1")}, weights={"spread": Decimal("1")}, directions={"spread": ScoreDirection.LOWER_IS_BETTER})


def test_invalid_and_zero_total_weights() -> None:
    with pytest.raises(InvalidWeightError):
        RelativeValueScore(raw_values={"spread": Decimal("0.1")}, weights={"spread": Decimal("0")}, directions={"spread": ScoreDirection.LOWER_IS_BETTER})


def test_relative_value_score_reconciles_contributions_and_component_weights() -> None:
    score = RelativeValueScore(
        raw_values={"spread": Decimal("0.1"), "liquidity": Decimal("0.8")},
        weights={"spread": Decimal("0.3"), "liquidity": Decimal("0.7")},
        directions={"spread": ScoreDirection.LOWER_IS_BETTER, "liquidity": ScoreDirection.HIGHER_IS_BETTER},
    )
    assert score.final_score == Decimal("0.83")
    assert score.component_contributions["spread"] == Decimal("0.27")
    assert score.component_contributions["liquidity"] == Decimal("0.56")


def test_rich_cheap_classification() -> None:
    score = RichCheapScore(Decimal("0.002"))
    assert score.status is ValuationStatus.CHEAP


def test_rich_cheap_score_handles_boundary_and_invalid_values() -> None:
    assert RichCheapScore(Decimal("0")).status is ValuationStatus.FAIR
    assert RichCheapScore(Decimal("-0.001")).status is ValuationStatus.RICH
    assert RichCheapScore(Decimal("0.001")).status is ValuationStatus.CHEAP
    with pytest.raises(ValueError):
        RichCheapScore(Decimal("NaN"))


def test_confidence_based_on_evidence_completeness() -> None:
    score = ConfidenceScore(Decimal("0.8"), Decimal("0.9"), Decimal("0.7"))
    assert score.level is ConfidenceLevel.HIGH


def test_confidence_score_validates_boundary_and_incomplete_components() -> None:
    assert ConfidenceScore(Decimal("0.0"), Decimal("0.0"), Decimal("0.0")).level is ConfidenceLevel.LOW
    assert ConfidenceScore(Decimal("0.5"), Decimal("0.5"), Decimal("0.5")).level is ConfidenceLevel.MEDIUM
    with pytest.raises(ValueError):
        ConfidenceScore(Decimal("1.1"), Decimal("0.5"), Decimal("0.5"))
    with pytest.raises(ValueError):
        ConfidenceScore(Decimal("NaN"), Decimal("0.5"), Decimal("0.5"))


def test_decision_matrix_reconciliation() -> None:
    matrix = DecisionMatrix(
        factor_id="spread",
        factor_label="Spread",
        raw_value=Decimal("0.01"),
        unit="bp",
        normalized_value=Decimal("0.6"),
        configured_weight=Decimal("0.4"),
        effective_weight=Decimal("0.24"),
        contribution=Decimal("0.24"),
        direction=ScoreDirection.HIGHER_IS_BETTER,
        evidence="evidence",
        reference="ref",
        status="PASS",
    )
    assert matrix.contribution == Decimal("0.24")


def test_buy_recommendation() -> None:
    result = RecommendationEngine().recommend(
        score=Decimal("0.9"),
        policy_summary={"status": "PASSED"},
        thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")},
        policy_result=None,
    )
    assert result.recommendation is RecommendationType.BUY


def test_accumulate_recommendation() -> None:
    result = RecommendationEngine().recommend(
        score=Decimal("0.7"),
        policy_summary={"status": "PASSED"},
        thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")},
        policy_result=None,
    )
    assert result.recommendation is RecommendationType.ACCUMULATE


def test_hold_recommendation() -> None:
    result = RecommendationEngine().recommend(
        score=Decimal("0.5"),
        policy_summary={"status": "PASSED"},
        thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")},
        policy_result=None,
    )
    assert result.recommendation is RecommendationType.HOLD


def test_reduce_recommendation() -> None:
    result = RecommendationEngine().recommend(
        score=Decimal("0.2"),
        policy_summary={"status": "PASSED"},
        thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")},
        policy_result=None,
    )
    assert result.recommendation is RecommendationType.REDUCE


def test_sell_recommendation() -> None:
    result = RecommendationEngine().recommend(
        score=Decimal("0.0"),
        policy_summary={"status": "PASSED"},
        thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")},
        policy_result=None,
    )
    assert result.recommendation is RecommendationType.SELL


def test_review_recommendation() -> None:
    result = RecommendationEngine().recommend(
        score=Decimal("0.5"),
        policy_summary={"status": "WARNING"},
        thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")},
        policy_result=None,
    )
    assert result.recommendation is RecommendationType.REVIEW


def test_blocking_policy_failure() -> None:
    policy_result = Recommendation("policy", RecommendationType.BUY, Decimal("0.9"), Decimal("0.9"), "", policy_summary={"blocking": True})
    with pytest.raises(RecommendationError):
        RecommendationEngine().recommend(score=Decimal("0.9"), policy_summary={"status": "FAILED"}, thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")}, policy_result=policy_result)


def test_warning_policy_outcome() -> None:
    result = RecommendationEngine().recommend(
        score=Decimal("0.9"),
        policy_summary={"status": "WARNING"},
        thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")},
        policy_result=None,
    )
    assert result.recommendation is RecommendationType.REVIEW


def test_disabled_policy() -> None:
    policy_result = Recommendation("policy", RecommendationType.BUY, Decimal("0.9"), Decimal("0.9"), "", policy_summary={"disabled": True})
    result = RecommendationEngine().recommend(score=Decimal("0.9"), policy_summary={"status": "NOT_APPLICABLE"}, thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")}, policy_result=policy_result)
    assert result.recommendation is RecommendationType.HOLD


def test_not_applicable_policy() -> None:
    policy_result = Recommendation("policy", RecommendationType.BUY, Decimal("0.9"), Decimal("0.9"), "", policy_summary={"not_applicable": True})
    result = RecommendationEngine().recommend(score=Decimal("0.9"), policy_summary={"status": "NOT_APPLICABLE"}, thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")}, policy_result=policy_result)
    assert result.recommendation is RecommendationType.HOLD


def test_ranking_order() -> None:
    ranking = InvestmentRanking()
    opportunities = (
        InvestmentOpportunity("B", Decimal("0.8"), recommendation=RecommendationType.BUY),
        InvestmentOpportunity("A", Decimal("0.9"), recommendation=RecommendationType.BUY),
    )
    result = ranking.rank(opportunities)
    assert [item.business_id for item in result.ranked_items] == ["A", "B"]


def test_dense_rank() -> None:
    ranking = InvestmentRanking()
    opportunities = (
        InvestmentOpportunity("A", Decimal("0.9"), recommendation=RecommendationType.BUY),
        InvestmentOpportunity("B", Decimal("0.9"), recommendation=RecommendationType.BUY),
    )
    result = ranking.rank(opportunities)
    assert result.dense_rank == (1, 1)


def test_percentile_rank() -> None:
    ranking = InvestmentRanking()
    opportunities = (
        InvestmentOpportunity("A", Decimal("0.9"), recommendation=RecommendationType.BUY),
        InvestmentOpportunity("B", Decimal("0.8"), recommendation=RecommendationType.BUY),
    )
    result = ranking.rank(opportunities)
    assert result.percentile_rank == (Decimal("1"), Decimal("0.5"))


def test_ranking_ties() -> None:
    ranking = InvestmentRanking()
    opportunities = (
        InvestmentOpportunity("A", Decimal("0.9"), recommendation=RecommendationType.BUY),
        InvestmentOpportunity("B", Decimal("0.9"), recommendation=RecommendationType.BUY),
    )
    result = ranking.rank(opportunities)
    assert result.tie_groups == (("A", "B"),)


def test_duplicate_identifiers() -> None:
    ranking = InvestmentRanking()
    opportunities = (
        InvestmentOpportunity("A", Decimal("0.9"), recommendation=RecommendationType.BUY),
        InvestmentOpportunity("A", Decimal("0.8"), recommendation=RecommendationType.BUY),
    )
    with pytest.raises(ValueError):
        ranking.rank(opportunities)


def test_explanation_factors_and_references() -> None:
    explanation = RecommendationExplanation(
        concise_conclusion="Conclusion",
        supporting_factors=(
            {
                "name": "spread",
                "value": Decimal("0.01"),
                "direction": "higher_is_better",
                "contribution": Decimal("0.01"),
                "source_reference": "ref",
            },
        ),
    )
    assert explanation.supporting_factor_objects[0].source_reference == "ref"


def test_recommendation_explanation_handles_positive_negative_and_empty_factors() -> None:
    explanation = RecommendationExplanation(
        concise_conclusion="Conclusion",
        supporting_factors=(
            {"name": "spread", "value": Decimal("0.01"), "direction": "higher_is_better", "contribution": Decimal("0.02"), "source_reference": "curve"},
            {"name": "credit", "value": Decimal("-0.005"), "direction": "lower_is_better", "contribution": Decimal("-0.01"), "source_reference": "policy"},
            "unsupported",
        ),
        assumptions=("Assumption",),
        warnings=("Warning",),
        source_references=("reference",),
    )
    built = explanation.to_explanation()
    assert built.concise_conclusion == "Conclusion"
    assert [factor.name for factor in built.supporting_factors] == ["spread", "credit"]
    assert built.assumptions == ("Assumption",)
    assert built.warnings == ("Warning",)
    assert built.source_references == ("reference",)
    assert explanation.supporting_factor_objects[1].source_reference == "policy"

    empty_explanation = RecommendationExplanation(concise_conclusion="Empty", supporting_factors=())
    empty_build = empty_explanation.to_explanation()
    assert empty_build.supporting_factors[0].name == "default"
    assert empty_build.supporting_factors[0].contribution == Decimal("0")


def test_assumptions_and_warnings() -> None:
    result = RelativeValueResult(
        instrument_id="A",
        observed_market_price=Decimal("100"),
        theoretical_price=Decimal("95"),
        absolute_price_difference=Decimal("5"),
        percentage_price_difference=Decimal("0.05"),
        nominal_spread=Decimal("0.01"),
        benchmark_spread=Decimal("0.01"),
        interpolated_curve_spread=Decimal("0.01"),
        z_spread=Decimal("0.01"),
        rich_cheap_score=Decimal("0.01"),
        relative_value_score=Decimal("0.01"),
        confidence_score=Decimal("0.01"),
        ranking_result=None,
        recommendation=RecommendationType.BUY,
        policy_evaluation_summary={"status": "PASSED"},
        decision_matrix=(),
        assumptions=("assumption",),
        warnings=("warning",),
        references=("ref",),
        explanation="explanation",
        calculation_timestamp=datetime.now(),
        calculation_identifier="id",
        valuation_status=ValuationStatus.CHEAP,
    )
    assert result.assumptions == ("assumption",)
    assert result.warnings == ("warning",)


def test_provider_failure_paths() -> None:
    engine = RelativeValueEngine()
    request = RelativeValueRequest(
        valuation_date=date(2024, 1, 1),
        instrument=_build_instrument(),
        observed_market_price=Decimal("980000"),
        observed_market_yield=Decimal("0.046"),
        pricing_configuration={"curve": None},
    )
    with pytest.raises(RelativeValueError):
        engine.evaluate(request)


def test_every_domain_exception() -> None:
    with pytest.raises(BenchmarkNotAvailableError):
        BenchmarkSpreadCalculator().calculate(Decimal("0.045"), None)
    with pytest.raises(CurveNotAvailableError):
        InterpolatedCurveSpreadCalculator().calculate(Decimal("0.045"), None, Decimal("5"))
    with pytest.raises(UnsupportedSpreadTypeError):
        SpreadEngine().calculate("unsupported", Decimal("0.045"), Decimal("0.05"))
    with pytest.raises(RecommendationError):
        RecommendationEngine().recommend(score=Decimal("0.9"), policy_summary={"status": "FAILED"}, thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")}, policy_result=None)


# Additional regression tests for the earlier defects.

def test_regression_missing_curve_reference() -> None:
    request = RelativeValueRequest(
        valuation_date=date(2024, 1, 1),
        instrument=_build_instrument(),
        observed_market_price=Decimal("980000"),
        observed_market_yield=Decimal("0.046"),
        pricing_configuration={"curve": None},
    )
    with pytest.raises(CurveNotAvailableError):
        RelativeValueEngine().evaluate(request)


def test_relative_value_engine_handles_benchmark_yield_and_curve_paths() -> None:
    engine = RelativeValueEngine()
    request = RelativeValueRequest(
        valuation_date=date(2024, 1, 1),
        instrument=_build_instrument(),
        observed_market_price=Decimal("980000"),
        observed_market_yield=Decimal("0.046"),
        reference_curve=_build_curve(),
        benchmark_yield=Decimal("0.05"),
        pricing_configuration={},
    )
    result = engine.evaluate(request)
    assert result.nominal_spread == Decimal("-0.004")
    assert result.benchmark_spread == Decimal("-0.004")


def test_relative_value_request_rejects_non_finite_decimal_values() -> None:
    with pytest.raises(ValueError):
        RelativeValueRequest(
            valuation_date=date(2024, 1, 1),
            instrument=_build_instrument(),
            observed_market_price=Decimal("NaN"),
            observed_market_yield=Decimal("0.046"),
            reference_curve=_build_curve(),
        )
    with pytest.raises(ValueError):
        RelativeValueRequest(
            valuation_date=date(2024, 1, 1),
            instrument=_build_instrument(),
            observed_market_price=Decimal("980000"),
            observed_market_yield=Decimal("NaN"),
            reference_curve=_build_curve(),
        )
