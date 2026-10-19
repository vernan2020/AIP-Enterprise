from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from aip.domain.liquidity.cashflow.services.sugef210_funding_capacity import (
    ConfirmedFundingFacility,
    calculate_funding_headroom,
)
from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
    project_sugef210,
)

CUTOFF = date(2026, 9, 30)


def _projection():
    return project_sugef210(
        cutoff=CUTOFF,
        scenario="BASE",
        flows=[
            LiquidityProjectionFlow(
                reference="DEPOSIT-PAYMENT", source="CERTIFIED-DEPOSIT-LEDGER",
                currency="CRC", payment_date=CUTOFF + timedelta(days=1),
                amount=Decimal("80"), side=LiquidityFlowSide.OUTFLOW,
                area=LiquidityBalanceArea.LIABILITY,
                evidence=LiquidityEvidence.CONTRACTUAL,
            )
        ],
        opening_liquidity={"CRC": Decimal("50"), "USD": Decimal("0")},
        source_areas_covered=[LiquidityBalanceArea.LIABILITY],
    )


def _facility():
    return ConfirmedFundingFacility(
        reference="LINE-01", currency="CRC", available_net_amount=Decimal("40"),
        evidence_cutoff=CUTOFF, drawable_from=CUTOFF,
        expires_on=CUTOFF + timedelta(days=365),
        financing_approval="ALCO-FINANCING-LIMIT-2026-09",
        source_reference="FINANCING-CONTRACT-2026",
        collateral_nonduplication_reference="COLLATERAL-RECON-01",
    )


def test_confirmed_headroom_does_not_automatically_increase_cash():
    projection = _projection()
    report = calculate_funding_headroom(
        projection=projection,
        facilities=[_facility()],
        certification_reference="TREASURY-FINANCING-CERTIFICATION-20260930",
    )
    day1 = report.rows[1]
    assert day1.projected_liquidity_before_financing == Decimal("-30")
    assert day1.potential_undrawn == Decimal("40")
    assert day1.uncovered_shortfall == Decimal("30")
    assert day1.shortfall_after_potential_draw == Decimal("0")
    assert projection.rows[1].projected_liquidity == Decimal("-30")


def test_unverified_financing_capacity_is_missing_not_assumed_zero():
    report = calculate_funding_headroom(
        projection=_projection(),
        facilities=[_facility()],
        certification_reference=None,
    )
    assert report.status == "FUNDING_CAPACITY_NOT_CERTIFIED"
    assert report.rows[1].potential_undrawn is None
    assert report.rows[1].shortfall_after_potential_draw is None


def test_same_collateral_and_mismatched_cutoffs_are_blocked():
    projection = _projection()
    facility = _facility()
    with pytest.raises(ValueError, match="collateral"):
        calculate_funding_headroom(
            projection=projection,
            facilities=[facility, replace(facility, reference="LINE-02")],
            certification_reference="APPROVED",
        )
    with pytest.raises(ValueError, match="date differs"):
        calculate_funding_headroom(
            projection=projection,
            facilities=[replace(facility, evidence_cutoff=date(2026, 8, 31))],
            certification_reference="APPROVED",
        )
