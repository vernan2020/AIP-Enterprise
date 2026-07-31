from __future__ import annotations

import pytest

from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.product.demo.exceptions import DemoConfigurationError
from aip.product.demo.workflows.initial_load_workflow import InitialLoadWorkflow
from aip.product.demo.workflows.refresh_all_workflow import RefreshAllWorkflow


class DummyPortfolioProvider:
    def get_portfolio(self) -> dict[str, object]:
        return {"portfolio_name": "Configured Portfolio", "positions": []}


class DummyMarketProvider:
    def get_market(self) -> dict[str, object]:
        return {"market_status": "Configured"}


class DummyLiquidityProvider:
    def get_liquidity(self) -> dict[str, object]:
        return {"liquidity_gap": 0.0}


class DummyHealthProvider:
    def get_health(self) -> dict[str, object]:
        return {"sql_server": "DEGRADED", "folder_watch": "DEGRADED", "bccr": "DEGRADED"}


def test_environment_loader_prefers_canonical_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP_EXECUTION_MODE", "CONFIGURED")
    monkeypatch.setenv("AIP_DEMO_EXECUTION_MODE", "DEMO")
    monkeypatch.setenv("AIP_ENVIRONMENT", "staging")
    monkeypatch.setenv("AIP_DEMO_ENVIRONMENT", "demo")
    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "false")
    monkeypatch.setenv("AIP_SQLSERVER_ENABLED", "true")

    config = EnvironmentLoader().load()

    assert config.execution_mode == "CONFIGURED"
    assert config.environment_name == "staging"
    assert config.demo_mode_enabled is False
    assert config.source_config["sql_server"]["enabled"] is True


def test_environment_loader_rejects_invalid_execution_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP_EXECUTION_MODE", "INVALID")
    with pytest.raises(DemoConfigurationError):
        EnvironmentLoader().load()


def test_workflows_accept_provider_protocols() -> None:
    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    workflow = InitialLoadWorkflow(
        config,
        portfolio_provider=DummyPortfolioProvider(),
        market_provider=DummyMarketProvider(),
        liquidity_provider=DummyLiquidityProvider(),
        health_provider=DummyHealthProvider(),
    )
    result = workflow.execute("corr-protocol")

    assert result["portfolio"]["portfolio_name"] == "Configured Portfolio"
    assert result["market"]["market_status"] == "Configured"
    assert result["liquidity"]["liquidity_gap"] == 0.0

    refresh_workflow = RefreshAllWorkflow(
        config,
        portfolio_provider=DummyPortfolioProvider(),
        market_provider=DummyMarketProvider(),
        liquidity_provider=DummyLiquidityProvider(),
        health_provider=DummyHealthProvider(),
    )
    refresh_result = refresh_workflow.execute("corr-refresh")
    assert refresh_result["portfolio"]["portfolio_name"] == "Configured Portfolio"
