from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from aip.domain.irrbb.sugef_standard_gap import SugefGapScheduleRecord


class IRRBBCreditGapScheduleFailureCode(str, Enum):
    """Stable failure codes for the governed Credit GAP schedule complement."""

    NOT_FOUND = "NOT_FOUND"
    INVALID_SCHEDULE = "INVALID_SCHEDULE"
    SOURCE_ERROR = "SOURCE_ERROR"


@dataclass(frozen=True, slots=True)
class IRRBBCreditGapScheduleEntry:
    """Contractual GAP schedule supplied for one canonical credit operation."""

    operation_id: str
    schedule: tuple[SugefGapScheduleRecord, ...]
    source_reference: str

    def __post_init__(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("credit GAP schedule operation_id is required")
        if not self.schedule:
            raise ValueError("credit GAP schedule cannot be empty")
        if not self.source_reference.strip():
            raise ValueError("credit GAP schedule source_reference is required")

        currencies = {record.amount.currency for record in self.schedule}
        if len(currencies) != 1:
            raise ValueError("credit GAP schedule must use a single currency per operation")


@dataclass(frozen=True, slots=True)
class IRRBBCreditGapScheduleFailure:
    """Auditable failure for one requested contractual credit schedule."""

    operation_id: str
    code: IRRBBCreditGapScheduleFailureCode
    message: str
    source_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("credit GAP schedule failure operation_id is required")
        if not self.message.strip():
            raise ValueError("credit GAP schedule failure message is required")
        if self.source_reference is not None and not self.source_reference.strip():
            raise ValueError("credit GAP schedule failure source_reference cannot be blank")


@dataclass(frozen=True, slots=True)
class IRRBBCreditGapScheduleSnapshot:
    """Complete outcome set for a requested Credit GAP contractual complement.

    Every requested operation must be represented exactly once as either a
    contractual schedule entry or an explicit failure. This prevents silent record
    loss and keeps the physical source technology outside the IRRBB domain.
    """

    cutoff_date: date
    requested_operation_ids: tuple[str, ...]
    entries: tuple[IRRBBCreditGapScheduleEntry, ...]
    failures: tuple[IRRBBCreditGapScheduleFailure, ...] = ()
    source_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        requested = self.requested_operation_ids
        if not requested:
            raise ValueError("credit GAP schedule request must contain operation ids")
        if any(not operation_id.strip() for operation_id in requested):
            raise ValueError("credit GAP schedule requested operation ids cannot be blank")
        if len(requested) != len(set(requested)):
            raise ValueError("credit GAP schedule requested operation ids must be unique")

        entry_ids = tuple(entry.operation_id for entry in self.entries)
        failure_ids = tuple(failure.operation_id for failure in self.failures)
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError("credit GAP schedule entry operation ids must be unique")
        if len(failure_ids) != len(set(failure_ids)):
            raise ValueError("credit GAP schedule failure operation ids must be unique")
        if set(entry_ids) & set(failure_ids):
            raise ValueError("credit GAP schedule operation cannot be both ready and failed")

        represented = set(entry_ids) | set(failure_ids)
        if represented != set(requested):
            raise ValueError(
                "every requested credit operation must have exactly one schedule outcome"
            )

        for source_reference in self.source_references:
            if not source_reference.strip():
                raise ValueError("credit GAP schedule source references cannot be blank")
