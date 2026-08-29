from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aip.platform.observability.audit.observability_audit import ObservabilityAudit
from aip.platform.observability.configuration.observability_config import ObservabilityConfig
from aip.platform.observability.correlation.correlation_context import CorrelationContext
from aip.platform.observability.events.observability_events import ObservabilityEvent
from aip.platform.observability.exceptions.observability_exceptions import ObservabilityError
from aip.platform.observability.health.component_health import ComponentHealth, HealthStatus
from aip.platform.observability.health.health_service import HealthService
from aip.platform.observability.logging.logger import Logger
from aip.platform.observability.logging.logger_factory import LoggerFactory
from aip.platform.observability.logging.structured_log import StructuredLog
from aip.platform.observability.metrics.counter import Counter
from aip.platform.observability.metrics.gauge import Gauge
from aip.platform.observability.metrics.histogram import Histogram
from aip.platform.observability.metrics.metrics_registry import MetricsRegistry
from aip.platform.observability.metrics.timer import Timer
from aip.platform.observability.monitoring.monitoring_service import MonitoringService
from aip.platform.observability.providers.console_provider import ConsoleProvider
from aip.platform.observability.providers.null_provider import NullProvider
from aip.platform.observability.telemetry.telemetry_service import TelemetryService
from aip.platform.observability.tracing.trace_context import TraceContext
from aip.platform.observability.tracing.tracer import Span, Tracer


class RecordingProvider:
    def __init__(self) -> None:
        self.entries: list[StructuredLog] = []

    def emit(self, log: StructuredLog) -> None:
        self.entries.append(log)


def test_structured_logging_and_logger_factory() -> None:
    provider = RecordingProvider()
    logger = LoggerFactory.create_logger(
        "payments", provider=provider, config=ObservabilityConfig(service_name="orders")
    )

    logger.info(
        "started",
        correlation_id="corr-1",
        execution_id="exec-1",
        component="payments",
        metadata={"tenant": "t1"},
    )
    logger.warning("warned", component="payments")
    logger.error("failed", exception=RuntimeError("boom"))
    logger.critical("critical", component="payments")
    logger.debug("debug", component="payments")

    assert len(provider.entries) == 5
    first = provider.entries[0]
    assert first.level == "INFO"
    assert first.correlation_id == "corr-1"
    assert first.execution_id == "exec-1"
    assert first.component == "payments"
    assert first.metadata["tenant"] == "t1"
    assert first.to_dict()["message"] == "started"

    second = provider.entries[1]
    assert second.level == "WARNING"

    third = provider.entries[2]
    assert third.level == "ERROR"
    assert third.exception is not None
    assert "boom" in third.exception

    fourth = provider.entries[3]
    assert fourth.level == "CRITICAL"

    fifth = provider.entries[4]
    assert fifth.level == "DEBUG"

    logger_without_provider = Logger()
    logger_without_provider.info("ignored")


def test_tracing_and_trace_context_propagation() -> None:
    tracer = Tracer()
    with tracer.start_span("outer", correlation_id="corr", execution_id="exec") as outer:
        assert isinstance(outer, Span)
        with tracer.start_span("inner", parent=outer) as inner:
            assert inner.parent_span_id == outer.span_id
            assert inner.trace_id == outer.trace_id

    assert outer.status == "completed"
    assert outer.duration_seconds >= 0.0

    active_span = Span(name="pending", trace_id="trace-1", span_id="span-1")
    assert active_span.duration_seconds == 0.0

    with Tracer() as tracer_context:
        assert tracer_context is not None

    context = TraceContext(
        trace_id="t-1", span_id="s-1", correlation_id="corr", execution_id="exec"
    )
    assert context.to_dict()["trace_id"] == "t-1"


