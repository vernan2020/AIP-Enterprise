from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from aip.ui.modules.price_risk.models.price_risk_row import RiskChartPoint


@dataclass(frozen=True, slots=True)
class PriceRiskSimulationSecurityOption:
    """Presentation-safe security option for the portfolio simulator."""

    security_key: str
    series: str
    issuer: str
    currency: str
    source: str
    in_portfolio: bool
    current_market_value_crc: Decimal
    current_market_value: str
    market_price: str
    market_yield: str
    display_text: str


@dataclass(frozen=True, slots=True)
class PriceRiskSimulationAppliedTradeRow:
    """One applied hypothetical transaction shown in simulation results."""

    action: str
    series: str
    issuer: str
    currency: str
    market_value: str
    source: str


@dataclass(frozen=True, slots=True)
class PriceRiskSimulationViewModel:
    """Immutable base-versus-simulated VeR presentation contract."""

    status: str = "PENDING"
    valuation_date: str = "-"

    base_var: str = "-"
    simulated_var: str = "-"
    delta_var: str = "-"
    relative_var_change: str = "-"

    base_var_percent: str = "-"
    simulated_var_percent: str = "-"
    delta_var_percent_points: str = "-"

    base_market_value: str = "-"
    simulated_market_value: str = "-"
    delta_market_value: str = "-"

    base_scenario: str = "-"
    simulated_scenario: str = "-"

    comparison_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    trades: tuple[PriceRiskSimulationAppliedTradeRow, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
