from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.extensions.coopealianza.treasury.decision.analytics.decision_analytics import DecisionAnalytics
from src.extensions.coopealianza.treasury.decision.configuration.decision_config import DecisionConfig
from src.extensions.coopealianza.treasury.decision.enums.recommendation_type import RecommendationType
from src.extensions.coopealianza.treasury.decision.exceptions import (
    ConflictingRecommendationError,
    DecisionConfigurationError,
    DecisionProviderError,
    PrioritizationError,
    RecommendationError,
    TreasuryDecisionEvaluationError,
)
from src.extensions.coopealianza.treasury.decision.models.decision_request import TreasuryDecisionRequest
from src.extensions.coopealianza.treasury.decision.models.decision_result import TreasuryDecisionResult
from src.extensions.coopealianza.treasury.decision.models.impact_metrics import ImpactMetrics
from src.extensions.coopealianza.treasury.decision.models.priority import PriorityLevel
from src.extensions.coopealianza.treasury.decision.models.recommendation import Recommendation
from src.extensions.coopealianza.treasury.decision.models.recommendation_group import RecommendationGroup
from src.extensions.coopealianza.treasury.decision.providers.recommendation_provider import RecommendationProvider


class TreasuryDecisionEngine:
    """Compose explainable treasury recommendations from existing engine outputs."""

    def __init__(self, provider: RecommendationProvider | None = None) -> None:
        self._analytics = DecisionAnalytics()
        self._provider = provider

    def evaluate(self, request: TreasuryDecisionRequest) -> TreasuryDecisionResult:
        if not request.portfolio_reference:
            raise TreasuryDecisionEvaluationError("Portfolio reference is required")
        if not request.policy_results and not request.configuration:
            raise TreasuryDecisionEvaluationError("At least one policy result or configuration is required")
        if any(result.status == "FAILED" for result in request.policy_results):
            raise RecommendationError("Blocking policy failed")
        review = any(result.status == "WARNING" for result in request.policy_results)
        config = self._coerce_config(request.configuration)
        if not config.enabled:
            raise DecisionConfigurationError("Decision configuration is disabled")
        if self._provider is not None:
            try:
                provider_recommendations = self._provider.get_recommendations(request)
            except Exception as exc:  # pragma: no cover - translation layer
                raise DecisionProviderError("Recommendation provider failed") from exc
            if provider_recommendations is None:
                raise DecisionProviderError("Recommendation provider returned no data")
            recommendations = self._dedupe_recommendations(provider_recommendations)
        else:
            recommendations = self._build_recommendations(request, config, review)
        self._ensure_no_conflicts(recommendations)
        groups = self._build_groups(recommendations)
        explanation = self._analytics.build_explanation(
            conclusion="Treasury decision generated",
            factors=[("total_recommendations", Decimal(len(recommendations)))],
        )
        summary = {
            "total_recommendations": len(recommendations),
            "priority_groups": len(groups),
            "highest_priority": groups[0].priority if groups else 0,
        }
        return TreasuryDecisionResult(
            portfolio_reference=request.portfolio_reference,
            recommendations=recommendations,
            recommendation_groups=groups,
            summary=summary,
            explanation=explanation,
            calculation_identifier=request.calculation_id or f"treasury-decision-{request.portfolio_reference}",
            correlation_id=request.correlation_id,
        )

    def _build_recommendations(self, request: TreasuryDecisionRequest, config: DecisionConfig, review: bool) -> tuple[Recommendation, ...]:
        base_score = self._score(request)
        recommendations: list[Recommendation] = []
        buy_threshold = config.recommendation_thresholds.get("buy", Decimal("0.65"))
        sell_threshold = config.recommendation_thresholds.get("sell", Decimal("0.3"))
        enabled_types = {item.lower() for item in config.enabled_recommendation_types}

        def is_enabled(recommendation_type: RecommendationType) -> bool:
            if not enabled_types:
                return True
            return recommendation_type.value.lower() in enabled_types or recommendation_type.name.lower() in enabled_types

        if is_enabled(RecommendationType.BUY) and request.relative_value_result is not None and base_score >= buy_threshold:
            recommendations.append(self._make_recommendation(request, RecommendationType.ACCUMULATE, base_score, PriorityLevel.HIGH, ImpactMetrics(liquidity_gap_impact=Decimal("0.20"), market_value_exposure=Decimal("100000")), (RecommendationType.SELL, RecommendationType.MONITOR)))
        if is_enabled(RecommendationType.SELL) and request.relative_value_result is not None and base_score <= sell_threshold:
            recommendations.append(self._make_recommendation(request, RecommendationType.SELL, base_score, PriorityLevel.MEDIUM, ImpactMetrics(liquidity_gap_impact=Decimal("-0.10"), market_value_exposure=Decimal("-50000")), (RecommendationType.BUY, RecommendationType.NO_ACTION)))
        if is_enabled(RecommendationType.USE_AS_COLLATERAL) and request.mil_result is not None and request.mil_result.status_counts.get("eligible"):
            recommendations.append(self._make_recommendation(request, RecommendationType.USE_AS_COLLATERAL, base_score, PriorityLevel.MEDIUM, ImpactMetrics(collateral_capacity_impact=Decimal("0.10"), mil_capacity_impact=Decimal("0.05")), (RecommendationType.DO_NOT_USE_AS_COLLATERAL,)))
        if is_enabled(RecommendationType.DO_NOT_USE_AS_COLLATERAL) and request.mil_result is not None and request.mil_result.status_counts.get("ineligible"):
            recommendations.append(self._make_recommendation(request, RecommendationType.DO_NOT_USE_AS_COLLATERAL, base_score, PriorityLevel.HIGH, ImpactMetrics(collateral_capacity_impact=Decimal("-0.10"), mil_capacity_impact=Decimal("-0.05")), (RecommendationType.USE_AS_COLLATERAL,)))
        if is_enabled(RecommendationType.REDUCE_CONCENTRATION) and self._has_concentration_breach(request, config):
            recommendations.append(self._make_recommendation(request, RecommendationType.REDUCE_CONCENTRATION, base_score, PriorityLevel.HIGH, ImpactMetrics(concentration_impact=Decimal("0.10")), (RecommendationType.NO_ACTION,)))
        if is_enabled(RecommendationType.IMPROVE_LIQUIDITY) and request.gap_result is not None and request.gap_result.net_gap < 0:
            recommendations.append(self._make_recommendation(request, RecommendationType.IMPROVE_LIQUIDITY, base_score, PriorityLevel.CRITICAL, ImpactMetrics(liquidity_gap_impact=Decimal("0.15")), (RecommendationType.NO_ACTION,)))
        if is_enabled(RecommendationType.LIMIT_EXCESS_RISK) and request.stress_result is not None and request.stress_result.summary.get("max_effect", Decimal("0")) > Decimal("0"):
            recommendations.append(self._make_recommendation(request, RecommendationType.LIMIT_EXCESS_RISK, base_score, PriorityLevel.HIGH, ImpactMetrics(stress_resilience_impact=Decimal("0.10")), (RecommendationType.NO_ACTION,)))
        if is_enabled(RecommendationType.HOLD) and request.relative_value_result is not None and request.relative_value_result.relative_value_score <= sell_threshold:
            recommendations.append(self._make_recommendation(request, RecommendationType.HOLD, base_score - Decimal("0.05"), PriorityLevel.MEDIUM, ImpactMetrics(policy_compliance_impact=Decimal("0.01")), (RecommendationType.BUY, RecommendationType.SELL)))
        if is_enabled(RecommendationType.NO_ACTION):
            recommendations.append(self._make_recommendation(request, RecommendationType.NO_ACTION, base_score, PriorityLevel.INFO, ImpactMetrics(), ()))
        if is_enabled(RecommendationType.MONITOR) and review:
            recommendations.append(self._make_recommendation(request, RecommendationType.MONITOR, base_score - Decimal("0.10"), PriorityLevel.LOW, ImpactMetrics(policy_compliance_impact=Decimal("0.01")), (RecommendationType.NO_ACTION,)))
        return self._dedupe_recommendations(tuple(recommendations))

    def _make_recommendation(self, request: TreasuryDecisionRequest, recommendation_type: RecommendationType, score: Decimal, priority: PriorityLevel, impact: ImpactMetrics, rejected: tuple[RecommendationType, ...]) -> Recommendation:
        return Recommendation(
            recommendation_id=f"{request.portfolio_reference}:{recommendation_type.value}:{request.decision_horizon}",
            instrument_id=request.portfolio_reference,
            recommendation=recommendation_type,
            priority=priority,
            score=score,
            confidence=self._confidence(recommendation_type),
            explanation=self._explanation(recommendation_type),
            rationale=self._rationale(recommendation_type),
            policy_summary={"status": "PASSED"},
            rejected_alternatives=rejected,
            expected_impact=impact,
            policy_references=tuple(ref.identifier for result in request.policy_results for ref in result.references),
            affected_assets=tuple(ref.identifier for result in request.policy_results for ref in result.references),
            upstream_calculation_references=self._upstream_references(request),
            assumptions=("Existing treasury engines were reused",),
            warnings=tuple(),
            correlation_id=request.correlation_id,
            calculation_id=request.calculation_id,
            decision_horizon=request.decision_horizon,
        )

    def _dedupe_recommendations(self, recommendations: tuple[Recommendation, ...]) -> tuple[Recommendation, ...]:
        seen: set[tuple[str, str]] = set()
        deduped: list[Recommendation] = []
        for recommendation in recommendations:
            key = (recommendation.recommendation_id, recommendation.recommendation.value)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(recommendation)
        return tuple(deduped)

    def _ensure_no_conflicts(self, recommendations: tuple[Recommendation, ...]) -> None:
        conflicting = [recommendation for recommendation in recommendations if recommendation.recommendation in {RecommendationType.BUY, RecommendationType.SELL}]
        if len({recommendation.recommendation for recommendation in conflicting}) > 1:
            raise ConflictingRecommendationError("Conflicting recommendations were generated")

    def _build_groups(self, recommendations: tuple[Recommendation, ...]) -> tuple[RecommendationGroup, ...]:
        ordered = sorted(recommendations, key=lambda item: (self._priority_value(item.priority), -item.score, item.recommendation_id))
        groups = [RecommendationGroup(group_name=priority.value, recommendations=tuple(item for item in ordered if item.priority == priority), priority=self._priority_value(priority)) for priority in PriorityLevel]
        return tuple(group for group in groups if group.recommendations)

    def _score(self, request: TreasuryDecisionRequest) -> Decimal:
        relative_value_score = Decimal("0")
        if request.relative_value_result is not None:
            relative_value_score = request.relative_value_result.relative_value_score
        stress_score = Decimal("0")
        if request.stress_result is not None:
            stress_score = Decimal(str(request.stress_result.summary.get("max_effect", Decimal("0"))))
        blended_score = (relative_value_score * Decimal("0.95")) + ((stress_score / Decimal("10000")) * Decimal("0.05"))
        return max(Decimal("0"), min(Decimal("1"), blended_score))

    def _priority_value(self, priority: PriorityLevel | None) -> int:
        if priority is None:
            raise PrioritizationError("Priority evidence is missing")
        try:
            return {PriorityLevel.CRITICAL: 5, PriorityLevel.HIGH: 4, PriorityLevel.MEDIUM: 3, PriorityLevel.LOW: 2, PriorityLevel.INFO: 1}[priority]
        except KeyError as exc:
            raise PrioritizationError("Priority could not be derived") from exc

    def _confidence(self, recommendation_type: RecommendationType) -> Decimal:
        return {RecommendationType.ACCUMULATE: Decimal("0.90"), RecommendationType.BUY: Decimal("0.90"), RecommendationType.SELL: Decimal("0.85"), RecommendationType.HOLD: Decimal("0.80"), RecommendationType.USE_AS_COLLATERAL: Decimal("0.82"), RecommendationType.DO_NOT_USE_AS_COLLATERAL: Decimal("0.81"), RecommendationType.REDUCE_CONCENTRATION: Decimal("0.83"), RecommendationType.IMPROVE_LIQUIDITY: Decimal("0.84"), RecommendationType.LIMIT_EXCESS_RISK: Decimal("0.81"), RecommendationType.MONITOR: Decimal("0.70"), RecommendationType.NO_ACTION: Decimal("0.65")}[recommendation_type]

    def _explanation(self, recommendation_type: RecommendationType) -> str:
        return {
            RecommendationType.ACCUMULATE: "Attractive relative value justified the recommendation.",
            RecommendationType.BUY: "Attractive relative value justified the recommendation.",
            RecommendationType.SELL: "Relative value was unattractive and the recommendation reduced risk.",
            RecommendationType.HOLD: "The profile was stable and required no immediate action.",
            RecommendationType.USE_AS_COLLATERAL: "MIL eligibility supported collateral use.",
            RecommendationType.DO_NOT_USE_AS_COLLATERAL: "MIL eligibility or encumbrance status did not support collateral use.",
            RecommendationType.REDUCE_CONCENTRATION: "Issuer concentration exceeded materiality thresholds.",
            RecommendationType.IMPROVE_LIQUIDITY: "Liquidity gap metrics warranted action.",
            RecommendationType.LIMIT_EXCESS_RISK: "Stress metrics called for risk mitigation.",
            RecommendationType.MONITOR: "The evidence was incomplete, so the recommendation is to monitor.",
            RecommendationType.NO_ACTION: "No material issue was identified.",
        }[recommendation_type]

    def _rationale(self, recommendation_type: RecommendationType) -> tuple[str, ...]:
        return {RecommendationType.ACCUMULATE: ("relative_value",), RecommendationType.BUY: ("relative_value",), RecommendationType.SELL: ("relative_value", "risk"), RecommendationType.HOLD: ("stability",), RecommendationType.USE_AS_COLLATERAL: ("mil_eligibility",), RecommendationType.DO_NOT_USE_AS_COLLATERAL: ("mil_ineligibility",), RecommendationType.REDUCE_CONCENTRATION: ("concentration",), RecommendationType.IMPROVE_LIQUIDITY: ("liquidity_gap",), RecommendationType.LIMIT_EXCESS_RISK: ("stress",), RecommendationType.MONITOR: ("partial_evidence",), RecommendationType.NO_ACTION: ("no_material_issue",)}[recommendation_type]

    def _upstream_references(self, request: TreasuryDecisionRequest) -> tuple[str, ...]:
        refs: list[str] = []
        if request.portfolio_result is not None:
            refs.append("portfolio")
        if request.pricing_result is not None:
            refs.append("pricing")
        if request.relative_value_result is not None:
            refs.append("relative_value")
        if request.hqla_result is not None:
            refs.append("hqla")
        if request.mil_result is not None:
            refs.append("mil")
        if request.cash_flow_result is not None:
            refs.append("cash_flow")
        if request.gap_result is not None:
            refs.append("gap")
        if request.stress_result is not None:
            refs.append("stress")
        return tuple(refs)

    def _has_concentration_breach(self, request: TreasuryDecisionRequest, config: DecisionConfig) -> bool:
        threshold = config.materiality_thresholds.get("concentration", Decimal("0.2"))
        concentration_ratio = getattr(request.portfolio_result, "concentration_ratio", None)
        if concentration_ratio is None:
            return False
        return Decimal(str(concentration_ratio)) > threshold

    def _coerce_config(self, config: Any) -> DecisionConfig:
        if isinstance(config, DecisionConfig):
            return config
        if isinstance(config, dict):
            return DecisionConfig.from_mapping(config)
        return DecisionConfig(policy_id="default", version="1.0", name="Default", enabled_recommendation_types=tuple(RecommendationType.__members__.keys()), recommendation_thresholds={"buy": Decimal("0.65"), "sell": Decimal("0.3")}, priority_thresholds={"warning": Decimal("0.5"), "blocking": Decimal("0.8")}, factor_weights={"relative_value": Decimal("0.8")}, materiality_thresholds={"concentration": Decimal("0.2")}, confidence_bands={"high": Decimal("0.8")})
