from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_macro_feature_reader import (
    SUGEFMacroFeatureReader,
)
from aip.product.configured.repositories.economic_historical_repository import (
    EconomicHistoricalRepository,
)
from aip.product.economic.advanced_forecasting import AdvancedIndicatorForecastResult
from aip.product.economic.econometric_dataset import EconometricMonthlyDataset
from aip.product.economic.econometric_dataset_builder import EconometricDatasetBuilder

if TYPE_CHECKING:
    from aip.product.economic.advanced_forecasting_service import (
        AdvancedMacroForecastingService,
    )


class ConfiguredAdvancedMacroForecastingService:
    """Forecast lab over BCCR targets enriched with lag-safe SUGEF features."""

    def __init__(
        self,
        *,
        repository: EconomicHistoricalRepository | None = None,
        forecasting_service: AdvancedMacroForecastingService | None = None,
        sugef_config: SUGEFFinancialSourceConfig | None = None,
    ) -> None:
        self._repository = repository or EconomicHistoricalRepository()
        self._dataset_builder = EconometricDatasetBuilder(self._repository)
        self._forecasting_service = forecasting_service
        self._sugef_reader = (
            SUGEFMacroFeatureReader(sugef_config) if sugef_config is not None else None
        )
        self._cached_dataset: EconometricMonthlyDataset | None = None
        self._cached_signature: tuple[tuple[str, date | None], ...] | None = None
        self._result_cache: dict[
            tuple[tuple[tuple[str, date | None], ...], str, int], AdvancedIndicatorForecastResult
        ] = {}

    def evaluate_indicator(
        self,
        indicator_code: str,
        *,
        forecast_horizon: int = 12,
        force_refresh: bool = False,
    ) -> AdvancedIndicatorForecastResult:
        signature = self._history_signature()
        if force_refresh or self._cached_signature != signature:
            self._cached_dataset = None
            self._result_cache.clear()
            self._cached_signature = signature
        code = indicator_code.strip().upper()
        cache_key = (signature, code, forecast_horizon)
        if not force_refresh and cache_key in self._result_cache:
            return self._result_cache[cache_key]
        dataset = self._dataset()
        result = self._forecasting_engine().evaluate(
            dataset,
            code,
            forecast_horizon=forecast_horizon,
        )
        self._result_cache[cache_key] = result
        return result

    def _forecasting_engine(self) -> AdvancedMacroForecastingService:
        if self._forecasting_service is None:
            from aip.product.economic.advanced_forecasting_service import (
                AdvancedMacroForecastingService,
            )

            self._forecasting_service = AdvancedMacroForecastingService()
        return self._forecasting_service

    def dataset(self) -> EconometricMonthlyDataset:
        """Expose the immutable normalized dataset for diagnostics/audit."""
        return self._dataset()

    def _dataset(self) -> EconometricMonthlyDataset:
        if self._cached_dataset is None:
            dataset = self._dataset_builder.build_monthly(include_incomplete=True)
            self._cached_dataset = self._enrich_with_sugef_features(dataset)
        return self._cached_dataset

    def _enrich_with_sugef_features(
        self,
        dataset: EconometricMonthlyDataset,
    ) -> EconometricMonthlyDataset:
        if self._sugef_reader is None or dataset.last_period is None:
            return dataset
        try:
            feature_result = self._sugef_reader.read(dataset.last_period)
        except (ConnectionError, TimeoutError, ValueError, OSError):
            return dataset
        if not feature_result.points:
            return dataset
        existing_keys = {
            (point.indicator_code, point.period, point.observation_date)
            for point in dataset.data_points
        }
        additional = tuple(
            point
            for point in feature_result.points
            if (point.indicator_code, point.period, point.observation_date) not in existing_keys
        )
        if not additional:
            return dataset
        data_points = tuple(
            sorted(
                (*dataset.data_points, *additional),
                key=lambda point: (
                    point.period,
                    point.indicator_code,
                    point.observation_date,
                ),
            )
        )
        feature_codes = tuple(
            code
            for code in SUGEFMacroFeatureReader.FEATURE_CODES
            if any(point.indicator_code == code for point in additional)
        )
        return EconometricMonthlyDataset(
            rows=dataset.rows,
            indicator_codes=(*dataset.indicator_codes, *feature_codes),
            first_period=dataset.first_period,
            last_period=dataset.last_period,
            data_points=data_points,
        )

    def _history_signature(self) -> tuple[tuple[str, date | None], ...]:
        return tuple(
            (code, self._repository.latest_available_date(code))
            for code in EconometricDatasetBuilder.MONTHLY_INDICATORS
        )
