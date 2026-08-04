from __future__ import annotations

from datetime import date
from pathlib import Path

import openpyxl
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


def test_environment_loader_reads_vector_configuration_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP_EXECUTION_MODE", "CONFIGURED")
    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "false")
    monkeypatch.setenv("AIP_VECTOR_ENABLED", "true")
    monkeypatch.setenv("AIP_VECTOR_ROOT", r"C:\\Institutional Data\\Vector")
    monkeypatch.setenv("AIP_VECTOR_DIRECTORY_ALIASES", "vector,Vector Pip,vector pipca")
    monkeypatch.setenv("AIP_VECTOR_SUPPORTED_EXTENSIONS", ".xls,.xlsx")

    config = EnvironmentLoader().load()
    vector_config = config.source_config["vector"]

    assert vector_config["enabled"] is True
    assert vector_config["root"] == r"C:\Institutional Data\Vector"
    assert vector_config["directory_aliases"] == ["vector", "Vector Pip", "vector pipca"]
    assert vector_config["supported_extensions"] == [".xls", ".xlsx"]


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


def test_portfolio_master_discovery_uses_canonical_maestro_path_and_ignores_unrelated_dirs(tmp_path: Path) -> None:
    root = tmp_path / "institutional"
    (root / "Inversiones" / "2026" / "maestro").mkdir(parents=True)
    (root / "Inversiones" / "2026" / "cuadre").mkdir(parents=True)
    (root / "Inversiones" / "2026" / "ESCRITORIO").mkdir(parents=True)
    (root / "Inversiones" / "2026" / "informe").mkdir(parents=True)
    (root / "Inversiones" / "2026" / "limites").mkdir(parents=True)
    (root / "Inversiones" / "2026" / "maestro" / "31-12-2026.xls").write_text("x")
    (root / "Inversiones" / "2026" / "cuadre" / "01-01-2026.xls").write_text("x")
    (root / "Inversiones" / "2026" / "ESCRITORIO" / "02-02-2026.xls").write_text("x")
    (root / "Inversiones" / "2026" / "informe" / "03-03-2026.xls").write_text("x")
    (root / "Inversiones" / "2026" / "limites" / "04-04-2026.xls").write_text("x")

    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root)),
    )

    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "HEALTHY"
    assert payload["portfolio_master"]["file_name"] == "31-12-2026.xls"
    assert payload["portfolio_master"]["valuation_date"] == "2026-12-31"


def test_portfolio_master_discovery_supports_root_already_at_inversiones(tmp_path: Path) -> None:
    root = tmp_path / "Inversiones"
    (root / "2024" / "maestro").mkdir(parents=True)
    (root / "2024" / "maestro" / "31-12-2024.xlsx").write_text("x")

    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root)),
    )

    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["status"] == "HEALTHY"
    assert payload["portfolio_master"]["file_name"] == "31-12-2024.xlsx"
    assert payload["portfolio_master"]["valuation_date"] == "2024-12-31"


def test_portfolio_master_prefers_date_only_file_over_ambiguous_suffixes(tmp_path: Path) -> None:
    root = tmp_path / "institutional"
    (root / "Inversiones" / "2023" / "maestro").mkdir(parents=True)
    (root / "Inversiones" / "2023" / "maestro" / "01-01-2023.xls").write_text("x")
    (root / "Inversiones" / "2023" / "maestro" / "01-01-2023 maestro inversiones.xls").write_text("x")
    (root / "Inversiones" / "2023" / "maestro" / "01-01-2023-2.xls").write_text("x")

    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root)),
    )

    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    assert payload["portfolio_master"]["file_name"] == "01-01-2023.xls"
    assert payload["portfolio_master"]["valuation_date"] == "2023-01-01"


def test_provider_emits_full_diagnostics_and_enriches_positions(tmp_path: Path) -> None:
    root = tmp_path / "institutional"
    maestro_dir = root / "Inversiones" / "2026" / "maestro" / "julio"
    vector_dir = root / "Inversiones" / "2026" / "vector" / "julio"
    maestro_dir.mkdir(parents=True)
    vector_dir.mkdir(parents=True)

    maestro_path = maestro_dir / "29-07-2026.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Maestro"
    worksheet.append(["Resumen institucional", ""])
    worksheet.append(["", ""])
    worksheet.append(["ISIN", "Emisor", "Valor de Mercado", "Valor en Libros"])
    worksheet.append(["US1234567890", "Banco Central", 1000000, 980000])
    worksheet.append(["", "Banco Central", 1000000, 980000])
    workbook.save(maestro_path)

    vector_path = vector_dir / "29-07-2026.txt"
    vector_path.write_text(
        "BCCR  BC12M120826 12/08/2026  100.0 100.008344  2.842 0.000000 0\n"
        "bad line without enough fields\n",
        encoding="utf-8",
    )

    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False, data_cutoff_date=date(2026, 7, 29))
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root), vector_path=str(vector_dir)),
        metadata={"diagnostic_mode": True},
    )

    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    assert payload["positions"]
    assert payload["positions"][0]["isin"] == "US1234567890"
    assert payload["positions"][0]["vector_match"]["matched"] is False
    assert payload["portfolio_master"]["diagnostics"]["trace"]["records_read"] == 2
    assert payload["portfolio_master"]["diagnostics"]["trace"]["records_discarded"] == 0
    assert payload["portfolio_master"]["diagnostics"]["trace"]["record_trace"][0]["status"] == "accepted"
    assert payload["portfolio_master"]["diagnostics"]["trace"]["record_trace"][1]["status"] == "accepted"
    assert payload["price_vector"]["diagnostics"]["trace"]["records_discarded"] == 1
    assert payload["price_vector"]["diagnostics"]["trace"]["records_valid"] == 1


def test_vector_discovery_uses_supported_aliases_and_skips_maestro(tmp_path: Path) -> None:
    root = tmp_path / "institutional"
    (root / "Inversiones" / "2026" / "maestro").mkdir(parents=True)
    (root / "Inversiones" / "2026" / "vector").mkdir(parents=True)
    (root / "Inversiones" / "2026" / "maestro" / "31-12-2026.xls").write_text("x")
    (root / "Inversiones" / "2026" / "vector" / "31-12-2026.xlsx").write_text("x")

    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root), vector_path=str(root / "Inversiones" / "2026" / "vector")),
    )

    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    assert payload["price_vector"]["status"] == "HEALTHY"
    assert payload["price_vector"]["file_name"] == "31-12-2026.xlsx"
    assert payload["price_vector"]["valuation_date"] == "2026-12-31"
    assert payload["price_vector"]["directory"] == str(root / "Inversiones" / "2026" / "vector")


def test_vector_discovery_uses_explicit_root_precedence(tmp_path: Path) -> None:
    root = tmp_path / "institutional"
    explicit_root = root / "custom-vector"
    explicit_root.mkdir(parents=True)
    (explicit_root / "31-12-2026.xlsx").write_text("x")

    config = DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    source_config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(root), vector_path=str(explicit_root)),
    )

    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()

    assert payload["price_vector"]["status"] == "HEALTHY"
    assert payload["price_vector"]["file_name"] == "31-12-2026.xlsx"
    assert payload["price_vector"]["directory"] == str(explicit_root)
