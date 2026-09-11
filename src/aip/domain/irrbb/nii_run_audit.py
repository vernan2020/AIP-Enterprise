from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.domain.irrbb.nii_reproducibility import NIIRunEvidenceManifest
from aip.domain.irrbb.nii_run_specification import (
    NIIMethodologyRunResult,
    NIIMethodologyRunSpecification,
)


class NIIRunAuditWriteStatus(str, Enum):
    """Outcome of an immutable NII audit-record write."""

    STORED = "STORED"
    IDEMPOTENT = "IDEMPOTENT"


class NIIRunAuditConflictError(ValueError):
    """Raised when an existing run reference conflicts with a submitted audit record."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditRecord:
    """Immutable auditable bundle for one completed NII methodology run."""

    specification: NIIMethodologyRunSpecification
    manifest: NIIRunEvidenceManifest
    result: NIIMethodologyRunResult

    def __post_init__(self) -> None:
        if self.manifest.run_reference != self.specification.run_reference:
            raise ValueError("NII audit manifest substituted run_reference")
        if self.result.specification != self.specification:
            raise ValueError("NII audit result substituted methodology run specification")

    @property
    def run_reference(self) -> str:
        return self.specification.run_reference

    @property
    def specification_fingerprint(self) -> str:
        return self.manifest.specification_fingerprint


@dataclass(frozen=True, slots=True)
class NIIRunAuditRepositoryPutResult:
    """Atomic repository response for insert-if-absent semantics."""

    created: bool
    record: NIIRunAuditRecord


@dataclass(frozen=True, slots=True)
class NIIRunAuditWriteResult:
    """Public domain outcome of an immutable audit-record write."""

    status: NIIRunAuditWriteStatus
    record: NIIRunAuditRecord
