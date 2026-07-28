from __future__ import annotations

from typing import Protocol

from aip.domain.liquidity.gap.models.gap_request import GapRequest


class LiquidityPolicyProvider(Protocol):
    """Protocol for resolving liquidity policy inputs for gap calculations."""

    def get_policy(self, request: GapRequest) -> dict[str, object]:
        ...
