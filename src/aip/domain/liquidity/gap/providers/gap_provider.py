from __future__ import annotations

from typing import Protocol

from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.gap.models.gap_request import GapRequest


class GapProvider(Protocol):
    """Protocol for providers that can resolve projection inputs for gaps."""

    def get_projection_request(self, request: GapRequest) -> ProjectionRequest: ...
