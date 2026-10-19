from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from aip.product.configured.liquidity.investment_current_account_xml_audit import (
    InvestmentXMLCurrentAccountAudit,
    InvestmentXMLRecordEvidence,
)
from aip.product.configured.liquidity.sight_investment_opening_bridge import (
    VerifiedSightInvestmentBalance,
    add_verified_sight_investments_to_opening,
)

CUTOFF = date(2026, 9, 30)


def _record() -> VerifiedSightInvestmentBalance:
    return VerifiedSightInvestmentBalance(
        source_record_reference="XML-INV:ACCOUNT-001",
        xml_sha256="a" * 64,
        cutoff=CUTOFF,
        accounting_account="APPROVED-ACCOUNT",
        currency="USD",
        xml_principal=Decimal("100.00"),
        confirmed_available=Decimal("60.00"),
        withdrawal_available_date=CUTOFF,
        account_classification_approval="ALCO-ACCOUNT-MAPPING",
        operational_availability_evidence="BANK-STATEMENT-20260930",
        nonduplication_reconciliation="RECON-MASTER-ICL-20260930",
        restriction_clearance_reference="TREASURY-RESTRICTION-CHECK-202609",
    )


def _approved(proof: VerifiedSightInvestmentBalance) -> dict:
    original = InvestmentXMLRecordEvidence(
        source_reference=proof.source_record_reference,
        raw_record_id="1",
        record_ordinal=1,
        action="1",
        account_code=proof.accounting_account,
        currency_source_code="2",
        raw_principal=str(proof.xml_principal),
        principal=proof.xml_principal,
        instrument_id="SOURCE-ID-1",
        instrument_classification_original="5",
        maturity_original="",
        isin="",
        series="",
        classification="APPROVED_CURRENT_ACCOUNT_CANDIDATE",
        master_reconciliation="UNMATCHED_ID_NOT_PROOF_OF_NEW_BALANCE",
    )
    audit = InvestmentXMLCurrentAccountAudit(
        cutoff=CUTOFF,
        xml_month=date(2026, 9, 1),
        xml_sha256=proof.xml_sha256,
        xml_filename="Crediticio_InversionesActivas.xml",
        entity_id="TEST-ENTITY",
        records_read=1,
        groups=(),
        invalid_source_principal=0,
        missing_account_codes=0,
        records=(original,),
    )
    return {
        "source_audit": audit,
        "approved_currency_mapping": {"2": "USD"},
        "currency_mapping_approval_reference": "TREASURY-APPROVED-CURRENCY-CATALOG",
        "opening_reconciliation_reference": "CONFIRMED-NOT-IN-ICL-OPENING",
    }


def test_only_verified_available_funds_are_added_once_without_fx():
    proof = _record()
    result = add_verified_sight_investments_to_opening(
        cutoff=CUTOFF,
        existing_opening={"CRC": Decimal("2000"), "USD": Decimal("10")},
        source_accounts=[proof],
        **_approved(proof),
    )
    assert dict(result.opening_by_currency) == {"CRC": Decimal("2000"), "USD": Decimal("70")}
    assert result.included_xml_accounts == 1
    assert dict(result.added_by_currency)["USD"] == Decimal("60")
    assert result.included_source_references == (proof.source_record_reference,)
    assert result.xml_sha256 == proof.xml_sha256
    assert result.opening_reconciliation_reference == "CONFIRMED-NOT-IN-ICL-OPENING"
    assert result.status == "OPENING_XML_SIGHT_FUNDS_VERIFIED_NO_FUTURE_CASHFLOW"


def test_blocks_premature_available_dates_and_unreconciled_duplicates():
    proof = _record()
    with pytest.raises(ValueError, match="withdrawal"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[replace(proof, withdrawal_available_date=CUTOFF + timedelta(days=1))],
            **_approved(proof),
        )
    with pytest.raises(ValueError, match="duplicated"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[proof],
            existing_source_references=frozenset({proof.source_record_reference}),
            **_approved(proof),
        )


def test_blocks_unapproved_unrestricted_or_unmapped_source_and_invalid_amounts():
    original = _record()
    with pytest.raises(ValueError, match="institutional evidence"):
        replace(original, account_classification_approval="")
    with pytest.raises(ValueError, match="currency"):
        replace(original, currency="2")
    with pytest.raises(ValueError, match="exceed"):
        replace(original, confirmed_available=Decimal("200"))
    with pytest.raises(ValueError, match="cutoff"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[replace(original, cutoff=CUTOFF - timedelta(days=1))],
            **_approved(original),
        )


def test_sight_opening_rejects_non_audited_unclassified_or_overlapping_xml():
    proof = _record()
    with pytest.raises(ValueError, match="source audit"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF, existing_opening={}, source_accounts=[proof]
        )
    approved = _approved(proof)
    with pytest.raises(ValueError, match="native-currency"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[proof],
            **{**approved, "approved_currency_mapping": {"2": "CRC"}},
        )
    with pytest.raises(ValueError, match="audited XML"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[replace(proof, xml_principal=Decimal("110"))],
            **approved,
        )
    audit = approved["source_audit"]
    unresolved = replace(
        audit,
        records=(replace(audit.records[0], master_reconciliation="POSSIBLE_MASTER_OVERLAP_ISIN"),),
    )
    with pytest.raises(ValueError, match="unresolved overlap"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[proof],
            **{**approved, "source_audit": unresolved},
        )
    unapproved = replace(
        audit,
        records=(replace(audit.records[0], classification="NOT_APPROVED_FOR_CURRENT_ACCOUNT"),),
    )
    with pytest.raises(ValueError, match="not approved"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[proof],
            **{**approved, "source_audit": unapproved},
        )


def test_sight_opening_blocks_missing_opening_reconciliation_and_duplicate_xml_ids():
    proof = _record()
    approved = _approved(proof)
    with pytest.raises(ValueError, match="reconciliation"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[proof],
            **{**approved, "opening_reconciliation_reference": ""},
        )
    with pytest.raises(ValueError, match="Repeated XML"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF,
            existing_opening={},
            source_accounts=[proof],
            **{
                **approved,
                "source_audit": replace(approved["source_audit"], repeated_record_ids=1),
            },
        )
