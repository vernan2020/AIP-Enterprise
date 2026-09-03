from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.portfolio.risk.historical_price_series import HistoricalPriceSeries


@dataclass(frozen=True, slots=True)
class PortfolioVaRPosition:
    """Position input to consolidated historical VeR."""

    security_key: str
    series: str
    issuer: str
    currency: str
    market_value_crc: Decimal
    price_series: HistoricalPriceSeries

    def __post_init__(self) -> None:
        if not self.security_key.strip():
            raise ValueError("security_key is required")
        if self.market_value_crc <= 0:
            raise ValueError("market_value_crc must be greater than zero")


@dataclass(frozen=True, slots=True)
class PortfolioVaRPositionResult:
    """Contribution of one title at the portfolio VeR scenario."""

    security_key: str
    series: str
    issuer: str
    currency: str
    market_value_crc: Decimal
    pnl_at_portfolio_var_scenario_crc: Decimal
    contribution_at_var_scenario_percent: Decimal
    individual_var_crc: Decimal
    individual_var_percent: Decimal
    real_price_observations: int
    synthetic_price_observations: int


@dataclass(frozen=True, slots=True)
class PortfolioHistoricalVaRResult:
    """Auditable consolidated 95% historical VeR result."""

    portfolio_market_value_crc: Decimal
    portfolio_var_crc: Decimal
    portfolio_var_percent: Decimal
    scenario_count: int
    horizon_observations: int
    confidence_level: Decimal
    percentile: Decimal
    var_rank: int
    var_scenario_number: int
    var_scenario_lagged_date: date
    var_scenario_date: date
    selected_scenario_pnl_crc: Decimal
    scenario_pnl_crc: tuple[Decimal, ...]
    positions: tuple[PortfolioVaRPositionResult, ...]

    @property
    def selected_scenario_rank(self) -> int:
        return self.var_rank

    @property
    def position_count(self) -> int:
        return len(self.positions)


