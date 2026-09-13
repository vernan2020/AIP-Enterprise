from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

AdvancedForecastStatus = Literal[
    "AVAILABLE",
    "AVAILABLE_WITH_WARNINGS",
    "INSUFFICIENT_DATA",
    "FAILED",
]

ModelResultStatus = Literal[
    "AVAILABLE",
    "AVAILABLE_WITH_WARNINGS",
    "UNAVAILABLE",
    "INSUFFICIENT_DATA",
    "FAILED",
]


@dataclass(frozen=True, slots=True)
class MultiHorizonMetric:
    horizon_months: int
    observations: int
    rmse: float | None
    mae: float | None
    bias: float | None
    directional_accuracy: float | None
    relative_rmse_vs_naive: float | None = None


@dataclass(frozen=True, slots=True)
class MacroModelBacktestResult:
    model_name: str
    model_family: str
    status: ModelResultStatus
    metrics: tuple[MultiHorizonMetric, ...] = field(default_factory=tuple)
    weighted_relative_score: float | None = None
    improvement_vs_naive: float | None = None
    warning_count: int = 0
    failure_count: int = 0
    diagnostic: str | None = None

    @property
    def available(self) -> bool:
        return self.status in {"AVAILABLE", "AVAILABLE_WITH_WARNINGS"}

    def metric_for_horizon(self, horizon_months: int) -> MultiHorizonMetric | None:
        return next(
            (item for item in self.metrics if item.horizon_months == horizon_months),
            None,
        )


@dataclass(frozen=True, slots=True)
class EnsembleModelWeight:
    model_name: str
    model_family: str
    weight: float
    weighted_relative_score: float


@dataclass(frozen=True, slots=True)
class AdvancedForecastPoint:
    horizon_months: int
    forecast_origin: date
    target_period: date
    point_forecast: float
    lower_80: float | None
    upper_80: float | None
    lower_95: float | None
    upper_95: float | None


@dataclass(frozen=True, slots=True)
class AdvancedIndicatorForecastResult:
    indicator_code: str
    status: AdvancedForecastStatus
    forecast_origin: date | None
    historical_observations: int
    champion_model_name: str | None
    champion_model_family: str | None
    model_results: tuple[MacroModelBacktestResult, ...] = field(default_factory=tuple)
    ensemble_weights: tuple[EnsembleModelWeight, ...] = field(default_factory=tuple)
    forecast_points: tuple[AdvancedForecastPoint, ...] = field(default_factory=tuple)
    confidence_score: float | None = None
    diagnostic: str | None = None

    @property
    def available(self) -> bool:
        return self.status in {"AVAILABLE", "AVAILABLE_WITH_WARNINGS"} and bool(
            self.forecast_points
        )

    def point_at_horizon(self, horizon_months: int) -> AdvancedForecastPoint | None:
        return next(
            (item for item in self.forecast_points if item.horizon_months == horizon_months),
            None,
        )
