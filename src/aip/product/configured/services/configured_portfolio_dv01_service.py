from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.portfolio.services.portfolio_dv01_aggregation_service import (
    DV01AggregateRow,
    PortfolioDV01AggregationService,
)
from aip.product.configured.protocols import PortfolioDataProvider


@dataclass(frozen=True, slots=True)
class ConfiguredPortfolioDV01Result:
    valuation_date: object
    total_market_value_crc: Decimal
    calculated_market_value_crc: Decimal
    policy_excluded_market_value_crc: Decimal
    data_unavailable_market_value_crc: Decimal
    coverage_percent: Decimal
    total_dv01_crc: Decimal
    dv01_crc_currency: Decimal
    dv01_usd_currency: Decimal
    calculated_position_count: int
    policy_excluded_position_count: int
    data_unavailable_position_count: int
    by_currency: tuple[DV01AggregateRow, ...]
    by_issuer: tuple[DV01AggregateRow, ...]
    by_product: tuple[DV01AggregateRow, ...]
    by_bucket: tuple[DV01AggregateRow, ...]
    status: str


class ConfiguredPortfolioDV01Service:
    """Application service for institutional portfolio DV01."""

    def __init__(self, portfolio_provider: PortfolioDataProvider) -> None:
        self._portfolio_provider = portfolio_provider

    def calculate(self) -> ConfiguredPortfolioDV01Result:
        portfolio = self._portfolio_provider.get_portfolio()
        positions = [
            position for position in portfolio.get("positions", []) if isinstance(position, dict)
        ]
        raw_valuation_date = portfolio.get("valuation_date")
        if isinstance(raw_valuation_date, date):
            valuation_date = raw_valuation_date
        elif isinstance(raw_valuation_date, str):
            valuation_date = date.fromisoformat(raw_valuation_date[:10])
        else:
            raise ValueError("Portfolio valuation date is unavailable for DV01 bucket aggregation")

        aggregate = PortfolioDV01AggregationService.calculate(
            positions,
            valuation_date=valuation_date,
        )
        dv01_crc_currency = Decimal("0")
        dv01_usd_currency = Decimal("0")
        for row in aggregate.by_currency:
            key = row.key.strip().casefold()
            if key in {"crc", "colon", "colones", "mn"}:
                dv01_crc_currency += row.dv01_crc
            elif key in {"dolar", "dólar", "usd", "me"}:
                dv01_usd_currency += row.dv01_crc

        status = (
            "CALCULATED"
            if aggregate.data_unavailable_position_count == 0
            else "CALCULATED_WITH_DATA_GAPS"
        )
        return ConfiguredPortfolioDV01Result(
            valuation_date=portfolio.get("valuation_date"),
            total_market_value_crc=aggregate.total_market_value_crc,
            calculated_market_value_crc=aggregate.calculated_market_value_crc,
            policy_excluded_market_value_crc=aggregate.policy_excluded_market_value_crc,
            data_unavailable_market_value_crc=aggregate.data_unavailable_market_value_crc,
            coverage_percent=aggregate.coverage_percent,
            total_dv01_crc=aggregate.total_dv01_crc,
            dv01_crc_currency=dv01_crc_currency,
            dv01_usd_currency=dv01_usd_currency,
            calculated_position_count=aggregate.calculated_position_count,
            policy_excluded_position_count=aggregate.policy_excluded_position_count,
            data_unavailable_position_count=aggregate.data_unavailable_position_count,
            by_currency=aggregate.by_currency,
            by_issuer=aggregate.by_issuer,
            by_product=aggregate.by_product,
            by_bucket=aggregate.by_bucket,
            status=status,
        )
