from __future__ import annotations

from dataclasses import dataclass, field

from src.aip.platform.reporting.models.report import Report


@dataclass(slots=True)
class ReportingMetrics:
    """Basic metrics tracker for reporting operations."""

    report_count: int = 0
    average_generation_time_ms: float = 0.0
    renderer_failures: int = 0
    template_usage: dict[str, int] = field(default_factory=dict)
    export_size_bytes: int = 0

    def record_report_generated(self, report: Report) -> None:
        self.report_count += 1

    def record_renderer_failure(self, renderer_name: str) -> None:
        self.renderer_failures += 1

    def record_template_usage(self, template_name: str) -> None:
        self.template_usage[template_name] = self.template_usage.get(template_name, 0) + 1

    def record_export_size(self, size_bytes: int) -> None:
        self.export_size_bytes += size_bytes
