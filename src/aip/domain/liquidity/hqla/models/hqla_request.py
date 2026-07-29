from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aip.domain.relative_value.providers.hqla_eligibility_provider import (
        HQLAEligibilityProvider,
    )


@dataclass(frozen=True, slots=True)
class HQLARequest:
    """Immutable request for HQLA classification."""

    valuation_date: date
    instrument_id: str | None = None
    marketability_score: Decimal | None = None
    transferability_score: Decimal | None = None
    liquidity_quality_score: Decimal | None = None
    market_depth_score: Decimal | None = None
    price_availability_score: Decimal | None = None
    settlement_capability_score: Decimal | None = None
    encumbered: bool = False
    eligibility_provider: "HQLAEligibilityProvider | None" = None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    policies: tuple[object, ...] = ()
    configuration: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.valuation_date is None:
            raise ValueError("Valuation date is required")
