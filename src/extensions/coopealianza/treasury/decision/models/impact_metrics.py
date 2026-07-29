from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ImpactMetrics:
    """Immutable expected impact values for a recommendation."""

    liquidity_gap_impact: Decimal = Decimal("0")
    hqla_impact: Decimal = Decimal("0")
    mil_capacity_impact: Decimal = Decimal("0")
    collateral_capacity_impact: Decimal = Decimal("0")
    concentration_impact: Decimal = Decimal("0")
    stress_resilience_impact: Decimal = Decimal("0")
    market_value_exposure: Decimal = Decimal("0")
    policy_compliance_impact: Decimal = Decimal("0")
    assumptions: tuple[str, ...] = field(default_factory=tuple)
