from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.liquidity.cashflow.models.behavioral_assumption import BehavioralAssumption

if TYPE_CHECKING:
    from aip.domain.liquidity.cashflow.providers.behavioral_provider import BehavioralProvider
    from aip.domain.liquidity.cashflow.providers.rollover_provider import RolloverProvider
    from aip.domain.liquidity.cashflow.providers.scenario_provider import ScenarioProvider


@dataclass(frozen=True, slots=True)
class ProjectionRequest:
    """Immutable request for a projection run."""

    valuation_date: date
    contractual_cashflows: tuple[CashFlow, ...] = ()
    behavioral_assumptions: tuple[BehavioralAssumption, ...] = ()
    scenario_name: str | None = None
    portfolio_reference: str | None = None
    business_unit: str | None = None
    currency: str | None = None
    product_type: str | None = None
    counterparty: str | None = None
    instrument_id: str | None = None
    projection_type: str | None = None
    behavioral_provider: BehavioralProvider | None = None
    scenario_provider: ScenarioProvider | None = None
    rollover_provider: RolloverProvider | None = None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    configuration: dict[str, Decimal | str | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.valuation_date is None:
            raise ValueError("Valuation date is required")
        if self.projection_type is not None and self.projection_type.strip().lower() == "scenario" and not self.scenario_name and self.scenario_provider is None:
            raise ValueError("Scenario context is required for scenario projection")
        if self.behavioral_assumptions is None:
            object.__setattr__(self, "behavioral_assumptions", ())
        elif isinstance(self.behavioral_assumptions, tuple):
            object.__setattr__(self, "behavioral_assumptions", self.behavioral_assumptions)
        else:
            object.__setattr__(self, "behavioral_assumptions", (self.behavioral_assumptions,))