def test_metrics_registry_counter_gauge_histogram_and_timer() -> None:
    registry = MetricsRegistry()
    counter = registry.counter("requests")
    gauge = registry.gauge("queue")
    histogram = registry.histogram("latency")
    timer = registry.timer("request_time")

    assert isinstance(counter, Counter)
    assert isinstance(gauge, Gauge)
    assert isinstance(histogram, Histogram)
    assert isinstance(timer, Timer)

    counter.increment(2)
    gauge.set(7)
    histogram.observe(1.5)
    histogram.observe(2.5)
    timer.record(0.25)

    snapshot = registry.snapshot()
    assert snapshot["requests"] == 2
    assert snapshot["queue"] == 7
    assert snapshot["latency"]["count"] == 2
    assert snapshot["latency"]["average"] == 2.0
    assert snapshot["request_time"]["count"] == 1

    with timer.time():
        pass

    assert timer.snapshot()["count"] >= 1


def test_health_service_aggregation() -> None:
    empty_service = HealthService()
    assert empty_service.aggregate_status() == HealthStatus.UNKNOWN

    service = HealthService()
    service.update_component("database", HealthStatus.HEALTHY, {"latency_ms": 2})
    service.update_component("cache", HealthStatus.DEGRADED, {"miss_rate": 0.2})
    service.update_component("queue", HealthStatus.UNAVAILABLE, {"backlog": 10})

    snapshot = service.snapshot()
    assert len(snapshot) == 3
    assert service.aggregate_status() == HealthStatus.UNAVAILABLE

    healthy_service = HealthService()
    healthy_service.update_component("database", HealthStatus.HEALTHY)
    assert healthy_service.aggregate_status() == HealthStatus.HEALTHY

    degraded_service = HealthService()
    degraded_service.update_component("cache", HealthStatus.DEGRADED)
    assert degraded_service.aggregate_status() == HealthStatus.DEGRADED

    unknown_service = HealthService()
    unknown_service.update_component("api", HealthStatus.UNKNOWN)
    assert unknown_service.aggregate_status() == HealthStatus.UNKNOWN

    component = ComponentHealth(
        name="api", status=HealthStatus.UNKNOWN, details={"status": "booting"}
    )
    assert component.to_dict()["status"] == "unknown"


def test_correlation_context_and_telemetry_service() -> None:
    CorrelationContext.clear()
    context = CorrelationContext(correlation_id="corr-2", execution_id="exec-2")
    CorrelationContext.set_current(context)

    current = CorrelationContext.get_current()
    assert current.correlation_id == "corr-2"
    assert current.execution_id == "exec-2"

    telemetry = TelemetryService()
    telemetry.emit_log("info", "hello")
    telemetry.record_counter("events", 1)
    telemetry.record_gauge("cpu", 0.5)
    telemetry.observe_histogram("duration", 1.2)
    telemetry.update_component_health("api", HealthStatus.HEALTHY)

    with telemetry.start_span("step") as span:
        assert span.name == "step"

    snapshot = telemetry.snapshot()
    assert snapshot["metrics"]["events"] == 1
    assert snapshot["health"]["api"]["status"] == "healthy"

    CorrelationContext.clear()


def test_monitoring_service_audit_and_events() -> None:
    audit = ObservabilityAudit()
    event = ObservabilityEvent(
        event_type="log",
        message="captured",
        timestamp=datetime.now(UTC),
        metadata={"source": "tests"},
    )
    audit.record(event)

    monitoring = MonitoringService()
    monitoring.record_event(event)
    monitoring.record_health("api", HealthStatus.HEALTHY)
    monitoring.record_metric("requests", 3)

    snapshot = monitoring.snapshot()
    assert snapshot["events"][0]["message"] == "captured"
    assert snapshot["health"]["api"]["status"] == "healthy"
    assert snapshot["metrics"]["requests"] == 3
    assert audit.entries[-1].message == "captured"


def test_configuration_and_exceptions() -> None:
    config = ObservabilityConfig.from_dict(
        {"service_name": "checkout", "enabled": True, "json_logs": True}
    )
    assert config.service_name == "checkout"
    assert config.enabled is True
    assert config.json_logs is True

    config.validate()

    invalid = ObservabilityConfig(service_name="", enabled=True)
    with pytest.raises(ObservabilityError):
        invalid.validate()

    logger = Logger(provider=NullProvider())
    assert isinstance(logger.provider, NullProvider)

    console = ConsoleProvider()
    console.emit(StructuredLog(level="INFO", message="hello"))
