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

        def latest_available_dates(self, codes) -> dict:
            return {}

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


def test_bccr_incremental_upsert_keeps_recent_revisions_but_skips_old_rows(monkeypatch) -> None:
    saved = []
    closed = []

    class FakeStore:
        def close(self) -> None:
            closed.append(True)

    class FakeRepository:
        store = FakeStore()

        def latest_available_dates(self, codes) -> dict:
            assert tuple(codes) == ("TPM",)
            return {"TPM": date(2026, 10, 14)}

        def append(self, rows) -> int:
            saved.extend(rows)
            return len(rows)

    import aip.product.configured.adapters.configured_economic_indicators_provider as provider_module

    monkeypatch.setattr(provider_module, "EconomicHistoricalRepository", FakeRepository)
    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    count = provider._persist_official_history(
        {
            "TPM": (
                _point("TPM", "3.50", date(2026, 9, 1)),
                _point("TPM", "3.25", date(2026, 10, 12)),
                _point("TPM", "3.00", date(2026, 10, 14)),
            )
        }
    )
    assert count == 2
    assert [row.observation_date for row in saved] == [date(2026, 10, 12), date(2026, 10, 14)]
    assert closed == [True]


def test_bccr_live_series_load_uses_bounded_workers_and_preserves_dates(monkeypatch) -> None:
    from threading import Lock, current_thread
    from time import sleep

    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    workers = set()
    lock = Lock()
    saved = []
    observed = _point("TPM", "3.25", date(2026, 10, 14))

    def core(code):
        with lock:
            workers.add(current_thread().name)
        sleep(0.02)
        return (observed,) if code == "TPM" else ()

    def grouped(*, chart_code, logical_codes, history_days, ttl_seconds):
        with lock:
            workers.add(current_thread().name)
        return {}

    def tri():
        with lock:
            workers.add(current_thread().name)
        return {}

    monkeypatch.setattr(provider, "_get_or_fetch_observations", core)
    monkeypatch.setattr(provider, "_get_or_fetch_grouped_chart_observations", grouped)
    monkeypatch.setattr(provider, "_get_or_fetch_tri_observations", tri)
    monkeypatch.setattr(provider, "_persist_official_history", lambda rows: saved.append(rows))

    payload = provider.get_indicators()
    assert payload["source"] == "BCCR"
    assert payload["status"] == "AVAILABLE"
    assert len(payload["indicators"]) == 1
    assert payload["indicators"][0]["date"] == date(2026, 10, 14)
    assert len(workers) >= 2
    assert all(name.startswith("bccr-live") for name in workers)
    assert len(saved) == 1


def test_incremental_bccr_query_ranges_keep_previous_observations() -> None:
    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    today = date(2026, 10, 14)
    assert provider._incremental_start(
        codes=("TPM",), end=today, default_days=45
    ) == date(2026, 8, 30)

    provider._history_watermarks = {"TPM": date(2026, 10, 13)}
    assert provider._incremental_start(
        codes=("TPM",), end=today, default_days=45
    ) == date(2026, 9, 29)

    provider._history_watermarks = {"IMAE": date(2026, 9, 30)}
    assert provider._incremental_start(
        codes=("IMAE",), end=today, default_days=450
    ) == date(2026, 7, 22)

    # An unknown or invalid watermark must never hide missing historical data.
    provider._history_watermarks = {
        "FX_BUY": date(2026, 10, 13),
        "FX_SELL": date(2026, 10, 15),
    }
    assert provider._incremental_start(
        codes=("FX_BUY", "FX_SELL"), end=today, default_days=45
    ) == date(2026, 8, 30)

    provider._history_watermarks["FX_SELL"] = date(2026, 10, 12)
    assert provider._incremental_start(
        codes=("FX_BUY", "FX_SELL"), end=today, default_days=45
    ) == date(2026, 9, 28)


def test_incremental_bccr_watermarks_are_read_once_and_connection_closed(monkeypatch) -> None:
    calls = []
    closed = []

    class FakeStore:
        def close(self):
            closed.append(True)

    class FakeRepository:
        store = FakeStore()

        def latest_available_dates(self, codes):
            calls.append(codes)
            return {"TPM": date(2026, 10, 13), "FX_BUY": None}

    import aip.product.configured.adapters.configured_economic_indicators_provider as module

    monkeypatch.setattr(module, "EconomicHistoricalRepository", FakeRepository)
    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    assert provider._load_history_watermarks() == ()
    assert provider._history_watermarks == {"TPM": date(2026, 10, 13)}
    assert len(calls) == 1
    assert {"FX_BUY", "FX_SELL", "TPM", "TBP", "IMAE", "GDP", "INFLATION"} <= set(calls[0])
    assert len(provider._tri_codes()) == 18
    assert closed == [True]


def test_incremental_bccr_api_requests_use_last_persisted_period(monkeypatch) -> None:
    import aip.product.configured.adapters.configured_economic_indicators_provider as module

    class FixedClock:
        @staticmethod
        def today():
            return date(2026, 10, 14)

    class RecordingClient:
        def __init__(self):
            self.queries = []

        def fetch_series(self, *, indicator_code, from_date, to_date):
            self.queries.append(("series", indicator_code, from_date, to_date))
            return {"body": {"datos": []}}

        def fetch_chart_series(self, *, chart_code, from_date, to_date):
            self.queries.append(("chart", chart_code, from_date, to_date))
            return {"body": {"estado": True, "datos": []}}

    monkeypatch.setattr(module, "date", FixedClock)
    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    client = RecordingClient()
    provider._client = client
    provider._history_watermarks = {
        "TPM": date(2026, 10, 13),
        "FX_BUY": date(2026, 10, 13),
        "FX_SELL": date(2026, 10, 13),
    }
    assert provider._fetch_observations("TPM") == ()
    assert provider._fetch_grouped_chart_observations(
        chart_code="1", logical_codes=("FX_BUY", "FX_SELL"), history_days=45
    ) == {}
    assert client.queries == [
        ("series", "3541", "2026/09/29", "2026/10/14"),
        ("chart", "1", "2026/09/29", "2026/10/14"),
    ]
