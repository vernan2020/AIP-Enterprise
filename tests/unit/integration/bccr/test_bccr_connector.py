from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from aip.integration.audit.execution_result import ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.connector import cache as bccr_cache_module
from aip.integration.bccr.connector.bccr_connector import BCCRConnector
from aip.integration.bccr.connector.cache import BCCRCache
from aip.integration.bccr.connector.http_client import HTTPClient
from aip.integration.bccr.contracts.request import BCCRRequest
from aip.integration.bccr.contracts.response import BCCRResponse
from aip.integration.bccr.events.bccr_events import BCCREvent, BCCREventType
from aip.integration.bccr.monitoring.bccr_health import BCCRHealthMonitor
from aip.integration.bccr.normalization.response_normalizer import ResponseNormalizer
from aip.integration.bccr.providers.http_provider import HTTPProvider
from aip.integration.bccr.synchronization.bccr_synchronizer import BCCRSynchronizer
from aip.integration.bccr.telemetry.bccr_metrics import BCCRMetrics
from aip.integration.bccr.validation.response_validator import ResponseValidator
from aip.integration.events.synchronization_events import IntegrationEventBus, SynchronizationEvent, SynchronizationEventType
from aip.integration.exceptions.exceptions import IntegrationError


@dataclass
class FakeHTTPProvider(HTTPProvider):
    payload: dict[str, Any] | None = None
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def get(self, url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
        self.calls.append((url, headers or {}))
        return self.payload or {}


def test_bccr_config_validation_and_repr() -> None:
    config = BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"], timeout_seconds=5.0, cache_ttl_seconds=60)
    assert config.base_url == "https://api.bccr.fi.cr"
    assert config.indicators == ["IPC"]
    assert "https://api.bccr.fi.cr" in repr(config)

    with pytest.raises(ValueError):
        BCCRConfig(base_url="", indicators=["IPC"])
    with pytest.raises(ValueError):
        BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=[], timeout_seconds=0)
    with pytest.raises(ValueError):
        BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"], cache_ttl_seconds=-1)


def test_response_validator_accepts_and_rejects_expected_payloads() -> None:
    validator = ResponseValidator()
    valid_request = BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31")
    assert validator.validate(valid_request).ok is True

    invalid_request = BCCRRequest(indicator_codes=[], from_date="", to_date="")
    result = validator.validate(invalid_request)
    assert result.ok is False
    assert result.issues[0].field == "indicator_codes"

    response = BCCRResponse(indicator_code="IPC", value=12.34, observation_date="2024-01-31", source="bccr")
    assert validator.validate(response).ok is True


def test_response_normalizer_returns_generic_metadata() -> None:
    normalizer = ResponseNormalizer()
    payload = normalizer.normalize({"indicatorCode": "IPC", "value": "12.34"})
    assert payload["indicator_code"] == "IPC"
    assert payload["value"] == "12.34"

    scalar = normalizer.normalize("plain")
    assert scalar["value"] == "plain"


def test_bccr_cache_supports_expiration() -> None:
    cache = BCCRCache(ttl_seconds=60)
    cache.set("ipc", {"indicator_code": "IPC"})
    assert cache.get("ipc") == {"indicator_code": "IPC"}
    assert cache.get("missing") is None

    expired = BCCRCache(ttl_seconds=0)
    expired.set("ipc", {"indicator_code": "IPC"})
    assert expired.get("ipc") is None


def test_bccr_cache_expired_entries_are_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bccr_cache_module, "time", lambda: 100.0)
    cache = BCCRCache(ttl_seconds=5)
    cache.set("stale", {"indicator_code": "IPC"})

    monkeypatch.setattr(bccr_cache_module, "time", lambda: 106.0)
    assert cache.get("stale") is None


def test_http_client_fetches_payloads() -> None:
    provider = FakeHTTPProvider(payload={"status_code": 200, "content_type": "application/json", "body": {"indicators": [{"code": "IPC", "value": "12.34"}]}})
    client = HTTPClient(provider=provider)
    payload = client.fetch(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))
    assert payload["indicators"][0]["code"] == "IPC"
    assert provider.calls[0][0].endswith("/indicators/IPC")


