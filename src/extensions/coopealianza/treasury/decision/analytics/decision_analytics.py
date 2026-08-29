from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from src.extensions.coopealianza.treasury.decision.exceptions import DecisionAnalyticsError
from src.extensions.coopealianza.treasury.decision.models.recommendation import Recommendation


class DecisionAnalytics:
    """Analytics helpers for treasury decision recommendations."""

    def build_explanation(
        self, conclusion: str, factors: list[tuple[str, Decimal | str]]
    ) -> Explanation:
        if not conclusion:
            raise DecisionAnalyticsError("Conclusion is required")
        builder = ExplanationBuilder()
        explanation_factors = [
            ExplanationFactor(
                name=name,
                value=(
                    Decimal(str(value))
                    if not isinstance(value, str) or self._is_decimal_string(str(value))
                    else Decimal("0")
                ),
                direction="positive",
                contribution=Decimal("1"),
                source_reference=None,
            )
            for name, value in factors
        ]
        return builder.build(conclusion, explanation_factors)

    @staticmethod
    def _is_decimal_string(value: str) -> bool:
        try:
            Decimal(value)
        except Exception:
            return False
        return True

    def summarize(self, recommendations: tuple[Recommendation, ...]) -> dict[str, Any]:
        if not recommendations:
            return {
                "count_by_type": {},
                "count_by_priority": {},
                "affected_market_value": Decimal("0"),
                "affected_issuers": 0,
                "expected_liquidity_improvement": Decimal("0"),
                "expected_collateral_improvement": Decimal("0"),
                "policy_failure_distribution": {},
                "confidence_distribution": {},
                "rejected_alternatives": 0,
                "no_action_ratio": Decimal("0"),
            }

        count_by_type = Counter(
            getattr(
                getattr(item, "recommendation", None),
                "value",
                str(getattr(item, "recommendation", item)),
            )
            for item in recommendations
        )
        count_by_priority = Counter(
            getattr(getattr(item, "priority", None), "value", str(getattr(item, "priority", item)))
            for item in recommendations
        )
        affected_market_value = sum(
            getattr(getattr(item, "expected_impact", None), "market_value_exposure", Decimal("0"))
            for item in recommendations
        )
        affected_issuers = len(
            {asset for item in recommendations for asset in getattr(item, "affected_assets", ())}
        )
        expected_liquidity_improvement = sum(
            getattr(getattr(item, "expected_impact", None), "liquidity_gap_impact", Decimal("0"))
            for item in recommendations
        )
        expected_collateral_improvement = sum(
            getattr(
                getattr(item, "expected_impact", None), "collateral_capacity_impact", Decimal("0")
            )
            for item in recommendations
        )
        policy_failure_distribution = Counter(
            str(
                getattr(getattr(item, "policy_summary", {}), "get", lambda *_args, **_kwargs: "")(
                    "status", ""
                )
            )
            for item in recommendations
        )
        confidence_distribution = Counter(
            str(getattr(item, "confidence", Decimal("0"))) for item in recommendations
        )
        rejected_alternatives = sum(
            len(getattr(item, "rejected_alternatives", ())) for item in recommendations
        )
        no_action_ratio = (
            Decimal("0")
            if not recommendations
            else Decimal(
                sum(
                    1
                    for item in recommendations
                    if str(
                        getattr(
                            getattr(item, "recommendation", None),
                            "value",
                            getattr(item, "recommendation", item),
                        )
                    ).upper()
                    == "NO_ACTION"
                )
            )
            / Decimal(len(recommendations))
        )
        return {
            "count_by_type": dict(count_by_type),
            "count_by_priority": dict(count_by_priority),
            "affected_market_value": affected_market_value,
            "affected_issuers": affected_issuers,
            "expected_liquidity_improvement": expected_liquidity_improvement,
            "expected_collateral_improvement": expected_collateral_improvement,
            "policy_failure_distribution": dict(policy_failure_distribution),
            "confidence_distribution": dict(confidence_distribution),
            "rejected_alternatives": rejected_alternatives,
            "no_action_ratio": no_action_ratio,
        }
