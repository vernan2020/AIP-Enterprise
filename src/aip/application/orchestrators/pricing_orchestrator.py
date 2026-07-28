from __future__ import annotations

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.contracts.analysis_result import AnalysisResult
from aip.application.exceptions import translate_application_exception
from aip.application.workflows.relative_value_workflow import RelativeValueWorkflow


class PricingOrchestrator:
    """Coordinates pricing-oriented workflows without owning business rules."""

    def __init__(self, workflow: RelativeValueWorkflow | None = None) -> None:
        self._workflow = workflow or RelativeValueWorkflow()

    def execute(self, request: AnalysisRequest) -> AnalysisResult:
        try:
            return self._workflow.execute(request)
        except Exception as exc:
            raise translate_application_exception(exc, context="orchestrator") from exc
