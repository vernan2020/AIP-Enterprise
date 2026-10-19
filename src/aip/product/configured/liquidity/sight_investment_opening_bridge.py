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
from typing import Iterable


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
    existing_source_references: frozenset[str] = frozenset(),
) -> SightOpeningLiquidityResult:
    """Explicit proof required; no totals inferred from account-code inventory."""
    opening = dict(existing_opening)
    for currency, amount in opening.items():
        if currency not in {"CRC", "USD"} or not amount.is_finite() or amount < 0:
            raise ValueError("Existing liquidity base has invalid currency or balance")
    added = {"CRC": Decimal(0), "USD": Decimal(0)}
    records = tuple(source_accounts)
    seen = set(existing_source_references)
    for entry in records:
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
