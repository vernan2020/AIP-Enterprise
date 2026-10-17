from __future__ import annotations

from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def test_environment_loader_honors_existing_xml_confia_configuration(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIP_XML_CONFIA_ROOT", str(tmp_path))
    monkeypatch.setenv("AIP_XML_CONFIA_ENABLED", "true")

    loader = EnvironmentLoader()
    runtime = loader.load_source_config()
    embedded = loader.load().source_config

    assert runtime.xml_confia.enabled
    assert runtime.xml_confia.root == str(tmp_path)
    assert embedded["xml_confia"]["enabled"] is True
    assert embedded["xml_confia"]["root"] == str(tmp_path)


def test_xml_confia_source_remains_disabled_when_not_configured(monkeypatch) -> None:
    for key in ("AIP_XML_CONFIA_ROOT", "AIP_XMLCONFIA_ROOT", "AIP_XML_CONFIA_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    config = EnvironmentLoader().load_source_config()
    assert not config.xml_confia.enabled
    assert config.xml_confia.root is None


def test_regulatory_readiness_cli_requires_existing_config(monkeypatch, capsys) -> None:
    from aip.product.configured.irrbb.regulatory_xml_readiness_cli import main

    for key in ("AIP_XML_CONFIA_ROOT", "AIP_XMLCONFIA_ROOT", "AIP_XML_CONFIA_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    assert main(["--cutoff", "2026-09-30"]) == 2
    assert '"UNCONFIGURED"' in capsys.readouterr().out


def test_configured_xml_only_source_activates_non_demo_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIP_XML_CONFIA_ROOT", str(tmp_path))
    monkeypatch.setenv("AIP_XML_CONFIA_ENABLED", "true")
    monkeypatch.delenv("AIP_EXECUTION_MODE", raising=False)
    monkeypatch.delenv("AIP_DEMO_EXECUTION_MODE", raising=False)
    monkeypatch.delenv("AIP_DEMO_MODE_ENABLED", raising=False)

    runtime = EnvironmentLoader().load()

    assert runtime.execution_mode == "CONFIGURED"
    assert not runtime.demo_mode_enabled
