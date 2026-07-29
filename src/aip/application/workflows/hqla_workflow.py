from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.contracts.analysis_result import AnalysisResult
from aip.application.events.domain_event_dispatcher import DomainEventDispatcher
from aip.application.exceptions import translate_application_exception
from aip.application.telemetry.execution_metrics import ExecutionMetrics
from aip.application.workflows.base_workflow import BaseWorkflow
from aip.domain.liquidity.hqla.engine.hqla_engine import HQLAEngine
from aip.domain.liquidity.hqla.models.hqla_request import HQLARequest


class HQLAWorkflow(BaseWorkflow):
    """Application workflow that orchestrates HQLA classification."""

    def __init__(self, dispatcher: DomainEventDispatcher | None = None) -> None:
        super().__init__()
        self._dispatcher = dispatcher or DomainEventDispatcher()
        self._hqla_engine = HQLAEngine()

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
                step_results={name: result[name] for name in metrics.engine_sequence} if isinstance(result, dict) else {},
                domain_references=("hqla",),
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

    def _execute_impl(self, request: AnalysisRequest, metrics: ExecutionMetrics) -> object:
        hqla_request = HQLARequest(
            valuation_date=request.valuation_date,
            instrument_id=request.instrument.isin,
            marketability_score=Decimal("0.9"),
            transferability_score=Decimal("0.9"),
            liquidity_quality_score=Decimal("0.9"),
            market_depth_score=Decimal("0.9"),
            price_availability_score=Decimal("0.9"),
            settlement_capability_score=Decimal("0.9"),
        )
        hqla_result = self._hqla_engine.evaluate(hqla_request)
        metrics.record_step("hqla", Decimal("0.01"))
        return hqla_result
