from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb import (
    IRRBBPositionSourceRecord,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
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


def test_source_acl_retains_mapping_failures_instead_of_dropping_records() -> None:
    records = (
        IRRBBSourceRecordEnvelope(
            source_record_id="ROW-1",
            source_reference="SOURCE:ROW-1",
            payload=_RawPosition(position_id="INV-1", principal=Decimal("1000")),
        ),
        IRRBBSourceRecordEnvelope(
            source_record_id="ROW-2",
            source_reference="SOURCE:ROW-2",
            payload=_RawPosition(position_id=None, principal=Decimal("500")),
        ),
    )

    snapshot = IRRBBSourceSnapshotAssembler(_Mapper()).assemble(
        cutoff_date=CUTOFF,
        source_records=records,
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
    record = IRRBBSourceRecordEnvelope(
        source_record_id="ROW-1",
        source_reference="SOURCE:ROW-1",
        payload=_RawPosition(position_id="INV-1", principal=Decimal("1000")),
    )

    with pytest.raises(ValueError, match="preserve source lineage"):
        IRRBBSourceSnapshotAssembler(_BadLineageMapper()).assemble(
            cutoff_date=CUTOFF,
            source_records=(record,),
        )
