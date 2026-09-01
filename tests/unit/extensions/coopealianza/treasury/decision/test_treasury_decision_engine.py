from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.liquidity.cashflow.models.projection_result import ProjectionResult
from aip.domain.liquidity.gap.models.gap_result import GapResult
from aip.domain.liquidity.hqla.enums import HQLAClassification
from aip.domain.liquidity.hqla.models.hqla_result import HQLAResult
from aip.domain.policies.base.policy_result import PolicyResult
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity
from aip.domain.relative_value.enums.recommendation_type import (
    RecommendationType as RelativeValueRecommendationType,
)
from aip.domain.relative_value.models.relative_value_result import RelativeValueResult
from src.extensions.coopealianza.liquidity.mil.models.mil_result import MilResult
from src.extensions.coopealianza.liquidity.stress.models.stress_result import StressResult
from src.extensions.coopealianza.treasury.decision.analytics.decision_analytics import (
    DecisionAnalytics,
)
from src.extensions.coopealianza.treasury.decision.configuration.decision_config import (
    DecisionConfig,
)
from src.extensions.coopealianza.treasury.decision.engine.decision_engine import (
    TreasuryDecisionEngine,
)
from src.extensions.coopealianza.treasury.decision.enums.recommendation_type import (
    RecommendationType,
)
from src.extensions.coopealianza.treasury.decision.exceptions import (
    ConflictingRecommendationError,
    DecisionAnalyticsError,
    DecisionConfigurationError,
    DecisionProviderError,
    DecisionReportError,
    PrioritizationError,
    RecommendationError,
    TreasuryDecisionConfigurationError,
    TreasuryDecisionError,
    TreasuryDecisionEvaluationError,
)
from src.extensions.coopealianza.treasury.decision.models.decision_request import (
    TreasuryDecisionRequest,
)
from src.extensions.coopealianza.treasury.decision.models.decision_result import (
    TreasuryDecisionResult,
)
from src.extensions.coopealianza.treasury.decision.models.impact_metrics import ImpactMetrics
from src.extensions.coopealianza.treasury.decision.models.priority import PriorityLevel
from src.extensions.coopealianza.treasury.decision.models.recommendation import Recommendation
from src.extensions.coopealianza.treasury.decision.providers.recommendation_provider import (
    RecommendationProvider,
)
from src.extensions.coopealianza.treasury.decision.reports.decision_report_builder import (
    DecisionReportBuilder,
)


def make_policy_result(status: str = "PASSED") -> PolicyResult:
    return PolicyResult(
        policy_id="policy-1",
        status=status,
        message="ok",
        severity=PolicySeverity.INFO,
        references=(PolicyReference(source="coopealianza", identifier="POL-1"),),
        timestamp=datetime(2024, 1, 1, 12, 0),
        evaluation_duration=0.1,
        context_id="ctx-1",
    )


def make_relative_value_result() -> RelativeValueResult:
    return RelativeValueResult(
        instrument_id="bond-1",
        observed_market_price=Decimal("1000"),
        theoretical_price=Decimal("980"),
        absolute_price_difference=Decimal("20"),
        percentage_price_difference=Decimal("0.02"),
        nominal_spread=Decimal("0.01"),
        benchmark_spread=Decimal("0.02"),
        interpolated_curve_spread=Decimal("0.015"),
        z_spread=Decimal("0.01"),
        rich_cheap_score=Decimal("0.8"),
        relative_value_score=Decimal("0.75"),
        confidence_score=Decimal("0.82"),
        ranking_result=None,
        recommendation=RelativeValueRecommendationType.ACCUMULATE,
        policy_evaluation_summary={"status": "PASSED"},
        explanation="rich",
    )


def make_hqla_result() -> HQLAResult:
    return HQLAResult(
        valuation_date=date(2024, 1, 1),
        instrument_id="bond-1",
        classification=HQLAClassification.ELIGIBLE,
        eligible=True,
        score=Decimal("0.91"),
        reason="eligible",
        analytics={"liquidity": Decimal("0.91")},
        explanation=Explanation(
            concise_conclusion="eligible",
            supporting_factors=(),
        ),
    )


