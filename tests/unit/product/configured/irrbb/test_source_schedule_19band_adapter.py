from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb.contracts import (
    IRRBBPositionSourceRecord,
    IRRBBSourceSnapshot,
)
from aip.application.irrbb.source_certification import (
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationReport,
    IRRBBSourceCertificationService,
    IRRBBSourceCertificationStatus,
    IRRBBSourcePerimeter,
    IRRBBSourceRequirement,
    IRRBBSourceRequirementAssessment,
    IRRBBSourceRequirementProfile,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowDirection,
    IRRBBInstrumentClass,
    OptionalityType,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.sugef_standard_gap import SugefGapScheduleRecord
from aip.product.configured.irrbb.source_schedule_19band_adapter import (
    bridge_certified_fixed_schedules,
)
from aip.shared.money import Currency, Money

CUTOFF = date(2026, 9, 30)


def _certification(
    status: IRRBBSourceCertificationStatus = IRRBBSourceCertificationStatus.READY,
) -> IRRBBSourceCertificationReport:
    profile = IRRBBSourceRequirementProfile(
        code="SCHEDULE-UNIT",
        version="1",
        effective_from=CUTOFF,
        source_reference="CERTIFIED-TEST-SOURCE",
        requirements=(
            IRRBBSourceRequirement(
                requirement_id="SCHED",
                canonical_variable="contractual_schedule",
                perimeter=IRRBBSourcePerimeter.COMMON,
                description="Source-provided dated contractual payment schedule",
            ),
        ),
    )
    readiness = (
        IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
        if status is IRRBBSourceCertificationStatus.READY
        else IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_GAP
    )
    return IRRBBSourceCertificationService.certify(
        profile=profile,
        assessments=(
            IRRBBSourceRequirementAssessment(
                requirement_id="SCHED",
                status=readiness,
                source_reference=(
                    "CERTIFIED-TEST-SOURCE"
                    if status is IRRBBSourceCertificationStatus.READY
                    else None
                ),
                evidence_reference=(
                    "VERIFIED-SCHEDULE" if status is IRRBBSourceCertificationStatus.READY else None
                ),
            ),
        ),
    )


def _record() -> IRRBBPositionSourceRecord:
    position = BankingBookPosition(
        position_id="T-001",
        product_type="CERTIFICATE",
        side=BankingBookSide.LIABILITY,
        currency=Currency.CRC,
        principal=Money(Decimal("100.15"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2027, 1, 31),
        source_reference="XML-210-CAPF",
        optionality=OptionalityType.NONE,
        payment_structure=PaymentStructure.BULLET,
        instrument_class=IRRBBInstrumentClass.TERM_DEPOSIT,
    )
    cashflows = (
        SugefGapScheduleRecord(
            payment_date=date(2026, 10, 31),
            amount=Money(Decimal("2.50"), Currency.CRC),
            direction=CashFlowDirection.PAYABLE,
            flow_type="INTEREST",
            source_reference="CERTIFICATE:COUPON:1",
        ),
        SugefGapScheduleRecord(
            payment_date=date(2027, 1, 31),
            amount=Money(Decimal("100.15"), Currency.CRC),
            direction=CashFlowDirection.PAYABLE,
            flow_type="PRINCIPAL",
            source_reference="CERTIFICATE:PRINCIPAL",
        ),
    )
    return IRRBBPositionSourceRecord(
        position=position,
        gap_schedule=cashflows,
        mapping_rule_reference="VERSIONED-REAL-SOURCE-RULE",
    )


def _snapshot(
    record: IRRBBPositionSourceRecord | None = None,
) -> IRRBBSourceSnapshot:
    return IRRBBSourceSnapshot(
        cutoff_date=CUTOFF,
        position_records=(record or _record(),),
        source_references=("SOURCE-XML-210-AND-CAPF",),
    )


def test_certified_source_schedule_bands_principal_and_interest_without_inference():
    result = bridge_certified_fixed_schedules(snapshot=_snapshot(), certification=_certification())
    assert result.certified_positions == 1
    assert result.source_flows == 2
    assert result.status == "FIXED_SCHEDULE_EVIDENCE_ONLY_NOT_CERTIFIED_GAP"
    assert result.publishable_regulatory_gap is False
    assert result.evidence.total_flows == 2
    assert result.evidence.included_segments == ("CAPTACIONES",)
    assert len(result.evidence.rows) == 19
    assert sum(row.liabilities for row in result.evidence.rows) == Decimal("102.65")
    assert sum(row.assets for row in result.evidence.rows) == 0


def test_rejects_uncertified_snapshots_and_missing_schedule():
    with pytest.raises(ValueError, match="not READY"):
        bridge_certified_fixed_schedules(
            snapshot=_snapshot(),
            certification=_certification(IRRBBSourceCertificationStatus.BLOCKED),
        )
    with pytest.raises(ValueError, match="schedule is missing"):
        bridge_certified_fixed_schedules(
            snapshot=_snapshot(replace(_record(), gap_schedule=())),
            certification=_certification(),
        )


def test_rejects_floating_instruments_without_repricing_residual():
    floating_position = replace(_record().position, rate_type=RateType.FLOATING)
    with pytest.raises(ValueError, match="Floating-rate repricing"):
        bridge_certified_fixed_schedules(
            snapshot=_snapshot(replace(_record(), position=floating_position)),
            certification=_certification(),
        )


def test_rejects_unapproved_optionality_and_dates():
    original = _record()
    with pytest.raises(ValueError, match="optionality"):
        bridge_certified_fixed_schedules(
            snapshot=_snapshot(
                replace(
                    original,
                    position=replace(
                        original.position, optionality=OptionalityType.TERM_DEPOSIT_EARLY_WITHDRAWAL
                    ),
                )
            ),
            certification=_certification(),
        )
    invalid_payment = replace(original.gap_schedule[0], payment_date=date(2027, 2, 1))
    with pytest.raises(ValueError, match="exceeds certified maturity"):
        bridge_certified_fixed_schedules(
            snapshot=_snapshot(
                replace(original, gap_schedule=(invalid_payment, *original.gap_schedule[1:]))
            ),
            certification=_certification(),
        )


def test_rejects_incompatible_cashflow_currency():
    record = _record()
    payment = replace(
        record.gap_schedule[0],
        amount=Money(Decimal("2.50"), Currency.USD),
    )
    with pytest.raises(ValueError, match="schedule currency"):
        bridge_certified_fixed_schedules(
            snapshot=_snapshot(replace(record, gap_schedule=(payment, record.gap_schedule[1]))),
            certification=_certification(),
        )


def test_rejects_unbalanced_principal_schedule():
    original = _record()
    incorrect_payment = replace(
        original.gap_schedule[1],
        amount=Money(Decimal("99.99"), Currency.CRC),
    )
    with pytest.raises(ValueError, match="principal payments do not match"):
        bridge_certified_fixed_schedules(
            snapshot=_snapshot(
                replace(
                    original,
                    gap_schedule=(original.gap_schedule[0], incorrect_payment),
                )
            ),
            certification=_certification(),
        )


def test_all_four_certified_segments_bandeo_keeps_asset_liability_sides_separate():
    records = []
    for position_id, instrument, side, direction in (
        (
            "CREDIT-1",
            IRRBBInstrumentClass.CREDIT,
            BankingBookSide.ASSET,
            CashFlowDirection.RECEIVABLE,
        ),
        (
            "INV-1",
            IRRBBInstrumentClass.INVESTMENT,
            BankingBookSide.ASSET,
            CashFlowDirection.RECEIVABLE,
        ),
        (
            "CAP-1",
            IRRBBInstrumentClass.TERM_DEPOSIT,
            BankingBookSide.LIABILITY,
            CashFlowDirection.PAYABLE,
        ),
        (
            "BORROW-1",
            IRRBBInstrumentClass.BORROWING,
            BankingBookSide.LIABILITY,
            CashFlowDirection.PAYABLE,
        ),
    ):
        original = _record()
        position = replace(
            original.position,
            position_id=position_id,
            instrument_class=instrument,
            side=side,
            source_reference=f"SOURCE:{position_id}",
        )
        schedule = tuple(
            replace(
                payment,
                direction=direction,
                source_reference=f"{position_id}:{index}",
            )
            for index, payment in enumerate(original.gap_schedule)
        )
        records.append(replace(original, position=position, gap_schedule=schedule))
    snapshot = IRRBBSourceSnapshot(
        cutoff_date=CUTOFF,
        position_records=tuple(records),
        source_references=("CERTIFIED-SOURCE-PERIMETER-FOUR-SEGMENTS",),
    )
    result = bridge_certified_fixed_schedules(
        snapshot=snapshot,
        certification=_certification(),
    )
    assert result.certified_positions == 4
    assert result.source_flows == 8
    assert result.evidence.missing_segments == ()
    assert result.evidence.included_segments == (
        "BORROWING",
        "CAPTACIONES",
        "CREDIT",
        "INVESTMENT",
    )
    assert sum(row.assets for row in result.evidence.rows) == Decimal("205.30")
    assert sum(row.liabilities for row in result.evidence.rows) == Decimal("205.30")
    assert not result.publishable_regulatory_gap
