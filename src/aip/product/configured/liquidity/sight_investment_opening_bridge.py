"""Governed path for investments in current accounts absent from the Master.

Balances sourced from Crediticio_InversionesActivas.xml may contribute to
opening liquidity only after their account, availability, restrictions and
double-counting have independent institutional approvals.
No XML balance is a future income flow and no FX rate is inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping

from aip.product.configured.liquidity.investment_current_account_xml_audit import (
    InvestmentXMLCurrentAccountAudit,
)


@dataclass(frozen=True, slots=True)
class VerifiedSightInvestmentBalance:
    source_record_reference: str
    xml_sha256: str
    cutoff: date
    accounting_account: str
    currency: str
    xml_principal: Decimal
    confirmed_available: Decimal
    withdrawal_available_date: date
    account_classification_approval: str
    operational_availability_evidence: str
    nonduplication_reconciliation: str
    restriction_clearance_reference: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.source_record_reference,
                self.xml_sha256,
                self.accounting_account,
                self.account_classification_approval,
                self.operational_availability_evidence,
                self.nonduplication_reconciliation,
                self.restriction_clearance_reference,
            )
        ):
            raise ValueError("Sight investment requires full institutional evidence")
        if self.currency not in {"CRC", "USD"}:
            raise ValueError("Original XML currency needs a certified mapping to CRC or USD")
        if (
            not self.xml_principal.is_finite()
            or not self.confirmed_available.is_finite()
            or self.xml_principal < 0
            or self.confirmed_available < 0
            or self.confirmed_available > self.xml_principal
        ):
            raise ValueError("Confirmed available funds exceed the XML source balance")


@dataclass(frozen=True, slots=True)
class SightOpeningLiquidityResult:
    cutoff: date
    opening_by_currency: tuple[tuple[str, Decimal], ...]
    included_xml_accounts: int
    added_by_currency: tuple[tuple[str, Decimal], ...]
    status: str = "OPENING_XML_SIGHT_FUNDS_VERIFIED_NO_FUTURE_CASHFLOW"


def add_verified_sight_investments_to_opening(
    *,
    cutoff: date,
    existing_opening: dict[str, Decimal],
    source_accounts: Iterable[VerifiedSightInvestmentBalance],
    source_audit: InvestmentXMLCurrentAccountAudit | None = None,
    approved_currency_mapping: Mapping[str, str] | None = None,
    currency_mapping_approval_reference: str = "",
    opening_reconciliation_reference: str = "",
    existing_source_references: frozenset[str] = frozenset(),
) -> SightOpeningLiquidityResult:
    """Explicit proof required; no totals inferred from account-code inventory."""
    opening = dict(existing_opening)
    for currency, amount in opening.items():
        if currency not in {"CRC", "USD"} or not amount.is_finite() or amount < 0:
            raise ValueError("Existing liquidity base has invalid currency or balance")
    added = {"CRC": Decimal(0), "USD": Decimal(0)}
    records = tuple(source_accounts)
    if records:
        if source_audit is None:
            raise ValueError("Real XML source audit is required for opening funds")
        if source_audit.cutoff != cutoff:
            raise ValueError("XML audit cutoff differs from opening cutoff")
        if (source_audit.xml_month.year, source_audit.xml_month.month) != (
            cutoff.year, cutoff.month
        ):
            raise ValueError("XML audit reporting month differs from opening cutoff")
        if source_audit.repeated_record_ids:
            raise ValueError("Repeated XML record identifiers require reconciliation")
        if not (
            approved_currency_mapping
            and currency_mapping_approval_reference.strip()
            and opening_reconciliation_reference.strip()
        ):
            raise ValueError(
                "Approved original-currency mapping and opening reconciliation are mandatory"
            )
    original_records = (
        {row.source_reference: row for row in source_audit.records}
        if source_audit is not None
        else {}
    )
    seen = set(existing_source_references)
    for entry in records:
        origin = original_records.get(entry.source_record_reference)
        if origin is None:
            raise ValueError("Authorized balance has no matching audited XML record")
        if (
            source_audit is None
            or entry.xml_sha256 != source_audit.xml_sha256
            or entry.accounting_account != origin.account_code
            or origin.principal is None
            or entry.xml_principal != origin.principal
        ):
            raise ValueError("Original audited XML amount/account/hash does not match")
        if (
            approved_currency_mapping is None
            or approved_currency_mapping.get(origin.currency_source_code) != entry.currency
        ):
            raise ValueError("XML currency has no approved native-currency mapping")
        if origin.classification != "APPROVED_CURRENT_ACCOUNT_CANDIDATE":
            raise ValueError("XML accounting account is not approved for sight liquidity")
        if origin.master_reconciliation not in {
            "UNMATCHED_ID_NOT_PROOF_OF_NEW_BALANCE", "NO_IDENTIFIER_UNRESOLVED"
        }:
            raise ValueError("XML record has unresolved overlap or Master not loaded")

        if entry.cutoff != cutoff:
            raise ValueError("Investment account cutoff differs from liquidity projection")
        if entry.withdrawal_available_date > cutoff:
            raise ValueError("Current account funds cannot be counted before withdrawal availability")
        if entry.source_record_reference in seen:
            raise ValueError("Investment account is duplicated in Master or opening liquidity")
        seen.add(entry.source_record_reference)
        added[entry.currency] += entry.confirmed_available
    for currency in ("CRC", "USD"):
        if currency in opening or added[currency] != 0:
            opening[currency] = opening.get(currency, Decimal(0)) + added[currency]
    return SightOpeningLiquidityResult(
        cutoff=cutoff,
        opening_by_currency=tuple(sorted(opening.items())),
        included_xml_accounts=len(records),
        added_by_currency=tuple(sorted(added.items())),
    )
