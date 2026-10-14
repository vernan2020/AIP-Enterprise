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
    monkeypatch.setattr(
        provider, "_restore_missing_from_local_history", lambda live_codes: ([], ())
    )

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
    assert provider._incremental_start(codes=("TPM",), end=today, default_days=45) == date(
        2026, 8, 30
    )

    provider._history_watermarks = {"TPM": date(2026, 10, 13)}
    assert provider._incremental_start(codes=("TPM",), end=today, default_days=45) == date(
        2026, 9, 29
    )

    provider._history_watermarks = {"IMAE": date(2026, 9, 30)}
    assert provider._incremental_start(codes=("IMAE",), end=today, default_days=450) == date(
        2026, 7, 22
    )

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
            return {"body": {"estado": True, "datos": []}}

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
    assert (
        provider._fetch_grouped_chart_observations(
            chart_code="1", logical_codes=("FX_BUY", "FX_SELL"), history_days=45
        )
        == {}
    )
    assert client.queries == [
        ("series", "3541", "2026/09/29", "2026/10/14"),
        ("chart", "1", "2026/09/29", "2026/10/14"),
    ]


def test_bccr_partial_urllib_failure_keeps_healthy_official_series(monkeypatch) -> None:
    from urllib.error import URLError

    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    observation = _point("TPM", "3.25", date(2026, 10, 14))

    monkeypatch.setattr(provider, "_load_history_watermarks", lambda: ())
    monkeypatch.setattr(
        provider,
        "_get_or_fetch_grouped_chart_observations",
        lambda **kwargs: (_ for _ in ()).throw(URLError("offline")),
    )
    monkeypatch.setattr(
        provider,
        "_get_or_fetch_observations",
        lambda code: (observation,) if code == "TPM" else (),
    )
    monkeypatch.setattr(provider, "_get_or_fetch_tri_observations", lambda: {})
    monkeypatch.setattr(provider, "_persist_official_history", lambda rows: 1)

    payload = provider.get_indicators()

    assert payload["status"] == "AVAILABLE"
    assert payload["source"] == "BCCR"
    assert any(item["code"] == "TPM" for item in payload["indicators"])
    assert any(message.startswith("FX: URLError") for message in payload["diagnostics"])
    assert any(message.startswith("LABOR: URLError") for message in payload["diagnostics"])


def test_partial_bccr_api_merges_missing_historical_cards_without_replacing_live(
    monkeypatch,
) -> None:
    from aip.product.economic.economic_history import (
        EconomicHistoricalObservation,
        EconomicHistoricalSeries,
    )

    opened = []
    closed = []

    class FakeStore:
        def close(self) -> None:
            closed.append(True)

    class FakeRepository:
        store = FakeStore()

        def __init__(self) -> None:
            opened.append(True)

        def available_series(self) -> tuple[str, ...]:
            return ("TPM", "FX_BUY", "FX_SELL", "IMAE")

        def get_recent_series(self, code: str, *, limit: int = 2):
            assert code != "TPM"  # Never replace a confirmed live TPM.
            assert limit == 2
            item = EconomicHistoricalObservation(
                indicator_code=code,
                observation_date=date(2026, 8, 31),
                value=Decimal("400.25"),
                source="BCCR",
                source_series_code="1234",
                unit="%",
                frequency="DAILY",
            )
            return EconomicHistoricalSeries(
                indicator_code=code, observations=(item,), source="BCCR"
            )

    import aip.product.configured.adapters.configured_economic_indicators_provider as module

    monkeypatch.setattr(module, "EconomicHistoricalRepository", FakeRepository)
    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    monkeypatch.setattr(provider, "_load_history_watermarks", lambda: ())
    monkeypatch.setattr(provider, "_get_or_fetch_grouped_chart_observations", lambda **kwargs: {})
    monkeypatch.setattr(
        provider,
        "_get_or_fetch_observations",
        lambda code: (_point("TPM", "3.25", date(2026, 10, 14)),) if code == "TPM" else (),
    )
    monkeypatch.setattr(provider, "_get_or_fetch_tri_observations", lambda: {})
    monkeypatch.setattr(provider, "_persist_official_history", lambda rows: 1)
    payload = provider.get_indicators()
    cards = {item["code"]: item for item in payload["indicators"]}
    assert payload["source"] == "BCCR · MIXTO CON HISTÓRICO LOCAL"
    assert cards["TPM"]["date"] == date(2026, 10, 14)
    assert cards["TPM"]["source"] == "BCCR"
    assert cards["FX_BUY"]["date"] == date(2026, 8, 31)
    assert cards["FX_BUY"]["source"] == "BCCR · HISTÓRICO LOCAL"
    assert "sin confirmación BCCR en vivo" in " ".join(payload["diagnostics"])
    assert len(opened) == 1
    assert closed == [True]


def test_partial_bccr_network_diagnostics_never_disclose_sensitive_error_text(
    monkeypatch,
) -> None:
    from urllib.error import URLError

    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    monkeypatch.setattr(provider, "_load_history_watermarks", lambda: ())
    monkeypatch.setattr(
        provider,
        "_get_or_fetch_grouped_chart_observations",
        lambda **kwargs: (_ for _ in ()).throw(URLError("secret=DO_NOT_LEAK")),
    )
    monkeypatch.setattr(
        provider,
        "_get_or_fetch_observations",
        lambda code: (_point("TPM", "3.25", date(2026, 10, 14)),) if code == "TPM" else (),
    )
    monkeypatch.setattr(provider, "_get_or_fetch_tri_observations", lambda: {})
    monkeypatch.setattr(provider, "_persist_official_history", lambda rows: 1)
    monkeypatch.setattr(
        provider, "_restore_missing_from_local_history", lambda live_codes: ([], ())
    )
    payload = provider.get_indicators()
    assert payload["status"] == "AVAILABLE"
    assert "FX: URLError" in payload["diagnostics"]
    assert "secret=DO_NOT_LEAK" not in str(payload["diagnostics"])


def test_unavailable_duckdb_does_not_block_working_live_bccr(monkeypatch) -> None:
    import aip.product.configured.adapters.configured_economic_indicators_provider as module

    def inaccessible_history():
        raise OSError("sensitive database path must stay private")

    monkeypatch.setattr(module, "EconomicHistoricalRepository", inaccessible_history)
    provider = ConfiguredEconomicIndicatorsProvider(bccr_config=BCCRConfig(token="TEST_ONLY"))
    monkeypatch.setattr(provider, "_get_or_fetch_grouped_chart_observations", lambda **kwargs: {})
    monkeypatch.setattr(
        provider,
        "_get_or_fetch_observations",
        lambda code: (_point("TPM", "3.25", date(2026, 10, 14)),) if code == "TPM" else (),
    )
    monkeypatch.setattr(provider, "_get_or_fetch_tri_observations", lambda: {})
    monkeypatch.setattr(provider, "_persist_official_history", lambda rows: 0)

    payload = provider.get_indicators()
    assert payload["status"] == "AVAILABLE"
    assert payload["source"] == "BCCR"
    assert [item["code"] for item in payload["indicators"]] == ["TPM"]
    assert "sensitive database path" not in str(payload["diagnostics"])
    assert any("histórico incremental no disponible" in d for d in payload["diagnostics"])
    assert any("histórico local no disponible" in d for d in payload["diagnostics"])
