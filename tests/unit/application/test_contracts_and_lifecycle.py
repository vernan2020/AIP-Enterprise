from __future__ import annotations

from dataclasses import replace
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
    TelemetryError,
    WorkflowExecutionError,
)
from aip.application.telemetry.execution_metrics import ExecutionMetrics
from aip.application.workflows.base_workflow import BaseWorkflow, WorkflowLifecycleState
from aip.application.workflows.relative_value_workflow import RelativeValueWorkflow
from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.shared.conventions import DayCountConvention


class _Instrument(GovernmentBond):
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
        )


class _WorkflowWithFailure(BaseWorkflow):
    def execute(self) -> None:
        self.begin_execution()
        self.fail_execution()


def _make_request(**overrides: Any) -> AnalysisRequest:
    request = AnalysisRequest(
        workflow_id="wf-1",
        correlation_id="corr-1",
        valuation_date=date(2026, 1, 1),
        instrument=_Instrument(),
        market_yield=Decimal("0.04"),
        curve=YieldCurve(
            valuation_date=date(2026, 1, 1),
            currency="USD",
            points=(
                CurvePoint(tenor=Decimal("1"), zero_rate=Decimal("0.03")),
                CurvePoint(tenor=Decimal("10"), zero_rate=Decimal("0.04")),
            ),
        ),
        market_price=Decimal("1000000"),
        benchmark_yield=Decimal("0.05"),
        calculation_id="calc-1",
        requested_at=datetime(2026, 1, 1, tzinfo=UTC),
        context={"deterministic_ids": True},
    )
    return replace(request, **overrides) if overrides else request


def test_analysis_request_validates_required_identifiers() -> None:
    with pytest.raises(ContractValidationError):
        AnalysisRequest(
            workflow_id="",
            correlation_id="corr",
            valuation_date=date(2026, 1, 1),
            instrument=_Instrument(),
            market_yield=Decimal("0.04"),
        )

    with pytest.raises(ContractValidationError):
        AnalysisRequest(
            workflow_id="wf",
            correlation_id="",
            valuation_date=date(2026, 1, 1),
            instrument=_Instrument(),
            market_yield=Decimal("0.04"),
        )


def test_analysis_request_and_result_defensively_copy_metadata() -> None:
    context_payload = {"nested": {"flag": True}}
    request = AnalysisRequest(
        workflow_id="wf",
        correlation_id="corr",
        valuation_date=date(2026, 1, 1),
        instrument=_Instrument(),
        market_yield=Decimal("0.04"),
        context=context_payload,
    )
    assert request.context is not None
    context_payload["nested"]["flag"] = False
    assert request.context["nested"]["flag"] is True

    metadata_payload = {"trace": {"value": 1}}
    result = AnalysisResult(
        workflow_id="wf",
        correlation_id="corr",
        status="COMPLETED",
        result={"value": Decimal("1.23")},
        metadata=metadata_payload,
    )
    assert result.metadata["trace"]["value"] == 1
    metadata_payload["trace"]["value"] = 2
    assert result.metadata["trace"]["value"] == 1


def test_analysis_result_validates_timestamps_and_preserves_decimal_values() -> None:
    requested_at = datetime(2026, 1, 1, tzinfo=UTC)
    completed_at = datetime(2026, 1, 2, tzinfo=UTC)
    result = AnalysisResult(
        workflow_id="wf",
        correlation_id="corr",
        status="COMPLETED",
        result={"amount": Decimal("10.50")},
        requested_at=requested_at,
        completed_at=completed_at,
    )
    assert result.result["amount"] == Decimal("10.50")
    assert result.completed_at == completed_at

    with pytest.raises(ContractValidationError):
        AnalysisResult(
            workflow_id="wf",
            correlation_id="corr",
            status="COMPLETED",
            result=None,
            requested_at=completed_at,
            completed_at=requested_at,
        )


def test_execution_metrics_capture_step_order_and_reject_negative_duration() -> None:
    metrics = ExecutionMetrics(workflow_id="wf", correlation_id="corr")
    metrics.record_start_timestamp(datetime(2026, 1, 1, tzinfo=UTC))
    metrics.record_step("pricing", Decimal("0.01"))
    metrics.record_step("relative_value", Decimal("0.02"))
    metrics.record_warning("warning")
    metrics.record_error("error")
    metrics.record_execution_time(Decimal("0.03"))
    metrics.record_end_timestamp(datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC))
    metrics.mark_completed("COMPLETED")

    assert metrics.engine_sequence == ("pricing", "relative_value")
    assert metrics.step_order == ("pricing", "relative_value")
    assert metrics.total_duration == Decimal("0.03")
    assert metrics.warnings == ("warning",)
    assert metrics.errors == ("error",)

    with pytest.raises(TelemetryError):
        metrics.record_step("bad", Decimal("-0.01"))


def test_domain_event_dispatcher_preserves_order_and_isolates_handler_failure() -> None:
    dispatcher = DomainEventDispatcher(raise_on_error=False)
    events: list[tuple[str, dict[str, Any]]] = []

    def fail_handler(payload: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    dispatcher.subscribe("pre_workflow", lambda payload: events.append(("pre", payload)))
    dispatcher.subscribe("pre_workflow", fail_handler)
    dispatcher.subscribe("pre_workflow", lambda payload: events.append(("pre-2", payload)))
    dispatcher.dispatch("pre_workflow", {"workflow_id": "wf"})

    assert [event[0] for event in events] == ["pre", "pre-2"]

    dispatcher.unsubscribe("pre_workflow", lambda payload: events.append(("ignored", payload)))
    dispatcher.dispatch("pre_workflow", {"workflow_id": "wf-2"})


def test_domain_event_dispatcher_raises_when_configured() -> None:
    dispatcher = DomainEventDispatcher(raise_on_error=True)
    dispatcher.subscribe(
        "workflow_failed", lambda payload: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(EventDispatchError):
        dispatcher.dispatch("workflow_failed", {"workflow_id": "wf"})


def test_base_workflow_lifecycle_transitions_are_deterministic() -> None:
    workflow = _WorkflowWithFailure()
    workflow.begin_execution()
    workflow.fail_execution()
    assert workflow.lifecycle_state == WorkflowLifecycleState.FAILED

    with pytest.raises(WorkflowExecutionError):
        workflow.complete_execution()

    another = BaseWorkflow()
    with pytest.raises(WorkflowExecutionError):
        another.complete_execution()


def test_relative_value_workflow_uses_existing_domain_engines_and_preserves_correlation_id() -> (
    None
):
    request = _make_request()
    workflow = RelativeValueWorkflow()
    result = workflow.execute(request)

    assert result.status == "COMPLETED"
    assert result.correlation_id == request.correlation_id
    assert result.telemetry is not None
    assert result.domain_references == ("pricing", "relative_value")
