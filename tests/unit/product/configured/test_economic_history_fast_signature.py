"""Fast macro history cache signatures preserve certified observations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from aip.product.configured.repositories.economic_historical_repository import (
    EconomicHistoricalRepository,
)
from aip.product.configured.repositories.economic_historical_store import (
    EconomicHistoricalStore,
)
from aip.product.configured.services.configured_advanced_macro_forecasting_service import (
    ConfiguredAdvancedMacroForecastingService,
)
from aip.product.economic.economic_history import EconomicHistoricalObservation
from aip.product.economic.econometric_dataset_builder import EconometricDatasetBuilder


def _observation(code: str, value: str, observed: date) -> EconomicHistoricalObservation:
    return EconomicHistoricalObservation(
        indicator_code=code,
        observation_date=observed,
        value=Decimal(value),
        source="BCCR",
        source_series_code=None,
        unit="percent",
        frequency="MONTHLY",
    )


def test_latest_values_and_dates_equal_previous_full_series_scan(tmp_path: Path) -> None:
    store = EconomicHistoricalStore(project_root=tmp_path)
    observations = (
        _observation("TPM", "3.25", date(2026, 8, 1)),
        _observation("TPM", "3.00", date(2026, 9, 1)),
        _observation("TBP", "3.62", date(2026, 8, 31)),
        _observation("FX_SELL", "452.88", date(2026, 8, 27)),
    )
    try:
        store.upsert_observations(observations)
        repository = EconomicHistoricalRepository(store=store)
        for code in ("TPM", "TBP", "FX_SELL"):
            expected = store.observations_for_series(indicator_code=code)[-1]
            assert store.latest_observation(indicator_code=code) == expected
            assert repository.latest_available_date(code) == expected.observation_date
        codes = ("TPM", "FX_SELL", "UNKNOWN", "TBP", "TPM")
        observed = repository.latest_available_dates(codes)
        assert observed == {
            "TPM": date(2026, 9, 1),
            "FX_SELL": date(2026, 8, 27),
            "UNKNOWN": None,
            "TBP": date(2026, 8, 31),
        }
        assert store.latest_observation(indicator_code="UNKNOWN") is None
        assert store.latest_observation(indicator_code="") is None
    finally:
        store.close()


def test_signature_changes_only_when_an_observation_date_changes(tmp_path: Path) -> None:
    store = EconomicHistoricalStore(project_root=tmp_path)
    try:
        store.upsert_observations((_observation("TPM", "3.25", date(2026, 8, 1)),))
        service = ConfiguredAdvancedMacroForecastingService(
            repository=EconomicHistoricalRepository(store=store)
        )
        original = service._history_signature()
        assert len(original) == len(EconometricDatasetBuilder.MONTHLY_INDICATORS)
        store.upsert_observations((_observation("TPM", "3.00", date(2026, 9, 1)),))
        changed = service._history_signature()
        assert dict(changed)["TPM"] == date(2026, 9, 1)
        assert original != changed
        store.upsert_observations((_observation("TPM", "2.99", date(2026, 9, 1)),))
        assert service._history_signature() == changed
    finally:
        store.close()
