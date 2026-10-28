"""The individual liquidity run must reject any non-reconciling cash identity."""

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
from aip.product.configured.liquidity import sugef210_projection_assembler as assembler

CUTOFF = date(2026, 9, 30)


def _run():
    cash = LiquidityProjectionFlow(
        reference="SYNTHETIC-OFFBALANCE-1",
        source="TEST-INDEPENDENT-EVIDENCE",
        currency="CRC",
        payment_date=CUTOFF + timedelta(days=1),
        amount=Decimal("25"),
        side=LiquidityFlowSide.OUTFLOW,
        area=LiquidityBalanceArea.OFF_BALANCE,
        evidence=LiquidityEvidence.CONTRACTUAL,
    )
    return assembler.assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        off_balance_flows=(cash,),
        off_balance_certification_reference="SYNTHETIC-ONLY-NO-REGULATORY-APPROVAL",
        opening_by_currency={"CRC": Decimal("100"), "USD": Decimal("10")},
        opening_certifications={"CRC": "TEST-CASH-CRC", "USD": "TEST-CASH-USD"},
        opening_nonduplication_reference="TEST-OPENING-NONDUPLICATION",
    )


def test_valid_individual_scenario_reconciles_audited_cash_and_opening():
    assembled = _run()
    row = next(
        item for item in assembled.projection.rows
        if item.currency == "CRC" and item.window.key == "D01"
    )
    assert row.off_balance_outflows == Decimal("25")
    assert row.net_flow == Decimal("-25")
    assert row.accumulated_flow == Decimal("-25")
    assert row.projected_liquidity == Decimal("75")
    assert row.financing_need == Decimal(0)
    assert len(assembled.audited_events) == 1
    assert assembled.projection.certified_comprehensive is False


@pytest.mark.parametrize(
    ("changed_field", "changed_value", "expected_message"),
    [
        ("net_flow", Decimal("-24"), "Net cashflow differs"),
        ("accumulated_flow", Decimal("-23"), "Accumulated liquidity gap"),
        ("projected_liquidity", Decimal("76"), "Projected cash and financing need"),
        ("financing_need", Decimal("1"), "Projected cash and financing need"),
    ],
)
def test_individual_scenario_blocks_any_corrupted_projected_identity(
    monkeypatch, changed_field, changed_value, expected_message
):
    assembled = _run()
    rows = list(assembled.projection.rows)
    index = next(
        i for i, row in enumerate(rows)
        if row.currency == "CRC" and row.window.key == "D01"
    )
    rows[index] = replace(rows[index], **{changed_field: changed_value})
    corrupted = replace(assembled.projection, rows=tuple(rows))
    monkeypatch.setattr(assembler, "project_sugef210", lambda **kwargs: corrupted)
    with pytest.raises(ValueError, match=expected_message):
        _run()


def test_individual_scenario_blocks_unknown_opening_with_invented_cash(monkeypatch):
    assembled = _run()
    rows = list(assembled.projection.rows)
    index = next(
        i for i, row in enumerate(rows)
        if row.currency == "CRC" and row.window.key == "D01"
    )
    rows[index] = replace(
        rows[index], opening_liquidity=None, projected_liquidity=Decimal("75")
    )
    corrupted = replace(assembled.projection, rows=tuple(rows))
    monkeypatch.setattr(assembler, "project_sugef210", lambda **kwargs: corrupted)
    with pytest.raises(ValueError, match="Missing opening liquidity"):
        _run()
