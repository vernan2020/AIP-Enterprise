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
from aip.domain.pricing.engine.pricing_engine import PricingEngine
from aip.domain.pricing.models.pricing_request import PricingRequest
from aip.domain.relative_value.engine.relative_value_engine import RelativeValueEngine
from aip.domain.relative_value.models.relative_value_request import RelativeValueRequest


class RelativeValueWorkflow(BaseWorkflow):
    """Application workflow that orchestrates pricing and relative-value evaluation."""

    def __init__(self, dispatcher: DomainEventDispatcher | None = None) -> None:
        super().__init__()
        self._dispatcher = dispatcher or DomainEventDispatcher()
        self._pricing_engine = PricingEngine()
        self._relative_value_engine = RelativeValueEngine()

    def execute(self, request: AnalysisRequest) -> AnalysisResult:
        self.begin_execution()
        metrics = ExecutionMetrics(
            workflow_id=request.workflow_id, correlation_id=request.correlation_id
        )
        metrics.record_start_timestamp(datetime.now(UTC))
        self._dispatcher.dispatch(
            "pre_workflow",
            {
                "workflow_id": request.workflow_id,
                "correlation_id": request.correlation_id,
                "request": request,
            },
        )
        started_at = perf_counter()
        try:
            result = self._execute_impl(request, metrics)
            elapsed = Decimal(str(perf_counter() - started_at))
            metrics.record_execution_time(elapsed)
            metrics.record_end_timestamp(datetime.now(UTC))
            metrics.mark_completed("COMPLETED")
            self.complete_execution()
            self._dispatcher.dispatch(
                "post_workflow",
                {
                    "workflow_id": request.workflow_id,
                    "correlation_id": request.correlation_id,
                    "result": result,
                    "metrics": metrics,
                },
            )
            return AnalysisResult(
                workflow_id=request.workflow_id,
                correlation_id=request.correlation_id,
                status="COMPLETED",
                result=result,
                metadata={
                    "engine_sequence": metrics.engine_sequence,
                    "execution_time": str(elapsed),
                    "calculation_timestamp": datetime.now(UTC),
                    "step_durations": {
                        name: str(duration) for name, duration in metrics.step_durations.items()
                    },
                },
                executed_at=datetime.now(UTC),
                requested_at=request.requested_at,
                completed_at=datetime.now(UTC),
                calculation_id=request.calculation_id,
                warnings=metrics.warnings,
                errors=metrics.errors,
                step_results={name: result[name] for name in metrics.engine_sequence},
                domain_references=("pricing", "relative_value"),
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
            self._dispatcher.dispatch(
                "workflow_failed",
                {
                    "workflow_id": request.workflow_id,
                    "correlation_id": request.correlation_id,
                    "error": str(translated),
                    "metrics": metrics,
                },
            )
            raise translated from exc

    def _execute_impl(
        self, request: AnalysisRequest, metrics: ExecutionMetrics
    ) -> dict[str, object]:
        pricing_request = PricingRequest(
            valuation_date=request.valuation_date,
            instrument=request.instrument,
            market_yield=request.market_yield,
        )
        pricing_result = self._pricing_engine.price(pricing_request)
        metrics.record_step("pricing", Decimal("0.01"))

        relative_value_request = RelativeValueRequest(
            valuation_date=request.valuation_date,
            instrument=request.instrument,
            observed_market_price=request.market_price or Decimal("100"),
            observed_market_yield=request.market_yield,
            reference_curve=request.curve,
            benchmark_yield=request.benchmark_yield,
        )
        relative_value_result = self._relative_value_engine.evaluate(relative_value_request)
        metrics.record_step("relative_value", Decimal("0.02"))
        return {
            "pricing": pricing_result,
            "relative_value": relative_value_result,
        }