def test_bccr_synchronizer_processes_and_retries() -> None:
    provider = FakeHTTPProvider(payload={"indicators": [{"code": "IPC", "value": "12.34"}]})
    synchronizer = BCCRSynchronizer(
        client=HTTPClient(provider=provider),
        validator=ResponseValidator(),
        normalizer=ResponseNormalizer(),
        max_retries=1,
    )
    result = synchronizer.synchronize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))
    assert result.status == ExecutionStatus.COMPLETED
    assert result.records_processed == 1

    failure = synchronizer.synchronize(BCCRRequest(indicator_codes=[], from_date="", to_date=""))
    assert failure.status == ExecutionStatus.FAILED


def test_bccr_connector_lifecycle_and_events() -> None:
    provider = FakeHTTPProvider(payload={"indicators": [{"code": "IPC", "value": "12.34"}]})
    event_bus = IntegrationEventBus()
    events: list[SynchronizationEvent] = []
    event_bus.subscribe(events.append)
    connector = BCCRConnector(
        config=BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"]),
        provider=provider,
        event_bus=event_bus,
    )

    connector.connect()
    assert connector.health() is True
    connector.disconnect()
    assert connector.health() is False
    assert any(event.event_type == SynchronizationEventType.CONNECTED for event in events)

    result = connector.synchronize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"), correlation_id="corr")
    assert result.status == ExecutionStatus.COMPLETED

    with pytest.raises(IntegrationError, match="Validation failed"):
        connector.synchronize(BCCRRequest(indicator_codes=[], from_date="", to_date=""), correlation_id="corr")


def test_bccr_health_monitor_and_metrics() -> None:
    monitor = BCCRHealthMonitor()
    monitor.record_success("bccr", 1)
    monitor.record_failure("bccr")
    monitor.record_retry("bccr")
    monitor.record_latency("bccr", 4.2)
    monitor.record_state("bccr", "running")
    snapshot = monitor.snapshot("bccr")
    assert snapshot["requests_processed"] == 1
    assert snapshot["failures"] == 1
    assert snapshot["state"] == "running"

    metrics = BCCRMetrics()
    metrics.increment("requests")
    metrics.gauge("latency", 3.0)
    assert metrics.snapshot()["requests"] == 1.0


def test_bccr_audit_records_events() -> None:
    from aip.integration.bccr.audit.bccr_audit import BCCRAudit

    audit = BCCRAudit()
    log = SynchronizationLog(execution_id="exec-1", correlation_id="corr-1", connector="bccr", duration_seconds=0.0, records_processed=1, user="ops", timestamp=datetime.now(UTC))
    audit.record(log)
    assert audit.history[-1].execution_id == "exec-1"


def test_bccr_connector_normalize_and_validate_paths() -> None:
    connector = BCCRConnector(
        config=BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"]),
        provider=FakeHTTPProvider(payload={"indicators": [{"code": "IPC", "value": "12.34"}]}),
    )
    normalized = connector.normalize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))
    assert normalized["indicator_codes"] == ["IPC"]
    assert normalized["from_date"] == "2024-01-01"
    assert normalized["to_date"] == "2024-01-31"
    assert connector.normalize("plain")["value"] == "plain"
    assert connector.validate(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31")).ok is True


def test_bccr_connector_handles_cancellation_and_cache_hit() -> None:
    connector = BCCRConnector(
        config=BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"]),
        provider=FakeHTTPProvider(payload={"indicators": [{"code": "IPC", "value": "12.34"}]}),
    )
    connector.connect()
    with pytest.raises(IntegrationError, match="cancelled"):
        connector.synchronize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"), cancellation_token="cancelled")
    result = connector.synchronize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))
    assert result.status == ExecutionStatus.COMPLETED


