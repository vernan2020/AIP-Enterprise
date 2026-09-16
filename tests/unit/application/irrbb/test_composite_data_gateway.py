from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.application.irrbb.composite_data_gateway import (
    CompositeIRRBBDataGateway,
    IRRBBDataGatewayBinding,
)
from aip.application.irrbb.contracts import (
    IRRBBCurveSourcePoint,
    IRRBBPositionSourceRecord,
    IRRBBSourceSnapshot,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    IRRBBScenario,
    PaymentStructure,
    RateType,
)
from aip.shared.money import Currency, Money

CUTOFF = date(2026, 8, 31)


class _Gateway:
    def __init__(self, snapshot: IRRBBSourceSnapshot) -> None:
        self.snapshot = snapshot
        self.requested_cutoffs: list[date] = []

    def load_snapshot(self, *, cutoff_date: date) -> IRRBBSourceSnapshot:
        self.requested_cutoffs.append(cutoff_date)
        return self.snapshot


def _record(
    position_id: str,
    instrument_class: IRRBBInstrumentClass,
    side: BankingBookSide,
    source: str,
    currency: Currency = Currency.CRC,
) -> IRRBBPositionSourceRecord:
    return IRRBBPositionSourceRecord(
        position=BankingBookPosition(
            position_id=position_id,
            product_type=instrument_class.value,
            side=side,
            currency=currency,
            principal=Money(Decimal("1000"), currency),
            rate_type=RateType.FIXED,
            maturity_date=date(2028, 8, 31),
            source_reference=source,
            contractual_rate=Decimal("0.06"),
            payment_frequency_months=1,
            instrument_class=instrument_class,
            payment_structure=PaymentStructure.BULLET,
        )
    )


def _curve(rate: str, source: str = "CURVE:OFFICIAL") -> IRRBBCurveSourcePoint:
    return IRRBBCurveSourcePoint(
        curve_id="CRC_BASE",
        as_of_date=CUTOFF,
        currency=Currency.CRC,
        scenario=IRRBBScenario.BASE,
        tenor_years=Decimal("1"),
        rate=Decimal(rate),
        source_reference=source,
    )


def test_composite_gateway_merges_credit_deposits_and_borrowings_same_cutoff() -> None:
    credit = _Gateway(
        IRRBBSourceSnapshot(
            cutoff_date=CUTOFF,
            position_records=(
                _record(
                    "CR-1",
                    IRRBBInstrumentClass.CREDIT,
                    BankingBookSide.ASSET,
                    "POWERBI:CREDITO:CR-1",
                ),
            ),
            curve_points=(_curve("0.05"),),
            source_references=("POWERBI:CREDITO", "CURVE:OFFICIAL"),
        )
    )
    deposits = _Gateway(
        IRRBBSourceSnapshot(
            cutoff_date=CUTOFF,
            position_records=(
                _record(
                    "CDP-1",
                    IRRBBInstrumentClass.TERM_DEPOSIT,
                    BankingBookSide.LIABILITY,
                    "POWERBI:CAPTACIONES:CDP-1",
                ),
            ),
            curve_points=(_curve("0.05"),),
            source_references=("POWERBI:CAPTACIONES", "CURVE:OFFICIAL"),
        )
    )
    borrowings = _Gateway(
        IRRBBSourceSnapshot(
            cutoff_date=CUTOFF,
            position_records=(
                _record(
                    "OBL-1",
                    IRRBBInstrumentClass.BORROWING,
                    BankingBookSide.LIABILITY,
                    "EXCEL:OBLIGACIONES:OBL-1",
                    Currency.USD,
                ),
            ),
            source_references=("EXCEL:OBLIGACIONES",),
        )
    )

    gateway = CompositeIRRBBDataGateway(
        (
            IRRBBDataGatewayBinding("credit", credit),
            IRRBBDataGatewayBinding("term_deposit", deposits),
            IRRBBDataGatewayBinding("borrowing", borrowings),
        )
    )
    snapshot = gateway.load_snapshot(cutoff_date=CUTOFF)

    assert credit.requested_cutoffs == [CUTOFF]
    assert deposits.requested_cutoffs == [CUTOFF]
    assert borrowings.requested_cutoffs == [CUTOFF]
    assert tuple(record.position.position_id for record in snapshot.position_records) == (
        "CR-1",
        "CDP-1",
        "OBL-1",
    )
    assert snapshot.curve_points == (_curve("0.05"),)
    assert snapshot.source_references == (
        "POWERBI:CREDITO",
        "CURVE:OFFICIAL",
        "POWERBI:CAPTACIONES",
        "EXCEL:OBLIGACIONES",
    )
    assert snapshot.mapping_failures == ()


def test_composite_gateway_excludes_duplicate_position_id_and_reports_failure() -> None:
    left = _Gateway(
        IRRBBSourceSnapshot(
            cutoff_date=CUTOFF,
            position_records=(
                _record(
                    "DUP-1",
                    IRRBBInstrumentClass.CREDIT,
                    BankingBookSide.ASSET,
                    "SOURCE-A:DUP-1",
                ),
            ),
        )
    )
    right = _Gateway(
        IRRBBSourceSnapshot(
            cutoff_date=CUTOFF,
            position_records=(
                _record(
                    "DUP-1",
                    IRRBBInstrumentClass.BORROWING,
                    BankingBookSide.LIABILITY,
                    "SOURCE-B:DUP-1",
                ),
            ),
        )
    )

    snapshot = CompositeIRRBBDataGateway(
        (
            IRRBBDataGatewayBinding("source-a", left),
            IRRBBDataGatewayBinding("source-b", right),
        )
    ).load_snapshot(cutoff_date=CUTOFF)

    assert snapshot.position_records == ()
    assert len(snapshot.mapping_failures) == 1
    failure = snapshot.mapping_failures[0]
    assert failure.canonical_field == "position_id"
    assert "doble conteo" in failure.message
    assert "source-a" in failure.message
    assert "source-b" in failure.message


def test_composite_gateway_deduplicates_identical_curve_points() -> None:
    point = _curve("0.05")
    gateway = CompositeIRRBBDataGateway(
        (
            IRRBBDataGatewayBinding(
                "credit",
                _Gateway(IRRBBSourceSnapshot(CUTOFF, (), curve_points=(point,))),
            ),
            IRRBBDataGatewayBinding(
                "deposits",
                _Gateway(IRRBBSourceSnapshot(CUTOFF, (), curve_points=(point,))),
            ),
        )
    )

    snapshot = gateway.load_snapshot(cutoff_date=CUTOFF)

    assert snapshot.curve_points == (point,)
    assert snapshot.mapping_failures == ()


def test_composite_gateway_excludes_conflicting_curve_point_and_reports_failure() -> None:
    gateway = CompositeIRRBBDataGateway(
        (
            IRRBBDataGatewayBinding(
                "credit",
                _Gateway(IRRBBSourceSnapshot(CUTOFF, (), curve_points=(_curve("0.05"),))),
            ),
            IRRBBDataGatewayBinding(
                "deposits",
                _Gateway(IRRBBSourceSnapshot(CUTOFF, (), curve_points=(_curve("0.06"),))),
            ),
        )
    )

    snapshot = gateway.load_snapshot(cutoff_date=CUTOFF)

    assert snapshot.curve_points == ()
    assert len(snapshot.mapping_failures) == 1
    assert snapshot.mapping_failures[0].canonical_field == "curve_points"
    assert "conflictivos" in snapshot.mapping_failures[0].message
