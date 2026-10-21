"""Isolated coupon fixtures. No fictitious institutional runtime source."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)
from aip.product.configured.liquidity.sugef210_master_coupon_schedule import (
    read_approved_master_coupons,
)
from aip.product.configured.liquidity.sugef210_master_maturity_bridge import (
    MasterPrincipalEvidence,
)
from aip.product.configured.liquidity.sugef210_projection_assembler import (
    assemble_partial_institutional_projection,
)

CUTOFF = date(2026, 9, 30)
MASTER_SHA = "a" * 64
HEADERS = (
    "master_principal_reference",
    "payment_reference",
    "payment_date",
    "currency",
    "amount",
    "settlement_reference",
    "nonduplication_reference",
)


def _master() -> MasterPrincipalEvidence:
    principal = LiquidityProjectionFlow(
        reference=f"MASTER:{MASTER_SHA}:5:PRINCIPAL",
        source="TEST-MASTER-ORIGINAL-ROW-5",
        currency="USD",
        payment_date=date(2026, 12, 31),
        amount=Decimal("100.00"),
        side=LiquidityFlowSide.INFLOW,
        area=LiquidityBalanceArea.ASSET,
        evidence=LiquidityEvidence.CONTRACTUAL,
    )
    return MasterPrincipalEvidence(
        cutoff=CUTOFF,
        master_sha256=MASTER_SHA,
        positions_read=1,
        flows=(principal,),
        excluded=(),
        principal_by_currency=(("USD", Decimal("100.00")),),
    )


def _source(tmp_path):
    custody = tmp_path / "custodian-source-document.csv"
    custody.write_bytes(b"UNIT-TEST-EVIDENCE-NOT-INSTITUTIONAL")
    ledger = tmp_path / "coupon-ledger.csv"
    row = {
        "master_principal_reference": _master().flows[0].reference,
        "payment_reference": "TEST-COUPON-USD-001",
        "payment_date": "2026-10-31",
        "currency": "USD",
        "amount": "5.25",
        "settlement_reference": "TEST-CUSTODY-SETTLEMENT-001",
        "nonduplication_reference": "TEST-COUPON-NONDOUBLE-001",
    }
    with ledger.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerow(row)
    approval = tmp_path / "approved-coupons.json"
    document = {
        "schema": "SUGEF210_MASTER_COUPONS_V1",
        "cutoff": CUTOFF.isoformat(),
        "master_sha256": MASTER_SHA,
        "ledger_sha256": hashlib.sha256(ledger.read_bytes()).hexdigest(),
        "custodian_document_sha256": hashlib.sha256(custody.read_bytes()).hexdigest(),
        "custodian_approval_reference": "TEST-CUSTODY-CONFIRMATION",
        "treasury_settlement_approval": "TEST-TREASURY-INSTRUMENT-APPROVAL",
        "nonduplication_approval": "TEST-NOT-PREVIOUSLY-IN-OPENING",
        "approved_payment_records": [{**row, "explicitly_approved": True}],
    }
    approval.write_text(json.dumps(document), encoding="utf-8")
    return ledger, approval, custody, row, document


def _read(ledger, approval, custody, **kwargs):
    return read_approved_master_coupons(
        source=_master(),
        cutoff=CUTOFF,
        master_sha256=MASTER_SHA,
        ledger_file=ledger,
        approval_file=approval,
        custodian_document_file=custody,
        **kwargs,
    )


def _rewrite_ledger(path, row):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerow(row)


def test_individually_approved_coupon_is_future_native_usd_inflow_not_principal(tmp_path):
    ledger, approval, custody, _row, _doc = _source(tmp_path)
    intake = _read(ledger, approval, custody)
    assert len(intake.events) == 1
    flow = intake.events[0]
    assert flow.payment_date == date(2026, 10, 31)
    assert flow.amount == Decimal("5.25")
    assert flow.currency == "USD"
    assert flow.area == LiquidityBalanceArea.ASSET
    assert flow.side == LiquidityFlowSide.INFLOW
    assert flow.evidence == LiquidityEvidence.CONTRACTUAL
    assert flow.reference.startswith("MASTER_COUPON:")
    assert intake.nonduplication_references == frozenset({"TEST-COUPON-NONDOUBLE-001"})
    assert intake.status == "SELECTED_MASTER_COUPONS_ONLY_NOT_COMPLETE_INVESTMENT_COVERAGE"

    assembly = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        approved_investment_coupons=intake,
        opening_by_currency={"CRC": Decimal("50"), "USD": Decimal("10")},
        opening_certifications={"CRC": "TEST-CRC-ICL", "USD": "TEST-USD-ICL"},
        opening_nonduplication_reference="TEST-INDEPENDENT-ICL",
    )
    projected = next(
        item
        for item in assembly.projection.rows
        if item.currency == "USD" and item.window.key == "M01"
    )
    assert projected.asset_inflows == Decimal("5.25")
    assert projected.projected_liquidity == Decimal("15.25")
    assert assembly.projection.source_flow_count == 1
    assert not assembly.projection.certified_comprehensive
    assert any(
        source.source_name == "APPROVED_MASTER_COUPONS"
        for source in assembly.source_reconciliations
    )


def test_ledger_and_custodian_changes_cannot_reuse_approval(tmp_path):
    ledger, approval, custody, row, doc = _source(tmp_path)
    custody.write_bytes(b"CHANGED-UNAPPROVED-CUSTODY-EVIDENCE")
    with pytest.raises(ValueError, match="Custodian supporting document SHA-256"):
        _read(ledger, approval, custody)
    custody.write_bytes(b"UNIT-TEST-EVIDENCE-NOT-INSTITUTIONAL")
    _rewrite_ledger(ledger, {**row, "amount": "7.25"})
    with pytest.raises(ValueError, match="Coupon ledger SHA-256"):
        _read(ledger, approval, custody)
    doc["ledger_sha256"] = hashlib.sha256(ledger.read_bytes()).hexdigest()
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="ledger and individual authorized payment differ"):
        _read(ledger, approval, custody)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("payment_date", "2027-01-01", "outside future Master instrument life"),
        ("payment_date", "2026-09-30", "outside future Master instrument life"),
        ("currency", "CRC", "native currency differs"),
        ("master_principal_reference", "UNRECOGNIZED", "not validated"),
        ("amount", "NaN", "strictly positive"),
        ("nonduplication_reference", "TEST-PRINCIPAL-NONDOUBLE", "reuses"),
    ),
)
def test_invalid_source_date_currency_amount_and_double_count_fail_closed(
    tmp_path, field, value, error
):
    ledger, approval, custody, row, doc = _source(tmp_path)
    _rewrite_ledger(ledger, {**row, field: value})
    doc["ledger_sha256"] = hashlib.sha256(ledger.read_bytes()).hexdigest()
    approval.write_text(json.dumps(doc), encoding="utf-8")
    protected = (
        frozenset({"TEST-PRINCIPAL-NONDOUBLE"})
        if field == "nonduplication_reference"
        else frozenset()
    )
    with pytest.raises(ValueError, match=error):
        _read(
            ledger,
            approval,
            custody,
            prohibited_nonduplication_refs=protected,
        )


def test_individual_unapproved_repeated_or_missing_payment_blocked(tmp_path):
    ledger, approval, custody, _row, doc = _source(tmp_path)
    doc["approved_payment_records"][0]["explicitly_approved"] = False
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="Unapproved investment coupon"):
        _read(ledger, approval, custody)
    doc["approved_payment_records"][0]["explicitly_approved"] = True
    doc["approved_payment_records"].append(dict(doc["approved_payment_records"][0]))
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="Repeated individual coupon approval"):
        _read(ledger, approval, custody)
    doc["approved_payment_records"] = [replace_record for replace_record in []]
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="Individual dated coupon approvals"):
        _read(ledger, approval, custody)


def test_coupon_source_master_cutoff_and_document_independence(tmp_path):
    ledger, approval, custody, _row, _doc = _source(tmp_path)
    with pytest.raises(ValueError, match="independent"):
        _read(ledger, approval, ledger)
    with pytest.raises(ValueError, match="Master cutoff"):
        read_approved_master_coupons(
            source=replace(_master(), cutoff=date(2026, 8, 31)),
            cutoff=CUTOFF,
            master_sha256=MASTER_SHA,
            ledger_file=ledger,
            approval_file=approval,
            custodian_document_file=custody,
        )

def test_custody_ledger_cannot_drop_approved_coupon_or_repeat_payment(tmp_path):
    ledger, approval, custody, row, doc = _source(tmp_path)
    doc["approved_payment_records"].append(
        {
            **row,
            "payment_reference": "TEST-COUPON-SECOND-APPROVED-BUT-MISSING",
            "explicitly_approved": True,
        }
    )
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="do not exactly match custody ledger"):
        _read(ledger, approval, custody)

    doc["approved_payment_records"] = [{**row, "explicitly_approved": True}]
    with ledger.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writerow(row)
    doc["ledger_sha256"] = hashlib.sha256(ledger.read_bytes()).hexdigest()
    approval.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate investment coupon payment reference"):
        _read(ledger, approval, custody)

