from __future__ import annotations

from decimal import Decimal

from aip.domain.relative_value.enums.recommendation_type import RecommendationType
from aip.domain.relative_value.exceptions import RecommendationError
from aip.domain.relative_value.models.recommendation import Recommendation


class RecommendationEngine:
    """Derive recommendations from score and policy inputs."""

    def recommend(
        self,
        *,
        score: Decimal,
        policy_summary: dict[str, object],
        thresholds: dict[str, Decimal],
        policy_result: Recommendation | None,
    ) -> Recommendation:
        status = str(policy_summary.get("status", "PASSED"))
        if status == "FAILED":
            raise RecommendationError("Blocking policy failed")
        if status == "WARNING":
            return Recommendation(
                instrument_id="",
                recommendation=RecommendationType.REVIEW,
                score=score,
                confidence=Decimal("0.3"),
                explanation="Warning policy requires review",
                policy_summary=policy_summary,
            )
        if policy_result is not None and policy_result.policy_summary.get("blocking"):
            raise RecommendationError("Blocking policy failed")
        if policy_result is not None and policy_result.policy_summary.get("disabled"):
            return Recommendation(
                "",
                RecommendationType.HOLD,
                score,
                Decimal("0.5"),
                "Disabled policy",
                policy_summary,
            )
        if policy_result is not None and policy_result.policy_summary.get("not_applicable"):
            return Recommendation(
                "",
                RecommendationType.HOLD,
                score,
                Decimal("0.5"),
                "Policy not applicable",
                policy_summary,
            )
        buy_threshold = thresholds.get("buy", Decimal("0.8"))
        accumulate_threshold = thresholds.get("accumulate", Decimal("0.65"))
        if score >= buy_threshold:
            recommendation = RecommendationType.BUY
        elif score >= accumulate_threshold:
            recommendation = RecommendationType.ACCUMULATE
        elif score >= Decimal("0.3"):
            recommendation = RecommendationType.HOLD
        elif score >= Decimal("0.1"):
            recommendation = RecommendationType.REDUCE
        else:
            recommendation = RecommendationType.SELL
        return Recommendation(
            "", recommendation, score, Decimal("0.8"), "Score-based recommendation", policy_summary
        )
