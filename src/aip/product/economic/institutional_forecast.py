from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


InstitutionalForecastStatus = Literal[
    "APPROVED",
    "APPROVED_WITH_WARNINGS",
    "REVIEW_REQUIRED",
    "UNAVAILABLE",
]


@dataclass(frozen=True, slots=True)
class InstitutionalForecastPoint:
    """
    Punto mensual de la trayectoria institucional.
    """

    horizon: int
    forecast_origin: date
    target_period: date
    point_forecast: float
    lower_bound: float | None
    upper_bound: float | None
    confidence_level: float


@dataclass(frozen=True, slots=True)
class InstitutionalHorizonMetric:
    """
    Métrica OOS correspondiente a un horizonte
    de gobernanza.
    """

    horizon_months: int
    observations: int
    rmse: float | None
    mae: float | None
    bias: float | None
    naive_rmse: float | None
    relative_rmse: float | None


@dataclass(frozen=True, slots=True)
class InstitutionalForecastResult:
    """
    Forecast económico gobernado y auditable.

    approved_for_base_scenario indica si la trayectoria
    puede propagarse automáticamente al escenario base.

    REVIEW_REQUIRED conserva la trayectoria candidata,
    pero bloquea su utilización automática.
    """

    indicator_code: str
    status: InstitutionalForecastStatus

    statistical_model_name: str | None
    statistical_model_family: str | None

    governance_model_name: str | None
    governance_model_family: str | None

    forecast_origin: date | None
    last_observed_value: float | None
    historical_observations: int

    horizon_months: int
    confidence_level: float

    weighted_relative_score: float | None
    improvement_vs_naive: float | None
    materiality_threshold: float

    horizon_metrics: tuple[
        InstitutionalHorizonMetric,
        ...,
    ]

    dynamic_stability_status: str | None
    dynamic_stability_ratio: float | None

    points: tuple[
        InstitutionalForecastPoint,
        ...,
    ]

    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]

    data_as_of_date: date | None = None
    forecast_origin_period: date | None = None
    data_lag_days: int | None = None
    data_lag_months: int | None = None
    is_current_period: bool | None = None

    diagnostic: str | None = None

    @property
    def available(self) -> bool:
        return bool(
            self.points
        )

    @property
    def approved_for_base_scenario(
        self,
    ) -> bool:
        return (
            self.status
            in (
                "APPROVED",
                "APPROVED_WITH_WARNINGS",
            )
            and bool(
                self.points
            )
        )

    @property
    def requires_review(self) -> bool:
        return (
            self.status
            == "REVIEW_REQUIRED"
        )

    def point_at_horizon(
        self,
        horizon: int,
    ) -> InstitutionalForecastPoint | None:
        for point in self.points:
            if point.horizon == horizon:
                return point

        return None

    def metric_at_horizon(
        self,
        horizon: int,
    ) -> InstitutionalHorizonMetric | None:
        for metric in self.horizon_metrics:
            if metric.horizon_months == horizon:
                return metric

        return None
