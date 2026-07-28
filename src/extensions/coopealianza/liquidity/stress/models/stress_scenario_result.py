from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class StressScenarioResult:
    """Outcome for one liquidity stress scenario."""

    scenario_name: str
    scenario_type: str
    severity: Decimal
    stressed_gap: Decimal
    stressed_outflow: Decimal
    stressed_inflow: Decimal
    effect: Decimal
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    stressed_parameters: dict[str, Decimal] = field(default_factory=dict)
    policy_references: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    affected_assets: tuple[str, ...] = field(default_factory=tuple)
    affected_buckets: tuple[str, ...] = field(default_factory=tuple)
    calculation_identifier: str = ""
