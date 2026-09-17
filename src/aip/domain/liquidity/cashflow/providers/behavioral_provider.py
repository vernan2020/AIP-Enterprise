from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ..models.behavioral_assumption import BehavioralAssumption

if TYPE_CHECKING:
    from ..models.projection_request import ProjectionRequest


class BehavioralProvider(Protocol):
    """Protocol for providing behavioral assumptions for a projection request."""

    def get_behavioral_assumptions(
        self, request: ProjectionRequest
    ) -> tuple[BehavioralAssumption, ...]: ...
