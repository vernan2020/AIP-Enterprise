from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    IRRBBCashFlow,
)
from aip.product.configured.irrbb.contractual_cashflow_19band import (
    Contractual19BandEvidenceAggregator,
    EvidencedFlow,
)
from aip.shared.money import Currency, Money

CUTOFF = date(2026, 9, 30)


def _flow(
    segment: str,
    *,
    position: str,
    day: date,
    risk: date | None = None,
    amount: str = "100.15",
    currency: Currency = Currency.CRC,
    status: CashFlowAmountStatus = CashFlowAmountStatus.CONTRACTUAL,
) -> EvidencedFlow:
    asset = segment in {"CREDIT", "INVESTMENT"}
    return EvidencedFlow(
        segment=segment,
        cashflow=IRRBBCashFlow(
            position_id=position,
            side=BankingBookSide.ASSET if asset else BankingBookSide.LIABILITY,
            direction=CashFlowDirection.RECEIVABLE if asset else CashFlowDirection.PAYABLE,
            amount=Money(Decimal(amount), currency),
            cashflow_date=day,
            risk_date=risk or day,
            flow_type="PRINCIPAL",
            source_reference=f"{segment}|{position}",
            amount_status=status,
        ),
        validation_reference="VALIDATED_SOURCE_SCHEDULE",
    )


def test_contractual_flows_reconcile_all_nineteen_bands_without_mixing_currencies():
    aggregate = Contractual19BandEvidenceAggregator().aggregate(
        cutoff_date=CUTOFF,
        flows=(
            _flow("CREDIT", position="loan", day=date(2026, 10, 1)),
            _flow("CAPTACIONES", position="deposit", day=date(2026, 10, 1), amount="60.05"),
            _flow(
                "INVESTMENT",
                position="bond",
                day=date(2050, 12, 31),
                amount="75.00",
                currency=Currency.USD,
            ),
            _flow(
                "BORROWING",
                position="bankloan",
                day=date(2026, 10, 30),
                amount="10.00",
                currency=Currency.USD,
            ),
        ),
    )
    assert aggregate.total_flows == 4
    assert aggregate.included_segments == (
        "BORROWING",
        "CAPTACIONES",
        "CREDIT",
        "INVESTMENT",
    )
    assert len(aggregate.rows) == 38
    assert aggregate.missing_segments == ()
    assert aggregate.publishable_regulatory_gap is False
    first_crc = next(
        row for row in aggregate.rows if row.currency is Currency.CRC and row.ordinal == 1
    )
    assert first_crc.assets == Decimal("100.15")
    assert first_crc.liabilities == Decimal("60.05")
    assert first_crc.net == Decimal("40.10")
    usd_long = next(
        row for row in aggregate.rows if row.currency is Currency.USD and row.ordinal == 19
    )
    assert usd_long.assets == Decimal("75")
    assert usd_long.liabilities == 0


def test_rejects_duplicate_flow_and_projected_amount():
    flow = _flow("CREDIT", position="a", day=date(2027, 1, 1))
    with pytest.raises(ValueError, match="Duplicate"):
        Contractual19BandEvidenceAggregator().aggregate(
            cutoff_date=CUTOFF,
            flows=(flow, flow),
        )
    with pytest.raises(ValueError, match="derived or behavioral"):
        Contractual19BandEvidenceAggregator().aggregate(
            cutoff_date=CUTOFF,
            flows=(
                _flow(
                    "CREDIT",
                    position="b",
                    day=date(2027, 1, 1),
                    status=CashFlowAmountStatus.SCENARIO_PROJECTED,
                ),
            ),
        )


def test_rejects_stale_date_and_incompatible_side():
    with pytest.raises(ValueError, match="Historical"):
        Contractual19BandEvidenceAggregator().aggregate(
            cutoff_date=CUTOFF,
            flows=(_flow("BORROWING", position="a", day=date(2026, 9, 1)),),
        )
    original = _flow("CREDIT", position="a", day=date(2027, 1, 1))
    with pytest.raises(ValueError, match="incompatible banking-book side"):
        EvidencedFlow(
            segment="BORROWING",
            cashflow=original.cashflow,
            validation_reference="SOURCE",
        )


def test_empty_input_never_produces_a_publishable_gap():
    result = Contractual19BandEvidenceAggregator().aggregate(cutoff_date=CUTOFF, flows=())
    assert result.rows == ()
    assert result.total_flows == 0
    assert len(result.missing_segments) == 4
    assert not result.publishable_regulatory_gap


def test_conflicting_amount_for_same_source_event_is_not_double_counted():
    first = _flow("CREDIT", position="a", day=date(2027, 1, 1), amount="100")
    changed = _flow("CREDIT", position="a", day=date(2027, 1, 1), amount="200")
    with pytest.raises(ValueError, match="Duplicate"):
        Contractual19BandEvidenceAggregator().aggregate(cutoff_date=CUTOFF, flows=(first, changed))


def test_disallows_inconsistent_asset_direction():
    original = _flow("CREDIT", position="a", day=date(2027, 1, 1))
    inconsistent = replace(
        original,
        cashflow=replace(original.cashflow, direction=CashFlowDirection.PAYABLE),
    )
    with pytest.raises(ValueError, match="direction"):
        Contractual19BandEvidenceAggregator().aggregate(cutoff_date=CUTOFF, flows=(inconsistent,))


def test_similar_events_in_distinct_currencies_remain_separate():
    crc = _flow("CREDIT", position="same", day=date(2027, 1, 1), currency=Currency.CRC)
    usd = _flow("CREDIT", position="same", day=date(2027, 1, 1), currency=Currency.USD)
    result = Contractual19BandEvidenceAggregator().aggregate(cutoff_date=CUTOFF, flows=(crc, usd))
    assert result.total_flows == 2
    assert len(result.rows) == 38
