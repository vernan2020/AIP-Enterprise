"""Offline BCCR cards read a bounded, chronological DuckDB tail."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.product.configured.repositories.economic_historical_repository import (
    EconomicHistoricalRepository,
)
from aip.product.configured.repositories.economic_historical_store import (
    EconomicHistoricalStore,
)


def test_recent_history_reads_only_two_newest_rows_in_chronological_order() -> None:
    queries: list[tuple[str, list]] = []

    class FakeConnection:
        def execute(self, query: str, parameters: list):
            queries.append((query, parameters))
            return self

        def fetchall(self) -> list[tuple]:
            return [
                ("TPM", date(2026, 10, 14), "3.25", "BCCR", "123", "%", "DAILY"),
                ("TPM", date(2026, 10, 13), "3.00", "BCCR", "123", "%", "DAILY"),
            ]

    class FakeDatabase:
        connection = FakeConnection()

    store = object.__new__(EconomicHistoricalStore)
    store._initialized = True
    store._database = FakeDatabase()
    repository = EconomicHistoricalRepository(store=store)

    series = repository.get_recent_series("tpm", limit=2)
    assert series.indicator_code == "TPM"
    assert series.source == "BCCR"
    assert [row.observation_date for row in series.observations] == [
        date(2026, 10, 13),
        date(2026, 10, 14),
    ]
    assert [row.value for row in series.observations] == [
        Decimal("3.00"),
        Decimal("3.25"),
    ]
    assert "ORDER BY observation_date DESC" in queries[0][0]
    assert queries[0][1] == ["TPM", 2]


def test_recent_history_does_not_query_duckdb_for_invalid_limits() -> None:
    store = object.__new__(EconomicHistoricalStore)
    store._initialized = False
    assert store.recent_observations_for_series(indicator_code="", limit=2) == ()
    assert store.recent_observations_for_series(indicator_code="TPM", limit=0) == ()