def make_mil_result() -> MilResult:
    return MilResult(
        portfolio_reference="portfolio-1",
        configuration_version="1.0",
        calculation_date=date(2024, 1, 1),
        total_assets_evaluated=1,
        positions=(),
        capacity=object(),
        status_counts={"eligible": 1},
        policy_references=("MIL-REF",),
        warnings=(),
        recommended_actions=(),
        explanation=None,
        calculation_identifier="mil-1",
    )


def make_stress_result() -> StressResult:
    return StressResult(
        portfolio_reference="portfolio-1",
        configuration_version="1.0",
        total_scenarios=1,
        scenario_results=(),
        summary={
            "max_stressed_gap": Decimal("1230"),
            "max_stressed_outflow": Decimal("6000"),
            "max_effect": Decimal("230"),
        },
        explanation=None,
        assumptions=(),
        stressed_parameters={},
        policy_references=(),
        warnings=(),
        affected_assets=(),
        affected_buckets=(),
        calculation_identifier="stress-1",
    )


def make_request() -> TreasuryDecisionRequest:
    return TreasuryDecisionRequest(
        portfolio_reference="portfolio-1",
        policy_results=(make_policy_result(),),
        relative_value_result=make_relative_value_result(),
        hqla_result=make_hqla_result(),
        mil_result=make_mil_result(),
        stress_result=make_stress_result(),
        projection_result=ProjectionResult(projection_type="contractual", projected_cashflows=()),
        gap_result=GapResult(
            valuation_date=date(2024, 1, 1),
            gap_type="daily",
            net_gap=Decimal("1000"),
            gross_inflow=Decimal("4000"),
            gross_outflow=Decimal("5000"),
            incremental_gap=Decimal("100"),
            cumulative_gap=Decimal("1000"),
            summary_value=Decimal("1000"),
        ),
        configuration=DecisionConfig(
            policy_id="treasury-decision", version="1.0", name="Treasury Decision"
        ),
    )


def test_engine_generates_deterministic_recommendations() -> None:
    engine = TreasuryDecisionEngine()
    result = engine.evaluate(make_request())

    assert isinstance(result, TreasuryDecisionResult)
    assert result.recommendations
    assert result.recommendations[0].recommendation == RecommendationType.ACCUMULATE
    assert result.recommendation_groups
    assert (
        result.recommendation_groups[0].recommendations[0].recommendation
        == RecommendationType.ACCUMULATE
    )
    assert result.explanation is not None
    assert result.summary["total_recommendations"] == 4


def test_engine_raises_for_blocking_policy_statuses() -> None:
    request = replace(make_request(), policy_results=(make_policy_result("FAILED"),))
    engine = TreasuryDecisionEngine()
    with pytest.raises(TreasuryDecisionError):
        engine.evaluate(request)


def test_analytics_builds_explanation_and_report_builder_works() -> None:
    analytics = DecisionAnalytics()
    explanation = analytics.build_explanation(
        conclusion="Treasury decision generated",
        factors=[("relative_value_score", Decimal("0.75"))],
    )
    assert explanation.concise_conclusion == "Treasury decision generated"
    assert explanation.supporting_factors[0].value == Decimal("0.75")

    report = DecisionReportBuilder().build(
        make_request(), TreasuryDecisionEngine().evaluate(make_request())
    )
    assert report["portfolio_reference"] == "portfolio-1"
    assert report["recommendations"][0]["recommendation"] == "ACCUMULATE"


def test_configuration_supports_mapping_and_validation() -> None:
    config = DecisionConfig.from_mapping({"policy_id": "p", "version": "1.0", "name": "n"})
    assert config.policy_id == "p"
    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(policy_id="", version="1.0", name="")


def test_analytics_summary_handles_empty_and_non_empty_inputs() -> None:
    analytics = DecisionAnalytics()
    empty_summary = analytics.summarize(())
    assert empty_summary["count_by_type"] == {}
    assert empty_summary["no_action_ratio"] == Decimal("0")

    populated_summary = analytics.summarize(
        (
            Recommendation(
                recommendation_id="rec-1",
                instrument_id="instrument-1",
                recommendation=RecommendationType.ACCUMULATE,
                priority=PriorityLevel.HIGH,
                score=Decimal("0.8"),
                confidence=Decimal("0.9"),
                explanation="ok",
                rationale=("relative_value",),
                policy_summary={"status": "PASSED"},
                rejected_alternatives=(),
                expected_impact=ImpactMetrics(),
                policy_references=(),
                affected_assets=(),
                upstream_calculation_references=(),
                assumptions=(),
                warnings=(),
                correlation_id="",
                calculation_id="",
                decision_horizon="T+1",
            ),
        )
    )
    assert populated_summary["count_by_type"] == {"ACCUMULATE": 1}


