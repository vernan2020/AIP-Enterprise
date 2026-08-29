from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

import pytest

from src.aip.platform.reporting.audit.reporting_audit import ReportingAudit
from src.aip.platform.reporting.configuration.reporting_config import ReportingConfig
from src.aip.platform.reporting.engine.renderer import Renderer
from src.aip.platform.reporting.engine.report_engine import ReportEngine
from src.aip.platform.reporting.events.reporting_events import (
    ExportCompleted,
    ExportStarted,
    ReportCompleted,
    ReportFailed,
    ReportStarted,
    RetryCompleted,
    RetryStarted,
)
from src.aip.platform.reporting.exceptions.reporting_exceptions import (
    RendererError,
    ReportingError,
)
from src.aip.platform.reporting.export.export_service import ExportService
from src.aip.platform.reporting.formatting.formatter import Formatter
from src.aip.platform.reporting.models.report import Report
from src.aip.platform.reporting.models.report_metadata import ReportMetadata
from src.aip.platform.reporting.models.section import Section
from src.aip.platform.reporting.models.table import Table
from src.aip.platform.reporting.monitoring.reporting_health import ReportingHealth, ReportingMonitor
from src.aip.platform.reporting.renderers.excel_renderer import ExcelRenderer
from src.aip.platform.reporting.renderers.html_renderer import HtmlRenderer
from src.aip.platform.reporting.renderers.json_renderer import JsonRenderer
from src.aip.platform.reporting.renderers.pdf_renderer import PdfRenderer
from src.aip.platform.reporting.renderers.ppt_renderer import PptRenderer
from src.aip.platform.reporting.telemetry.reporting_metrics import ReportingMetrics
from src.aip.platform.reporting.templates.template import Template
from src.aip.platform.reporting.templates.template_registry import TemplateRegistry


@dataclass(frozen=True, slots=True)
class FakeRenderer(Renderer):
    name: str

    def render(self, report: Report) -> str:
        return f"rendered:{self.name}:{report.title}"


class TestReportingPlatform:
    def test_report_model_is_immutable(self) -> None:
        report = Report(title="Quarterly Report", sections=(Section(title="Overview"),))
        with pytest.raises(AttributeError):
            report.title = "Changed"  # type: ignore[assignment]

    def test_engine_formats_and_renders(self) -> None:
        report = Report(
            title="Quarterly Report",
            subtitle="Board Summary",
            sections=(
                Section(title="Overview", tables=(Table(columns=("Name",), rows=(("A",),)),)),
            ),
            metadata=ReportMetadata(
                author="Ops", generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc)
            ),
        )

        engine = ReportEngine(renderer=HtmlRenderer())
        rendered = engine.render(report)
        assert "Quarterly Report" in rendered
        assert "Board Summary" in rendered
        assert "Overview" in rendered

    def test_renderers_share_contract(self) -> None:
        report = Report(title="Example")
        assert HtmlRenderer().render(report).startswith("<html")
        assert PdfRenderer().render(report).startswith("PDF")
        assert ExcelRenderer().render(report).startswith("xlsx")
        assert PptRenderer().render(report).startswith("ppt")
        assert JsonRenderer().render(report).startswith("{")

    def test_templates_and_registry(self) -> None:
        registry = TemplateRegistry()
        registry.register(Template("corporate"))
        registry.register(Template("minimal"))
        registry.register(Template("dark"))
        assert registry.get("corporate").name == "corporate"
        assert registry.get("minimal").name == "minimal"
        assert registry.get("dark").name == "dark"
        assert registry.names() == ("corporate", "minimal", "dark")

    def test_formatter_formats_values(self) -> None:
        formatter = Formatter()
        assert formatter.format_value(Decimal("1234.5")) == "1,234.50"
        assert formatter.format_value(1234.5) == "1,234.50"
        assert formatter.format_value("hello") == "hello"
        assert formatter.format_value(None) == ""

    def test_export_service_supports_file_memory_and_streaming(self) -> None:
        service = ExportService()
        payload = service.export_file("report", BytesIO(b"payload"), path="/tmp/report.txt")
        assert payload == "/tmp/report.txt"

        memory = service.export_memory("report", b"payload")
        assert memory == b"payload"

        stream = service.export_streaming("report", BytesIO(b"payload"))
        assert stream.read() == b"payload"

    def test_export_service_supports_retry_and_cancellation(self) -> None:
        service = ExportService(retry_attempts=2, retry_delay_seconds=0)
        cancelable = service.export_file("report", BytesIO(b"payload"), path="/tmp/cancel.txt")
        assert cancelable == "/tmp/cancel.txt"

        service.cancel()
        assert service.is_cancelled is True

    def test_reporting_audit_and_monitoring(self) -> None:
        audit = ReportingAudit()
        heart = ReportingHealth()
        metrics = ReportingMetrics()
        report = Report(title="Audit Report")

        audit.record(
            report_id="r-1",
            execution_id="e-1",
            correlation_id="c-1",
            renderer="html",
            template="corporate",
            duration_ms=12,
            pages=1,
            warnings=("warn",),
            errors=(),
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        health = ReportingMonitor(health=heart, metrics=metrics)
        health.record_report_generated(report)
        health.record_renderer_failure("html")
        health.record_template_usage("corporate")
        health.record_export_size(2048)

        assert audit.records[-1].report_id == "r-1"
        assert health.health.reports_generated == 1
        assert health.health.renderer_failures == 1
        assert health.health.template_usage["corporate"] == 1
        assert health.health.export_size_bytes == 2048
        assert metrics.report_count == 1

    def test_reporting_events(self) -> None:
        events = [
            ReportStarted(report_id="r-1"),
            ReportCompleted(report_id="r-1"),
            ReportFailed(report_id="r-1", error="boom"),
            ExportStarted(report_id="r-1"),
            ExportCompleted(report_id="r-1"),
            RetryStarted(report_id="r-1", attempt=1),
            RetryCompleted(report_id="r-1", attempt=1),
        ]
        assert [event.__class__.__name__ for event in events] == [
            "ReportStarted",
            "ReportCompleted",
            "ReportFailed",
            "ExportStarted",
            "ExportCompleted",
            "RetryStarted",
            "RetryCompleted",
        ]

    def test_configuration_and_exceptions(self) -> None:
        config = ReportingConfig()
        assert config.output_format == "html"
        assert config.template_name == "corporate"
        assert config.enable_streaming is True

        with pytest.raises(ReportingError):
            raise ReportingError("boom")

        with pytest.raises(RendererError):
            raise RendererError("boom")

    def test_engine_supports_dependency_injection(self) -> None:
        renderer = FakeRenderer(name="fake")
        engine = ReportEngine(renderer=renderer)
        assert engine.render(Report(title="X")) == "rendered:fake:X"
