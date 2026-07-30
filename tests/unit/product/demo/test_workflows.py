from __future__ import annotations

from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.workflows.executive_refresh_workflow import ExecutiveRefreshWorkflow
from aip.product.demo.workflows.initial_load_workflow import InitialLoadWorkflow
from aip.product.demo.workflows.refresh_all_workflow import RefreshAllWorkflow


def test_initial_load_workflow_returns_consistent_context() -> None:
    workflow = InitialLoadWorkflow(DemoConfig())
    result = workflow.execute("corr-load")
    assert result["correlation_id"] == "corr-load"
    assert result["application_readiness"] == "READY"
    assert result["portfolio"]["portfolio_name"] == "Coopealianza Demo Portfolio"


def test_refresh_all_workflow_uses_single_correlation_id() -> None:
    workflow = RefreshAllWorkflow(DemoConfig())
    result = workflow.execute("corr-refresh")
    assert result["correlation_id"] == "corr-refresh"
    assert result["valuation_date"] == "2026-07-29"


def test_executive_refresh_workflow_sets_execution_context() -> None:
    workflow = ExecutiveRefreshWorkflow(DemoConfig())
    result = workflow.execute("corr-executive")
    assert result["mode"] == "DEMO"
    assert result["status"] == "READY"