class PortfolioHistoricalVaRService:
    """Institutional historical simulation VeR.

    Methodology: 521 prices, log returns, 21-observation horizon, exactly
    500 overlapping historical scenarios and the lower 5% tail. Scenario
    profit or loss is the accumulated log return multiplied by current market
    value, matching the institutional Coopealianza model. With 500 scenarios
    the selected observation is the 25th worst (1-based).
    """

    REQUIRED_PRICES = 521
    HORIZON_OBSERVATIONS = 21
    REQUIRED_SCENARIOS = 500
    CONFIDENCE_LEVEL = Decimal("0.95")
    PERCENTILE = Decimal("0.05")
    SELECTED_SCENARIO_RANK = 25

    @classmethod
    def calculate(
        cls,
        *,
        positions: tuple[PortfolioVaRPosition, ...],
    ) -> PortfolioHistoricalVaRResult:
        if not positions:
            raise ValueError("at least one position is required")

        common_dates = positions[0].price_series.dates
        if len(common_dates) != cls.REQUIRED_PRICES:
            raise ValueError(
                f"historical VeR requires exactly {cls.REQUIRED_PRICES} aligned prices"
            )

        for position in positions:
            if position.price_series.dates != common_dates:
                raise ValueError("all position price series must share the same market calendar")
            if position.price_series.observation_count != cls.REQUIRED_PRICES:
                raise ValueError(
                    f"{position.security_key} does not contain {cls.REQUIRED_PRICES} prices"
                )

        scenario_count = cls.REQUIRED_PRICES - cls.HORIZON_OBSERVATIONS
        if scenario_count != cls.REQUIRED_SCENARIOS:
            raise RuntimeError("institutional VeR scenario geometry is inconsistent")

        portfolio_scenarios = [Decimal("0") for _ in range(scenario_count)]
        position_scenarios: list[tuple[PortfolioVaRPosition, tuple[Decimal, ...]]] = []

        for position in positions:
            prices = position.price_series.prices
            numeric = [float(price) for price in prices]
            if any(price <= 0.0 or not math.isfinite(price) for price in numeric):
                raise ValueError(f"invalid price in historical series {position.security_key}")

            one_day_log_returns = [
                math.log(numeric[index] / numeric[index - 1]) for index in range(1, len(numeric))
            ]
            if len(one_day_log_returns) != 520:
                raise RuntimeError("expected 520 one-day returns from 521 prices")

            pnl_values: list[Decimal] = []
            rolling_sum = sum(one_day_log_returns[: cls.HORIZON_OBSERVATIONS])
            for scenario_index in range(scenario_count):
                if scenario_index > 0:
                    rolling_sum += one_day_log_returns[
                        scenario_index + cls.HORIZON_OBSERVATIONS - 1
                    ]
                    rolling_sum -= one_day_log_returns[scenario_index - 1]

                # Institutional reconciliation rule:
                #
                # The approved Coopealianza workbook applies the accumulated
                # 21-observation logarithmic return directly to current market
                # value. Converting it back to a simple return with
                # ``exp(rolling_sum) - 1`` understates losses and does not
                # reconcile with the regulatory VeR reference.
                log_return = rolling_sum
                pnl = position.market_value_crc * Decimal(str(log_return))
                pnl_values.append(pnl)
                portfolio_scenarios[scenario_index] += pnl

            position_scenarios.append((position, tuple(pnl_values)))

        ranked_indices = sorted(
            range(scenario_count),
            key=lambda index: portfolio_scenarios[index],
        )
        selected_index = ranked_indices[cls.SELECTED_SCENARIO_RANK - 1]
        selected = portfolio_scenarios[selected_index]
        portfolio_var = max(Decimal("0"), -selected)
        market_value = sum(
            (position.market_value_crc for position in positions),
            Decimal("0"),
        )
        var_percent = (
            portfolio_var / market_value * Decimal("100") if market_value > 0 else Decimal("0")
        )

        position_results: list[PortfolioVaRPositionResult] = []
        for position, scenarios in position_scenarios:
            pnl_at_selected = scenarios[selected_index]
            individual_selected = sorted(scenarios)[cls.SELECTED_SCENARIO_RANK - 1]
            individual_var = max(Decimal("0"), -individual_selected)
            individual_var_percent = (
                individual_var / position.market_value_crc * Decimal("100")
                if position.market_value_crc > 0
                else Decimal("0")
            )
            contribution = (
                pnl_at_selected / selected * Decimal("100") if selected != 0 else Decimal("0")
            )
            synthetic_count = position.price_series.synthetic_count
            position_results.append(
                PortfolioVaRPositionResult(
                    security_key=position.security_key,
                    series=position.series,
                    issuer=position.issuer,
                    currency=position.currency,
                    market_value_crc=position.market_value_crc,
                    pnl_at_portfolio_var_scenario_crc=pnl_at_selected,
                    contribution_at_var_scenario_percent=contribution,
                    individual_var_crc=individual_var,
                    individual_var_percent=individual_var_percent,
                    real_price_observations=(
                        position.price_series.observation_count - synthetic_count
                    ),
                    synthetic_price_observations=synthetic_count,
                )
            )

        return PortfolioHistoricalVaRResult(
            portfolio_market_value_crc=market_value,
            portfolio_var_crc=portfolio_var,
            portfolio_var_percent=var_percent,
            scenario_count=scenario_count,
            horizon_observations=cls.HORIZON_OBSERVATIONS,
            confidence_level=cls.CONFIDENCE_LEVEL,
            percentile=cls.PERCENTILE,
            var_rank=cls.SELECTED_SCENARIO_RANK,
            var_scenario_number=selected_index + 1,
            var_scenario_lagged_date=common_dates[selected_index],
            var_scenario_date=common_dates[selected_index + cls.HORIZON_OBSERVATIONS],
            selected_scenario_pnl_crc=selected,
            scenario_pnl_crc=tuple(portfolio_scenarios),
            positions=tuple(position_results),
        )
