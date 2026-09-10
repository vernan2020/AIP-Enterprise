from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb import (
    IRRBBPositionSourceRecord,
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationReport,
    IRRBBSourceCertificationService,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
    IRRBBSourcePerimeter,
    IRRBBSourceRequirement,
    IRRBBSourceRequirementAssessment,
    IRRBBSourceRequirementProfile,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBInstrumentClass,
    PaymentStructure,
    RateType,
)
from aip.product.configured.irrbb import IRRBBSourceRecordEnvelope, IRRBBSourceSnapshotAssembler
from aip.shared.money import Currency, Money

CUTOFF = date(2026, 8, 31)


@dataclass(frozen=True, slots=True)
class _RawPosition:
    position_id: str | None
    principal: Decimal


class _Mapper:
    def map_record(
        self,
        record: IRRBBSourceRecordEnvelope[_RawPosition],
    ) -> IRRBBPositionSourceRecord | IRRBBSourceMappingFailure:
        if record.payload.position_id is None:
            return IRRBBSourceMappingFailure(
                source_record_id=record.source_record_id,
                source_reference=record.source_reference,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="position_id",
                message="Canonical position_id is unavailable in the source record.",
            )

        return IRRBBPositionSourceRecord(
            position=BankingBookPosition(
                position_id=record.payload.position_id,
                product_type="TEST_BOND",
                side=BankingBookSide.ASSET,
                currency=Currency.CRC,
                principal=Money(record.payload.principal, Currency.CRC),
                rate_type=RateType.FIXED,
                maturity_date=date(2028, 8, 31),
                source_reference=record.source_reference,
                contractual_rate=Decimal("0.06"),
                payment_frequency_months=6,
                instrument_class=IRRBBInstrumentClass.INVESTMENT,
                payment_structure=PaymentStructure.BULLET,
            )
        )


class _BadLineageMapper(_Mapper):
    def map_record(
        self,
        record: IRRBBSourceRecordEnvelope[_RawPosition],
    ) -> IRRBBPositionSourceRecord | IRRBBSourceMappingFailure:
        mapped = super().map_record(record)
        if isinstance(mapped, IRRBBSourceMappingFailure):
            return mapped
        position = mapped.position
        return IRRBBPositionSourceRecord(
            position=BankingBookPosition(
                position_id=position.position_id,
                product_type=position.product_type,
                side=position.side,
                currency=position.currency,
                principal=position.principal,
                rate_type=position.rate_type,
                maturity_date=position.maturity_date,
                source_reference="DIFFERENT:SOURCE",
                contractual_rate=position.contractual_rate,
                payment_frequency_months=position.payment_frequency_months,
                instrument_class=position.instrument_class,
                payment_structure=position.payment_structure,
            )
        )


class _NeverCalledMapper:
    def map_record(
        self,
        record: IRRBBSourceRecordEnvelope[_RawPosition],
    ) -> IRRBBPositionSourceRecord | IRRBBSourceMappingFailure:
        raise AssertionError(f"mapper must not run for uncertified record {record.source_record_id}")


def _profile() -> IRRBBSourceRequirementProfile:
    return IRRBBSourceRequirementProfile(
        code="RTILB-TEST-SOURCE",
        version="2026.1",
        effective_from=CUTOFF,
        source_reference="TEST:SOURCE-CERTIFICATION",
        requirements=(
            IRRBBSourceRequirement(
                requirement_id="REQ-POSITION-ID",
                canonical_variable="position_id",
                perimeter=IRRBBSourcePerimeter.INVESTMENT,
                description="Stable source position identity",
            ),
        ),
    )


def _ready_certification() -> IRRBBSourceCertificationReport:
    return IRRBBSourceCertificationService.certify(
        profile=_profile(),
        assessments=(
            IRRBBSourceRequirementAssessment(
                requirement_id="REQ-POSITION-ID",
                status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
                source_reference="SOURCE:BATCH",
                evidence_reference="EVIDENCE:POSITION-ID",
            ),
        ),
    )


def _incomplete_certification() -> IRRBBSourceCertificationReport:
    return IRRBBSourceCertificationService.certify(
        profile=_profile(),
        assessments=(),
    )


