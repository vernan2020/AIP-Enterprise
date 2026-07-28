from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest


class RolloverProvider(Protocol):
    """Protocol for providing rollover rates for a projection request."""

    def get_rollover_rate(self, request: ProjectionRequest) -> Decimal:
        ...
