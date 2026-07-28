from __future__ import annotations

from aip.application.contracts.analysis_request import AnalysisRequest
from aip.application.workflows.liquidity_workflow import LiquidityWorkflow
from aip.application.workflows.relative_value_workflow import RelativeValueWorkflow
from aip.application.workflows.hqla_workflow import HQLAWorkflow


def test_application_workflows_preserve_identifiers_and_steps(analysis_request, treasury_instrument) -> None:
    relative_value_result = RelativeValueWorkflow().execute(analysis_request)
    liquidity_result = LiquidityWorkflow().execute(analysis_request)
    hqla_result = HQLAWorkflow().execute(analysis_request)

    assert relative_value_result.workflow_id == analysis_request.workflow_id
    assert relative_value_result.correlation_id == analysis_request.correlation_id
    assert relative_value_result.calculation_id == analysis_request.calculation_id
    assert relative_value_result.metadata["engine_sequence"] == ("pricing", "relative_value")
    assert liquidity_result.metadata["engine_sequence"] == ("cashflow", "gap")
    assert hqla_result.metadata["engine_sequence"] == ("hqla",)
    assert relative_value_result.status == "COMPLETED"
    assert liquidity_result.status == "COMPLETED"
    assert hqla_result.status == "COMPLETED"