def test_engine_uses_provider_when_available() -> None:
    class StubProvider(RecommendationProvider):
        def get_recommendations(
            self, request: TreasuryDecisionRequest
        ) -> tuple[Recommendation, ...]:
            return (
                Recommendation(
                    recommendation_id="provider-rec",
                    instrument_id=request.portfolio_reference,
                    recommendation=RecommendationType.ACCUMULATE,
                    priority=PriorityLevel.HIGH,
                    score=Decimal("0.9"),
                    confidence=Decimal("0.95"),
                    explanation="provider",
                    rationale=("provider",),
                    policy_summary={"status": "PASSED"},
                    rejected_alternatives=(),
                    expected_impact=ImpactMetrics(),
                    policy_references=(),
                    affected_assets=(),
                    upstream_calculation_references=(),
                    assumptions=(),
                    warnings=(),
                    correlation_id=request.correlation_id,
                    calculation_id=request.calculation_id,
                    decision_horizon=request.decision_horizon,
                ),
            )

    engine = TreasuryDecisionEngine(provider=StubProvider())
    result = engine.evaluate(make_request())

    assert result.recommendations[0].recommendation == RecommendationType.ACCUMULATE


def test_configuration_rejects_invalid_thresholds_and_dates() -> None:
    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p",
            version="1.0",
            name="n",
            recommendation_thresholds={"buy": Decimal("-1")},
        )

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p",
            version="1.0",
            name="n",
            effective_date=date(2099, 1, 1),
            expiration_date=date(2099, 2, 1),
        )


def test_configuration_covers_branch_conditions() -> None:
    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p",
            version="1.0",
            name="n",
            materiality_thresholds={"concentration": Decimal("1.1")},
        )

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p",
            version="1.0",
            name="n",
            priority_thresholds={"warning": Decimal("0.8"), "blocking": Decimal("0.7")},
        )

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p",
            version="1.0",
            name="n",
            require_policy_references=True,
            policy_references=(),
        )

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p", version="1.0", name="n", conflicting_signal_resolution="invalid"
        )

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(policy_id="p", version="1.0", name="n", partial_input_behavior="invalid")

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p", version="1.0", name="n", enabled_recommendation_types=("BUY", "BUY")
        )

    config = DecisionConfig.from_mapping(
        {
            "policy_id": "p",
            "version": "1.0",
            "name": "n",
            "enabled_recommendation_types": ("BUY", "SELL"),
            "policy_references": ("POL-1",),
            "require_policy_references": True,
        }
    )
    assert config.policy_references == ("POL-1",)


def test_decision_engine_covers_all_recommendation_types_and_priorities() -> None:
    request = replace(
        make_request(),
        policy_results=(make_policy_result(),),
        relative_value_result=replace(
            make_relative_value_result(), relative_value_score=Decimal("0.1")
        ),
        mil_result=replace(make_mil_result(), status_counts={"eligible": 1}),
        gap_result=GapResult(
            valuation_date=date(2024, 1, 1),
            gap_type="daily",
            net_gap=Decimal("-100"),
            gross_inflow=Decimal("4000"),
            gross_outflow=Decimal("5000"),
            incremental_gap=Decimal("100"),
            cumulative_gap=Decimal("-100"),
            summary_value=Decimal("-100"),
        ),
        stress_result=replace(make_stress_result(), summary={"max_effect": Decimal("10")}),
    )
    result = TreasuryDecisionEngine().evaluate(request)
    recommendation_values = {item.recommendation.value for item in result.recommendations}
    assert RecommendationType.SELL.value in recommendation_values
    assert RecommendationType.USE_AS_COLLATERAL.value in recommendation_values
    assert RecommendationType.IMPROVE_LIQUIDITY.value in recommendation_values
    assert RecommendationType.LIMIT_EXCESS_RISK.value in recommendation_values
    assert RecommendationType.NO_ACTION.value in recommendation_values
    priorities = {item.priority.value for item in result.recommendations}
    assert priorities.issuperset(
        {
            PriorityLevel.CRITICAL.value,
            PriorityLevel.HIGH.value,
            PriorityLevel.MEDIUM.value,
            PriorityLevel.INFO.value,
        }
    )


