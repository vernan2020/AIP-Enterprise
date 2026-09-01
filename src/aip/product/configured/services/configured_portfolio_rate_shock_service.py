from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.portfolio.services.portfolio_rate_shock_aggregation_service import (
    PortfolioRateShockAggregationService,
    RateShockScenarioAggregate,
)
from aip.product.configured.protocols import PortfolioDataProvider


@dataclass(frozen=True, slots=True)
class ConfiguredPortfolioRateShockResult:
    """Resultado configurado de sensibilidad del portafolio a tasas."""

    valuation_date: object
    total_market_value_crc: Decimal
    calculated_market_value_crc: Decimal
    policy_excluded_market_value_crc: Decimal
    data_unavailable_market_value_crc: Decimal
    coverage_percent: Decimal
    calculated_position_count: int
    policy_excluded_position_count: int
    data_unavailable_position_count: int
    scenarios: tuple[RateShockScenarioAggregate, ...]
    worst_shock_bp: int | None
    worst_delta_eve_crc: Decimal | None
    status: str


class ConfiguredPortfolioRateShockService:
    """Application service for configured portfolio parallel-rate sensitivity."""

    def __init__(self, portfolio_provider: PortfolioDataProvider) -> None:
        self._portfolio_provider = portfolio_provider

    def calculate(self) -> ConfiguredPortfolioRateShockResult:
        portfolio = self._portfolio_provider.get_portfolio()
        positions = [
            position for position in portfolio.get("positions", []) if isinstance(position, dict)
        ]
        aggregate = PortfolioRateShockAggregationService.calculate(positions)
        status = (
            "CALCULATED"
            if aggregate.data_unavailable_position_count == 0
            else "CALCULATED_WITH_DATA_GAPS"
        )
        return ConfiguredPortfolioRateShockResult(
            valuation_date=portfolio.get("valuation_date"),
            total_market_value_crc=aggregate.total_market_value_crc,
            calculated_market_value_crc=aggregate.calculated_market_value_crc,
            policy_excluded_market_value_crc=aggregate.policy_excluded_market_value_crc,
            data_unavailable_market_value_crc=aggregate.data_unavailable_market_value_crc,
            coverage_percent=aggregate.coverage_percent,
            calculated_position_count=aggregate.calculated_position_count,
            policy_excluded_position_count=aggregate.policy_excluded_position_count,
            data_unavailable_position_count=aggregate.data_unavailable_position_count,
            scenarios=aggregate.scenarios,
            worst_shock_bp=aggregate.worst_shock_bp,
            worst_delta_eve_crc=aggregate.worst_delta_eve_crc,
            status=status,
        )
