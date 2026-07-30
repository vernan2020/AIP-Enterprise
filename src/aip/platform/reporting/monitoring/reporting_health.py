from __future__ import annotations

from dataclasses import dataclass, field

from src.aip.platform.reporting.models.report import Report
from src.aip.platform.reporting.telemetry.reporting_metrics import ReportingMetrics


@dataclass(slots=True)
class ReportingHealth:
    """Aggregates reporting health counters."""

    reports_generated: int = 0
    renderer_failures: int = 0
    template_usage: dict[str, int] = field(default_factory=dict)
    export_size_bytes: int = 0


@dataclass(slots=True)
class ReportingMonitor:
    """Simple monitoring service for report generation and export."""

    health: ReportingHealth = field(default_factory=ReportingHealth)
    metrics: ReportingMetrics = field(default_factory=ReportingMetrics)

    def record_report_generated(self, report: Report) -> None:
        self.health.reports_generated += 1
        self.metrics.record_report_generated(report)

    def record_renderer_failure(self, renderer_name: str) -> None:
        self.health.renderer_failures += 1
        self.metrics.record_renderer_failure(renderer_name)

    def record_template_usage(self, template_name: str) -> None:
        self.health.template_usage[template_name] = self.health.template_usage.get(template_name, 0) + 1
        self.metrics.record_template_usage(template_name)

    def record_export_size(self, size_bytes: int) -> None:
        self.health.export_size_bytes += size_bytes
        self.metrics.record_export_size(size_bytes)
