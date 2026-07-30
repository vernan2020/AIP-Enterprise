from __future__ import annotations

from aip.product.demo.bootstrap.demo_bootstrap import DemoBootstrap
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.workflows.initial_load_workflow import InitialLoadWorkflow


def test_demo_bootstrap_initial_load_and_viewmodel_context() -> None:
    config = DemoConfig()
    bootstrap = DemoBootstrap(config)
    factory, steps = bootstrap.bootstrap(correlation_id="corr-runtime")
    workflow = factory.initial_load_workflow()
    result = workflow.execute("corr-runtime")
    assert result["correlation_id"] == "corr-runtime"
    assert result["application_readiness"] == "READY"
    assert any(step.correlation_id == "corr-runtime" for step in steps)
