"""Source-backed operator preflight regression; test fixtures are not AIP runtime data."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from aip.product.configured.liquidity import sugef210_operational_readiness as readiness

CUTOFF = date(2026, 9, 30)
INVENTORY = {
    "status": "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH",
    "master_review_status": "MASTER_EXACT_CUTOFF_READ",
    "xml_records_read": 114,
    "master_positions_read": 10,
}


def _configured(monkeypatch):
    monkeypatch.setenv("AIP_EXECUTION_MODE", "CONFIGURED")
    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "false")


def test_readiness_refuses_demo_without_even_reading_institutional_sources(monkeypatch):
    monkeypatch.setenv("AIP_EXECUTION_MODE", "DEMO")
    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "true")
    monkeypatch.setattr(
        readiness,
        "inspect_xml_investment_source",
        lambda cutoff: (_ for _ in ()).throw(AssertionError("Source should remain closed")),
    )
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    assert result["status"] == "BLOCKED_NOT_CONFIGURED"


def test_sources_ready_are_inventory_only_and_do_not_activate_cashflows(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    monkeypatch.setattr(
        readiness,
        "run_configured_sight_opening",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("No ALCO approvals")),
    )
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    assert result["status"] == "SOURCE_READY_APPROVALS_REQUIRED"
    assert result["xml_records_read"] == 114
    assert result["master_positions_read"] == 10
    assert result["projection_regulatorily_certified"] is False
    assert "approved_source_events" not in result


def test_master_missing_or_only_one_approval_blocks(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(
        readiness,
        "inspect_xml_investment_source",
        lambda _: {**INVENTORY, "master_review_status": "MASTER_NOT_CONFIGURED"},
    )
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE")
    assert result["status"] == "BLOCKED_MASTER_AT_CUTOFF"

    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    result = readiness.evaluate_readiness(cutoff=CUTOFF, scenario="BASE", approval="approved.json")
    assert result["status"] == "BLOCKED_APPROVAL_PAIR_REQUIRED"


def test_operational_status_is_partial_with_authorized_real_source_contract(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    proxy = SimpleNamespace(
        source_name="TEST-XML-LEDGER",
        currency="CRC",
        events_inside_horizon=1,
        events_after_horizon=0,
        status="SELECTED_PAYMENTS_ONLY",
    )
    projection = SimpleNamespace(
        windows=tuple(range(17)),
        rows=tuple(
            SimpleNamespace(
                currency=currency,
                opening_liquidity=100,
            )
            for currency in ("CRC", "USD")
            for _ in range(17)
        ),
        certified_comprehensive=False,
        source_flow_count=1,
        status="PARTIAL_EVIDENCE_NOT_CERTIFIED",
        excluded_out_of_horizon=0,
    )
    received = {}

    def governed(**kwargs):
        received.update(kwargs)
        return SimpleNamespace(
            assembly=SimpleNamespace(
                projection=projection,
                audited_events=(SimpleNamespace(reference="TEST-REF"),),
                source_reconciliations=(proxy,),
                missing_institutional_evidence=("UNSELECTED_CONTRACTS",),
            )
        )

    monkeypatch.setattr(readiness, "run_configured_sight_opening", governed)
    result = readiness.evaluate_readiness(
        cutoff=CUTOFF,
        scenario="BASE",
        approval="institutional-sight.json",
        bank="institutional-bank.json",
    )
    assert result["status"] == "PARTIAL_GOVERNED_PROJECTION"
    assert result["projection_rows"] == 34
    assert result["band_count"] == 17
    assert result["approved_source_events"] == 1
    assert result["opening_supported_currencies"] == ["CRC", "USD"]
    assert result["projection_regulatorily_certified"] is False
    assert "bank_or_icl_source_file" not in str(result)
    assert received["approval_manifest"] == "institutional-sight.json"
    assert received["bank_support_manifest"] == "institutional-bank.json"


def test_inconsistent_event_lineage_rejected_by_operator_preflight(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(readiness, "inspect_xml_investment_source", lambda _: INVENTORY)
    monkeypatch.setattr(
        readiness,
        "run_configured_sight_opening",
        lambda **kwargs: SimpleNamespace(
            assembly=SimpleNamespace(
                projection=SimpleNamespace(
                    windows=tuple(range(17)),
                    rows=tuple(range(34)),
                    certified_comprehensive=False,
                    source_flow_count=1,
                ),
                audited_events=(),
            )
        ),
    )
    try:
        readiness.evaluate_readiness(
            cutoff=CUTOFF, scenario="BASE", approval="one.json", bank="two.json"
        )
    except ValueError as exc:
        assert "partial contract" in str(exc)
    else:
        raise AssertionError("Invalid institutional source count was accepted")


def test_self_test_checks_live_qt_tabs_and_never_loads_contractual_sources(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr(
        readiness,
        "inspect_xml_investment_source",
        lambda *_args: (_ for _ in ()).throw(AssertionError("no institutional read")),
    )
    assert readiness.main(["--self-test"]) == 0
    result = readiness.verify_runtime_without_institutional_data()
    assert result["status"] == "RUNTIME_SELFTEST_OK"
    assert result["window_count"] == 17
    assert result["expected_currency_rows"] == 34
    assert result["institutional_files_read"] is False
    assert result["projection_regulatorily_certified"] is False


def test_self_test_refuses_source_arguments_and_demo_configuration(monkeypatch, capsys):
    import pytest

    _configured(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        readiness.main(["--self-test", "--cutoff", "2026-09-30"])
    assert exc.value.code == 2

    monkeypatch.setenv("AIP_DEMO_MODE_ENABLED", "true")
    assert readiness.main(["--self-test"]) == 2
    status = capsys.readouterr().out
    assert "BLOCKED_NOT_CONFIGURED" in status
