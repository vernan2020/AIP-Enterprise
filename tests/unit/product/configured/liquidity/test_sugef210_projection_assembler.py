"""Source assembly regression cases: artificial fixtures, never operational DEMO."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)
from aip.product.configured.liquidity.irrbb_schedule_liquidity_bridge import (
    LiquiditySourceBridgeResult,
)
from aip.product.configured.liquidity.sugef210_master_maturity_bridge import (
    MasterPrincipalEvidence,
)
from aip.product.configured.liquidity.sugef210_projection_assembler import (
    assemble_partial_institutional_projection,
)

CUTOFF = date(2026, 9, 30)


def _event(
    reference: str,
    day: int,
    amount: str,
    *,
    currency: str = "CRC",
    area: LiquidityBalanceArea = LiquidityBalanceArea.ASSET,
) -> LiquidityProjectionFlow:
    return LiquidityProjectionFlow(
        reference=reference,
        source="TEST_ONLY_CONTRACT_SOURCE",
        currency=currency,
        payment_date=CUTOFF + timedelta(days=day),
        amount=Decimal(amount),
        side=(
            LiquidityFlowSide.OUTFLOW
            if area in {LiquidityBalanceArea.LIABILITY, LiquidityBalanceArea.OFF_BALANCE}
            else LiquidityFlowSide.INFLOW
        ),
        area=area,
        evidence=LiquidityEvidence.CONTRACTUAL,
    )


def _master(*events: LiquidityProjectionFlow) -> MasterPrincipalEvidence:
    total = sum((event.amount for event in events), Decimal(0))
    return MasterPrincipalEvidence(
        cutoff=CUTOFF,
        master_sha256="a" * 64,
        positions_read=len(events),
        flows=tuple(events),
        excluded=(),
        principal_by_currency=(("CRC", total),),
    )


def test_master_inventory_not_automatically_counted_as_cash_event():
    result = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        master=_master(_event("MASTER:AA:ROW:PRINCIPAL", 31, "120")),
    )
    assert result.projection.source_flow_count == 0
    assert result.projection.rows[12].net_flow == 0
    assert result.projection.rows[12].projected_liquidity is None
    assert "MASTER_MATURITIES_NOT_APPROVED_AS_LIQUIDITY_EVENTS" in (
        result.missing_institutional_evidence
    )
    assert not result.projection.certified_comprehensive


def test_reconciled_source_events_are_windowed_by_native_currency():
    events = (
        _event("CREDIT-01", 31, "120"),
        _event("CAPTACION-01", 31, "50", area=LiquidityBalanceArea.LIABILITY),
        _event("BORROWING-02", 366, "15", currency="USD", area=LiquidityBalanceArea.LIABILITY),
    )
    schedule = LiquiditySourceBridgeResult(
        cashflows=events,
        covered_balance_areas=frozenset(
            {LiquidityBalanceArea.ASSET, LiquidityBalanceArea.LIABILITY}
        ),
        source_status="CERTIFIED_CONTRACTUAL_DATES_ONLY_OFFBALANCE_NOT_INCLUDED",
    )
    result = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        contractual=schedule,
        opening_by_currency={"CRC": Decimal("10"), "USD": Decimal("7")},
        opening_certifications={"CRC": "BANK-RECON", "USD": "BANK-RECON-USD"},
        opening_nonduplication_reference="RECON-ICL-TEST",
    )
    assert result.projection.rows[12].net_flow == Decimal("70")
    assert result.projection.rows[12].projected_liquidity == Decimal("80")
    assert result.projection.rows[17 + 12].projected_liquidity == Decimal("7")
    assert result.projection.excluded_out_of_horizon == 1
    assert result.source_reconciliations[0].events_inside_horizon == 2
    assert result.source_reconciliations[1].events_after_horizon == 1
    assert "OFF_BALANCE_COMMITMENT_COVERAGE_NOT_CERTIFIED" in (
        result.missing_institutional_evidence
    )
    assert result.status == "PARTIAL_INSTITUTIONAL_LIQUIDITY_NOT_CERTIFIED"


def test_opening_requires_certification_and_source_reference_deduplication():
    event = _event("A1", 1, "12")
    schedule = LiquiditySourceBridgeResult(
        cashflows=(event,),
        covered_balance_areas=frozenset({LiquidityBalanceArea.ASSET}),
        source_status="CERTIFIED_CONTRACTUAL_DATES_ONLY_OFFBALANCE_NOT_INCLUDED",
    )
    with pytest.raises(ValueError, match="nonduplication"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            contractual=schedule,
            opening_by_currency={"CRC": Decimal("100")},
        )
    with pytest.raises(ValueError, match="already present"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            contractual=schedule,
            already_in_opening=frozenset({"A1"}),
        )


def test_rejects_duplicated_master_and_schedule_investments():
    event = _event("INVESTMENT:ABC", 31, "90")
    schedule = LiquiditySourceBridgeResult(
        cashflows=(event,),
        covered_balance_areas=frozenset({LiquidityBalanceArea.ASSET}),
        source_status="CERTIFIED_CONTRACTUAL_DATES_ONLY_OFFBALANCE_NOT_INCLUDED",
    )
    with pytest.raises(ValueError, match="overlap"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            master=_master(_event("MASTER-ABC", 31, "90")),
            master_maturity_recognition_reference="ALCO-TEST-SETTLEMENT",
            contractual=schedule,
        )


def test_offbalance_requires_external_certification_and_exact_contracts():
    event = _event("GUARANTEE-01", 14, "40", area=LiquidityBalanceArea.OFF_BALANCE)
    with pytest.raises(ValueError, match="independent certification"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF, scenario="BASE", off_balance_flows=(event,)
        )
    result = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        off_balance_flows=(event,),
        off_balance_certification_reference="LEGAL-TEST-001",
    )
    assert result.projection.rows[8].off_balance_outflows == Decimal("40")
    assert result.projection.status == "PARTIAL_EVIDENCE_NOT_CERTIFIED"


def test_master_principal_must_reconcile_before_any_cash_recognition():
    original = _master(_event("MASTER-TEST-01", 31, "120"))
    inconsistent = replace(original, principal_by_currency=(("CRC", Decimal("119")),))
    with pytest.raises(ValueError, match="does not reconcile"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            master=inconsistent,
        )
