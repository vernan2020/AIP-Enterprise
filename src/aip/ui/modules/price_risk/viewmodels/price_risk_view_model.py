from __future__ import annotations

from dataclasses import dataclass, field

from aip.ui.modules.price_risk.models.price_risk_row import PriceRiskRow, RiskChartPoint


@dataclass(frozen=True, slots=True)
class PriceRiskViewModel:
    """Immutable presentation contract for the institutional price-risk workspace."""

    valuation_date: str = "-"
    var_crc: str = "-"
    var_percent: str = "-"
    eligible_market_value: str = "-"
    coverage_percent: str = "-"
    eligible_positions: int = 0
    calculated_titles: int = 0
    required_prices: int = 0
    horizon_observations: int = 0
    scenario_count: int = 0
    var_rank: int = 0
    scenario_number: int = 0
    scenario_start_date: str = "-"
    scenario_end_date: str = "-"

    dv01_total: str = "-"
    dv01_crc: str = "-"
    dv01_usd: str = "-"
    dv01_coverage_percent: str = "-"
    dv01_eligible_market_value: str = "-"
    dv01_calculated_positions: int = 0
    dv01_excluded_positions: int = 0
    dv01_data_gaps: int = 0
    dv01_status: str = "UNAVAILABLE"

    dv01_bucket_lt1_value: str = "-"
    dv01_bucket_lt1_percent: str = "-"
    dv01_bucket_lt1_market_value: str = "-"
    dv01_bucket_lt1_positions: int = 0
    dv01_bucket_1to5_value: str = "-"
    dv01_bucket_1to5_percent: str = "-"
    dv01_bucket_1to5_market_value: str = "-"
    dv01_bucket_1to5_positions: int = 0
    dv01_bucket_gt5_value: str = "-"
    dv01_bucket_gt5_percent: str = "-"
    dv01_bucket_gt5_market_value: str = "-"
    dv01_bucket_gt5_positions: int = 0

    var_contribution_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    var_pareto_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    dv01_bucket_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    dv01_currency_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)

    status: str = "UNAVAILABLE"
    diagnostic: str | None = None
    rows: tuple[PriceRiskRow, ...] = field(default_factory=tuple)
