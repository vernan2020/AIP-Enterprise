from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.contracts.analysis_result import AnalysisResult
from aip.application.events.domain_event_dispatcher import DomainEventDispatcher
from aip.application.exceptions import (
    ContractValidationError,
    EventDispatchError,
    OrchestratorExecutionError,
    TelemetryError,
    WorkflowExecutionError,
    translate_application_exception,
)
from aip.application.kernel import ApplicationKernel
from aip.application.orchestrators.investment_decision_orchestrator import (
    InvestmentDecisionOrchestrator,
)
from aip.application.orchestrators.liquidity_analysis_orchestrator import (
    LiquidityAnalysisOrchestrator,
)
from aip.application.orchestrators.portfolio_analysis_orchestrator import (
    PortfolioAnalysisOrchestrator,
)
from aip.application.orchestrators.pricing_orchestrator import PricingOrchestrator
from aip.application.telemetry.execution_metrics import ExecutionMetrics
from aip.application.workflows.base_workflow import WorkflowLifecycleState
from aip.application.workflows.hqla_workflow import HQLAWorkflow
from aip.application.workflows.liquidity_workflow import LiquidityWorkflow
from aip.application.workflows.relative_value_workflow import RelativeValueWorkflow
from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.shared.conventions import DayCountConvention


class _StubInstrument(GovernmentBond):
    def __init__(self) -> None:
        issuer = Issuer(code="gov", name="Government", issuer_type=IssuerType.GOVERNMENT)
        super().__init__(
            isin="US123",
            name="Stub Bond",
            issuer=issuer,
            currency="USD",
            settlement_calendar="USD",
            business_day_convention="FOLLOWING",
            day_count_convention=DayCountConvention.ACTUAL_365,
            issue_date=date(2020, 1, 1),
            settlement_date=date(2020, 1, 3),
            maturity_date=date(2030, 1, 1),
            coupon_schedule=None,
            nominal_value=Decimal("1000000"),
            book_value=Decimal("1000000"),
            market_value=Decimal("1000000"),
            face_value=Decimal("1000000"),
            outstanding_amount=Decimal("1000000"),
            yield_rate=Decimal("0.03"),
            duration=Decimal("4"),
            modified_duration=Decimal("4"),
            convexity=Decimal("0.5"),
            dirty_price=Decimal("1000000"),
            clean_price=Decimal("1000000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.05"),
            payment_frequency=PaymentFrequency.SEMIANNUAL,
        )


