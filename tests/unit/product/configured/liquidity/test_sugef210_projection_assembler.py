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
from aip.product.configured.liquidity.sight_investment_opening_bridge import (
    SightOpeningLiquidityResult,
)
from aip.product.configured.liquidity.sugef210_dated_xml_contracts import (
    ApprovedXMLContractualSchedule,
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


def test_verified_sight_investment_reconciles_only_opening_not_future_cashflow():
    sight = SightOpeningLiquidityResult(
        cutoff=CUTOFF,
        opening_by_currency=(("CRC", Decimal("100")), ("USD", Decimal("30"))),
        included_xml_accounts=1,
        added_by_currency=(("CRC", Decimal("0")), ("USD", Decimal("20"))),
        included_source_references=("XML:INV-0001",),
        xml_sha256="e" * 64,
        opening_reconciliation_reference="BANK-ICL-NONDOUBLECOUNT",
    )
    result = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        verified_sight_opening=sight,
        opening_by_currency={"CRC": Decimal("100"), "USD": Decimal("30")},
        opening_certifications={"CRC": "BANK-CRC", "USD": "BANK-USD"},
        opening_nonduplication_reference="BANK-ICL-NONDOUBLECOUNT",
    )
    assert result.projection.source_flow_count == 0
    assert result.projection.rows[17].opening_liquidity == Decimal("30")
    assert result.projection.rows[17].projected_liquidity == Decimal("30")
    assert not result.projection.certified_comprehensive
    with pytest.raises(ValueError, match="reconcile exactly"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            verified_sight_opening=sight,
            opening_by_currency={"CRC": Decimal("100"), "USD": Decimal("10")},
            opening_certifications={"CRC": "BANK-CRC", "USD": "BANK-USD"},
            opening_nonduplication_reference="BANK-ICL-NONDOUBLECOUNT",
        )
    with pytest.raises(ValueError, match="already exists"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            verified_sight_opening=sight,
            opening_by_currency={"CRC": Decimal("100"), "USD": Decimal("30")},
            opening_certifications={"CRC": "BANK-CRC", "USD": "BANK-USD"},
            opening_nonduplication_reference="BANK-ICL-NONDOUBLECOUNT",
            already_in_opening=frozenset({"XML:INV-0001"}),
        )


def test_sight_opening_requires_matching_icl_reconciliation_and_available_cash():
    sight = SightOpeningLiquidityResult(
        cutoff=CUTOFF,
        opening_by_currency=(("CRC", Decimal("100")), ("USD", Decimal("30"))),
        included_xml_accounts=1,
        added_by_currency=(("CRC", Decimal("0")), ("USD", Decimal("20"))),
        included_source_references=("XML:INV-0001",),
        xml_sha256="e" * 64,
        opening_reconciliation_reference="BANK-ICL-202609",
    )
    with pytest.raises(ValueError, match="references differ"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            verified_sight_opening=sight,
            opening_by_currency={"CRC": Decimal("100"), "USD": Decimal("30")},
            opening_certifications={"CRC": "BANK-CRC", "USD": "BANK-USD"},
            opening_nonduplication_reference="OTHER-RECONCILIATION",
        )
    with pytest.raises(ValueError, match="exceed bank-reconciled"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            verified_sight_opening=replace(sight, added_by_currency=(("USD", Decimal("60")),)),
            opening_by_currency={"CRC": Decimal("100"), "USD": Decimal("30")},
            opening_certifications={"CRC": "BANK-CRC", "USD": "BANK-USD"},
            opening_nonduplication_reference="BANK-ICL-202609",
        )


def test_individually_approved_xml_credit_and_term_deposit_appear_in_native_31_60_band():
    events = (
        _event("XML_CONTRACT:CREDIT:HASH:1:PAY-A", 31, "100"),
        _event(
            "XML_CONTRACT:CAPTACIONES:HASH:1:PAY-B",
            31,
            "30",
            currency="USD",
            area=LiquidityBalanceArea.LIABILITY,
        ),
    )
    approved = ApprovedXMLContractualSchedule(
        cutoff=CUTOFF,
        events=events,
        source_hashes=(("CREDIT", "a" * 64), ("CAPTACIONES", "b" * 64)),
        ledger_sha256="c" * 64,
        included_source_records=(("CREDIT", 1), ("CAPTACIONES", 1)),
    )
    result = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        approved_xml_schedule=approved,
        opening_by_currency={"CRC": Decimal("1000"), "USD": Decimal("70")},
        opening_certifications={"CRC": "TEST-CRC", "USD": "TEST-USD"},
        opening_nonduplication_reference="TEST-ICL-OPENING",
    )
    assert result.projection.rows[12].net_flow == Decimal("100")
    assert result.projection.rows[12].projected_liquidity == Decimal("1100")
    assert result.projection.rows[17 + 12].net_flow == Decimal("-30")
    assert result.projection.rows[17 + 12].projected_liquidity == Decimal("40")
    assert result.projection.source_flow_count == 2
    assert "UNSELECTED_CREDIT_DEPOSIT_AND_BORROWING_SOURCE_RECORDS" in (
        result.missing_institutional_evidence
    )
    assert not result.projection.certified_comprehensive


