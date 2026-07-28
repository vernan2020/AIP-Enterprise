from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MilCapacityResult:
    total_market_value_evaluated: Decimal = Decimal("0")
    eligible_market_value: Decimal = Decimal("0")
    conditionally_eligible_market_value: Decimal = Decimal("0")
    ineligible_market_value: Decimal = Decimal("0")
    unknown_market_value: Decimal = Decimal("0")
    eligible_adjusted_collateral_value: Decimal = Decimal("0")
    conditional_adjusted_collateral_value: Decimal = Decimal("0")
    total_potential_collateral_capacity: Decimal = Decimal("0")
    capacity_by_issuer: dict[str, Decimal] = field(default_factory=dict)
    capacity_by_currency: dict[str, Decimal] = field(default_factory=dict)
    capacity_by_maturity_band: dict[str, Decimal] = field(default_factory=dict)
    capacity_by_classification: dict[str, Decimal] = field(default_factory=dict)
    encumbered_value: Decimal = Decimal("0")
    unavailable_value: Decimal = Decimal("0")
    excluded_classification_value: Decimal = Decimal("0")
