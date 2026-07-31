from __future__ import annotations

import pytest

from aip.product.configured.adapters.configured_portfolio_provider import ConfiguredPortfolioProvider
from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig, FolderWatchSourceConfig, SQLServerSourceConfig
from aip.product.configured.configuration.institutional_paths import resolve_institutional_path
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


def test_environment_loader_uses_institutional_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIP_SQLSERVER_VIEW", raising=False)
    monkeypatch.delenv("AIP_SQLSERVER_SCENARIOS", raising=False)
    monkeypatch.setenv("AIP_PORTFOLIO_ROOT", r"C:\\Institutional Data\\Inversiones")
    monkeypatch.setenv("AIP_ICL_ROOT", r"C:\\Institutional Data\\ICL")
    monkeypatch.setenv("AIP_CURVES_WORKBOOK", r"C:\\Users\\Jane Doe\\OneDrive\\Grafico Curvas de Rendimiento.xlsx")

    config = EnvironmentLoader().load()
    sql_config = config.source_config["sql_server"]
    folder_config = config.source_config["folder_watch"]

    assert sql_config["view"] == "VISTA_1514_1515_1516"
    assert sql_config["scenario_filters"] == ["Reales", "Presupuesto 2026%"]
    assert folder_config["portfolio_root"] == r"C:\Institutional Data\Inversiones"
    assert folder_config["icl_root"] == r"C:\Institutional Data\ICL"
    assert config.source_config["curves"]["workbook"] == r"C:\Users\Jane Doe\OneDrive\Grafico Curvas de Rendimiento.xlsx"


def test_path_resolution_supports_spaces_and_unc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP_INSTITUTIONAL_DATA_ROOT", r"C:\\Institutional Data")
    resolved = resolve_institutional_path(r"\\server\share\folder with spaces")
    assert resolved == r"\\server\share\folder with spaces"

    joined = resolve_institutional_path(r"Inversiones\2026", base_root=r"C:\\Institutional Data")
    assert joined == r"C:\Institutional Data\Inversiones\2026"


def test_configured_portfolio_provider_returns_empty_state_without_demo_data() -> None:
    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    source_config = ConfiguredSourceConfig(
        sql_server=SQLServerSourceConfig(enabled=False),
        folder_watch=FolderWatchSourceConfig(enabled=False),
    )

    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    assert payload["positions"] == []
    assert payload["market_value"] == 0.0
    assert payload["book_value"] == 0.0
    assert payload["hqla_percent"] == 0.0
    assert payload["mil_eligible_percent"] == 0.0
    assert "Acme Bank" not in str(payload)
    assert "Blue Ridge" not in str(payload)
