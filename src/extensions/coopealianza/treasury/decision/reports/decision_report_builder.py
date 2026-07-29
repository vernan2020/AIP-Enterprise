from __future__ import annotations

from typing import Any

from src.extensions.coopealianza.treasury.decision.exceptions import DecisionReportError
from src.extensions.coopealianza.treasury.decision.models.decision_request import TreasuryDecisionRequest
from src.extensions.coopealianza.treasury.decision.models.decision_result import TreasuryDecisionResult


class DecisionReportBuilder:
    """Build a serializable report payload from a decision result."""

    def build(self, request: TreasuryDecisionRequest, result: TreasuryDecisionResult) -> dict[str, Any]:
        if not request.portfolio_reference:
            raise DecisionReportError("Portfolio reference is required")
        if not result.recommendations:
            raise DecisionReportError("Decision result has no recommendations")
        return {
            "portfolio_reference": request.portfolio_reference,
            "recommendations": [
                {
                    "recommendation": item.recommendation.value,
                    "priority": item.priority.value,
                    "score": str(item.score),
                    "confidence": str(item.confidence),
                }
                for item in result.recommendations
            ],
            "summary": result.summary,
        }
