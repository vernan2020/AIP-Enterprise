from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from aip.product.configured.liquidity.sight_investment_opening_bridge import (
    VerifiedSightInvestmentBalance,
    add_verified_sight_investments_to_opening,
)


CUTOFF = date(2026, 9, 30)


def _record() -> VerifiedSightInvestmentBalance:
    return VerifiedSightInvestmentBalance(
        source_record_reference="XML-INV:ACCOUNT-001",
        xml_sha256="SOURCE-SHA256-202609",
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


def test_only_verified_available_funds_are_added_once_without_fx():
    proof = _record()
    result = add_verified_sight_investments_to_opening(
        cutoff=CUTOFF,
        existing_opening={"CRC": Decimal("2000"), "USD": Decimal("10")},
        source_accounts=[proof],
    )
    assert dict(result.opening_by_currency) == {
        "CRC": Decimal("2000"), "USD": Decimal("70")
    }
    assert result.included_xml_accounts == 1
    assert dict(result.added_by_currency)["USD"] == Decimal("60")
    assert result.status == "OPENING_XML_SIGHT_FUNDS_VERIFIED_NO_FUTURE_CASHFLOW"


def test_blocks_premature_available_dates_and_unreconciled_duplicates():
    proof = _record()
    with pytest.raises(ValueError, match="withdrawal"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF, existing_opening={},
            source_accounts=[replace(proof, withdrawal_available_date=CUTOFF + timedelta(days=1))]
        )
    with pytest.raises(ValueError, match="duplicated"):
        add_verified_sight_investments_to_opening(
            cutoff=CUTOFF, existing_opening={},
            source_accounts=[proof], existing_source_references=frozenset({proof.source_record_reference})
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
        )
