"""BCCR REST latency controls must use configuration and respect provider pacing."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.connector import rest_client as rest_module
from aip.integration.bccr.connector.rest_client import BCCRRestClient


class RecordingProvider:
    def __init__(self, codes: list[int]) -> None:
        self.codes = codes
        self.calls = 0

    def get(self, url: str, *, timeout: float, headers=None) -> dict:
        self.calls += 1
        return {
            "status_code": self.codes[min(self.calls - 1, len(self.codes) - 1)],
            "headers": {"Retry-After": "0"} if self.codes[self.calls - 1] == 429 else {},
            "body": {"estado": True, "datos": []},
        }


def test_retry_count_uses_configuration_instead_of_five_hardcoded_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rest_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(rest_module.random, "uniform", lambda _start, _end: 0.0)
    provider = RecordingProvider([429, 429, 200])
    client = BCCRRestClient(
        config=BCCRConfig(token="TEST_ONLY", retry_attempts=1),
        provider=provider,
    )
    client._MIN_REQUEST_INTERVAL_SECONDS = 0.0
    with pytest.raises(ConnectionError, match="429"):
        client.fetch_series(indicator_code="317", from_date="2026/10/01", to_date="2026/10/14")
    assert provider.calls == 2


def test_bccr_successful_retry_and_no_retry_for_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rest_module.time, "sleep", lambda _seconds: None)
    retry = RecordingProvider([429, 200])
    client = BCCRRestClient(
        config=BCCRConfig(token="TEST_ONLY", retry_attempts=1),
        provider=retry,
    )
    client._MIN_REQUEST_INTERVAL_SECONDS = 0.0
    assert (
        client.fetch_series(indicator_code="317", from_date="2026/10/01", to_date="2026/10/14")[
            "status_code"
        ]
        == 200
    )
    assert retry.calls == 2

    unauthorized = RecordingProvider([401])
    client = BCCRRestClient(
        config=BCCRConfig(token="TEST_ONLY", retry_attempts=3),
        provider=unauthorized,
    )
    with pytest.raises(ConnectionError, match="HTTP 401") as error:
        client.fetch_series(indicator_code="317", from_date="2026/10/01", to_date="2026/10/14")
    assert "TEST_ONLY" not in str(error.value)
    assert unauthorized.calls == 1


def test_concurrent_call_starts_are_reserved_with_minimum_spacing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    lock = Lock()

    def record_delay(value: float) -> None:
        with lock:
            delays.append(round(value, 3))

    monkeypatch.setattr(
        rest_module,
        "time",
        SimpleNamespace(monotonic=lambda: 100.0, sleep=record_delay),
    )
    client = BCCRRestClient(
        config=BCCRConfig(token="TEST_ONLY"),
        provider=RecordingProvider([200]),
    )
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: client._throttle(), range(4)))
    assert sorted(delays) == [0.75, 1.5, 2.25]


def test_sdde_query_parameter_casing_matches_bccr_specification() -> None:
    """Both public SDDE series routes require fechaInicio, not fechainicio."""
    client = BCCRRestClient(config=BCCRConfig(token="TEST_ONLY"), provider=RecordingProvider([200]))
    urls = (
        client.build_chart_url(chart_code="1", from_date="2026/10/01", to_date="2026/10/14"),
        client.build_url(indicator_code="317", from_date="2026/10/01", to_date="2026/10/14"),
    )
    for url in urls:
        params = parse_qs(urlsplit(url).query)
        assert params == {
            "fechaInicio": ["2026/10/01"],
            "fechaFin": ["2026/10/14"],
            "idioma": ["es"],
        }
