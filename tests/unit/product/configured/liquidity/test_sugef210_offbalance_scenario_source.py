"""Only test fixtures: approved off-balance utilization, never DEMO runtime."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from decimal import Decimal

import pytest

from aip.product.configured.liquidity.sugef210_offbalance_scenario_source import (
    read_governed_offbalance_scenario,
)

CUTOFF = date(2026, 9, 30)
SCENARIO = "SYSTEMIC"
_HEADERS = (
    "commitment_reference", "account_code", "original_currency_code",
    "native_currency", "committed_limit", "already_disbursed", "restricted_amount",
    "available_undrawn", "expiration_date", "category",
    "nonduplication_reference", "source_evidence_reference",
)


def _files(tmp_path, *, exp="2027-02-01"):
    register = tmp_path / "source-commitments.csv"
    with register.open("w", encoding="utf-8", newline="") as stream:
        w = csv.DictWriter(stream, fieldnames=_HEADERS)
        w.writeheader()
        w.writerow({
            "commitment_reference": "SOURCE-LOC-1",
            "account_code": "OFFBAL-TEST-01",
            "original_currency_code": "2",
            "native_currency": "USD",
            "committed_limit": "1000.00",
            "already_disbursed": "200.00",
            "restricted_amount": "100.00",
            "available_undrawn": "700.00",
            "expiration_date": exp,
            "category": "FIRM_LINE",
            "nonduplication_reference": "BANK-TEST-OFFBAL-1",
            "source_evidence_reference": "BANK-DOCUMENT-TEST-1",
        })
    register_hash = hashlib.sha256(register.read_bytes()).hexdigest()
    approval = tmp_path / "governed-scenario.json"
    doc = {
        "schema": "SUGEF210_OFFBALANCE_SCENARIO_V1",
        "cutoff": CUTOFF.isoformat(),
        "scenario": SCENARIO,
        "source_sha256": register_hash,
        "approved_currency_codes": {"2": "USD"},
        "approved_account_codes": ["OFFBAL-TEST-01"],
        "classification_approval": "TEST-LEGAL-FIRM-COMMITMENT",
        "currency_mapping_approval": "TEST-TREASURY-CURRENCY",
        "nonduplication_approval": "TEST-BANK-RECON-ICL",
        "approved_rules": [{
            "reference": "TEST-UTILIZATION-SYSTEMIC",
            "exposure_category": "FIRM_LINE",
            "factor": "0.25",
            "projection_day": 7,
            "rationale": "TEST ONLY; separately reviewed exposure-based stress",
            "approval_reference": "TEST-ALCO-SCENARIO-202609",
            "source_reference": "TEST-RISK-POLICY-DOCUMENT",
            "version": "2026.09",
            "approved_on": "2026-09-01",
            "valid_from": "2026-09-01",
            "valid_to": "2026-12-31",
            "explicitly_approved": True,
        }],
    }
    approval.write_text(json.dumps(doc), encoding="utf-8")
    return register, approval, doc


def _run(register, approval, **kwargs):
    return read_governed_offbalance_scenario(
        cutoff=CUTOFF, scenario=SCENARIO, source_csv=register,
        approval_json=approval, **kwargs,
    )


def test_offbalance_limits_and_utilization_are_approved_not_cash(tmp_path):
    source, approval, _ = _files(tmp_path)
    result = _run(source, approval)
    assert result.commitments_checked == 1
    assert dict(result.verified_undrawn_by_currency)["USD"] == Decimal("700.00")
    assert result.evidence.matched_exposure_count == 1
    assert result.evidence.status == "APPROVED_SCENARIO_EVENTS_ONLY_NOT_FULL_COVERAGE"
    assert len(result.evidence.flows) == 1
    cash_event = result.evidence.flows[0]
    assert cash_event.payment_date == date(2026, 10, 7)
    assert cash_event.currency == "USD"
    assert cash_event.amount == Decimal("175.0000")
    assert cash_event.area.value == "OFF_BALANCE"
    assert cash_event.side.value == "OUTFLOW"
    assert cash_event.evidence.value == "GOVERNED_ASSUMPTION"
    assert len(result.evidence.assumptions) == 1
    assert result.status == "APPROVED_PARTIAL_OFFBALANCE_SCENARIO_NOT_CASH"


def test_register_amount_fraud_or_hash_drift_fails_closed(tmp_path):
    source, approval, document = _files(tmp_path)
    text = source.read_text(encoding="utf-8").replace("700.00", "701.00")
    source.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        _run(source, approval)
    document["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    approval.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="fails source limit reconciliation"):
        _run(source, approval)


def test_unapproved_scenario_or_invalid_utilization_rejected(tmp_path):
    source, approval, document = _files(tmp_path)
    document["approved_rules"][0]["explicitly_approved"] = False
    approval.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="explicit institutional approval"):
        _run(source, approval)
    document["approved_rules"][0]["explicitly_approved"] = True
    document["approved_rules"][0]["factor"] = "1.1"
    approval.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="100 percent"):
        _run(source, approval)
    document["approved_rules"][0]["factor"] = "0.25"
    document["scenario"] = "BASE"
    approval.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="scenario differs"):
        _run(source, approval)


def test_dated_drawdown_must_precede_original_contract_expiration(tmp_path):
    source, approval, document = _files(tmp_path, exp="2026-10-05")
    with pytest.raises(ValueError, match="after commitment expiration"):
        _run(source, approval)
    document["approved_rules"][0]["projection_day"] = -1
    approval.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="365-day horizon"):
        _run(source, approval)


def test_no_double_counting_with_opening_or_contractual_schedules(tmp_path):
    source, approval, _ = _files(tmp_path)
    with pytest.raises(ValueError, match="already appears"):
        _run(source, approval, already_in_opening=frozenset({"SOURCE-LOC-1"}))
    with pytest.raises(ValueError, match="already appears"):
        _run(
            source, approval,
            existing_contractual_source_refs=frozenset({"SOURCE-LOC-1"}),
        )


def test_source_category_must_have_a_dated_approved_rule(tmp_path):
    source, approval, document = _files(tmp_path)
    document["approved_rules"][0]["exposure_category"] = "UNKNOWN_CATEGORY"
    approval.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="Missing source category"):
        _run(source, approval)


def test_duplicate_json_approval_keys_are_blocked(tmp_path):
    source, approval, _ = _files(tmp_path)
    approval.write_text('{"schema":"SUGEF210_OFFBALANCE_SCENARIO_V1","schema":"INVALID"}')
    with pytest.raises(ValueError, match="Duplicate off-balance authorization"):
        _run(source, approval)
