from __future__ import annotations

from datetime import date

import pytest

from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.product.demo.exceptions import DemoConfigurationError


def test_demo_configuration_defaults_to_demo_mode() -> None:
    config = DemoConfig()
    assert config.execution_mode == "DEMO"
    assert config.demo_mode_enabled is True


def test_demo_configuration_rejects_invalid_execution_mode() -> None:
    with pytest.raises(DemoConfigurationError):
        DemoConfig(execution_mode="INVALID")


def test_environment_loader_reads_safe_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIP_DEMO_EXECUTION_MODE", "CONFIGURED")
    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "true")
    monkeypatch.setenv("AIP_DATA_CUTOFF_DATE", "2026-07-29")
    config = EnvironmentLoader().load()
    assert config.execution_mode == "CONFIGURED"
    assert config.demo_mode_enabled is True
    assert config.data_cutoff_date == date(2026, 7, 29)


def test_safe_representation_does_not_expose_secrets() -> None:
    config = DemoConfig()
    representation = config.safe_representation()
    assert representation["execution_mode"] == "DEMO"
    assert "password" not in representation
