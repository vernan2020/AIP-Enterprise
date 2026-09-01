from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest


class ScenarioProvider(Protocol):
    """Protocol for providing the scenario name for a projection request."""

    def get_scenario(self, request: ProjectionRequest) -> str: ...
