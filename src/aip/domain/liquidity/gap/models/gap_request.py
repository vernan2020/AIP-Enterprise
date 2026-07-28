from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest

if TYPE_CHECKING:
    from aip.domain.liquidity.gap.providers.exchange_rate_policy_provider import ExchangeRatePolicyProvider
    from aip.domain.liquidity.gap.providers.gap_provider import GapProvider
    from aip.domain.liquidity.gap.providers.liquidity_policy_provider import LiquidityPolicyProvider


@dataclass(frozen=True, slots=True)
class GapRequest:
    """Immutable request for a liquidity gap run."""

    valuation_date: date
    cashflow_request: ProjectionRequest | None = None
    gap_type: str | None = None
    currency: str | None = None
    gap_provider: GapProvider | None = None
    liquidity_policy_provider: LiquidityPolicyProvider | None = None
    exchange_rate_policy_provider: ExchangeRatePolicyProvider | None = None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    configuration: dict[str, Decimal | str | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.valuation_date is None:
            raise ValueError("Valuation date is required")
