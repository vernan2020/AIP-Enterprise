from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..models.projection_request import ProjectionRequest


class ScenarioProvider(Protocol):
    """Protocol for providing the scenario name for a projection request."""

    def get_scenario(self, request: ProjectionRequest) -> str: ...
