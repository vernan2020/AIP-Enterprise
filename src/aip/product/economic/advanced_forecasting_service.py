from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

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
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from aip.product.economic.advanced_forecasting import (
    AdvancedForecastPoint,
    AdvancedIndicatorForecastResult,
    EnsembleModelWeight,
    MacroModelBacktestResult,
    MultiHorizonMetric,
)
from aip.product.economic.econometric_dataset import EconometricMonthlyDataset
from aip.product.economic.macro_model_registry import (
    MacroModelRegistry,
    MacroModelSpecification,
)


@dataclass(frozen=True, slots=True)
class _BacktestMetric:
    horizon: int
    observations: int
    rmse: float | None
    mae: float | None
    bias: float | None
    directional_accuracy: float | None
    warning_count: int
    failure_count: int


class AdvancedMacroForecastingService:
    """Governed multimodel macro forecasting laboratory.

    This engine is intentionally isolated from the approved institutional
    scenario. It produces candidate analytics that must pass the existing
    scenario-governance process before they can become an institutional input.

    Leakage controls:
    - rolling origins use only information available at each origin;
    - direct models train only on target observations known by that origin;
    - no interpolation, forward-fill or back-fill is performed;
    - contemporaneous drivers are used only when observed at the origin.
    """

    SUPPORTED_INDICATORS = (
        "FX_SELL",
        "TPM",
        "TBP",
        "TRI_CRC_12M",
        "TRI_USD_12M",
        "INFLATION",
        "IMAE",
    )

    COLUMN_MAPPING = {
        "FX_SELL": "FX_SELL",
        "TPM": "TPM",
        "TBP": "TBP",
        "TRI_CRC_12M": "TRI_CRC_12M",
        "TRI_USD_12M": "TRI_USD_12M",
        "INFLATION": "INFLATION",
        "IMAE": "IMAE",
    }

    DEFAULT_HORIZONS = ((1, 0.20), (3, 0.30), (6, 0.30), (12, 0.20))
    _FULL_FEATURE_LAGS = (0, 1, 3, 6)
    _ARDL_TARGET_LAGS = (0, 1, 3, 6)
    _ARDL_DRIVER_LAGS = (0, 1)
    _TARGET_DRIVER_MAP = {
        "FX_SELL": ("TPM", "INFLATION", "IMAE"),
        "TPM": ("INFLATION", "IMAE", "FX_SELL"),
        "TBP": ("TPM", "INFLATION", "IMAE"),
        "TRI_CRC_12M": ("TPM", "TBP", "INFLATION"),
        "TRI_USD_12M": ("FX_SELL", "TPM", "INFLATION"),
        "INFLATION": ("FX_SELL", "IMAE", "TPM"),
        "IMAE": ("TPM", "INFLATION", "FX_SELL"),
    }

    def __init__(
        self,
        *,
        registry: MacroModelRegistry | None = None,
        minimum_training_observations: int = 36,
        minimum_backtest_observations: int = 8,
        minimum_material_improvement: float = 0.05,
        horizon_weights: tuple[tuple[int, float], ...] = DEFAULT_HORIZONS,
        maximum_ensemble_models: int = 5,
    ) -> None:
        if minimum_training_observations < 24:
            raise ValueError("minimum_training_observations must be >= 24")
        if minimum_backtest_observations < 4:
            raise ValueError("minimum_backtest_observations must be >= 4")
        if not 0.0 <= minimum_material_improvement < 1.0:
            raise ValueError("minimum_material_improvement must be in [0, 1)")
        if maximum_ensemble_models < 1:
            raise ValueError("maximum_ensemble_models must be positive")
        if not math.isclose(sum(weight for _, weight in horizon_weights), 1.0, abs_tol=1e-9):
            raise ValueError("horizon_weights must sum to 1.0")

        self._registry = registry or MacroModelRegistry()
        self._minimum_training_observations = minimum_training_observations
        self._minimum_backtest_observations = minimum_backtest_observations
        self._minimum_material_improvement = minimum_material_improvement
        self._horizon_weights = horizon_weights
        self._maximum_ensemble_models = maximum_ensemble_models

    @property
    def registry(self) -> MacroModelRegistry:
        return self._registry

    def evaluate(
        self,
        dataset: EconometricMonthlyDataset,
        indicator_code: str,
        *,
        forecast_horizon: int = 12,
    ) -> AdvancedIndicatorForecastResult:
        code = indicator_code.strip().upper()
        if code not in self.SUPPORTED_INDICATORS:
            return AdvancedIndicatorForecastResult(
                indicator_code=code,
                status="FAILED",
                forecast_origin=None,
                historical_observations=0,
                champion_model_name=None,
                champion_model_family=None,
                diagnostic="Unsupported macro indicator",
            )
        if not 1 <= forecast_horizon <= 12:
            raise ValueError("forecast_horizon must be between 1 and 12")

        frame = self._frame(dataset)
        target = self.COLUMN_MAPPING[code]
        origin_position = self._last_observed_position(frame[target])
        if origin_position is None:
            return AdvancedIndicatorForecastResult(
                indicator_code=code,
                status="INSUFFICIENT_DATA",
                forecast_origin=None,
                historical_observations=0,
                champion_model_name=None,
                champion_model_family=None,
                diagnostic="No historical observations available",
            )

        frame = frame.iloc[: origin_position + 1].copy()
        history = frame[target].dropna()
        if len(history) < self._minimum_training_observations:
            return AdvancedIndicatorForecastResult(
                indicator_code=code,
                status="INSUFFICIENT_DATA",
                forecast_origin=frame.index[-1].date(),
                historical_observations=len(history),
                champion_model_name=None,
                champion_model_family=None,
                diagnostic=(
                    f"Insufficient observations: {len(history)} < "
                    f"{self._minimum_training_observations}"
                ),
            )

        raw_results: dict[str, tuple[_BacktestMetric, ...]] = {}
        diagnostics: dict[str, str | None] = {}
        for specification in self._registry.enabled():
            metrics, diagnostic = self._backtest_model(frame, target, specification)
            raw_results[specification.name] = metrics
            diagnostics[specification.name] = diagnostic

        naive_by_horizon = {item.horizon: item for item in raw_results.get("NAIVE", ())}
        horizon_weight_map = dict(self._horizon_weights)
        model_results: list[MacroModelBacktestResult] = []

        for specification in self._registry.enabled():
            raw = raw_results.get(specification.name, ())
            converted: list[MultiHorizonMetric] = []
            weighted_score = 0.0
            used_weight = 0.0
            warning_count = 0
            failure_count = 0
            available_horizons = 0

            for metric in raw:
                naive = naive_by_horizon.get(metric.horizon)
                relative = self._relative_rmse(
                    metric.rmse,
                    naive.rmse if naive is not None else None,
                )
                converted.append(
                    MultiHorizonMetric(
                        horizon_months=metric.horizon,
                        observations=metric.observations,
                        rmse=metric.rmse,
                        mae=metric.mae,
                        bias=metric.bias,
                        directional_accuracy=metric.directional_accuracy,
                        relative_rmse_vs_naive=relative,
                    )
                )
                warning_count += metric.warning_count
                failure_count += metric.failure_count
                weight = horizon_weight_map.get(metric.horizon, 0.0)
                if (
                    relative is not None
                    and metric.observations >= self._minimum_backtest_observations
                ):
                    weighted_score += weight * relative
                    used_weight += weight
                    available_horizons += 1

            score = (
                weighted_score
                if available_horizons == len(self._horizon_weights)
                and math.isclose(used_weight, 1.0, abs_tol=1e-9)
                else None
            )
            improvement = None if score is None else 1.0 - score
            diagnostic = diagnostics.get(specification.name)
            if diagnostic == "OPTIONAL_DEPENDENCY_UNAVAILABLE":
                status = "UNAVAILABLE"
            elif not converted:
                status = "FAILED"
            elif score is None:
                status = "INSUFFICIENT_DATA"
            elif warning_count or failure_count:
                status = "AVAILABLE_WITH_WARNINGS"
            else:
                status = "AVAILABLE"

            model_results.append(
                MacroModelBacktestResult(
                    model_name=specification.name,
                    model_family=specification.family,
                    status=status,
                    metrics=tuple(converted),
                    weighted_relative_score=score,
                    improvement_vs_naive=improvement,
                    warning_count=warning_count,
                    failure_count=failure_count,
                    diagnostic=diagnostic,
                )
            )

        model_results_tuple = tuple(model_results)
        champion = self._select_champion(model_results_tuple)
        if champion is None:
            return AdvancedIndicatorForecastResult(
                indicator_code=code,
                status="FAILED",
                forecast_origin=frame.index[-1].date(),
                historical_observations=len(history),
                champion_model_name=None,
                champion_model_family=None,
                model_results=model_results_tuple,
                diagnostic="No model achieved complete multi-horizon backtesting coverage",
            )

        weights = self._ensemble_weights(model_results_tuple, champion)
        if not weights:
            return AdvancedIndicatorForecastResult(
                indicator_code=code,
                status="FAILED",
                forecast_origin=frame.index[-1].date(),
                historical_observations=len(history),
                champion_model_name=champion.model_name,
                champion_model_family=champion.model_family,
                model_results=model_results_tuple,
                diagnostic="No eligible model remained for the ensemble",
            )

        points, forecast_warnings = self._forecast_ensemble(
            frame,
            target,
            weights,
            model_results_tuple,
            forecast_horizon,
        )
        if not points:
            return AdvancedIndicatorForecastResult(
                indicator_code=code,
                status="FAILED",
                forecast_origin=frame.index[-1].date(),
                historical_observations=len(history),
                champion_model_name=champion.model_name,
                champion_model_family=champion.model_family,
                model_results=model_results_tuple,
                ensemble_weights=weights,
                diagnostic="Final ensemble could not produce a forecast path",
            )

        confidence = self._confidence_score(
            historical_observations=len(history),
            champion=champion,
            ensemble_weights=weights,
            points=points,
        )
        status = "AVAILABLE_WITH_WARNINGS" if forecast_warnings else "AVAILABLE"
        diagnostic_parts = [
            f"Champion={champion.model_name}",
            f"Ensemble models={len(weights)}",
        ]
        if forecast_warnings:
            diagnostic_parts.append(f"Final forecast warnings={forecast_warnings}")

        return AdvancedIndicatorForecastResult(
            indicator_code=code,
            status=status,
            forecast_origin=frame.index[-1].date(),
            historical_observations=len(history),
            champion_model_name=champion.model_name,
            champion_model_family=champion.model_family,
            model_results=model_results_tuple,
            ensemble_weights=weights,
            forecast_points=points,
            confidence_score=confidence,
            diagnostic="; ".join(diagnostic_parts),
        )

    def _backtest_model(
        self,
        frame: pd.DataFrame,
        target: str,
        specification: MacroModelSpecification,
    ) -> tuple[tuple[_BacktestMetric, ...], str | None]:
        results: list[_BacktestMetric] = []
        for horizon, _weight in self._horizon_weights:
            try:
                results.append(self._backtest_horizon(frame, target, specification, horizon))
            except ImportError:
                return (), "OPTIONAL_DEPENDENCY_UNAVAILABLE"
        return tuple(results), None

    def _backtest_horizon(
        self,
        frame: pd.DataFrame,
        target: str,
        specification: MacroModelSpecification,
        horizon: int,
    ) -> _BacktestMetric:
        forecasts: list[float] = []
        actuals: list[float] = []
        origin_values: list[float] = []
        warning_count = 0
        failure_count = 0
        first_origin = self._minimum_training_observations - 1
        last_origin = len(frame) - horizon - 1

        if last_origin < first_origin:
            return _BacktestMetric(horizon, 0, None, None, None, None, 0, 0)

        for origin in range(first_origin, last_origin + 1):
            origin_value = frame[target].iloc[origin]
            actual = frame[target].iloc[origin + horizon]
            if pd.isna(origin_value) or pd.isna(actual):
                continue
            try:
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter("error")
                    warnings.simplefilter("always", SingularMatrixWarning)
                    warnings.simplefilter("always", ConvergenceWarning)
                    warnings.simplefilter("always", EstimationWarning)
                    forecast = self._forecast_at_origin(
                        frame,
                        target,
                        specification,
                        origin,
                        horizon,
                    )
                warning_count += sum(
                    1
                    for item in captured
                    if issubclass(
                        item.category,
                        (SingularMatrixWarning, ConvergenceWarning, EstimationWarning),
                    )
                )
            except ImportError:
                raise
            except (
                Warning,
                ValueError,
                TypeError,
                np.linalg.LinAlgError,
                RuntimeError,
                OverflowError,
            ):
                failure_count += 1
                continue
            if not math.isfinite(forecast):
                failure_count += 1
                continue
            forecasts.append(float(forecast))
            actuals.append(float(actual))
            origin_values.append(float(origin_value))

        if len(forecasts) < self._minimum_backtest_observations:
            return _BacktestMetric(
                horizon,
                len(forecasts),
                None,
                None,
                None,
                None,
                warning_count,
                failure_count,
            )

        forecast_array = np.asarray(forecasts, dtype=float)
        actual_array = np.asarray(actuals, dtype=float)
        origin_array = np.asarray(origin_values, dtype=float)
        errors = forecast_array - actual_array
        direction_forecast = np.sign(forecast_array - origin_array)
        direction_actual = np.sign(actual_array - origin_array)

        return _BacktestMetric(
            horizon=horizon,
            observations=len(forecasts),
            rmse=float(np.sqrt(np.mean(np.square(errors)))),
            mae=float(np.mean(np.abs(errors))),
            bias=float(np.mean(errors)),
            directional_accuracy=float(np.mean(direction_forecast == direction_actual)),
            warning_count=warning_count,
            failure_count=failure_count,
        )

    def _forecast_at_origin(
        self,
        frame: pd.DataFrame,
        target: str,
        specification: MacroModelSpecification,
        origin: int,
        horizon: int,
    ) -> float:
        if specification.mode == "UNIVARIATE":
            history = frame[target].iloc[: origin + 1].dropna().astype(float)
            if len(history) < self._minimum_training_observations:
                raise ValueError("Insufficient univariate history")
            return self._forecast_univariate(history, specification, horizon)
        return self._forecast_direct(frame, target, specification, origin, horizon)

    @staticmethod
    def _forecast_univariate(
        history: pd.Series,
        specification: MacroModelSpecification,
        horizon: int,
    ) -> float:
        values = history.to_numpy(dtype=float)
        family = specification.family
        parameters = dict(specification.parameters)

        if family == "NAIVE":
            return float(values[-1])
        if family == "DRIFT":
            if len(values) < 2:
                raise ValueError("DRIFT requires at least two observations")
            drift = (values[-1] - values[0]) / (len(values) - 1)
            return float(values[-1] + drift * horizon)
        if family == "AR":
            lags = int(parameters.get("lags", "1"))
            fitted = AutoReg(values, lags=lags, trend="ct").fit()
            forecast = fitted.predict(
                start=len(values),
                end=len(values) + horizon - 1,
                dynamic=False,
            )
            return float(forecast[-1])
        if family == "ARIMA":
            order = tuple(int(value) for value in parameters["order"].split(","))
            if len(order) != 3:
                raise ValueError("Invalid ARIMA order")
            fitted = ARIMA(
                values,
                order=(order[0], order[1], order[2]),
                trend="t" if order[1] > 0 else "ct",
            ).fit()
            return float(fitted.forecast(steps=horizon)[-1])
        if family == "ETS":
            fitted = ExponentialSmoothing(
                values,
                trend="add",
                damped_trend=True,
                seasonal=None,
                initialization_method="estimated",
            ).fit(optimized=True)
            return float(fitted.forecast(horizon)[-1])
        raise ValueError(f"Unsupported univariate family: {family}")

    def _forecast_direct(
        self,
        frame: pd.DataFrame,
        target: str,
        specification: MacroModelSpecification,
        origin: int,
        horizon: int,
    ) -> float:
        x_train, y_train, x_predict = self._direct_training_data(
            frame,
            target,
            specification,
            origin,
            horizon,
        )
        minimum_rows = 20 if specification.family == "ARDL" else 18
        if len(y_train) < minimum_rows:
            raise ValueError("Insufficient complete multivariate observations")

        if specification.family == "ARDL":
            return self._ols_predict(x_train, y_train, x_predict)
        if specification.family == "RIDGE":
            alpha = float(dict(specification.parameters).get("alpha", "1.0"))
            return self._ridge_predict(x_train, y_train, x_predict, alpha=alpha)
        if specification.family == "ELASTIC_NET":
            parameters = dict(specification.parameters)
            return self._elastic_net_predict(
                x_train,
                y_train,
                x_predict,
                alpha=float(parameters.get("alpha", "0.05")),
                l1_ratio=float(parameters.get("l1_ratio", "0.25")),
            )
        if specification.family == "GRADIENT_BOOSTING":
            try:
                from sklearn.ensemble import GradientBoostingRegressor
            except ImportError as exc:
                raise ImportError("scikit-learn is not installed") from exc
            parameters = dict(specification.parameters)
            model = GradientBoostingRegressor(
                n_estimators=int(parameters.get("n_estimators", "100")),
                max_depth=int(parameters.get("max_depth", "2")),
                learning_rate=0.05,
                loss="huber",
                random_state=0,
            )
            model.fit(x_train, y_train)
            return float(model.predict(x_predict.reshape(1, -1))[0])
        raise ValueError(f"Unsupported direct family: {specification.family}")

    def _direct_training_data(
        self,
        frame: pd.DataFrame,
        target: str,
        specification: MacroModelSpecification,
        origin: int,
        horizon: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x_predict = self._feature_vector(frame, target, specification, origin)
        training_x: list[np.ndarray] = []
        training_y: list[float] = []
        max_feature_lag = self._max_feature_lag(specification)
        last_feature_origin = origin - horizon

        for feature_origin in range(max_feature_lag, last_feature_origin + 1):
            target_position = feature_origin + horizon
            target_value = frame[target].iloc[target_position]
            if pd.isna(target_value):
                continue
            try:
                features = self._feature_vector(
                    frame,
                    target,
                    specification,
                    feature_origin,
                )
            except ValueError:
                continue
            training_x.append(features)
            training_y.append(float(target_value))

        if not training_x:
            raise ValueError("No complete direct-model training rows")

        return (
            np.vstack(training_x).astype(float),
            np.asarray(training_y, dtype=float),
            x_predict.astype(float),
        )

    def _feature_vector(
        self,
        frame: pd.DataFrame,
        target: str,
        specification: MacroModelSpecification,
        position: int,
    ) -> np.ndarray:
        values: list[float] = []

        if specification.family == "ARDL":
            for lag in self._ARDL_TARGET_LAGS:
                values.append(self._value_at(frame, target, position - lag))
            for driver in self._TARGET_DRIVER_MAP[target]:
                for lag in self._ARDL_DRIVER_LAGS:
                    values.append(self._value_at(frame, driver, position - lag))
        else:
            for column in frame.columns:
                for lag in self._FULL_FEATURE_LAGS:
                    values.append(self._value_at(frame, column, position - lag))

        current = self._value_at(frame, target, position)
        lag_1 = self._value_at(frame, target, position - 1)
        lag_3 = self._value_at(frame, target, position - 3)
        lag_6 = self._value_at(frame, target, position - 6)
        values.extend((current - lag_1, current - lag_3, current - lag_6))
        return np.asarray(values, dtype=float)

    def _max_feature_lag(self, specification: MacroModelSpecification) -> int:
        if specification.family == "ARDL":
            return max(max(self._ARDL_TARGET_LAGS), max(self._ARDL_DRIVER_LAGS), 6)
        return max(max(self._FULL_FEATURE_LAGS), 6)

    @staticmethod
    def _value_at(frame: pd.DataFrame, column: str, position: int) -> float:
        if position < 0:
            raise ValueError("Insufficient lag history")
        value = frame[column].iloc[position]
        if pd.isna(value):
            raise ValueError("Missing lagged feature")
        return float(value)

    @staticmethod
    def _ols_predict(
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_predict: np.ndarray,
    ) -> float:
        x_mean = x_train.mean(axis=0)
        x_std = x_train.std(axis=0)
        x_std = np.where(x_std < 1e-12, 1.0, x_std)
        x_scaled = (x_train - x_mean) / x_std
        x_predict_scaled = (x_predict - x_mean) / x_std
        x_design = np.column_stack((np.ones(len(x_scaled)), x_scaled))
        beta, *_ = np.linalg.lstsq(x_design, y_train, rcond=None)
        return float(np.concatenate(([1.0], x_predict_scaled)) @ beta)

    @staticmethod
    def _ridge_predict(
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_predict: np.ndarray,
        *,
        alpha: float,
    ) -> float:
        x_mean = x_train.mean(axis=0)
        x_std = x_train.std(axis=0)
        x_std = np.where(x_std < 1e-12, 1.0, x_std)
        y_mean = float(y_train.mean())
        x_scaled = (x_train - x_mean) / x_std
        prediction_scaled = (x_predict - x_mean) / x_std
        y_centered = y_train - y_mean
        gram = x_scaled.T @ x_scaled
        penalty = np.eye(gram.shape[0], dtype=float) * max(alpha, 0.0)
        beta = np.linalg.solve(gram + penalty, x_scaled.T @ y_centered)
        return float(y_mean + prediction_scaled @ beta)

    @staticmethod
    def _elastic_net_predict(
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_predict: np.ndarray,
        *,
        alpha: float,
        l1_ratio: float,
        maximum_iterations: int = 1000,
        tolerance: float = 1e-7,
    ) -> float:
        if not 0.0 <= l1_ratio <= 1.0:
            raise ValueError("l1_ratio must be in [0, 1]")

        x_mean = x_train.mean(axis=0)
        x_std = x_train.std(axis=0)
        x_std = np.where(x_std < 1e-12, 1.0, x_std)
        y_mean = float(y_train.mean())
        y_std = float(y_train.std())
        if y_std < 1e-12:
            return y_mean

        x_scaled = (x_train - x_mean) / x_std
        y_scaled = (y_train - y_mean) / y_std
        prediction_scaled = (x_predict - x_mean) / x_std
        beta = np.zeros(x_scaled.shape[1], dtype=float)
        n = float(len(y_scaled))
        l1_penalty = max(alpha, 0.0) * l1_ratio
        l2_penalty = max(alpha, 0.0) * (1.0 - l1_ratio)
        column_norm = np.sum(np.square(x_scaled), axis=0) / n

        for _iteration in range(maximum_iterations):
            previous = beta.copy()
            prediction = x_scaled @ beta
            for column in range(x_scaled.shape[1]):
                residual = y_scaled - prediction + x_scaled[:, column] * beta[column]
                rho = float(np.dot(x_scaled[:, column], residual) / n)
                denominator = float(column_norm[column] + l2_penalty)
                updated = AdvancedMacroForecastingService._soft_threshold(
                    rho,
                    l1_penalty,
                ) / max(denominator, 1e-12)
                prediction += x_scaled[:, column] * (updated - beta[column])
                beta[column] = updated
            if float(np.max(np.abs(beta - previous))) <= tolerance:
                break

        return float(y_mean + y_std * (prediction_scaled @ beta))

    @staticmethod
    def _soft_threshold(value: float, penalty: float) -> float:
        if value > penalty:
            return value - penalty
        if value < -penalty:
            return value + penalty
        return 0.0

    @staticmethod
    def _relative_rmse(rmse: float | None, naive_rmse: float | None) -> float | None:
        if rmse is None or naive_rmse is None:
            return None
        if math.isclose(naive_rmse, 0.0, abs_tol=1e-12):
            return 1.0 if math.isclose(rmse, 0.0, abs_tol=1e-12) else None
        return rmse / naive_rmse

    def _select_champion(
        self,
        results: tuple[MacroModelBacktestResult, ...],
    ) -> MacroModelBacktestResult | None:
        available = tuple(
            item for item in results if item.available and item.weighted_relative_score is not None
        )
        if not available:
            return None

        best = min(
            available,
            key=lambda item: (
                float(item.weighted_relative_score),
                self._registry.get(item.model_name).complexity_score,
            ),
        )
        naive = next((item for item in available if item.model_name == "NAIVE"), None)
        if (
            naive is not None
            and best.model_name != "NAIVE"
            and (
                best.improvement_vs_naive is None
                or best.improvement_vs_naive < self._minimum_material_improvement
            )
        ):
            return naive
        return best

    def _ensemble_weights(
        self,
        results: tuple[MacroModelBacktestResult, ...],
        champion: MacroModelBacktestResult,
    ) -> tuple[EnsembleModelWeight, ...]:
        eligible = [
            item
            for item in results
            if item.available
            and item.weighted_relative_score is not None
            and item.weighted_relative_score <= 1.15
        ]
        if champion not in eligible:
            eligible.append(champion)
        eligible.sort(
            key=lambda item: (
                float(item.weighted_relative_score or math.inf),
                self._registry.get(item.model_name).complexity_score,
            )
        )
        eligible = eligible[: self._maximum_ensemble_models]

        raw = np.asarray(
            [1.0 / max(float(item.weighted_relative_score or 1.0), 0.05) ** 2 for item in eligible],
            dtype=float,
        )
        if not len(raw) or not np.isfinite(raw).all() or raw.sum() <= 0.0:
            return ()

        normalized = self._cap_weights(raw / raw.sum(), cap=0.50)
        return tuple(
            EnsembleModelWeight(
                model_name=item.model_name,
                model_family=item.model_family,
                weight=float(weight),
                weighted_relative_score=float(item.weighted_relative_score or 1.0),
            )
            for item, weight in zip(eligible, normalized, strict=True)
        )

    @staticmethod
    def _cap_weights(weights: np.ndarray, *, cap: float) -> np.ndarray:
        result = weights.astype(float).copy()
        for _ in range(10):
            over = result > cap
            if not np.any(over):
                break
            excess = float(np.sum(result[over] - cap))
            result[over] = cap
            under = ~over
            if not np.any(under):
                break
            under_total = float(result[under].sum())
            if under_total <= 0.0:
                result[under] += excess / float(np.sum(under))
            else:
                result[under] += excess * result[under] / under_total
        total = float(result.sum())
        return result / total if total > 0.0 else result

    def _forecast_ensemble(
        self,
        frame: pd.DataFrame,
        target: str,
        weights: tuple[EnsembleModelWeight, ...],
        results: tuple[MacroModelBacktestResult, ...],
        forecast_horizon: int,
    ) -> tuple[tuple[AdvancedForecastPoint, ...], int]:
        origin = len(frame) - 1
        origin_date = frame.index[origin]
        results_by_name = {item.model_name: item for item in results}
        points: list[AdvancedForecastPoint] = []
        warning_count = 0

        for horizon in range(1, forecast_horizon + 1):
            model_values: list[tuple[float, float, str]] = []
            for weight in weights:
                specification = self._registry.get(weight.model_name)
                try:
                    value = self._forecast_at_origin(
                        frame,
                        target,
                        specification,
                        origin,
                        horizon,
                    )
                except (
                    ImportError,
                    Warning,
                    ValueError,
                    TypeError,
                    np.linalg.LinAlgError,
                    RuntimeError,
                    OverflowError,
                ):
                    warning_count += 1
                    continue
                if math.isfinite(value):
                    model_values.append((float(value), weight.weight, weight.model_name))

            if not model_values:
                break

            total_weight = sum(item[1] for item in model_values)
            point_forecast = sum(item[0] * item[1] for item in model_values) / total_weight
            dispersion = math.sqrt(
                sum(item[1] * (item[0] - point_forecast) ** 2 for item in model_values)
                / total_weight
            )

            weighted_rmse = 0.0
            rmse_weight = 0.0
            for _value, raw_weight, model_name in model_values:
                rmse = self._interpolated_rmse(results_by_name[model_name], horizon)
                if rmse is not None:
                    weighted_rmse += raw_weight * rmse
                    rmse_weight += raw_weight
            rmse_component = weighted_rmse / rmse_weight if rmse_weight > 0.0 else 0.0
            sigma = math.sqrt(rmse_component**2 + dispersion**2)
            target_period = origin_date + MonthEnd(horizon)

            points.append(
                AdvancedForecastPoint(
                    horizon_months=horizon,
                    forecast_origin=origin_date.date(),
                    target_period=target_period.date(),
                    point_forecast=float(point_forecast),
                    lower_80=float(point_forecast - 1.2815515655446004 * sigma),
                    upper_80=float(point_forecast + 1.2815515655446004 * sigma),
                    lower_95=float(point_forecast - 1.959963984540054 * sigma),
                    upper_95=float(point_forecast + 1.959963984540054 * sigma),
                )
            )

        return tuple(points), warning_count

    @staticmethod
    def _interpolated_rmse(
        result: MacroModelBacktestResult,
        horizon: int,
    ) -> float | None:
        available = sorted(
            ((item.horizon_months, item.rmse) for item in result.metrics if item.rmse is not None),
            key=lambda item: item[0],
        )
        if not available:
            return None

        exact = next((rmse for candidate, rmse in available if candidate == horizon), None)
        if exact is not None:
            return float(exact)

        lower = [item for item in available if item[0] < horizon]
        upper = [item for item in available if item[0] > horizon]
        if not lower:
            return float(upper[0][1])
        if not upper:
            return float(lower[-1][1])

        h0, r0 = lower[-1]
        h1, r1 = upper[0]
        fraction = (horizon - h0) / (h1 - h0)
        return float(r0 + (r1 - r0) * fraction)

    @staticmethod
    def _confidence_score(
        *,
        historical_observations: int,
        champion: MacroModelBacktestResult,
        ensemble_weights: tuple[EnsembleModelWeight, ...],
        points: tuple[AdvancedForecastPoint, ...],
    ) -> float:
        history_score = min(1.0, historical_observations / 120.0)
        improvement = max(
            0.0,
            min(1.0, (champion.improvement_vs_naive or 0.0) / 0.20),
        )
        model_score = min(1.0, len(ensemble_weights) / 4.0)
        interval_scores: list[float] = []
        for point in points:
            if point.lower_80 is None or point.upper_80 is None:
                continue
            width = point.upper_80 - point.lower_80
            scale = max(abs(point.point_forecast), 1.0)
            interval_scores.append(1.0 / (1.0 + width / scale))
        stability = sum(interval_scores) / len(interval_scores) if interval_scores else 0.0
        value = 100.0 * (
            0.25 * history_score + 0.30 * improvement + 0.25 * model_score + 0.20 * stability
        )
        return round(max(0.0, min(100.0, value)), 1)

    @classmethod
    def _frame(cls, dataset: EconometricMonthlyDataset) -> pd.DataFrame:
        records = [
            {
                "PERIOD": row.period,
                "FX_SELL": cls._float_or_nan(row.fx_sell),
                "TPM": cls._float_or_nan(row.tpm),
                "TBP": cls._float_or_nan(row.tbp),
                "TRI_CRC_12M": cls._float_or_nan(row.tri_crc_12m),
                "TRI_USD_12M": cls._float_or_nan(row.tri_usd_12m),
                "INFLATION": cls._float_or_nan(row.inflation),
                "IMAE": cls._float_or_nan(row.imae),
            }
            for row in dataset.rows
        ]
        if not records:
            return pd.DataFrame(columns=tuple(cls.COLUMN_MAPPING.values()), dtype=float)
        frame = pd.DataFrame.from_records(records).set_index("PERIOD").sort_index()
        frame.index = pd.to_datetime(frame.index)
        return frame.astype(float)

    @staticmethod
    def _float_or_nan(value: object) -> float:
        if value is None:
            return float("nan")
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return float("nan")

    @staticmethod
    def _last_observed_position(series: pd.Series) -> int | None:
        positions = np.flatnonzero(~series.isna().to_numpy())
        return int(positions[-1]) if len(positions) else None
