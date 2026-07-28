from __future__ import annotations

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.contracts.analysis_result import AnalysisResult
from aip.application.workflows.liquidity_workflow import LiquidityWorkflow


class LiquidityAnalysisOrchestrator:
    """Coordinates liquidity analysis workflows."""

    def __init__(self, workflow: LiquidityWorkflow | None = None) -> None:
        self._workflow = workflow or LiquidityWorkflow()

    def execute(self, request: AnalysisRequest) -> AnalysisResult:
        return self._workflow.execute(request)
