from __future__ import annotations

from aip.product.demo.bootstrap.demo_bootstrap import DemoBootstrap
from aip.product.demo.configuration.demo_config import DemoConfig


def test_bootstrap_succeeds_with_demo_config() -> None:
    bootstrap = DemoBootstrap(DemoConfig())
    factory, steps = bootstrap.bootstrap(correlation_id="corr-test")
    assert factory is bootstrap.factory
    assert len(steps) == 8
    assert steps[0].component_name == "configuration"
    assert steps[-1].component_name == "notifications"
