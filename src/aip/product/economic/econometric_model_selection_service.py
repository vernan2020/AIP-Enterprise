from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
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
from aip.product.economic.econometric_model_selection import (
    EconometricEstimationWarning,
    EconometricForecastPoint,
    EconometricModelCandidateResult,
    EconometricModelMetrics,
    EconometricModelSelectionResult,
)


@dataclass(
    frozen=True,
    slots=True,
)
class _CandidateSpecification:
    name: str
    family: str

    ar_lags: int | None = None

    arima_order: (
        tuple[
            int,
            int,
            int,
        ]
        | None
    ) = None


class EconometricModelSelectionService:
    """
    Selección de modelos mediante expanding-window backtesting.

    Principios:
    - ningún modelo gana por ajuste in-sample;
    - todos compiten fuera de muestra;
    - NAIVE siempre participa como benchmark;
    - selección primaria por RMSE;
    - MAE actúa como desempate;
    - modelos fallidos no interrumpen toda la selección.

    Esta versión es univariada.

    Los modelos multivariados, ARDL y ECM se incorporarán
    posteriormente como candidatos adicionales.
    """

    _COLUMN_MAPPING = {
        "FX_SELL": "FX_SELL",
        "TPM": "TPM",
        "TBP": "TBP",
        "TRI_CRC_12M": "TRI_CRC_12M",
        "TRI_USD_12M": "TRI_USD_12M",
        "INFLATION": "INFLATION",
        "IMAE": "IMAE",
    }

    def __init__(
        self,
        *,
        minimum_training_observations: int = 36,
        forecast_horizon: int = 1,
        minimum_backtest_observations: int = 12,
        minimum_rmse_improvement: float = 0.05,
        rmse_equivalence_tolerance: float = 1e-6,
    ) -> None:
        if minimum_training_observations < 24:
            raise ValueError("minimum_training_observations must be >= 24")

        if forecast_horizon != 1:
            raise ValueError(
                "Initial model-selection engine " "supports one-step-ahead backtesting only"
            )

        if minimum_backtest_observations < 6:
            raise ValueError("minimum_backtest_observations must be >= 6")

        self._minimum_training_observations = minimum_training_observations

        self._forecast_horizon = forecast_horizon

        self._minimum_backtest_observations = minimum_backtest_observations

        if not 0.0 <= minimum_rmse_improvement < 1.0:
            raise ValueError("minimum_rmse_improvement must be between 0 and 1")

        if rmse_equivalence_tolerance < 0.0:
            raise ValueError("rmse_equivalence_tolerance must be non-negative")

        self._minimum_rmse_improvement = minimum_rmse_improvement

        self._rmse_equivalence_tolerance = rmse_equivalence_tolerance

        self._frame_builder = EconometricDiagnosticsService()

    def select(
        self,
        dataset: EconometricMonthlyDataset,
        indicator_code: str,
    ) -> EconometricModelSelectionResult:
        code = indicator_code.strip().upper()

        if code not in self._COLUMN_MAPPING:
            raise ValueError("Unsupported econometric indicator: " f"{indicator_code}")

        series = (
            self._frame_builder.build_series(
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
            return EconometricModelSelectionResult(
                indicator_code=code,
                candidates=(),
                selected_model_name=None,
                selected_model_family=None,
                selection_metric="RMSE",
                diagnostic=("Indicator unavailable in dataset"),
            )

        specifications = self._candidate_specifications(code)

        candidates = tuple(
            self._backtest_candidate(
                indicator_code=code,
                series=series,
                specification=specification,
            )
            for specification in specifications
        )

        available = tuple(
            candidate
            for candidate in candidates
            if (
                candidate.status
                in (
                    "AVAILABLE",
                    "AVAILABLE_WITH_WARNINGS",
                )
                and candidate.metrics.rmse is not None
            )
        )

        if not available:
            return EconometricModelSelectionResult(
                indicator_code=code,
                candidates=candidates,
                selected_model_name=None,
                selected_model_family=None,
                selection_metric="RMSE",
                diagnostic=("No model produced sufficient " "out-of-sample forecasts"),
            )

        best_rmse_candidate = min(
            available,
            key=lambda candidate: (
                float(candidate.metrics.rmse),
                float(candidate.metrics.mae if candidate.metrics.mae is not None else math.inf),
                self._complexity_score(candidate.model_name),
            ),
        )

        best_rmse = float(best_rmse_candidate.metrics.rmse)

        equivalent_candidates = tuple(
            candidate
            for candidate in available
            if (
                candidate.metrics.rmse is not None
                and abs(float(candidate.metrics.rmse) - best_rmse)
                <= max(
                    self._rmse_equivalence_tolerance,
                    abs(best_rmse) * self._rmse_equivalence_tolerance,
                )
            )
        )

        best_candidate = min(
            equivalent_candidates,
            key=lambda candidate: (
                self._complexity_score(candidate.model_name),
                float(candidate.metrics.mae if candidate.metrics.mae is not None else math.inf),
            ),
        )

        naive = next(
            (candidate for candidate in available if (candidate.model_name == "NAIVE")),
            None,
        )

        winner = best_candidate
        selection_diagnostic = None

        if (
            naive is not None
            and naive.metrics.rmse is not None
            and best_candidate.model_name != "NAIVE"
        ):
            naive_rmse = float(naive.metrics.rmse)

            candidate_rmse = float(best_candidate.metrics.rmse)

            improvement = (naive_rmse - candidate_rmse) / naive_rmse

            if improvement < self._minimum_rmse_improvement:
                winner = naive

                selection_diagnostic = (
                    "NAIVE retained: best alternative "
                    "improves RMSE by "
                    f"{improvement * 100.0:.2f}%; "
                    "minimum required improvement is "
                    f"{self._minimum_rmse_improvement * 100.0:.2f}%."
                )

            else:
                selection_diagnostic = (
                    f"{best_candidate.model_name} selected: "
                    "RMSE improvement versus NAIVE = "
                    f"{improvement * 100.0:.2f}%, "
                    "exceeding the "
                    f"{self._minimum_rmse_improvement * 100.0:.2f}% "
                    "materiality threshold."
                )

        return EconometricModelSelectionResult(
            indicator_code=code,
            candidates=candidates,
            selected_model_name=(winner.model_name),
            selected_model_family=(winner.model_family),
            selection_metric="RMSE",
            diagnostic=selection_diagnostic,
        )

    def select_all(
        self,
        dataset: EconometricMonthlyDataset,
    ) -> tuple[
        EconometricModelSelectionResult,
        ...,
    ]:
        return tuple(
            self.select(
                dataset,
                code,
            )
            for code in self._COLUMN_MAPPING
        )

    @staticmethod
    def _candidate_specifications(
        indicator_code: str,
    ) -> tuple[
        _CandidateSpecification,
        ...,
    ]:
        """
        Universo candidato inicial deliberadamente parsimonioso.

        Se mantiene pequeño mientras la muestra común sea
        aproximadamente 59 observaciones.
        """

        _ = indicator_code

        return (
            _CandidateSpecification(
                name="NAIVE",
                family="NAIVE",
            ),
            _CandidateSpecification(
                name="DRIFT",
                family="DRIFT",
            ),
            _CandidateSpecification(
                name="AR_1",
                family="AR",
                ar_lags=1,
            ),
            _CandidateSpecification(
                name="AR_2",
                family="AR",
                ar_lags=2,
            ),
            _CandidateSpecification(
                name="ARIMA_0_1_0",
                family="ARIMA",
                arima_order=(
                    0,
                    1,
                    0,
                ),
            ),
            _CandidateSpecification(
                name="ARIMA_1_1_0",
                family="ARIMA",
                arima_order=(
                    1,
                    1,
                    0,
                ),
            ),
            _CandidateSpecification(
                name="ARIMA_0_1_1",
                family="ARIMA",
                arima_order=(
                    0,
                    1,
                    1,
                ),
            ),
        )

    def _backtest_candidate(
        self,
        *,
        indicator_code: str,
        series: pd.Series,
        specification: _CandidateSpecification,
    ) -> EconometricModelCandidateResult:
        observations = len(series)

        if observations <= self._minimum_training_observations:
            return EconometricModelCandidateResult(
                indicator_code=indicator_code,
                model_name=(specification.name),
                model_family=(specification.family),
                parameters=(self._parameters(specification)),
                status=("INSUFFICIENT_DATA"),
                metrics=(self._empty_metrics()),
                forecasts=(),
                diagnostic=("Insufficient observations " "for backtesting"),
            )

        forecasts: list[EconometricForecastPoint] = []

        failures: list[str] = []

        estimation_warnings: list[EconometricEstimationWarning] = []

        for target_index in range(
            self._minimum_training_observations,
            observations,
        ):
            training = series.iloc[:target_index]

            target_period = series.index[target_index]

            actual = float(series.iloc[target_index])

            try:
                with warnings.catch_warnings(record=True) as warning_records:
                    # Warnings econométricos conocidos se
                    # registran y permiten continuar.
                    #
                    # Cualquier warning no gobernado conserva
                    # comportamiento estricto y se convierte
                    # en excepción.
                    warnings.simplefilter("error")

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

                    forecast = self._forecast_one_step(
                        training=training,
                        specification=(specification),
                    )

                for item in warning_records:
                    category = item.category

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
                        EconometricEstimationWarning(
                            forecast_origin=(training.index[-1].date()),
                            target_period=(target_period.date()),
                            warning_type=(category.__name__),
                            message=str(item.message),
                        )
                    )

            except (
                ValueError,
                TypeError,
                np.linalg.LinAlgError,
                RuntimeError,
            ) as exc:
                failures.append(f"{target_period}: " f"{type(exc).__name__}: " f"{exc}")

                continue

            if not math.isfinite(forecast):
                failures.append(f"{target_period}: " "non-finite forecast")

                continue

            error = forecast - actual

            forecasts.append(
                EconometricForecastPoint(
                    forecast_origin=(training.index[-1].date()),
                    target_period=(target_period.date()),
                    actual=actual,
                    forecast=forecast,
                    error=error,
                    absolute_error=abs(error),
                    squared_error=(error * error),
                )
            )

        if len(forecasts) < self._minimum_backtest_observations:
            failure_diagnostic = "Insufficient successful " "backtest forecasts"

            if failures:
                failure_diagnostic += f"; failures={len(failures)}"

            return EconometricModelCandidateResult(
                indicator_code=indicator_code,
                model_name=(specification.name),
                model_family=(specification.family),
                parameters=(self._parameters(specification)),
                status="FAILED",
                metrics=(self._metrics(forecasts)),
                forecasts=tuple(forecasts),
                warnings=tuple(estimation_warnings),
                diagnostic=failure_diagnostic,
            )

        diagnostic_parts: list[str] = []

        if failures:
            diagnostic_parts.append(f"{len(failures)} " "rolling estimations failed")

        if estimation_warnings:
            diagnostic_parts.append(f"{len(estimation_warnings)} " "estimation warnings captured")

        diagnostic: str | None = "; ".join(diagnostic_parts) if diagnostic_parts else None

        status = "AVAILABLE_WITH_WARNINGS" if estimation_warnings else "AVAILABLE"

        return EconometricModelCandidateResult(
            indicator_code=indicator_code,
            model_name=(specification.name),
            model_family=(specification.family),
            parameters=(self._parameters(specification)),
            status=status,
            metrics=(self._metrics(forecasts)),
            forecasts=tuple(forecasts),
            warnings=tuple(estimation_warnings),
            diagnostic=diagnostic,
        )

    @staticmethod
    def _forecast_one_step(
        *,
        training: pd.Series,
        specification: _CandidateSpecification,
    ) -> float:
        values = training.to_numpy(dtype=float)

        if specification.family == "NAIVE":
            return float(values[-1])

        if specification.family == "DRIFT":
            if len(values) < 2:
                raise ValueError("DRIFT requires at least " "two observations")

            drift = (values[-1] - values[0]) / (len(values) - 1)

            return float(values[-1] + drift)

        if specification.family == "AR":
            if specification.ar_lags is None:
                raise ValueError("AR lag configuration missing")

            model = AutoReg(
                values,
                lags=(specification.ar_lags),
                trend="ct",
            )

            fitted = model.fit()

            forecast = fitted.predict(
                start=len(values),
                end=len(values),
                dynamic=False,
            )

            return float(forecast[0])

        if specification.family == "ARIMA":
            if specification.arima_order is None:
                raise ValueError("ARIMA order missing")

            model = ARIMA(
                values,
                order=(specification.arima_order),
                trend=("t" if (specification.arima_order[1] > 0) else "ct"),
            )

            fitted = model.fit()

            forecast = fitted.forecast(steps=1)

            return float(forecast[0])

        raise ValueError("Unsupported model family: " f"{specification.family}")

    @staticmethod
    def _metrics(
        forecasts: list[EconometricForecastPoint],
    ) -> EconometricModelMetrics:
        if not forecasts:
            return EconometricModelSelectionService._empty_metrics()

        absolute_errors = np.asarray(
            [item.absolute_error for item in forecasts],
            dtype=float,
        )

        squared_errors = np.asarray(
            [item.squared_error for item in forecasts],
            dtype=float,
        )

        errors = np.asarray(
            [item.error for item in forecasts],
            dtype=float,
        )

        percentage_errors = []

        for item in forecasts:
            if abs(item.actual) <= 1e-12:
                continue

            percentage_errors.append(abs(item.error / item.actual) * 100.0)

        mae = float(np.mean(absolute_errors))

        rmse = float(np.sqrt(np.mean(squared_errors)))

        bias = float(np.mean(errors))

        mape = (
            float(
                np.mean(
                    np.asarray(
                        percentage_errors,
                        dtype=float,
                    )
                )
            )
            if percentage_errors
            else None
        )

        return EconometricModelMetrics(
            observations=len(forecasts),
            mae=mae,
            rmse=rmse,
            mape=mape,
            bias=bias,
        )

    @staticmethod
    def _empty_metrics() -> EconometricModelMetrics:
        return EconometricModelMetrics(
            observations=0,
            mae=None,
            rmse=None,
            mape=None,
            bias=None,
        )

    @staticmethod
    def _parameters(
        specification: _CandidateSpecification,
    ) -> tuple[
        tuple[
            str,
            str,
        ],
        ...,
    ]:
        output: list[
            tuple[
                str,
                str,
            ]
        ] = []

        if specification.ar_lags is not None:
            output.append(
                (
                    "lags",
                    str(specification.ar_lags),
                )
            )

        if specification.arima_order is not None:
            output.append(
                (
                    "order",
                    str(specification.arima_order),
                )
            )

        return tuple(output)

    @staticmethod
    def _complexity_score(
        model_name: str,
    ) -> int:
        ordering = {
            "NAIVE": 0,
            "DRIFT": 1,
            "AR_1": 2,
            "AR_2": 3,
            "ARIMA_0_1_0": 4,
            "ARIMA_1_1_0": 5,
            "ARIMA_0_1_1": 5,
        }

        return ordering.get(
            model_name,
            999,
        )