def test_engine_emits_expected_recommendation_family_for_each_branch() -> None:
    engine = TreasuryDecisionEngine()
    attractive_request = replace(
        make_request(),
        relative_value_result=replace(
            make_relative_value_result(), relative_value_score=Decimal("0.8")
        ),
    )
    attractive_result = engine.evaluate(attractive_request)
    assert RecommendationType.ACCUMULATE.value in {
        item.recommendation.value for item in attractive_result.recommendations
    }

    unattractive_request = replace(
        make_request(),
        relative_value_result=replace(
            make_relative_value_result(), relative_value_score=Decimal("0.1")
        ),
    )
    unattractive_result = engine.evaluate(unattractive_request)
    assert RecommendationType.SELL.value in {
        item.recommendation.value for item in unattractive_result.recommendations
    }

    hold_request = replace(
        make_request(),
        relative_value_result=replace(
            make_relative_value_result(), relative_value_score=Decimal("0.2")
        ),
    )
    hold_result = engine.evaluate(hold_request)
    assert RecommendationType.HOLD.value in {
        item.recommendation.value for item in hold_result.recommendations
    }

    collateral_request = replace(
        make_request(), mil_result=replace(make_mil_result(), status_counts={"eligible": 1})
    )
    collateral_result = engine.evaluate(collateral_request)
    assert RecommendationType.USE_AS_COLLATERAL.value in {
        item.recommendation.value for item in collateral_result.recommendations
    }

    ineligible_request = replace(
        make_request(), mil_result=replace(make_mil_result(), status_counts={"ineligible": 1})
    )
    ineligible_result = engine.evaluate(ineligible_request)
    assert RecommendationType.DO_NOT_USE_AS_COLLATERAL.value in {
        item.recommendation.value for item in ineligible_result.recommendations
    }

    concentration_request = replace(
        make_request(),
        portfolio_result=type("PortfolioResult", (), {"concentration_ratio": Decimal("0.3")})(),
    )
    concentration_result = engine.evaluate(concentration_request)
    assert RecommendationType.REDUCE_CONCENTRATION.value in {
        item.recommendation.value for item in concentration_result.recommendations
    }

    liquidity_request = replace(
        make_request(),
        gap_result=GapResult(
            date(2024, 1, 1),
            "daily",
            Decimal("-100"),
            Decimal("4000"),
            Decimal("5000"),
            Decimal("100"),
            Decimal("-100"),
            Decimal("-100"),
        ),
    )
    liquidity_result = engine.evaluate(liquidity_request)
    assert RecommendationType.IMPROVE_LIQUIDITY.value in {
        item.recommendation.value for item in liquidity_result.recommendations
    }

    stress_request = replace(
        make_request(),
        stress_result=replace(make_stress_result(), summary={"max_effect": Decimal("10")}),
    )
    stress_result = engine.evaluate(stress_request)
    assert RecommendationType.LIMIT_EXCESS_RISK.value in {
        item.recommendation.value for item in stress_result.recommendations
    }

    monitor_request = replace(make_request(), policy_results=(make_policy_result("WARNING"),))
    monitor_result = engine.evaluate(monitor_request)
    assert RecommendationType.MONITOR.value in {
        item.recommendation.value for item in monitor_result.recommendations
    }

    no_action_request = replace(
        make_request(),
        relative_value_result=None,
        mil_result=None,
        gap_result=None,
        stress_result=None,
        policy_results=(make_policy_result(),),
        portfolio_result=type("PortfolioResult", (), {"concentration_ratio": Decimal("0.1")})(),
    )
    no_action_result = engine.evaluate(no_action_request)
    assert RecommendationType.NO_ACTION.value in {
        item.recommendation.value for item in no_action_result.recommendations
    }


