from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from aip.product.configured.repositories.institutional_macro_scenario_repository import (
    InstitutionalMacroScenarioRepository,
)
from aip.product.economic.econometric_dataset import (
    EconometricMonthlyDataset,
)
from aip.product.economic.institutional_forecast import (
    InstitutionalForecastResult,
)
from aip.product.economic.institutional_forecast_service import (
    InstitutionalForecastService,
)
from aip.product.economic.institutional_macro_scenario import (
    InstitutionalMacroScenario,
    InstitutionalMacroScenarioIndicator,
    InstitutionalMacroScenarioPoint,
)


class InstitutionalMacroScenarioService:
    """
    Servicio de aplicación responsable de materializar una
    ejecución del Institutional Forecast Engine como una
    versión persistente y auditable de escenario.
    """

    _EXPECTED_INDICATORS = frozenset(
        {
            "FX_SELL",
            "TPM",
            "TBP",
            "TRI_CRC_12M",
            "TRI_USD_12M",
            "INFLATION",
            "IMAE",
        }
    )

    def __init__(
        self,
        *,
        forecast_service: InstitutionalForecastService | None = None,
        repository: InstitutionalMacroScenarioRepository | None = None,
    ) -> None:
        self._forecast_service = (
            forecast_service
            or InstitutionalForecastService(maximum_horizon=24)
        )

        self._repository = (
            repository
            or InstitutionalMacroScenarioRepository()
        )

    @property
    def repository(
        self,
    ) -> InstitutionalMacroScenarioRepository:
        return self._repository

    def create_draft(
        self,
        dataset: EconometricMonthlyDataset,
        *,
        horizon_months: int = 12,
        scenario_id: str | None = None,
        scenario_type: str = "BASE",
        created_by: str = "AIP_SYSTEM",
        description: str | None = None,
    ) -> InstitutionalMacroScenario:
        if dataset.as_of_date is None:
            raise ValueError(
                "Dataset does not contain a real as-of date"
            )

        normalized_type = (
            scenario_type
            .strip()
            .upper()
        )

        if normalized_type not in {
            "BASE",
            "ADVERSE",
            "SEVERE",
            "MANAGEMENT",
        }:
            raise ValueError(
                "Unsupported scenario_type: "
                f"{scenario_type}"
            )

        normalized_created_by = (
            created_by.strip()
        )

        if not normalized_created_by:
            raise ValueError(
                "created_by cannot be empty"
            )

        if scenario_id is None:
            scenario_id = (
                "MACRO-"
                + uuid4().hex.upper()
            )

        scenario_id = (
            scenario_id
            .strip()
            .upper()
        )

        if not scenario_id:
            raise ValueError(
                "scenario_id cannot be empty"
            )

        results = (
            self._forecast_service
            .forecast_all_calendar_aligned(
                dataset,
                horizon_months=horizon_months,
            )
        )

        self._validate_results(
            results,
            horizon_months=horizon_months,
        )

        version = (
            self._repository
            .next_version(
                scenario_id
            )
        )

        indicators = tuple(
            self._map_indicator(
                result
            )
            for result in results
        )

        scenario = InstitutionalMacroScenario(
            scenario_id=scenario_id,
            version=version,
            scenario_type=normalized_type,
            status="DRAFT",
            dataset_as_of_date=(
                dataset.as_of_date
            ),
            horizon_months=horizon_months,
            created_at=datetime.now(
                timezone.utc
            ),
            indicators=indicators,
            created_by=(
                normalized_created_by
            ),
            description=description,
        )

        self._repository.save(
            scenario
        )

        return scenario

    def _validate_results(
        self,
        results: tuple[
            InstitutionalForecastResult,
            ...,
        ],
        *,
        horizon_months: int,
    ) -> None:
        codes = {
            result.indicator_code
            for result in results
        }

        missing = (
            self._EXPECTED_INDICATORS
            - codes
        )

        unexpected = (
            codes
            - self._EXPECTED_INDICATORS
        )

        if missing:
            raise ValueError(
                "Institutional forecast is missing "
                "required indicators: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )

        if unexpected:
            raise ValueError(
                "Institutional forecast contains "
                "unexpected indicators: "
                + ", ".join(
                    sorted(
                        unexpected
                    )
                )
            )

        if len(results) != len(
            self._EXPECTED_INDICATORS
        ):
            raise ValueError(
                "Institutional forecast contains "
                "duplicate indicators"
            )

        for result in results:
            if result.status == "UNAVAILABLE":
                continue

            if (
                len(result.points)
                != horizon_months
            ):
                raise ValueError(
                    "Invalid forecast trajectory for "
                    f"{result.indicator_code}: expected "
                    f"{horizon_months} points, found "
                    f"{len(result.points)}"
                )

            horizons = tuple(
                point.horizon
                for point in result.points
            )

            expected_horizons = tuple(
                range(
                    1,
                    horizon_months + 1,
                )
            )

            if horizons != expected_horizons:
                raise ValueError(
                    "Non-contiguous forecast horizons for "
                    f"{result.indicator_code}"
                )

    @staticmethod
    def _map_indicator(
        result: InstitutionalForecastResult,
    ) -> InstitutionalMacroScenarioIndicator:
        points = tuple(
            InstitutionalMacroScenarioPoint(
                indicator_code=(
                    result.indicator_code
                ),
                horizon=point.horizon,
                target_period=point.target_period,
                point_forecast=(
                    point.point_forecast
                ),
                lower_bound=point.lower_bound,
                upper_bound=point.upper_bound,
                confidence_level=(
                    point.confidence_level
                ),
            )
            for point in result.points
        )

        return InstitutionalMacroScenarioIndicator(
            indicator_code=(
                result.indicator_code
            ),

            statistical_model_name=(
                result.statistical_model_name
            ),
            statistical_model_family=(
                result.statistical_model_family
            ),

            governance_model_name=(
                result.governance_model_name
            ),
            governance_model_family=(
                result.governance_model_family
            ),

            institutional_status=(
                result.status
            ),

            data_as_of_date=(
                result.data_as_of_date
            ),
            forecast_origin_period=(
                result.forecast_origin_period
            ),

            last_observed_value=(
                result.last_observed_value
            ),

            historical_observations=(
                result.historical_observations
            ),

            weighted_relative_score=(
                result.weighted_relative_score
            ),
            improvement_vs_naive=(
                result.improvement_vs_naive
            ),

            dynamic_stability_status=(
                result.dynamic_stability_status
            ),
            dynamic_stability_ratio=(
                result.dynamic_stability_ratio
            ),

            data_lag_days=(
                result.data_lag_days
            ),
            data_lag_months=(
                result.data_lag_months
            ),
            is_current_period=(
                result.is_current_period
            ),

            approved_for_base_scenario=(
                result.approved_for_base_scenario
            ),

            reason_codes=(
                result.reason_codes
            ),
            warnings=(
                result.warnings
            ),

            points=points,

            diagnostic=(
                result.diagnostic
            ),
        )
