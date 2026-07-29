from __future__ import annotations

from abc import ABC, abstractmethod

from src.extensions.coopealianza.treasury.decision.models.decision_request import (
    TreasuryDecisionRequest,
)
from src.extensions.coopealianza.treasury.decision.models.recommendation import Recommendation


class RecommendationProvider(ABC):
    """Interface for external treasury recommendation providers."""

    @abstractmethod
    def get_recommendations(self, request: TreasuryDecisionRequest) -> tuple[Recommendation, ...]:
        raise NotImplementedError
