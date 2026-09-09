from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from aip.domain.irrbb.data_quality import IRRBBPositionAssessment, IRRBBValidationContext
from aip.domain.irrbb.models import BankingBookPosition, IRRBBScenario
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapRoutingMetadata,
    SugefGapScheduleRecord,
)
from aip.shared.money import Currency


class IRRBBSourceLoadStatus(str, Enum):
    """Aggregate readiness of a source snapshot before IRRBB calculation."""

    EMPTY = "EMPTY"
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class IRRBBSourceLoadRequest:
    """Source-agnostic request to load one banking-book valuation cutoff."""

    cutoff_date: date


@dataclass(frozen=True, slots=True)
class IRRBBPositionSourceRecord:
    """Canonical position plus source capabilities required for readiness checks.

    The record intentionally carries no SQL/XML/Excel fields. Physical adapters are
    responsible for normalizing their source into the domain contract before this
    boundary is crossed.
    """

    position: BankingBookPosition
    validation_context: IRRBBValidationContext = IRRBBValidationContext()
    gap_schedule: tuple[SugefGapScheduleRecord, ...] = ()
    gap_routing_metadata: SugefGapRoutingMetadata | None = None

    def __post_init__(self) -> None:
        metadata = self.gap_routing_metadata
        if metadata is not None and metadata.position_id != self.position.position_id:
            raise ValueError("gap routing metadata position_id must match the position")
        for record in self.gap_schedule:
            if record.amount.currency is not self.position.currency:
                raise ValueError("gap schedule currency must match the position currency")


@dataclass(frozen=True, slots=True)
class IRRBBCurveSourcePoint:
    """Auditable source curve point carried to the application calculation boundary."""

    curve_id: str
    as_of_date: date
    currency: Currency
    scenario: IRRBBScenario
    tenor_years: Decimal
    rate: Decimal
    source_reference: str

    def __post_init__(self) -> None:
        if not self.curve_id.strip():
            raise ValueError("curve_id is required")
        if self.tenor_years < 0:
            raise ValueError("curve tenor_years cannot be negative")
        if not self.source_reference.strip():
            raise ValueError("curve source_reference is required")


@dataclass(frozen=True, slots=True)
class IRRBBSourceSnapshot:
    """Normalized source snapshot independent of the physical ingestion technology."""

    cutoff_date: date
    position_records: tuple[IRRBBPositionSourceRecord, ...]
    curve_points: tuple[IRRBBCurveSourcePoint, ...] = ()
    source_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifiers = tuple(record.position.position_id for record in self.position_records)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("IRRBB source snapshot position_id values must be unique")
        for source_reference in self.source_references:
            if not source_reference.strip():
                raise ValueError("source_references cannot contain blank values")

    @property
    def positions(self) -> tuple[BankingBookPosition, ...]:
        return tuple(record.position for record in self.position_records)


@dataclass(frozen=True, slots=True)
class IRRBBSourceLoadResult:
    """Validated source load result; no EVE or GAP amounts are calculated here."""

    snapshot: IRRBBSourceSnapshot
    assessments: tuple[IRRBBPositionAssessment, ...]
    status: IRRBBSourceLoadStatus
    ready_position_ids: tuple[str, ...]
    incomplete_position_ids: tuple[str, ...]
    excluded_position_ids: tuple[str, ...]

    @property
    def ready_positions(self) -> tuple[BankingBookPosition, ...]:
        ready = set(self.ready_position_ids)
        return tuple(
            position for position in self.snapshot.positions if position.position_id in ready
        )
