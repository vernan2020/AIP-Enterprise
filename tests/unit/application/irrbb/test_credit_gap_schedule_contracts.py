from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb import (
    IRRBBCreditGapScheduleEntry,
    IRRBBCreditGapScheduleFailure,
    IRRBBCreditGapScheduleFailureCode,
    IRRBBCreditGapScheduleSnapshot,
)
from aip.domain.irrbb.models import CashFlowDirection
from aip.domain.irrbb.sugef_standard_gap import SugefGapScheduleRecord
from aip.shared.money import Currency, Money


def _record(*, currency: Currency = Currency.CRC) -> SugefGapScheduleRecord:
    return SugefGapScheduleRecord(
        payment_date=date(2026, 10, 15),
        amount=Money(Decimal("125.50"), currency),
        direction=CashFlowDirection.RECEIVABLE,
        flow_type="INSTALLMENT",
        source_reference="CONTRACTUAL_SOURCE:OP-1:2026-10-15",
        principal_component=Money(Decimal("100.00"), currency),
    )


def test_snapshot_requires_exactly_one_outcome_per_requested_operation() -> None:
    ready = IRRBBCreditGapScheduleEntry(
        operation_id="OP-1",
        schedule=(_record(),),
        source_reference="CONTRACTUAL_SOURCE:OP-1",
    )
    missing = IRRBBCreditGapScheduleFailure(
        operation_id="OP-2",
        code=IRRBBCreditGapScheduleFailureCode.NOT_FOUND,
        message="No governed contractual schedule was returned.",
    )

    snapshot = IRRBBCreditGapScheduleSnapshot(
        cutoff_date=date(2026, 9, 30),
        requested_operation_ids=("OP-1", "OP-2"),
        entries=(ready,),
        failures=(missing,),
        source_references=("CONTRACTUAL_SOURCE:2026-09-30",),
    )

    assert snapshot.entries == (ready,)
    assert snapshot.failures == (missing,)


def test_snapshot_rejects_silent_loss_of_requested_operation() -> None:
    ready = IRRBBCreditGapScheduleEntry(
        operation_id="OP-1",
        schedule=(_record(),),
        source_reference="CONTRACTUAL_SOURCE:OP-1",
    )

    with pytest.raises(ValueError, match="exactly one schedule outcome"):
        IRRBBCreditGapScheduleSnapshot(
            cutoff_date=date(2026, 9, 30),
            requested_operation_ids=("OP-1", "OP-2"),
            entries=(ready,),
        )


def test_entry_rejects_mixed_currency_schedule() -> None:
    with pytest.raises(ValueError, match="single currency"):
        IRRBBCreditGapScheduleEntry(
            operation_id="OP-1",
            schedule=(
                _record(currency=Currency.CRC),
                _record(currency=Currency.USD),
            ),
            source_reference="CONTRACTUAL_SOURCE:OP-1",
        )


def test_snapshot_rejects_operation_that_is_both_ready_and_failed() -> None:
    ready = IRRBBCreditGapScheduleEntry(
        operation_id="OP-1",
        schedule=(_record(),),
        source_reference="CONTRACTUAL_SOURCE:OP-1",
    )
    failed = IRRBBCreditGapScheduleFailure(
        operation_id="OP-1",
        code=IRRBBCreditGapScheduleFailureCode.INVALID_SCHEDULE,
        message="Schedule failed source validation.",
        source_reference="CONTRACTUAL_SOURCE:OP-1",
    )

    with pytest.raises(ValueError, match="both ready and failed"):
        IRRBBCreditGapScheduleSnapshot(
            cutoff_date=date(2026, 9, 30),
            requested_operation_ids=("OP-1",),
            entries=(ready,),
            failures=(failed,),
        )
