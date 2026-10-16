from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from aip.product.configured.irrbb import xml_contractual_coverage_cli as cli


def _config(*, enabled: bool = True, root: str = "/institutional/xml"):
    return SimpleNamespace(xml_confia=SimpleNamespace(enabled=enabled, root=root))


def test_cli_uses_configured_reader_and_returns_aggregate_only(monkeypatch, capsys):
    monkeypatch.setattr(cli, "EnvironmentLoader", lambda: SimpleNamespace(
        load_source_config=lambda: _config()
    ))
    monkeypatch.setattr(cli, "XMLConfiaMonthlySourceReader", lambda root: root)

    def inspect(reader, *, cutoff_date):
        assert reader == "/institutional/xml"
        assert cutoff_date == date(2026, 9, 30)
        return (SimpleNamespace(
            key="CREDIT", filename="NEC2024_Operaciones_5103.Nuevo.xml",
            period=date(2026, 9, 1), entity_id="3004045138",
            record_count=2, status="FIELD_GAPS_FOUND",
            missing_by_field=(("FechaVencimiento", 1),)
        ),)
    monkeypatch.setattr(cli, "inspect_xml_contractual_coverage", inspect)
    assert cli.main(["--cutoff", "2026-09-30"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "COVERAGE_INSPECTED"
    assert payload["sources"][0]["missing_by_field"]["FechaVencimiento"] == 1
    assert payload["investment_source"] == "INSTITUTIONAL_PORTFOLIO_MASTER"
    assert "records" in payload["sources"][0]


def test_cli_blocks_unconfigured_source(monkeypatch, capsys):
    monkeypatch.setattr(cli, "EnvironmentLoader", lambda: SimpleNamespace(
        load_source_config=lambda: _config(enabled=False)
    ))
    assert cli.main(["--cutoff", "2026-09-30"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "UNCONFIGURED"


def test_cli_fails_closed_without_leaking_source_path(monkeypatch, capsys):
    monkeypatch.setattr(cli, "EnvironmentLoader", lambda: SimpleNamespace(
        load_source_config=lambda: _config()
    ))
    monkeypatch.setattr(cli, "XMLConfiaMonthlySourceReader", lambda root: root)
    def fail(reader, *, cutoff_date):
        raise FileNotFoundError("sensitive/institutional/path")
    monkeypatch.setattr(cli, "inspect_xml_contractual_coverage", fail)
    assert cli.main(["--cutoff", "2026-09-30"]) == 2
    output = capsys.readouterr().out
    assert "sensitive" not in output
    assert json.loads(output)["reason_type"] == "FileNotFoundError"