def test_http_client_supports_conditional_requests_and_validates_status_and_content_type() -> None:
    class RecordingProvider(HTTPProvider):
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

        def get(self, url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
            self.calls.append((url, headers or {}, {"status_code": 304, "content_type": "application/json", "body": {}}))
            return {"status_code": 304, "content_type": "application/json", "body": {}}

    provider = RecordingProvider()
    client = HTTPClient(provider=provider, timeout_seconds=1.5)
    request = BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31", etag="abc123", last_modified="2024-01-31T00:00:00Z")
    payload = client.fetch(request)
    assert payload == {}
    assert provider.calls[0][1]["If-None-Match"] == "abc123"
    assert provider.calls[0][1]["If-Modified-Since"] == "2024-01-31T00:00:00Z"

    provider2 = RecordingProvider()
    client2 = HTTPClient(provider=provider2)
    with pytest.raises(ValueError, match="content-type"):
        provider2.get = lambda url, *, timeout, headers=None: {"status_code": 200, "content_type": "text/plain", "body": {"bad": True}}  # type: ignore[assignment]
        client2.fetch(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))

    class BadResponseProvider(HTTPProvider):
        def get(self, url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
            return 42  # type: ignore[return-value]

    with pytest.raises(ValueError, match="mapping"):
        HTTPClient(provider=BadResponseProvider()).fetch(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))

    class InvalidStatusProvider(HTTPProvider):
        def get(self, url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
            return {"status_code": 500, "content_type": "application/json", "body": {}}

    with pytest.raises(ValueError, match="invalid status code"):
        HTTPClient(provider=InvalidStatusProvider()).fetch(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))


def test_bccr_synchronizer_retries_and_handles_cancellation_and_failures() -> None:
    class FlakyProvider(HTTPProvider):
        def __init__(self) -> None:
            self.calls = 0

        def get(self, url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
            self.calls += 1
            if self.calls < 3:
                return {"status_code": 200, "content_type": "application/json", "body": {}}
            return {"status_code": 200, "content_type": "application/json", "body": {"indicators": [{"code": "IPC", "value": "12.34"}]}}

    provider = FlakyProvider()
    synchronizer = BCCRSynchronizer(client=HTTPClient(provider=provider), max_retries=2)
    cancelled = synchronizer.synchronize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"), cancellation_token="cancelled")
    assert cancelled.status == ExecutionStatus.CANCELLED

    result = synchronizer.synchronize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))
    assert result.status == ExecutionStatus.COMPLETED
    assert provider.calls >= 3


def test_bccr_connector_translates_connection_and_timeout_failures() -> None:
    class FailingProvider(HTTPProvider):
        def get(self, url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
            raise TimeoutError("timed out")

    connector = BCCRConnector(config=BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"]), provider=FailingProvider())
    with pytest.raises(IntegrationError, match="timed out"):
        connector.synchronize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))


