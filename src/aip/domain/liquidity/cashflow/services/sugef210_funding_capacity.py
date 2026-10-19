"""Verified funding lines and financing headroom for the SUGEF 2-10 ladder.

Drawable capacity is NOT cash received, HQLA, collateral liquidity or a
contractual inflow. Facilities need dated approval and nonduplicated collateral.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityProjectionResult,
)


@dataclass(frozen=True, slots=True)
class ConfirmedFundingFacility:
    reference: str
    currency: str
    available_net_amount: Decimal
    evidence_cutoff: date
    drawable_from: date
    expires_on: date
    financing_approval: str
    source_reference: str
    collateral_nonduplication_reference: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.reference,
                self.financing_approval,
                self.source_reference,
                self.collateral_nonduplication_reference,
            )
        ):
            raise ValueError("Funding line requires approval and collateral evidence")
        if self.currency not in {"CRC", "USD"}:
            raise ValueError("Funding currency is not certified")
        if not self.available_net_amount.is_finite() or self.available_net_amount < 0:
            raise ValueError("Funding capacity must be nonnegative and finite")
        if self.drawable_from > self.expires_on:
            raise ValueError("Funding availability and expiry are inconsistent")


@dataclass(frozen=True, slots=True)
class FinancingHeadroomRow:
    window_key: str
    currency: str
    potential_undrawn: Decimal | None
    projected_liquidity_before_financing: Decimal | None
    uncovered_shortfall: Decimal | None
    shortfall_after_potential_draw: Decimal | None


@dataclass(frozen=True, slots=True)
class FinancingHeadroomResult:
    cutoff: date
    rows: tuple[FinancingHeadroomRow, ...]
    status: str = "CERTIFIED_POTENTIAL_DRAW_CAPACITY_NOT_CASH"


def calculate_funding_headroom(
    *,
    projection: LiquidityProjectionResult,
    facilities: Iterable[ConfirmedFundingFacility],
    certification_reference: str | None,
) -> FinancingHeadroomResult:
    """Show feasible financing independently from projected available cash."""
    items = tuple(facilities)
    if not certification_reference:
        return FinancingHeadroomResult(
            cutoff=projection.cutoff,
            rows=tuple(
                FinancingHeadroomRow(
                    window_key=row.window.key,
                    currency=row.currency,
                    potential_undrawn=None,
                    projected_liquidity_before_financing=row.projected_liquidity,
                    uncovered_shortfall=(
                        max(Decimal(0), -row.projected_liquidity)
                        if row.projected_liquidity is not None
                        else None
                    ),
                    shortfall_after_potential_draw=None,
                )
                for row in projection.rows
            ),
            status="FUNDING_CAPACITY_NOT_CERTIFIED",
        )
    references: set[str] = set()
    collateral: set[str] = set()
    for facility in items:
        if facility.evidence_cutoff != projection.cutoff:
            raise ValueError("Funding certification date differs from scenario cutoff")
        if facility.reference in references:
            raise ValueError("Duplicate funding facility reference")
        references.add(facility.reference)
        if facility.collateral_nonduplication_reference in collateral:
            raise ValueError("Funding capacities reuse the same confirmed collateral")
        collateral.add(facility.collateral_nonduplication_reference)

    rows: list[FinancingHeadroomRow] = []
    for row in projection.rows:
        # Conservative: available at the START and sustained through the whole bucket.
        available = sum(
            (
                f.available_net_amount
                for f in items
                if f.currency == row.currency
                and f.drawable_from <= row.window.start
                and f.expires_on >= row.window.end
            ),
            Decimal(0),
        )
        initial = row.projected_liquidity
        shortage = max(Decimal(0), -initial) if initial is not None else None
        rows.append(
            FinancingHeadroomRow(
                window_key=row.window.key,
                currency=row.currency,
                potential_undrawn=available,
                projected_liquidity_before_financing=initial,
                uncovered_shortfall=shortage,
                shortfall_after_potential_draw=(
                    max(Decimal(0), shortage - available)
                    if shortage is not None
                    else None
                ),
            )
        )
    return FinancingHeadroomResult(cutoff=projection.cutoff, rows=tuple(rows))
