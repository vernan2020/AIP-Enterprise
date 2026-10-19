"""Read-only contractual breakdown for independently certified four-source bands.

Preserves principal/interest and currency/side independently; no exchange-rate
conversion, valuation, NII, EVE or regulatory GAP certification is performed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from aip.domain.irrbb.models import BankingBookSide
from aip.domain.irrbb.services.time_bucket_service import IRRBBTimeBucketService
from aip.product.configured.irrbb.four_source_19band_consolidation import (
    ConsolidatedSourceEvidence,
)
from aip.shared.money import Currency


@dataclass(frozen=True, slots=True)
class Contractual19BandBreakdownRow:
    currency: Currency
    ordinal: int
    label: str
    principal_assets: Decimal
    interest_assets: Decimal
    principal_liabilities: Decimal
    interest_liabilities: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    period_net: Decimal
    cumulative_net: Decimal
    flow_count: int


@dataclass(frozen=True, slots=True)
class Contractual19BandBreakdown:
    rows: tuple[Contractual19BandBreakdownRow, ...]
    cutoff: str
    status: str = "CONTRACTUAL_BREAKDOWN_ONLY_NOT_REGULATORY_GAP"

    @property
    def publishable_regulatory_gap(self) -> bool:
        return False


def breakdown_four_sources(
    evidence: ConsolidatedSourceEvidence,
) -> Contractual19BandBreakdown:
    """Reconcile source flows to the independently certified 19-band aggregates.

    Unknown cashflow types are rejected, not silently interpreted as coupons.
    """
    keyed: dict[tuple[Currency, int, BankingBookSide, str], Decimal] = defaultdict(Decimal)
    seen: dict[tuple[Currency, int], int] = defaultdict(int)
    for item in evidence.evidence.rows:
        if item.ordinal not in range(1, 20):
            raise ValueError("Noncanonical time band in consolidated evidence")
    # The source aggregator has already checked duplicate events, direction and dates.
    # Use the original flows to separate principal from interest without approximations.
    original = evidence.flows
    for item in original:
        event = item.cashflow
        kind = event.flow_type.strip().upper()
        if kind not in {"PRINCIPAL", "INTEREST"}:
            raise ValueError("Unsupported contractual flow type for principal-interest split")
        assigned = IRRBBTimeBucketService.assign(
            valuation_date=evidence.cutoff_date,
            risk_date=event.risk_date,
        )
        currency = event.amount.currency
        keyed[(currency, assigned.ordinal, event.side, kind)] += event.amount.amount
        seen[(currency, assigned.ordinal)] += 1
    cumulative: dict[Currency, Decimal] = defaultdict(Decimal)
    results: list[Contractual19BandBreakdownRow] = []
    for row in evidence.evidence.rows:
        currency, ordinal = row.currency, row.ordinal
        pa = keyed[(currency, ordinal, BankingBookSide.ASSET, "PRINCIPAL")]
        ia = keyed[(currency, ordinal, BankingBookSide.ASSET, "INTEREST")]
        pl = keyed[(currency, ordinal, BankingBookSide.LIABILITY, "PRINCIPAL")]
        il = keyed[(currency, ordinal, BankingBookSide.LIABILITY, "INTEREST")]
        if pa + ia != row.assets or pl + il != row.liabilities:
            raise ValueError("Principal and interest do not reconcile to 19-band amounts")
        if seen[(currency, ordinal)] != row.flow_count:
            raise ValueError("Principal and interest counts disagree with source evidence")
        cumulative[currency] += row.net
        results.append(
            Contractual19BandBreakdownRow(
                currency=currency,
                ordinal=ordinal,
                label=row.label,
                principal_assets=pa,
                interest_assets=ia,
                principal_liabilities=pl,
                interest_liabilities=il,
                total_assets=row.assets,
                total_liabilities=row.liabilities,
                period_net=row.net,
                cumulative_net=cumulative[currency],
                flow_count=row.flow_count,
            )
        )
    if len(results) != len(evidence.evidence.rows):
        raise ValueError("Incomplete source-flow breakdown")
    if sum(row.flow_count for row in results) != len(original):
        raise ValueError("Source-flow breakdown counts do not reconcile")
    return Contractual19BandBreakdown(rows=tuple(results), cutoff=evidence.cutoff_date.isoformat())
