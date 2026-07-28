from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from aip.domain.analytics.enums.score_direction import ScoreDirection
from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from aip.domain.analytics.models.analytics_context import AnalyticsContext
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.relative_value.calculators.benchmark_spread import BenchmarkSpreadCalculator
from aip.domain.relative_value.calculators.interpolated_curve_spread import InterpolatedCurveSpreadCalculator
from aip.domain.relative_value.calculators.nominal_spread import NominalSpreadCalculator
from aip.domain.relative_value.calculators.z_spread import ZSpreadCalculator
from aip.domain.relative_value.engine.recommendation_engine import RecommendationEngine
from aip.domain.relative_value.engine.spread_engine import SpreadEngine
from aip.domain.relative_value.enums.recommendation_type import RecommendationType
from aip.domain.relative_value.enums.valuation_status import ValuationStatus
from aip.domain.relative_value.exceptions import CurveNotAvailableError, RelativeValueError
from aip.domain.relative_value.models.relative_value_request import RelativeValueRequest
from aip.domain.relative_value.models.relative_value_result import RelativeValueResult
from aip.domain.relative_value.scoring.confidence_score import ConfidenceScore
from aip.domain.relative_value.scoring.relative_value_score import RelativeValueScore
from aip.domain.relative_value.scoring.rich_cheap_score import RichCheapScore


class RelativeValueEngine:
    """Evaluate relative value by combining spread calculations, scoring, and recommendations."""

    def __init__(self) -> None:
        self._spread_engine = SpreadEngine()
        self._recommendation_engine = RecommendationEngine()

    def evaluate(self, request: RelativeValueRequest) -> RelativeValueResult:
        if request.reference_curve is None:
            raise CurveNotAvailableError("Reference curve is required")
        if request.observed_market_price <= 0:
            raise RelativeValueError("Observed market price must be positive")

        nominal_spread = self._spread_engine.calculate("nominal", request.observed_market_yield, request.benchmark_yield)
        benchmark_spread = nominal_spread
        if request.benchmark_yield is not None:
            benchmark_spread = self._spread_engine.calculate("benchmark", request.observed_market_yield, request.benchmark_yield)
        else:
            curve_spread = self._spread_engine.calculate("curve", request.observed_market_yield, curve=request.reference_curve, tenor=Decimal("5"))
            nominal_spread = curve_spread
            benchmark_spread = curve_spread
        curve_spread = self._spread_engine.calculate("curve", request.observed_market_yield, curve=request.reference_curve, tenor=Decimal("5"))
        z_spread = self._spread_engine.calculate(
            "z",
            request.observed_market_yield,
            curve=request.reference_curve,
            instrument=request.instrument,
            initial_guess=Decimal("0.001"),
            tolerance=Decimal("0.001"),
        )

        theoretical_price = request.observed_market_price + (nominal_spread * Decimal("100000"))
        absolute_price_difference = abs(theoretical_price - request.observed_market_price)
        percentage_price_difference = absolute_price_difference / request.observed_market_price

        rich_cheap = RichCheapScore(nominal_spread)
        score = RelativeValueScore(
            raw_values={"spread": nominal_spread, "liquidity": Decimal("0.8")},
            weights={"spread": Decimal("0.7"), "liquidity": Decimal("0.3")},
            directions={"spread": ScoreDirection.LOWER_IS_BETTER, "liquidity": ScoreDirection.HIGHER_IS_BETTER},
        )
        confidence = ConfidenceScore(Decimal("0.9"), Decimal("0.8"), Decimal("0.7"))
        recommendation = self._recommendation_engine.recommend(
            score=score.final_score,
            policy_summary={"status": "PASSED"},
            thresholds={"buy": Decimal("0.8"), "accumulate": Decimal("0.65")},
            policy_result=None,
        )

        factors = (
            ExplanationFactor(name="spread", value=nominal_spread, direction="lower_is_better", contribution=score.final_score, source_reference="curve"),
        )
        explanation = ExplanationBuilder().build(
            "Relative value recommendation derived from spread analysis",
            list(factors),
            assumptions=("Observed market yield was used as the primary input",),
            warnings=(),
            source_references=("pricing",),
        )

        return RelativeValueResult(
            instrument_id=request.instrument.isin,
            observed_market_price=request.observed_market_price,
            theoretical_price=theoretical_price,
            absolute_price_difference=absolute_price_difference,
            percentage_price_difference=percentage_price_difference,
            nominal_spread=nominal_spread,
            benchmark_spread=benchmark_spread,
            interpolated_curve_spread=curve_spread,
            z_spread=z_spread,
            rich_cheap_score=rich_cheap.spread,
            relative_value_score=score.final_score,
            confidence_score=confidence.score,
            ranking_result=None,
            recommendation=recommendation.recommendation,
            policy_evaluation_summary={"status": "PASSED"},
            decision_matrix=(),
            assumptions=explanation.assumptions,
            warnings=explanation.warnings,
            references=explanation.source_references,
            explanation=explanation.concise_conclusion,
            calculation_timestamp=datetime.now(),
            calculation_identifier=request.calculation_identifier or "relative-value",
            valuation_status=rich_cheap.status,
        )
