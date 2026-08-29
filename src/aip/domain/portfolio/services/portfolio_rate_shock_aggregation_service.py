from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from aip.domain.portfolio.services.portfolio_rate_shock_service import PortfolioRateShockService


@dataclass(frozen=True, slots=True)
class RateShockScenarioAggregate:
    """Resultado agregado para un shock paralelo de tasas."""

    shock_bp: int
    delta_eve_crc: Decimal
    shocked_market_value_crc: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioRateShockAggregateResult:
    """Resultado agregado de sensibilidad de tasa del portafolio."""

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


class PortfolioRateShockAggregationService:
    """Agrega sensibilidad del portafolio para shocks paralelos."""

    @classmethod
    def calculate(cls, positions: list[dict[str, Any]]) -> PortfolioRateShockAggregateResult:
        shocks = PortfolioRateShockService.SUPPORTED_SHOCKS_BP
        scenario_rows: dict[int, list[tuple[dict[str, Any], Any]]] = {}
        for shock_bp in shocks:
            scenario_rows[shock_bp] = [
                (position, PortfolioRateShockService.calculate(position, shock_bp))
                for position in positions
            ]

        reference_rows = scenario_rows[shocks[0]]
        total_market_value = sum(
            (result.base_market_value_crc for _, result in reference_rows), Decimal("0")
        )
        calculated_market_value = sum(
            (
                result.base_market_value_crc
                for _, result in reference_rows
                if result.status == "CALCULATED"
            ),
            Decimal("0"),
        )
        policy_excluded_market_value = sum(
            (
                result.base_market_value_crc
                for _, result in reference_rows
                if result.status == "POLICY_EXCLUDED"
            ),
            Decimal("0"),
        )
        data_unavailable_market_value = sum(
            (
                result.base_market_value_crc
                for _, result in reference_rows
                if result.status == "DATA_UNAVAILABLE"
            ),
            Decimal("0"),
        )
        coverage_percent = (
            calculated_market_value / total_market_value * Decimal("100")
            if total_market_value > 0
            else Decimal("0")
        )

        scenarios: list[RateShockScenarioAggregate] = []
        for shock_bp in shocks:
            rows = scenario_rows[shock_bp]
            delta_eve = sum(
                (
                    result.delta_eve_crc or Decimal("0")
                    for _, result in rows
                    if result.status == "CALCULATED"
                ),
                Decimal("0"),
            )
            shocked_market_value = sum(
                (
                    result.shocked_market_value_crc or Decimal("0")
                    for _, result in rows
                    if result.status == "CALCULATED"
                ),
                Decimal("0"),
            )
            scenarios.append(
                RateShockScenarioAggregate(
                    shock_bp=shock_bp,
                    delta_eve_crc=delta_eve,
                    shocked_market_value_crc=shocked_market_value,
                )
            )

        worst_scenario = min(scenarios, key=lambda item: item.delta_eve_crc) if scenarios else None
        return PortfolioRateShockAggregateResult(
            total_market_value_crc=total_market_value,
            calculated_market_value_crc=calculated_market_value,
            policy_excluded_market_value_crc=policy_excluded_market_value,
            data_unavailable_market_value_crc=data_unavailable_market_value,
            coverage_percent=coverage_percent,
            calculated_position_count=sum(
                1 for _, result in reference_rows if result.status == "CALCULATED"
            ),
            policy_excluded_position_count=sum(
                1 for _, result in reference_rows if result.status == "POLICY_EXCLUDED"
            ),
            data_unavailable_position_count=sum(
                1 for _, result in reference_rows if result.status == "DATA_UNAVAILABLE"
            ),
            scenarios=tuple(scenarios),
            worst_shock_bp=worst_scenario.shock_bp if worst_scenario is not None else None,
            worst_delta_eve_crc=(
                worst_scenario.delta_eve_crc if worst_scenario is not None else None
            ),
        )