def test_engine_covers_error_fallback_and_provider_branches() -> None:
    engine = TreasuryDecisionEngine()

    with pytest.raises(TreasuryDecisionEvaluationError):
        engine.evaluate(replace(make_request(), portfolio_reference=""))

    with pytest.raises(TreasuryDecisionEvaluationError):
        engine.evaluate(replace(make_request(), policy_results=(), configuration=None))

    with pytest.raises(DecisionConfigurationError):
        engine.evaluate(
            replace(
                make_request(),
                configuration=DecisionConfig(policy_id="p", version="1.0", name="n", enabled=False),
            )
        )

    dict_config_result = engine.evaluate(
        replace(
            make_request(),
            configuration={
                "policy_id": "p",
                "version": "1.0",
                "name": "n",
                "enabled_recommendation_types": ("BUY",),
            },
        )
    )
    assert RecommendationType.ACCUMULATE.value in {
        item.recommendation.value for item in dict_config_result.recommendations
    }
    assert RecommendationType.NO_ACTION.value not in {
        item.recommendation.value for item in dict_config_result.recommendations
    }

    fallback_result = engine.evaluate(replace(make_request(), configuration=object()))
    assert fallback_result.summary["total_recommendations"] >= 1

    class BoomProvider(RecommendationProvider):
        def get_recommendations(
            self, request: TreasuryDecisionRequest
        ) -> tuple[Recommendation, ...]:
            raise RuntimeError("boom")

    class NullProvider(RecommendationProvider):
        def get_recommendations(
            self, request: TreasuryDecisionRequest
        ) -> tuple[Recommendation, ...]:
            return None  # type: ignore[return-value]

    with pytest.raises(DecisionProviderError):
        TreasuryDecisionEngine(provider=BoomProvider()).evaluate(make_request())

    with pytest.raises(DecisionProviderError):
        TreasuryDecisionEngine(provider=NullProvider()).evaluate(make_request())


def test_decision_analytics_and_config_cover_edge_branches() -> None:
    analytics = DecisionAnalytics()

    with pytest.raises(DecisionAnalyticsError):
        analytics.build_explanation("", [("value", Decimal("1"))])

    assert analytics._is_decimal_string("42") is True
    assert analytics._is_decimal_string("not-a-decimal") is False

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p",
            version="1.0",
            name="n",
            effective_date=date(2024, 1, 2),
            expiration_date=date(2024, 1, 1),
        )

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(
            policy_id="p",
            version="1.0",
            name="n",
            effective_date=date(2023, 1, 1),
            expiration_date=date(2024, 1, 1),
        )

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig(policy_id="p", version="1.0", name="n", duplicate_handling="invalid")

    config = DecisionConfig.from_mapping(
        {
            "policy_id": "p",
            "version": "1.0",
            "name": "n",
            "effective_date": str(date.today() - timedelta(days=1)),
            "expiration_date": str(date.today() + timedelta(days=2)),
        }
    )
    assert config.effective_date == date.today() - timedelta(days=1)

    with pytest.raises(TreasuryDecisionConfigurationError):
        DecisionConfig.from_mapping(
            {"policy_id": "p", "version": "1.0", "name": "n", "effective_date": object()}
        )


def test_engine_helpers_cover_priority_and_upstream_branches() -> None:
    engine = TreasuryDecisionEngine()

    with pytest.raises(PrioritizationError):
        engine._priority_value(None)

    with pytest.raises(PrioritizationError):
        engine._priority_value("unsupported")

    request = replace(
        make_request(), pricing_result=object(), relative_value_result=None, stress_result=None
    )
    references = engine._upstream_references(request)
    assert "pricing" in references
    assert "relative_value" not in references


