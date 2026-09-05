from __future__ import annotations

from dataclasses import dataclass, field

from aip.ui.modules.price_risk.models.price_risk_row import (
    PriceRiskRow,
    RateShockViewRow,
    RiskChartPoint,
)


@dataclass(frozen=True, slots=True)
class PriceRiskViewModel:
    """Contrato inmutable de presentación para Riesgo de Precio y Tasa."""

    valuation_date: str = "-"

    # VeR
    var_crc: str = "-"
    var_percent: str = "-"
    eligible_market_value: str = "-"
    calculated_market_value: str = "-"
    policy_excluded_market_value: str = "-"
    history_excluded_market_value: str = "-"
    coverage_percent: str = "-"
    contribution_reconciliation_percent: str = "-"
    eligible_positions: int = 0
    policy_excluded_positions: int = 0
    calculated_titles: int = 0
    history_excluded_titles: int = 0
    required_prices: int = 0
    horizon_observations: int = 0
    scenario_count: int = 0
    var_rank: int = 0
    scenario_number: int = 0
    scenario_start_date: str = "-"
    scenario_end_date: str = "-"

    # DV01
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

    # Sensibilidad de tasas (aproximación por duración)
    rate_shock_coverage_percent: str = "-"
    rate_shock_status: str = "UNAVAILABLE"
    worst_shock: str = "-"
    worst_delta_eve: str = "-"
    rate_shock_rows: tuple[RateShockViewRow, ...] = field(default_factory=tuple)

    # Gráficos
    var_contribution_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    var_pareto_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    issuer_contribution_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    currency_market_value_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    dv01_bucket_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    dv01_currency_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)
    rate_shock_points: tuple[RiskChartPoint, ...] = field(default_factory=tuple)

    status: str = "UNAVAILABLE"
    diagnostic: str | None = None
    rows: tuple[PriceRiskRow, ...] = field(default_factory=tuple)
