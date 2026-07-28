from __future__ import annotations

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.contracts.analysis_result import AnalysisResult
from aip.application.workflows.relative_value_workflow import RelativeValueWorkflow


class InvestmentDecisionOrchestrator:
    """Coordinates investment decision workflows."""

    def __init__(self, workflow: RelativeValueWorkflow | None = None) -> None:
        self._workflow = workflow or RelativeValueWorkflow()

    def execute(self, request: AnalysisRequest) -> AnalysisResult:
        return self._workflow.execute(request)
