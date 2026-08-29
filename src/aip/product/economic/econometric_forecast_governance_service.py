from __future__ import annotations

from dataclasses import dataclass
import math
import warnings

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
from aip.product.economic.econometric_forecast_governance import (
    DynamicStabilityDiagnostic,
    ForecastGovernanceResult,
    HorizonBacktestMetrics,
    ModelHorizonGovernance,
)
from aip.product.economic.econometric_model_selection_service import (
    EconometricModelSelectionService,
)


@dataclass(frozen=True, slots=True)
class _Specification:
    name: str
    family: str
    ar_lags: int | None = None
    arima_order: tuple[int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class _RawHorizonMetrics:
    horizon: int
    observations: int
    rmse: float | None
    mae: float | None
    bias: float | None
    warning_count: int
    failure_count: int


class ForecastGovernanceService:
    """
    Gobernanza econométrica multi-horizonte.

    La selección one-step existente se conserva como
    referencia estadística.

    La recomendación institucional se calcula con:
    - backtesting rolling a 1M, 3M, 6M y 12M;
    - RMSE relativo al benchmark NAIVE por horizonte;
    - score ponderado multi-horizonte;
    - umbral de materialidad frente a NAIVE;
    - prueba de estabilidad dinámica basada en la
      distribución histórica de cambios a 12 meses.

    No realiza imputación.
    No realiza forward-fill.
    No incorpora supuestos discrecionales.
    """

    DEFAULT_HORIZON_WEIGHTS = (
        (1, 0.20),
        (3, 0.30),
        (6, 0.30),
        (12, 0.20),
    )

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
        minimum_training_observations: int = 36,
        minimum_backtest_observations: int = 12,
        minimum_material_improvement: float = 0.05,
        long_horizon_relative_rmse_limit: float = 1.10,
        model_equivalence_tolerance: float = 0.02,
        dynamic_percentile: float = 0.95,
        horizon_weights: tuple[
            tuple[int, float],
            ...
        ] = DEFAULT_HORIZON_WEIGHTS,
    ) -> None:
        if (
            minimum_training_observations
            < 12
        ):
            raise ValueError(
                "minimum_training_observations "
                "must be at least 12"
            )

        if (
            minimum_backtest_observations
            < 1
        ):
            raise ValueError(
                "minimum_backtest_observations "
                "must be positive"
            )

        if not (
            0.0
            <= minimum_material_improvement
            < 1.0
        ):
            raise ValueError(
                "minimum_material_improvement "
                "must be in [0, 1)"
            )

        if (
            long_horizon_relative_rmse_limit
            < 1.0
        ):
            raise ValueError(
                "long_horizon_relative_rmse_limit "
                "must be at least 1.0"
            )

        if not (
            0.0
            <= model_equivalence_tolerance
            < 1.0
        ):
            raise ValueError(
                "model_equivalence_tolerance "
                "must be in [0, 1)"
            )

        if not (
            0.50
            < dynamic_percentile
            < 1.0
        ):
            raise ValueError(
                "dynamic_percentile must be "
                "between 0.50 and 1.00"
            )

        total_weight = sum(
            weight
            for _,
            weight
            in horizon_weights
        )

        if not math.isclose(
            total_weight,
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "horizon_weights must sum to 1.0"
            )

        if any(
            horizon < 1
            or weight <= 0.0
            for horizon, weight
            in horizon_weights
        ):
            raise ValueError(
                "Invalid horizon_weights"
            )

        self._model_selection_service = (
            model_selection_service
            or EconometricModelSelectionService(
                minimum_training_observations=(
                    minimum_training_observations
                ),
                minimum_backtest_observations=(
                    minimum_backtest_observations
                ),
            )
        )

        self._frame_builder = (
            EconometricDiagnosticsService()
        )

        self._minimum_training_observations = (
            minimum_training_observations
        )

        self._minimum_backtest_observations = (
            minimum_backtest_observations
        )

        self._minimum_material_improvement = (
            minimum_material_improvement
        )

        self._long_horizon_relative_rmse_limit = (
            long_horizon_relative_rmse_limit
        )

        self._model_equivalence_tolerance = (
            model_equivalence_tolerance
        )

        self._dynamic_percentile = (
            dynamic_percentile
        )

        self._horizon_weights = (
            horizon_weights
        )

    def evaluate(
        self,
        dataset: EconometricMonthlyDataset,
        indicator_code: str,
    ) -> ForecastGovernanceResult:
        code = (
            indicator_code
            .strip()
            .upper()
        )

        if (
            code
            not in self._SUPPORTED_INDICATORS
        ):
            return ForecastGovernanceResult(
                indicator_code=code,
                status="UNAVAILABLE",
                statistical_model_name=None,
                statistical_model_family=None,
                governance_model_name=None,
                governance_model_family=None,
                weighted_relative_score=None,
                improvement_vs_naive=None,
                materiality_threshold=(
                    self._minimum_material_improvement
                ),
                horizon_results=(),
                dynamic_stability=None,
                warnings=(),
                reason_codes=(
                    "UNAVAILABLE",
                ),
                diagnostic=(
                    "Unsupported econometric indicator"
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

        if (
            len(series)
            <= self._minimum_training_observations
        ):
            return ForecastGovernanceResult(
                indicator_code=code,
                status="UNAVAILABLE",
                statistical_model_name=None,
                statistical_model_family=None,
                governance_model_name=None,
                governance_model_family=None,
                weighted_relative_score=None,
                improvement_vs_naive=None,
                materiality_threshold=(
                    self._minimum_material_improvement
                ),
                horizon_results=(),
                dynamic_stability=None,
                warnings=(),
                reason_codes=(
                    "UNAVAILABLE",
                ),
                diagnostic=(
                    "Insufficient observations "
                    "for governance backtesting"
                ),
            )

        selection = (
            self._model_selection_service
            .select(
                dataset,
                code,
            )
        )

        statistical_model_name = (
            selection.selected_model_name
        )

        statistical_model_family = (
            selection.selected_model_family
        )

        specifications = tuple(
            self._specification_from_candidate(
                candidate
            )
            for candidate
            in selection.candidates
            if (
                candidate.model_name
                and candidate.model_family
            )
        )

        if not specifications:
            return ForecastGovernanceResult(
                indicator_code=code,
                status="UNAVAILABLE",
                statistical_model_name=(
                    statistical_model_name
                ),
                statistical_model_family=(
                    statistical_model_family
                ),
                governance_model_name=None,
                governance_model_family=None,
                weighted_relative_score=None,
                improvement_vs_naive=None,
                materiality_threshold=(
                    self._minimum_material_improvement
                ),
                horizon_results=(),
                dynamic_stability=None,
                warnings=(),
                reason_codes=(
                    "UNAVAILABLE",
                ),
                diagnostic=(
                    "No candidate specifications "
                    "available"
                ),
            )

        raw_results: dict[
            str,
            tuple[_RawHorizonMetrics, ...],
        ] = {}

        specifications_by_name = {
            specification.name: specification
            for specification
            in specifications
        }

        for specification in specifications:
            raw_results[
                specification.name
            ] = tuple(
                self._backtest_horizon(
                    series=series,
                    specification=(
                        specification
                    ),
                    horizon=(
                        horizon
                    ),
                )
                for horizon, _
                in self._horizon_weights
            )

        naive_raw = raw_results.get(
            "NAIVE"
        )

        if naive_raw is None:
            return ForecastGovernanceResult(
                indicator_code=code,
                status="UNAVAILABLE",
                statistical_model_name=(
                    statistical_model_name
                ),
                statistical_model_family=(
                    statistical_model_family
                ),
                governance_model_name=None,
                governance_model_family=None,
                weighted_relative_score=None,
                improvement_vs_naive=None,
                materiality_threshold=(
                    self._minimum_material_improvement
                ),
                horizon_results=(),
                dynamic_stability=None,
                warnings=(),
                reason_codes=(
                    "UNAVAILABLE",
                ),
                diagnostic=(
                    "NAIVE benchmark unavailable"
                ),
            )

        naive_by_horizon = {
            item.horizon: item
            for item in naive_raw
        }

        governed_models: list[
            ModelHorizonGovernance
        ] = []

        for specification in specifications:
            raw_model = raw_results[
                specification.name
            ]

            horizon_metrics: list[
                HorizonBacktestMetrics
            ] = []

            weighted_sum = 0.0
            used_weight = 0.0
            available_horizons = 0
            warning_count = 0
            failure_count = 0

            for (
                raw_metric,
                (
                    horizon,
                    weight,
                ),
            ) in zip(
                raw_model,
                self._horizon_weights,
                strict=True,
            ):
                naive_metric = (
                    naive_by_horizon[
                        horizon
                    ]
                )

                relative_rmse = None

                if (
                    raw_metric.rmse
                    is not None
                    and naive_metric.rmse
                    is not None
                ):
                    if math.isclose(
                        naive_metric.rmse,
                        0.0,
                        abs_tol=1e-12,
                    ):
                        relative_rmse = (
                            1.0
                            if math.isclose(
                                raw_metric.rmse,
                                0.0,
                                abs_tol=1e-12,
                            )
                            else None
                        )
                    else:
                        relative_rmse = (
                            raw_metric.rmse
                            / naive_metric.rmse
                        )

                horizon_metrics.append(
                    HorizonBacktestMetrics(
                        horizon_months=horizon,
                        observations=(
                            raw_metric.observations
                        ),
                        rmse=raw_metric.rmse,
                        mae=raw_metric.mae,
                        bias=raw_metric.bias,
                        naive_rmse=(
                            naive_metric.rmse
                        ),
                        relative_rmse=(
                            relative_rmse
                        ),
                    )
                )

                warning_count += (
                    raw_metric.warning_count
                )

                failure_count += (
                    raw_metric.failure_count
                )

                if (
                    relative_rmse
                    is not None
                    and raw_metric.observations
                    >= self._minimum_backtest_observations
                ):
                    weighted_sum += (
                        weight
                        * relative_rmse
                    )

                    used_weight += weight
                    available_horizons += 1

            weighted_score = None

            if (
                available_horizons
                == len(
                    self._horizon_weights
                )
                and math.isclose(
                    used_weight,
                    1.0,
                    abs_tol=1e-9,
                )
            ):
                weighted_score = (
                    weighted_sum
                )

            improvement = (
                None
                if weighted_score is None
                else 1.0 - weighted_score
            )

            governed_models.append(
                ModelHorizonGovernance(
                    model_name=(
                        specification.name
                    ),
                    model_family=(
                        specification.family
                    ),
                    parameters=(
                        self._parameters(
                            specification
                        )
                    ),
                    horizons=tuple(
                        horizon_metrics
                    ),
                    weighted_relative_score=(
                        weighted_score
                    ),
                    improvement_vs_naive=(
                        improvement
                    ),
                    available_horizons=(
                        available_horizons
                    ),
                    warning_count=(
                        warning_count
                    ),
                    failed_estimations=(
                        failure_count
                    ),
                )
            )

        available_models = tuple(
            item
            for item in governed_models
            if item.available
        )

        if not available_models:
            return ForecastGovernanceResult(
                indicator_code=code,
                status="UNAVAILABLE",
                statistical_model_name=(
                    statistical_model_name
                ),
                statistical_model_family=(
                    statistical_model_family
                ),
                governance_model_name=None,
                governance_model_family=None,
                weighted_relative_score=None,
                improvement_vs_naive=None,
                materiality_threshold=(
                    self._minimum_material_improvement
                ),
                horizon_results=tuple(
                    governed_models
                ),
                dynamic_stability=None,
                warnings=(),
                reason_codes=(
                    "UNAVAILABLE",
                ),
                diagnostic=(
                    "No model has complete "
                    "multi-horizon coverage"
                ),
            )

        best_model = min(
            available_models,
            key=lambda item: (
                float(
                    item.weighted_relative_score
                ),
                self._complexity_score(
                    item.model_name,
                    item.model_family,
                ),
            ),
        )

        naive_model = next(
            (
                item
                for item
                in available_models
                if item.model_name
                == "NAIVE"
            ),
            None,
        )

        governance_model = (
            best_model
        )

        parsimony_message = None
        equivalence_message = None

        if (
            best_model.model_name
            != "NAIVE"
            and naive_model is not None
        ):
            improvement = (
                best_model
                .improvement_vs_naive
            )

            if (
                improvement is None
                or improvement
                < self._minimum_material_improvement
            ):
                governance_model = (
                    naive_model
                )

                parsimony_message = (
                    "NAIVE retained by multi-horizon "
                    "materiality policy"
                )

        # Model-equivalence parsimony:
        # if the governance winner and the one-step
        # statistical winner are economically equivalent
        # in multi-horizon score, retain the simpler model.
        if (
            statistical_model_name
            and governance_model.model_name
            != statistical_model_name
        ):
            statistical_governance_result = next(
                (
                    item
                    for item
                    in available_models
                    if item.model_name
                    == statistical_model_name
                ),
                None,
            )

            if (
                statistical_governance_result
                is not None
                and statistical_governance_result
                .weighted_relative_score
                is not None
                and governance_model
                .weighted_relative_score
                is not None
            ):
                score_difference = abs(
                    statistical_governance_result
                    .weighted_relative_score
                    - governance_model
                    .weighted_relative_score
                )

                if (
                    score_difference
                    <= self._model_equivalence_tolerance
                    and self._complexity_score(
                        statistical_governance_result
                        .model_name,
                        statistical_governance_result
                        .model_family,
                    )
                    < self._complexity_score(
                        governance_model.model_name,
                        governance_model.model_family,
                    )
                ):
                    governance_model = (
                        statistical_governance_result
                    )

                    equivalence_message = (
                        "Simpler statistically selected "
                        "model retained because "
                        "multi-horizon scores are "
                        "equivalent within tolerance "
                        f"{self._model_equivalence_tolerance:.2%}"
                    )

        selected_specification = (
            specifications_by_name[
                governance_model.model_name
            ]
        )

        dynamic = (
            self._dynamic_stability(
                series=series,
                specification=(
                    selected_specification
                ),
            )
        )

        governance_warnings: list[
            str
        ] = []

        reason_codes: list[
            str
        ] = []

        status = "APPROVED"

        if parsimony_message:
            reason_codes.append(
                "NAIVE_MATERIALITY_RETENTION"
            )

        if equivalence_message:
            reason_codes.append(
                "MODEL_EQUIVALENCE"
            )

        if (
            governance_model.warning_count
            > 0
        ):
            governance_warnings.append(
                f"{governance_model.warning_count} "
                "governed estimation warning(s) "
                "were captured during "
                "multi-horizon backtesting"
            )

            reason_codes.append(
                "ESTIMATION_WARNING"
            )

            status = (
                "APPROVED_WITH_WARNINGS"
            )

        if (
            governance_model
            .available_horizons
            < len(
                self._horizon_weights
            )
        ):
            governance_warnings.append(
                "Incomplete multi-horizon coverage"
            )

            reason_codes.append(
                "INCOMPLETE_HORIZON_COVERAGE"
            )

            status = "REVIEW_REQUIRED"

        long_horizon = (
            governance_model
            .metrics_for_horizon(
                12
            )
        )

        if (
            long_horizon is None
            or long_horizon.relative_rmse
            is None
        ):
            governance_warnings.append(
                "12-month relative RMSE "
                "is unavailable"
            )

            reason_codes.append(
                "LONG_HORIZON_UNAVAILABLE"
            )

            status = "REVIEW_REQUIRED"

        elif (
            long_horizon.relative_rmse
            > self._long_horizon_relative_rmse_limit
        ):
            governance_warnings.append(
                "12-month RMSE deterioration "
                "versus NAIVE exceeds permitted "
                "long-horizon threshold: "
                f"{long_horizon.relative_rmse:.4f} "
                "> "
                f"{self._long_horizon_relative_rmse_limit:.4f}"
            )

            reason_codes.append(
                "LONG_HORIZON_DEGRADATION"
            )

            status = "REVIEW_REQUIRED"

        if (
            dynamic.status
            == "REVIEW_REQUIRED"
        ):
            governance_warnings.append(
                dynamic.diagnostic
                or (
                    "Dynamic stability review "
                    "required"
                )
            )

            reason_codes.append(
                "DYNAMIC_INSTABILITY"
            )

            status = "REVIEW_REQUIRED"

        if not reason_codes:
            reason_codes.append(
                "MULTI_HORIZON_APPROVED"
            )

        diagnostic_parts: list[str] = []

        if parsimony_message:
            diagnostic_parts.append(
                parsimony_message
            )

        if equivalence_message:
            diagnostic_parts.append(
                equivalence_message
            )

        if (
            statistical_model_name
            != governance_model.model_name
        ):
            diagnostic_parts.append(
                "One-step statistical winner "
                f"{statistical_model_name} differs "
                "from multi-horizon governance "
                f"recommendation "
                f"{governance_model.model_name}"
            )
        else:
            diagnostic_parts.append(
                "One-step statistical selection "
                "and multi-horizon governance agree"
            )

        if (
            governance_model
            .improvement_vs_naive
            is not None
        ):
            diagnostic_parts.append(
                "multi-horizon improvement versus "
                "NAIVE="
                f"{governance_model.improvement_vs_naive:.2%}"
            )

        return ForecastGovernanceResult(
            indicator_code=code,
            status=status,
            statistical_model_name=(
                statistical_model_name
            ),
            statistical_model_family=(
                statistical_model_family
            ),
            governance_model_name=(
                governance_model.model_name
            ),
            governance_model_family=(
                governance_model.model_family
            ),
            weighted_relative_score=(
                governance_model
                .weighted_relative_score
            ),
            improvement_vs_naive=(
                governance_model
                .improvement_vs_naive
            ),
            materiality_threshold=(
                self._minimum_material_improvement
            ),
            horizon_results=tuple(
                governed_models
            ),
            dynamic_stability=dynamic,
            warnings=tuple(
                governance_warnings
            ),
            reason_codes=tuple(
                reason_codes
            ),
            diagnostic=(
                "; ".join(
                    diagnostic_parts
                )
                if diagnostic_parts
                else None
            ),
        )

    def evaluate_all(
        self,
        dataset: EconometricMonthlyDataset,
    ) -> tuple[
        ForecastGovernanceResult,
        ...
    ]:
        return tuple(
            self.evaluate(
                dataset,
                code,
            )
            for code
            in self._SUPPORTED_INDICATORS
        )

    def _backtest_horizon(
        self,
        *,
        series: pd.Series,
        specification: _Specification,
        horizon: int,
    ) -> _RawHorizonMetrics:
        forecasts: list[float] = []
        actuals: list[float] = []

        warning_count = 0
        failure_count = 0

        observations = len(
            series
        )

        first_origin_index = (
            self._minimum_training_observations
            - 1
        )

        last_origin_index = (
            observations
            - horizon
            - 1
        )

        if (
            last_origin_index
            < first_origin_index
        ):
            return _RawHorizonMetrics(
                horizon=horizon,
                observations=0,
                rmse=None,
                mae=None,
                bias=None,
                warning_count=0,
                failure_count=0,
            )

        for origin_index in range(
            first_origin_index,
            last_origin_index + 1,
        ):
            training = (
                series.iloc[
                    :origin_index + 1
                ]
            )

            target_index = (
                origin_index
                + horizon
            )

            actual = float(
                series.iloc[
                    target_index
                ]
            )

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

                    forecast = (
                        self._forecast_horizon(
                            training=training,
                            specification=(
                                specification
                            ),
                            horizon=horizon,
                        )
                    )

                for item in warning_records:
                    if issubclass(
                        item.category,
                        (
                            SingularMatrixWarning,
                            ConvergenceWarning,
                            EstimationWarning,
                        ),
                    ):
                        warning_count += 1

            except (
                ValueError,
                TypeError,
                np.linalg.LinAlgError,
                RuntimeError,
            ):
                failure_count += 1
                continue

            if not math.isfinite(
                forecast
            ):
                failure_count += 1
                continue

            forecasts.append(
                forecast
            )

            actuals.append(
                actual
            )

        if (
            len(forecasts)
            < self._minimum_backtest_observations
        ):
            return _RawHorizonMetrics(
                horizon=horizon,
                observations=len(
                    forecasts
                ),
                rmse=None,
                mae=None,
                bias=None,
                warning_count=(
                    warning_count
                ),
                failure_count=(
                    failure_count
                ),
            )

        forecast_array = np.asarray(
            forecasts,
            dtype=float,
        )

        actual_array = np.asarray(
            actuals,
            dtype=float,
        )

        errors = (
            forecast_array
            - actual_array
        )

        rmse = float(
            np.sqrt(
                np.mean(
                    np.square(
                        errors
                    )
                )
            )
        )

        mae = float(
            np.mean(
                np.abs(
                    errors
                )
            )
        )

        bias = float(
            np.mean(
                errors
            )
        )

        return _RawHorizonMetrics(
            horizon=horizon,
            observations=len(
                forecasts
            ),
            rmse=rmse,
            mae=mae,
            bias=bias,
            warning_count=(
                warning_count
            ),
            failure_count=(
                failure_count
            ),
        )

    @staticmethod
    def _forecast_horizon(
        *,
        training: pd.Series,
        specification: _Specification,
        horizon: int,
    ) -> float:
        values = training.to_numpy(
            dtype=float
        )

        if (
            specification.family
            == "NAIVE"
        ):
            return float(
                values[
                    -1
                ]
            )

        if (
            specification.family
            == "DRIFT"
        ):
            if len(
                values
            ) < 2:
                raise ValueError(
                    "DRIFT requires at least "
                    "two observations"
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

            return float(
                values[
                    -1
                ]
                + drift
                * horizon
            )

        if (
            specification.family
            == "AR"
        ):
            if (
                specification.ar_lags
                is None
            ):
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
                    + horizon
                    - 1
                ),
                dynamic=False,
            )

            return float(
                forecast[
                    -1
                ]
            )

        if (
            specification.family
            == "ARIMA"
        ):
            if (
                specification.arima_order
                is None
            ):
                raise ValueError(
                    "ARIMA order missing"
                )

            model = ARIMA(
                values,
                order=(
                    specification
                    .arima_order
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
                steps=horizon
            )

            return float(
                forecast[
                    -1
                ]
            )

        raise ValueError(
            "Unsupported model family: "
            f"{specification.family}"
        )

    def _dynamic_stability(
        self,
        *,
        series: pd.Series,
        specification: _Specification,
    ) -> DynamicStabilityDiagnostic:
        values = series.to_numpy(
            dtype=float
        )

        if len(
            values
        ) < 24:
            return DynamicStabilityDiagnostic(
                historical_observations=len(
                    values
                ),
                historical_change_observations=0,
                last_observed_value=(
                    float(
                        values[
                            -1
                        ]
                    )
                    if len(values)
                    else None
                ),
                projected_12m_value=None,
                projected_change_12m=None,
                historical_abs_change_p95=None,
                stability_ratio=None,
                status="UNAVAILABLE",
                diagnostic=(
                    "Insufficient history for "
                    "12-month dynamic stability test"
                ),
            )

        try:
            projected = (
                self._forecast_horizon(
                    training=series,
                    specification=(
                        specification
                    ),
                    horizon=12,
                )
            )
        except (
            ValueError,
            TypeError,
            np.linalg.LinAlgError,
            RuntimeError,
        ) as exc:
            return DynamicStabilityDiagnostic(
                historical_observations=len(
                    values
                ),
                historical_change_observations=0,
                last_observed_value=float(
                    values[
                        -1
                    ]
                ),
                projected_12m_value=None,
                projected_change_12m=None,
                historical_abs_change_p95=None,
                stability_ratio=None,
                status="REVIEW_REQUIRED",
                diagnostic=(
                    "Unable to evaluate final "
                    "12-month dynamic path: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        historical_changes = (
            values[
                12:
            ]
            - values[
                :-12
            ]
        )

        finite_changes = (
            historical_changes[
                np.isfinite(
                    historical_changes
                )
            ]
        )

        if not len(
            finite_changes
        ):
            return DynamicStabilityDiagnostic(
                historical_observations=len(
                    values
                ),
                historical_change_observations=0,
                last_observed_value=float(
                    values[
                        -1
                    ]
                ),
                projected_12m_value=(
                    projected
                ),
                projected_change_12m=(
                    projected
                    - float(
                        values[
                            -1
                        ]
                    )
                ),
                historical_abs_change_p95=None,
                stability_ratio=None,
                status="UNAVAILABLE",
                diagnostic=(
                    "No valid historical "
                    "12-month changes"
                ),
            )

        abs_changes = np.abs(
            finite_changes
        )

        historical_p95 = float(
            np.quantile(
                abs_changes,
                self._dynamic_percentile,
            )
        )

        projected_change = (
            projected
            - float(
                values[
                    -1
                ]
            )
        )

        if math.isclose(
            historical_p95,
            0.0,
            abs_tol=1e-12,
        ):
            ratio = (
                0.0
                if math.isclose(
                    projected_change,
                    0.0,
                    abs_tol=1e-12,
                )
                else math.inf
            )
        else:
            ratio = (
                abs(
                    projected_change
                )
                / historical_p95
            )

        status = (
            "REVIEW_REQUIRED"
            if ratio > 1.0
            else "STABLE"
        )

        diagnostic = (
            None
            if status == "STABLE"
            else (
                "Projected absolute 12-month "
                "change exceeds the empirical "
                f"{self._dynamic_percentile:.0%} "
                "historical absolute-change "
                "percentile"
            )
        )

        return DynamicStabilityDiagnostic(
            historical_observations=len(
                values
            ),
            historical_change_observations=len(
                finite_changes
            ),
            last_observed_value=float(
                values[
                    -1
                ]
            ),
            projected_12m_value=(
                projected
            ),
            projected_change_12m=(
                projected_change
            ),
            historical_abs_change_p95=(
                historical_p95
            ),
            stability_ratio=(
                ratio
            ),
            status=status,
            diagnostic=diagnostic,
        )

    @staticmethod
    def _specification_from_candidate(
        candidate,
    ) -> _Specification:
        name = (
            candidate.model_name
        )

        family = (
            candidate.model_family
        )

        parameters = dict(
            candidate.parameters
            or ()
        )

        ar_lags = None
        arima_order = None

        if family == "AR":
            lag_value = (
                parameters.get(
                    "lags"
                )
                or parameters.get(
                    "ar_lags"
                )
            )

            if lag_value is not None:
                ar_lags = int(
                    lag_value
                )
            elif name.startswith(
                "AR_"
            ):
                ar_lags = int(
                    name.split(
                        "_",
                        1,
                    )[
                        1
                    ]
                )

        if family == "ARIMA":
            order_value = (
                parameters.get(
                    "order"
                )
            )

            if order_value:
                cleaned = (
                    order_value
                    .strip()
                    .replace(
                        "(",
                        "",
                    )
                    .replace(
                        ")",
                        "",
                    )
                )

                parts = tuple(
                    int(
                        item.strip()
                    )
                    for item
                    in cleaned.split(
                        ","
                    )
                )

                if len(
                    parts
                ) == 3:
                    arima_order = (
                        parts[
                            0
                        ],
                        parts[
                            1
                        ],
                        parts[
                            2
                        ],
                    )

            if (
                arima_order is None
                and name.startswith(
                    "ARIMA_"
                )
            ):
                parts = (
                    name.replace(
                        "ARIMA_",
                        "",
                        1,
                    )
                    .split(
                        "_"
                    )
                )

                if len(
                    parts
                ) == 3:
                    arima_order = tuple(
                        int(
                            item
                        )
                        for item
                        in parts
                    )

        return _Specification(
            name=name,
            family=family,
            ar_lags=ar_lags,
            arima_order=arima_order,
        )

    @staticmethod
    def _parameters(
        specification: _Specification,
    ) -> tuple[
        tuple[str, str],
        ...
    ]:
        if (
            specification.family
            == "AR"
            and specification.ar_lags
            is not None
        ):
            return (
                (
                    "lags",
                    str(
                        specification.ar_lags
                    ),
                ),
            )

        if (
            specification.family
            == "ARIMA"
            and specification.arima_order
            is not None
        ):
            return (
                (
                    "order",
                    str(
                        specification.arima_order
                    ),
                ),
            )

        return ()

    @staticmethod
    def _complexity_score(
        model_name: str,
        model_family: str,
    ) -> int:
        if model_family == "NAIVE":
            return 0

        if model_family == "DRIFT":
            return 1

        if (
            model_family == "AR"
            and model_name == "AR_1"
        ):
            return 2

        if (
            model_family == "ARIMA"
            and model_name
            == "ARIMA_0_1_0"
        ):
            return 2

        if model_family == "AR":
            return 3

        if model_family == "ARIMA":
            return 4

        return 99