def _blocked_certification() -> IRRBBSourceCertificationReport:
    return IRRBBSourceCertificationService.certify(
        profile=_profile(),
        assessments=(
            IRRBBSourceRequirementAssessment(
                requirement_id="REQ-POSITION-ID",
                status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
                notes="Stable position identity is unavailable.",
            ),
        ),
    )


def _record(
    source_record_id: str,
    *,
    position_id: str | None,
    principal: str = "1000",
) -> IRRBBSourceRecordEnvelope[_RawPosition]:
    return IRRBBSourceRecordEnvelope(
        source_record_id=source_record_id,
        source_reference=f"SOURCE:{source_record_id}",
        payload=_RawPosition(
            position_id=position_id,
            principal=Decimal(principal),
        ),
    )


def test_source_acl_retains_mapping_failures_instead_of_dropping_records() -> None:
    records = (
        _record("ROW-1", position_id="INV-1"),
        _record("ROW-2", position_id=None, principal="500"),
    )

    snapshot = IRRBBSourceSnapshotAssembler(_Mapper()).assemble(
        cutoff_date=CUTOFF,
        source_records=records,
        source_certification=_ready_certification(),
        source_references=("SOURCE:BATCH",),
    )

    assert tuple(position.position_id for position in snapshot.positions) == ("INV-1",)
    assert tuple(failure.source_record_id for failure in snapshot.mapping_failures) == ("ROW-2",)
    assert snapshot.mapping_failures[0].code is (
        IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD
    )
    assert snapshot.source_references == (
        "SOURCE:BATCH",
        "SOURCE:ROW-1",
        "SOURCE:ROW-2",
    )


def test_source_acl_rejects_mapper_that_breaks_source_lineage() -> None:
    record = _record("ROW-1", position_id="INV-1")

    with pytest.raises(ValueError, match="preserve source lineage"):
        IRRBBSourceSnapshotAssembler(_BadLineageMapper()).assemble(
            cutoff_date=CUTOFF,
            source_records=(record,),
            source_certification=_ready_certification(),
        )


def test_incomplete_certification_rejects_every_record_without_invoking_mapper() -> None:
    records = (
        _record("ROW-1", position_id="INV-1"),
        _record("ROW-2", position_id="INV-2"),
    )

    snapshot = IRRBBSourceSnapshotAssembler(_NeverCalledMapper()).assemble(
        cutoff_date=CUTOFF,
        source_records=records,
        source_certification=_incomplete_certification(),
        source_references=("SOURCE:BATCH",),
    )

    assert snapshot.position_records == ()
    assert tuple(failure.source_record_id for failure in snapshot.mapping_failures) == (
        "ROW-1",
        "ROW-2",
    )
    assert all(
        failure.code is IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED
        for failure in snapshot.mapping_failures
    )
    assert all(failure.canonical_field is None for failure in snapshot.mapping_failures)
    assert all(
        "RTILB-TEST-SOURCE@2026.1 is INCOMPLETE" in failure.message
        for failure in snapshot.mapping_failures
    )
    assert all(
        "not_assessed=REQ-POSITION-ID" in failure.message
        for failure in snapshot.mapping_failures
    )
    assert snapshot.source_references == (
        "SOURCE:BATCH",
        "SOURCE:ROW-1",
        "SOURCE:ROW-2",
    )


def test_blocked_certification_rejects_record_with_blocking_evidence_trace() -> None:
    record = _record("ROW-1", position_id="INV-1")

    snapshot = IRRBBSourceSnapshotAssembler(_NeverCalledMapper()).assemble(
        cutoff_date=CUTOFF,
        source_records=(record,),
        source_certification=_blocked_certification(),
    )

    assert snapshot.position_records == ()
    assert len(snapshot.mapping_failures) == 1
    failure = snapshot.mapping_failures[0]
    assert failure.source_record_id == "ROW-1"
    assert failure.source_reference == "SOURCE:ROW-1"
    assert failure.code is IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED
    assert failure.canonical_field is None
    assert "RTILB-TEST-SOURCE@2026.1 is BLOCKED" in failure.message
    assert "blocking=REQ-POSITION-ID" in failure.message