def test_certified_rtilb_and_selected_confia_contracts_cannot_duplicate_same_cash():
    observed = _event("CREDIT-REAL-APPROVED", 31, "120")
    selected = ApprovedXMLContractualSchedule(
        cutoff=CUTOFF,
        events=(observed,),
        source_hashes=(("CREDIT", "a" * 64),),
        ledger_sha256="b" * 64,
        included_source_records=(("CREDIT", 1),),
    )
    four_source = LiquiditySourceBridgeResult(
        cashflows=(observed,),
        covered_balance_areas=frozenset({LiquidityBalanceArea.ASSET}),
        source_status="CERTIFIED_CONTRACTUAL_DATES_ONLY_OFFBALANCE_NOT_INCLUDED",
    )
    with pytest.raises(ValueError, match="overlap"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            contractual=four_source,
            approved_xml_schedule=selected,
        )


def test_event_audit_reconciles_signed_cash_by_currency_band_and_after_horizon():
    events = (
        _event("TEST-CREDIT-CRC", 31, "120.50"),
        _event("TEST-DEPOSIT-CRC", 31, "32.75", area=LiquidityBalanceArea.LIABILITY),
        _event("TEST-AFTER-YEAR", 366, "33.25", currency="USD"),
    )
    schedule = LiquiditySourceBridgeResult(
        cashflows=events,
        covered_balance_areas=frozenset(
            {
                LiquidityBalanceArea.ASSET,
                LiquidityBalanceArea.LIABILITY,
            }
        ),
        source_status="CERTIFIED_CONTRACTUAL_DATES_ONLY_OFFBALANCE_NOT_INCLUDED",
    )
    assembled = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        contractual=schedule,
        opening_by_currency={"CRC": Decimal("50"), "USD": Decimal("10")},
        opening_certifications={"CRC": "TEST-BANK-CRC", "USD": "TEST-BANK-USD"},
        opening_nonduplication_reference="TEST-OPENING",
    )
    ledger = assembled.audited_events
    assert len(ledger) == assembled.projection.source_flow_count == 3
    assert tuple(event.reference for event in ledger) == (
        "TEST-CREDIT-CRC",
        "TEST-DEPOSIT-CRC",
        "TEST-AFTER-YEAR",
    )
    assert ledger[0].source_group == "CERTIFIED_DATED_SOURCE_SCHEDULE"
    assert ledger[0].band_key == "M01"
    assert ledger[0].horizon_status == "IN_365D"
    assert ledger[0].native_amount == Decimal("120.50")
    assert ledger[1].side == LiquidityFlowSide.OUTFLOW
    assert ledger[1].native_amount == Decimal("32.75")
    assert ledger[2].band_key == "OUTSIDE_365D"
    assert ledger[2].horizon_status == "AFTER_365D"
    assert ledger[2].native_amount == Decimal("33.25")
    assert assembled.projection.rows[12].net_flow == Decimal("87.75")
    assert assembled.projection.excluded_out_of_horizon == 1
    assert not assembled.projection.certified_comprehensive


def test_large_native_event_ledger_reconciles_all_34_bands_and_preserves_decimals():
    """Scale case: no rounding, cross-currency netting or omitted source events."""
    events = tuple(
        _event(
            f"LEDGER-ORIGINAL-{n:05d}",
            1 + n % 365,
            "0.01",
            currency="CRC" if n % 2 == 0 else "USD",
            area=(LiquidityBalanceArea.ASSET if n % 3 else LiquidityBalanceArea.LIABILITY),
        )
        for n in range(2040)
    ) + (_event("LEDGER-AFTER-365", 366, "2.99", currency="USD"),)
    scheduled = LiquiditySourceBridgeResult(
        cashflows=events,
        covered_balance_areas=frozenset(
            {LiquidityBalanceArea.ASSET, LiquidityBalanceArea.LIABILITY}
        ),
        source_status="CERTIFIED_CONTRACTUAL_DATES_ONLY_OFFBALANCE_NOT_INCLUDED",
    )
    result = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        contractual=scheduled,
        opening_by_currency={"CRC": Decimal("1.00"), "USD": Decimal("2.00")},
        opening_certifications={"CRC": "TEST-ICL-CRC", "USD": "TEST-ICL-USD"},
        opening_nonduplication_reference="TEST-OPENING-UNIQUE",
    )
    assert len(result.audited_events) == 2041
    assert result.projection.source_flow_count == 2041
    assert result.projection.excluded_out_of_horizon == 1
    for row in result.projection.rows:
        candidates = tuple(
            event
            for event in events
            if event.currency == row.currency
            and row.window.start <= event.payment_date <= row.window.end
        )
        assert row.event_count == len(candidates)
        assert row.asset_inflows == sum(
            (event.amount for event in candidates if event.area == LiquidityBalanceArea.ASSET),
            Decimal(0),
        )
        assert row.liability_outflows == sum(
            (event.amount for event in candidates if event.area == LiquidityBalanceArea.LIABILITY),
            Decimal(0),
        )
    assert result.audited_events[-1].band_key == "OUTSIDE_365D"
    assert not result.projection.certified_comprehensive
