from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from aip.domain.liquidity.cashflow.models.behavioral_assumption import BehavioralAssumption

if TYPE_CHECKING:
    from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest


class BehavioralProvider(Protocol):
    """Protocol for providing behavioral assumptions for a projection request."""

    def get_behavioral_assumptions(self, request: ProjectionRequest) -> tuple[BehavioralAssumption, ...]:
        ...
