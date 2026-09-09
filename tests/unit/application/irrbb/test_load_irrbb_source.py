from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb import (
    IRRBBPositionSourceRecord,
    IRRBBSourceLoadRequest,
    IRRBBSourceLoadStatus,
    IRRBBSourceSnapshot,
    LoadIRRBBSourceSnapshot,
)
from aip.domain.irrbb.data_quality import IRRBBValidationContext
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    PaymentStructure,
    RateType,
)
from aip.shared.money import Currency, Money

CUTOFF = date(2026, 8, 31)


def _fixed_investment(position_id: str = "INV-1") -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="BOND",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2028, 8, 31),
        source_reference=f"TEST:{position_id}",
        contractual_rate=Decimal("0.06"),
        payment_frequency_months=6,
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        payment_structure=PaymentStructure.BULLET,
    )


def _incomplete_credit() -> BankingBookPosition:
    return BankingBookPosition(
        position_id="LOAN-1",
        product_type="CREDIT",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("500"), Currency.CRC),
        rate_type=RateType.FLOATING,
        maturity_date=date(2030, 8, 31),
        source_reference="TEST:LOAN-1",
        reference_rate="TBP",
        spread=Decimal("0.02"),
        repricing_frequency_months=1,
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
    )


class _Gateway:
    def __init__(self, snapshot: IRRBBSourceSnapshot) -> None:
        self.snapshot = snapshot
        self.requested_cutoff: date | None = None

    def load_snapshot(self, *, cutoff_date: date) -> IRRBBSourceSnapshot:
        self.requested_cutoff = cutoff_date
        return self.snapshot


def test_load_use_case_reports_partial_readiness_without_calculating_risk() -> None:
    snapshot = IRRBBSourceSnapshot(
        cutoff_date=CUTOFF,
        position_records=(
            IRRBBPositionSourceRecord(position=_fixed_investment()),
            IRRBBPositionSourceRecord(
                position=_incomplete_credit(),
                validation_context=IRRBBValidationContext(
                    explicit_schedule_available=True,
                    scenario_repricing_model_available=True,
                ),
            ),
        ),
        source_references=("TEST:CANONICAL",),
    )
    gateway = _Gateway(snapshot)

    result = LoadIRRBBSourceSnapshot(gateway).execute(IRRBBSourceLoadRequest(CUTOFF))

    assert gateway.requested_cutoff == CUTOFF
    assert result.status is IRRBBSourceLoadStatus.PARTIAL
    assert result.ready_position_ids == ("INV-1",)
    assert result.incomplete_position_ids == ("LOAN-1",)
    assert result.excluded_position_ids == ()
    assert tuple(position.position_id for position in result.ready_positions) == ("INV-1",)


def test_empty_snapshot_is_explicitly_empty() -> None:
    snapshot = IRRBBSourceSnapshot(cutoff_date=CUTOFF, position_records=())

    result = LoadIRRBBSourceSnapshot(_Gateway(snapshot)).execute(
        IRRBBSourceLoadRequest(CUTOFF)
    )

    assert result.status is IRRBBSourceLoadStatus.EMPTY
    assert result.assessments == ()
    assert result.ready_positions == ()


def test_gateway_cannot_silently_return_a_different_cutoff() -> None:
    snapshot = IRRBBSourceSnapshot(
        cutoff_date=date(2026, 7, 31),
        position_records=(IRRBBPositionSourceRecord(position=_fixed_investment()),),
    )

    with pytest.raises(ValueError, match="different cutoff date"):
        LoadIRRBBSourceSnapshot(_Gateway(snapshot)).execute(IRRBBSourceLoadRequest(CUTOFF))


def test_snapshot_rejects_duplicate_canonical_position_ids() -> None:
    record = IRRBBPositionSourceRecord(position=_fixed_investment())

    with pytest.raises(ValueError, match="position_id values must be unique"):
        IRRBBSourceSnapshot(
            cutoff_date=CUTOFF,
            position_records=(record, record),
        )
