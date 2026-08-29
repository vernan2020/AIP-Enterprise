from __future__ import annotations

import math
import warnings

import numpy as np
from pandas.tseries.offsets import MonthEnd
from statsmodels.tools.sm_exceptions import (
    ConvergenceWarning,
    EstimationWarning,
    SingularMatrixWarning,
)

from aip.product.economic.econometric_dataset import (
    EconometricMonthlyDataset,
)
from aip.product.economic.econometric_diagnostics_service import (
    EconometricDiagnosticsService,
)
from aip.product.economic.econometric_forecast_governance import (
    ForecastGovernanceResult,
)
from aip.product.economic.econometric_forecast_governance_service import (
    ForecastGovernanceService,
)
from aip.product.economic.econometric_forecast_service import (
    EconometricForecastService,
    _SelectedSpecification,
)
from aip.product.economic.institutional_forecast import (
    InstitutionalForecastPoint,
    InstitutionalForecastResult,
    InstitutionalHorizonMetric,
)


class InstitutionalForecastService:
    """
    Orquestador institucional de forecast económico.

    Responsabilidades:
    - ejecutar Forecast Governance;
    - recuperar el modelo gobernado;
    - reestimar ese modelo con toda la historia disponible;
    - construir trayectoria mensual;
    - incorporar métricas multi-horizonte;
    - impedir uso automático de REVIEW_REQUIRED.

    Este servicio NO:
    - modifica datos históricos;
    - imputa observaciones;
    - modifica EconometricForecastService;
    - contiene lógica de UI;
    - aprueba automáticamente modelos bajo revisión.
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
        governance_service: (
            ForecastGovernanceService
            | None
        ) = None,
        confidence_level: float = 0.95,
        minimum_horizon: int = 1,
        maximum_horizon: int = 12,
    ) -> None:
        if not (
            0.50
            < confidence_level
            < 1.0
        ):
            raise ValueError(
                "confidence_level must be "
                "between 0.50 and 1.0"
            )

        if minimum_horizon < 1:
            raise ValueError(
                "minimum_horizon must be >= 1"
            )

        if (
            maximum_horizon
            < minimum_horizon
        ):
            raise ValueError(
                "maximum_horizon must be "
                ">= minimum_horizon"
            )

        self._governance_service = (
            governance_service
            or ForecastGovernanceService()
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
    ) -> InstitutionalForecastResult:
        code = (
            indicator_code
            .strip()
            .upper()
        )

        self._validate_horizon(
            horizon_months
        )

        if (
            code
            not in self._SUPPORTED_INDICATORS
        ):
            return self._unavailable(
                indicator_code=code,
                horizon_months=(
                    horizon_months
                ),
                diagnostic=(
                    "Unsupported institutional "
                    "forecast indicator"
                ),
                reason_codes=(
                    "UNSUPPORTED_INDICATOR",
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
            return self._unavailable(
                indicator_code=code,
                horizon_months=(
                    horizon_months
                ),
                diagnostic=(
                    "No historical observations "
                    "available"
                ),
                reason_codes=(
                    "INSUFFICIENT_DATA",
                ),
            )

        temporal_metadata = (
            self._resolve_temporal_metadata(
                dataset=dataset,
                indicator_code=code,
                series=series,
            )
        )

        governance = (
            self._governance_service
            .evaluate(
                dataset,
                code,
            )
        )

        if (
            governance.governance_model_name
            is None
            or governance.governance_model_family
            is None
        ):
            return self._from_unavailable_governance(
                governance=governance,
                series=series,
                horizon_months=(
                    horizon_months
                ),
            )

        model_result = (
            governance.model_result(
                governance.governance_model_name
            )
        )

        if model_result is None:
            return self._unavailable(
                indicator_code=code,
                horizon_months=(
                    horizon_months
                ),
                diagnostic=(
                    "Governance model result "
                    "not found"
                ),
                reason_codes=(
                    "GOVERNANCE_MODEL_MISSING",
                ),
                governance=governance,
                series=series,
            )

        try:
            specification = (
                self._specification_from_governance(
                    model_name=(
                        model_result.model_name
                    ),
                    model_family=(
                        model_result.model_family
                    ),
                    parameters=(
                        model_result.parameters
                    ),
                )
            )
        except (
            ValueError,
            TypeError,
        ) as exc:
            return self._unavailable(
                indicator_code=code,
                horizon_months=(
                    horizon_months
                ),
                diagnostic=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
                reason_codes=(
                    "INVALID_GOVERNANCE_MODEL",
                ),
                governance=governance,
                series=series,
            )

        estimation_warning_messages: list[
            str
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
                    EconometricForecastService
                    ._forecast_multi_step(
                        series=series,
                        specification=(
                            specification
                        ),
                        horizon_months=(
                            horizon_months
                        ),
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
                    estimation_warning_messages.append(
                        f"{item.category.__name__}: "
                        f"{item.message}"
                    )

        except (
            ValueError,
            TypeError,
            np.linalg.LinAlgError,
            RuntimeError,
        ) as exc:
            return self._unavailable(
                indicator_code=code,
                horizon_months=(
                    horizon_months
                ),
                diagnostic=(
                    "Final governed model "
                    "estimation failed: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
                reason_codes=(
                    "FINAL_ESTIMATION_FAILED",
                ),
                governance=governance,
                series=series,
            )

        if (
            len(forecasts)
            != horizon_months
        ):
            return self._unavailable(
                indicator_code=code,
                horizon_months=(
                    horizon_months
                ),
                diagnostic=(
                    "Governed forecast returned "
                    "an unexpected number of "
                    "projection points"
                ),
                reason_codes=(
                    "INVALID_FORECAST_LENGTH",
                ),
                governance=governance,
                series=series,
            )

        if not all(
            math.isfinite(
                float(value)
            )
            for value
            in forecasts
        ):
            return self._unavailable(
                indicator_code=code,
                horizon_months=(
                    horizon_months
                ),
                diagnostic=(
                    "Governed forecast contains "
                    "non-finite values"
                ),
                reason_codes=(
                    "NON_FINITE_FORECAST",
                ),
                governance=governance,
                series=series,
            )

        forecast_origin = (
            series.index[
                -1
            ]
        )

        last_observed_value = float(
            series.iloc[
                -1
            ]
        )

        horizon_metrics = tuple(
            InstitutionalHorizonMetric(
                horizon_months=(
                    metric.horizon_months
                ),
                observations=(
                    metric.observations
                ),
                rmse=metric.rmse,
                mae=metric.mae,
                bias=metric.bias,
                naive_rmse=(
                    metric.naive_rmse
                ),
                relative_rmse=(
                    metric.relative_rmse
                ),
            )
            for metric
            in model_result.horizons
        )

        points: list[
            InstitutionalForecastPoint
        ] = []

        z_score = (
            EconometricForecastService
            ._normal_quantile(
                self._confidence_level
            )
        )

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

            horizon_rmse = (
                self._rmse_for_projection_horizon(
                    model_result=model_result,
                    horizon=index,
                )
            )

            lower_bound = None
            upper_bound = None

            if (
                horizon_rmse is not None
                and math.isfinite(
                    horizon_rmse
                )
                and horizon_rmse >= 0.0
            ):
                margin = (
                    z_score
                    * horizon_rmse
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
                InstitutionalForecastPoint(
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

        result_status = (
            governance.status
        )

        result_reason_codes = list(
            governance.reason_codes
        )

        result_warnings = list(
            governance.warnings
        )

        if estimation_warning_messages:
            result_warnings.extend(
                estimation_warning_messages
            )

            if (
                "FINAL_ESTIMATION_WARNING"
                not in result_reason_codes
            ):
                result_reason_codes.append(
                    "FINAL_ESTIMATION_WARNING"
                )

            if (
                result_status
                == "APPROVED"
            ):
                result_status = (
                    "APPROVED_WITH_WARNINGS"
                )

        dynamic_status = None
        dynamic_ratio = None

        if (
            governance.dynamic_stability
            is not None
        ):
            dynamic_status = (
                governance
                .dynamic_stability
                .status
            )

            dynamic_ratio = (
                governance
                .dynamic_stability
                .stability_ratio
            )

        diagnostic_parts: list[str] = []

        if governance.diagnostic:
            diagnostic_parts.append(
                governance.diagnostic
            )

        if (
            result_status
            == "REVIEW_REQUIRED"
        ):
            diagnostic_parts.append(
                "Candidate forecast generated "
                "for analysis but blocked from "
                "automatic base-scenario use"
            )

        if estimation_warning_messages:
            diagnostic_parts.append(
                "Final governed estimation "
                f"produced "
                f"{len(estimation_warning_messages)} "
                "warning(s)"
            )

        return InstitutionalForecastResult(
            indicator_code=code,
            status=result_status,
            statistical_model_name=(
                governance
                .statistical_model_name
            ),
            statistical_model_family=(
                governance
                .statistical_model_family
            ),
            governance_model_name=(
                governance
                .governance_model_name
            ),
            governance_model_family=(
                governance
                .governance_model_family
            ),
            forecast_origin=(
                forecast_origin.date()
            ),
            last_observed_value=(
                last_observed_value
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
            weighted_relative_score=(
                governance
                .weighted_relative_score
            ),
            improvement_vs_naive=(
                governance
                .improvement_vs_naive
            ),
            materiality_threshold=(
                governance
                .materiality_threshold
            ),
            horizon_metrics=(
                horizon_metrics
            ),
            dynamic_stability_status=(
                dynamic_status
            ),
            dynamic_stability_ratio=(
                dynamic_ratio
            ),
            points=tuple(
                points
            ),
            reason_codes=tuple(
                result_reason_codes
            ),
            warnings=tuple(
                result_warnings
            ),
            data_as_of_date=(
                temporal_metadata[
                    "data_as_of_date"
                ]
            ),
            forecast_origin_period=(
                temporal_metadata[
                    "forecast_origin_period"
                ]
            ),
            data_lag_days=(
                temporal_metadata[
                    "data_lag_days"
                ]
            ),
            data_lag_months=(
                temporal_metadata[
                    "data_lag_months"
                ]
            ),
            is_current_period=(
                temporal_metadata[
                    "is_current_period"
                ]
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
        InstitutionalForecastResult,
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
    def _specification_from_governance(
        *,
        model_name: str,
        model_family: str,
        parameters: tuple[
            tuple[str, str],
            ...,
        ],
    ) -> _SelectedSpecification:
        parameter_map = dict(
            parameters
        )

        if model_family == "NAIVE":
            return _SelectedSpecification(
                model_name=model_name,
                family="NAIVE",
            )

        if model_family == "DRIFT":
            return _SelectedSpecification(
                model_name=model_name,
                family="DRIFT",
            )

        if model_family == "AR":
            raw_lags = (
                parameter_map.get(
                    "lags"
                )
                or parameter_map.get(
                    "ar_lags"
                )
            )

            if raw_lags is None:
                if model_name.startswith(
                    "AR_"
                ):
                    raw_lags = (
                        model_name.split(
                            "_",
                            1,
                        )[
                            1
                        ]
                    )
                else:
                    raw_lags = (
                        EconometricForecastService
                        ._infer_ar_lags_from_name(
                            model_name
                        )
                    )

            return _SelectedSpecification(
                model_name=model_name,
                family="AR",
                ar_lags=int(
                    raw_lags
                ),
            )

        if model_family == "ARIMA":
            raw_order = (
                parameter_map.get(
                    "order"
                )
            )

            if raw_order is not None:
                order = (
                    EconometricForecastService
                    ._parse_arima_order(
                        raw_order
                    )
                )

            elif model_name.startswith(
                "ARIMA_"
            ):
                parts = (
                    model_name
                    .replace(
                        "ARIMA_",
                        "",
                        1,
                    )
                    .split(
                        "_"
                    )
                )

                if len(parts) != 3:
                    raise ValueError(
                        "Invalid governed "
                        "ARIMA model name"
                    )

                order = tuple(
                    int(value)
                    for value
                    in parts
                )

            else:
                order = (
                    EconometricForecastService
                    ._infer_arima_order_from_name(
                        model_name
                    )
                )

            return _SelectedSpecification(
                model_name=model_name,
                family="ARIMA",
                arima_order=order,
            )

        raise ValueError(
            "Unsupported governed model family: "
            f"{model_family}"
        )

    def forecast_all_calendar_aligned(
        self,
        dataset: EconometricMonthlyDataset,
        *,
        horizon_months: int = 12,
    ) -> tuple[
        InstitutionalForecastResult,
        ...,
    ]:
        """
        Build forecasts aligned to one institutional
        calendar irrespective of publication lag.

        Statistical horizon and institutional scenario
        horizon are intentionally different concepts.

        An indicator with older information may require
        more statistical forecast steps in order to cover
        the same scenario calendar.

        Example for dataset as-of 2026-08-27:

        FX:
            origin 2026-08-31
            statistical horizon 12

        Inflation:
            origin 2026-07-31
            statistical horizon 13

        IMAE:
            origin 2026-06-30
            statistical horizon 14

        The returned institutional result nevertheless
        contains exactly horizon_months points on the
        common scenario calendar.
        """
        from dataclasses import replace

        from aip.product.economic.institutional_macro_scenario_calendar import (
            build_scenario_calendar,
            required_projection_horizon,
        )

        self._validate_horizon(
            horizon_months
        )

        dataset_as_of_date = (
            dataset.as_of_date
        )

        if dataset_as_of_date is None:
            raise ValueError(
                "Econometric dataset does not have "
                "an as-of date."
            )

        scenario_calendar = (
            build_scenario_calendar(
                dataset_as_of_date=(
                    dataset_as_of_date
                ),
                horizon_months=(
                    horizon_months
                ),
            )
        )

        scenario_periods = set(
            scenario_calendar
        )

        baseline_results = (
            self.forecast_all(
                dataset,
                horizon_months=(
                    horizon_months
                ),
            )
        )

        aligned_results: list[
            InstitutionalForecastResult
        ] = []

        for baseline in baseline_results:
            if not baseline.points:
                aligned_results.append(
                    baseline
                )
                continue

            forecast_origin_period = (
                baseline.forecast_origin_period
            )

            if forecast_origin_period is None:
                raise ValueError(
                    "Forecast result has points but "
                    "does not provide forecast origin "
                    f"for {baseline.indicator_code}."
                )

            required_horizon = (
                required_projection_horizon(
                    forecast_origin_period=(
                        forecast_origin_period
                    ),
                    scenario_calendar=(
                        scenario_calendar
                    ),
                )
            )

            candidate = baseline

            if (
                required_horizon
                > horizon_months
            ):
                candidate = self.forecast(
                    dataset,
                    baseline.indicator_code,
                    horizon_months=(
                        required_horizon
                    ),
                )

            selected_points = tuple(
                point
                for point
                in candidate.points
                if (
                    point.target_period
                    in scenario_periods
                )
            )

            if (
                len(selected_points)
                != horizon_months
            ):
                raise ValueError(
                    "Unable to align institutional "
                    "forecast calendar for "
                    f"{baseline.indicator_code}. "
                    f"Expected {horizon_months} "
                    "calendar points, found "
                    f"{len(selected_points)}."
                )

            selected_periods = tuple(
                point.target_period
                for point
                in selected_points
            )

            if (
                selected_periods
                != scenario_calendar
            ):
                raise ValueError(
                    "Institutional forecast calendar "
                    "is not contiguous for "
                    f"{baseline.indicator_code}."
                )

            institutional_points = tuple(
                replace(
                    point,
                    horizon=index,
                )
                for index, point
                in enumerate(
                    selected_points,
                    start=1,
                )
            )

            aligned_results.append(
                replace(
                    candidate,
                    horizon_months=(
                        horizon_months
                    ),
                    points=(
                        institutional_points
                    ),
                )
            )

        return tuple(
            aligned_results
        )

    @staticmethod
    def _rmse_for_projection_horizon(
        *,
        model_result,
        horizon: int,
    ) -> float | None:
        """
        Interpola de manera prudente el RMSE OOS entre
        los horizontes efectivamente validados:
        1, 3, 6 y 12 meses.

        Para horizontes intermedios se utiliza el RMSE
        del siguiente horizonte validado, evitando
        atribuir artificialmente menor incertidumbre.
        """

        ordered = sorted(
            (
                metric
                for metric
                in model_result.horizons
                if metric.rmse is not None
            ),
            key=lambda item: (
                item.horizon_months
            ),
        )

        if not ordered:
            return None

        for metric in ordered:
            if (
                horizon
                <= metric.horizon_months
            ):
                return float(
                    metric.rmse
                )

        return float(
            ordered[
                -1
            ].rmse
        )

    @staticmethod
    def _resolve_temporal_metadata(
        *,
        dataset: EconometricMonthlyDataset,
        indicator_code: str,
        series,
    ) -> dict[
        str,
        object,
    ]:
        """
        Resuelve las dos fechas semánticamente distintas:

        data_as_of_date:
            fecha real del dato utilizado.

        forecast_origin_period:
            bucket mensual desde el cual parte
            la proyección econométrica.

        El rezago se mide contra dataset.as_of_date,
        es decir, contra la fecha real más reciente
        disponible en el conjunto de información.
        """

        forecast_origin_period = (
            series.index[
                -1
            ].date()
        )

        point = (
            dataset.latest_data_point(
                indicator_code
            )
        )

        if point is not None:
            data_as_of_date = (
                point.observation_date
            )
        else:
            # Compatibilidad con datasets sintéticos
            # construidos directamente en tests.
            data_as_of_date = (
                forecast_origin_period
            )

        dataset_as_of_date = (
            dataset.as_of_date
            or data_as_of_date
        )

        lag_days = max(
            0,
            (
                dataset_as_of_date
                - data_as_of_date
            ).days,
        )

        lag_months = max(
            0,
            (
                dataset_as_of_date.year
                - data_as_of_date.year
            )
            * 12
            + (
                dataset_as_of_date.month
                - data_as_of_date.month
            ),
        )

        is_current_period = (
            data_as_of_date.year
            == dataset_as_of_date.year
            and data_as_of_date.month
            == dataset_as_of_date.month
        )

        return {
            "data_as_of_date": (
                data_as_of_date
            ),
            "forecast_origin_period": (
                forecast_origin_period
            ),
            "data_lag_days": (
                lag_days
            ),
            "data_lag_months": (
                lag_months
            ),
            "is_current_period": (
                is_current_period
            ),
        }

    def _from_unavailable_governance(
        self,
        *,
        governance: ForecastGovernanceResult,
        series,
        horizon_months: int,
    ) -> InstitutionalForecastResult:
        return self._unavailable(
            indicator_code=(
                governance.indicator_code
            ),
            horizon_months=(
                horizon_months
            ),
            diagnostic=(
                governance.diagnostic
                or (
                    "Forecast governance "
                    "is unavailable"
                )
            ),
            reason_codes=(
                governance.reason_codes
                or (
                    "GOVERNANCE_UNAVAILABLE",
                )
            ),
            governance=governance,
            series=series,
        )

    def _unavailable(
        self,
        *,
        indicator_code: str,
        horizon_months: int,
        diagnostic: str,
        reason_codes: tuple[
            str,
            ...,
        ],
        governance: (
            ForecastGovernanceResult
            | None
        ) = None,
        series=None,
    ) -> InstitutionalForecastResult:
        forecast_origin = None
        last_observed_value = None
        historical_observations = 0

        if (
            series is not None
            and not series.empty
        ):
            forecast_origin = (
                series.index[
                    -1
                ].date()
            )

            last_observed_value = float(
                series.iloc[
                    -1
                ]
            )

            historical_observations = len(
                series
            )

        return InstitutionalForecastResult(
            indicator_code=(
                indicator_code
            ),
            status="UNAVAILABLE",
            statistical_model_name=(
                governance
                .statistical_model_name
                if governance is not None
                else None
            ),
            statistical_model_family=(
                governance
                .statistical_model_family
                if governance is not None
                else None
            ),
            governance_model_name=(
                governance
                .governance_model_name
                if governance is not None
                else None
            ),
            governance_model_family=(
                governance
                .governance_model_family
                if governance is not None
                else None
            ),
            forecast_origin=(
                forecast_origin
            ),
            last_observed_value=(
                last_observed_value
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
            weighted_relative_score=(
                governance
                .weighted_relative_score
                if governance is not None
                else None
            ),
            improvement_vs_naive=(
                governance
                .improvement_vs_naive
                if governance is not None
                else None
            ),
            materiality_threshold=(
                governance
                .materiality_threshold
                if governance is not None
                else 0.0
            ),
            horizon_metrics=(),
            dynamic_stability_status=(
                governance
                .dynamic_stability
                .status
                if (
                    governance is not None
                    and governance
                    .dynamic_stability
                    is not None
                )
                else None
            ),
            dynamic_stability_ratio=(
                governance
                .dynamic_stability
                .stability_ratio
                if (
                    governance is not None
                    and governance
                    .dynamic_stability
                    is not None
                )
                else None
            ),
            points=(),
            reason_codes=(
                reason_codes
            ),
            warnings=(
                governance.warnings
                if governance is not None
                else ()
            ),
            diagnostic=(
                diagnostic
            ),
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