class _StubPricingService:
    def price(self, instrument: Any, valuation_date: date, market_yield: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
        return (
            Decimal("100"),
            Decimal("100"),
            Decimal("2"),
            Decimal("100"),
            market_yield,
            Decimal("4"),
            Decimal("3"),
            Decimal("0.5"),
            Decimal("0.01"),
            Decimal("0.02"),
        )


class _FailingWorkflow(RelativeValueWorkflow):
    def _execute_impl(self, request: AnalysisRequest, metrics: ExecutionMetrics) -> object:
        raise RuntimeError("boom")


def _make_request() -> AnalysisRequest:
    instrument = _StubInstrument()
    curve = YieldCurve(
        valuation_date=date(2026, 1, 1),
        currency="USD",
        points=(
            CurvePoint(tenor=Decimal("1"), zero_rate=Decimal("0.03")),
            CurvePoint(tenor=Decimal("10"), zero_rate=Decimal("0.04")),
        ),
    )
    return AnalysisRequest(
        workflow_id="wf-1",
        correlation_id="corr-1",
        valuation_date=date(2026, 1, 1),
        instrument=instrument,
        market_yield=Decimal("0.04"),
        curve=curve,
        market_price=Decimal("1000000"),
        benchmark_yield=Decimal("0.05"),
        context={
            "contractual_cashflows": (
                CashFlow(payment_date=date(2026, 6, 1), amount=Decimal("100000"), currency="USD", cash_flow_type="coupon"),
            ),
        },
    )


def test_workflow_ordering_and_engine_reuse() -> None:
    request = _make_request()
    workflow = RelativeValueWorkflow()
    result = workflow.execute(request)

    assert result.workflow_id == "wf-1"
    assert result.correlation_id == "corr-1"
    assert result.metadata["engine_sequence"] == ("pricing", "relative_value")
    assert result.metadata["calculation_timestamp"] is not None
    assert result.telemetry is not None
    assert result.step_results["pricing"] is not None
    assert result.step_results["relative_value"] is not None


def test_liquidity_workflow_uses_existing_domain_engines() -> None:
    request = _make_request()
    workflow = LiquidityWorkflow()
    result = workflow.execute(request)

    assert result.metadata["engine_sequence"] == ("cashflow", "gap")
    assert result.status == "COMPLETED"
    assert result.telemetry is not None
    assert result.domain_references == ("cashflow", "gap")


def test_liquidity_workflow_translates_execution_failures() -> None:
    request = _make_request()

    class _FailingLiquidityWorkflow(LiquidityWorkflow):
        def _execute_impl(self, request: AnalysisRequest, metrics: ExecutionMetrics) -> dict[str, object]:
            raise RuntimeError("liquidity boom")

    workflow = _FailingLiquidityWorkflow()
    with pytest.raises(WorkflowExecutionError):
        workflow.execute(request)


def test_hqla_workflow_creates_hqla_result() -> None:
    request = _make_request()
    workflow = HQLAWorkflow()
    result = workflow.execute(request)

    assert result.metadata["engine_sequence"] == ("hqla",)
    assert result.status == "COMPLETED"
    assert result.telemetry is not None
    assert result.domain_references == ("hqla",)


def test_hqla_workflow_translates_execution_failures() -> None:
    request = _make_request()

    class _FailingHQLAWorkflow(HQLAWorkflow):
        def _execute_impl(self, request: AnalysisRequest, metrics: ExecutionMetrics) -> object:
            raise RuntimeError("hqla boom")

    workflow = _FailingHQLAWorkflow()
    with pytest.raises(WorkflowExecutionError):
        workflow.execute(request)


def test_orchestrators_delegate_without_duplication() -> None:
    request = _make_request()
    orchestrator = PricingOrchestrator()
    result = orchestrator.execute(request)
    assert result.status == "COMPLETED"

    portfolio_orchestrator = PortfolioAnalysisOrchestrator()
    portfolio_result = portfolio_orchestrator.execute(request)
    assert portfolio_result.status == "COMPLETED"

    liquidity_orchestrator = LiquidityAnalysisOrchestrator()
    liquidity_result = liquidity_orchestrator.execute(request)
    assert liquidity_result.status == "COMPLETED"

    investment_orchestrator = InvestmentDecisionOrchestrator()
    investment_result = investment_orchestrator.execute(request)
    assert investment_result.status == "COMPLETED"


def test_execution_metrics_capture_telemetry() -> None:
    metrics = ExecutionMetrics(workflow_id="wf-1", correlation_id="corr-1")
    metrics.record_start_timestamp(datetime.now(UTC))
    metrics.record_step("pricing", Decimal("0.01"))
    metrics.record_step("relative_value", Decimal("0.02"))
    metrics.record_warning("warning")
    metrics.record_error("error")
    metrics.record_execution_time(Decimal("0.03"))
    metrics.record_end_timestamp(datetime.now(UTC))
    metrics.mark_completed("COMPLETED")

    assert metrics.workflow_id == "wf-1"
    assert metrics.correlation_id == "corr-1"
    assert metrics.step_durations["pricing"] == Decimal("0.01")
    assert metrics.warnings == ("warning",)
    assert metrics.errors == ("error",)
    assert metrics.step_order == ("pricing", "relative_value")
    assert metrics.final_status == "COMPLETED"
    assert metrics.total_duration == Decimal("0.03")


def test_domain_event_dispatcher_supports_workflow_lifecycle() -> None:
    dispatcher = DomainEventDispatcher()
    events: list[tuple[str, dict[str, Any]]] = []
    dispatcher.subscribe("pre_workflow", lambda event: events.append(("pre", event)))
    dispatcher.subscribe("post_workflow", lambda event: events.append(("post", event)))
    dispatcher.subscribe("workflow_failed", lambda event: events.append(("failed", event)))

    request = _make_request()
    workflow = RelativeValueWorkflow(dispatcher=dispatcher)
    workflow.execute(request)

    assert len(events) == 2
    assert events[0][0] == "pre"
    assert events[1][0] == "post"
    assert events[0][1]["correlation_id"] == "corr-1"


def test_domain_event_dispatcher_raises_when_configured_to_do_so() -> None:
    dispatcher = DomainEventDispatcher(raise_on_error=True)

    def failing_handler(payload: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    dispatcher.subscribe("pre_workflow", failing_handler)
    with pytest.raises(EventDispatchError):
        dispatcher.dispatch("pre_workflow", {"correlation_id": "corr"})


def test_domain_event_dispatcher_supports_unsubscribe_and_error_isolation() -> None:
    dispatcher = DomainEventDispatcher(raise_on_error=False)
    events: list[tuple[str, dict[str, Any]]] = []

    def failing_handler(payload: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    def good_handler(payload: dict[str, Any]) -> None:
        events.append(("good", payload))

    dispatcher.subscribe("pre_workflow", failing_handler)
    dispatcher.subscribe("pre_workflow", good_handler)
    dispatcher.dispatch("pre_workflow", {"correlation_id": "corr-2"})

    assert len(events) == 1
    dispatcher.unsubscribe("pre_workflow", good_handler)
    dispatcher.dispatch("pre_workflow", {"correlation_id": "corr-2"})
    assert len(events) == 1


def test_workflow_failures_propagate_and_emit_events() -> None:
    dispatcher = DomainEventDispatcher()
    events: list[tuple[str, dict[str, Any]]] = []
    dispatcher.subscribe("workflow_failed", lambda event: events.append(("failed", event)))

    workflow = _FailingWorkflow(dispatcher=dispatcher)
    with pytest.raises(WorkflowExecutionError):
        workflow.execute(AnalysisRequest(workflow_id="wf-2", correlation_id="corr-2", valuation_date=date(2026, 1, 1), instrument=_StubInstrument(), market_yield=Decimal("0.04"), curve=YieldCurve(valuation_date=date(2026, 1, 1), currency="USD", points=(CurvePoint(tenor=Decimal("1"), zero_rate=Decimal("0.03")),))))

    assert len(events) == 1


def test_contracts_validate_required_identifiers_and_timezone() -> None:
    with pytest.raises(ContractValidationError):
        AnalysisRequest(workflow_id="", correlation_id="corr", valuation_date=date(2026, 1, 1), instrument=_StubInstrument(), market_yield=Decimal("0.04"))
    with pytest.raises(ContractValidationError):
        AnalysisRequest(workflow_id="wf", correlation_id="", valuation_date=date(2026, 1, 1), instrument=_StubInstrument(), market_yield=Decimal("0.04"))
    with pytest.raises(ContractValidationError):
        AnalysisRequest(workflow_id="wf", correlation_id="corr", valuation_date=date(2026, 1, 1), instrument=_StubInstrument(), market_yield=Decimal("0.04"), requested_at=datetime(2026, 1, 1))


def test_results_preserve_metadata_and_decimals() -> None:
    result = AnalysisResult(
        workflow_id="wf",
        correlation_id="corr",
        status="COMPLETED",
        result={"value": Decimal("1.23")},
        metadata={"nested": {"flag": True}},
        warnings=("warn",),
        errors=("err",),
        step_results={"pricing": Decimal("1.23")},
        domain_references=("pricing",),
    )

    assert result.metadata["nested"]["flag"] is True
    assert result.result["value"] == Decimal("1.23")
    assert result.warnings == ("warn",)
    assert result.errors == ("err",)


def test_analysis_contracts_validate_timezone_and_ordering() -> None:
    with pytest.raises(ContractValidationError):
        AnalysisResult(
            workflow_id="wf",
            correlation_id="corr",
            status="COMPLETED",
            result=None,
            executed_at=datetime(2026, 1, 1),
        )

    with pytest.raises(ContractValidationError):
        AnalysisResult(
            workflow_id="wf",
            correlation_id="corr",
            status="COMPLETED",
            result=None,
            requested_at=datetime(2026, 1, 2, tzinfo=UTC),
            completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_workflow_lifecycle_transitions_are_deterministic() -> None:
    workflow = RelativeValueWorkflow()
    assert workflow.lifecycle_state == WorkflowLifecycleState.CREATED
    workflow.begin_execution()
    assert workflow.lifecycle_state == WorkflowLifecycleState.RUNNING
    workflow.complete_execution()
    assert workflow.lifecycle_state == WorkflowLifecycleState.COMPLETED

    with pytest.raises(WorkflowExecutionError):
        workflow.complete_execution()

    workflow = RelativeValueWorkflow()
    workflow.begin_execution()
    workflow.mark_partially_completed()
    assert workflow.lifecycle_state == WorkflowLifecycleState.PARTIALLY_COMPLETED

    workflow = RelativeValueWorkflow()
    workflow.begin_execution()
    workflow.fail_execution()
    assert workflow.lifecycle_state == WorkflowLifecycleState.FAILED

    with pytest.raises(WorkflowExecutionError):
        workflow.complete_execution()

    workflow = RelativeValueWorkflow()
    with pytest.raises(WorkflowExecutionError):
        workflow.fail_execution()

    workflow = RelativeValueWorkflow()
    workflow.begin_execution()
    with pytest.raises(WorkflowExecutionError):
        workflow.begin_execution()

    workflow = RelativeValueWorkflow()
    with pytest.raises(WorkflowExecutionError):
        workflow.mark_partially_completed()


def test_execution_metrics_validate_inputs() -> None:
    metrics = ExecutionMetrics(workflow_id="wf", correlation_id="corr")
    with pytest.raises(TelemetryError):
        metrics.record_step("pricing", Decimal("-0.01"))
    with pytest.raises(TelemetryError):
        metrics.record_execution_time(Decimal("-0.01"))


def test_results_are_defensively_copied_and_preserve_decimals() -> None:
    metadata = {"nested": {"flag": True}}
    step_results = {"pricing": Decimal("1.23")}
    result = AnalysisResult(
        workflow_id="wf",
        correlation_id="corr",
        status="COMPLETED",
        result={"value": Decimal("1.23")},
        metadata=metadata,
        warnings=("warn",),
        errors=("err",),
        step_results=step_results,
        domain_references=("pricing",),
    )

    metadata["nested"]["flag"] = False
    step_results["pricing"] = Decimal("0")
    assert result.metadata["nested"]["flag"] is True
    assert result.step_results["pricing"] == Decimal("1.23")


def test_analysis_request_copies_context_and_assigns_deterministic_ids() -> None:
    context = {"nested": {"flag": True}}
    request = AnalysisRequest(
        workflow_id="wf",
        correlation_id="corr",
        valuation_date=date(2026, 1, 1),
        instrument=_StubInstrument(),
        market_yield=Decimal("0.04"),
        context=context,
    )
    context["nested"]["flag"] = False
    assert request.context["nested"]["flag"] is True

    deterministic_request = AnalysisRequest(
        workflow_id="wf",
        correlation_id="corr",
        valuation_date=date(2026, 1, 1),
        instrument=_StubInstrument(),
        market_yield=Decimal("0.04"),
        context={"deterministic_ids": True},
    )
    assert deterministic_request.calculation_id == "wf:corr"


def test_exception_translation_uses_application_specific_types() -> None:
    assert isinstance(translate_application_exception(ValueError("bad")), ContractValidationError)
    assert isinstance(translate_application_exception(RuntimeError("boom")), WorkflowExecutionError)
    assert isinstance(translate_application_exception(KeyError("missing"), context="orchestrator"), OrchestratorExecutionError)


def test_metrics_reject_negative_durations() -> None:
    metrics = ExecutionMetrics(workflow_id="wf", correlation_id="corr")
    with pytest.raises(TelemetryError):
        metrics.record_step("pricing", Decimal("-0.01"))
    with pytest.raises(TelemetryError):
        metrics.record_execution_time(Decimal("-0.01"))


def test_orchestrators_translate_failures_into_application_errors() -> None:
    request = _make_request()
    workflow = _FailingWorkflow()
    orchestrator = PricingOrchestrator(workflow=workflow)
    with pytest.raises(WorkflowExecutionError):
        orchestrator.execute(request)

    class _BrokenWorkflow(RelativeValueWorkflow):
        def execute(self, request: AnalysisRequest) -> AnalysisResult:
            raise ValueError("bad")

    with pytest.raises(OrchestratorExecutionError):
        PricingOrchestrator(workflow=_BrokenWorkflow()).execute(request)


def test_application_kernel_runs_and_shuts_down(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Signal:
        def __init__(self) -> None:
            self.callback: Any = None

        def connect(self, callback: Any) -> None:
            self.callback = callback

        def emit(self) -> None:
            if self.callback is not None:
                self.callback()

    class _QtApplication:
        def __init__(self) -> None:
            self.aboutToQuit = _Signal()

        def exec(self) -> int:
            return 0

    class _FakeLogger:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def info(self, message: str) -> None:
            self.messages.append(message)

    class _FakeLogging:
        def bind(self, component: str) -> _FakeLogger:
            return _FakeLogger()

    class _FakeDatabase:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class _FakeAudit:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict[str, Any]]] = []

        def record(self, name: str, payload: dict[str, Any]) -> None:
            self.events.append((name, payload))

    class _FakeWindow:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.shown = False

        def show(self) -> None:
            self.shown = True

    class _FakeServices:
        def __init__(self) -> None:
            self.logging = _FakeLogging()
            self.configuration = type("Config", (), {"settings": {}})()
            self.database = _FakeDatabase()
            self.audit = _FakeAudit()

    monkeypatch.setattr("aip.application.kernel.MainWindow", _FakeWindow)
    qt_app = _QtApplication()
    services = _FakeServices()
    kernel = ApplicationKernel(qt_application=qt_app, services=services)

    assert kernel.run() == 0
    qt_app.aboutToQuit.emit()
    assert services.database.closed is True


def test_workflows_are_deterministic() -> None:
    workflow = RelativeValueWorkflow()
    first = workflow.execute(_make_request())
    second = workflow.execute(_make_request())
    assert first.metadata["engine_sequence"] == second.metadata["engine_sequence"]
    assert first.result is not None
    assert second.result is not None