def test_conflicting_recommendations_and_deduplication() -> None:
    engine = TreasuryDecisionEngine()
    request = make_request()
    with pytest.raises(ConflictingRecommendationError):
        engine._ensure_no_conflicts(
            (
                Recommendation(
                    recommendation_id="a",
                    instrument_id=request.portfolio_reference,
                    recommendation=RecommendationType.BUY,
                    priority=PriorityLevel.HIGH,
                    score=Decimal("0.8"),
                    confidence=Decimal("0.8"),
                    explanation="x",
                    rationale=("r",),
                    policy_summary={"status": "PASSED"},
                    rejected_alternatives=(),
                    expected_impact=ImpactMetrics(),
                    policy_references=(),
                    affected_assets=(),
                    upstream_calculation_references=(),
                    assumptions=(),
                    warnings=(),
                    correlation_id="",
                    calculation_id="",
                    decision_horizon=request.decision_horizon,
                ),
                Recommendation(
                    recommendation_id="b",
                    instrument_id=request.portfolio_reference,
                    recommendation=RecommendationType.SELL,
                    priority=PriorityLevel.HIGH,
                    score=Decimal("0.8"),
                    confidence=Decimal("0.8"),
                    explanation="x",
                    rationale=("r",),
                    policy_summary={"status": "PASSED"},
                    rejected_alternatives=(),
                    expected_impact=ImpactMetrics(),
                    policy_references=(),
                    affected_assets=(),
                    upstream_calculation_references=(),
                    assumptions=(),
                    warnings=(),
                    correlation_id="",
                    calculation_id="",
                    decision_horizon=request.decision_horizon,
                ),
            )
        )

    deduped = engine._dedupe_recommendations(
        (
            Recommendation(
                recommendation_id="dedupe-1",
                instrument_id=request.portfolio_reference,
                recommendation=RecommendationType.NO_ACTION,
                priority=PriorityLevel.INFO,
                score=Decimal("0.1"),
                confidence=Decimal("0.6"),
                explanation="x",
                rationale=("r",),
                policy_summary={"status": "PASSED"},
                rejected_alternatives=(),
                expected_impact=ImpactMetrics(),
                policy_references=(),
                affected_assets=(),
                upstream_calculation_references=(),
                assumptions=(),
                warnings=(),
                correlation_id="",
                calculation_id="",
                decision_horizon=request.decision_horizon,
            ),
            Recommendation(
                recommendation_id="dedupe-1",
                instrument_id=request.portfolio_reference,
                recommendation=RecommendationType.NO_ACTION,
                priority=PriorityLevel.INFO,
                score=Decimal("0.1"),
                confidence=Decimal("0.6"),
                explanation="x",
                rationale=("r",),
                policy_summary={"status": "PASSED"},
                rejected_alternatives=(),
                expected_impact=ImpactMetrics(),
                policy_references=(),
                affected_assets=(),
                upstream_calculation_references=(),
                assumptions=(),
                warnings=(),
                correlation_id="",
                calculation_id="",
                decision_horizon=request.decision_horizon,
            ),
        )
    )
    assert len(deduped) == 1


def test_engine_preserves_identifiers_and_upstream_references() -> None:
    request = replace(make_request(), calculation_id="calc-123", correlation_id="corr-123")
    result = TreasuryDecisionEngine().evaluate(request)
    assert result.calculation_identifier == "calc-123"
    assert result.correlation_id == "corr-123"
    first = result.recommendations[0]
    assert first.calculation_id == "calc-123"
    assert first.correlation_id == "corr-123"
    assert first.upstream_calculation_references


def test_report_builder_handles_empty_and_partial_payloads() -> None:
    builder = DecisionReportBuilder()
    with pytest.raises(DecisionReportError):
        builder.build(
            make_request(),
            TreasuryDecisionResult(
                portfolio_reference="p",
                recommendations=(),
                recommendation_groups=(),
                summary={},
                explanation=None,
            ),
        )

    request = replace(make_request(), portfolio_reference="")
    with pytest.raises(DecisionReportError):
        builder.build(request, TreasuryDecisionEngine().evaluate(make_request()))


def test_provider_and_exception_paths() -> None:
    class BrokenProvider(RecommendationProvider):
        def get_recommendations(
            self, request: TreasuryDecisionRequest
        ) -> tuple[Recommendation, ...]:
            raise RuntimeError("boom")

    with pytest.raises(DecisionProviderError):
        TreasuryDecisionEngine(provider=BrokenProvider()).evaluate(make_request())

    with pytest.raises(DecisionProviderError):
        TreasuryDecisionEngine(
            provider=type("P", (), {"get_recommendations": lambda self, request: None})()
        ).evaluate(make_request())

    with pytest.raises(DecisionAnalyticsError):
        DecisionAnalytics().build_explanation("", factors=[])

    with pytest.raises(DecisionConfigurationError):
        DecisionConfig(policy_id="", version="1.0", name="")

    with pytest.raises(RecommendationError):
        TreasuryDecisionEngine().evaluate(
            replace(make_request(), policy_results=(make_policy_result("FAILED"),))
        )

    with pytest.raises(PrioritizationError):
        TreasuryDecisionEngine()._priority_value(None)

    with pytest.raises(DecisionReportError):
        DecisionReportBuilder().build(
            make_request(),
            TreasuryDecisionResult(
                portfolio_reference="p",
                recommendations=(),
                recommendation_groups=(),
                summary={},
                explanation=None,
            ),
        )
