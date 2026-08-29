from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


ForecastStatus = Literal[
    "AVAILABLE",
    "FAILED",
    "INSUFFICIENT_DATA",
]


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricForecastWarning:
    """
    Warning producido durante la estimación del modelo definitivo.
    """

    warning_type: str
    message: str


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricProjectionPoint:
    """
    Punto de una trayectoria económica proyectada.

    horizon:
        Número de meses posteriores al forecast_origin.

    point_forecast:
        Pronóstico puntual.

    lower_bound / upper_bound:
        Intervalo de incertidumbre construido utilizando
        el error RMSE observado durante backtesting.
    """

    horizon: int
    forecast_origin: date
    target_period: date

    point_forecast: float

    lower_bound: float | None
    upper_bound: float | None

    confidence_level: float


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricForecastResult:
    """
    Resultado auditable del forecast definitivo de un indicador.
    """

    indicator_code: str

    status: ForecastStatus

    model_name: str | None
    model_family: str | None

    parameters: tuple[
        tuple[
            str,
            str,
        ],
        ...,
    ]

    forecast_origin: date | None
    historical_observations: int

    horizon_months: int
    confidence_level: float

    backtest_observations: int
    backtest_rmse: float | None
    backtest_mae: float | None
    backtest_bias: float | None

    points: tuple[
        EconometricProjectionPoint,
        ...,
    ]

    warnings: tuple[
        EconometricForecastWarning,
        ...,
    ]

    diagnostic: str | None = None

    @property
    def available(
        self,
    ) -> bool:
        return (
            self.status == "AVAILABLE"
            and bool(
                self.points
            )
        )

    def point_at_horizon(
        self,
        horizon: int,
    ) -> EconometricProjectionPoint | None:
        for point in self.points:
            if point.horizon == horizon:
                return point

        return None
