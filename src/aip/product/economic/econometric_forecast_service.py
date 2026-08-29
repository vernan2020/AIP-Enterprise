from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from statsmodels.tools.sm_exceptions import (
    ConvergenceWarning,
    EstimationWarning,
    SingularMatrixWarning,
)
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.arima.model import ARIMA

from aip.product.economic.econometric_dataset import (
    EconometricMonthlyDataset,
)
from aip.product.economic.econometric_diagnostics_service import (
    EconometricDiagnosticsService,
)
from aip.product.economic.econometric_forecast import (
    EconometricForecastResult,
    EconometricForecastWarning,
    EconometricProjectionPoint,
)
from aip.product.economic.econometric_model_selection import (
    EconometricModelCandidateResult,
)
from aip.product.economic.econometric_model_selection_service import (
    EconometricModelSelectionService,
)


@dataclass(
    frozen=True,
    slots=True,
)
class _SelectedSpecification:
    model_name: str
    family: str

    ar_lags: int | None = None

    arima_order: tuple[
        int,
        int,
        int,
    ] | None = None


class EconometricForecastService:
    """
    Motor institucional de forecast económico.

    Responsabilidades:
    - ejecutar la gobernanza pública de selección de modelos;
    - recuperar el modelo ganador;
    - reestimar dicho modelo utilizando toda la historia disponible;
    - producir una trayectoria multi-step;
    - construir bandas homogéneas de incertidumbre con RMSE OOS;
    - preservar warnings econométricos para auditoría.

    El servicio no:
    - modifica datos históricos;
    - imputa observaciones faltantes;
    - contiene lógica de UI;
    - sustituye la gobernanza de selección existente.
    """

    _SUPPORTED_INDICATORS = (
        "FX_SELL",
        "TPM",
        "TBP",
        "TRI_CRC_12M",
        "TRI_USD_12M",
        "INFLATION",
        "IMAE",
    )

    def __init__(
        self,
        *,
        model_selection_service: (
            EconometricModelSelectionService
            | None
        ) = None,
        confidence_level: float = 0.95,
        minimum_horizon: int = 1,
        maximum_horizon: int = 12,
    ) -> None:
        if not 0.50 < confidence_level < 1.0:
            raise ValueError(
                "confidence_level must be between 0.50 and 1.0"
            )

        if minimum_horizon < 1:
            raise ValueError(
                "minimum_horizon must be >= 1"
            )

        if maximum_horizon < minimum_horizon:
            raise ValueError(
                "maximum_horizon must be >= minimum_horizon"
            )

        self._model_selection_service = (
            model_selection_service
            or EconometricModelSelectionService()
        )

        self._confidence_level = (
            confidence_level
        )

        self._minimum_horizon = (
            minimum_horizon
        )

        self._maximum_horizon = (
            maximum_horizon
        )

        self._frame_builder = (
            EconometricDiagnosticsService()
        )

    def forecast(
        self,
        dataset: EconometricMonthlyDataset,
        indicator_code: str,
        *,
        horizon_months: int = 12,
    ) -> EconometricForecastResult:
        """
        Genera el forecast definitivo de un indicador.

        La selección se realiza exclusivamente mediante el servicio
        institucional de model selection.
        """

        code = (
            indicator_code
            .strip()
            .upper()
        )

        self._validate_horizon(
            horizon_months
        )

        if code not in self._SUPPORTED_INDICATORS:
            return self._failed_result(
                indicator_code=code,
                horizon_months=horizon_months,
                diagnostic=(
                    "Unsupported indicator"
                ),
            )

        series = (
            self._frame_builder
            .build_series(
                dataset,
                code,
            )
            .replace(
                [
                    np.inf,
                    -np.inf,
                ],
                np.nan,
            )
            .dropna()
            .astype(float)
        )

        if series.empty:
            return self._failed_result(
                indicator_code=code,
                horizon_months=horizon_months,
                diagnostic=(
                    "No historical observations available"
                ),
                status="INSUFFICIENT_DATA",
            )

        selection = (
            self._model_selection_service
            .select(
                dataset,
                code,
            )
        )

        selected = (
            selection.selected_candidate
        )

        if selected is None:
            return self._failed_result(
                indicator_code=code,
                horizon_months=horizon_months,
                diagnostic=(
                    selection.diagnostic
                    or "No model selected"
                ),
                historical_observations=len(
                    series
                ),
                forecast_origin=(
                    series.index[
                        -1
                    ].date()
                ),
            )

        specification = (
            self._specification_from_candidate(
                selected
            )
        )

        estimation_warnings: list[
            EconometricForecastWarning
        ] = []

        try:
            with warnings.catch_warnings(
                record=True
            ) as warning_records:
                warnings.simplefilter(
                    "error"
                )

                warnings.simplefilter(
                    "always",
                    SingularMatrixWarning,
                )

                warnings.simplefilter(
                    "always",
                    ConvergenceWarning,
                )

                warnings.simplefilter(
                    "always",
                    EstimationWarning,
                )

                forecasts = (
                    self._forecast_multi_step(
                        series=series,
                        specification=specification,
                        horizon_months=(
                            horizon_months
                        ),
                    )
                )

            for item in warning_records:
                category = (
                    item.category
                )

                if not issubclass(
                    category,
                    (
                        SingularMatrixWarning,
                        ConvergenceWarning,
                        EstimationWarning,
                    ),
                ):
                    continue

                estimation_warnings.append(
                    EconometricForecastWarning(
                        warning_type=(
                            category.__name__
                        ),
                        message=str(
                            item.message
                        ),
                    )
                )

        except (
            ValueError,
            TypeError,
            np.linalg.LinAlgError,
            RuntimeError,
        ) as exc:
            return self._failed_result(
                indicator_code=code,
                horizon_months=horizon_months,
                diagnostic=(
                    f"{type(exc).__name__}: {exc}"
                ),
                historical_observations=len(
                    series
                ),
                forecast_origin=(
                    series.index[
                        -1
                    ].date()
                ),
                model_name=(
                    selected.model_name
                ),
                model_family=(
                    selected.model_family
                ),
                parameters=(
                    selected.parameters
                ),
                warnings_result=tuple(
                    estimation_warnings
                ),
                candidate=selected,
            )

        if len(
            forecasts
        ) != horizon_months:
            return self._failed_result(
                indicator_code=code,
                horizon_months=horizon_months,
                diagnostic=(
                    "Forecast engine returned an unexpected "
                    "number of projection points"
                ),
                historical_observations=len(
                    series
                ),
                forecast_origin=(
                    series.index[
                        -1
                    ].date()
                ),
                model_name=(
                    selected.model_name
                ),
                model_family=(
                    selected.model_family
                ),
                parameters=(
                    selected.parameters
                ),
                warnings_result=tuple(
                    estimation_warnings
                ),
                candidate=selected,
            )

        if not all(
            math.isfinite(
                value
            )
            for value in forecasts
        ):
            return self._failed_result(
                indicator_code=code,
                horizon_months=horizon_months,
                diagnostic=(
                    "Forecast contains non-finite values"
                ),
                historical_observations=len(
                    series
                ),
                forecast_origin=(
                    series.index[
                        -1
                    ].date()
                ),
                model_name=(
                    selected.model_name
                ),
                model_family=(
                    selected.model_family
                ),
                parameters=(
                    selected.parameters
                ),
                warnings_result=tuple(
                    estimation_warnings
                ),
                candidate=selected,
            )

        forecast_origin = (
            series.index[
                -1
            ]
        )

        rmse = (
            selected.metrics.rmse
        )

        z_score = (
            self._normal_quantile(
                self._confidence_level
            )
        )

        points: list[
            EconometricProjectionPoint
        ] = []

        for index, forecast_value in enumerate(
            forecasts,
            start=1,
        ):
            target_period = (
                forecast_origin
                + MonthEnd(
                    index
                )
            )

            lower_bound: float | None = None
            upper_bound: float | None = None

            if (
                rmse is not None
                and math.isfinite(
                    float(
                        rmse
                    )
                )
                and rmse >= 0.0
            ):
                interval_scale = (
                    float(
                        rmse
                    )
                    * math.sqrt(
                        index
                    )
                )

                margin = (
                    z_score
                    * interval_scale
                )

                lower_bound = (
                    float(
                        forecast_value
                    )
                    - margin
                )

                upper_bound = (
                    float(
                        forecast_value
                    )
                    + margin
                )

            points.append(
                EconometricProjectionPoint(
                    horizon=index,
                    forecast_origin=(
                        forecast_origin.date()
                    ),
                    target_period=(
                        target_period.date()
                    ),
                    point_forecast=float(
                        forecast_value
                    ),
                    lower_bound=(
                        lower_bound
                    ),
                    upper_bound=(
                        upper_bound
                    ),
                    confidence_level=(
                        self._confidence_level
                    ),
                )
            )

        diagnostic_parts: list[
            str
        ] = []

        if selection.diagnostic:
            diagnostic_parts.append(
                selection.diagnostic
            )

        if estimation_warnings:
            diagnostic_parts.append(
                "Final estimation produced "
                f"{len(estimation_warnings)} "
                "governed warning(s)"
            )

        return EconometricForecastResult(
            indicator_code=code,
            status="AVAILABLE",
            model_name=(
                selected.model_name
            ),
            model_family=(
                selected.model_family
            ),
            parameters=(
                selected.parameters
            ),
            forecast_origin=(
                forecast_origin.date()
            ),
            historical_observations=len(
                series
            ),
            horizon_months=(
                horizon_months
            ),
            confidence_level=(
                self._confidence_level
            ),
            backtest_observations=(
                selected.metrics.observations
            ),
            backtest_rmse=(
                selected.metrics.rmse
            ),
            backtest_mae=(
                selected.metrics.mae
            ),
            backtest_bias=(
                selected.metrics.bias
            ),
            points=tuple(
                points
            ),
            warnings=tuple(
                estimation_warnings
            ),
            diagnostic=(
                "; ".join(
                    diagnostic_parts
                )
                if diagnostic_parts
                else None
            ),
        )

    def forecast_all(
        self,
        dataset: EconometricMonthlyDataset,
        *,
        horizon_months: int = 12,
    ) -> tuple[
        EconometricForecastResult,
        ...,
    ]:
        self._validate_horizon(
            horizon_months
        )

        return tuple(
            self.forecast(
                dataset,
                code,
                horizon_months=(
                    horizon_months
                ),
            )
            for code
            in self._SUPPORTED_INDICATORS
        )

    @staticmethod
    def _specification_from_candidate(
        candidate: EconometricModelCandidateResult,
    ) -> _SelectedSpecification:
        parameters = {
            key: value
            for key, value
            in candidate.parameters
        }

        family = (
            candidate.model_family
        )

        if family == "NAIVE":
            return _SelectedSpecification(
                model_name=(
                    candidate.model_name
                ),
                family=family,
            )

        if family == "DRIFT":
            return _SelectedSpecification(
                model_name=(
                    candidate.model_name
                ),
                family=family,
            )

        if family == "AR":
            raw_lags = (
                parameters.get(
                    "lags"
                )
                or parameters.get(
                    "ar_lags"
                )
            )

            if raw_lags is None:
                raw_lags = (
                    EconometricForecastService
                    ._infer_ar_lags_from_name(
                        candidate.model_name
                    )
                )

            try:
                lags = int(
                    raw_lags
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Invalid AR lag configuration"
                ) from exc

            return _SelectedSpecification(
                model_name=(
                    candidate.model_name
                ),
                family=family,
                ar_lags=lags,
            )

        if family == "ARIMA":
            raw_order = (
                parameters.get(
                    "order"
                )
            )

            if raw_order is None:
                order = (
                    EconometricForecastService
                    ._infer_arima_order_from_name(
                        candidate.model_name
                    )
                )

            else:
                order = (
                    EconometricForecastService
                    ._parse_arima_order(
                        raw_order
                    )
                )

            return _SelectedSpecification(
                model_name=(
                    candidate.model_name
                ),
                family=family,
                arima_order=order,
            )

        raise ValueError(
            "Unsupported selected model family: "
            f"{family}"
        )

    @staticmethod
    def _forecast_multi_step(
        *,
        series: pd.Series,
        specification: _SelectedSpecification,
        horizon_months: int,
    ) -> tuple[
        float,
        ...,
    ]:
        values = (
            series.to_numpy(
                dtype=float
            )
        )

        if specification.family == "NAIVE":
            last_value = float(
                values[
                    -1
                ]
            )

            return tuple(
                last_value
                for _ in range(
                    horizon_months
                )
            )

        if specification.family == "DRIFT":
            if len(
                values
            ) < 2:
                raise ValueError(
                    "DRIFT requires at least two observations"
                )

            drift = (
                values[
                    -1
                ]
                - values[
                    0
                ]
            ) / (
                len(
                    values
                )
                - 1
            )

            last_value = float(
                values[
                    -1
                ]
            )

            return tuple(
                float(
                    last_value
                    + drift
                    * horizon
                )
                for horizon in range(
                    1,
                    horizon_months
                    + 1,
                )
            )

        if specification.family == "AR":
            if specification.ar_lags is None:
                raise ValueError(
                    "AR lag configuration missing"
                )

            model = AutoReg(
                values,
                lags=(
                    specification.ar_lags
                ),
                trend="ct",
            )

            fitted = model.fit()

            forecast = fitted.predict(
                start=len(
                    values
                ),
                end=(
                    len(
                        values
                    )
                    + horizon_months
                    - 1
                ),
                dynamic=False,
            )

            return tuple(
                float(
                    value
                )
                for value
                in np.asarray(
                    forecast,
                    dtype=float,
                )
            )

        if specification.family == "ARIMA":
            if specification.arima_order is None:
                raise ValueError(
                    "ARIMA order missing"
                )

            model = ARIMA(
                values,
                order=(
                    specification.arima_order
                ),
                trend=(
                    "t"
                    if (
                        specification
                        .arima_order[
                            1
                        ]
                        > 0
                    )
                    else "ct"
                ),
            )

            fitted = model.fit()

            forecast = fitted.forecast(
                steps=(
                    horizon_months
                )
            )

            return tuple(
                float(
                    value
                )
                for value
                in np.asarray(
                    forecast,
                    dtype=float,
                )
            )

        raise ValueError(
            "Unsupported model family: "
            f"{specification.family}"
        )

    @staticmethod
    def _infer_ar_lags_from_name(
        model_name: str,
    ) -> str:
        normalized = (
            model_name
            .strip()
            .upper()
        )

        if normalized.startswith(
            "AR("
        ) and normalized.endswith(
            ")"
        ):
            return normalized[
                3:-1
            ]

        raise ValueError(
            "AR lag configuration missing "
            f"for {model_name}"
        )

    @staticmethod
    def _infer_arima_order_from_name(
        model_name: str,
    ) -> tuple[
        int,
        int,
        int,
    ]:
        normalized = (
            model_name
            .strip()
            .upper()
        )

        if not (
            normalized.startswith(
                "ARIMA("
            )
            and normalized.endswith(
                ")"
            )
        ):
            raise ValueError(
                "ARIMA order configuration missing "
                f"for {model_name}"
            )

        return (
            EconometricForecastService
            ._parse_arima_order(
                normalized[
                    6:-1
                ]
            )
        )

    @staticmethod
    def _parse_arima_order(
        raw_order: Any,
    ) -> tuple[
        int,
        int,
        int,
    ]:
        if isinstance(
            raw_order,
            tuple,
        ):
            parts = list(
                raw_order
            )

        elif isinstance(
            raw_order,
            list,
        ):
            parts = raw_order

        else:
            normalized = (
                str(
                    raw_order
                )
                .strip()
                .replace(
                    "(",
                    "",
                )
                .replace(
                    ")",
                    "",
                )
                .replace(
                    " ",
                    "",
                )
            )

            parts = (
                normalized
                .split(
                    ","
                )
            )

        if len(
            parts
        ) != 3:
            raise ValueError(
                "ARIMA order must contain p,d,q"
            )

        try:
            order = tuple(
                int(
                    value
                )
                for value
                in parts
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Invalid ARIMA order"
            ) from exc

        if any(
            value < 0
            for value
            in order
        ):
            raise ValueError(
                "ARIMA order values must be non-negative"
            )

        return (
            order[
                0
            ],
            order[
                1
            ],
            order[
                2
            ],
        )

    @staticmethod
    def _normal_quantile(
        confidence_level: float,
    ) -> float:
        """
        Cuantil normal bilateral sin introducir dependencia adicional
        de scipy en el dominio del servicio.

        Los niveles institucionales habituales quedan explícitos.
        """

        known = {
            0.90: 1.6448536269514722,
            0.95: 1.959963984540054,
            0.99: 2.5758293035489004,
        }

        for level, value in known.items():
            if math.isclose(
                confidence_level,
                level,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                return value

        from statistics import NormalDist

        return float(
            NormalDist()
            .inv_cdf(
                0.5
                + confidence_level
                / 2.0
            )
        )

    def _validate_horizon(
        self,
        horizon_months: int,
    ) -> None:
        if not (
            self._minimum_horizon
            <= horizon_months
            <= self._maximum_horizon
        ):
            raise ValueError(
                "horizon_months must be between "
                f"{self._minimum_horizon} and "
                f"{self._maximum_horizon}"
            )

    def _failed_result(
        self,
        *,
        indicator_code: str,
        horizon_months: int,
        diagnostic: str,
        status: str = "FAILED",
        historical_observations: int = 0,
        forecast_origin=None,
        model_name: str | None = None,
        model_family: str | None = None,
        parameters: tuple[
            tuple[
                str,
                str,
            ],
            ...,
        ] = (),
        warnings_result: tuple[
            EconometricForecastWarning,
            ...,
        ] = (),
        candidate: (
            EconometricModelCandidateResult
            | None
        ) = None,
    ) -> EconometricForecastResult:
        return EconometricForecastResult(
            indicator_code=(
                indicator_code
            ),
            status=status,
            model_name=model_name,
            model_family=(
                model_family
            ),
            parameters=parameters,
            forecast_origin=(
                forecast_origin
            ),
            historical_observations=(
                historical_observations
            ),
            horizon_months=(
                horizon_months
            ),
            confidence_level=(
                self._confidence_level
            ),
            backtest_observations=(
                candidate.metrics.observations
                if candidate is not None
                else 0
            ),
            backtest_rmse=(
                candidate.metrics.rmse
                if candidate is not None
                else None
            ),
            backtest_mae=(
                candidate.metrics.mae
                if candidate is not None
                else None
            ),
            backtest_bias=(
                candidate.metrics.bias
                if candidate is not None
                else None
            ),
            points=(),
            warnings=(
                warnings_result
            ),
            diagnostic=(
                diagnostic
            ),
        )
