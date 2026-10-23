"""Govended source-only cashflow CLI never labels partial sources regulatory."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal

from aip.product.configured.liquidity.sugef210_opening_cli import (
    main,
    summarize_session,
)
from aip.product.configured.liquidity.sugef210_opening_session import (
    ConfiguredOpeningSession,
)
from aip.product.configured.liquidity.sugef210_projection_assembler import (
    assemble_partial_institutional_projection,
)


def _session() -> ConfiguredOpeningSession:
    cutoff = date(2026, 9, 30)
    assembled = assemble_partial_institutional_projection(
        cutoff=cutoff,
        scenario="BASE",
        opening_by_currency={"CRC": Decimal("100"), "USD": Decimal("15")},
        opening_certifications={"CRC": "TEST-ICL-CRC", "USD": "TEST-ICL-USD"},
        opening_nonduplication_reference="TEST-ICL-NONDOUBLE",
    )
    return ConfiguredOpeningSession(
        cutoff=cutoff,
        scenario="BASE",
        assembly=assembled,
        sight_records_approved=1,
        sight_source_sha256="a" * 64,
        bank_support_sha256="b" * 64,
        bank_document_sha256="c" * 64,
    )


def test_json_diagnostic_preserves_partial_amounts_and_separate_currencies():
    report = summarize_session(_session())
    assert report["not_a_regulatory_cashflow_certification"] is True
    assert report["document_hash_is_not_a_bank_signature"] is True
    assert report["projection_status"] == "PARTIAL_EVIDENCE_NOT_CERTIFIED"
    assert len(report["windows"]) == 34
    assert report["windows"][0]["currency"] == "CRC"
    assert report["windows"][0]["cash_inflow_asset"] is None
    assert report["windows"][0]["opening"] == "100"
    assert report["windows"][17]["currency"] == "USD"
    assert report["windows"][17]["balance_partial"] == "15"
    assert report["source_flows_included"] == 0
    assert report["reconciliation_by_source_and_currency"] == []


def test_cli_reports_protected_error_category_not_private_filepath(monkeypatch, capsys):
    from aip.product.configured.liquidity import sugef210_opening_cli as cli

    def reject(**kwargs):
        raise ValueError("Sensitive file location C:/Private/Bank/data.xlsx")

    monkeypatch.setattr(cli, "run_configured_sight_opening", reject)
    status = main(
        [
            "--cutoff",
            "2026-09-30",
            "--scenario",
            "BASE",
            "--approval",
            "C:/Private/approval.json",
            "--bank",
            "C:/Private/bank.json",
        ]
    )
    assert status == 2
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "BLOCKED_INSTITUTIONAL_EVIDENCE"
    assert output["error_type"] == "ValueError"
    assert "Private" not in json.dumps(output)


def test_cli_success_emits_structured_17_band_native_currency_waterfall(monkeypatch, capsys):
    from aip.product.configured.liquidity import sugef210_opening_cli as cli

    monkeypatch.setattr(cli, "run_configured_sight_opening", lambda **kwargs: _session())
    status = main(
        [
            "--cutoff",
            "2026-09-30",
            "--scenario",
            "BASE",
            "--approval",
            "approved.json",
            "--bank",
            "opening.json",
        ]
    )
    assert status == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["windows"]) == 34
    assert payload["status"] == "PARTIAL_DOCUMENTED_OPENING_NOT_COMPLETE_FORECAST"


def test_cmd_exposes_approved_native_xml210_account_reconciliation_without_fx():
    session = replace(
        _session(),
        demand_deposit_accounts_reviewed=2,
        demand_deposit_runoff_events_approved=3,
        demand_deposit_source_sha256="d" * 64,
        demand_deposit_native_reconciliations=(
            ("TEST-210", "SIGHT", "1", 1, Decimal("80.00")),
            ("TEST-210", "SIGHT", "2", 1, Decimal("100.00")),
        ),
    )
    payload = summarize_session(session)
    assert payload["demand_deposit_accounts_reviewed"] == 2
    assert payload["demand_deposit_runoff_events_approved"] == 3
    assert payload["demand_deposit_xml_sha256"] == "d" * 64
    groups = payload["demand_deposit_reconciled_source_groups"]
    assert len(groups) == 2
    assert groups[0]["original_currency_code"] == "1"
    assert groups[0]["original_native_balance"] == "80.00"
    assert groups[1]["original_currency_code"] == "2"
    assert groups[1]["original_native_balance"] == "100.00"
    assert payload["not_a_regulatory_cashflow_certification"] is True
