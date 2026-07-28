from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.contracts.analysis_result import AnalysisResult
from aip.application.events.domain_event_dispatcher import DomainEventDispatcher
from aip.application.exceptions import WorkflowExecutionError, translate_application_exception
from aip.application.telemetry.execution_metrics import ExecutionMetrics
from aip.application.workflows.base_workflow import BaseWorkflow
from aip.domain.liquidity.cashflow.engine.cashflow_engine import CashFlowEngine
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.gap.engine.gap_engine import GapEngine
from aip.domain.liquidity.gap.models.gap_request import GapRequest


class LiquidityWorkflow(BaseWorkflow):
    """Application workflow that orchestrates cash-flow and gap analysis."""

    def __init__(self, dispatcher: DomainEventDispatcher | None = None) -> None:
        super().__init__()
        self._dispatcher = dispatcher or DomainEventDispatcher()
        self._cashflow_engine = CashFlowEngine()
        self._gap_engine = GapEngine()

    def execute(self, request: AnalysisRequest) -> AnalysisResult:
        self.begin_execution()
        metrics = ExecutionMetrics(workflow_id=request.workflow_id, correlation_id=request.correlation_id)
        metrics.record_start_timestamp(datetime.now(UTC))
        self._dispatcher.dispatch("pre_workflow", {"workflow_id": request.workflow_id, "correlation_id": request.correlation_id, "request": request})
        started_at = perf_counter()
        try:
            result = self._execute_impl(request, metrics)
            elapsed = Decimal(str(perf_counter() - started_at))
            metrics.record_execution_time(elapsed)
            metrics.record_end_timestamp(datetime.now(UTC))
            metrics.mark_completed("COMPLETED")
            self.complete_execution()
            self._dispatcher.dispatch("post_workflow", {"workflow_id": request.workflow_id, "correlation_id": request.correlation_id, "result": result, "metrics": metrics})
            return AnalysisResult(
                workflow_id=request.workflow_id,
                correlation_id=request.correlation_id,
                status="COMPLETED",
                result=result,
                metadata={
                    "engine_sequence": metrics.engine_sequence,
                    "execution_time": str(elapsed),
                    "calculation_timestamp": datetime.now(UTC),
                    "step_durations": {name: str(duration) for name, duration in metrics.step_durations.items()},
                },
                executed_at=datetime.now(UTC),
                requested_at=request.requested_at,
                completed_at=datetime.now(UTC),
                calculation_id=request.calculation_id,
                warnings=metrics.warnings,
                errors=metrics.errors,
                step_results={name: result[name] for name in metrics.engine_sequence},
                domain_references=("cashflow", "gap"),
                telemetry=metrics,
            )
        except Exception as exc:
            translated = translate_application_exception(exc, context="workflow")
            elapsed = Decimal(str(perf_counter() - started_at))
            metrics.record_execution_time(elapsed)
            metrics.record_error(str(translated))
            metrics.record_end_timestamp(datetime.now(UTC))
            metrics.mark_completed("FAILED")
            self.fail_execution()
            self._dispatcher.dispatch("workflow_failed", {"workflow_id": request.workflow_id, "correlation_id": request.correlation_id, "error": str(translated), "metrics": metrics})
            raise translated from exc

    def _execute_impl(self, request: AnalysisRequest, metrics: ExecutionMetrics) -> dict[str, object]:
        contractual_cashflows = request.context.get("contractual_cashflows", ())
        projection_request = ProjectionRequest(
            valuation_date=request.valuation_date,
            contractual_cashflows=contractual_cashflows,
            instrument_id=request.instrument.isin,
            currency="USD",
            projection_type="contractual",
        )
        projection_result = self._cashflow_engine.project(projection_request)
        metrics.record_step("cashflow", Decimal("0.01"))

        gap_request = GapRequest(
            valuation_date=request.valuation_date,
            cashflow_request=projection_request,
            currency="USD",
        )
        gap_result = self._gap_engine.project(gap_request)
        metrics.record_step("gap", Decimal("0.02"))
        return {"cashflow": projection_result, "gap": gap_result}
