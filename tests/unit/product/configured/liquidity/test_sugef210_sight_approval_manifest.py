"""Approved sight opening tests use only fixture records, no institution data."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.product.configured.liquidity.investment_current_account_xml_audit import (
    InvestmentXMLCurrentAccountAudit,
    InvestmentXMLRecordEvidence,
)
from aip.product.configured.liquidity.sugef210_sight_approval_manifest import (
    read_approved_sight_manifest,
)

CUTOFF = date(2026, 9, 30)


def _xml_audit() -> InvestmentXMLCurrentAccountAudit:
    record = InvestmentXMLRecordEvidence(
        source_reference="3004045138:2026-09-01:INVESTMENT:ROW-00000001",
        raw_record_id="001",
        record_ordinal=1,
        action="1",
        account_code="12345",
        currency_source_code="2",
        raw_principal="200.00",
        principal=Decimal("200.00"),
        instrument_id="001",
        instrument_classification_original="5",
        maturity_original="",
        isin="",
        series="",
        classification="APPROVED_CURRENT_ACCOUNT_CANDIDATE",
        master_reconciliation="UNMATCHED_ID_NOT_PROOF_OF_NEW_BALANCE",
    )
    return InvestmentXMLCurrentAccountAudit(
        cutoff=CUTOFF,
        xml_month=date(2026, 9, 1),
        xml_sha256="b" * 64,
        xml_filename="Crediticio_InversionesActivas.xml",
        entity_id="3004045138",
        records_read=1,
        groups=(),
        invalid_source_principal=0,
        missing_account_codes=0,
        records=(record,),
    )


def _manifest(audit: InvestmentXMLCurrentAccountAudit) -> dict[str, object]:
    return {
        "schema": "SUGEF210_SIGHT_OPENING_V1",
        "cutoff": CUTOFF.isoformat(),
        "xml_sha256": audit.xml_sha256,
        "account_classification_approval": "TEST-ALCO-ACCOUNT-VALIDATED",
        "currency_mapping_approval_reference": "TEST-CURRENCY-CATALOG",
        "opening_reconciliation_reference": "TEST-TREASURY-ICL-RECON",
        "approved_account_codes": ["12345"],
        "approved_currency_mapping": {"2": "USD"},
        "approved_records": [
            {
                "source_record_reference": audit.records[0].source_reference,
                "accounting_account": "12345",
                "currency": "USD",
                "xml_principal": "200.00",
                "confirmed_available": "75.25",
                "withdrawal_available_date": CUTOFF.isoformat(),
                "availability_evidence": "TEST-VERIFIED-BANK",
                "nonduplication_reconciliation": "TEST-NO-ICL-DUPLICATION",
                "restriction_clearance_reference": "TEST-RESTRICTION-REVIEW",
            }
        ],
    }


def _read(tmp_path, audit, doc):
    filename = tmp_path / "approved.json"
    filename.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return read_approved_sight_manifest(
        manifest_path=filename,
        cutoff=CUTOFF,
        source_audit=audit,
        bank_reconciled_opening={"CRC": Decimal("1000"), "USD": Decimal("10")},
        opening_certifications={"CRC": "TEST-CRC", "USD": "TEST-USD"},
    )


def test_manifest_matches_original_xml_and_adds_only_releasable_balance(tmp_path):
    audit = _xml_audit()
    result = _read(tmp_path, audit, _manifest(audit))
    assert dict(result.opening_by_currency) == {"CRC": Decimal("1000"), "USD": Decimal("85.25")}
    assert result.included_source_references == (audit.records[0].source_reference,)
    assert result.xml_sha256 == "b" * 64
    assert result.opening_reconciliation_reference == "TEST-TREASURY-ICL-RECON"


def test_manifest_rejects_hash_drift_and_duplicate_keys(tmp_path):
    audit = _xml_audit()
    invalid = _manifest(audit)
    invalid["xml_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="XML hash"):
        _read(tmp_path, audit, invalid)
    name = tmp_path / "duplicated.json"
    name.write_text('{"schema":"SUGEF210_SIGHT_OPENING_V1","schema":"override"}')
    with pytest.raises(ValueError, match="Duplicated approval"):
        read_approved_sight_manifest(
            manifest_path=name,
            cutoff=CUTOFF,
            source_audit=audit,
            bank_reconciled_opening={},
            opening_certifications={"CRC": "BANK"},
        )


def test_manifest_does_not_map_currency_or_balances_by_guess(tmp_path):
    audit = _xml_audit()
    invalid = _manifest(audit)
    invalid["approved_currency_mapping"] = {"2": "CRC"}
    with pytest.raises(ValueError, match="native-currency"):
        _read(tmp_path, audit, invalid)
    invalid = _manifest(audit)
    invalid["approved_records"][0]["confirmed_available"] = "205"
    with pytest.raises(ValueError, match="exceed"):
        _read(tmp_path, audit, invalid)
    invalid = _manifest(audit)
    invalid["approved_records"][0]["withdrawal_available_date"] = "2026-10-01"
    with pytest.raises(ValueError, match="withdrawal"):
        _read(tmp_path, audit, invalid)


def test_manifest_blocks_unapproved_accounts_and_possible_master_overlap(tmp_path):
    audit = _xml_audit()
    invalid = _manifest(audit)
    invalid["approved_account_codes"] = ["54321"]
    with pytest.raises(ValueError, match="not included"):
        _read(tmp_path, audit, invalid)
    unresolved = replace(
        audit,
        records=(replace(audit.records[0], master_reconciliation="POSSIBLE_MASTER_OVERLAP_ISIN"),),
    )
    with pytest.raises(ValueError, match="overlap"):
        _read(tmp_path, unresolved, _manifest(unresolved))
    unapproved = replace(
        audit,
        records=(replace(audit.records[0], classification="NOT_APPROVED_FOR_CURRENT_ACCOUNT"),),
    )
    with pytest.raises(ValueError, match="not approved"):
        _read(tmp_path, unapproved, _manifest(unapproved))
