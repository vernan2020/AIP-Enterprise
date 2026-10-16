from __future__ import annotations

from datetime import date

from aip.product.configured.configuration.configured_source_config import (
    BCCRSourceConfig,
    ConfiguredSourceConfig,
    FolderWatchSourceConfig,
    XMLConfiaSourceConfig,
)
from aip.product.configured.global_source_preflight_cli import preflight


def test_preflight_reports_configuration_not_connectivity(tmp_path) -> None:
    config = ConfiguredSourceConfig(
        folder_watch=FolderWatchSourceConfig(
            enabled=True,
            portfolio_root=str(tmp_path),
            icl_root=str(tmp_path),
        ),
        bccr=BCCRSourceConfig(
            enabled=True,
            name="private-name",
            email="private-email",
            token="private-secret",
        ),
        xml_confia=XMLConfiaSourceConfig(enabled=True, root=str(tmp_path)),
    )
    report = preflight(
        date(2026, 9, 30),
        config,
        environment={
            "AIP_EXECUTION_MODE": "CONFIGURED",
            "AIP_DEMO_MODE_ENABLED": "false",
        },
    )
    sources = report["sources"]
    assert sources["investment_master_root"]["status"] == "PRESENT"
    assert sources["icl_root"]["status"] == "PRESENT"
    assert sources["bccr_api"]["status"] == "CONFIGURED_NETWORK_NOT_TESTED"
    assert sources["xml_confia"]["cutoff_sources"]["CAPTACIONES"] == ("NOT_AVAILABLE_FOR_CUTOFF")
    assert sources["runtime"]["status"] == "CONFIGURED"
    serialized = str(report)
    assert "private-secret" not in serialized
    assert "private-name" not in serialized
    assert str(tmp_path) not in serialized
    assert report["status"] == "LOCAL_SOURCE_PREFLIGHT_ONLY"


def test_preflight_disables_config_without_files() -> None:
    report = preflight(
        date(2026, 9, 30),
        ConfiguredSourceConfig(),
        environment={"AIP_EXECUTION_MODE": "DEMO"},
    )
    sources = report["sources"]
    assert sources["bccr_api"]["status"] == "DISABLED"
    assert sources["xml_confia"]["cutoff_sources"]["CREDIT"] == "UNCONFIGURED"
    assert sources["runtime"]["status"] == "MODE_NOT_VERIFIED"