def test_bccr_connector_cover_fallback_paths() -> None:
    connector = BCCRConnector(config=BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"]))
    with pytest.raises(IntegrationError, match="Validation failed"):
        connector.validate("plain")
    connector.audit(SynchronizationLog(execution_id="exec-1", correlation_id="corr-1", connector="bccr", duration_seconds=0.0, records_processed=0, user="ops", timestamp=datetime.now(UTC)))
    assert connector.synchronizer.client.provider is not None


def test_bccr_health_monitor_supports_degraded_and_unavailable_states() -> None:
    monitor = BCCRHealthMonitor()
    monitor.record_degraded("bccr")
    monitor.record_unavailable("bccr")
    snapshot = monitor.snapshot("bccr")
    assert snapshot["state"] == "unavailable"


def test_bccr_events_and_contracts_are_immutable() -> None:
    event = BCCREvent.started("bccr", "exec")
    assert event.event_type == BCCREventType.STARTED
    assert BCCREvent.retry_started("bccr", "exec", 1).details["attempt"] == 1
    assert BCCREvent.cache_hit("bccr", "exec").details["source"] == "cache"
    assert BCCREvent.cache_miss("bccr", "exec").details["source"] == "network"

    request = BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31")
    response = BCCRResponse(indicator_code="IPC", value=Decimal("12.3400"), observation_date="2024-01-31", source="bccr")
    with pytest.raises(FrozenInstanceError):
        request.indicator_codes.append("USD")
    assert response.value == Decimal("12.3400")


def test_response_validator_rejects_invalid_timestamp_and_invalid_response() -> None:
    validator = ResponseValidator()
    invalid_response = BCCRResponse(indicator_code="IPC", value=12.34, observation_date="not-a-date", source="bccr")
    assert validator.validate(invalid_response).ok is False
    assert validator.validate(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31")).ok is True
    fallback_result = validator.validate(object())
    assert fallback_result.ok is False
    assert fallback_result.issues[0].field == "payload"


def test_bccr_config_and_connector_edge_paths() -> None:
    with pytest.raises(ValueError):
        BCCRConfig(base_url="", indicators=["IPC"])
    with pytest.raises(ValueError):
        BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=[], timeout_seconds=1.0)
    with pytest.raises(ValueError):
        BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"], timeout_seconds=0)
    with pytest.raises(ValueError):
        BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"], cache_ttl_seconds=-1)

    connector = BCCRConnector(
        config=BCCRConfig(base_url="https://api.bccr.fi.cr", indicators=["IPC"]),
        provider=FakeHTTPProvider(payload={"indicators": [{"code": "IPC", "value": "12.34"}]})
    )
    assert connector.normalize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))["indicator_codes"] == ["IPC"]
    assert connector.validate(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31")).ok is True


def test_bccr_request_and_response_contracts_are_serializable() -> None:
    request = BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31")
    response = BCCRResponse(indicator_code="IPC", value=Decimal("12.34"), observation_date="2024-01-31", source="bccr")
    assert request.to_dict()["indicator_codes"] == ["IPC"]
    assert response.to_dict()["indicator_code"] == "IPC"


def test_bccr_request_mutations_are_blocked_and_events_cover_more_branches() -> None:
    request = BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31")
    for mutation in (lambda codes: codes.append("USD"), lambda codes: codes.extend(["USD"]), lambda codes: codes.insert(1, "USD"), lambda codes: codes.remove("IPC"), lambda codes: codes.pop(), lambda codes: codes.clear()):
        with pytest.raises(FrozenInstanceError):
            mutation(request.indicator_codes)

    assert BCCREvent.failed("bccr", "exec", "boom").details["error"] == "boom"
    assert BCCREvent.retry_completed("bccr", "exec", 2).details["attempt"] == 2
    assert BCCREvent.request_started("bccr", "exec").event_type == BCCREventType.REQUEST_STARTED
    assert BCCREvent.request_completed("bccr", "exec").event_type == BCCREventType.REQUEST_COMPLETED
    assert BCCREvent.request_failed("bccr", "exec", "oops").details["error"] == "oops"
    assert BCCREvent.completed("bccr", "exec").event_type == BCCREventType.COMPLETED


def test_response_normalizer_handles_more_payload_shapes() -> None:
    normalizer = ResponseNormalizer()
    assert normalizer.normalize({}) == {"value": {}}
    payload = normalizer.normalize({
        "indicator_code": "IPC",
        "value": "12.34",
        "indicator_codes": ["IPC"],
        "from_date": "2024-01-01",
        "to_date": "2024-01-31",
        "format": "json",
        "status_code": 200,
        "content_type": "application/json",
        "body": {"indicators": [{"code": "IPC", "value": "12.34"}]},
    })
    assert payload["indicator_code"] == "IPC"
    assert payload["indicator_codes"] == ["IPC"]
    assert payload["from_date"] == "2024-01-01"
    assert payload["to_date"] == "2024-01-31"
    assert payload["format"] == "json"
    assert payload["body"]["indicators"][0]["value"] == "12.34"


def test_http_client_returns_empty_payload_when_body_missing() -> None:
    class EmptyBodyProvider(HTTPProvider):
        def get(self, url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
            return {"status_code": 200, "content_type": "application/json"}

    payload = HTTPClient(provider=EmptyBodyProvider()).fetch(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))
    assert payload == {}


def test_bccr_synchronizer_returns_failed_when_retries_are_exhausted() -> None:
    class EmptyProvider(HTTPProvider):
        def get(self, url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
            return {"status_code": 200, "content_type": "application/json", "body": {}}

    synchronizer = BCCRSynchronizer(client=HTTPClient(provider=EmptyProvider()), max_retries=2)
    result = synchronizer.synchronize(BCCRRequest(indicator_codes=["IPC"], from_date="2024-01-01", to_date="2024-01-31"))
    assert result.status == ExecutionStatus.FAILED
