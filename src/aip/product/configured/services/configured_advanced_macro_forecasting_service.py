from __future__ import annotations

from datetime import date

from aip.product.configured.repositories.economic_historical_repository import (
    EconomicHistoricalRepository,
)
from aip.product.economic.advanced_forecasting import AdvancedIndicatorForecastResult
from aip.product.economic.advanced_forecasting_service import AdvancedMacroForecastingService
from aip.product.economic.econometric_dataset import EconometricMonthlyDataset
from aip.product.economic.econometric_dataset_builder import EconometricDatasetBuilder


class ConfiguredAdvancedMacroForecastingService:
    """Application service exposing the forecast lab over persisted BCCR history."""

    def __init__(
        self,
        *,
        repository: EconomicHistoricalRepository | None = None,
        forecasting_service: AdvancedMacroForecastingService | None = None,
    ) -> None:
        self._repository = repository or EconomicHistoricalRepository()
        self._dataset_builder = EconometricDatasetBuilder(self._repository)
        self._forecasting_service = forecasting_service or AdvancedMacroForecastingService()
        self._cached_dataset: EconometricMonthlyDataset | None = None
        self._cached_signature: tuple[tuple[str, date | None], ...] | None = None
        self._result_cache: dict[tuple[tuple[tuple[str, date | None], ...], str, int], AdvancedIndicatorForecastResult] = {}

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
        result = self._forecasting_service.evaluate(
            dataset,
            code,
            forecast_horizon=forecast_horizon,
        )
        self._result_cache[cache_key] = result
        return result

    def dataset(self) -> EconometricMonthlyDataset:
        """Expose the immutable normalized dataset for diagnostics/audit."""
        return self._dataset()

    def _dataset(self) -> EconometricMonthlyDataset:
        if self._cached_dataset is None:
            self._cached_dataset = self._dataset_builder.build_monthly(include_incomplete=True)
        return self._cached_dataset

    def _history_signature(self) -> tuple[tuple[str, date | None], ...]:
        return tuple(
            (code, self._repository.latest_available_date(code))
            for code in EconometricDatasetBuilder.MONTHLY_INDICATORS
        )
