from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PriceRiskRow:
    """Fila inmutable de presentación para un título en el escenario VeR."""

    series: str
    issuer: str
    currency: str
    market_value: str
    pnl_scenario: str
    contribution_percent: str
    individual_var_percent: str
    real_observations: int
    synthetic_observations: int
    security_key: str


@dataclass(frozen=True, slots=True)
class RiskChartPoint:
    """Punto de presentación consumido por los gráficos de riesgo."""

    label: str
    value: Decimal
    secondary_value: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class RateShockViewRow:
    """Fila de presentación para sensibilidad paralela de tasas."""

    shock_bp: int
    shock_label: str
    delta_eve: str
    shocked_market_value: str
    delta_eve_crc: Decimal
