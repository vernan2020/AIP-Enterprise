from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

ModelFamily = Literal[
    "NAIVE",
    "DRIFT",
    "AR",
    "ARIMA",
]

ModelStatus = Literal[
    "AVAILABLE",
    "AVAILABLE_WITH_WARNINGS",
    "FAILED",
    "INSUFFICIENT_DATA",
]


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricForecastPoint:
    """
    Pronóstico generado durante backtesting.

    forecast_origin:
        último período disponible al momento de estimar.

    target_period:
        período que se intenta pronosticar.

    No puede utilizar observaciones posteriores a forecast_origin.
    """

    forecast_origin: date
    target_period: date

    actual: float
    forecast: float
    error: float

    absolute_error: float
    squared_error: float


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricModelMetrics:
    observations: int

    mae: float | None
    rmse: float | None
    mape: float | None

    bias: float | None



@dataclass(
    frozen=True,
    slots=True,
)
class EconometricEstimationWarning:
    """
    Advertencia producida durante una estimación rolling.

    Permite conservar trazabilidad del período concreto
    en que Statsmodels reportó una condición numérica
    relevante sin convertir automáticamente el modelo
    completo en fallido.
    """

    forecast_origin: date
    target_period: date

    warning_type: str
    message: str


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricModelCandidateResult:
    indicator_code: str

    model_name: str
    model_family: ModelFamily

    parameters: tuple[
        tuple[
            str,
            str,
        ],
        ...,
    ]

    status: ModelStatus

    metrics: EconometricModelMetrics

    forecasts: tuple[
        EconometricForecastPoint,
        ...,
    ]

    warnings: tuple[
        EconometricEstimationWarning,
        ...,
    ] = ()

    diagnostic: str | None = None

    @property
    def warning_count(
        self,
    ) -> int:
        return len(
            self.warnings
        )


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricModelSelectionResult:
    indicator_code: str

    candidates: tuple[
        EconometricModelCandidateResult,
        ...,
    ]

    selected_model_name: str | None
    selected_model_family: ModelFamily | None

    selection_metric: str

    diagnostic: str | None = None

    @property
    def selected_candidate(
        self,
    ) -> EconometricModelCandidateResult | None:
        if self.selected_model_name is None:
            return None

        for candidate in self.candidates:
            if (
                candidate.model_name
                == self.selected_model_name
            ):
                return candidate

        return None
