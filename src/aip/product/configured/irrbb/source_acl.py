from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Generic, Protocol, TypeAlias, TypeVar

from aip.application.irrbb.contracts import (
    IRRBBCurveSourcePoint,
    IRRBBPositionSourceRecord,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
    IRRBBSourceSnapshot,
)
from aip.application.irrbb.source_certification import IRRBBSourceCertificationReport

SourceRecordT = TypeVar("SourceRecordT")


@dataclass(frozen=True, slots=True)
class IRRBBSourceRecordEnvelope(Generic[SourceRecordT]):
    """Opaque source record with stable lineage before canonical mapping.

    ``payload`` remains owned by the physical adapter. The ACL only requires a
    stable source-record identifier and source reference so failed mappings stay
    auditable without leaking SQL/XML/Excel/API field names into the canonical
    IRRBB contracts.
    """

    source_record_id: str
    source_reference: str
    payload: SourceRecordT

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise ValueError("source_record_id is required")
        if not self.source_reference.strip():
            raise ValueError("source_reference is required")


IRRBBCanonicalPositionMapResult: TypeAlias = IRRBBPositionSourceRecord | IRRBBSourceMappingFailure


class IRRBBCanonicalPositionMapper(Protocol[SourceRecordT]):
    """Map one adapter-owned source payload into the canonical IRRBB boundary."""

    def map_record(
        self,
        record: IRRBBSourceRecordEnvelope[SourceRecordT],
    ) -> IRRBBCanonicalPositionMapResult: ...


class IRRBBSourceSnapshotAssembler(Generic[SourceRecordT]):
    """Assemble a traceable canonical snapshot behind a certification gate.

    Mappers may return either a canonical position record or an explicit mapping
    failure. Failures are retained in the snapshot and are never converted into
    zero-valued positions or silently discarded. A source certification report is
    mandatory for every assembly call because source sufficiency can vary by cutoff
    and snapshot. The mapper is never invoked unless that report is ``READY``.
    """

    def __init__(self, mapper: IRRBBCanonicalPositionMapper[SourceRecordT]) -> None:
        self._mapper = mapper

    def assemble(
        self,
        *,
        cutoff_date: date,
        source_records: tuple[IRRBBSourceRecordEnvelope[SourceRecordT], ...],
        source_certification: IRRBBSourceCertificationReport,
        curve_points: tuple[IRRBBCurveSourcePoint, ...] = (),
        source_references: tuple[str, ...] = (),
    ) -> IRRBBSourceSnapshot:
        position_records: list[IRRBBPositionSourceRecord] = []
        mapping_failures: list[IRRBBSourceMappingFailure] = []

        if source_certification.is_ready:
            for source_record in source_records:
                mapped = self._mapper.map_record(source_record)
                self._validate_lineage(source_record=source_record, mapped=mapped)
                if isinstance(mapped, IRRBBSourceMappingFailure):
                    mapping_failures.append(mapped)
                else:
                    position_records.append(mapped)
        else:
            mapping_failures.extend(
                self._certification_rejection(
                    source_record=source_record,
                    certification=source_certification,
                )
                for source_record in source_records
            )

        lineage = self._unique_references(
            source_references
            + tuple(record.source_reference for record in source_records)
            + tuple(point.source_reference for point in curve_points)
        )
        return IRRBBSourceSnapshot(
            cutoff_date=cutoff_date,
            position_records=tuple(position_records),
            curve_points=curve_points,
            source_references=lineage,
            mapping_failures=tuple(mapping_failures),
        )

    @classmethod
    def _certification_rejection(
        cls,
        *,
        source_record: IRRBBSourceRecordEnvelope[SourceRecordT],
        certification: IRRBBSourceCertificationReport,
    ) -> IRRBBSourceMappingFailure:
        return IRRBBSourceMappingFailure(
            source_record_id=source_record.source_record_id,
            source_reference=source_record.source_reference,
            code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
            canonical_field=None,
            message=cls._certification_rejection_message(certification),
        )

    @staticmethod
    def _certification_rejection_message(
        certification: IRRBBSourceCertificationReport,
    ) -> str:
        details: list[str] = []
        if certification.blocking_requirement_ids:
            details.append(
                "blocking=" + ",".join(certification.blocking_requirement_ids)
            )
        if certification.not_assessed_requirement_ids:
            details.append(
                "not_assessed=" + ",".join(certification.not_assessed_requirement_ids)
            )
        unresolved = "; ".join(details) or "source requirements remain unresolved"
        return (
            "Canonical mapping rejected: source certification "
            f"{certification.profile.code}@{certification.profile.version} is "
            f"{certification.status.value}; {unresolved}."
        )

    @staticmethod
    def _validate_lineage(
        *,
        source_record: IRRBBSourceRecordEnvelope[SourceRecordT],
        mapped: IRRBBCanonicalPositionMapResult,
    ) -> None:
        if isinstance(mapped, IRRBBSourceMappingFailure):
            if mapped.source_record_id != source_record.source_record_id:
                raise ValueError("mapper changed source_record_id")
            if mapped.source_reference != source_record.source_reference:
                raise ValueError("mapper changed source_reference")
            return

        if mapped.position.source_reference != source_record.source_reference:
            raise ValueError("canonical position source_reference must preserve source lineage")

    @staticmethod
    def _unique_references(values: tuple[str, ...]) -> tuple[str, ...]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value.strip():
                raise ValueError("source references cannot contain blank values")
            if value in seen:
                continue
            seen.add(value)
            unique.append(value)
        return tuple(unique)
