"""Official BCCR refresh never invents observations or keeps stale cached data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.economic.economic_indicator_observation import EconomicIndicatorObservation
from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.product.configured.adapters.configured_economic_indicators_provider import (
    ConfiguredEconomicIndicatorsProvider,
)


def _point(code: str, value: str, observed: date) -> EconomicIndicatorObservation:
    return EconomicIndicatorObservation(
        indicator_code=code,
        observation_date=observed,
        value=Decimal(value),
        source="BCCR",
        unit="%",
        source_series_code="1234",
        quality_status="VALID",
        is_preliminary=False,
    )


def test_live_bccr_rows_keep_official_date_value_and_frequency() -> None:
    rows = ConfiguredEconomicIndicatorsProvider._official_history_rows(
        {"TPM": (_point("TPM", "3.00", date(2026, 10, 12)),)}
    )
    assert len(rows) == 1
    assert rows[0].indicator_code == "TPM"
    assert rows[0].observation_date == date(2026, 10, 12)
    assert rows[0].value == Decimal("3.00")
    assert rows[0].frequency == "DAILY"


def test_refresh_invalidates_cached_bccr_responses() -> None:
    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    provider._cache.set("chart:1", {"FX_SELL": ("old",)})
    assert provider._cache.size() == 1
    provider.invalidate_cache()
    assert provider._cache.size() == 0


def test_bccr_history_records_are_written_to_repository(monkeypatch) -> None:
    saved = []

    class FakeStore:
        def close(self) -> None:
            pass

    class FakeRepository:
        store = FakeStore()

        def append(self, rows) -> int:
            saved.extend(rows)
            return len(rows)

    import aip.product.configured.adapters.configured_economic_indicators_provider as provider_module

    monkeypatch.setattr(provider_module, "EconomicHistoricalRepository", FakeRepository)
    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    assert (
        provider._persist_official_history({"TBP": (_point("TBP", "3.62", date(2026, 10, 12)),)})
        == 1
    )
    assert saved[0].value == Decimal("3.62")
